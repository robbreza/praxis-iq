"""Management's own guidance, extrapolated to EPS — and the float upside they described.

WHAT THIS IS. On the Q1 2026 call (2026-05-13) management gave enough to build a full P&L:
a revenue growth range, a cost line they committed to holding, and a gross margin they said
had bottomed. Nobody had built the bridge. This does — and the answer is a much larger EPS
swing than the peer-multiple work implies, because USIO is at the point in its operating
leverage where small gross profit changes are large percentage earnings changes.

THIS IS NOT OUR FORECAST. It is management's guidance, arithmetic, and the assumptions named
below. Every input is tagged GUIDED (management said the number), TARGET (management said it
but did not guide it), or ASSUMED (we chose it, and it is defensible but it is ours). Anyone
reading the output is entitled to know which parts are Usio's claims and which are ours, so
the tag travels with every line. Where management hedged, the hedge is preserved verbatim
rather than smoothed into a point estimate.

WHAT MANAGEMENT ACTUALLY SAID — Q1 2026 call, verbatim, all of it attributable:

  * REVENUE — reiterated full-year "Double-digit revenue growth, up 10%-12%". Barry Sine
    (Litchfield Hills) read the list back; Hoch: "That's correct."  -> GUIDED
  * CASH SG&A — "Cash SG&A for the rest of the year, roughly flattish." Hoch: "That's
    correct."  -> GUIDED. This is the crux: it is the line that turns gross profit into EPS.
  * PROFITABILITY — "You expect to be profitable and EBITDA positive." Hoch: "That's
    correct."  -> GUIDED
  * PREPAID — "prepaid should return to growth for the full year." Hoch: "That's correct."
    -> GUIDED
  * GROSS MARGIN — Hoch: "I feel that we've hit the bottom on the gross margins this quarter,
    and, you know, we should be able to get back to 23%-25% in the short term."  -> TARGET.
    Note the hedges: "I feel", "should be able to", "in the short term". This is NOT guidance
    and must never be quoted as though it were.

WHY THE GROSS MARGIN CLAIM IS THE WHOLE BALLGAME. Our own analysis found gross margin
compressing (21.9% -> 20.2% in Q1) and an INCREMENTAL gross margin of just 9.5% — i.e. new
revenue was arriving at a fraction of the average margin, which is why revenue grew 15.7%
while gross profit grew 6.8%. Management's answer to exactly that is a MIX argument, and it
is specific rather than hand-waving:

  * "Real-Time Payments has a higher margin than PINless Debit. PINless Debit has higher
    revenue, the margins will increase as we move traffic from PINless to Real-Time Payments."
    RTP went from ~2,000 transactions in January to over 200,000 in the latest month.
  * Output electronic presentment: "the margins on that are almost 100%." Electronic documents
    +41% in Q1.
  * "interest income is a 100% margin" — and it FELL this year, which is part of why margin
    compressed. "We expect our balances to be higher... especially as we bring some of these
    larger card programs on live, that will increase balances."

So the compression we measured and the recovery they project are the same mix story running in
opposite directions. That is a coherent, falsifiable claim — not a deflection — and Q2 is the
test: they said Q1 was the bottom.

THE FLOAT CATALYST. Hoch: "one of them is a school voucher program... We've been told that as
much as $1 billion is gonna be distributed through Usio for two different states." And from the
prepared remarks: "An existing client continues to be on track to launch two state-sponsored
school choice voucher programs that will utilize both Usio card issuing and ACH. We expect
those distributions to exceed $1 billion in re-disbursements."

Scale that against the run rate: prepaid "processed over $80 million in card loads in the first
quarter" — about $320M annualised. $1B of re-disbursements is roughly **3x the entire current
card-load business**.

Float revenue is the highest-quality revenue Usio has: management's own words are that interest
is "100% margin", it requires no incremental cost of services, and with cash SG&A held flat it
drops essentially intact to operating income. It is also the exact antidote to the 9.5%
incremental margin problem — it arrives at ~100% instead.

BUT THE HEDGES ARE LOAD-BEARING, AND THIS MODULE KEEPS THEM. "We've been told", "as much as",
"We're not sure how... If it all goes on cards", "Part of it is gonna go on ACH". None of that
is a contract, a signed volume, or a date, and NONE of the $1B is in the 10-12% guidance. The
float upside is therefore modelled SEPARATELY from the guidance case and never added into a
headline. The two things that decide its value — how much lands on cards, and how long balances
dwell before being spent — were not disclosed, so they are inputs here, not findings.
"""

from datetime import date

# ── FY2025 actuals, from the 10-K (filed 2026-03-18). The baseline everything bridges from.
FY25 = {
    "revenue": 85_393_626,
    "cost_of_services": 65_700_927,
    "gross_profit": 19_692_699,
    "cash_sga": 18_362_187,
    "sbc": 1_743_893,
    "d_and_a": 1_946_224,
    "operating_income": -2_359_605,
    "net_income": -2_512_339,
    "eps_diluted": -0.09,
    "diluted_shares": 26_926_838,
}

