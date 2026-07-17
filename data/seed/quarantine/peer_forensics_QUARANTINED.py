"""
=============================================================================
QUARANTINED 2026-07-16 — DO NOT IMPORT. RETAINED AS EVIDENCE ONLY.
=============================================================================

Every verbatim 10-K citation in this file is FABRICATED. It was transcribed in
good faith from the client's own workbook (USIO_Peer_Benchmarking_Report_v2_2.xlsx,
"Footnote Forensics" sheet). The workbook invented the quotes. Verified against
the primary sources on 2026-07-16:

  USIO — claimed: 10-K p.58 "Revenue is recognized net of interchange and network
    fees." / "USIO is a true net reporter."
    ACTUAL (10-K filed 2026-03-18): "The Company complies with ASC 606-10 and
    reports revenues at GROSS as a PRINCIPAL versus net as an agent." and
    "Revenues ... are reported gross of amounts paid to sponsor banks as well as
    interchange and assessments paid to credit card associations."
    The string "net of interchange" does not appear anywhere in USIO's 10-K.
    -> The classification is INVERTED. USIO is a gross reporter.

  RPAY — claimed: 10-K p.38 "Revenue recognized net of interchange."
    ACTUAL (10-K filed 2026-03-09): no such sentence. RPAY performs a per-contract
    principal/agent evaluation under ASC 606-10-55-36 through -40 — i.e. MIXED and
    judgment-based, not a blanket "net reporter."

  FOUR — claimed: 10-K p.94, gross incl. ~$1.8B interchange pass-through.
    ACTUAL (10-K filed 2026-02-27): no such sentence. FOUR's disclosure is mixed
    ("TFS revenue is recognized net, as the Company is considered an agent").

Because the ONE claim that could be independently checked turned out fabricated,
and then the next two also did, NO entry in this file may be treated as fact. The
margin figures are equally unsourced: GDOT, CASS and PSFE do not report a gross
profit line AT ALL (no GrossProfit / CostOfRevenue tag in XBRL), so the workbook's
"GDOT reported_gm 40.5%" cannot have come from a 10-K — the line does not exist.

Downstream damage this file caused, all now retracted (see CHANGELOG 2026-07-16):
  * "USIO BEATS FOUR after adjustment"  — false, stale-data artefact.
  * "USIO is clean on 3/3 distortions"  — false, inverted; USIO IS the gross reporter.
  * "The RPAY gap is real economics"    — false; RPAY/USIO are not on a common basis.

Kept on disk unmodified so the error is auditable and the client's workbook can be
corrected against it. Nothing imports this module.
"""

"""
data/seed/peer_forensics.py — accounting-policy facts that make peer margins
non-comparable, with the 10-K citation for each.

WHY THIS EXISTS. Reported margins across payment processors are not comparable,
and the gap is not small. Three policy choices distort them:

  1. GROSS vs NET revenue recognition — a gross reporter books interchange it
     never keeps, inflating revenue and depressing gross margin. Same economics,
     different optics. Largest single distortion.
  2. CAPITALIZED SOFTWARE (ASC 350-40) — capitalizing development defers cost off
     the current P&L and flatters margin now, at the price of amortization later.
     A company that expenses as incurred (ASC 730) looks worse and is not.
  3. SBC ADD-BACKS in adjusted EBITDA — every peer adds SBC back, but adding back
     $89M is not the same act as adding back $1.8M. The add-back is uniform; the
     dilution it represents is not.

USIO is undistorted on all three — net reporter, expenses software as incurred,
minimal SBC — so its reported numbers are already what peers' numbers become only
AFTER adjustment. On reported figures USIO looks worse than it is. That is the
mispricing, and it is invisible unless you do this work.

SOURCING. Transcribed from USIO_Peer_Benchmarking_Report_v2 (June 2026), the IR
team's own forensic workbook, which cites a 10-K page for every entry. Those
citations are carried through verbatim — a forensic claim without a source is an
opinion, and this analysis is only worth anything if a CFO can check it.

COVERAGE IS DELIBERATELY INCOMPLETE. Only peers with real 10-K work appear here.
The workbook covered GDOT/PRTH/EEFT/FOUR/RPAY; our curated peer set (CP()) is
RPAY/CASS/CSGS/PSFE/PAY/FOUR/GDOT, so CASS, CSGS, PSFE and PAY have NO forensic
data yet. They are omitted rather than assumed clean — **mixing an unadjusted peer
into an adjusted comparison is precisely the error this tab exists to prevent.**
PRTH and EEFT are retained because the work exists, and flagged not-in-comp-set:
the peer tiering deliberately dropped them, so they inform but never enter a
median.
"""

# method: how revenue is recognised. reported_gm/adjusted_gm as decimals.
# distortion_pp: adjusted − reported, in percentage points (negative = flattered).
REVENUE_RECOGNITION = {
    "USIO": {"method": "Net reporter", "revenue_m": 94.1, "reported_gm": 0.238,
             "adjusted_gm": 0.238, "distortion_pp": 0.0,
             "cite": "10-K p.58: 'Revenue is recognized net of interchange and network fees.'"},
    "GDOT": {"method": "Gross reporter (partial)", "revenue_m": 1752, "reported_gm": 0.405,
             "adjusted_gm": 0.261, "distortion_pp": -14.4,
             "cite": "10-K p.71: reports interchange gross on Banking, net on Processing."},
    "FOUR": {"method": "Gross reporter", "revenue_m": 4236, "reported_gm": 0.321,
             "adjusted_gm": 0.218, "distortion_pp": -10.3,
             "cite": "10-K p.94: reports gross processing volume as revenue including "
                     "interchange pass-through (~$1.8B)."},
    "RPAY": {"method": "Net reporter", "revenue_m": 320, "reported_gm": 0.575,
             "adjusted_gm": 0.575, "distortion_pp": 0.0,
             "cite": "10-K p.38: 'Revenue recognized net of interchange.' Highest true net margin."},
    # Work exists but these are NOT in the curated comp set (peer tiering dropped
    # them). Kept for context; never enters a median.
    "PRTH": {"method": "Net reporter", "revenue_m": 852, "reported_gm": 0.278,
             "adjusted_gm": 0.278, "distortion_pp": 0.0, "not_in_comp_set": True,
             "cite": "10-K p.44: 'Revenue recognized at net amounts, excluding interchange "
                     "and assessment fees.'"},
    "EEFT": {"method": "Mixed — segment dependent", "revenue_m": 3870, "reported_gm": 0.545,
             "adjusted_gm": 0.482, "distortion_pp": -6.3, "not_in_comp_set": True,
             "cite": "10-K p.89: EFT Processing reports gross; epay reports net."},
}

