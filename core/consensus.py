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

import statistics
from datetime import datetime

from core import activity_log, db
from data.seed.consensus_estimates import get_seed_consensus


def _real_pt_history(seed, cid=None):
    """Real PT-drift series, built from the analyst rating-action feed (core.rating_actions —
    sourced from Yahoo, free, no key): each dated price target a covering desk has PUBLISHED, per
    firm, over calendar time. THIS is the genuine PT-snapshot-over-time source — the registry holds
    only each desk's CURRENT PT, while this feed carries the whole trail (HCW $3.50→$4.00, Ladenburg
    $4.50→$5.75→$6.25, ...).

    Returns the same shape the consumers expect: firm series aligned to a shared, chronological date
    axis (None where a firm had no revision on that date), so the first-vs-last drift math in
    risk_scorecard / board_slides / narrative_engine stays correct. Empty (and every consumer falls
    through to its honest "not tracked yet" state) until the feed is backfilled or fewer than two
    distinct revision dates exist."""
    from core import rating_actions
    events = rating_actions.recent(cid) or []
    pts = [(e["firm"], e["date"], e["pt_current"]) for e in events
           if e.get("firm") and e.get("date") and e.get("pt_current")]
    dates = sorted({d for _, d, _ in pts})
    if len(dates) < 2:
        return {"labels": [], "by_firm": {}, "colors": {}, "stock_prices": []}
    firms = []
    for f, _, _ in pts:
        if f not in firms:
            firms.append(f)
    pt_map = {}
    for f, d, p in pts:
        pt_map[(f, d)] = p   # last write wins for the same firm+date
    by_firm = {f: [pt_map.get((f, d)) for d in dates] for f in firms}
    return {"labels": dates, "by_firm": by_firm, "colors": {}, "stock_prices": []}

_ESTIMATE_FIELDS = ("Rating", "Price Target", "EPS Est", "Revenue Est ($M)", "EBITDA Est ($M)")


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def get_consensus(client_id=None):
    cid = _resolve_client_id(client_id)
    seed = get_seed_consensus(cid)
    # Pass client_id explicitly: these overrides are per-tenant, and callers (e.g.
    # rolled_consensus) may request a client that isn't the active one. Without it the
    # db.load_json calls read the ACTIVE client's data — wrong tenant.
    seed["period_estimates"] = db.load_json("period_estimates.json", None, client_id=cid) or seed.get("period_estimates", {})
    seed["period_guidance"] = db.load_json("period_guidance.json", None, client_id=cid) or seed.get("period_guidance", {})
    override_dates = db.load_json("analyst_dates_override.json", {}, client_id=cid) or {}
    seed["analyst_dates"] = {**seed.get("analyst_dates", {}), **override_dates}
    # Replace the seed's fabricated 8-quarter pt_history with the REAL one, built from the analyst
    # rating-action feed (Yahoo). Every downstream consumer reads pt_history through this function,
    # so this one line makes the whole app's PT-drift story real at the source.
    seed["pt_history"] = _real_pt_history(seed, cid)
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


