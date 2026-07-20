"""
core/sec_filings.py — SEC EDGAR data fetching for ownership-stake alerts
(13D/13G) and institutional holdings (13F), cached via core.db so pages
never block on a live network call.

Two very different data shapes live here, on purpose:

- 13D / 13G ("who just took or changed a >5% stake") — cheap, per-issuer
  lookups against EDGAR's browse-edgar company search. Meant to refresh
  ~daily; the app_nicegui.py startup hook kicks this off in the
  background on every server start (see refresh_all()).
- 13F ("who among all institutional managers holds this stock, and how
  much") — there is no per-ticker SEC endpoint for exact position sizes,
  but EDGAR's full-text search (efts.sec.gov) DOES let us search 13F-HR
  filings for a company name/ticker directly, returning which filers
  mentioned it without downloading every manager's full position list.
  REPLACED 2026-07-12 (see SEC_13F_extraction_reference.md): this used to
  pull SEC's entire quarterly bulk structured dataset (every institutional
  manager's full position list across the whole market, tens of MB
  compressed) and filter it down client-side — reliable in theory but slow
  and heavy enough in practice to make "Refresh 13F Holders" look hung.
  The full-text-search approach is a handful of lightweight, paginated,
  per-ticker JSON requests instead. It tells us WHO holds a position (and,
  via _qoq_trend, whether that's NEW this quarter) but not the exact
  share/dollar size of that one position — see _search_holders_for_ticker's
  size_known sentinel. Exact whole-book totals (needed for the Fit Score's
  "purchasing power" signal) are fetched separately, lazily, and only for
  filers behind prospects actually being displayed — see
  get_or_fetch_filer_book_total / ensure_book_totals. 13F is also only
  filed quarterly with a 45-day lag, so refreshing this on every app
  startup would be both slow and pointless — it's meant to run on its own
  quarterly cadence or an explicit "Refresh 13F Holders" button (see
  page_modules_nicegui/investors_page.py's SEC Intelligence tab), never
  inline with a page render.

Tracked universe: the active client's own ticker plus its full peer list
(config.client_config.CP()) — the same peer list already driving Markets
and Investor Cross-Targeting, so "competitors to watch" isn't a second
list to maintain here.

SEC's fair-access policy requires every request to declare a real
requester identity (company name + contact email) in the User-Agent
header, or requests get rate-limited/blocked — see
https://www.sec.gov/os/webmaster-faq#developers. That identity is pulled
from the active client's own IR contact (config.client_config.CI()), not
hardcoded, so this stays correct per-tenant.

IMPORTANT — network access: this module was written and syntax/logic-
tested without a live route to sec.gov (the dev sandbox this was built in
has no general internet access). The request/response *shapes* below
follow SEC's documented, stable public API contracts, and the parsing
logic has unit coverage against hand-built fixtures matching those
contracts, but the very first live run against the real endpoints should
happen somewhere with normal internet access (i.e. wherever this app is
actually deployed) before being relied on. If a request shape has
drifted, the exceptions raised here are specific enough to show up
immediately rather than silently returning empty data.
"""

import csv
import io
import re
import threading
import time
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timedelta

import requests

from core import db

SEC_TICKER_MAP_KEY = "sec_ticker_cik_map.json"
SEC_TICKER_MAP_TTL_DAYS = 7

SEC_13D13G_KEY_FMT = "sec_13d13g_{ticker}.json"
SEC_13D13G_TTL_HOURS = 24

SEC_13F_HOLDERS_KEY_FMT = "sec_13f_holders_{ticker}.json"
SEC_13F_HOLDERS_PRIOR_KEY_FMT = "sec_13f_holders_prior_{ticker}.json"
SEC_13F_BOOK_TOTALS_KEY = "sec_13f_book_totals.json"

SEC_REFRESH_LOG_KEY = "sec_refresh_log.json"

# Manual CIK overrides — fill in here if a ticker fails to auto-resolve via
# SEC's company_tickers.json (happens for very recent IPOs, ADRs, or a
# ticker that changed after the last time SEC refreshed that file). Format:
# {"TICKER": "1234567"} — any digit count is fine, resolve_cik() zero-pads.
MANUAL_CIK_OVERRIDES = {
    # Fiserv renamed FISV -> FI in 2023, but SEC has not caught up: BOTH
    # company_tickers.json AND data.sec.gov/submissions/CIK0000798354.json still
    # list only "FISV" (verified 2026-07-16). No automated lookup — including the
    # browse-EDGAR fallback below — can resolve "FI", so this override is the only
    # route. Verified: CIK 798354 = FISERV INC, Nasdaq, 10-K filed 2026-02-19.
    #
    # FI was dropped from the peer set on 2026-07-16 (too large to inform a micro-cap
    # comp), so nothing calls this today. Retained deliberately: it is a verified fact
    # about SEC's data that cost an investigation to establish, and without it anyone
    # re-adding FI would hit the same SILENT failure — resolve_cik returning None and
    # the comp table quietly falling back to estimates.
    "FI": "798354",
}

# Negative + positive cache for the browse-EDGAR ticker fallback below, so a miss
# costs one request per TTL rather than one per call.
SEC_CIK_FALLBACK_KEY = "sec_cik_fallback.json"
SEC_CIK_FALLBACK_TTL_DAYS = 30

_REQUEST_DELAY_SEC = 0.15  # stay well under SEC's ~10 req/sec fair-access limit
_ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def _user_agent():
    try:
        from config.client_config import C, CI
        client = C()
        contact = CI()
        name = client.get("name", "Praxis Point Advisory")
        email = contact.get("email") or "ir@example.com"
        return f"{name} {email}"
    except Exception:
        return "Praxis Point Advisory ir@example.com"


# Global, thread-safe pacing for every SEC request.
#
# _get() used to sleep _REQUEST_DELAY_SEC AFTER each call. That is a per-CALL delay, not
# a rate limit: it works only because every caller was sequential. The moment anything
# fetches in parallel — which is the only way to make a 9-company cold render fast — each
# thread sleeps on its own clock and the aggregate rate is threads/delay. Four threads at
# 0.15s is ~26 req/s, well over SEC's ~10 req/s fair-access limit, and SEC blocks abusers.
#
# This paces globally instead: one shared "next allowed slot" that every thread advances
# under a lock, so N threads cannot exceed _MAX_RPS between them no matter how many there
# are. Sleeping BEFORE the request (not after) also stops the delay being wasted on the
# last call of a batch.
_MAX_RPS = 8.0                      # under SEC's ~10/s, with headroom
_MIN_INTERVAL = 1.0 / _MAX_RPS
_rate_lock = threading.Lock()
_next_slot = [0.0]


def _throttle():
    """Block until this thread's turn. Shared across every SEC caller in the process."""
    while True:
        with _rate_lock:
            now = time.monotonic()
            slot = max(now, _next_slot[0])
            _next_slot[0] = slot + _MIN_INTERVAL
        wait = slot - time.monotonic()
        if wait <= 0:
            return
        time.sleep(wait)
        return


def _get(url, params=None, timeout=15):
    _throttle()
    resp = requests.get(url, params=params, headers={"User-Agent": _user_agent()}, timeout=timeout)
    resp.raise_for_status()
    return resp


def _is_stale(iso_timestamp, max_age):
    if not iso_timestamp:
        return True
    try:
        then = datetime.fromisoformat(iso_timestamp)
    except Exception:
        return True
    return datetime.now() - then > max_age


# ─────────────────────────────────────────────────────────────────────────
# CIK resolution
# ─────────────────────────────────────────────────────────────────────────
def resolve_cik(ticker):
    """Ticker -> zero-padded 10-digit CIK string, or None if not found.

    Resolution order: MANUAL_CIK_OVERRIDES, then SEC's company_tickers.json
    (cached a week), then a browse-EDGAR lookup.

    WHY THE FALLBACK EXISTS: company_tickers.json is NOT exhaustive. It carried
    ~10,426 tickers on 2026-07-16 and was missing CSGS (CSG Systems International,
    Nasdaq, 10-K filed 2026-02-19) outright. That miss was silent — resolve_cik
    returned None, edgar_financials degraded to Yahoo, and the benchmarking table
    quietly showed a market-sourced margin for a company we appeared to have filing
    data for. A peer vanishing from EDGAR should be loud, not a shrug.
    """
    ticker = ticker.upper().strip()
    if ticker in MANUAL_CIK_OVERRIDES:
        return str(MANUAL_CIK_OVERRIDES[ticker]).zfill(10)

    cached = db.load_json(SEC_TICKER_MAP_KEY, default=None)
    if cached is None or _is_stale(cached.get("_fetched_at"), timedelta(days=SEC_TICKER_MAP_TTL_DAYS)):
        cached = _refresh_ticker_cik_map()

    cik = (cached or {}).get(ticker)
    if cik:
        return cik.zfill(10)
    return _resolve_cik_via_edgar(ticker)


