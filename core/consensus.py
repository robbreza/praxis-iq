"""
core/consensus.py — the one place that reads and writes sell-side consensus
estimates (per period, per covering firm), guidance, and the "last updated"
date shown next to each analyst on the Markets Consensus Matrix tab.

Two independent things live in this module:

1. Consensus estimates + guidance (get_consensus/update_estimate/
   update_guidance) — a thin persistence layer over the existing
   data.seed.consensus_estimates seed, following the same "seed is the
   day-one default, a real edit becomes a persisted override" pattern used
   everywhere else in this app. Only period_estimates, period_guidance,
   and analyst_dates are made writable.

2. Confirming a routed model email (confirm_model_review) - the queue
   entry itself lives in core/inbox_queue.py (shared across all routed
   email categories). This module only owns the consensus-specific half
   of "model" confirmation: write the numbers into consensus, then tell
   inbox_queue.py the item's done.
"""

from datetime import datetime

from core import activity_log, db
from data.seed.consensus_estimates import get_seed_consensus

_ESTIMATE_FIELDS = ("Rating", "Price Target", "EPS Est", "Revenue Est ($M)", "EBITDA Est ($M)")


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def get_consensus(client_id=None):
    cid = _resolve_client_id(client_id)
    seed = get_seed_consensus(cid)
    seed["period_estimates"] = db.load_json("period_estimates.json", None) or seed.get("period_estimates", {})
    seed["period_guidance"] = db.load_json("period_guidance.json", None) or seed.get("period_guidance", {})
    override_dates = db.load_json("analyst_dates_override.json", {}) or {}
    seed["analyst_dates"] = {**seed.get("analyst_dates", {}), **override_dates}
    return seed


def update_estimate(period, firm, rating=None, price_target=None, eps_est=None,
                     revenue_est=None, ebitda_est=None, source="manual", client_id=None):
    cid = _resolve_client_id(client_id)
    consensus = get_consensus(cid)
    period_estimates = consensus["period_estimates"]
    period_estimates.setdefault(period, {})
    period_estimates[period][firm] = {
        "Rating": rating, "Price Target": price_target, "EPS Est": eps_est,
        "Revenue Est ($M)": revenue_est, "EBITDA Est ($M)": ebitda_est,
    }
    db.save_json("period_estimates.json", period_estimates, client_id=cid)

    dates_override = db.load_json("analyst_dates_override.json", {}, client_id=cid) or {}
    dates_override[firm] = datetime.now().strftime("%b %d %Y")
    db.save_json("analyst_dates_override.json", dates_override, client_id=cid)

    activity_log.log_event("consensus_updated", entity=firm, period=period, source=source)
    return period_estimates[period][firm]


def update_guidance(period, eps_est, revenue_est, ebitda_est, client_id=None):
    cid = _resolve_client_id(client_id)
    consensus = get_consensus(cid)
    period_guidance = consensus["period_guidance"]
    period_guidance[period] = {"EPS Est": eps_est, "Revenue Est ($M)": revenue_est, "EBITDA Est ($M)": ebitda_est}
    db.save_json("period_guidance.json", period_guidance, client_id=cid)
    return period_guidance[period]


def confirm_model_review(item_id, period, firm, rating=None, price_target=None,
                          eps_est=None, revenue_est=None, ebitda_est=None, client_id=None):
    from core import inbox_queue
    cid = _resolve_client_id(client_id)
    item = inbox_queue.get_item(item_id, client_id=cid)
    if item is None or item.get("status") != "pending":
        return False
    update_estimate(period, firm, rating=rating, price_target=price_target, eps_est=eps_est,
                     revenue_est=revenue_est, ebitda_est=ebitda_est,
                     source="email_model_intake", client_id=cid)
    inbox_queue.mark_confirmed(item_id, outcome=f"Consensus updated for {firm}, {period}", client_id=cid)
    return True
