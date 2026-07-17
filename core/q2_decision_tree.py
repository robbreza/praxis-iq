"""Q2 FY26 call: which script to run, decided off the printed gross margin.

WHY A TREE. There are two full scripts (core/q2_script.py for the recovery, core/q2_script_miss.py
for the ~20% miss) and a partial case between them. Choosing among them ON THE DAY, in the hour
between the numbers landing and the call, is exactly when judgment is worst and the pull toward
the flattering revenue headline is strongest. The branch should be chosen BEFORE the print exists,
so that on the day it is a lookup, not a debate.

THE BOUNDARIES ARE ECONOMIC, NOT ROUND NUMBERS. Modelled on management's GUIDED +11% revenue with
Q1 cash SG&A held flat (core/mgmt_model.guidance_case):

    breakeven gross margin (operating income = 0)  =  20.73%

Below that USIO does not clear its own cost base and the GUIDED "profitable and EBITDA positive"
is at risk. That single fact sets the hard line. The branches are drawn around it:

    >= 23%      RECOVERY   promise kept        run q2_script  (lead with the kept promise)
    21.0-22.9%  PARTIAL    above breakeven,    hybrid          (credit the direction, no victory
                           below the promise                    lap, do NOT re-promise the level)
    <= 20.9%    MISS       at/below breakeven, run q2_script_miss (stop making forward claims;
                           2nd commitment at risk               board decides guidance first)

Note where Q1 landed: 20.2% — i.e. BELOW breakeven. So "Q2 simply repeats Q1" is already the MISS
branch, not a neutral outcome. The recovery is the thing that has to happen; flat is the bad case.

ONE RULE SPANS ALL THREE BRANCHES: the float is observed fact (program funded 2026-07-01, call is
~5 weeks into Q3), so it is said on every branch, always as a dated balance and never as the $1B
headline stripped of management's hedges, always to everyone at once (Reg FD). What CHANGES across
branches is only how much forward-looking framing management has earned the right to attach to it —
a lot on recovery, none on a miss.
"""

from datetime import date

from core import mgmt_model

# Economic boundaries, recomputed live so they cannot drift from the model.
_BREAKEVEN_GM = None


def breakeven_gm():
    """Gross margin at which FY2026 operating income = 0, on guided +11% rev, flat cash SG&A."""
    global _BREAKEVEN_GM
    if _BREAKEVEN_GM is None:
        lo, hi = 18.0, 24.0
        for _ in range(50):
            mid = (lo + hi) / 2
            if mgmt_model.guidance_case(11.0, mid, "q1_run_rate")["operating_income"] > 0:
                hi = mid
            else:
                lo = mid
        _BREAKEVEN_GM = round((lo + hi) / 2, 2)
    return _BREAKEVEN_GM


def _at(gm):
    c = mgmt_model.guidance_case(11.0, gm, "q1_run_rate")
    return {"gm": gm, "oi": c["operating_income"], "eps": c["eps"], "ebitda": c["ebitda"],
            "gaap_positive": c["eps"] > 0}


def branches():
    be = breakeven_gm()
    return [
        {
            "key": "recovery", "range": ">= 23.0%", "label": "RECOVERY — promise kept",
            "script": "q2_script (base)", "color": "good",
            "econ": _at(23.0),
            "headline": ("Lead with the gross margin against the 23-25% commitment. First forward "
                         "claim to land in over a year — state it plainly, no victory lap."),
            "float_framing": ("Full: report observed balances AND frame the shape of a full "
                              "program year. Management has earned a little forward latitude by "
                              "keeping the checkable promise."),
            "guidance": "Reaffirm 10-12% and 'profitable/EBITDA positive' — both are comfortably covered.",
        },
        {
            "key": "partial", "range": f"{be:.1f}%-22.9%", "label": "PARTIAL — above breakeven, below promise",
            "script": "hybrid (q2_script spine, miss-case discipline on the recovery claim)",
            "color": "warn",
            "econ": _at(21.9),
            "headline": ("Credit the DIRECTION with measured data (PINless->RTP, 2,000 -> 200,000+ "
                         "transactions), acknowledge the LEVEL is not yet at target, and do NOT "
                         "attach a new date to 23-25%."),
            "float_framing": ("Observed balances as fact. No full-year projection off them yet — "
                              "the margin promise only partly landed, so forward latitude is limited."),
            "guidance": ("GAAP-positive and EBITDA-positive hold above breakeven, so 'profitable/"
                         "EBITDA positive' can stand; be specific that the MARGIN target slipped, "
                         "not the profitability commitment."),
        },
        {
            "key": "miss", "range": f"<= {be:.1f}%", "label": "MISS — at/below breakeven",
            "script": "q2_script_miss", "color": "bad",
            "econ": _at(20.2),
            "headline": ("Open on the miss before anything good — 'record' must not precede "
                         "'margin'. STOP making forward claims; 'no timeline on the recovery "
                         "today' is a complete answer."),
            "float_framing": ("Observed balances ONLY, as bare fact — this is now the sole "
                              "unspent asset precisely because it is not a forecast. No shape, "
                              "no full-year framing, no reaching for the $1B headline."),
            "guidance": ("At/below breakeven, operating income is negative and the GUIDED "
                         "'profitable/EBITDA positive' is AT RISK. Reaffirm/qualify/withdraw is "
                         "a BOARD decision taken before the call, never improvised in Q&A."),
        },
    ]