def _resolve_cik_via_edgar(ticker):
    """Fallback: ask browse-EDGAR directly. Caches hits AND misses (a miss is a
    real answer worth remembering) so a gap costs one request per TTL.

    Confirms the CIK actually belongs to the ticker before returning it — a name
    match is not an identity match, and a wrong CIK here would silently attribute
    another company's financials to a peer.
    """
    store = db.load_json(SEC_CIK_FALLBACK_KEY, default=None) or {}
    hit = store.get(ticker)
    if hit and not _is_stale(hit.get("at"), timedelta(days=SEC_CIK_FALLBACK_TTL_DAYS)):
        return hit.get("cik")

    cik = None
    try:
        url = ("https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany"
               f"&CIK={ticker}&type=10-K&dateb=&owner=include&count=1&output=atom")
        m = re.search(r"<cik>(\d+)</cik>", _get(url, timeout=20).text, re.I)
        if m:
            candidate = m.group(1).zfill(10)
            subs = _get(f"https://data.sec.gov/submissions/CIK{candidate}.json", timeout=25).json()
            # Only accept it if SEC itself lists this ticker on that CIK.
            if ticker in [t.upper() for t in (subs.get("tickers") or [])]:
                cik = candidate
                print(f"[sec] resolved {ticker} -> CIK {cik} ({subs.get('name')}) via browse-EDGAR "
                      f"— absent from company_tickers.json")
            else:
                print(f"[sec] browse-EDGAR returned CIK {candidate} for {ticker} but SEC lists it as "
                      f"{subs.get('tickers')} — REJECTED, will not attribute another issuer's filings")
    except Exception as e:
        print(f"[sec] CIK fallback lookup failed for {ticker}: {e}")
        return None  # transient — don't poison the cache with a network blip

    if cik is None:
        print(f"[sec] {ticker}: NO CIK — not in company_tickers.json and browse-EDGAR could not "
              f"resolve it. Anything EDGAR-sourced for this ticker will be missing, not estimated.")
    store[ticker] = {"cik": cik, "at": datetime.now().isoformat()}
    db.save_json(SEC_CIK_FALLBACK_KEY, store)
    return cik


def _refresh_ticker_cik_map():
    resp = _get("https://www.sec.gov/files/company_tickers.json")
    raw = resp.json()  # {"0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."}, ...}
    mapping = _parse_ticker_map(raw)
    mapping["_fetched_at"] = datetime.now().isoformat()
    db.save_json(SEC_TICKER_MAP_KEY, mapping)
    return mapping


def _parse_ticker_map(raw):
    """Split out from _refresh_ticker_cik_map so the parsing logic can be
    unit-tested against a small fixture without a live SEC call."""
    return {str(row["ticker"]).upper(): str(row["cik_str"]) for row in raw.values()}


# ─────────────────────────────────────────────────────────────────────────
# 13D / 13G — ownership-stake alerts
# ─────────────────────────────────────────────────────────────────────────
def _fetch_ownership_filings_atom(cik10, form_type):
    """One SC 13D or SC 13G Atom feed page (up to 100 entries) for the
    given issuer CIK. Deliberately using EDGAR's browse-edgar company
    search here, not data.sec.gov/submissions/CIK##.json — the
    submissions endpoint only lists filings a CIK filed itself (10-K,
    10-Q, 8-K, etc), not filings OTHERS filed about it. 13D/13G filings
    are filed by the acquiring investor, about the issuer, so the
    subject-company index (which browse-edgar provides) is the correct
    lookup for 'who has taken a position in this stock.'"""
    resp = _get(
        "https://www.sec.gov/cgi-bin/browse-edgar",
        params={
            "action": "getcompany", "CIK": cik10, "type": form_type,
            "dateb": "", "owner": "include", "count": "100", "output": "atom",
        },
    )
    return _parse_ownership_atom(resp.content, form_type)


def _parse_ownership_atom(xml_bytes, form_type):
    """Split out from _fetch_ownership_filings_atom so parsing can be unit-
    tested against a small hand-built Atom fixture without a live call."""
    root = ET.fromstring(xml_bytes)
    out = []
    for entry in root.findall("a:entry", _ATOM_NS):
        title = (entry.findtext("a:title", default="", namespaces=_ATOM_NS) or "").strip()
        updated = (entry.findtext("a:updated", default="", namespaces=_ATOM_NS) or "")[:10]
        link_el = entry.find("a:link", _ATOM_NS)
        link = link_el.get("href") if link_el is not None else ""
        summary = (entry.findtext("a:summary", default="", namespaces=_ATOM_NS) or "").strip()
        out.append({"form": form_type, "title": title, "date": updated, "link": link, "summary": summary})
    return out


def fetch_13d_13g_filings(ticker):
    """Live fetch of recent SC 13D / SC 13D-A / SC 13G / SC 13G-A filings
    against this issuer, newest first. Raises if the ticker can't be
    resolved to a CIK, or if the request itself fails — callers (see
    get_cached_13d_13g) should catch this and fall back to whatever's
    cached rather than showing a broken page."""
    cik10 = resolve_cik(ticker)
    if not cik10:
        raise ValueError(
            f"Could not resolve a SEC CIK for ticker '{ticker}'. "
            f"Add a manual override in core/sec_filings.py's MANUAL_CIK_OVERRIDES."
        )
    filings = []
    for form in ("SC 13D", "SC 13D/A", "SC 13G", "SC 13G/A"):
        filings.extend(_fetch_ownership_filings_atom(cik10, form))
    filings.sort(key=lambda f: f["date"], reverse=True)
    return filings


def get_cached_13d_13g(ticker, refresh_if_stale=True, force=False):
    """Cache-first accessor — page code should call this, not
    fetch_13d_13g_filings() directly, so a page render never blocks on a
    live SEC call. Only actually hits the network if the cache is empty
    or older than SEC_13D13G_TTL_HOURS; the startup hook in
    app_nicegui.py normally keeps this warm in the background, so pages
    rarely take that path themselves.

    force=True skips the TTL check entirely and always hits SEC live —
    this is what a manual 'Refresh 13D/13G Now' button click means: a
    person explicitly asked for the freshest data *right now*, not
    'refresh if it happens to be more than a day old.' Without this, a
    click within SEC_13D13G_TTL_HOURS of the last fetch (including the
    automatic one from the startup hook) silently returned the same
    cached snapshot and reported success, with no visible sign that
    nothing new was actually fetched — real bug, found 2026-07-10 when a
    freshly-added peer ticker's filings looked stuck on old dates after
    repeated manual refresh clicks."""
    key = SEC_13D13G_KEY_FMT.format(ticker=ticker.upper())
    cached = db.load_json(key, default=None)
    if not force and cached and not _is_stale(cached.get("_fetched_at"), timedelta(hours=SEC_13D13G_TTL_HOURS)):
        return cached
    if not refresh_if_stale and not force:
        return cached or {"filings": [], "_fetched_at": None, "_error": "not yet fetched"}
    try:
        filings = fetch_13d_13g_filings(ticker)
        result = {"filings": filings, "_fetched_at": datetime.now().isoformat(), "_error": None}
    except Exception as e:
        result = cached or {"filings": []}
        result["_error"] = str(e)
        result["_fetched_at"] = result.get("_fetched_at") or datetime.now().isoformat()
    db.save_json(key, result)
    return result


# ─────────────────────────────────────────────────────────────────────────
# 13F — aggregated institutional ownership
# ─────────────────────────────────────────────────────────────────────────
FORM_13F_INDEX_URL = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"

# Matches a dataset link on SEC's index page, e.g.
# href="/files/structureddata/data/form-13f-data-sets/01mar2026-31may2026_form13f.zip"
_13F_ZIP_LINK_RE = re.compile(
    r'href="(/files/structureddata/data/form-13f-data-sets/'
    r'(\d{2}[a-z]{3}\d{4})-(\d{2}[a-z]{3}\d{4})_form13f\.zip)"',
    re.IGNORECASE,
)


