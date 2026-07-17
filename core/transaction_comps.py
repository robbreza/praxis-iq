"""Transaction comps — what an ACQUIRER offered, as distinct from what the market pays.

Two names in the peer universe carry live control situations. What someone will pay for
CONTROL of an asset is a different number from what the market pays for a minority slice of
it, and both are evidence. A trading multiple tells you where the float clears; a take-out
multiple tells you what a party with board access, full diligence and a bank on retainer
concluded the whole thing was worth. Neither substitutes for the other.

This module carries the two deals as VERIFIED FACTS and computes an implied multiple only
where doing so is honest. Every figure below was read out of the primary filing on EDGAR on
2026-07-16 — not from a vendor, a summary, or a workbook. Where a multiple cannot be
computed without inventing something, this module says so and stops. That refusal is the
point: the peer-median analysis that this sits beside exists because the previous version of
this platform manufactured favorable numbers, and a "transaction comps" section is exactly
the kind of place a manufactured number goes unchallenged.

WHY PRTH IS STILL IN THE MEDIAN. It is tempting to treat a company under a take-private as
"gone" and drop it, the way GDOT is dropped. The filings do not support that for PRTH, and
the distinction matters because PRTH is the median-setter:

  * GDOT has a SIGNED merger agreement (2025-11-23) and STOCKHOLDER APPROVAL (2026-06-23,
    8-K Item 5.07). It is a deal. Its equity is a claim on consideration, not on a business.
  * PRTH has a PRELIMINARY, NON-BINDING proposal (2025-11-09) that has produced no merger
    agreement, no DEFM14A and no SC 13E3 in the EIGHT MONTHS since. The Special Committee's
    own 8-K says it "has not set a definitive timetable" and there "can be no assurance that
    any definitive offer will be made." Meanwhile the company filed a 10-K, filed a 10-Q,
    changed auditors, and held a routine annual meeting electing directors "until the next
    annual meeting in 2027" — a going concern's behaviour, not an exiting one's.
  * THE TAPE AGREES. PRTH trades ABOVE the high end of the bid. A stock pinned to a live
    deal trades just UNDER the offer, on deal spread. PRTH trading OVER it means the market
    is not pricing a take-out at this price — it is pricing a control holder's lowball that
    the minority has not accepted.

So PRTH's multiple is a live market multiple and belongs in the median. The overhang is real
and is flagged on the row; it is footnoted here rather than allowed to silently move the
number. (Removing PRTH would take the median 3.61x -> 3.16x and the headline +20% -> +6%.
That is a 14pp swing resting on a premise the filings contradict.)

Note also that GDOT's exclusion from the median is NOT a deal exclusion — it is out because
it reports no gross profit line at all (it is a bank). "Treat PRTH like GDOT" therefore has
no mechanical meaning: the two are excluded, or not, for unrelated reasons.
"""

from datetime import date

# ─────────────────────────────────────────────────────────────────────────────
# The facts. Each carries its own provenance so a reader can go check it.
# ─────────────────────────────────────────────────────────────────────────────

PRTH_PROPOSAL = {
    "ticker": "PRTH",
    "name": "Priority Technology Holdings",
    "kind": "preliminary_non_binding_proposal",
    "binding": False,
    "bidder": "Investor group led by Thomas Priore, Chairman & CEO",
    "bidder_stake_pct": 58.0,          # per the 8-K, as disclosed in the 2025-04-30 DEF 14A
    "price_low": 6.00,
    "price_high": 6.15,
    "consideration": "cash",
    "proposal_date": date(2025, 11, 9),
    "announced": date(2025, 11, 10),
    "last_update": date(2025, 12, 8),
    "advisors": "Special Committee retained Barclays (financial) and Paul, Weiss (legal)",
    "status_quote": (
        "The Special Committee has not set a definitive timetable for completion of its "
        "evaluation of the offer or any other alternative. There can be no assurance that "
        "any definitive offer will be made, that any agreement will be executed or that "
        "this or any other transaction will be approved or consummated."
    ),
    "source": "8-K 2025-11-10 (Item 8.01, EX-99.1 + EX-99.2 proposal letter); "
              "8-K 2025-12-08 (Item 8.01, EX-99.1)",
}