def build():
    be = breakeven_gm()
    return {
        "as_of": date.today().isoformat(),
        "quarter": "Q2 FY2026",
        "breakeven_gm": be,
        "q1_actual_gm": 20.2,
        "q2_ly_comp_gm": 25.8,
        "branches": branches(),
        "read": _read(be),
    }


def recompute(revenue, opex, gross_margin=None, other_income=None, shares=None,
              basis="full-year actual+estimate"):
    """Re-price the whole tree off ACTUAL revenue and opex once the release lands.

    The boundaries in build() are modelled on GUIDED +11% revenue and Q1 run-rate opex — correct
    before the print, stale after it. This replaces both with real figures. It is the operation
    to run the moment the Q2 (or any) release hits, and it is deliberately a ONE-LINE call so it
    happens on the day instead of becoming a rebuild under time pressure.

    THE BREAK-EVEN IS CLOSED-FORM AND EXACT. Operating income is zero when gross profit equals
    opex, i.e. when gross margin = opex / revenue. No model, no bisection, no assumption survives
    into this number beyond the two inputs themselves:

        breakeven gross margin (%) = opex / revenue x 100

    So a recompute is only as good as the two figures fed in, and both come straight off the
    release. `revenue` and `opex` are FULL-YEAR (actual where reported, estimated for the rest);
    `opex` is total operating expense on the same definition build() uses (cash SG&A + SBC + D&A).

    WHAT MOVES AND WHAT DOES NOT. The 23% "recovery" line is management's STATED promise and does
    not move with cost structure — it is their words, not our arithmetic. What moves is the
    break-even line that separates PARTIAL from MISS. If opex rises or revenue disappoints,
    break-even climbs toward 23% and the partial band narrows; if break-even crosses 23% there is
    no partial band left at all, and any margin below the promise is at-or-below break-even — a
    signal in itself, surfaced as `partial_band_collapsed`.
    """
    if not revenue or revenue <= 0:
        return {"status": "no_revenue", "detail": "Revenue must be positive to recompute."}
    be = opex / revenue * 100.0

    def econ(gm):
        return mgmt_model.scenario_from_actuals(revenue, opex, gm, other_income, shares)

    promise_floor = 23.0
    collapsed = be >= promise_floor
    out = {
        "status": "ok", "basis": basis,
        "revenue": revenue, "opex": opex, "implied_opex_pct": opex / revenue * 100,
        "breakeven_gm": round(be, 2), "promise_floor": promise_floor,
        "partial_band_collapsed": collapsed,
        "vs_modelled_breakeven": round(be - breakeven_gm(), 2),
        "branches": [
            {"key": "recovery", "range": f">= {promise_floor:.1f}%",
             "label": "RECOVERY — promise kept", "script": "q2_script (base)",
             "econ_at": econ(max(promise_floor, be + 0.1))},
            {"key": "partial",
             "range": (f"{be:.1f}%-{promise_floor:.1f}%" if not collapsed else "— none —"),
             "label": ("PARTIAL — above breakeven, below promise" if not collapsed
                       else "PARTIAL BAND COLLAPSED — breakeven now at/above the promise"),
             "script": "hybrid", "econ_at": (econ((be + promise_floor) / 2) if not collapsed else None)},
            {"key": "miss", "range": f"<= {be:.1f}%", "label": "MISS — at/below breakeven",
             "script": "q2_script_miss", "econ_at": econ(min(be, 20.2))},
        ],
    }
    if gross_margin is not None:
        c = econ(gross_margin)
        branch = ("recovery" if gross_margin >= promise_floor
                  else "miss" if gross_margin <= be else "partial")
        out["printed"] = {
            "gross_margin": gross_margin, "branch": branch,
            "operating_income": c["operating_income"], "eps": c["eps"],
            "gaap_positive": c["eps"] > 0, "ebitda": c["ebitda"],
            "clears_cost_base": c["operating_income"] > 0,
        }
    out["read"] = _recompute_read(out)
    return out