def _latest_13f_dataset():
    """Finds the most recently posted quarterly Form 13F bulk dataset by
    reading SEC's own index page, rather than computing a filename from
    date math.

    REPLACED 2026-07-10 after the first-ever live run against sec.gov
    (see module docstring's original caveat that this had only been
    logic-tested against fixtures) hit a 404. The original
    _current_13f_quarter() assumed two things that turned out to both be
    wrong: (1) the file lives under /files/dera/data/form-13f-data-sets/,
    when it's actually /files/structureddata/data/form-13f-data-sets/;
    (2) it's named by calendar quarter ({year}q{quarter}_form13f.zip),
    when SEC actually names it by a rolling 3-month date range that does
    NOT line up with calendar quarters — e.g. 'Mar-May', not 'Q1/Jan-Mar'
    (confirmed live: as of Jul 10, 2026 the newest posted set is
    01mar2026-31may2026_form13f.zip, i.e. a Dec-Feb/Mar-May/Jun-Aug/
    Sep-Nov cadence, offset from calendar quarters).

    Hardcoding that new scheme would just risk the exact same failure
    mode again the next time SEC changes it. Reading the live index page
    and taking whichever dataset link appears first (SEC lists newest
    first) means this keeps working even if the window boundaries or
    naming shift again — it always reflects whatever SEC currently has
    posted rather than a guess about what should be posted."""
    resp = _get(FORM_13F_INDEX_URL, timeout=30)
    match = _13F_ZIP_LINK_RE.search(resp.text)
    if not match:
        raise ValueError(
            "Could not find a Form 13F dataset download link on SEC's index page "
            f"({FORM_13F_INDEX_URL}) — the page structure may have changed again. "
            "Check that URL manually and update _13F_ZIP_LINK_RE in core/sec_filings.py."
        )
    path, start, end = match.group(1), match.group(2), match.group(3)
    return f"https://www.sec.gov{path}", f"{start}-{end}"


_MONTH_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
               "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def _parse_dataset_date(s):
    """'01mar2026' -> date(2026, 3, 1) — same DDmmmYYYY format
    _latest_13f_dataset() already parses out of SEC's index page link."""
    from datetime import date
    day = int(s[:2])
    mon = _MONTH_ABBR[s[2:5].lower()]
    year = int(s[5:9])
    return date(year, mon, day)


def _quarter_search_window():
    """(startdt, enddt, quarter_label) — the ISO date bounds to pass to
    EDGAR full-text search for 'the latest completed 13F quarter,' reusing
    _latest_13f_dataset()'s own live index-page lookup purely for its date
    labels (a cheap single-page fetch), never for the multi-MB dataset
    link it also returns. startdt is the quarter's own end date (a 13F-HR
    covering that quarter can't have been filed before the quarter ended);
    enddt is today, so this always covers every filing made so far,
    including late amendments — full-text search cost is per result page,
    not per day of window, so there's no reason to narrow this further."""
    _, label = _latest_13f_dataset()
    _, end_s = label.split("-")
    q_end = _parse_dataset_date(end_s)
    return q_end.isoformat(), datetime.now().date().isoformat(), label


_CORP_SUFFIX_RE = re.compile(r"\b(INCORPORATED|INC|CORPORATION|CORP|COMPANY|CO|LLC|LIMITED|LTD|PLC|LP|LLP)\b\.?")


def _normalize_company_name(name):
    """'Usio, Inc.' and SEC's own 'USIO INC' need to match each other, but
    a naive substring check fails on the punctuation and suffix-style
    differences between a display name (config/client_config.py's
    'Usio, Inc.') and SEC's INFOTABLE issuer strings (which are typically
    unpunctuated and suffix-heavy, e.g. 'USIO INC'). Normalizing both
    sides to bare-words-only, with common corporate suffixes stripped,
    fixes that without needing a hand-maintained alias table."""
    n = (name or "").upper()
    n = re.sub(r"[.,]", "", n)
    n = _CORP_SUFFIX_RE.sub("", n)
    return re.sub(r"\s+", " ", n).strip()


EDGAR_FULLTEXT_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"

# 'Pacer Advisors, Inc.  (CIK 0001616667)' -> 'Pacer Advisors, Inc.' — strips
# the "(CIK #######)" suffix EDGAR's full-text search API appends to every
# display name. NOTE (fixed 2026-07-12, first live run against the real
# endpoint): the suffix includes the literal "CIK " prefix inside the
# parens, not just bare digits — the original regex here (`\(\d+\)`, no
# "CIK") never matched a single real display name, so every filer name
# silently kept its "(CIK 0001616667)" suffix attached until this fix.
_DISPLAY_NAME_CIK_RE = re.compile(r"^(.*?)\s*\(CIK\s+\d+\)\s*$", re.IGNORECASE)


def _parse_display_name(raw):
    if not raw:
        return raw
    m = _DISPLAY_NAME_CIK_RE.match(raw.strip())
    return m.group(1).strip() if m else raw.strip()


def _fulltext_search_page(phrase, startdt, enddt, from_=0, forms="13F-HR"):
    """One page (10 hits) of SEC EDGAR's full-text search API. Endpoint
    and response shape verified live 2026-07-12 (see
    SEC_13F_extraction_reference.md, ported from a working sibling
    project's usio_prospects.py/wrap_target.py) — hits carry ciks (plural,
    a list), display_names, adsh (the accession number), file_date, and
    _id (= 'accession:filename', the exact info-table file that matched)."""
    resp = _get(
        EDGAR_FULLTEXT_SEARCH_URL,
        params={"q": f'"{phrase}"', "forms": forms, "startdt": startdt, "enddt": enddt, "from": from_},
        timeout=20,
    )
    return resp.json()


def _search_13f_holders_raw(phrase, startdt, enddt, max_results=150):
    """Paginated EDGAR full-text search for every 13F-HR filing that
    mentions `phrase` (a company's display name) within [startdt, enddt].
    Deduped by CIK, keeping the most recent file_date if a manager shows
    up more than once (an original filing plus a same-quarter amendment).

    THIS is the replacement for the old bulk-quarterly-dataset download —
    see SEC_13F_extraction_reference.md: a handful of lightweight paginated
    JSON requests scoped to one company, instead of downloading and parsing
    every institutional manager's every position across the entire market
    (tens of MB compressed, dramatically larger unzipped) just to filter it
    down to the tickers we care about. That bulk download is what made a
    'Refresh 13F' click look hung/frozen in practice (2026-07-12).

    Returns a list of {filer, cik, accession, filename, file_date} dicts —
    filename comes from splitting the hit's _id on ':', which is exactly
    the info-table XML SEC matched our phrase against for that filer, so a
    later whole-book fetch (see get_or_fetch_filer_book_total) needs no
    extra discovery request.

    FIXED 2026-07-12 after the first-ever live run against the real
    endpoint (verified directly by querying efts.sec.gov by hand): the
    original field names here were guessed from SEC_13F_extraction_
    reference.md's prose description and didn't match the actual JSON.
    The real per-hit _source carries the filer's CIK under "ciks" (plural,
    a list — not "cik"), and the accession number under "adsh" (not
    "accession"). Reading the wrong (nonexistent) keys meant `cik` was
    always None, so every single hit silently failed the `if not cik`
    check and got skipped — 13F refresh completed "successfully" with
    zero holders for every tracked ticker, no exception, no visible error.
    The hit's own _id (always 'accession:filename', confirmed live) is
    used as the primary source for accession/filename now, since it's
    guaranteed present; "adsh" is cross-checked as a fallback only."""
    holders = {}
    from_ = 0
    page_size = 10
    while from_ < max_results:
        data = _fulltext_search_page(phrase, startdt, enddt, from_=from_)
        hits = (data.get("hits") or {}).get("hits") or []
        if not hits:
            break
        for h in hits:
            src = h.get("_source", {})
            cik = src.get("ciks")
            if isinstance(cik, list):
                cik = cik[0] if cik else None
            if not cik:
                continue
            display = src.get("display_names")
            display = display[0] if isinstance(display, list) and display else display
            filer = _parse_display_name(display) or "Unknown filer"
            hit_id = h.get("_id", "")
            accession, filename = (hit_id.split(":", 1) + [None])[:2] if ":" in hit_id else (None, None)
            accession = accession or src.get("adsh")
            file_date = src.get("file_date", "")
            existing = holders.get(cik)
            if existing is None or file_date > existing.get("file_date", ""):
                holders[cik] = {
                    "filer": filer, "cik": cik, "accession": accession,
                    "filename": filename, "file_date": file_date,
                }
        total = ((data.get("hits") or {}).get("total") or {}).get("value", 0)
        from_ += page_size
        if from_ >= total:
            break
    return list(holders.values())


