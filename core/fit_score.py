# -*- coding: utf-8 -*-
"""
core/fit_score.py — the transparent, decomposable Fit Score for Target
Database prospects, replacing the old (-relevance, -shares) sort with a
real six-component score: Peer conviction /30 + New-buyer /20 +
Comparability fit /15 + Turnover /15 + Purchasing power /10 +
Contactability /10 = /100, plus a P1-P5 priority tier.

Ported from a separate Claude Project ("IR OS") the client built
independently — specifically its ir_analytics.py (scoring formula + tiers),
position_econ.py (quarter-over-quarter add/trim/exit classification, now
folded into core.sec_filings.get_cached_13f_holders_with_trend), and
score_tuning.py (the re-weighting-from-outcomes algorithm below). Reviewed
against the actual source (not just its own README) on 2026-07-12 — see
that review for what carried over vs. what got re-architected:

  - Conviction/Fit/tier logic ported close to verbatim — it's clean,
    deterministic, and already well-designed.
  - Purchasing power is a REAL computed number here (each filer's whole
    13F book total, from core.sec_filings.get_cached_book_total), not a
    hand-typed guess — the source's own PP classification was a manual
    H/M/L judgment call. We get this for free from the same bulk-dataset
    pass that builds the holder list, at zero extra network cost.
  - Turnover style and contactability ARE still rough automated heuristics
    (classify_turnover / classify_contactability below), not measured
    data — true trade-level turnover needs a paid vendor (Capital IQ /
    Daloopa / bigdata.com — installed but not yet authorized). Per the
    client's explicit call: ship the heuristic now, log real outcomes via
    suggest_reweight() once meetings start happening, refine from there.
  - "Weight-sum that maps to full conviction" (MAXWS in the source) was a
    hand-tuned per-client constant. Here it's computed from the peer
    universe's own configured weights (top-2 peers by weight), so it
    doesn't need re-tuning by hand for a different client or peer set.

Same "seed is default, edit persists as override" pattern as
core/consensus.py: get_weights() returns a db override if one exists,
otherwise DEFAULT_WEIGHTS. Every component is always returned in its own
field — score_prospect() never collapses to just a bare number — so the
composite is never a black box, matching the source's explicit design
intent.
"""

from core import db, sec_filings

_WEIGHTS_KEY = "fit_score_weights.json"
DEFAULT_WEIGHTS = dict(conviction=30, newbuyer=20, fit=15, turnover=15, pp=10, contact=10)

TIER_LABELS = {
    "P1": "P1 — New-to-core buyer",
    "P2": "P2 — High conviction",
    "P3": "P3 — Core holder",
    "P4": "P4 — Adjacent (large-cap only)",
}

_CLASS_RANK = {"H": 0, "M": 1, "L": 2, "V": 0, "P": 1, "N": 2}


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


# ─────────────────────────────────────────────────────────────────────────
# Weights — persisted, editable (not "hand-edit the .py file" like the source)
# ─────────────────────────────────────────────────────────────────────────
def get_weights(client_id=None):
    cid = _resolve_client_id(client_id)
    override = db.load_json(_WEIGHTS_KEY, None, client_id=cid)
    return override if override is not None else dict(DEFAULT_WEIGHTS)


def save_weights(weights, client_id=None):
    cid = _resolve_client_id(client_id)
    db.save_json(_WEIGHTS_KEY, dict(weights), client_id=cid)


# ─────────────────────────────────────────────────────────────────────────
# Peer config — reads the SAME "peer_universe.csv" db key the Manage Peer
# Universe UI (page_modules_nicegui/investors_page.py) reads/writes. Not a
# page-module import (core/ modules don't import page_modules_nicegui/ —
# see core/prospecting.py's docstring for why); just the same underlying
# db key both sides already treat as the source of truth.
# ─────────────────────────────────────────────────────────────────────────
_DEFAULT_PEER_ENTRY = {"weight": 1.0, "tier": "close"}


