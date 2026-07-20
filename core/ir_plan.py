"""
core/ir_plan.py — composes a live, forward-looking 90-day IR action plan from
data the platform already holds: the earnings-cycle dates (config), the NDR
schedule (ndr_trips), the named catalysts (guidance policy), ownership signals
(NOBO flow + threshold), consensus/valuation, and the positioning thesis.

Pure composition, no UI — reports_page renders it and report_pdf exports it. The
plan is the forward complement to the (current-state) Board IR Report.
"""

from datetime import datetime, timedelta

from config.client_config import CE, CGP, CT


def _date(s):
    if not s:
        return None
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def compose_ir_plan(client_id=None):
    today = datetime.now().date()
    end = today + timedelta(days=90)
    ce = CE()
    quarter = ce.get("current_quarter", "")

    # ── Context snapshot (valuation / financials — best-effort) ──
    ctx = {"ticker": CT("ticker"), "name": CT("name"), "quarter": quarter}
    try:
        from core import benchmarking_engine
        bm = benchmarking_engine.build_benchmark()
        u = bm["usio"]
        ctx.update(ev_gp=u["ev_gp"], discount_gp=bm["discount_gp"], rev_growth=u["rev_growth"],
                   median_gp=bm["median_gp"])
    except Exception:
        pass
    try:
        from core import edgar_financials
        fs = edgar_financials.financial_summary(CT("ticker"))
        if fs and not fs.get("_error"):
            ctx["op_margin"] = fs["income"].get("operating_margin")
    except Exception:
        pass
    try:
        from core import risk_scorecard, market_data
        pt = risk_scorecard._consensus_pt_avg()
        snap = market_data.get_snapshot(CT("ticker"))
        price = snap.get("last_price") if snap else None
        ctx["consensus_pt"] = pt
        ctx["price"] = price
        ctx["upside"] = ((pt / price - 1) * 100) if (pt and price) else None
    except Exception:
        pass

    # ── Timeline: earnings cycle + roadshows within the window ──
    timeline = []
    qs, qe, earn = _date(ce.get("quiet_start")), _date(ce.get("quiet_end")), _date(ce.get("earnings_date"))
    if qs:
        timeline.append((qs, "Quiet period begins", "No MNPI — complete analyst outreach before this date."))
    if earn:
        timeline.append((earn, f"{quarter} earnings call", f"{ce.get('call_time','')}".strip() or "Earnings release & call."))
    if qe:
        timeline.append((qe, "Quiet period ends", "Resume active outreach; begin post-call NDRs."))
    try:
        from core import db
        for t in db.load_json("ndr_trips.json", []):
            d = _date(t.get("dates"))
            if d:
                n = len([m for m in t.get("meetings", []) if m.get("type") != "break"])
                timeline.append((d, f"NDR — {t.get('city','')}", f"{t.get('name','')} · {n} meetings"))
    except Exception:
        pass
    timeline = sorted([(d, lbl, det) for (d, lbl, det) in timeline if d and today <= d <= end])

    # ── Objectives for the quarter ──
    objectives = [
        (f"Deliver the {quarter} print and guidance decision",
         "Finalize the script through legal sign-off; make and communicate the guidance call cleanly."),
        ("Reinforce the operating-leverage narrative",
         "The re-rating catalyst is margin. Give the Street a credible bridge from revenue growth to profit."),
        ("Execute the roadshow schedule",
         "Run the booked NDRs, fill open slots from tracked ownership, and convert non-holders."),
        ("Broaden and defend the ownership base",
         "Reinforce accumulators, re-engage trimmers, and keep the retail float widening."),
    ]

    # ── Targeting: booked trips + priority prospects ──
    trips = []
    try:
        from core import db
        for t in db.load_json("ndr_trips.json", []):
            trips.append({"name": t.get("name"), "city": t.get("city"), "dates": t.get("dates", "TBD"),
                          "meetings": len([m for m in t.get("meetings", []) if m.get("type") != "break"])})
    except Exception:
        pass
    prospects = []
    try:
        from config.client_config import get_active_client_id
        # REAL universe, not data/seed/buyside_institutions.py. The seed's invented fund names
        # ("Perkins Investment Management", "Rutabaga Capital") were reaching a client-facing PDF.
        from core import targets as targets_mod
        from core.investor_scoring import score_institutions
        _cid = client_id or get_active_client_id()
        scored = score_institutions(targets_mod.targets_as_institutions(client_id=_cid)
                                    + targets_mod.promoted_prospects(_cid),
                                    "pre_earnings", set(), [])
        nh = sorted([i for i in scored if not i.get("USIO_Holder")],
                    key=lambda i: -(i.get("Engagement_Score") or 0))[:5]
        prospects = [{"fund": i["Fund"], "score": i.get("Engagement_Score"), "metro": i.get("Metro")} for i in nh]
    except Exception:
        pass

    catalysts = CGP().get("known_h2_catalysts", [])

    # ── Positioning: the messages to land ──
    # The first two are qualitative thesis statements and are legitimately static.
    # The third USED to be static too — "the valuation discount is real, not a margin
    # weakness" — which is a claim about a LIVE number frozen into a string. That
    # number has been +37%, then -3% (a PREMIUM), then +9% in a single day of peer-set
    # work. On the day it was a premium this line would have sent the IR team out to
    # tell investors a discount was real. Worse, "not a margin weakness" is contradicted
    # by our own EV/Revenue bridge: the EV/Rev gap IS a margin difference, and any
    # analyst who multiplies EV/GP by gross margin will find that in about a minute.
    positioning = [
        "Frame the margin story — a credible operating-leverage bridge is the single biggest re-rating catalyst.",
        "Balance sheet: the settlement float is customer money held in custody, not corporate leverage — we're net cash.",
    ]
    positioning.append(_valuation_message(ctx))

    # ── Ownership actions (from NOBO flow + threshold) ──
    ownership = []
    try:
        from core import nobo_engine
        from config.client_config import get_active_client_id
        pulls = nobo_engine.get_active_pulls(client_id or get_active_client_id())
        so = pulls["shares_outstanding"]
        if pulls.get("prior"):
            fl = nobo_engine.flow(pulls["current"], pulls["prior"])
            if fl["accumulators"]:
                h, d = fl["accumulators"][0]
                ownership.append(("Reinforce the top accumulator",
                                  f"{h['name']} added {d:,} shares — keep them close ahead of the print."))
            if fl["n_new"]:
                ownership.append(("Keep broadening retail",
                                  f"Retail base grew {fl['n_new']} new holders vs the prior pull — sustain the momentum."))
            if fl["distributors"]:
                h, d = fl["distributors"][0]
                ownership.append(("Re-engage a trimmer",
                                  f"{h['name']} trimmed {abs(d):,} shares — understand why before the call."))
        alerts = nobo_engine.threshold_alerts(pulls["current"], so)
        if alerts:
            a = alerts[0]
            ownership.append(("Watch the 13D/13G builder",
                              f"{a['holder']['name']} at {a['pct']:.1f}% of shares out — {a['level']}."))
    except Exception:
        pass

    return {
        "as_of": today, "window_end": end, "context": ctx,
        "timeline": timeline, "objectives": objectives,
        "trips": trips, "prospects": prospects, "catalysts": catalysts,
        "positioning": positioning, "ownership": ownership,
    }