def _search_holders_for_ticker(company_name, startdt, enddt, max_results=150):
    """Same output shape core.fit_score/investors_page.py already expect
    from a holder-cache entry (filer/shares/value), built from EDGAR
    full-text search instead of the bulk dataset. shares/value can't come
    from a phrase search the way they could from filtering the full
    INFOTABLE dataset row-by-row — full-text search confirms WHO holds a
    position, not the exact share count or dollar value of that one
    position — so those are set to honest sentinels (shares=1: 'confirmed
    a nonzero position, exact count unknown'; value=0) with an explicit
    size_known=False flag so display code shows 'confirmed holder'
    instead of a fabricated-looking '1 shares / $0 reported'. shares=1
    (not None/0) is deliberate: live_peer_overlap_map's '> 0' holder check
    and get_cached_13f_holders_with_trend's NEW/EXITED detection both key
    off shares being truthy — those signals only ever needed presence,
    never magnitude, so they keep working unchanged; only ADD/TRIM
    (a magnitude comparison) is lost. cik/accession/filename ride along on
    every holder so a later purchasing-power backfill (see
    get_or_fetch_filer_book_total) can fetch that exact filer's own whole
    info table with zero extra discovery requests."""
    needle = (company_name or "").strip()
    if not needle:
        return []
    hits = _search_13f_holders_raw(needle, startdt, enddt, max_results=max_results)
    holders = [
        {
            "filer": h["filer"], "shares": 1, "value": 0, "size_known": False,
            "cik": h["cik"], "accession": h["accession"], "filename": h["filename"],
            "file_date": h["file_date"],
        }
        for h in hits
    ]
    return sorted(holders, key=lambda h: h["filer"])


def _fetch_filer_info_table_xml(cik, accession, filename):
    """Fetches ONE filer's own 13F information-table XML for a specific
    filing — the exact accession+filename EDGAR full-text search already
    told us about that filer (see _search_13f_holders_raw), so this needs
    no index/discovery request first. URL form per
    SEC_13F_extraction_reference.md's endpoint map."""
    cik_int = str(int(cik))
    accession_nodash = accession.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{accession_nodash}/{filename}"
    resp = _get(url, timeout=20)
    return resp.content


def _infotable_entries(xml_bytes):
    """Yield {issuer, cusip, value, shares} for every <infoTable> in a filer's 13F information
    table. Matches by LOCAL tag name so it works whichever namespace the filing agent used."""
    root = ET.fromstring(xml_bytes)
    for el in root.iter():
        if el.tag.split("}")[-1] != "infoTable":
            continue
        rec = {}
        for ch in el.iter():
            t = ch.tag.split("}")[-1]
            txt = (ch.text or "").strip()
            if t == "nameOfIssuer":
                rec["issuer"] = txt
            elif t == "cusip":
                rec["cusip"] = txt
            elif t == "value":
                try:
                    rec["value"] = int(float(txt))
                except ValueError:
                    pass
            elif t == "sshPrnamt":
                try:
                    rec["shares"] = int(float(txt))
                except ValueError:
                    pass
        if rec:
            yield rec


def enrich_holder_positions(ticker, client_id=None, limit=None, throttle=0.2, issuer_token=None):
    """Upgrade presence-only holder rows to REAL magnitude.

    The full-text-search path (refresh_13f_holders) confirms WHO holds but not how much —
    shares=1/value=0/size_known=False. Each of those rows still carries the filer's accession +
    info-table filename, so we can fetch that one document and read the actual position (shares,
    value, cusip) plus the filer's whole-book total — no bulk market-wide download.

    This is the prerequisite for driving the target database off real 13F holders: without it a
    tenant refreshed via full-text search has no share counts, no AUM proxy and no geography.

    Idempotent: rows already marked size_known are skipped. Returns a summary dict.
    """
    import time
    from config.client_config import get_client, get_active_client_id

    tk = (ticker or "").upper()
    cid = client_id or get_active_client_id()
    key = SEC_13F_HOLDERS_KEY_FMT.format(ticker=tk)
    book = db.load_json(key, default=None, client_id=cid) or {}
    holders = book.get("holders") or []
    if not holders:
        return {"ticker": tk, "holders": 0, "enriched": 0, "reason": "no cached holders"}

    # Prefer CUSIP matching (exact); fall back to an issuer-name token from the client record.
    cusip = next((h.get("cusip") for h in holders if h.get("cusip")), None)
    if not issuer_token:
        nm = (get_client(cid) or {}).get("name") or tk
        issuer_token = re.sub(r"[^A-Za-z]", "", nm.split(",")[0].split()[0]).upper()

    todo = [h for h in holders if not h.get("size_known")]
    if limit:
        todo = todo[:limit]

    enriched, missed, failed = 0, 0, 0
    for h in todo:
        if not (h.get("cik") and h.get("accession") and h.get("filename")):
            failed += 1
            continue
        try:
            xml = _fetch_filer_info_table_xml(h["cik"], h["accession"], h["filename"])
        except Exception:
            failed += 1
            continue
        try:
            total, positions, mine = 0, 0, None
            for rec in _infotable_entries(xml):
                total += rec.get("value") or 0
                positions += 1
                if mine is None:
                    if cusip and rec.get("cusip") == cusip:
                        mine = rec
                    elif not cusip and issuer_token and issuer_token in (rec.get("issuer") or "").upper():
                        mine = rec
                        cusip = rec.get("cusip") or cusip   # learn it once, then match exactly
        except Exception:
            failed += 1
            continue

        h["book_total"] = total
        h["book_positions"] = positions
        if mine:
            h["shares"] = mine.get("shares") or 0
            h["value"] = mine.get("value") or 0
            h["cusip"] = mine.get("cusip") or h.get("cusip")
            h["size_known"] = True
            enriched += 1
        else:
            missed += 1        # filer's book fetched, but our issuer wasn't in it
        if throttle:
            time.sleep(throttle)

    book["holders"] = holders
    db.save_json(key, book, client_id=cid)
    return {"ticker": tk, "holders": len(holders), "attempted": len(todo),
            "enriched": enriched, "issuer_not_in_book": missed, "failed": failed, "cusip": cusip}


def filer_13f_filings(cik, limit=8):
    """A filer's recent 13F-HR filings, newest first: [{form, date, accession}].

    From EDGAR's submissions API, so it's the filer's own history by CIK — no name matching."""
    try:
        cik_i = int(str(cik).strip())
    except Exception:
        return []
    try:
        r = _get(f"https://data.sec.gov/submissions/CIK{cik_i:010d}.json", timeout=20)
        rec = (r.json() or {}).get("filings", {}).get("recent", {})
    except Exception:
        return []
    forms = rec.get("form") or []
    out = []
    for i, form in enumerate(forms):
        if not str(form).startswith("13F-HR"):
            continue
        out.append({"form": form,
                    "date": (rec.get("filingDate") or [None] * len(forms))[i],
                    "accession": (rec.get("accessionNumber") or [None] * len(forms))[i]})
        if len(out) >= limit:
            break
    return out


def _info_table_filename(cik, accession):
    """The information-table XML inside one accession. The submissions API gives us the primary
    doc (the cover page), not the holdings table, so read the accession's file index and pick the
    XML that isn't primary_doc."""
    try:
        cik_i = int(str(cik).strip())
    except Exception:
        return None
    acc = str(accession or "").replace("-", "")
    if not acc:
        return None
    try:
        r = _get(f"https://www.sec.gov/Archives/edgar/data/{cik_i}/{acc}/index.json", timeout=20)
        items = ((r.json() or {}).get("directory", {}) or {}).get("item", []) or []
    except Exception:
        return None
    xmls = [it.get("name") for it in items
            if str(it.get("name", "")).lower().endswith(".xml")
            and "primary_doc" not in str(it.get("name", "")).lower()]
    if not xmls:
        return None
    # prefer an explicitly-named info table when the agent provides one
    for n in xmls:
        if any(k in n.lower() for k in ("info", "table", "holding")):
            return n
    return xmls[0]