def load_peer_config(client_id=None):
    """{ticker: {"weight": float, "tier": "core"|"close"|"large"}}. A
    ticker that isn't in the peer universe at all (e.g. an Analyst
    Coverage Network ticker like WYY that lives in that list instead)
    gets a neutral default rather than a KeyError."""
    cid = _resolve_client_id(client_id)
    records = db.load_json("peer_universe.csv", default=None, client_id=cid)
    cfg = {}
    if records:
        for r in records:
            tkr = (r.get("ticker") or "").upper()
            if not tkr:
                continue
            cfg[tkr] = {
                "weight": float(r.get("weight", 1.0) or 1.0),
                "tier": r.get("tier") or "close",
            }
    return cfg


def _peer_entry(ticker, peer_config):
    return peer_config.get(ticker.upper(), _DEFAULT_PEER_ENTRY)


# ─────────────────────────────────────────────────────────────────────────
# Rough automated heuristics — turnover / purchasing power / contactability
# ─────────────────────────────────────────────────────────────────────────
_PASSIVE_GIANTS = (
    "VANGUARD", "BLACKROCK", "STATE STREET", "GEODE CAPITAL", "NORTHERN TRUST",
    "CHARLES SCHWAB", "SCHWAB", "FIDELITY", "DIMENSIONAL FUND ADVISORS",
    "SSGA", "NUVEEN", "INVESCO",
)
_HIGH_TURNOVER_KEYWORDS = (
    "HEDGE", "OPPORTUNITY", "OPPORTUNITIES", "SPECIAL SITUATIONS",
    "EVENT-DRIVEN", "EVENT DRIVEN", "ACTIVIST", "ARBITRAGE", "ARB",
    "MULTI-STRAT", "DISTRESSED", "LONG/SHORT", "L/S EQUITY",
)
_LOW_TURNOVER_KEYWORDS = (
    "TRUST CO", "RETIREMENT SYSTEM", "PENSION", "ENDOWMENT", "FOUNDATION",
    "WEALTH MANAGEMENT", "WEALTH ADVISORS", "WEALTH PARTNERS", "INDEX", " ETF",
)


def classify_turnover(fund_name):
    """Rough automated heuristic — real trade-level turnover needs a paid
    vendor (not yet authorized). Keyword/name-pattern matching against the
    SEC-registered manager name, deliberately simple and over-inclusive
    rather than precise. Checks the existing tracked Buy-Side Intelligence
    roster's own hand-set Turnover_Style first (real IR judgment beats a
    keyword guess whenever it's already on file), then falls back to the
    keyword heuristic. Returns (class, why) — H/M/L."""
    from data.seed.buyside_institutions import get_seed_buyside_institutions
    needle = (fund_name or "").strip().upper()
    if not needle:
        return "M", "no fund name to classify"

    for inst in get_seed_buyside_institutions(_resolve_client_id(None)):
        if inst.get("Fund", "").strip().upper() == needle and inst.get("Turnover_Style"):
            style = inst["Turnover_Style"]
            cls = "L" if style.startswith("Low") else "H" if style.startswith("High") else "M"
            return cls, f"already-tracked institution — {style}"

    if any(g in needle for g in _PASSIVE_GIANTS):
        return "L", "known index/passive manager — rarely initiates off IR outreach"
    if any(k in needle for k in _HIGH_TURNOVER_KEYWORDS):
        return "H", "name pattern suggests opportunistic/HF/activist style — initiates fast, less sticky"
    if any(k in needle for k in _LOW_TURNOVER_KEYWORDS):
        return "L", "name pattern suggests long-duration holder — slow to enter, sticky once in"
    return "M", "no strong pattern match — assumed active growth/core style"


_PP_HIGH_THRESHOLD = 1_000_000_000  # $1B+ whole-book 13F value
_PP_MED_THRESHOLD = 100_000_000     # $100M+