# ── Q1 FY26 actuals, from the 10-Q (filed 2026-05-13). The run rate management guides off.
Q1_26 = {
    "revenue": 25_465_774,
    "gross_profit": 5_136_883,
    "gross_margin": 20.2,
    "cash_sga": 4_356_142,
    "sbc": 329_284,
    "d_and_a": 225_745,
    "operating_income": 225_712,
    "interest_income": 91_491,
    "interest_expense": -22_826,
    "other_income": 68_665,
    "federal_tax": 67_084,
    "state_tax": 104_790,
    "diluted_shares": 27_748_037,
    "card_loads": 80_000_000,          # "over $80 million in card loads in the first quarter"
    "float_interest_total": 400_000,   # "$0.4 million in interest earnings"
    "float_interest_in_revenue": 300_000,  # "$0.3 million was recognized as revenue"
}

GUIDANCE = {
    "rev_growth_low": 10.0, "rev_growth_high": 12.0,          # GUIDED
    "gross_margin_low": 23.0, "gross_margin_high": 25.0,      # TARGET, not guidance
    "cash_sga": "roughly flattish for the rest of the year",  # GUIDED
    "source": "Q1 2026 earnings call, 2026-05-13",
}

VOUCHER = {
    "distributions": 1_000_000_000,
    "quote": ("We expect those distributions to exceed $1 billion in re-disbursements "
              "(prepared remarks); \"We've been told that as much as $1 billion is gonna be "
              "distributed through Usio for two different states\" (Hoch, Q&A)"),
    "hedges": ["\"We've been told\"", "\"as much as\"",
               "\"We're not sure how... If it all goes on cards\"",
               "\"Part of it is gonna go on ACH\""],
    "in_guidance": False,
}


def _tax(pretax):
    """USIO's tax is not a single rate, and modelling it as one is wrong in both directions.

    Q1 FY26: $67,084 federal and $104,790 state on $294,377 of pretax income. The state line
    is the Texas franchise tax, which is levied on MARGIN, not income — so it is broadly fixed
    and is owed even in a loss year (FY2025 paid $512,811 of tax ON A LOSS). Treating tax as
    a flat % of pretax would understate it at low pretax and overstate it at high pretax.

    So: federal at Q1's effective rate on pretax, plus the state line annualised as fixed.
    """
    fed_rate = Q1_26["federal_tax"] / 294_377
    state_fixed = Q1_26["state_tax"] * 4
    return max(0.0, pretax) * fed_rate + state_fixed


def scenario_from_actuals(revenue, opex, gross_margin, other_income=None, shares=None):
    """A P&L built from EXPLICIT revenue and opex, not from a growth rate off FY2025.

    This is the release-day path. `guidance_case` projects revenue as FY25 x (1+growth) and opex
    off Q1's run rate — the right inputs BEFORE the print, wrong ones after it. Once the release
    lands, revenue and opex are known, so they go in directly and only the gross margin and the
    below-the-line items carry any assumption.

    `revenue` and `opex` are FULL-YEAR figures: actuals where reported, estimate for the balance
    of the year. `opex` is TOTAL operating expense (cash SG&A + SBC + D&A) — the same line the
    breakeven is defined against. `other_income` and `shares` default to the annualised Q1 basis
    but are overridable, because a share count and an interest line both move once you have H1.
    """
    gp = revenue * gross_margin / 100
    oi = gp - opex
    other = other_income if other_income is not None else (
        (Q1_26["interest_income"] + Q1_26["interest_expense"] + Q1_26["other_income"]) * 4)
    pretax = oi + other
    tax = _tax(pretax)
    ni = pretax - tax
    sh = shares or Q1_26["diluted_shares"]
    return {
        "revenue": revenue, "gross_margin": gross_margin, "gross_profit": gp,
        "opex": opex, "operating_income": oi, "operating_margin": oi / revenue * 100,
        "other_income": other, "pretax": pretax, "tax": tax,
        "net_income": ni, "eps": ni / sh, "diluted_shares": sh,
        "ebitda": oi + Q1_26["d_and_a"] * 4,
    }