def _peer_key(name):
    """A peer's company name normalized for matching <nameOfIssuer>.

    Uses the first TWO significant tokens joined, not one. Matching on a single token is unsafe:
    "Global Payments" -> "global" matched "ZETA GLOBAL HOLDINGS CORP", which would have had IR
    telling a holder they own a peer they don't. "globalpayments" correctly fails that match."""
    stop = {"the", "inc", "incorporated", "corp", "corporation", "co", "company", "group",
            "holdings", "holding", "ltd", "limited", "plc", "llc", "lp"}
    toks = [t for t in re.sub(r"[^a-z0-9 ]", " ", str(name or "").lower()).split()
            if t not in stop]
    if not toks:
        return None
    return "".join(toks[:2]) if len(toks) >= 2 else toks[0]


def _issuer_key(name):
    """<nameOfIssuer> normalized the same way, for substring comparison against _peer_key."""
    stop = {"the", "inc", "incorporated", "corp", "corporation", "co", "company", "group",
            "holdings", "holding", "ltd", "limited", "plc", "llc", "lp"}
    toks = [t for t in re.sub(r"[^a-z0-9 ]", " ", str(name or "").lower()).split()
            if t not in stop]
    return "".join(toks)


def holder_history(cik, cusip=None, issuer_token=None, quarters=6, peers=None, throttle=0.2):
    """Profile ONE holder over time — the intelligence you want before calling them.

    Walks the filer's last `quarters` 13F filings and reads our position out of each, giving:
      * position history (shares/value per quarter) and the QoQ change
      * how long they've held (first quarter our issuer appears in the window)
      * peer overlap — which of the client's peers sit in the SAME book
    Peer overlap costs nothing extra: it comes out of info tables we're already fetching, which
    the position-enrichment pass was previously discarding.

    On-demand by design: this is several document fetches per holder, so it's meant to be run for
    the holder you're about to call, not swept across the book.
    """
    import time
    filings = filer_13f_filings(cik, limit=quarters)
    peer_keys = {}
    for p in (peers or []):
        k = _peer_key(p.get("name") if isinstance(p, dict) else p)
        if k:
            peer_keys[k] = (p.get("ticker") if isinstance(p, dict) else p)

    history, peer_hits, learned_cusip = [], {}, cusip
    for f in filings:
        name = _info_table_filename(cik, f["accession"])
        if not name:
            continue
        try:
            xml = _fetch_filer_info_table_xml(cik, f["accession"], name)
        except Exception:
            continue
        mine, total, positions = None, 0, 0
        for rec in _infotable_entries(xml):
            total += rec.get("value") or 0
            positions += 1
            issuer = (rec.get("issuer") or "").lower()
            if mine is None:
                if learned_cusip and rec.get("cusip") == learned_cusip:
                    mine = rec
                elif not learned_cusip and issuer_token and issuer_token.lower() in issuer:
                    mine = rec
                    learned_cusip = rec.get("cusip") or learned_cusip
            # peer overlap — only from the most recent filing we process
            if not history:
                ikey = _issuer_key(rec.get("issuer"))
                for k, tkr in peer_keys.items():
                    if k and ikey and k in ikey:
                        peer_hits.setdefault(tkr, {"issuer": rec.get("issuer"),
                                                   "value": rec.get("value"),
                                                   "shares": rec.get("shares")})
        history.append({"date": f["date"], "accession": f["accession"],
                        "shares": (mine or {}).get("shares"), "value": (mine or {}).get("value"),
                        "held": mine is not None, "book_total": total, "book_positions": positions})
        if throttle:
            time.sleep(throttle)

    held = [h for h in history if h["held"]]
    qoq = None
    if len(history) >= 2 and history[0]["held"] and history[1]["held"]:
        qoq = (history[0]["shares"] or 0) - (history[1]["shares"] or 0)

    # CHRONOLOGICAL view (oldest -> newest) with per-quarter deltas. `history` is newest-first
    # because that's how EDGAR returns it, and reading deltas off it backwards makes selling look
    # like buying — so state the direction explicitly rather than leaving it to the caller.
    chrono = list(reversed(history))
    prev = None
    for h in chrono:
        h["change_vs_prior"] = None if (prev is None or not h["held"] or h["shares"] is None) \
            else h["shares"] - prev
        if h["shares"] is not None:
            prev = h["shares"]
    first_held = next((h for h in chrono if h["held"]), None)
    last_held = next((h for h in reversed(chrono) if h["held"]), None)
    net = None
    if first_held and last_held and first_held is not last_held:
        net = (last_held["shares"] or 0) - (first_held["shares"] or 0)
    direction = None
    if net is not None:
        direction = "trimming" if net < 0 else ("adding" if net > 0 else "flat")

    return {"cik": str(cik), "cusip": learned_cusip, "quarters_examined": len(history),
            "history": history, "chronological": chrono,
            "qoq_change_shares": qoq,
            "net_change_shares": net, "direction": direction,
            "quarters_held_in_window": len(held),
            "held_since_at_least": held[-1]["date"] if held else None,
            "continuous": all(h["held"] for h in history) if history else False,
            "peer_overlap": peer_hits}


def _sum_info_table_value(xml_bytes):
    """Sums every <value> element in a 13F information-table XML — this
    filer's WHOLE quarter-end 13F book (every issuer they hold, not just
    the one whose search hit led us here). Matches by local tag name only
    (ignoring the XML namespace), since the namespace URI varies by which
    EDGAR filer-agent software a manager's filing agent used."""
    root = ET.fromstring(xml_bytes)
    total = 0
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag.lower() == "value" and el.text:
            try:
                total += int(float(el.text.strip()))
            except ValueError:
                continue
    return total


def _filer_book_cache_key(cik):
    return f"sec_13f_filer_book_{cik}.json"


def get_or_fetch_filer_book_total(cik, accession, filename, quarter_label):
    """Cached per (cik, quarter) — the "purchasing power" signal
    core/fit_score.py needs, computed lazily and per-filer instead of in
    one big pass over the whole market's bulk dataset (see module history:
    that bulk pass, _compute_book_totals, is what made 'Refresh 13F' hang;
    replaced 2026-07-12 with EDGAR full-text search for holder lookups
    plus this on-demand per-filer fetch for whole-book sizing).

    A single lightweight request per filer — deliberately called for a
    BOUNDED set of filers (score_all_holders's visible top N, not every
    confirmed holder of a peer ticker; see
    SEC_13F_extraction_reference.md's own "skip filers whose info table
    exceeds the fetch limit" guidance — same idea, applied by only ever
    fetching whoever actually needs to show a real number). Returns None
    (and caches that None) if the fetch/parse fails for any reason —
    purchasing power then just falls back to its existing neutral 'M'
    default, same as "no 13F refresh has run yet."""
    cache_key = _filer_book_cache_key(cik)
    cached = db.load_json(cache_key, default=None)
    if cached and cached.get("quarter") == quarter_label and cached.get("total") is not None:
        return cached["total"]
    try:
        xml_bytes = _fetch_filer_info_table_xml(cik, accession, filename)
        total = _sum_info_table_value(xml_bytes)
    except Exception as e:
        print(f"[sec_filings] Book-total fetch failed for CIK {cik}: {e}")
        total = None
    db.save_json(cache_key, {"quarter": quarter_label, "total": total, "_fetched_at": datetime.now().isoformat()})
    return total


def get_cached_filer_refs(peer_tickers):
    """{filer_name: {cik, accession, filename, quarter}} built from the
    CACHED per-ticker 13F holder lists for `peer_tickers` — no network,
    same batched-read pattern as live_peer_overlap_map. This is what lets
    a caller (score_all_holders) turn "these fund names need a real
    purchasing-power number" into the cik/accession/filename
    get_or_fetch_filer_book_total needs, without re-searching EDGAR. If
    the same filer shows up under more than one peer ticker, whichever is
    read last wins — they all point at the same manager's same-quarter
    filing, so any one of them fetches the correct whole book."""
    refs = {}
    for t in peer_tickers:
        cached = get_cached_13f_holders(t)
        if not cached.get("quarter"):
            continue
        for h in cached.get("holders", []):
            filer = h.get("filer")
            if filer and h.get("cik") and h.get("accession") and h.get("filename"):
                refs[filer] = {
                    "filer": filer, "cik": h["cik"], "accession": h["accession"],
                    "filename": h["filename"], "quarter": cached["quarter"],
                }
    return refs