def _valuation_message(ctx):
    """The valuation line to take into a meeting — derived, never asserted.

    Two things have to be true at once and only one of them is fixed:
      * Benchmark on GROSS PROFIT, not revenue. Always true, because USIO reports
        revenue gross of interchange as a principal (10-K filed 2026-03-18) and
        revenue cancels out of EV/Gross Profit. This half is thesis.
      * Whether there IS a discount. Live, and it changes.
    """
    d, ev_gp, med = ctx.get("discount_gp"), ctx.get("ev_gp"), ctx.get("median_gp")
    base = ("Benchmark us on gross profit, not gross revenue — gross-vs-net revenue treatment "
            "varies across our peer set, so EV/Revenue is not a usable comparison and any "
            "'revenue discount' quoted off it is a margin difference, not a valuation gap. "
            if CT("ticker") != "USIO" else
            "Benchmark us on gross profit, not gross revenue — we report revenue gross of "
            "interchange we never keep, so EV/Revenue is not a usable comparison and any "
            "'revenue discount' quoted off it is a margin difference, not a valuation gap. ")
    if d is None or ev_gp is None:
        return base + "The live EV/Gross Profit comparison could not be sourced — do not quote a discount."
    if d > 0:
        return (base + f"On EV/Gross Profit — the one multiple our peer set's accounting doesn't "
                       f"distort — we trade at {ev_gp:.1f}x vs a {med:.1f}x peer median, a {d:.0f}% "
                       f"discount. That is the number to use, and it is defensible line by line.")
    return (base + f"AND DO NOT CLAIM A DISCOUNT RIGHT NOW: on EV/Gross Profit we trade at "
                   f"{ev_gp:.1f}x vs a {med:.1f}x peer median — a {abs(d):.0f}% PREMIUM. The case "
                   f"has to be made on the margin bridge and growth, not on being cheap.")
