"""
core/prospecting.py — Target Database's automated prospecting tools, ported
from app.py's "Automated Prospecting Pipeline" and "NOBO Cross-Reference"
(both previously un-ported — see page_modules_nicegui/investors_page.py's
module docstring history). Three independent pieces:

1. Coverage-network prospecting (generate_coverage_prospects) — for a
   covering analyst's other Buy-rated tickers (core.analyst_coverage), pull
   REAL institutional holders from core.sec_filings' live SEC 13F cache and
   rank them as prospects. This is a genuine improvement on app.py's
   original version, not just a straight port: the original's "Automated
   Prospecting Pipeline" button read from a hardcoded KNOWN_13F_HOLDERS
   dict covering six unrelated demo tickers (FPAY/WYY/AEYE/INUV/RPAY/PRTH)
   — it never actually queried SEC. core.sec_filings now has a real, working
   13F fetcher (fixed 2026-07-10), so this rebuild uses that instead of a
   static guess. A ticker only contributes real prospects once its 13F data
   has actually been refreshed from the SEC Intelligence tab — see
   not_fetched_tickers below.

2. NOBO cross-reference (save_nobo_list / get_nobo_list / match_against_nobo)
   — compares a list of names (call-listener log, prospect queue, coverage
   prospects) against this client's actual NOBO shareholder file (requested
   from the transfer agent quarterly) to separate "already an identified
   shareholder" from "genuine, unconfirmed prospect." Same substring
   fuzzy-match app.py used (NOBO exports are inconsistent about legal-entity
   suffixes — "BlackRock Inc" vs "BlackRock, Inc." — so exact match would
   miss real matches; a stricter matcher can be swapped in later if false
   positives turn up on a specific client's data).

3. Bulk-paste table parsing (parse_pasted_table) — a fallback for sites
   whose holder tables don't survive copy/paste as clean columns (WhaleWisdom
   in particular renders styled grids, not plain HTML tables). Tab-separated
   if present, otherwise splits on 2+ spaces. Pure function, no I/O, so the
   caller (investors_page.py) owns the review-before-add UI step — this
   never writes anything on its own.
"""

from datetime import datetime

from core import db, peer_prospects, sec_filings

_NOBO_KEY = "nobo_list.json"
# Above this many 13F positions a book is an index/quant sleeve, not a conviction
# holder. Matches the breadth reasoning in core.peer_prospects.
_MAX_BREADTH = 800


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def _name_matches(a, b):
    """Same lightweight matcher app.py used for both '_matches_known_holder'
    and the NOBO comparison: case-insensitive substring either direction, or
    first-word match for names with a long-enough first word. Deliberately
    permissive — the cost of a false positive here (a real prospect gets
    hidden) is judged worse than the cost of a false negative (a human
    re-verifies one extra name), same tradeoff app.py made explicitly."""
    an, bn = str(a).lower().strip(), str(b).lower().strip()
    if not an or not bn:
        return False
    if an in bn or bn in an:
        return True
    a_first, b_first = an.split()[0], bn.split()[0]
    return a_first == b_first and len(a_first) > 4