def ensure_book_totals(filer_refs, quarter_label):
    """filer_refs: iterable of dicts with filer/cik/accession/filename
    (e.g. from get_cached_filer_refs, filtered down to whichever prospects
    a caller is about to display). Fetches + caches a real book total for
    whichever of these don't already have one cached for this quarter,
    then persists the merged {filer_name: total} dict under the same
    SEC_13F_BOOK_TOTALS_KEY get_all_cached_book_totals()/
    get_cached_book_total() already read — those two accessors don't
    change at all; this just changes how that shared cache gets
    populated (incrementally, filer by filer, on demand) instead of one
    big bulk-dataset pass. No return value — callers re-read via those
    accessors after calling this."""
    totals = get_all_cached_book_totals()
    changed = False
    for ref in filer_refs:
        filer = ref.get("filer")
        if not filer or filer in totals:
            continue
        cik, accession, filename = ref.get("cik"), ref.get("accession"), ref.get("filename")
        if not (cik and accession and filename):
            continue
        total = get_or_fetch_filer_book_total(cik, accession, filename, quarter_label)
        if total is not None:
            totals[filer] = total
            changed = True
    if changed:
        db.save_json(SEC_13F_BOOK_TOTALS_KEY, {"quarter": quarter_label, "totals": totals,
                                                "_fetched_at": datetime.now().isoformat()})


def get_cached_book_total(filer_name):
    """Cache-only accessor — a filer's total 13F portfolio value for the
    most recently refreshed quarter. None if no 13F refresh has run yet,
    or if this filer wasn't present in that quarter's bulk dataset (e.g.
    a fund that only files 13F occasionally, or a name-matching miss).

    Single-filer convenience wrapper — does one db.load_json() call. Do
    NOT call this in a loop over many filers (e.g. every holder of a
    peer ticker); that fires one Neon round-trip per filer and can
    block the event loop long enough to trip the browser's websocket
    ping timeout ("Connection lost"). Loop callers should use
    get_all_cached_book_totals() once, then dict.get() per filer."""
    cached = db.load_json(SEC_13F_BOOK_TOTALS_KEY, default=None)
    if not cached:
        return None
    return cached.get("totals", {}).get(filer_name)


def get_all_cached_book_totals():
    """Bulk accessor — the full {filer_name: total_value} dict from the
    most recently refreshed quarter, in ONE db.load_json() call. Use this
    (not get_cached_book_total in a loop) whenever you need book totals
    for many filers at once, e.g. core.fit_score.score_all_holders()
    scoring every confirmed holder of a peer ticker — a large peer like
    GDOT or EEFT can easily have 100+ holders, and 100+ sequential Neon
    round-trips inside one synchronous call is exactly what caused the
    2026-07-11 bug where clicking "Rank by Fit Score" froze the event
    loop long enough for the client to report "Connection lost."
    Returns {} if no 13F refresh has computed book totals yet."""
    cached = db.load_json(SEC_13F_BOOK_TOTALS_KEY, default=None)
    if not cached:
        return {}
    return cached.get("totals", {})


def _qoq_trend(cur_shares, prior_shares):
    """Ported near-verbatim from IR OS's position_econ.py qoq_trend() —
    classifies one holder's quarter-over-quarter share-count change.
    NEW/EXITED are the two "hard" signals (a fund entering or leaving a
    position entirely); ADD/TRIM use a 10% move as the threshold for
    "meaningful," matching the source. This is pure logic, no I/O — safe
    to unit test against fixtures."""
    if prior_shares in (None, 0) and cur_shares:
        return "NEW"
    if cur_shares in (None, 0) and prior_shares:
        return "EXITED"
    if cur_shares is None or prior_shares is None:
        return "n/a"
    d = cur_shares - prior_shares
    if d == 0:
        return "FLAT"
    pct = d / prior_shares * 100
    if pct >= 10:
        return f"ADD +{pct:.0f}%"
    if pct <= -10:
        return f"TRIM {pct:.0f}%"
    return "~flat"


def get_cached_13f_holders_prior(ticker):
    """The quarter-before-last-refresh snapshot for `ticker`, archived by
    refresh_13f_for_tracked_tickers right before it overwrites the
    "current" cache — see that function's docstring. Empty holder list if
    no prior quarter has been archived yet (e.g. this is the first-ever
    refresh for this ticker)."""
    key = SEC_13F_HOLDERS_PRIOR_KEY_FMT.format(ticker=ticker.upper())
    return db.load_json(key, default={"quarter": None, "holders": []})


def get_cached_13f_holders_with_trend(ticker):
    """Same as get_cached_13f_holders, but each holder also carries a
    'trend' field (NEW / ADD +x% / TRIM -x% / ~flat / FLAT / n/a) from
    diffing against get_cached_13f_holders_prior. A holder that was in the
    prior quarter but has fully exited (0 shares now, so it no longer
    appears as a "current" INFOTABLE row at all) is appended explicitly
    with trend='EXITED' and shares=0 — "someone just sold out entirely" is
    itself a real signal that a plain iteration over current holders would
    silently miss, since an exited holder has no current row to iterate.

    This is the 'newbuyer' signal core/fit_score.py's scoring needs — a
    holder here with trend == 'NEW' is exactly what IR OS's rec["newbuyer"]
    boolean meant. Cache-only, same non-blocking contract as
    get_cached_13f_holders — never triggers a live fetch."""
    cur = get_cached_13f_holders(ticker)
    prior = get_cached_13f_holders_prior(ticker)
    prior_shares = {h["filer"]: h.get("shares", 0) for h in prior.get("holders", [])}

    cur_filers = set()
    annotated = []
    for h in cur.get("holders", []):
        h = dict(h)
        cur_filers.add(h["filer"])
        h["trend"] = _qoq_trend(h.get("shares", 0), prior_shares.get(h["filer"]))
        annotated.append(h)
    for filer, shares in prior_shares.items():
        if filer not in cur_filers and shares:
            annotated.append({"filer": filer, "shares": 0, "value": 0, "trend": "EXITED"})

    result = dict(cur)
    result["holders"] = annotated
    return result


def _archive_prior_if_new_quarter(ticker, new_label):
    """Before a ticker's "current" 13F cache gets overwritten, shift
    whatever was there into the "prior" slot — but only if the incoming
    quarter is actually different from what's already cached. Re-running a
    refresh mid-quarter (e.g. re-pulling after fixing a bug, or a second
    manual click) must NOT stomp real prior-quarter history with this same
    quarter's own data — that would make every holder look like a 'NEW'
    buyer relative to itself. See get_cached_13f_holders_with_trend."""
    existing = db.load_json(SEC_13F_HOLDERS_KEY_FMT.format(ticker=ticker.upper()), default=None)
    if existing and existing.get("quarter") and existing.get("quarter") != new_label:
        db.save_json(SEC_13F_HOLDERS_PRIOR_KEY_FMT.format(ticker=ticker.upper()), existing)


def refresh_13f_holders(ticker, company_name):
    """Live EDGAR full-text-search fetch of institutional 13F holders in
    `ticker` for the latest completed quarter. Heavy-ish (a handful of
    paginated SEC requests, see module history) — call this from a manual
    'Refresh 13F Holders' button or a quarterly schedule, never from a
    page render or the startup hook. Purchasing-power book totals are
    NOT computed here anymore — see get_or_fetch_filer_book_total /
    ensure_book_totals, called lazily by core/fit_score.py for whichever
    prospects actually get displayed, instead of for every holder up
    front."""
    startdt, enddt, label = _quarter_search_window()
    holders = _search_holders_for_ticker(company_name, startdt, enddt)
    result = {
        "quarter": label, "holders": holders,
        "_fetched_at": datetime.now().isoformat(), "_error": None,
    }
    _archive_prior_if_new_quarter(ticker, label)
    db.save_json(SEC_13F_HOLDERS_KEY_FMT.format(ticker=ticker.upper()), result)
    return result


