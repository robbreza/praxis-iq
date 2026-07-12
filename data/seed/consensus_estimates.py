"""
data/seed/consensus_estimates.py — sell-side consensus estimates, price
target history, and IR risk-dashboard narrative content for the Markets
page.

All of this was inline in app.py's "Markets" section as several very large,
hardcoded-to-USIO Python dicts (PERIOD_GUIDANCE, PERIOD_ESTIMATES, PT_DATA,
PT_JUSTIFICATION, plus the IR Risk Dashboard's SIGNALS/risk-category lists).
Moved here, keyed by client_id, for the same reason as every other seed
file — client #2 will have a different covering analyst roster, different
guidance, and a different price history, not USIO's.

Firm-name keys here intentionally match the "firm" field used in
CLIENT_REGISTRY[...]["analysts"] (config/client_config.py) exactly, so the
page can derive analyst person-names from CA() instead of keeping a second,
independently-maintained firm->analyst-name mapping.

ALL_PERIODS / DERIVED_PERIODS are generic period-sequencing helpers, not
client data, so they stay as module-level constants rather than per-client
seed values.
"""

ALL_PERIODS = ["Q2 2026E", "Q3 2026E", "Q4 2026E", "FY 2026E",
               "Q1 2027E", "Q2 2027E", "Q3 2027E", "Q4 2027E", "FY 2027E"]

# Periods extrapolated from FY guidance via seasonal split, not directly
# published by analysts at the quarterly level.
DERIVED_PERIODS = {"Q4 2026E", "Q1 2027E", "Q2 2027E", "Q3 2027E", "Q4 2027E"}