def guidance_case(rev_growth, gross_margin, cash_sga_mode="q1_run_rate"):
    """One scenario built strictly from management's numbers plus stated assumptions."""
    rev = FY25["revenue"] * (1 + rev_growth / 100)
    gp = rev * gross_margin / 100

    # "Roughly flattish" is ambiguous by design; model both readings rather than pick one.
    if cash_sga_mode == "q1_run_rate":
        cash_sga = Q1_26["cash_sga"] * 4          # hold Q1's actual flat: $17.4M
    else:
        cash_sga = FY25["cash_sga"]                # hold FY25's level flat: $18.4M
    sbc = Q1_26["sbc"] * 4
    dna = Q1_26["d_and_a"] * 4                     # falling: Output Solutions amortisation done
    opex = cash_sga + sbc + dna

    oi = gp - opex
    other = (Q1_26["interest_income"] + Q1_26["interest_expense"] + Q1_26["other_income"]) * 4
    pretax = oi + other
    tax = _tax(pretax)
    ni = pretax - tax
    sh = Q1_26["diluted_shares"]
    return {
        "rev_growth": rev_growth, "gross_margin": gross_margin,
        "revenue": rev, "gross_profit": gp,
        "gp_growth": (gp / FY25["gross_profit"] - 1) * 100,
        "cash_sga": cash_sga, "cash_sga_mode": cash_sga_mode,
        "sbc": sbc, "d_and_a": dna, "opex": opex,
        "operating_income": oi, "operating_margin": oi / rev * 100,
        "other_income": other, "pretax": pretax, "tax": tax,
        "net_income": ni, "eps": ni / sh, "diluted_shares": sh,
        "ebitda": oi + dna,
        "eps_delta_vs_fy25": ni / sh - FY25["eps_diluted"],
    }


def float_upside(distributions=None, on_card_pct=60.0, dwell_days=30, yield_pct=4.0):
    """The voucher float, modelled explicitly — every driver an input, because none was given.

    THE ARITHMETIC IS TRIVIAL; THE INPUTS ARE THE WHOLE ARGUMENT:

        average float balance = distributions x on_card% x (dwell_days / 365)
        incremental revenue   = balance x yield
        incremental EPS       = revenue x (1 - tax) / shares      [~100% margin, flat SG&A]

    Not one of `on_card_pct`, `dwell_days` or `yield_pct` was disclosed. Management said only
    "as much as $1 billion", "We're not sure how... If it all goes on cards", and "Part of it
    is gonna go on ACH". So this is a SENSITIVITY, not a forecast, and the honest output is a
    grid — a point estimate here would be inventing three numbers and reporting one.

    Why ~100% margin flows to EPS: interest on customer balances is booked into revenue with no
    cost of services against it ("interest income is a 100% margin" — Hoch), and cash SG&A is
    guided flat, so it is not consumed on the way down either.

    Defaults are deliberately middle-of-road, not promotional:
      * on_card_pct 60% — management said part goes to ACH; ACH earns fees, not float.
      * dwell_days 30 — a disbursement program's funds are spent down, not parked. School
        voucher money turns over as families spend it.
      * yield_pct 4.0 — short-term rates. USIO's own realised yield looks lower (see
        `implied_current_yield`), so this is charitable and is flagged as such.
    """
    dist = distributions or VOUCHER["distributions"]
    balance = dist * (on_card_pct / 100) * (dwell_days / 365)
    revenue = balance * (yield_pct / 100)
    fed_rate = Q1_26["federal_tax"] / 294_377
    # ~100% margin, flat SG&A -> flows to pretax intact; only federal applies at the margin
    # (the state franchise line is already fixed in the base case, so no double-count).
    net = revenue * (1 - fed_rate)
    return {
        "distributions": dist, "on_card_pct": on_card_pct, "dwell_days": dwell_days,
        "yield_pct": yield_pct,
        "avg_float_balance": balance, "incremental_revenue": revenue,
        "incremental_net_income": net,
        "incremental_eps": net / Q1_26["diluted_shares"],
        "vs_current_card_loads_x": dist / (Q1_26["card_loads"] * 4),
    }


def implied_current_yield():
    """What USIO actually earns on float today — the reality check on `yield_pct`.

    Q1 FY26 float interest was $0.4M in total. Customer funds (settlement processing assets +
    prepaid card load assets + customer deposits + merchant reserves) ran roughly $84M at the
    Q1 2025 balance-sheet date. That implies a realised yield well BELOW headline short rates,
    because not every balance is invested and not every program passes interest to Usio.

    Stated as a caveat rather than a correction: the balance figure is approximate and the
    Q2/Q3 balances are not read here. But if a model needs 4% to work and the company realises
    ~2%, the model is the problem.
    """
    approx_balances = 83_600_000
    annualised = Q1_26["float_interest_total"] * 4
    return {
        "approx_customer_balances": approx_balances,
        "annualised_float_interest": annualised,
        "implied_yield_pct": annualised / approx_balances * 100,
        "caveat": ("Balances are approximate (Q1 2025 balance sheet: settlement processing "
                   "assets + prepaid card load assets + customer deposits + merchant "
                   "reserves). Not every balance is invested and not every program passes "
                   "interest to Usio, so this is a floor on quality rather than a precise "
                   "yield. If a float model needs 4% and the company realises ~2%, halve it."),
    }