def refresh_13f_for_tracked_tickers(ticker_name_pairs):
    """Refreshes institutional 13F holders for every tracked ticker (the
    active client + its full peer universe) via EDGAR full-text search —
    one targeted, paginated search per ticker, scoped to that company's
    name within the latest completed quarter's filing window.

    REPLACED 2026-07-12 (see SEC_13F_extraction_reference.md, ported from
    a sibling project's working usio_prospects.py/wrap_target.py): this
    used to download and parse SEC's entire quarterly bulk structured
    dataset ONCE and filter it down to tracked tickers client-side — every
    institutional manager's every position across the whole market, tens
    of MB compressed and dramatically larger unzipped. That download was
    the real cause of a "Refresh 13F" click looking hung/frozen; even
    wrapped in a background thread (see the async refresh_13f handler in
    investors_page.py) it could take minutes with no visible progress.
    Full-text search per ticker is a handful of lightweight JSON requests
    instead — slower in one sense (N tickers = N searches instead of one
    shared download) but each one is fast and bounded, so the total is
    both quicker in practice and, critically, predictable.

    Purchasing-power book totals are NOT computed here — see
    get_or_fetch_filer_book_total's docstring for why that moved to a
    lazy, per-filer, visible-results-only fetch instead of a bulk pass
    over every confirmed holder.

    Each ticker's search is wrapped in its own try/except — same
    isolation fix as before (2026-07-10): one ticker's failure (a bad
    response shape, a transient SEC error) shouldn't abort every ticker
    still queued after it.

    Saves each ticker's result to the same per-ticker cache key
    (SEC_13F_HOLDERS_KEY_FMT) this always used, so every existing reader
    (get_cached_13f_holders, live_peer_overlap_map, the SEC Intelligence
    tab) is unaffected — this only changes HOW the cache gets populated
    and what shape each holder record carries (cik/accession/filename/
    size_known added; shares/value are now sentinels — see
    _search_holders_for_ticker), not the cache's top-level shape.

    Returns {ticker: result_dict}."""
    startdt, enddt, label = _quarter_search_window()
    results = {}
    for ticker, company_name in ticker_name_pairs:
        try:
            holders = _search_holders_for_ticker(company_name, startdt, enddt)
            result = {
                "quarter": label, "holders": holders,
                "_fetched_at": datetime.now().isoformat(), "_error": None,
            }
        except Exception as e:
            result = {
                "quarter": label, "holders": [],
                "_fetched_at": datetime.now().isoformat(), "_error": str(e),
            }
        _archive_prior_if_new_quarter(ticker, label)
        db.save_json(SEC_13F_HOLDERS_KEY_FMT.format(ticker=ticker.upper()), result)
        results[ticker] = result

    return results


def _read_tsv_member(zf, base):
    """Yield rows (dicts) from a TAB-delimited member of the 13F dataset zip
    whose name ends with `base` (e.g. 'INFOTABLE.TSV'), streaming rather than
    loading the whole (large) member into memory."""
    member = next((n for n in zf.namelist() if n.upper().endswith(base)), None)
    if not member:
        return
    with zf.open(member) as fh:
        reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8", errors="replace"), delimiter="\t")
        for row in reader:
            yield row


def refresh_13f_bulk_all(ticker_name_pairs):
    """Complete institutional 13F holders for every tracked ticker, from SEC's
    quarterly Form 13F BULK structured dataset — filtered by issuer, joined to
    the filing manager. Unlike the EDGAR full-text-search path (which only
    confirms WHO holds a position, sparsely, for issuers its index happens to
    cover), this returns the EXACT, COMPLETE holder list with real share counts
    and dollar values — the same source Irwin/S&P consume.

    One ~100MB download covers the whole tracked universe (client + peers), so
    this streams the INFOTABLE once and fans each row out to whichever tracked
    issuer it matches (normalized-name token subset — 'Usio, Inc.' ↔ 'USIO INC
    COM'). Heavy and slow (download + parse) — call from an explicit button or
    a quarterly schedule in a background thread, never a page render.

    Writes the same per-ticker cache shape (SEC_13F_HOLDERS_KEY_FMT) every
    existing reader already expects, but with size_known=True and real
    shares/value, plus city/state and the resolved CUSIP. Returns
    {ticker: result_dict}."""
    zip_url, label = _latest_13f_dataset()
    resp = _get(zip_url, timeout=300)
    zf = zipfile.ZipFile(io.BytesIO(resp.content))

    # Small tables loaded fully: accession -> manager identity / filing meta.
    cover = {}
    for row in _read_tsv_member(zf, "COVERPAGE.TSV"):
        acc = (row.get("ACCESSION_NUMBER") or "").strip()
        cover[acc] = (
            (row.get("FILINGMANAGER_NAME") or "").strip(),
            (row.get("FILINGMANAGER_CITY") or "").strip(),
            (row.get("FILINGMANAGER_STATEORCOUNTRY") or "").strip(),
        )
    submission = {}
    for row in _read_tsv_member(zf, "SUBMISSION.TSV"):
        acc = (row.get("ACCESSION_NUMBER") or "").strip()
        submission[acc] = ((row.get("FILING_DATE") or "").strip(), (row.get("CIK") or "").strip())

    targets = [(tk, set(_normalize_company_name(nm).split())) for tk, nm in ticker_name_pairs]

    # PASS 1 — name-match (issuer-name token subset) only to DISCOVER each
    # ticker's CUSIP. The name match is conservative: it misses abbreviated issuer
    # spellings a filer might use ("REPAY HLDGS CORP" vs our "Repay Holdings"), so
    # it under-counts holders — but it's reliable enough to learn the security's
    # 9-char CUSIP, which every filer of the same security reports identically.
    # While we're streaming the whole INFOTABLE once, also accumulate each
    # filer's TOTAL book value and position count (per accession) — the
    # denominator for conviction/concentration and the breadth signal that
    # separates active managers from quasi-index holders. Free here (one pass),
    # vs a per-filer XML fetch that needs a filename the bulk rows don't carry.
    book_val = Counter()
    book_cnt = Counter()
    cusip_seen = {tk: Counter() for tk, _t in targets}
    for row in _read_tsv_member(zf, "INFOTABLE.TSV"):
        if (row.get("PUTCALL") or "").strip():     # options, not share ownership
            continue
        acc = (row.get("ACCESSION_NUMBER") or "").strip()
        try:
            book_val[acc] += int(float(row.get("VALUE") or 0))
        except (TypeError, ValueError):
            pass
        book_cnt[acc] += 1
        issuer_tokens = set(_normalize_company_name(row.get("NAMEOFISSUER") or "").split())
        if not issuer_tokens:
            continue
        matched = [tk for tk, toks in targets if toks and toks.issubset(issuer_tokens)]
        if not matched:
            continue
        cusip = (row.get("CUSIP") or "").strip()
        if cusip:
            for tk in matched:
                cusip_seen[tk][cusip] += 1

    # Resolve each ticker to its CUSIP(s) and invert to CUSIP -> tickers. Keep the
    # dominant CUSIP plus any share-class variant with a meaningful share of the
    # count; drop one-off typos so a fat-fingered CUSIP can't pull a wrong issuer.
    resolved_cusip = {}
    cusip_to_tk = {}
    for tk, ctr in cusip_seen.items():
        if not ctr:
            continue
        top_cusip, top_n = ctr.most_common(1)[0]
        resolved_cusip[tk] = top_cusip
        for c, n in ctr.items():
            if c and (c == top_cusip or n >= max(3, top_n * 0.2)):
                cusip_to_tk.setdefault(c, []).append(tk)

    # PASS 2 — CUSIP-match to collect the COMPLETE holder list: every filing of
    # that security, however the filer spelled the issuer name. This is what
    # closes the gap (e.g. RPAY jumps from the name-match subset to the full set).
    per = {tk: {} for tk, _t in targets}
    for row in _read_tsv_member(zf, "INFOTABLE.TSV"):
        if (row.get("PUTCALL") or "").strip():
            continue
        cusip = (row.get("CUSIP") or "").strip()
        tks = cusip_to_tk.get(cusip)
        if not tks:
            continue
        acc = (row.get("ACCESSION_NUMBER") or "").strip()
        mgr = cover.get(acc)
        if not mgr or not mgr[0]:
            continue
        try:
            shares = int(float(row.get("SSHPRNAMT") or 0))
        except (TypeError, ValueError):
            shares = 0
        try:
            value = int(float(row.get("VALUE") or 0))
        except (TypeError, ValueError):
            value = 0
        fdate, cik = submission.get(acc, ("", ""))
        key = _normalize_company_name(mgr[0]) or mgr[0].upper()
        for tk in tks:
            h = per[tk].get(key)
            if h:
                h["shares"] += shares
                h["value"] += value
            else:
                per[tk][key] = {
                    "filer": mgr[0], "shares": shares, "value": value, "size_known": True,
                    "cik": cik, "accession": acc, "filename": "", "file_date": fdate,
                    "city": mgr[1], "state": mgr[2], "cusip": cusip,
                    # Whole-book context for conviction scoring (from the same file).
                    "book_total": book_val.get(acc) or None, "book_positions": book_cnt.get(acc) or None,
                }

    results = {}
    for tk, _t in targets:
        holders = sorted(per[tk].values(), key=lambda h: -h["shares"])
        result = {
            "quarter": label, "holders": holders, "source": "bulk-cusip",
            "cusip": resolved_cusip.get(tk),
            "_fetched_at": datetime.now().isoformat(), "_error": None,
        }
        _archive_prior_if_new_quarter(tk, label)
        db.save_json(SEC_13F_HOLDERS_KEY_FMT.format(ticker=tk.upper()), result)
        results[tk] = result
    return results


