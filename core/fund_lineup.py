"""core/fund_lineup.py — for a fund manager, the roster of registered funds it runs.

A 13F holder tells you the MANAGER (the investment adviser). It does NOT tell you
which of the manager's funds holds the position — Form 13F is filed at the adviser
level and aggregates every discretionary account into one report. But an IR lead
often just wants the manager's fund LINEUP: when a 13F shows only "Heartland", is
that the micro-cap sleeve, the small-mid sleeve, or a sector fund? That granularity
IS public — it lives in the fund family's own '40-Act filings — and this module
pulls it, 100% from SEC EDGAR, cached.

Two SEC sources, both verified live:
  1. company_tickers_mf.json — every fund share class -> {cik, seriesId, classId,
     ticker}. Gives the registrant CIK and how many series/classes a family runs.
     (It carries no NAMES — those come from source 2.)
  2. The registrant's latest N-CEN (annual) or 485BPOS (prospectus) SGML header —
     lists EVERY series (fund) name and its share-class names in ONE document.
     NPORT-P is filed per-series so it names only one fund; not used for the roster.

The catch, and why there's a crosswalk: the adviser that files the 13F
("Heartland Advisors Inc") and the fund trust that files N-CEN
("Heartland Group Inc") are DIFFERENT EDGAR registrants with different CIKs and no
clean key joining them. Fuzzy name matching is unsafe (a plain "Heartland" search
returns unrelated companies). So the adviser->registrant link is a curated
crosswalk (_MANAGER_REGISTRANT), keyed by a normalized manager name. A manager not
in the crosswalk simply returns no lineup — the feature degrades quietly, it never
guesses. The crosswalk is meant to grow the way the curated-targets house book does.
"""
from datetime import timedelta
import re

from core import db, sec_filings as sf

_MF_INDEX_KEY = "sec_fund_mf_index"          # ticker/series universe, one small SEC file
_ROSTER_KEY = "sec_fund_roster_"             # + registrant CIK
_REG_NORMS_KEY = "sec_fund_registrant_norms"  # norm(name) -> [ciks] for fund registrants
_CROSSWALK_KEY = "sec_fund_crosswalk"        # auto/confirmed adviser -> registrant links
_MF_TTL = timedelta(days=30)
_ROSTER_TTL = timedelta(days=30)
_REG_NORMS_TTL = timedelta(days=30)
_ROSTER_SCHEMA = 2                            # bump to invalidate cached rosters on shape change

# Forms whose SGML header enumerates ALL of a registrant's series at once.
_ROSTER_FORMS = ("N-CEN", "485BPOS", "485APOS", "497")

# Everything here is SHARED across tenants — SEC reference data (MF index, rosters,
# registrant names) is client-independent, and the manager->fund-family crosswalk is a
# house book that accretes as any client is scanned (a Gabelli match confirmed for one
# issuer helps every issuer). Stored under the reserved global client id (same
# convention core.curated_targets uses for its global house book).
_GLOBAL = "_global"


def _gload(key, default=None):
    return db.load_json(key, default=default, client_id=_GLOBAL)


def _gsave(key, data):
    db.save_json(key, data, client_id=_GLOBAL)