def classify_purchasing_power(book_total):
    """book_total: this filer's whole 13F portfolio value for the quarter
    (core.sec_filings.get_cached_book_total) — a REAL computed number, not
    a guess, summed from the same bulk dataset every tracked-ticker holder
    already came from. None only if no 13F refresh has computed book
    totals yet, or this filer wasn't in that quarter's dataset — falls
    back to a neutral 'M' rather than overclaiming precision from
    nothing. Returns (class, why) — H/M/L."""
    if book_total is None:
        return "M", "no 13F book total on file yet — refresh 13F holders to compute this"
    if book_total >= _PP_HIGH_THRESHOLD:
        return "H", f"${book_total / 1e9:.1f}B 13F book — meaningful ticket size"
    if book_total >= _PP_MED_THRESHOLD:
        return "M", f"${book_total / 1e6:.0f}M 13F book — solid ticket size"
    return "L", f"${book_total / 1e6:.1f}M 13F book — small ticket, concentrated"


def classify_contactability(fund_name, client_id=None):
    """No dedicated contacts directory exists in this codebase yet. Rough
    heuristic: 'V' if this fund is already one of the actively covered
    institutions (Coverage_Priority 1 or 2 in the Buy-Side Intelligence
    roster) — a real relationship almost certainly means a real contact
    path already exists. 'P' (pattern-inferred) otherwise, since a named
    institutional manager's IR/investor-relations line is virtually
    always findable even without a stored record. 'N' is reserved for no
    usable fund identity at all. Returns (class, why) — V/P/N."""
    from data.seed.buyside_institutions import get_seed_buyside_institutions
    needle = (fund_name or "").strip().upper()
    if not needle:
        return "N", "no fund name to work with"
    cid = _resolve_client_id(client_id)
    for inst in get_seed_buyside_institutions(cid):
        if inst.get("Fund", "").strip().upper() == needle and inst.get("Coverage_Priority") in (1, 2):
            return "V", f"already an actively covered institution (Coverage Priority {inst['Coverage_Priority']})"
    return "P", "not yet in the tracked roster — IR/investor-relations contact is inferable but unverified"


def _tier_points(cls, max_pts, fractions):
    rank = _CLASS_RANK.get(cls, 1)
    return round(max_pts * fractions[rank])


# ─────────────────────────────────────────────────────────────────────────
# Conviction / Fit / Tier — ported close to verbatim from ir_analytics.py
# ─────────────────────────────────────────────────────────────────────────
def conviction_pts(peers_held, peer_config, weights):
    """Weighted sum of each held peer's configured 'weight', scaled
    against the two most heavily-weighted peers in the whole universe
    (holding your top ~2 core comps ≈ full conviction points), plus a
    flat +5 bonus for holding at least one 'core' (closest-size direct
    comp) peer. Returns (points, weighted_sum, has_core_peer)."""
    ws = sum(_peer_entry(t, peer_config)["weight"] for t in peers_held)
    has_core = any(_peer_entry(t, peer_config)["tier"] == "core" for t in peers_held)
    all_weights = sorted((v["weight"] for v in peer_config.values()), reverse=True)
    maxws = sum(all_weights[:2]) if len(all_weights) >= 2 else (all_weights[0] * 2 if all_weights else 2.0)
    core_bonus = min(5, weights["conviction"])
    scaled_max = weights["conviction"] - core_bonus
    pts = min(weights["conviction"], round(ws / maxws * scaled_max) + (core_bonus if has_core else 0))
    return pts, ws, has_core


def fit_pts(peers_held, peer_config, weights):
    """Full Fit points if this institution holds ANY 'core' peer,
    two-thirds if it holds a 'close' peer but no core, one-third if it
    only holds 'large' (mega-cap, weak-signal) peers."""
    tiers = {_peer_entry(t, peer_config)["tier"] for t in peers_held}
    if "core" in tiers:
        return weights["fit"]
    if "close" in tiers:
        return round(weights["fit"] * 0.66)
    return round(weights["fit"] * 0.33)


def tier(peers_held, peer_config, newbuyer, weighted_sum):
    """P1 new-to-core buyer > P2 high conviction (2+ peers incl. a core,
    or weighted-sum >= 3.0) > P3 core/close holder > P4 large-cap-only
    (weakest signal). Note: the source's own final branch had an
    unreachable P5 case (by the time you'd fall into it, a 'close' peer
    overlap is already guaranteed by the P4 check above it) — collapsed
    to P4-vs-P3 here rather than reproducing dead code."""
    tier_set = {_peer_entry(t, peer_config)["tier"] for t in peers_held}
    has_core = "core" in tier_set
    has_close_or_core = bool(tier_set & {"core", "close"})
    n_core = sum(1 for t in peers_held if _peer_entry(t, peer_config)["tier"] == "core")

    if newbuyer and has_core:
        return "P1"
    if weighted_sum >= 3.0 or (n_core >= 1 and len(peers_held) >= 2):
        return "P2"
    if has_core or has_close_or_core:
        return "P3"
    return "P4"


