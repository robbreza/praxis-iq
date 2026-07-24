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
_MF_TTL = timedelta(days=30)
_ROSTER_TTL = timedelta(days=30)

# Forms whose SGML header enumerates ALL of a registrant's series at once.
_ROSTER_FORMS = ("N-CEN", "485BPOS", "485APOS", "497")


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
    cached = db.load_json(_MF_INDEX_KEY, default=None)
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
        db.save_json(_MF_INDEX_KEY, store)
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
    cached = db.load_json(ck, default=None)
    if cached and not force and not sf._is_stale(cached.get("_fetched_at"), _ROSTER_TTL):
        return cached
    try:
        sub = sf._get(f"https://data.sec.gov/submissions/CIK{cik:010d}.json", timeout=25).json()
    except Exception:
        return cached
    registrant = sub.get("name")
    rec = sub.get("filings", {}).get("recent", {})
    forms, accs = rec.get("form", []), rec.get("accessionNumber", [])
    funds, source = [], None
    for want in _ROSTER_FORMS:
        acc = next((a for f, a in zip(forms, accs) if f == want), None)
        if not acc:
            continue
        accn = acc.replace("-", "")
        try:
            hdr = sf._get(f"https://www.sec.gov/Archives/edgar/data/{cik}/{accn}/{acc}.hdr.sgml", timeout=25)
        except Exception:
            continue
        if hdr.status_code != 200:
            continue
        parsed = _parse_series_blocks(hdr.text)
        if parsed:
            funds, source = parsed, f"{want} {acc}"
            break
    if not funds:
        return cached
    result = {
        "cik": cik, "registrant": registrant, "funds": funds,
        "series_count": len(funds), "class_count": sum(len(f["classes"]) for f in funds),
        "source": source, "_fetched_at": _iso_now(),
    }
    try:
        db.save_json(ck, result)
    except Exception:
        pass
    return result


def lineup_for_manager(manager_name):
    """The fund lineup for a 13F manager name, or None if we can't confidently map
    it to a registered fund family. Never guesses — an unmapped name returns None."""
    cik = _MANAGER_REGISTRANT.get(_norm(manager_name))
    if not cik:
        return None
    return series_roster(cik)


def has_lineup(manager_name):
    """Cheap check (no network) for whether a manager is in the crosswalk."""
    return _norm(manager_name) in _MANAGER_REGISTRANT