# Capitalised software: reported vs adjusted EBITDA margin. impact_bps negative =
# reported margin is flattered by deferring development cost.
CAPITALIZED_SOFTWARE = {
    "USIO": {"policy": "Expense as incurred", "capitalized_m": None, "amort_years": None,
             "reported_ebitda_m": 0.018, "adjusted_ebitda_m": 0.018, "impact_bps": 0,
             "cite": "10-K p.61: development costs expensed as incurred per ASC 730. No capitalization."},
    "GDOT": {"policy": "Capitalize & amortize", "capitalized_m": 38.4, "amort_years": 3,
             "reported_ebitda_m": 0.158, "adjusted_ebitda_m": 0.131, "impact_bps": -270,
             "cite": "10-K p.74: FY2025 $38.4M capitalized, $29.1M amortized."},
    "FOUR": {"policy": "Capitalize & amortize", "capitalized_m": 67.2, "amort_years": 3,
             "reported_ebitda_m": 0.175, "adjusted_ebitda_m": 0.142, "impact_bps": -330,
             "cite": "10-K p.97: $67.2M capitalized FY2025, amortized over 3 years."},
    "RPAY": {"policy": "Capitalize & amortize", "capitalized_m": 18.4, "amort_years": 3,
             "reported_ebitda_m": 0.320, "adjusted_ebitda_m": 0.298, "impact_bps": -220,
             "cite": "10-K p.41: $18.4M capitalized, 3-year amortization."},
    "PRTH": {"policy": "Minimal capitalization", "capitalized_m": 4.2, "amort_years": 2,
             "reported_ebitda_m": 0.108, "adjusted_ebitda_m": 0.104, "impact_bps": -40,
             "not_in_comp_set": True, "cite": "10-K p.47: ~$4.2M. Minimal distortion."},
    "EEFT": {"policy": "Significant capitalization", "capitalized_m": 112.0, "amort_years": 5,
             "reported_ebitda_m": 0.255, "adjusted_ebitda_m": 0.201, "impact_bps": -540,
             "not_in_comp_set": True,
             "cite": "10-K p.92: largest capitalizer in the group — $112M annually over 5 years."},
}

# SBC add-back: every peer does it; the size of what's being added back differs by
# an order of magnitude.
SBC = {
    "USIO": {"sbc_m": 1.8, "pct_rev": 0.019, "reported_ebitda_m": 0.018,
             "ex_addback_m": 0.002, "impact_bps": 160,
             "cite": "10-K p.63: $1.8M SBC FY2025, ~1.9% of revenue."},
    "GDOT": {"sbc_m": 28.4, "pct_rev": 0.016, "reported_ebitda_m": 0.158,
             "ex_addback_m": 0.142, "impact_bps": 160,
             "cite": "10-K p.76: $28.4M SBC, 1.6% of revenue — below peer average."},
    "FOUR": {"sbc_m": 89.4, "pct_rev": 0.021, "reported_ebitda_m": 0.175,
             "ex_addback_m": 0.153, "impact_bps": 220,
             "cite": "10-K p.99: $89.4M — largest absolute SBC in the peer group, 2.1% of revenue."},
    "PRTH": {"sbc_m": 14.8, "pct_rev": 0.017, "reported_ebitda_m": 0.108,
             "ex_addback_m": 0.090, "impact_bps": 180, "not_in_comp_set": True,
             "cite": "10-K p.49: $14.8M, ~1.7% of revenue."},
    "EEFT": {"sbc_m": 22.1, "pct_rev": 0.006, "reported_ebitda_m": 0.255,
             "ex_addback_m": 0.250, "impact_bps": 60, "not_in_comp_set": True,
             "cite": "10-K p.94: 0.6% of revenue — mature, minimal impact."},
}

SECTIONS = [
    ("Revenue recognition — gross vs net", "HIGH", REVENUE_RECOGNITION,
     "The single largest source of non-comparability across payment processors. A gross reporter "
     "books interchange it never keeps: revenue inflates, gross margin deflates. The underlying "
     "economics can be identical."),
    ("Capitalized software development (ASC 350-40)", "MEDIUM-HIGH", CAPITALIZED_SOFTWARE,
     "Capitalizing development defers cost out of the current period and flatters margin now, "
     "paying for it in later amortization. A company that expenses as incurred reports a worse "
     "margin for the same economics."),
    ("Stock-based compensation in adjusted EBITDA", "MEDIUM", SBC,
     "Every peer adds SBC back. Adding back $89M is not the same act as adding back $1.8M — the "
     "add-back is uniform, the dilution it represents is not."),
]


def covered_tickers():
    return sorted(set(REVENUE_RECOGNITION) | set(CAPITALIZED_SOFTWARE) | set(SBC))
