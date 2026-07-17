"""
core/fund_addresses.py — a canonical office-address book for the fund universe,
so the NDR itinerary can route real driving distances without an address being
typed into every single meeting.

WHY THIS EXISTS
The routing upgrade (core/routing.py) only produces real driving miles when a
stop has a real street address. Typing one per meeting doesn't scale, and the
same fund recurs across trips — so an address belongs to the FUND, once.

RESOLUTION ORDER (see page_modules_nicegui/investors_page._meeting_street):
  1. the meeting's own address     (per-meeting override — conference venue,
                                     satellite office, a one-off location)
  2. this address book, by fund    (the fund's office; SEC-sourced or manual)
  3. the fund's metro / trip city   (city-center fallback — no street level)

WHERE ADDRESSES COME FROM — best → worst:
  * SEC EDGAR business address BY CIK. Authoritative, current, free, and exact
    because there's no name-matching: every 13F/13D-G filer already carries a
    CIK in our holder data. `refresh_from_sec()` walks those CIKs and stores the
    filing's business address. This is the scalable backbone.
  * Manual entry (`set_address`) for funds with no SEC filing, for a specific
    office that isn't the registered HQ, or to correct a bad auto-match.
  * A small hand-verified SEED below for the funds on the near-term NDR calendar
    so those trips route immediately, before any pull is run.

NAME→CIK lookup is deliberately NOT done automatically: it false-matches badly
("BlackRock" resolves to a tiny Isle-of-Man subsidiary; "Vanguard Group" misses
entirely). Addresses for non-holder prospects are better filled by CIK when they
become holders, or entered manually after a human confirms the entity.
"""

import re

import requests

from core import db

_STORE = "fund_addresses.json"
_UA = {"User-Agent": "PraxisPoint IR robbreza@yahoo.com"}

# Hand-verified office addresses for funds on the near-term NDR calendar, so
# those trips route before any SEC pull is run. hq_metro flags the metro the
# office actually sits in — used to warn when a meeting is scheduled on a trip to
# a different city (e.g. an "NYC" meeting with a fund HQ'd in Cleveland).
_SEED = {
    "BlackRock Small Cap Growth": {"address": "50 Hudson Yards, New York, NY 10001",
                                   "hq_metro": "New York Metro", "source": "seed"},
    "Royce Investment Partners":  {"address": "One Madison Avenue, New York, NY 10010",
                                   "hq_metro": "New York Metro", "source": "seed"},
    "Ancora Advisors":            {"address": "6060 Parkland Blvd, Suite 200, Cleveland, OH 44124",
                                   "hq_metro": "Cleveland / Ohio", "source": "seed"},
    "Vanguard Group Inc":         {"address": "100 Vanguard Blvd, Malvern, PA 19355",
                                   "hq_metro": "Philadelphia / Baltimore", "source": "seed"},
}

_SUFFIXES = {"inc", "incorporated", "llc", "lp", "llp", "corp", "corporation",
             "co", "company", "ltd", "limited", "plc", "trust", "sa", "ag", "nv",
             "the", "group", "holdings", "advisors", "advisers", "associates",
             "capital", "management", "partners", "investments", "investment"}


def _norm(n):
    """Loose fund-name key for cross-source matching (mirrors investors_page's
    _norm_name): lowercase, alnum-only, drop common fund-name words."""
    toks = "".join(c if c.isalnum() else " " for c in str(n).lower()).split()
    core = "".join(t for t in toks if t not in _SUFFIXES)
    return core or "".join(toks)  # never empty (e.g. a name that's all suffixes)


def _load():
    book = db.load_json(_STORE, None)
    if book is None:
        book = {k: dict(v) for k, v in _SEED.items()}
        db.save_json(_STORE, book)
    return book


def _save(book):
    db.save_json(_STORE, book)


def address_for(fund_name):
    """The best-known street address string for a fund, or None. Exact match
    first, then a normalized-name match so 'Vanguard Group Inc' finds a record
    stored as 'VANGUARD GROUP INC'."""
    if not fund_name:
        return None
    book = _load()
    rec = book.get(fund_name)
    if not rec:
        key = _norm(fund_name)
        rec = next((v for k, v in book.items() if _norm(k) == key), None)
    return (rec or {}).get("address") or None


def record_for(fund_name):
    """Full stored record (address, hq_metro, source, cik) or {}."""
    if not fund_name:
        return {}
    book = _load()
    rec = book.get(fund_name)
    if not rec:
        key = _norm(fund_name)
        rec = next((v for k, v in book.items() if _norm(k) == key), None)
    return dict(rec or {})


def set_address(fund_name, address, source="manual", hq_metro=None, cik=None):
    book = _load()
    rec = book.get(fund_name, {})
    rec.update({"address": (address or "").strip(), "source": source})
    if hq_metro:
        rec["hq_metro"] = hq_metro
    if cik:
        rec["cik"] = cik
    book[fund_name] = rec
    _save(book)
    return rec


def _sec_business_address(cik):
    """(formatted_address, city, state) from a CIK's SEC business address, or
    (None, None, None)."""
    try:
        r = requests.get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json",
                         headers=_UA, timeout=12)
        r.raise_for_status()
        a = (r.json() or {}).get("addresses", {}).get("business") or {}
    except Exception:
        return None, None, None
    st1, st2 = a.get("street1"), a.get("street2")
    city, state, zc = a.get("city"), a.get("stateOrCountry"), a.get("zipCode")
    if not st1 or not city:
        return None, None, None
    street = " ".join(p for p in (st1, st2) if p).title()
    parts = [street, str(city).title(), " ".join(p for p in (state, zc) if p)]
    return ", ".join(p for p in parts if p).strip(), city, state


def refresh_from_sec(name_cik_pairs, throttle=0.15):
    """Populate the address book from SEC business addresses BY CIK — exact, no
    name-matching. `name_cik_pairs` is an iterable of (fund_name, cik). Returns
    {'updated': int, 'skipped': int}. Existing manual/seed entries are NOT
    overwritten unless they have no address."""
    import time
    book = _load()
    updated = skipped = 0
    seen = set()
    for name, cik in name_cik_pairs:
        if not name or not cik or (name, cik) in seen:
            continue
        seen.add((name, cik))
        existing = book.get(name)
        if existing and existing.get("source") in ("manual", "seed") and existing.get("address"):
            skipped += 1
            continue
        addr, _city, _state = _sec_business_address(cik)
        if not addr:
            skipped += 1
            continue
        book[name] = {"address": addr, "source": "SEC", "cik": str(cik)}
        updated += 1
        if updated % 25 == 0:
            _save(book)  # checkpoint so a long/interrupted pull keeps its progress
        time.sleep(throttle)
    _save(book)
    return {"updated": updated, "skipped": skipped}


def coverage(fund_names):
    """How many of the given fund names have a resolvable address — for a
    Settings/telemetry readout ('312 of 372 funds have an office address')."""
    have = sum(1 for n in fund_names if address_for(n))
    return {"have": have, "total": len(fund_names), "missing": len(fund_names) - have}