def rolled_consensus(period, client_id=None, metric="Revenue Est ($M)",
                     outlier_pct=0.10, min_models=2, coverage_threshold=0.5,
                     include_street=True):
    """Praxis Consensus: roll up the analyst models we've actually collected into the TRUE
    consensus, with the period-verified street aggregate as a labeled fallback when coverage is
    thin. This is the IR-vetted number — because we've seen each model we can see the dispersion
    a rough analyst creates, which the street's black-box mean hides.

    RULES (see the consensus design decision):
      * Headline = MEDIAN of received models (robust to one rough analyst); mean + range shown too.
      * Coverage = models received / covering (active) analysts. Authoritative when
        n_models >= min_models AND coverage >= coverage_threshold; otherwise provisional.
      * Precedence: (1) model roll-up if authoritative; else (2) period-verified street aggregate
        (provisional); else (3) a manual q2_consensus_rev override; else nothing.
      * Outliers are FLAGGED (any firm > outlier_pct off the median) but KEPT in the math — the
        median already softens their pull.
      * Reconciliation: always report model-median vs street so the IR person can see the street
        drifting and go manage it.

    include_street=False skips the network call (for cheap passive renders); the street fallback
    and reconciliation are then unavailable and precedence falls straight to the override.
    """
    cid = _resolve_client_id(client_id)
    from config.client_config import get_client
    client = get_client(cid)
    estimates = (get_consensus(cid).get("period_estimates", {}) or {}).get(period, {}) or {}

    analysts = client.get("analysts", []) or []
    covering_firms = {a.get("firm") for a in analysts if a.get("covering", True) and a.get("firm")}

    # received models = firms with a numeric value for this metric; restricted to the CURRENTLY
    # COVERING set when we know it (a genuinely lapsed analyst's stale model shouldn't count —
    # but "no PT logged" is NOT a lapse, so all five USIO firms count here).
    received = {}
    for firm, est in estimates.items():
        v = est.get(metric)
        if isinstance(v, (int, float)):
            if not covering_firms or firm in covering_firms:
                received[firm] = float(v)

    values = list(received.values())
    n_models = len(values)
    median = statistics.median(values) if values else None
    mean = statistics.fmean(values) if values else None
    low, high = (min(values), max(values)) if values else (None, None)

    # period-verified street aggregate (network) — only when asked
    street = None
    if include_street:
        try:
            from core import market_data
            from config.client_config import set_active_client_id, get_active_client_id
            _prev = get_active_client_id()
            set_active_client_id(cid)   # consensus_rev resolves ticker/registry from active client
            try:
                street = market_data.consensus_rev(client_id=cid)
            finally:
                set_active_client_id(_prev)
        except Exception:
            street = None
    street_ok = bool(street and (street.get("source") == "registry" or street.get("verified")))
    street_val = street.get("value_m") if street_ok else None
    street_n = street.get("n") if street else None

    n_covering = len(covering_firms) if covering_firms else (street_n or n_models)
    coverage = (n_models / n_covering) if n_covering else 0.0

    # outliers: flag-only (kept in the math)
    per_firm, outliers = [], []
    for firm, v in sorted(received.items(), key=lambda kv: kv[1]):
        is_out = bool(median) and abs(v - median) / median > outlier_pct
        if is_out:
            outliers.append(firm)
        per_firm.append({"firm": firm, "value": v, "is_outlier": is_out})

    override = client.get("q2_consensus_rev")
    override = float(override) if isinstance(override, (int, float)) and override else None

    # Fallback consensus (non-model). consensus_rev() already prefers a curated q2_consensus_rev
    # override over the live feed and labels it source="registry", so relabel by source rather than
    # calling an override "street". Without a network street (include_street=False) fall back to the
    # override directly so the cheap path still has a number.
    fb_val = fb_source = None
    if street_ok:
        fb_val = street_val
        fb_source = "override" if street.get("source") == "registry" else "street"
    elif override is not None:
        fb_val, fb_source = override, "override"

    authoritative = n_models >= min_models and coverage >= coverage_threshold
    if authoritative:
        headline, source, status = median, "models", "authoritative"
    elif fb_val is not None:
        headline, source, status = fb_val, fb_source, "provisional"
    else:
        headline, source, status = None, "none", "provisional"

    reconciliation = None
    if median is not None and fb_val:
        reconciliation = {"model_median": median, "ref": fb_val, "ref_source": fb_source,
                          "ref_vs_model_pct": (fb_val - median) / median * 100}

    return {
        "period": period, "metric": metric,
        "headline": headline, "source": source, "status": status,
        "median": median, "mean": mean, "low": low, "high": high,
        "n_models": n_models, "n_covering": n_covering, "coverage": coverage,
        "per_firm": per_firm, "outliers": outliers,
        "fallback": {"value_m": fb_val, "source": fb_source,
                     "n": street_n if fb_source == "street" else None,
                     "verified": bool(street and street.get("verified") and fb_source == "street")}
        if fb_val is not None else None,
        "override": override, "reconciliation": reconciliation,
    }


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
