"""core/portfolio.py — cross-tenant status roll-up for the Praxis Point Console.

The Console's portfolio home renders one card per client from this module. Everything here
is:
  * client_id-PARAMETERIZED — it summarizes any tenant without changing the session's active
    client (so a staff member sees the whole book from one screen), and
  * CHEAP / CACHED-ONLY — pure reads of already-cached data, never a network fetch. Rendering
    the board must not fan out N live SEC/Yahoo calls.

Note on consensus: we read the curated registry value (get_client(cid)['q2_consensus_rev'])
directly rather than market_data.consensus_rev(), because that function resolves the ticker
from the ACTIVE-client ContextVar (not its client_id arg) and its blank-registry path hits the
network — both wrong for a cross-tenant, cached board. The period-verified live estimate is a
workspace concern, not a status tile.
"""
from datetime import date, datetime, timezone

from config.client_config import CLIENT_REGISTRY, get_client
from core import db, market_data

# A 13F pull older than this (or missing entirely) is flagged on the board.
_STALE_13F_DAYS = 100
# Earnings within this many days is flagged "soon".
_EARNINGS_SOON_DAYS = 14

_SEC_13F_KEY = "sec_13f_holders_{ticker}.json"


def _days_until(date_str):
    try:
        return (date.fromisoformat(str(date_str)[:10]) - date.today()).days
    except Exception:
        return None


def _parse_ts(iso_ts):
    """Parse to an aware UTC datetime. A value with an offset (e.g. Postgres tz-aware fetched_at)
    is converted to UTC; a naive value (SQLite local-naive writes, 13F _fetched_at) is treated as
    local and converted. Comparing the result against datetime.now(timezone.utc) is correct for
    both — the old strip-the-offset approach read Neon's UTC timestamps hours in the future."""
    if not iso_ts:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_ts).strip().replace("Z", "+00:00"))
    except Exception:
        return None
    return dt.astimezone(timezone.utc)


def _age_days(iso_ts):
    ts = _parse_ts(iso_ts)
    return (datetime.now(timezone.utc) - ts).days if ts else None


def _age_minutes(iso_ts):
    ts = _parse_ts(iso_ts)
    return int((datetime.now(timezone.utc) - ts).total_seconds() // 60) if ts else None


def client_status(cid):
    """A cheap, cached status summary for one tenant — the shape a Console card renders.
    Never triggers a network fetch; every field degrades to None/[] when its cache is empty."""
    c = get_client(cid) or {}
    ticker = (c.get("ticker") or cid).upper()

    snap = market_data.get_cached(ticker, client_id=cid) or {}
    last_price = snap.get("last_price")
    pct_change = snap.get("pct_change")
    px_age_min = _age_minutes(snap.get("fetched_at")) if snap else None

    # Praxis Consensus roll-up — cheap: cached models + override, NO network (include_street=False).
    earnings0 = c.get("earnings") or {}
    _cq = (earnings0.get("current_quarter") or "").strip()
    _period = f"{_cq}E" if _cq else "Q2 2026E"
    try:
        from core import consensus as _consensus_mod
        _rc = _consensus_mod.rolled_consensus(_period, client_id=cid, include_street=False)
    except Exception:
        _rc = {}
    consensus = _rc.get("headline")
    consensus_source = _rc.get("source") or "none"   # models | street | override | none
    consensus_status = _rc.get("status")             # authoritative | provisional
    consensus_n_models = _rc.get("n_models")
    consensus_n_covering = _rc.get("n_covering")

    # NOBO: has a real Broadridge pull been uploaded for this tenant? (cheap DB read, no seed)
    try:
        from core import nobo_engine
        _pulls = (nobo_engine.load_pull_store(client_id=cid) or {}).get("pulls") or []
    except Exception:
        _pulls = []
    nobo_uploads = len(_pulls)
    nobo_latest = _pulls[-1].get("record_date") if _pulls else None

    earnings = c.get("earnings") or {}
    edate = earnings.get("earnings_date")
    days_to_earnings = _days_until(edate)

    book = db.load_json(_SEC_13F_KEY.format(ticker=ticker), default=None, client_id=cid) or {}
    holders = book.get("holders") or []
    holder_count = len(holders)
    f13_fetched = book.get("_fetched_at")
    f13_age = _age_days(f13_fetched)

    attention = []
    if days_to_earnings is not None and 0 <= days_to_earnings <= _EARNINGS_SOON_DAYS:
        attention.append("earnings soon")
    if holder_count == 0:
        attention.append("no 13F on file")
    elif f13_age is not None and f13_age > _STALE_13F_DAYS:
        attention.append("13F stale")
    if consensus is None:
        attention.append("no consensus")

    return {
        "cid": cid,
        "name": c.get("name") or cid,
        "ticker": ticker,
        "exchange": c.get("exchange") or "",
        "last_price": last_price,
        "pct_change": pct_change,
        "px_age_min": px_age_min,
        "consensus_rev_m": consensus,
        "consensus_source": consensus_source,
        "consensus_status": consensus_status,
        "consensus_n_models": consensus_n_models,
        "consensus_n_covering": consensus_n_covering,
        "earnings_date": edate,
        "days_to_earnings": days_to_earnings,
        "quarter": earnings.get("current_quarter"),
        "holder_count": holder_count,
        "f13_fetched_at": f13_fetched,
        "f13_age_days": f13_age,
        "nobo_uploads": nobo_uploads,
        "nobo_latest": nobo_latest,
        "attention": attention,
    }


def portfolio_overview():
    """client_status for every registered tenant, in registry order."""
    return [client_status(cid) for cid in CLIENT_REGISTRY]