SEED_CONSENSUS = {
    "usio": {
        "period_guidance": {
            "Q2 2026E": {"EPS Est": 0.00, "Revenue Est ($M)": 24.5, "EBITDA Est ($M)": 1.5},
            "Q3 2026E": {"EPS Est": 0.02, "Revenue Est ($M)": 25.0, "EBITDA Est ($M)": 1.8},
            "Q4 2026E": {"EPS Est": 0.04, "Revenue Est ($M)": 23.5, "EBITDA Est ($M)": 1.9},
            "FY 2026E": {"EPS Est": 0.20, "Revenue Est ($M)": 95.0, "EBITDA Est ($M)": 7.0},
            "Q1 2027E": {"EPS Est": 0.06, "Revenue Est ($M)": 25.2, "EBITDA Est ($M)": 2.3},
            "Q2 2027E": {"EPS Est": 0.08, "Revenue Est ($M)": 25.8, "EBITDA Est ($M)": 2.5},
            "Q3 2027E": {"EPS Est": 0.09, "Revenue Est ($M)": 26.4, "EBITDA Est ($M)": 2.7},
            "Q4 2027E": {"EPS Est": 0.13, "Revenue Est ($M)": 27.4, "EBITDA Est ($M)": 3.5},
            "FY 2027E": {"EPS Est": 0.38, "Revenue Est ($M)": 107.0, "EBITDA Est ($M)": 10.8},
        },
        "period_estimates": {
            "Q2 2026E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.00, "Revenue Est ($M)": 25.5, "EBITDA Est ($M)": 1.6},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.01, "Revenue Est ($M)": 24.8, "EBITDA Est ($M)": 1.7},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "Q3 2026E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.02, "Revenue Est ($M)": 26.0, "EBITDA Est ($M)": 1.9},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.03, "Revenue Est ($M)": 25.5, "EBITDA Est ($M)": 2.0},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "Q4 2026E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.04, "Revenue Est ($M)": 24.5, "EBITDA Est ($M)": 2.1},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.05, "Revenue Est ($M)": 23.7, "EBITDA Est ($M)": 2.3},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "FY 2026E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.18, "Revenue Est ($M)": 96.0, "EBITDA Est ($M)": 7.2},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.22, "Revenue Est ($M)": 94.5, "EBITDA Est ($M)": 7.5},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "Q1 2027E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.07, "Revenue Est ($M)": 25.9, "EBITDA Est ($M)": 2.4},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.08, "Revenue Est ($M)": 25.4, "EBITDA Est ($M)": 2.5},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "Q2 2027E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.08, "Revenue Est ($M)": 26.5, "EBITDA Est ($M)": 2.6},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.09, "Revenue Est ($M)": 26.1, "EBITDA Est ($M)": 2.7},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "Q3 2027E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.09, "Revenue Est ($M)": 27.2, "EBITDA Est ($M)": 2.8},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.10, "Revenue Est ($M)": 26.8, "EBITDA Est ($M)": 2.9},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "Q4 2027E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.11, "Revenue Est ($M)": 28.4, "EBITDA Est ($M)": 3.2},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.13, "Revenue Est ($M)": 27.7, "EBITDA Est ($M)": 3.9},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
            "FY 2027E": {
                "H.C. Wainwright":          {"Rating": "Buy", "Price Target": 4.00, "EPS Est": 0.35, "Revenue Est ($M)": 108.0, "EBITDA Est ($M)": 10.5},
                "Ladenburg Thalmann":       {"Rating": "Buy", "Price Target": 6.25, "EPS Est": 0.40, "Revenue Est ($M)": 106.0, "EBITDA Est ($M)": 11.0},
                "Maxim Group":              {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Litchfield Hills Research":{"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
                "Barrington Research":      {"Rating": None, "Price Target": None, "EPS Est": None, "Revenue Est ($M)": None, "EBITDA Est ($M)": None},
            },
        },
        "analyst_dates": {
            "H.C. Wainwright": "Mar 20 2026", "Ladenburg Thalmann": "May 15 2026",
            "Maxim Group": "—", "Litchfield Hills Research": "—", "Barrington Research": "—",
        },
        "pt_history": {
            "labels": ["Q3'24", "Q4'24", "Q1'25", "Q2'25", "Q3'25", "Q4'25", "Q1'26", "Q2'26"],
            "stock_prices": [1.85, 1.60, 1.30, 1.45, 1.55, 1.38, 1.59, 2.15],
            "by_firm": {
                "H.C. Wainwright":    [4.00, 4.00, 4.00, 4.00, 4.00, 4.00, 4.00, 4.00],
                "Ladenburg Thalmann": [None, None, None, 5.75, 5.75, 5.75, 5.75, 6.25],
                "Maxim Group":        [5.00, 5.00, 4.00, 4.00, 3.00, 3.00, None, None],
                "Litchfield Hills":   [5.00, 5.00, 5.00, 4.50, 4.50, 4.00, None, None],
                "Barrington Research":[6.00, 6.00, 5.00, 5.00, 4.00, 4.00, None, None],
            },
            "colors": {
                "H.C. Wainwright": "#1F3864", "Ladenburg Thalmann": "#2E75B6", "Maxim Group": "#70AD47",
                "Litchfield Hills": "#ED7D31", "Barrington Research": "#A5A5A5",
            },
        },
        "pt_justification": {
            "H.C. Wainwright": {
                "analyst": "Scott Buck", "current_pt": 4.00, "pt_set_date": "Mar 2026", "stock_at_set": 1.59,
                "methodology": "EV / Revenue", "basis_year": "FY 2027E", "rev_estimate": 108.0, "peer_multiple": 2.3,
                "stated_premium": "In-line peer group",
                "justification": "Applies an in-line peer group EV/Revenue multiple of ~2.3x on FY2027E revenue "
                                  "of ~$108M to arrive at a PT of $4.00. Does not explicitly claim a premium — "
                                  "uses peer median as the anchor.",
            },
            "Ladenburg Thalmann": {
                "analyst": "Jon Hickman", "current_pt": 6.25, "pt_set_date": "May 2026", "stock_at_set": 1.98,
                "methodology": "EV / Revenue", "basis_year": "FY 2027E", "rev_estimate": 106.0, "peer_multiple": 3.5,
                "stated_premium": "Premium to peers",
                "justification": "Applies a premium EV/Revenue multiple of ~3.5x on FY2027E revenue of ~$106M. "
                                  "The premium is justified in the note by improving margin profile and PayFac "
                                  "opportunity — implicitly assigns above peer-median execution quality.",
            },
        },
        "financial_position": {"shares_out_m": 28.3, "net_debt_m": -7.7},
        "risk_signals": [
            {"level": "red", "icon": "🔴", "title": "3 of 5 analyst models missing — consensus is unreliable",
             "desc": "Maxim, Litchfield Hills, and Barrington have no model on file. Full-year consensus is built "
                     "on 2 data points. If one analyst moves their PT, blended consensus swings 15-20%.",
             "action": "Send model request emails via Mail Gateway · Set Aug 1 as hard deadline"},
            {"level": "amber", "icon": "⚠️", "title": "Beat bar above guidance — street at $25.1M vs your $24.5M midpoint",
             "desc": "Street revenue consensus is 2.7% above guidance midpoint. Hitting your own number = a miss "
                     "vs street. Most common surprise-miss pattern for micro-caps.",
             "action": "Discuss with CFO: walk analysts back to $24.5M, or tighten guidance upward"},
            {"level": "green", "icon": "✅", "title": "138% upside to consensus PT — strongest buy-side talking point",
             "desc": "Consensus PT of $5.12 vs last trade of $2.15 = 138% implied upside. Both active analysts "
                     "are Buy-rated. Compelling non-deal roadshow headline.",
             "action": "Lead with this in institutional outreach"},
            {"level": "gray", "icon": "⚪", "title": "No insider-trading monitoring — genuine blind spot heading into earnings",
             "desc": "No Form 4 / insider transaction data source. Unplanned insider selling can be misread by "
                     "the market if it isn't anticipated and explained.",
             "action": "Manually confirm with CFO/General Counsel whether any insider transactions are scheduled."},
            {"level": "gray", "icon": "⚪", "title": "No short-interest tracking — worth watching given the size of the PT gap",
             "desc": "With large implied upside and thin analyst coverage, elevated short interest heading into "
                     "earnings would be a meaningful signal this system currently can't see.",
             "action": "Pull a short-interest report from your prime broker or a data provider ahead of the print."},
            {"level": "amber", "icon": "🗽", "title": "New York Metro NDR — highest opportunity-per-visit market on file, never visited",
             "desc": "Multiple tracked institutions here, including your top active conversion target.",
             "action": "Finalize the NY trip — Investors → NDR Planner → Active NDRs"},
            {"level": "gray", "icon": "⚪", "title": "No activism-vulnerability screening",
             "desc": "No activist-investor monitoring. For a company trading at a steep discount to consensus PT, "
                     "worth knowing about even though nothing here can track it automatically.",
             "action": "Periodically check 13D/13G filings and activist-fund screens manually."},
        ],
        "risk_categories": {
            "1. Market Signals": [
                ("Stock Performance", "YELLOW", "+1.2% AH on no specific catalyst — a real but modest, single-session move, not yet a trend."),
                ("Relative Performance", "GREEN", "Outperforming sector index by ~2 points same session."),
                ("Volatility", "GRAY", "Not tracked — no historical volatility series in this app."),
                ("Short Interest", "GRAY", "Not tracked — no short-interest data source exists here."),
            ],
            "2. Ownership / Liquidity": [
                ("Top Holder Concentration", "GRAY", "Not fully tracked — only a curated set of institutions on file, not a complete cap table."),
                ("Float Liquidity", "GRAY", "Not tracked — no shares-outstanding/float or ADV data in this app."),
                ("New Institutional Buying", "GREEN", "Multiple Tier 1 non-holders actively engaging — new investor signals tracked this period."),
                ("Retail / Momentum Risk", "GREEN", "No single outsized retail position on file."),
            ],
            "3. Estimate / Guidance Risk": [
                ("Consensus Revenue", "ORANGE", "Street sits above management's own guidance midpoint — beat bar exceeds the guided number."),
                ("EBITDA / EPS Risk", "RED", "Consensus is built on a minority of covering analysts' models — thin, easily distorted by one revision."),
                ("Guidance Credibility", "YELLOW", "No known credibility issue on file, but guidance framework hasn't been stress-tested against a print yet this cycle."),
                ("Revision Momentum", "YELLOW", "8-quarter PT history shows thin upward momentum — not negative, but not broad-based either."),
            ],
            "4. Investor Narrative Risk": [
                ("Equity Story Clarity", "YELLOW", "Re-rating thesis is clear internally, but the majority of sell-side models haven't caught up to it yet."),
                ("KPI Understanding", "GRAY", "Not tracked — no logged investor objections on file yet."),
                ("Investor Objection Trend", "GRAY", "Not tracked — same reason; populates once NDR debriefs start logging real objections."),
                ("Analyst Message Alignment", "GREEN", "Active covering analysts are Buy-rated with PT above last trade — aligned, not fighting the story."),
            ],
            "5. Event / Communication Risk": [
                ("Earnings Prep", "YELLOW", "Script and slides done, Q&A prep partial, guidance numbers still pending from CFO and legal review not yet started."),
                ("Conference Readiness", "GREEN", "Upcoming conference confirmed with management attending in person."),
                ("Disclosure Risk", "GRAY", "Not tracked — no Reg FD / selective-disclosure monitoring in this view (see Reports → Reg FD)."),
                ("Q&A Risk Topics", "ORANGE", "Named gaps identified in current Q&A prep, not yet closed."),
            ],
            "6. Governance / Reputation Risk": [
                ("Insider Selling Optics", "GRAY", "Not tracked — no Form 4 / insider transaction data source in this app."),
                ("Activism Vulnerability", "GRAY", "Not tracked — no activist-screening data source in this app."),
                ("Management Credibility", "GRAY", "Not tracked — no quantified source for this in this app."),
                ("ESG / Governance Noise", "GRAY", "Not tracked — no ESG/governance monitoring in this app."),
            ],
        },
    },
}


def get_seed_consensus(client_id):
    import copy
    return copy.deepcopy(SEED_CONSENSUS.get(client_id, {}))