# ─────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────
def score_prospect(peers_held, newbuyer, fund_name, book_total=None, client_id=None,
                    weights=None, peer_config=None):
    """Score one prospect institution end to end. peers_held: list of
    tracked-universe tickers this fund holds (from
    core.sec_filings.live_peer_overlap_map — the caller's job, not this
    function's, to keep this pure/testable). newbuyer: True if any held
    ticker shows trend=='NEW' in get_cached_13f_holders_with_trend.
    book_total: this filer's whole 13F book value, or None.

    weights/peer_config: pass these in when scoring many prospects in one
    call (see score_all_holders) so each one is loaded ONCE up front
    instead of once per prospect — get_weights()/load_peer_config() are
    each a db.load_json() round-trip, and score_all_holders can call this
    100+ times in a single click. Left as None for any other/standalone
    caller, which loads them itself exactly as before.

    Returns the full component breakdown plus composite /100 and P1-P4
    tier — never just a bare number, so the score is never a black box."""
    cid = _resolve_client_id(client_id)
    if weights is None:
        weights = get_weights(cid)
    if peer_config is None:
        peer_config = load_peer_config(cid)

    cv, ws, has_core = conviction_pts(peers_held, peer_config, weights)
    nb = weights["newbuyer"] if newbuyer else 0
    ft = fit_pts(peers_held, peer_config, weights)

    t_class, t_why = classify_turnover(fund_name)
    pp_class, pp_why = classify_purchasing_power(book_total)
    cq_class, cq_why = classify_contactability(fund_name, cid)

    tv = _tier_points(t_class, weights["turnover"], (1.0, 0.6, 0.33))
    pp = _tier_points(pp_class, weights["pp"], (1.0, 0.6, 0.3))
    ct = _tier_points(cq_class, weights["contact"], (1.0, 0.6, 0.3))

    composite = cv + nb + ft + tv + pp + ct
    tr = tier(peers_held, peer_config, newbuyer, ws)

    return {
        "fund": fund_name, "composite": composite, "tier": tr,
        "tier_label": TIER_LABELS.get(tr, tr),
        "conviction": cv, "newbuyer_pts": nb, "fit": ft,
        "turnover_pts": tv, "turnover_class": t_class, "turnover_why": t_why,
        "pp_pts": pp, "pp_class": pp_class, "pp_why": pp_why,
        "contact_pts": ct, "contact_class": cq_class, "contact_why": cq_why,
        "weighted_peer_sum": round(ws, 2), "has_core_peer": has_core,
        "peers_held": list(peers_held),
    }