# ─────────────────────────────────────────────────────────────────────────
# 1. Coverage-network prospecting
# ─────────────────────────────────────────────────────────────────────────
def generate_coverage_prospects(analyst_key, min_relevance=50, known_fund_names=None, client_id=None):
    """known_fund_names: names already tracked in the buy-side roster and/or
    prospect queue — excluded from results so this never re-suggests a fund
    the team already knows about. Passed in by the caller (investors_page.py)
    rather than imported here, since core/ modules don't import
    page_modules_nicegui/ (would be a reverse dependency)."""
    from core.analyst_coverage import get_coverage

    cid = _resolve_client_id(client_id)
    coverage = get_coverage(cid)
    if analyst_key not in coverage:
        return {"qualifying_stocks": [], "prospects": [], "not_fetched_tickers": []}

    analyst_data = coverage[analyst_key]
    known_fund_names = known_fund_names or set()

    qualifying = [s for s in analyst_data["coverage"]
                  if s.get("rating") == "Buy" and s.get("relevance", 0) >= min_relevance]

    prospects = []
    ria_holders = []
    not_fetched = []
    seen_funds = set()
    filtered_passive = 0
    filtered_breadth = 0
    for stock in sorted(qualifying, key=lambda s: -s.get("relevance", 0)):
        ticker = stock["ticker"]
        cached = sec_filings.get_cached_13f_holders(ticker)
        if not cached.get("quarter"):
            not_fetched.append(ticker)
            continue
        for h in cached.get("holders", []):
            fund = h.get("filer", "")
            if not fund or fund in seen_funds:
                continue
            if any(_name_matches(fund, known) for known in known_fund_names):
                continue
            # Quality gates — this pipeline used to dump every 13F holder of the
            # analyst's coverage stocks straight at the IR lead, surfacing market
            # makers (Optiver), mega-banks (Wells Fargo) and RIA aggregators as
            # "prospects". Same two filters the Peer Prospects queue already
            # applies, sharing peer_prospects' denylist so one list governs both.
            if peer_prospects.is_passive(fund):
                seen_funds.add(fund)
                filtered_passive += 1
                continue
            # RIAs / wealth managers aren't institutional NDR targets (no PM to
            # pitch), but they DO own the stock — so they go to their own bucket
            # instead of the bin, and only when there's a real position behind
            # the name. A filer with no known share count tells us nothing
            # actionable, so it's dropped rather than shown as an empty row.
            if peer_prospects.is_ria(fund):
                seen_funds.add(fund)
                if h.get("size_known", True) and (h.get("shares") or 0) > 0:
                    ria_holders.append({
                        "fund": fund,
                        "source_ticker": ticker,
                        "source_name": stock.get("name", ticker),
                        "relevance": stock.get("relevance", 0),
                        "shares": h.get("shares", 0),
                        "value": h.get("value", 0),
                        "size_known": True,
                    })
                continue
            # Generic catch for the noise the denylist doesn't name: a book with
            # this many positions is an index/quant sleeve, not a conviction
            # holder who'd take a micro-cap NDR. Only applied when the bulk 13F
            # data actually gave us a position count.
            if (h.get("book_positions") or 0) > _MAX_BREADTH:
                seen_funds.add(fund)
                filtered_breadth += 1
                continue
            seen_funds.add(fund)
            bridge = stock.get("bridge", "")
            bridge_short = (bridge[:160] + "...") if len(bridge) > 160 else bridge
            prospects.append({
                "fund": fund,
                "source_ticker": ticker,
                "source_name": stock.get("name", ticker),
                "relevance": stock.get("relevance", 0),
                "shares": h.get("shares", 0),
                "value": h.get("value", 0),
                "size_known": h.get("size_known", True),
                "talking_point": f"Owns {ticker} ({stock.get('name', ticker)}) — {analyst_data['analyst']} "
                                  f"({analyst_data['firm']}) covers both, rated {stock.get('rating')} at "
                                  f"${stock.get('pt', 0):.2f} PT. {bridge_short}",
            })

    prospects.sort(key=lambda p: (-p["relevance"], -p["shares"]))
    # RIA bucket ranks by position size — the only thing that makes one of these
    # worth a look is how much they actually hold.
    ria_holders.sort(key=lambda p: -p["shares"])
    return {"qualifying_stocks": qualifying, "prospects": prospects,
            "ria_holders": ria_holders,
            "not_fetched_tickers": not_fetched,
            "filtered_passive": filtered_passive, "filtered_breadth": filtered_breadth}


# ─────────────────────────────────────────────────────────────────────────
# 2. NOBO cross-reference
# ─────────────────────────────────────────────────────────────────────────
def save_nobo_list(rows, source_label, client_id=None):
    """rows: list of {"holder_name": str, "shares": int}. Replaces whatever
    NOBO list was previously on file — same "upload replaces" behavior as
    app.py (a NOBO file is a full quarterly snapshot from the transfer
    agent, not something to merge/append)."""
    cid = _resolve_client_id(client_id)
    payload = {"rows": rows, "source_label": source_label, "_fetched_at": datetime.now().isoformat()}
    db.save_json(_NOBO_KEY, payload, client_id=cid)
    return payload


def get_nobo_list(client_id=None):
    cid = _resolve_client_id(client_id)
    return db.load_json(_NOBO_KEY, default={"rows": [], "source_label": None, "_fetched_at": None}, client_id=cid)


def match_against_nobo(names, client_id=None):
    """Returns (matched, unmatched). matched: list of
    (compared_name, nobo_holder_name, shares). unmatched: list of names with
    no NOBO match — these are the real, unconfirmed prospects."""
    nobo = get_nobo_list(client_id)
    rows = nobo.get("rows", [])
    matched, unmatched = [], []
    for name in names:
        hit = next((r for r in rows if _name_matches(name, r.get("holder_name", ""))), None)
        if hit:
            matched.append((name, hit["holder_name"], hit.get("shares", 0)))
        else:
            unmatched.append(name)
    return matched, unmatched


# ─────────────────────────────────────────────────────────────────────────
# 3. Bulk-paste table parsing
# ─────────────────────────────────────────────────────────────────────────
def parse_pasted_table(raw_text):
    """Returns (columns, rows) — rows is a list of lists, all padded to the
    same width as the widest row. Pure parsing only; never guesses which
    column is the fund name (that's a UI decision — see investors_page.py)."""
    lines = [ln for ln in raw_text.strip().split("\n") if ln.strip()]
    parsed_rows = []
    for ln in lines:
        if "\t" in ln:
            cells = ln.split("\t")
        else:
            import re
            cells = re.split(r"\s{2,}", ln.strip())
        cells = [c.strip() for c in cells if c.strip() != ""]
        if cells:
            parsed_rows.append(cells)
    if not parsed_rows:
        return [], []
    max_cols = max(len(r) for r in parsed_rows)
    padded = [r + [""] * (max_cols - len(r)) for r in parsed_rows]
    columns = [f"Column {i + 1}" for i in range(max_cols)]
    return columns, padded
