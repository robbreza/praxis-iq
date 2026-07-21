"""
core/narrative_engine.py — the single source of truth for the Narrative
Momentum read: "what tomorrow might bring based on the narrative you wrote."

Pure compute, no UI. Same engine pattern as core/guidance_engine.py — page
modules render, this computes. The primary consumer is the Script Generation
"Tomorrow's Setup" panel (earnings_page), the forward bookend to Prior-Quarter
Review; Markets renders a lighter glance of the same numbers. Both read from
this one function so the two surfaces can never drift apart (the same reason
the guidance math was consolidated into guidance_engine).

Inputs are all real: analyst PT direction (active covering firms only), the
named H2 catalysts from guidance_policy, the guidance stance (the saved
decision if one's been made, else the engine's own recommendation), and
whether the stock has paid for the narrative yet (consensus PT vs price).
"""

from config.client_config import CA, CGP, CT
from core import db, guidance_engine, market_data, risk_scorecard

# Saved-decision action -> (label, score). Score feeds the momentum sum.
_STANCE_MAP = {
    "raise_mid": ("Raised", 2), "raise_low": ("Raised (low end)", 2),
    "narrow": ("Narrowed", 1), "reiterate": ("Reiterated", 1),
}
# Engine recommendation (no decision made yet) -> (label, score).
_REC_MAP = {
    "RAISE_MID": ("Raise midpoint (recommended)", 2),
    "RAISE_LOW": ("Raise low end (recommended)", 2),
    "REITERATE": ("Reiterate (recommended)", 1),
    "REITERATE_CAUTIOUS": ("Reiterate — cautious (recommended)", 1),
}


def narrative_read(seed):
    """Synthesize the narrative-momentum signal from real data. Returns a
    dict the page modules render (signal/color/thesis + the supporting
    metrics), never partially-built UI."""
    # Analyst PT direction — first vs latest PT, ACTIVE covering firms only.
    # PT momentum is only meaningful for analysts whose current target we actually track
    # (`pt` on file). The others cover the name too, but we haven't logged their target, so
    # they carry no real trajectory here — including them would count fabricated/absent drift.
    by_firm = seed.get("pt_history", {}).get("by_firm", {})
    pt_firms = {a["firm"] for a in CA() if a.get("pt") is not None}
    raising = flat = cutting = 0
    for firm, pts in by_firm.items():
        if pt_firms and firm not in pt_firms:
            continue
        vals = [p for p in pts if p is not None]
        if len(vals) >= 2:
            chg = vals[-1] - vals[0]
            if chg > 0.05:
                raising += 1
            elif chg < -0.05:
                cutting += 1
            else:
                flat += 1
    net_pt = raising - cutting

    catalysts = CGP().get("known_h2_catalysts", [])
    n_cat = len(catalysts)

    # Guidance stance — the saved decision if one's been made, otherwise the
    # engine's own recommendation, so this read and the guidance surfaces
    # always tell one consistent story rather than drifting apart.
    ss = db.load_json("script_workflow_state.json", {})
    gd = ss.get("guidance_decision", {})
    decided = bool(gd.get("action"))
    if decided:
        stance_label, stance_score = _STANCE_MAP.get(gd["action"], ("Reiterated", 1))
    else:
        try:
            scn = guidance_engine.seasonal_read(ss).get("scenario", "REITERATE")
        except Exception:
            scn = "REITERATE"
        stance_label, stance_score = _REC_MAP.get(scn, ("Reiterate (recommended)", 1))
    stance_verb = "raised" if stance_score >= 2 else "held"

    # Narrative vs price — is the stock reflecting the analyst target yet?
    pt_avg = risk_scorecard._consensus_pt_avg()
    snap = market_data.get_snapshot(CT("ticker"))
    last_price = snap["last_price"] if snap and snap.get("last_price") is not None else CT("last_price", 0)
    upside = ((pt_avg / last_price - 1) * 100) if (pt_avg and last_price) else 0

    momentum = stance_score + net_pt + (1 if n_cat >= 3 else 0)
    rerating = n_cat >= 3 and net_pt >= 0 and upside >= 30 and stance_score >= 1

    if rerating and momentum >= 2:
        signal, color = "RE-RATING SETUP", "#15803D"
        thesis = (f"Guidance {stance_verb} while {n_cat} named H2 catalysts are in play and analyst "
                  f"price targets are net {'higher' if net_pt > 0 else 'stable'} — yet the stock sits {upside:.0f}% "
                  f"below consensus PT. The narrative is running ahead of the price: the market hasn't paid for the "
                  f"story yet. This is the classic re-rating setup to lean into with proactive outreach.")
    elif momentum >= 2:
        signal, color = "POSITIVE", "#1E40AF"
        thesis = (f"Improving narrative — guidance {stance_verb}, {n_cat} catalysts in play, and analyst "
                  f"PTs net {net_pt:+d}. Reinforce the story with the buy-side.")
    elif momentum <= 0:
        signal, color = "CAUTION", "#B45309"
        thesis = (f"Narrative softening — analyst PTs net {net_pt:+d}. Get ahead of the H2 bridge question before "
                  f"the Street asks it.")
    else:
        signal, color = "NEUTRAL", "#475569"
        thesis = (f"Steady narrative — guidance {stance_verb}, {n_cat} catalysts, PTs net {net_pt:+d}. "
                  f"No inflection to press right now.")

    return {
        "raising": raising, "flat": flat, "cutting": cutting, "net_pt": net_pt,
        "catalysts": catalysts, "n_cat": n_cat,
        "stance_label": stance_label, "stance_score": stance_score,
        "stance_verb": stance_verb, "decided": decided,
        "pt_avg": pt_avg, "last_price": last_price, "upside": upside,
        "momentum": momentum, "rerating": rerating,
        "signal": signal, "color": color, "thesis": thesis,
    }