def score_all_holders(peer_tickers, client_id=None, backfill_top_n=40):
    """Convenience wrapper: scores EVERY institution confirmed holding at
    least one tracked peer ticker (live_peer_overlap_map over the union of
    every peer's cached holders), skipping anyone with zero confirmed
    peers. This is what the Peer Cross-Targeting / Automated Prospecting
    Pipeline UI calls to get a ranked, scored prospect list instead of a
    raw holder dump. Returns a list of score_prospect() dicts, sorted by
    composite descending.

    backfill_top_n: after the initial provisional sort (using whatever
    purchasing-power numbers happen to already be cached), fetch real
    whole-13F-book totals for the top N results and re-score just that
    slice — this is the resolution to the "purchasing power" chicken-
    and-egg problem: you can't know which ~40 prospects are worth an
    expensive per-filer network fetch until you've already ranked
    everyone once with neutral/placeholder purchasing power. Bounding
    the backfill to the top N (not every confirmed holder — a large peer
    can have 100+) keeps this fast and predictable instead of reviving
    the old "one big bulk pass over everyone" slowness this whole
    2026-07-12 rewrite was meant to fix (see sec_filings.py module
    history). Pass 0/None to skip the backfill entirely (e.g. a caller
    that only wants the cheap, cache-only provisional ranking)."""
    cid = _resolve_client_id(client_id)
    fund_names = set()
    for t in peer_tickers:
        cached = sec_filings.get_cached_13f_holders(t)
        for h in cached.get("holders", []):
            if h.get("filer"):
                fund_names.add(h["filer"])

    overlap = sec_filings.live_peer_overlap_map(sorted(fund_names), peer_tickers)

    newbuyer_by_ticker = {}
    for t in peer_tickers:
        trended = sec_filings.get_cached_13f_holders_with_trend(t)
        newbuyer_by_ticker[t] = {
            h["filer"] for h in trended.get("holders", []) if h.get("trend") == "NEW"
        }

    # Load book totals, weights, and peer config ONCE (three db round-trips
    # total), not per-fund inside the loop below. A large peer like GDOT or
    # EEFT can have 100+ confirmed holders — calling
    # sec_filings.get_cached_book_total(fund_name), get_weights(), and
    # load_peer_config() per holder means 300+ sequential Neon queries in
    # one synchronous call, which blocks the NiceGUI event loop long enough
    # to trip the browser's websocket ping timeout ("Connection lost" —
    # the real bug behind the 2026-07-11 "Rank by Fit Score" freeze). The
    # book-total dict lookup was the first fix; weights/peer_config passed
    # straight into score_prospect() below is the second and last piece —
    # every db call score_prospect can make is now hoisted out of this loop.
    book_totals = sec_filings.get_all_cached_book_totals()
    weights = get_weights(cid)
    peer_config = load_peer_config(cid)

    results = []
    for fund_name, info in overlap.items():
        peers_held = info.get("confirmed", [])
        if not peers_held:
            continue
        newbuyer = any(fund_name in newbuyer_by_ticker.get(t, set()) for t in peers_held)
        book_total = book_totals.get(fund_name)
        results.append(score_prospect(peers_held, newbuyer, fund_name, book_total, cid,
                                       weights=weights, peer_config=peer_config))

    results.sort(key=lambda r: -r["composite"])

    if backfill_top_n:
        top_slice = results[:backfill_top_n]
        top_fund_names = {r["fund"] for r in top_slice}
        filer_refs = sec_filings.get_cached_filer_refs(peer_tickers)
        refs_to_backfill = [ref for name, ref in filer_refs.items() if name in top_fund_names]
        if refs_to_backfill:
            quarter_label = refs_to_backfill[0]["quarter"]
            # Network calls happen here — one lightweight request per
            # not-yet-cached filer in refs_to_backfill, never more than
            # backfill_top_n of them. This is the only place in the whole
            # Fit Score pipeline that can hit the network; every caller
            # (investors_page.py) must run score_all_holders off the
            # event loop (asyncio.to_thread) for exactly this reason.
            sec_filings.ensure_book_totals(refs_to_backfill, quarter_label)
            new_totals = sec_filings.get_all_cached_book_totals()
            rescored_any = False
            for i, r in enumerate(top_slice):
                fund_name = r["fund"]
                new_total = new_totals.get(fund_name)
                if new_total is not None and new_total != book_totals.get(fund_name):
                    newbuyer = any(fund_name in newbuyer_by_ticker.get(t, set()) for t in r["peers_held"])
                    top_slice[i] = score_prospect(r["peers_held"], newbuyer, fund_name, new_total, cid,
                                                   weights=weights, peer_config=peer_config)
                    rescored_any = True
            if rescored_any:
                # Real purchasing-power numbers can move a prospect up or
                # down relative to others in the same top slice (a fund
                # that looked like a mid-tier "M" placeholder might turn
                # out to run a $50B book) — re-sort just this slice rather
                # than assuming the provisional order still holds.
                results = top_slice + results[backfill_top_n:]
                results.sort(key=lambda r: -r["composite"])

    return results