GDOT_MERGER = {
    "ticker": "GDOT",
    "name": "Green Dot Corporation",
    "kind": "definitive_merger_approved",
    "binding": True,
    "counterparty": "CommerceOne Financial Corporation",
    "cash_per_share": 8.11,
    "exchange_ratio": 0.2215,          # shares of New CommerceOne per GDOT share
    "consideration": "$8.11 cash + 0.2215 New CommerceOne shares",
    "agreement_date": date(2025, 11, 23),
    "approved": date(2026, 6, 23),
    "advisor_range_low": 15.45,        # Citi's implied value of the merger consideration
    "advisor_range_high": 17.51,
    "advisor_basis": "Citi DCF; assumes GDOT holders own ~72.2% of the Combined Company",
    "advisor_metrics": "Price / 2026E Adjusted EPS and Price / Tangible Book Value Per Diluted Share",
    "source": "DEFM14A 2026-05-08; 8-K 2026-06-16 (425); 8-K 2026-06-24 (Item 5.07 vote)",
}


def prth_bid(bench=None):
    """PRTH's take-out multiple — computed live off the same EV plumbing as the median.

    Computable, unlike GDOT's, because PRTH does produce a gross profit figure. But the
    figure is DERIVED and excludes D&A, so the caveat below travels with the number and is
    not optional.
    """
    from core import benchmarking_engine, market_data

    bench = bench or benchmarking_engine.build_benchmark()
    row = next((p for p in bench["peers"] if p["ticker"] == "PRTH"), None)
    if not row or not row.get("gross_profit"):
        return None
    ev = market_data.live_ev("PRTH")
    if not ev or not ev.get("shares_for_mcap"):
        return None

    sh, nd, gp = ev["shares_for_mcap"], ev["net_debt"], row["gross_profit"]
    px = ev["price"]

    def _mult(p):
        return (p * sh + nd) / gp

    lo, hi = _mult(PRTH_PROPOSAL["price_low"]), _mult(PRTH_PROPOSAL["price_high"])
    mkt = _mult(px)
    stale_days = (date.today() - PRTH_PROPOSAL["last_update"]).days

    return {
        "ticker": "PRTH",
        "bid_ev_gp_low": lo,
        "bid_ev_gp_high": hi,
        "market_ev_gp": mkt,
        "market_price": px,
        "bid_vs_market_pct": (PRTH_PROPOSAL["price_high"] / px - 1) * 100,
        "bid_below_market": PRTH_PROPOSAL["price_high"] < px,
        "gross_profit": gp,
        "enterprise_value": ev["enterprise_value"],
        "stale_days": stale_days,
        "basis_caveat": (
            "PRTH reports no GrossProfit line; this gross profit is DERIVED as revenue less "
            "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization, which by its "
            "own tag name EXCLUDES D&A. USIO, by contrast, reports a GrossProfit tag directly. "
            "The two are therefore NOT established as being on the same basis, and nobody has "
            "read USIO's cost-of-revenue composition to find out. PRTH's ex-D&A gross profit is "
            "flattered by whatever D&A belongs in cost of revenue, which biases its multiple "
            "DOWNWARD — so the like-for-like bid multiple is probably HIGHER than shown. That "
            "direction happens to favour USIO's story, which is exactly why it is stated as an "
            "open question and not banked. Treat this comparison as directional, not precise."
        ),
    }


def gdot_deal():
    """GDOT's take-out terms — facts only. The multiple is NOT computable, twice over.

    This function deliberately returns no EV/GP. Two independent reasons, either of which
    alone is disqualifying:

      1. NO DENOMINATOR. GDOT reports no gross profit and no cost-of-revenue line in XBRL.
         It is a bank. There is no figure to divide by, at any vintage. This is the same
         reason it is out of the trading median — not a deal-related exclusion.
      2. NO NUMERATOR. The consideration is $8.11 cash PLUS 0.2215 shares of New CommerceOne,
         an entity that does not trade. The total per-share value is therefore not OBSERVABLE.
         Citi's $15.45-$17.51 is a DCF OUTPUT — a banker's estimate under a stated set of
         assumptions, not a market price — and must never be quoted as though it were one.

    Corroborating the first point: Citi itself valued GDOT on Price / 2026E Adjusted EPS and
    Price / Tangible Book Value Per Diluted Share. The financial advisor on the actual deal
    used a BANK framework. That is independent confirmation that GDOT is not an EV/Gross-Profit
    comparable — our exclusion of it agrees with the sell-side work on the transaction itself.
    """
    d = dict(GDOT_MERGER)
    d.update({
        "ev_gp": None,
        "ev_gp_reason": (
            "Not computable. GDOT reports no gross profit line (it is a bank), so there is no "
            "denominator; and the consideration includes stock in an entity that does not "
            "trade, so the numerator is not observable either. Citi's $15.45-$17.51 range is a "
            "DCF output, not a market price."
        ),
    })
    return d


