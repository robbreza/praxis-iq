"""Comp quality — is the year-ago base the script will be measured against a clean one?

WHY THIS EXISTS. An earnings script that leads with a year-over-year growth rate is making a
claim about the BUSINESS. But a YoY rate is a statement about two quarters, and if the older
one was distorted, the rate describes the distortion rather than the business. Analysts on the
call know the base; they have the model open. Leading with a number the base inflated is the
fastest way to spend credibility you will want later.

THE ASYMMETRY THIS MODULE EXISTS TO CATCH. A quarter can be an EASY comp on one line and a HARD
comp on another, at the same time — and for USIO's upcoming Q2 FY26 it is exactly that:

    Q2 FY25 revenue      $19,960,990   the WEAKEST quarter of FY2025 (-6.5% vs the FY avg)
    Q2 FY25 gross profit  $5,140,069   the STRONGEST gross profit quarter in two years
    Q2 FY25 margin             25.8%   the HIGHEST margin in the series

Both at once, because the revenue that went missing was LOW-margin. The 10-Q names the causes:
"the loss of a meaningful customer in our Payfac business", "attrition in our legacy portfolios",
prepaid program customer losses, and lower interest revenue. Strip out low-margin revenue and
the margin goes UP while the top line goes DOWN.

So the script faces opposite pressures on the two lines it will be asked about:

  * REVENUE — an easy comp. Repeat Q1 FY26's $25.5M and the print is +27.6% YoY. That number is
    substantially the base, not the business: against the FY2025 AVERAGE quarter the same
    dollars are +19.3%, and the two-year stack is +12.6%/yr.
  * GROSS PROFIT — a hard comp, against the best GP quarter in two years. Q1 FY26's gross profit
    was $5,136,883 against Q2 FY25's $5,140,069. Flat revenue-to-gross-profit conversion means
    gross profit growth prints at roughly ZERO on a quarter where revenue prints +27%.

That gap IS the question the call will turn on, and it is better to name it in the script than
to be handed it in Q&A.

THE STRATEGIC POINT UNDERNEATH. Investors forgive slow growth when margins are expanding,
because cost is the lever management actually controls — margin expansion is self-help and it is
credible. They forgive thin margins when growth is fast, because scale is coming. USIO currently
has NEITHER: FY2025 gross profit grew +0.4% while gross margin fell 0.6pp, and Q1 FY26 put up
+15.7% revenue with margin down 21.9% -> 20.2%. Growing the top line by adding low-margin volume
is the one combination that earns no credit from either camp — it consumes working capital and
support cost to buy revenue the multiple does not pay for. A script that leads with revenue
growth in that setup is leading with the weakest available claim.

Everything here is computed from the filings; no vendor figures and no estimates.
"""

import statistics
from datetime import date

from core import sec_filings

_QTR_MIN, _QTR_MAX = 80, 100
_REV_TAGS = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"]
_GP_TAGS = ["GrossProfit"]


def _quarters(cf, tags):
    """{period_end: value} for ~quarterly durations."""
    out = {}
    gaap = cf.get("facts", {}).get("us-gaap", {})
    for t in tags:
        node = gaap.get(t)
        if not node:
            continue
        for unit in node["units"].values():
            for v in unit:
                if not v.get("start") or v.get("form") not in ("10-Q", "10-K"):
                    continue
                d = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
                if _QTR_MIN <= d <= _QTR_MAX:
                    out.setdefault(v["end"], v["val"])
    return out


def _prior_year(ends, target):
    """The period ~365 days before `target`, or None. Never 'the previous item in the list' —
    a missing quarter would silently turn a 2-year change into a 'YoY' rate."""
    td = date.fromisoformat(target)
    for e in ends:
        d = (td - date.fromisoformat(e)).days
        if 350 <= d <= 380:
            return e
    return None