def get_cached_13f_holders(ticker):
    """Cache-only accessor for page code — 13F refresh is quarterly/manual
    (see refresh_13f_holders), never triggered inline by a page render."""
    key = SEC_13F_HOLDERS_KEY_FMT.format(ticker=ticker.upper())
    return db.load_json(key, default={"quarter": None, "holders": [], "_fetched_at": None, "_error": "not yet fetched"})


def normalize_company_name(name):
    """Public wrapper around _normalize_company_name — the same
    punctuation/suffix-stripping normalization live_peer_overlap_map uses
    below to match SEC issuer/filer strings, exposed for callers outside
    this module that need to match a fund/company name against SEC's
    naming conventions."""
    return _normalize_company_name(name)


def live_peer_overlap_map(fund_names, peer_tickers):
    """For each fund in `fund_names`, checks every ticker in `peer_tickers`
    for a confirmed 13F institutional position, using cached data only
    (never triggers a live fetch — see get_cached_13f_holders).

    Matching is EXACT on the normalized name, not fuzzy substring, on
    purpose: 13F is filed at the parent-manager level (SEC sees "VANGUARD
    GROUP INC", not a specific fund/strategy within it). A fuzzy/substring
    match would misattribute one manager's aggregate position to every
    differently-named product under that umbrella — e.g. matching
    "BlackRock Small Cap Growth" (a specific strategy, not itself a 13F
    filer) against "BLACKROCK INC"'s aggregate position would be a
    confident-looking but false claim. Exact-match means some real
    strategy-level institutions in a curated list won't resolve to a
    filing (they aren't the filer of record) — that's treated as "unknown"
    (not_fetched-style caller handling), never silently guessed.

    Returns {fund_name: {"confirmed": [tickers with a real match],
    "not_fetched": [tickers with no 13F data cached yet]}}. A ticker
    appearing in neither list means its 13F data IS cached but this fund
    is confirmed NOT among its holders — a real negative, distinct from
    "we haven't checked" (not_fetched) or "we found a match" (confirmed).

    Batched (one cache read per ticker, not per fund x ticker) since this
    is meant to run once per page render across every tracked institution."""
    per_ticker = {t: get_cached_13f_holders(t) for t in peer_tickers}
    normalized_holders = {}
    for t, cached in per_ticker.items():
        if cached.get("quarter"):
            normalized_holders[t] = {
                _normalize_company_name(h.get("filer", "")): h.get("shares", 0)
                for h in cached.get("holders", [])
            }

    result = {}
    for fund_name in fund_names:
        needle = _normalize_company_name(fund_name)
        confirmed, not_fetched = [], []
        for t in peer_tickers:
            if per_ticker[t].get("quarter") is None:
                not_fetched.append(t)
            elif normalized_holders.get(t, {}).get(needle, 0) > 0:
                confirmed.append(t)
        result[fund_name] = {"confirmed": confirmed, "not_fetched": not_fetched}
    return result


# ─────────────────────────────────────────────────────────────────────────
# Orchestration — what the startup hook and the Refresh buttons call
# ─────────────────────────────────────────────────────────────────────────
def tracked_tickers():
    """Client's own ticker + its full peer universe
    (config.client_config.CP()) — the same peer list already used
    throughout Markets/Investors, so 'competitors to watch' isn't a
    second list to keep in sync; it's this one."""
    from config.client_config import C, CP
    client = C()
    tickers = [(client["ticker"], client["name"])]
    tickers += [(p["ticker"], p["name"]) for p in CP()]
    return tickers


def coverage_tickers(client_id=None):
    """The analyst COVERAGE-NETWORK tickers (every stock our covering analysts
    also rate), as (ticker, name) pairs, excluding anything already in the peer
    universe.

    Deliberately NOT part of tracked_tickers(): these are not USIO comps and must
    never leak into valuation/benchmarking or the peer medians — they exist only
    so the coverage-network prospecting pipeline has real holder data to mine
    ("who else owns Scott Buck's names?"). Keeping the two sets separate is what
    lets the curated comp tiering stay clean.
    """
    from core.analyst_coverage import get_coverage
    have = {t.upper() for t, _n in tracked_tickers()}
    out, seen = [], set()
    for entry in (get_coverage(client_id) or {}).values():
        for s in entry.get("coverage", []) or []:
            tk = (s.get("ticker") or "").strip()
            if not tk or tk.upper() in have or tk.upper() in seen:
                continue
            seen.add(tk.upper())
            out.append((tk, s.get("name") or tk))
    return out


def holder_pull_tickers(client_id=None):
    """Every issuer we want COMPLETE 13F holder lists for = the peer universe
    (benchmarking + peer overlap) PLUS the coverage network (prospecting). This
    is the set to hand refresh_13f_bulk_all: one ~100MB scan fans out to all of
    them, so the extra tickers are nearly free."""
    return tracked_tickers() + coverage_tickers(client_id)


def refresh_all(include_13f=False, force_13d13g=False):
    """Refreshes 13D/13G for every tracked ticker (cheap — meant to run
    ~daily; this is what app_nicegui.py's startup hook calls in the
    background). include_13f=True additionally refreshes institutional
    holders for every tracked ticker (expensive — meant to run
    quarterly/on demand, not on every startup). Returns a run-log dict
    that the Investors -> SEC Intelligence tab displays.

    force_13d13g=True bypasses the 24h TTL and always hits SEC live for
    13D/13G — pass this from a manual 'Refresh Now' button click (see
    investors_page.py), where the whole point of clicking is to get the
    live filings right now, not to conditionally hit the network only if
    the cache happens to be stale. Leave it False for the automatic
    startup-hook call, which should stay TTL-gated so it doesn't hammer
    SEC on every server restart.

    13D/13G stays a per-ticker loop (cheap, independent lookups per
    issuer). 13F is ALSO now a per-ticker loop — see
    refresh_13f_for_tracked_tickers's docstring: since the 2026-07-12
    rewrite to EDGAR full-text search, each ticker's search is its own
    small, bounded request instead of a shared multi-minute bulk-dataset
    download, so looping per ticker no longer means redoing an expensive
    shared fetch N times."""
    log = {"started_at": datetime.now().isoformat(), "results": []}
    tracked = tracked_tickers()

    for ticker, name in tracked:
        entry = {"ticker": ticker}
        try:
            r = get_cached_13d_13g(ticker, refresh_if_stale=True, force=force_13d13g)
            entry["13d13g_count"] = len(r.get("filings", []))
            entry["13d13g_error"] = r.get("_error")
        except Exception as e:
            entry["13d13g_error"] = str(e)
        log["results"].append(entry)

    if include_13f:
        try:
            results = refresh_13f_for_tracked_tickers(tracked)
        except Exception as e:
            results = {}
            for entry in log["results"]:
                entry["13f_error"] = str(e)
        else:
            for entry in log["results"]:
                r = results.get(entry["ticker"])
                if r is not None:
                    entry["13f_holder_count"] = len(r.get("holders", []))
                    entry["13f_error"] = r.get("_error")

    log["finished_at"] = datetime.now().isoformat()
    db.save_json(SEC_REFRESH_LOG_KEY, log)
    return log


def get_last_refresh_log():
    return db.load_json(SEC_REFRESH_LOG_KEY, default=None)