def _recompute_read(o):
    if o.get("status") != "ok":
        return o.get("detail", "")
    be = o["breakeven_gm"]
    drift = o["vs_modelled_breakeven"]
    bits = [
        f"RECOMPUTED OFF ACTUALS. On full-year revenue of ${o['revenue']/1e6:.1f}M and total opex "
        f"of ${o['opex']/1e6:.1f}M ({o['implied_opex_pct']:.1f}% of revenue), the break-even gross "
        f"margin is {be:.2f}% — operating income is zero exactly where gross margin equals opex "
        f"over revenue. That is {abs(drift):.2f}pp {'higher' if drift > 0 else 'lower'} than the "
        f"{breakeven_gm():.2f}% modelled on guidance."]
    if o["partial_band_collapsed"]:
        bits.append(
            f"THE PARTIAL BAND HAS COLLAPSED: break-even ({be:.2f}%) is now at or above the 23% "
            f"promise floor, so there is no 'above breakeven but below target' zone left. Any "
            f"margin under the promise is at-or-below breakeven — the miss script applies to "
            f"everything short of a clean 23%+.")
    else:
        bits.append(
            f"Branches: >=23% recovery; {be:.1f}%-23% partial; <={be:.1f}% miss. The 23% line is "
            f"management's stated promise and does not move with cost structure; only the "
            f"breakeven line separating partial from miss moves with actuals.")
    p = o.get("printed")
    if p:
        bits.append(
            f"AS PRINTED: {p['gross_margin']:.1f}% gross margin puts this in the {p['branch'].upper()} "
            f"branch — operating income {'+' if p['operating_income'] >= 0 else '-'}"
            f"${abs(p['operating_income'])/1e3:.0f}K, EPS {'+' if p['eps'] >= 0 else '-'}"
            f"${abs(p['eps']):.3f}, "
            + ("clears its cost base." if p['clears_cost_base'] else
               "does NOT clear its cost base — the guided 'profitable and EBITDA positive' is at risk."))
    return " ".join(bits)


def _read(be):
    return (
        f"CHOOSE THE BRANCH BEFORE THE PRINT, NOT AFTER. On guided +11% revenue with cash SG&A "
        f"held flat, FY2026 operating income turns positive at a gross margin of {be:.2f}% — that "
        f"is the hard line, because below it USIO does not clear its cost base and the GUIDED "
        f"'profitable and EBITDA positive' is at risk. Three branches around it: >=23% run the "
        f"recovery script and lead with the kept promise; {be:.0f}-23% run the hybrid — credit "
        f"the measured direction, admit the level, re-promise NOTHING; <={be:.0f}% run the miss "
        f"script — open on the miss, stop making forward claims, and treat guidance as a board "
        f"decision. "
        f"NOTE WHERE Q1 LANDED: 20.2%, BELOW breakeven. 'Q2 just repeats Q1' is the MISS branch, "
        f"not a neutral one — recovery is the event that has to happen, flat is already the bad "
        f"case. Last year's Q2 comp was 25.8% (the hardest gross-profit quarter in two years), so "
        f"the YoY optics will be ugly regardless; that is a comp artifact and must not drive the "
        f"branch — only the absolute margin does. "
        f"ACROSS ALL THREE BRANCHES the float is spoken as a dated, observed balance, to everyone "
        f"at once (Reg FD), never as the $1B headline stripped of management's hedges. What "
        f"changes by branch is ONLY how much forward framing management has earned: full on "
        f"recovery, limited on partial, none on a miss."
    )
