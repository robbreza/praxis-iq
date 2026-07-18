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
from datetime import date, datetime

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


def _age_days(iso_ts):
    try:
        ts = datetime.fromisoformat(str(iso_ts).replace("Z", "").split("+")[0])
        return (datetime.now() - ts).days
    except Exception:
        return None


def client_status(cid):
    """A cheap, cached status summary for one tenant — the shape a Console card renders.
    Never triggers a network fetch; every field degrades to None/[] when its cache is empty."""
    c = get_client(cid) or {}
    ticker = (c.get("ticker") or cid).upper()

    snap = market_data.get_cached(ticker, client_id=cid) or {}
    last_price = snap.get("last_price")
    pct_change = snap.get("pct_change")

    # curated registry consensus only (see module docstring for why not consensus_rev())
    consensus = c.get("q2_consensus_rev")
    consensus = float(consensus) if isinstance(consensus, (int, float)) and consensus else None

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
        "consensus_rev_m": consensus,
        "earnings_date": edate,
        "days_to_earnings": days_to_earnings,
        "quarter": earnings.get("current_quarter"),
        "holder_count": holder_count,
        "f13_fetched_at": f13_fetched,
        "f13_age_days": f13_age,
        "attention": attention,
    }


def portfolio_overview():
    """client_status for every registered tenant, in registry order."""
    return [client_status(cid) for cid in CLIENT_REGISTRY]
