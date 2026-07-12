"""
core/analyst_coverage.py — the registry of sell-side analysts who cover this
client, and the OTHER tickers each of them also covers with an active
rating. This is the "Analyst Coverage Network" that core/prospecting.py's
Automated Prospecting Pipeline mines: an institution that already owns a
stock a covering analyst rates Buy has demonstrated it trusts that analyst's
research and understands the surrounding sector thesis — a warmer prospect
than a cold list.

Ported from app.py's "Analyst Coverage Network Targeting" (Buy-Side
Intelligence tab). Same "seed is the day-one default, a real edit becomes a
persisted override" pattern as core/consensus.py: get_coverage() returns the
db override if one exists, otherwise the seed (data.seed.analyst_coverage).
Coverage entries are hand-authored, not computed — the "bridge" thesis text
and "relevance" score are a judgment call about why a fund owning that OTHER
ticker would plausibly buy this client too, which is exactly the kind of
call an IR team member with sector knowledge should make and edit, not
something this app infers on its own.
"""

from core import db
from data.seed.analyst_coverage import get_seed_analyst_coverage

_COVERAGE_KEY = "analyst_coverage_network.json"


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def get_coverage(client_id=None):
    """Returns {analyst_key: {"analyst":..., "firm":..., "email":..., "coverage": [...]}}."""
    cid = _resolve_client_id(client_id)
    override = db.load_json(_COVERAGE_KEY, None, client_id=cid)
    if override is not None:
        return override
    return get_seed_analyst_coverage(cid)


def add_coverage_stock(analyst_key, ticker, name, pt, rating, sector,
                        relevance=50, bridge="", shared_dna="", client_id=None):
    """Returns False if the analyst_key doesn't exist or the ticker is
    already in that analyst's coverage (no silent duplicate/overwrite —
    caller should surface that to the user)."""
    cid = _resolve_client_id(client_id)
    coverage = get_coverage(cid)
    if analyst_key not in coverage:
        return False
    ticker = ticker.upper().strip()
    if ticker in [s["ticker"] for s in coverage[analyst_key]["coverage"]]:
        return False
    coverage[analyst_key]["coverage"].append({
        "ticker": ticker, "name": name, "pt": pt, "rating": rating, "sector": sector,
        "relevance": max(0, min(100, relevance)), "bridge": bridge, "shared_dna": shared_dna,
    })
    db.save_json(_COVERAGE_KEY, coverage, client_id=cid)
    return True


def remove_coverage_stock(analyst_key, ticker, client_id=None):
    cid = _resolve_client_id(client_id)
    coverage = get_coverage(cid)
    if analyst_key not in coverage:
        return False
    before = len(coverage[analyst_key]["coverage"])
    coverage[analyst_key]["coverage"] = [
        s for s in coverage[analyst_key]["coverage"] if s["ticker"] != ticker.upper().strip()
    ]
    if len(coverage[analyst_key]["coverage"]) == before:
        return False
    db.save_json(_COVERAGE_KEY, coverage, client_id=cid)
    return True