# ─────────────────────────────────────────────────────────────────────────
# Score learning — ported from score_tuning.py's lift-based re-weighting
# ─────────────────────────────────────────────────────────────────────────
_COMPONENT_KEYS = [
    ("conviction", "Peer conviction"), ("newbuyer_pts", "New-buyer"),
    ("fit", "Comparability fit"), ("turnover_pts", "Turnover"),
    ("pp_pts", "Purchasing power"), ("contact_pts", "Contactability"),
]
_WEIGHT_KEY_FOR = {
    "conviction": "conviction", "newbuyer_pts": "newbuyer", "fit": "fit",
    "turnover_pts": "turnover", "pp_pts": "pp", "contact_pts": "contact",
}
MIN_LABELED = 12


def analyze_lift(labeled_rows):
    """labeled_rows: list of {**score_prospect() component fields,
    "_outcome": 1|0} — 1 = positive (meeting set / met / became a holder),
    0 = negative (passed). Pure function, no I/O — same algorithm as
    score_tuning.py's analyze(): for each component, compares its mean
    among positive vs negative outcomes ("lift"). Suggested weight =
    70% current + 30% lift-share of the total, renormalized so the
    composite still sums to the same total (stays transparent, never
    silently changes the /100 scale)."""
    pos = [r for r in labeled_rows if r["_outcome"] == 1]
    neg = [r for r in labeled_rows if r["_outcome"] == 0]
    weights = get_weights(None)

    out = []
    for key, label in _COMPONENT_KEYS:
        cur = weights[_WEIGHT_KEY_FOR[key]]
        mp = sum(r.get(key, 0) for r in pos) / len(pos) if pos else 0
        mn = sum(r.get(key, 0) for r in neg) / len(neg) if neg else 0
        lift = mp - mn
        out.append(dict(weight_key=_WEIGHT_KEY_FOR[key], label=label, cur=cur,
                         mean_pos=round(mp, 1), mean_neg=round(mn, 1), lift=round(lift, 1)))

    total = sum(o["cur"] for o in out) or 1
    lifts = [max(0.0, o["lift"]) for o in out]
    lift_sum = sum(lifts) or 1
    for o, lf in zip(out, lifts):
        lift_weighted = lf / lift_sum * total
        o["suggested"] = round(0.7 * o["cur"] + 0.3 * lift_weighted, 1)
    suggested_total = sum(o["suggested"] for o in out) or 1
    for o in out:
        o["suggested"] = round(o["suggested"] / suggested_total * total, 1)
        o["move"] = round(o["suggested"] - o["cur"], 1)
    return out, len(pos), len(neg)


def suggest_reweight(client_id=None):
    """Reads this client's labeled prospect outcomes (prospects.json
    entries with a stored 'score_breakdown' dict and an 'outcome' status —
    see page_modules_nicegui/investors_page.py's Target Database for
    where 'outcome' gets set) and proposes re-weighted components.
    Below MIN_LABELED resolved outcomes, returns mode='insufficient' with
    an empty result — no synthetic/illustrative sample here, since
    showing plausible-looking fake numbers this early risks getting
    mistaken for a real recommendation. Apply by calling save_weights()
    with the suggested values once you're satisfied — nothing here
    changes live weights automatically."""
    cid = _resolve_client_id(client_id)
    prospects = db.load_json("prospects.json", default=[], client_id=cid)
    labeled = []
    for p in prospects:
        outcome = p.get("outcome")
        score = p.get("score_breakdown")
        if not score or outcome not in ("positive", "negative"):
            continue
        row = dict(score)
        row["_outcome"] = 1 if outcome == "positive" else 0
        labeled.append(row)

    if len(labeled) < MIN_LABELED:
        return {"mode": "insufficient", "components": [], "n_pos": 0, "n_neg": 0,
                "message": f"Only {len(labeled)} resolved outcomes on file — need at least "
                           f"{MIN_LABELED} (prospects marked won or passed) before a re-weight "
                           f"suggestion is trustworthy. Log meeting outcomes as they happen; "
                           f"this re-checks itself every time you open this panel."}

    components, n_pos, n_neg = analyze_lift(labeled)
    return {"mode": "live", "components": components, "n_pos": n_pos, "n_neg": n_neg, "message": None}