def base_quality(ticker=None, upcoming_end=None):
    """Grade the year-ago base that the NEXT print will be measured against.

    `upcoming_end` is the quarter-end being reported (e.g. '2026-06-30'). Defaults to the
    quarter after the last one filed.
    """
    from config.client_config import CT
    ticker = ticker or CT("ticker")
    try:
        cik = sec_filings.resolve_cik(ticker)
        cf = sec_filings._get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json", timeout=120).json()
    except Exception as exc:
        return {"ticker": ticker, "status": "error", "detail": str(exc)}

    rev = _quarters(cf, _REV_TAGS)
    gp = _quarters(cf, _GP_TAGS)
    if not rev:
        return {"ticker": ticker, "status": "no_quarterly_revenue"}

    ends = sorted(rev, reverse=True)
    latest = ends[0]
    if not upcoming_end:
        # The quarter after the last one filed: same month + ~3 months.
        y, m, _ = (int(x) for x in latest.split("-"))
        m += 3
        if m > 12:
            m -= 12
            y += 1
        import calendar
        upcoming_end = f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"

    base_end = _prior_year(ends, upcoming_end)
    if not base_end:
        return {"ticker": ticker, "status": "no_base_quarter",
                "detail": f"No filed quarter ~1yr before {upcoming_end}."}

    base_rev, base_gp = rev.get(base_end), gp.get(base_end)

    # The FY the base quarter belongs to, for an average-quarter yardstick.
    fy_year = base_end[:4]
    fy_qs = [v for e, v in rev.items() if e[:4] == fy_year]
    fy_avg = statistics.mean(fy_qs) if len(fy_qs) >= 3 else None

    # Where does the base sit in its own year, and in the GP series?
    gp_vals = [(e, v) for e, v in sorted(gp.items()) if v is not None]
    gp_rank = None
    if base_gp is not None and gp_vals:
        recent = [v for e, v in gp_vals if e >= _shift_years(base_end, -2)]
        if recent:
            gp_rank = sorted(recent, reverse=True).index(base_gp) + 1
            gp_n = len(recent)
        else:
            gp_n = None
    else:
        gp_n = None

    out = {
        "ticker": ticker, "status": "ok",
        "upcoming_end": upcoming_end, "base_end": base_end,
        "base_revenue": base_rev, "base_gross_profit": base_gp,
        "base_margin": (base_gp / base_rev * 100) if (base_gp and base_rev) else None,
        "fy_avg_quarter": fy_avg,
        "base_vs_fy_avg_pct": ((base_rev / fy_avg - 1) * 100) if (fy_avg and base_rev) else None,
        "gp_rank_2yr": gp_rank, "gp_n_2yr": gp_n,
        "latest_filed_end": latest,
        "latest_revenue": rev.get(latest), "latest_gross_profit": gp.get(latest),
        "latest_margin": ((gp.get(latest) / rev[latest] * 100)
                          if (gp.get(latest) and rev.get(latest)) else None),
    }

    # If the next quarter merely repeats the last filed one, what prints?
    lr, lg = out["latest_revenue"], out["latest_gross_profit"]
    if lr and base_rev:
        out["repeat_rev_yoy"] = (lr / base_rev - 1) * 100
        if fy_avg:
            out["repeat_rev_vs_fy_avg"] = (lr / fy_avg - 1) * 100
        two_yr = _prior_year(ends, base_end)
        if two_yr and rev.get(two_yr):
            out["two_yr_stack_pct"] = (lr / rev[two_yr] - 1) * 100
            out["two_yr_cagr"] = ((lr / rev[two_yr]) ** 0.5 - 1) * 100
            out["two_yr_base_end"] = two_yr
    if lg and base_gp:
        out["repeat_gp_yoy"] = (lg / base_gp - 1) * 100

    # The verdict: easy on revenue, hard on gross profit, or both/neither.
    rev_easy = bool(out.get("base_vs_fy_avg_pct") is not None and out["base_vs_fy_avg_pct"] <= -3)
    gp_hard = bool(gp_rank == 1 or (gp_rank is not None and gp_n and gp_rank <= max(1, gp_n // 4)))
    out["revenue_comp_easy"] = rev_easy
    out["gp_comp_hard"] = gp_hard
    out["divergent"] = bool(rev_easy and gp_hard)
    out["read"] = _read(out)
    return out


def _shift_years(iso, years):
    y, m, d = (int(x) for x in iso.split("-"))
    return f"{y + years:04d}-{m:02d}-{d:02d}"


def _read(o):
    bits = []
    q = o["base_end"]
    if o.get("revenue_comp_easy"):
        bits.append(
            "THE REVENUE COMP IS EASY. The base for {} is {} — ${:,.0f}, which is {:.1f}% BELOW "
            "the average quarter of its own fiscal year. Repeat the last filed quarter's revenue "
            "and the print is {:+.1f}% YoY.".format(
                o["upcoming_end"], q, o["base_revenue"], abs(o["base_vs_fy_avg_pct"]),
                o.get("repeat_rev_yoy") or 0))
        extras = []
        if o.get("repeat_rev_vs_fy_avg") is not None:
            extras.append("{:+.1f}% against that year's AVERAGE quarter".format(o["repeat_rev_vs_fy_avg"]))
        if o.get("two_yr_cagr") is not None:
            extras.append("{:+.1f}%/yr on a two-year stack".format(o["two_yr_cagr"]))
        if extras:
            bits.append(
                "The same dollars are " + " and ".join(extras) +
                ". Those are the honest framings, and they are the ones the sell-side will "
                "compute for themselves within an hour of the release.")
    if o.get("gp_comp_hard"):
        bits.append(
            "AND THE GROSS PROFIT COMP IS HARD — at the same time, off the same quarter. {} "
            "carried ${:,.0f} of gross profit at a {:.1f}% margin, the strongest in the "
            "two-year series. Both are true because the revenue that went missing was LOW-margin: "
            "strip it out and margin rises while the top line falls.".format(
                q, o["base_gross_profit"], o["base_margin"]))
        if o.get("repeat_gp_yoy") is not None:
            bits.append(
                "Repeat the last filed quarter and gross profit prints {:+.1f}% YoY — on a "
                "quarter where revenue prints {:+.1f}%. A ~{:.0f}pp gap between the two growth "
                "rates is the question the call turns on. Name it in the script; do not get "
                "handed it in Q&A.".format(
                    o["repeat_gp_yoy"], o.get("repeat_rev_yoy") or 0,
                    abs((o.get("repeat_rev_yoy") or 0) - o["repeat_gp_yoy"])))
    if o.get("divergent"):
        bits.append(
            "WHAT TO DO WITH IT. Do not lead with the YoY revenue rate. It is the most flattering "
            "number available and the least defensible one — the base, not the business. Lead with "
            "gross profit dollars and the two-year stack, state the base effect BEFORE anyone asks, "
            "and give the margin trajectory. Investors forgive slow growth when margins expand, "
            "because cost is the lever management controls; they forgive thin margins when growth "
            "is fast. Presenting fast revenue growth on flat gross profit claims neither, and it "
            "invites the one conclusion to avoid: that the growth is bought with low-margin volume "
            "the multiple will not pay for.")
    if not bits:
        bits.append(
            "The base for {} looks unremarkable: ${:,.0f} of revenue, within a normal range of its "
            "own fiscal year. No base effect to pre-empt.".format(o["upcoming_end"], o["base_revenue"]))
    return " ".join(bits)


def build(client_id=None):
    return base_quality()