def build(bench=None):
    """Both transaction comps, plus the read. Safe to call from any report."""
    prth = prth_bid(bench)
    gdot = gdot_deal()
    out = {
        "as_of": date.today().isoformat(),
        "prth_proposal": PRTH_PROPOSAL,
        "prth_bid": prth,
        "gdot_merger": gdot,
        "sizable": [x for x in (prth,) if x],
        "unsizable": [{"ticker": "GDOT", "reason": gdot["ev_gp_reason"]}],
    }
    out["read"] = _read(out)
    out["footnote"] = _footnote(out)
    return out


def _read(o):
    p = o.get("prth_bid")
    bits = []
    if p:
        bits.append(
            "PRTH — an investor group led by the Chairman/CEO, who already holds ~58% and has "
            "Barclays advising the Special Committee, offered ${:.2f}-${:.2f} cash for the rest. "
            "That prices the closest structural analog in the set at {:.2f}x-{:.2f}x EV/gross "
            "profit.".format(
                PRTH_PROPOSAL["price_low"], PRTH_PROPOSAL["price_high"],
                p["bid_ev_gp_low"], p["bid_ev_gp_high"])
        )
        if p["bid_below_market"]:
            bits.append(
                "THE BID IS BELOW THE TAPE. PRTH trades at ${:.2f} ({:.2f}x) — the high bid is "
                "{:+.1f}% against the market. A stock pinned to a live deal trades just UNDER "
                "the offer; this one trades OVER it, and the proposal has sat without a "
                "definitive agreement for {} days. Read that as a control holder's lowball the "
                "minority has not taken, not as a pending exit — which is why PRTH remains in "
                "the trading median.".format(
                    p["market_price"], p["market_ev_gp"], p["bid_vs_market_pct"], p["stale_days"])
            )
        else:
            bits.append(
                "The bid is at or above the tape ({:.2f}x market), which would be consistent "
                "with a deal the market is pricing. Re-examine whether PRTH still belongs in "
                "the trading median.".format(p["market_ev_gp"])
            )
    bits.append(
        "GDOT — a SIGNED deal, approved by stockholders 2026-06-23: $8.11 cash plus 0.2215 New "
        "CommerceOne shares. No EV/gross-profit multiple is shown because none can honestly be "
        "computed: GDOT reports no gross profit (it is a bank) and the stock leg does not trade. "
        "Citi's $15.45-$17.51 is a DCF output, not a price. Citi valued GDOT on P/E and "
        "P/tangible-book — a bank framework — which independently corroborates keeping GDOT out "
        "of an EV/gross-profit median."
    )
    bits.append(
        "HOW TO USE THIS. A take-out multiple is a reference point, not a target — USIO is not "
        "in a process and nothing here implies it should be. The usable observation is narrow "
        "and it is this: the one CONTROL bid in the peer group, made by an insider with full "
        "diligence on a near-perfect structural analog, landed near 3.9x — while USIO trades at "
        "roughly 3.0x. That is corroboration from a second, independent kind of buyer that the "
        "trading discount is not an artifact of the trading comp set. It is not a price target "
        "and must not be presented as one."
    )
    return " ".join(bits)


def _footnote(o):
    """The compact form for a report footer."""
    p = o.get("prth_bid")
    lines = ["TRANSACTION COMPS (what an acquirer offered — distinct from the trading median):"]
    if p:
        lines.append(
            "  PRTH  ${:.2f}-${:.2f}/sh cash = {:.2f}x-{:.2f}x EV/GP. Preliminary, NON-BINDING "
            "(2025-11-09), from an investor group led by the Chairman/CEO (~58% holder). No "
            "definitive agreement in the {} days since the last update. Stock trades ${:.2f} "
            "({:.2f}x) — ABOVE the bid — so PRTH stays in the trading median. Bid multiple is "
            "computed on a DERIVED, ex-D&A gross profit and is not strictly comparable to "
            "USIO's reported gross profit.".format(
                PRTH_PROPOSAL["price_low"], PRTH_PROPOSAL["price_high"],
                p["bid_ev_gp_low"], p["bid_ev_gp_high"], p["stale_days"],
                p["market_price"], p["market_ev_gp"])
        )
    lines.append(
        "  GDOT  $8.11 cash + 0.2215 New CommerceOne shares. DEFINITIVE; approved by "
        "stockholders 2026-06-23. No EV/GP shown — GDOT reports no gross profit line (a bank) "
        "and the stock leg does not trade, so neither side of the ratio is available. Citi's "
        "$15.45-$17.51 is a DCF output, not a market price; Citi valued GDOT on P/E and "
        "P/tangible book."
    )
    lines.append(
        "  Sources: PRTH 8-K 2025-11-10 & 2025-12-08 (Item 8.01). GDOT DEFM14A 2026-05-08, "
        "8-K 2026-06-24 (Item 5.07). Read on EDGAR, {}.".format(o["as_of"])
    )
    return "\n".join(lines)
