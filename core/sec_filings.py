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

import io
import re
import time
import zipfile
import xml.etree.ElementTree as ET
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
    # "EXAMPLE": "1234567",
}

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


def _get(url, params=None, timeout=15):
    resp = requests.get(url, params=params, headers={"User-Agent": _user_agent()}, timeout=timeout)
    resp.raise_for_status()
    time.sleep(_REQUEST_DELAY_SEC)
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
    Uses SEC's free company_tickers.json (no API key needed), cached in
    SQLite for a week at a time since this list barely changes day to
    day. MANUAL_CIK_OVERRIDES is checked first."""
    ticker = ticker.upper().strip()
    if ticker in MANUAL_CIK_OVERRIDES:
        return str(MANUAL_CIK_OVERRIDES[ticker]).zfill(10)

    cached = db.load_json(SEC_TICKER_MAP_KEY, default=None)
    if cached is None or _is_stale(cached.get("_fetched_at"), timedelta(days=SEC_TICKER_MAP_TTL_DAYS)):
        cached = _refresh_ticker_cik_map()

    cik = (cached or {}).get(ticker)
    return cik.zfill(10) if cik else None


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
    Deduped by CIK, keep