def _norm(name):
    """Loose match key: lowercase, drop punctuation and the common adviser/entity
    suffixes so 'Heartland Advisors, Inc.' and 'HEARTLAND ADVISORS INC' collapse."""
    s = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower())
    s = re.sub(r"\b(inc|incorporated|llc|lp|llp|ltd|co|corp|company|the|advisors?|"
               r"advisers?|management|capital|asset|investments?|group|funds?|"
               r"partners?|holdings?|na|sa|ag|plc)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ── Adviser (13F filer) -> fund-trust registrant CIK ─────────────────────────────
# Curated. Key is _norm(adviser name). Value is the registrant CIK that files the
# fund family's N-CEN/485. Seeded with boutiques where the lineup is genuinely
# actionable (a handful of clearly-differentiated sleeves); grow it as needed. For
# mega-complexes (Fidelity, Vanguard) the "lineup" is hundreds of funds across many
# trusts, so a single-CIK mapping is deliberately omitted until we decide how to
# present those.
_MANAGER_REGISTRANT = {
    _norm("Heartland Advisors Inc"): 809586,          # Heartland Group Inc
    _norm("Heartland"): 809586,
}


def _mf_index():
    """{registrant_cik(int): {"series": set(seriesId), "classes": int,
    "tickers": [symbol,...]}} from company_tickers_mf.json. Cached 30 days."""
    cached = _gload(_MF_INDEX_KEY)
    if cached and not sf._is_stale(cached.get("_fetched_at"), _MF_TTL):
        # JSON keys come back as strings — rebuild int-keyed view.
        return {int(k): v for k, v in cached.items() if k != "_fetched_at"}
    try:
        raw = sf._get("https://www.sec.gov/files/company_tickers_mf.json", timeout=30).json()
    except Exception:
        return {int(k): v for k, v in (cached or {}).items() if k != "_fetched_at"}
    idx = {}
    for row in raw.get("data", []):
        cik, series_id, _class_id, symbol = row[0], row[1], row[2], row[3]
        d = idx.setdefault(int(cik), {"series": set(), "classes": 0, "tickers": []})
        d["series"].add(series_id)
        d["classes"] += 1
        if symbol:
            d["tickers"].append(symbol)
    store = {str(cik): {"series": sorted(v["series"]), "classes": v["classes"],
                        "tickers": sorted(v["tickers"])} for cik, v in idx.items()}
    store["_fetched_at"] = sf._now_iso() if hasattr(sf, "_now_iso") else _iso_now()
    try:
        _gsave(_MF_INDEX_KEY, store)
    except Exception:
        pass
    return {int(k): v for k, v in store.items() if k != "_fetched_at"}


def _iso_now():
    from datetime import datetime
    return datetime.now().isoformat()


def registrant_from_fund_ticker(ticker):
    """Registrant CIK that runs the fund with this share-class ticker (e.g. HRTVX
    -> 809586). For building/checking crosswalk entries."""
    t = (ticker or "").upper().strip()
    for cik, d in _mf_index().items():
        if t in d.get("tickers", []):
            return cik
    return None


def _parse_series_blocks(sgml):
    """Pull (series_name, [class_names]) out of an EDGAR SGML header. Series are
    delimited by <SERIES> ... blocks, each with one <SERIES-NAME> and zero+
    <CLASS-CONTRACT-NAME>."""
    out = []
    # Split on the opening SERIES tag; skip the pre-amble before the first one.
    for block in re.split(r"<SERIES>", sgml, flags=re.I)[1:]:
        nm = re.search(r"<SERIES-NAME>([^<\n]+)", block, re.I)
        if not nm:
            continue
        classes = [c.strip() for c in re.findall(r"<CLASS-CONTRACT-NAME>([^<\n]+)", block, re.I)]
        out.append({"name": nm.group(1).strip(), "classes": list(dict.fromkeys(classes))})
    # De-dupe by series name, preserving order (a header can repeat the block).
    seen, uniq = set(), []
    for s in out:
        if s["name"].upper() in seen:
            continue
        seen.add(s["name"].upper())
        uniq.append(s)
    return uniq


def series_roster(registrant_cik, force=False):
    """The registrant's fund lineup: {"cik", "registrant", "funds":[{name, classes}],
    "series_count", "class_count", "source"}. Pulled from the latest N-CEN/485BPOS
    header. Cached 30 days. Returns None if nothing usable is on file."""
    cik = int(registrant_cik)
    ck = f"{_ROSTER_KEY}{cik}"
    cached = _gload(ck)
    # schema gate — entries cached under an older shape are refetched once so the new
    # aggregation/completeness logic actually applies.
    if (cached and not force and cached.get("schema") == _ROSTER_SCHEMA
            and not sf._is_stale(cached.get("_fetched_at"), _ROSTER_TTL)):
        return cached
    try:
        sub = sf._get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", timeout=25).json()
    except Exception:
        return cached
    registrant = sub.get("name")
    rec = sub.get("filings", {}).get("recent", {})
    forms, accs = rec.get("form", []), rec.get("accessionNumber", [])
    expected = len((_mf_index().get(cik) or {}).get("series", []))

    def _hdr_series(acc):
        accn = acc.replace("-", "")
        try:
            hdr = sf._get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{acc}.hdr.sgml", timeout=25)
        except Exception:
            return []
        return _parse_series_blocks(hdr.text) if hdr.status_code == 200 else []

    # Aggregate series NAMES across recent filings. A single header doesn't always list
    # the whole family (a big complex's N-CEN can carry just one series), so we walk the
    # roster-enumerating forms first — one of them often lists everyone in one shot, which
    # is all a boutique needs — then fill any gaps from the per-series NPORT-P filings,
    # stopping as soon as we've matched the authoritative ticker-file series count (or hit
    # a fetch budget). Heartland completes in 1 fetch; Nuveen's 17 in ~two dozen.
    target = expected if expected else 1
    budget, fetched = 45, 0
    by_name, sources = {}, []
    ordered = ([(f, a) for f, a in zip(forms, accs) if f in _ROSTER_FORMS]
               + [(f, a) for f, a in zip(forms, accs) if f.startswith("NPORT")])
    for f, a in ordered:
        if fetched >= budget or len(by_name) >= target:
            break
        parsed = _hdr_series(a)
        if not parsed:
            continue
        fetched += 1
        added = False
        for s in parsed:
            k = s["name"].upper()
            if k not in by_name:
                by_name[k] = s
                added = True
            elif not by_name[k].get("classes") and s.get("classes"):
                by_name[k] = s      # upgrade to the copy that carries class names
        if added:
            sources.append(f"{f} {a}")
    funds = list(by_name.values())
    if not funds:
        return cached
    source = "; ".join(sources[:3]) + (f" +{len(sources) - 3} more" if len(sources) > 3 else "")
    # complete = we captured essentially the whole roster (the ticker file is the count
    # of record). Callers still DISPLAY partial rosters — a knowledgeable reader spots a
    # gap — but flag them so the UI can mark "partial".
    complete = expected == 0 or len(funds) >= max(1, round(expected * 0.75))
    result = {
        "cik": cik, "registrant": registrant, "funds": funds,
        "series_count": len(funds), "class_count": sum(len(f["classes"]) for f in funds),
        "expected_series": expected, "complete": complete,
        "source": source, "schema": _ROSTER_SCHEMA, "_fetched_at": _iso_now(),
    }
    try:
        _gsave(ck, result)
    except Exception:
        pass
    return result


def _crosswalk():
    """Persisted adviser->registrant links (auto-bootstrapped + user-confirmed),
    keyed by _norm(name): {"cik", "registrant", "confidence", "confirmed"}."""
    return _gload(_CROSSWALK_KEY, {}) or {}


def _registrant_cik(manager_name):
    """Resolve a manager name to a fund-registrant CIK: hardcoded seed first, then
    the persisted crosswalk (a high-confidence auto-match or a confirmed one). A
    user-rejected link or an unconfirmed ambiguous one is NOT used. None if unmapped."""
    nk = _norm(manager_name)
    if nk in _MANAGER_REGISTRANT:
        return _MANAGER_REGISTRANT[nk]
    e = _crosswalk().get(nk)
    if e and not e.get("rejected") and (e.get("confirmed") or e.get("confidence") == "high"):
        return e.get("cik")
    return None


# ── Crosswalk review / confirmation (the human-in-the-loop half of auto-bootstrap) ──
def _registrant_name(cik):
    """Just the current registrant name for a CIK (light submissions call), cached —
    used to label crosswalk candidates without triggering a full roster aggregation."""
    if not cik:
        return None
    key = f"sec_reg_name_{int(cik)}"
    c = _gload(key)
    if c and c.get("name"):
        return c["name"]
    try:
        sub = sf._get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", timeout=20).json()
        nm = sub.get("name")
    except Exception:
        return None
    try:
        _gsave(key, {"name": nm})
    except Exception:
        pass
    return nm


def crosswalk_entries():
    """All persisted crosswalk rows with their norm key, for the review UI. Each row:
    {norm, manager, cik|ciks, registrant, confidence, confirmed, rejected}."""
    out = []
    for nk, e in _crosswalk().items():
        rec = dict(e)
        rec["norm"] = nk
        out.append(rec)
    return out


def candidate_names(ciks):
    """[{cik, name}] for a review entry's candidate registrants, so the user can pick."""
    return [{"cik": c, "name": _registrant_name(c) or f"CIK {c}"} for c in (ciks or [])]


def confirm_entry(norm, cik=None):
    """Lock a mapping: mark confirmed (optionally choosing a specific candidate CIK).
    A confirmed link is used and is never overwritten by a future re-scan."""
    cw = _crosswalk()
    e = cw.get(norm) or {}
    if cik is not None:
        e["cik"] = int(cik)
        e["confidence"] = "manual"
    e["confirmed"] = True
    e["rejected"] = False
    e["registrant"] = _registrant_name(e.get("cik"))
    e["confirmed_at"] = _iso_now()
    cw[norm] = e
    _gsave(_CROSSWALK_KEY, cw)


def reject_entry(norm):
    """Mark a mapping wrong: it's no longer used, and a future re-scan won't re-add it
    (the record is kept as a tombstone so the auto-matcher doesn't resurrect it)."""
    cw = _crosswalk()
    e = cw.get(norm) or {}
    e["rejected"] = True
    e["confirmed"] = False
    e["rejected_at"] = _iso_now()
    cw[norm] = e
    _gsave(_CROSSWALK_KEY, cw)


def restore_entry(norm):
    """Undo a confirm/reject — back to its auto state (a high match becomes usable
    again; a review match goes back to needing confirmation)."""
    cw = _crosswalk()
    e = cw.get(norm)
    if not e:
        return
    e["confirmed"] = False
    e["rejected"] = False
    cw[norm] = e
    _gsave(_CROSSWALK_KEY, cw)


def bootstrap_from_book(cid=None):
    """Convenience for the UI 'rescan' button: match every manager in the client's
    peer-owner book against the fund-registrant universe and persist."""
    from core import peer_prospects
    names = [c.get("filer") for c in peer_prospects.all_candidates(cid) if c.get("filer")]
    return bootstrap_crosswalk(names)


def lineup_for_manager(manager_name):
    """The fund lineup for a 13F manager name, or None if we can't confidently map
    it to a registered fund family. Never guesses — an unmapped name returns None."""
    cik = _registrant_cik(manager_name)
    if not cik:
        return None
    return series_roster(cik)


def has_lineup(manager_name):
    """Cheap check (no network) for whether a manager resolves to a fund family."""
    return _registrant_cik(manager_name) is not None


# ── Auto-bootstrap: match managers in a book against the SEC fund-registrant universe ──
def _fund_registrant_norms():
    """{norm(name): [cik,...]} over every SEC investment-company registrant (the CIKs
    that appear in the mutual-fund ticker file). Built once from the EDGAR CIK->name
    dump, filtered to fund registrants, cached 30 days. This is what lets us match a
    13F adviser name to the trust that files the fund lineup."""
    cached = _gload(_REG_NORMS_KEY)
    if cached and not sf._is_stale(cached.get("_fetched_at"), _REG_NORMS_TTL):
        return {k: v for k, v in cached.items() if k != "_fetched_at"}
    fund_ciks = set(_mf_index().keys())
    if not fund_ciks:
        return {k: v for k, v in (cached or {}).items() if k != "_fetched_at"}
    try:
        # NAME:CIK: per line, uppercase. One ~40MB download; parsed line by line.
        txt = sf._get("https://www.sec.gov/Archives/edgar/cik-lookup-data.txt", timeout=60).text
    except Exception:
        return {k: v for k, v in (cached or {}).items() if k != "_fetched_at"}
    norms = {}
    for line in txt.splitlines():
        # lines look like "HEARTLAND GROUP INC:0000809586:"
        m = re.match(r"^(.*):(\d+):\s*$", line)
        if not m:
            continue
        cik = int(m.group(2))
        if cik not in fund_ciks:
            continue
        nk = _norm(m.group(1))
        if not nk:
            continue
        norms.setdefault(nk, [])
        if cik not in norms[nk]:
            norms[nk].append(cik)
    store = dict(norms)
    store["_fetched_at"] = _iso_now()
    try:
        _gsave(_REG_NORMS_KEY, store)
    except Exception:
        pass
    return norms


def _name_agrees(manager_norm, registrant_name):
    """True if the manager's normalized name still lines up with the registrant's
    CURRENT name — same token, or one is a token-subset of the other. Rejects stale
    EDGAR aliases (a match on a former name that no longer describes the family)."""
    rn = _norm(registrant_name)
    if not rn or not manager_norm:
        return False
    if rn == manager_norm:
        return True
    mt, rt = set(manager_norm.split()), set(rn.split())
    return mt.issubset(rt) or rt.issubset(mt)


def bootstrap_crosswalk(manager_names, persist=True):
    """Match each manager name against the fund-registrant universe by normalized
    name. A unique match is auto-filled as high-confidence; multiple matches (a
    mega-complex with many trusts, or a genuine name collision) are flagged for the
    user to confirm; no match means no registered fund family (a hedge fund/SMA).

    Returns {"high": {norm: {...}}, "review": {norm: {...}}, "unmatched": [names]}.
    Persists the high-confidence links (and the review candidates, unconfirmed) to
    the crosswalk store when persist=True."""
    norms = _fund_registrant_norms()
    high, review, unmatched, seen = {}, {}, [], set()
    for name in manager_names:
        nk = _norm(name)
        if not nk or nk in seen or nk in _MANAGER_REGISTRANT:
            continue
        seen.add(nk)
        ciks = norms.get(nk, [])
        if len(ciks) == 1:
            # Precision guard: EDGAR's CIK dump carries old name aliases, so a unique
            # match can be a stale collision (adviser "Potomac Capital Management" hits
            # CIK for the fund family FORMERLY named "Potomac Funds", now Direxion).
            # Validate against the registrant's CURRENT name and require a live lineup;
            # a mismatch is demoted to review rather than shown as fact.
            roster = series_roster(ciks[0])
            if roster and roster.get("funds") and _name_agrees(nk, roster.get("registrant")):
                high[nk] = {"cik": ciks[0], "manager": name, "registrant": roster.get("registrant"),
                            "confidence": "high", "confirmed": False}
            else:
                review[nk] = {"ciks": ciks, "manager": name, "confidence": "review",
                              "confirmed": False,
                              "note": "current registrant name doesn't match — likely a stale EDGAR alias"}
        elif len(ciks) > 1:
            review[nk] = {"ciks": ciks, "manager": name, "confidence": "review", "confirmed": False}
        else:
            unmatched.append(name)
    if persist:
        cw = _crosswalk()
        for nk, e in high.items():
            prev = cw.get(nk)
            if prev and (prev.get("confirmed") or prev.get("rejected")):  # respect user decisions
                continue
            cw[nk] = {"cik": e["cik"], "registrant": e.get("registrant"), "confidence": "high",
                      "confirmed": False, "rejected": False, "manager": e["manager"], "added_at": _iso_now()}
        for nk, e in review.items():
            if nk in cw and (cw[nk].get("confirmed") or cw[nk].get("rejected")):
                continue
            cw.setdefault(nk, {"ciks": e["ciks"], "confidence": "review", "confirmed": False,
                               "rejected": False, "manager": e["manager"],
                               "note": e.get("note"), "added_at": _iso_now()})
        try:
            _gsave(_CROSSWALK_KEY, cw)
        except Exception:
            pass
    return {"high": high, "review": review, "unmatched": unmatched}