def build():
    lo = guidance_case(GUIDANCE["rev_growth_low"], GUIDANCE["gross_margin_low"], "fy25_flat")
    hi = guidance_case(GUIDANCE["rev_growth_high"], GUIDANCE["gross_margin_high"], "q1_run_rate")
    mid = guidance_case(11.0, 24.0, "q1_run_rate")
    grid = [float_upside(on_card_pct=p, dwell_days=d)
            for p in (40.0, 60.0, 80.0) for d in (15, 30, 45)]
    out = {
        "as_of": date.today().isoformat(),
        "source": GUIDANCE["source"],
        "fy25": FY25, "q1_26": Q1_26,
        "low": lo, "mid": mid, "high": hi,
        "float_base": float_upside(),
        "float_grid": grid,
        "current_yield": implied_current_yield(),
        "voucher": VOUCHER,
    }
    out["read"] = _read(out)
    return out


def _read(o):
    lo, mid, hi = o["low"], o["mid"], o["high"]
    f = o["float_base"]
    cy = o["current_yield"]
    return (
        "MANAGEMENT'S OWN GUIDANCE, BRIDGED TO EPS. Revenue +10-12% (GUIDED) on a gross margin "
        "back to 23-25% (a TARGET — \"I feel that we've hit the bottom... we should be able to "
        "get back to 23%-25% in the short term\") with cash SG&A \"roughly flattish\" (GUIDED) "
        "produces FY2026 EPS of roughly ${:.2f} to ${:.2f}, against FY2025's actual -${:.2f}. "
        "That is a swing of {:.0f} to {:.0f} cents, and the mechanism is operating leverage: "
        "gross profit goes from ${:.1f}M to ${:.1f}-{:.1f}M while opex is held, so nearly every "
        "incremental gross profit dollar reaches pretax. "
        "WHY THIS IS LARGER THAN THE PEER-MULTIPLE WORK SUGGESTS. Our EV/Gross Profit analysis "
        "measures the DENOMINATOR and correctly found it flat (+0.4% FY25, +6.8% in Q1). But "
        "USIO earns so little on ${:.1f}M of gross profit today that the earnings swing is "
        "mostly about the cost line, and the cost line is the thing management has actually "
        "committed to. Both are true: the multiple is not cheap on trailing gross profit, AND "
        "the EPS delta from here is large. They are answers to different questions. "
        "THE FLOAT CATALYST IS THE PART THAT FIXES THE MIX PROBLEM. Two state school-choice "
        "voucher programs, \"expected to exceed $1 billion in re-disbursements\" — roughly {:.1f}x "
        "the entire current card-load business (${:.0f}M annualised). Float interest is, in "
        "management's own words, \"100% margin\", which is the precise antidote to the 9.5% "
        "INCREMENTAL gross margin we measured on the low-margin volume driving revenue today. "
        "At {:.0f}% landing on cards, {} days of dwell and a {:.1f}% yield, that is ~${:.1f}M of "
        "average float, ~${:.1f}M of ~100%-margin revenue and about {:+.0f} cents of EPS — on "
        "top of the guidance case. "
        "AND HERE IS WHERE TO PUSH BACK. NONE of the $1B is in the 10-12% guidance, and the "
        "hedges are load-bearing: \"We've been told\", \"as much as\", \"We're not sure how... "
        "If it all goes on cards\", \"Part of it is gonna go on ACH\". No contract, no signed "
        "volume, no date. The three inputs that decide the answer — card share, dwell days, "
        "yield — were not disclosed, so they are OURS, not Usio's. Worse for the model: USIO's "
        "own realised float yield looks like ~{:.1f}%, not the {:.1f}% assumed — annualised "
        "float interest of ~${:.1f}M on roughly ${:.0f}M of customer balances. If the model "
        "needs 4% and the company earns 2%, halve the answer. Use the grid, quote the range, "
        "and never present the point estimate as guidance."
    ).format(
        lo["eps"], hi["eps"], abs(o["fy25"]["eps_diluted"]),
        (lo["eps"] - o["fy25"]["eps_diluted"]) * 100, (hi["eps"] - o["fy25"]["eps_diluted"]) * 100,
        o["fy25"]["gross_profit"] / 1e6, lo["gross_profit"] / 1e6, hi["gross_profit"] / 1e6,
        o["fy25"]["gross_profit"] / 1e6,
        f["vs_current_card_loads_x"], o["q1_26"]["card_loads"] * 4 / 1e6,
        f["on_card_pct"], f["dwell_days"], f["yield_pct"],
        f["avg_float_balance"] / 1e6, f["incremental_revenue"] / 1e6, f["incremental_eps"] * 100,
        cy["implied_yield_pct"], f["yield_pct"],
        cy["annualised_float_interest"] / 1e6, cy["approx_customer_balances"] / 1e6,
    )
