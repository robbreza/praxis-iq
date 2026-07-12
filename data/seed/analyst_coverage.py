"""
data/seed/analyst_coverage.py — the Analyst Coverage Network seed: for each
sell-side analyst who covers this client, the OTHER tickers they also cover
with an active rating, plus a hand-authored "bridge" thesis explaining why an
institution that already owns that other ticker is a plausible prospect for
this client.

Ported from app.py's DEFAULT_ANALYST_COVERAGE (Buy-Side Intelligence >
Analyst Coverage Network Targeting). Same multi-tenancy reasoning as
data/seed/buyside_institutions.py: client #2 will have a different covering
analyst with a different coverage universe, not Scott Buck's. Keyed by
client_id for that reason.

The relevance score and bridge/shared_dna text are judgment calls an IR team
member with sector knowledge makes, not something computed from data — see
core/analyst_coverage.py's docstring. Editable at runtime via "Add stock to
this analyst's coverage" in the Target Database tab; edits persist as an
override (core/analyst_coverage.py), this seed is only the day-one default.
"""

SEED_ANALYST_COVERAGE = {
    "usio": {
        "H.C. Wainwright — Scott Buck": {
            "analyst": "Scott Buck",
            "firm": "H.C. Wainwright & Co.",
            "email": "sbuck@hcwco.com",
            "coverage": [
                {
                    "ticker": "FPAY", "name": "FlexShopper", "pt": 4.50, "rating": "Buy", "sector": "Fintech / LTO",
                    "relevance": 95,
                    "bridge": "Direct fintech/payments overlap. FlexShopper holders already own a micro-cap payments "
                              "platform with ACH and card processing. USIO is the same thesis with more diversified "
                              "revenue streams and a PayFac layer. Highest-probability convert.",
                    "shared_dna": "Fintech · ACH/card processing · Micro-cap · Scott Buck Buy",
                },
                {
                    "ticker": "WYY", "name": "WidePoint", "pt": 9.00, "rating": "Buy", "sector": "IT Services / Gov",
                    "relevance": 75,
                    "bridge": "WidePoint holders buy government-contracted technology businesses at early "
                              "profitability stages. USIO's ACH and card processing for government entities "
                              "(prepaid disbursements, benefits cards) maps directly. Both are Scott Buck Buy-rated "
                              "micro-caps approaching profitability inflection.",
                    "shared_dna": "Gov-adjacent tech · Profitability inflection · Micro-cap · Scott Buck Buy",
                },
                {
                    "ticker": "INUV", "name": "Inuvo", "pt": 6.00, "rating": "Buy", "sector": "AI Advertising Tech",
                    "relevance": 65,
                    "bridge": "Inuvo holders buy Scott Buck's AI-enabled SaaS thesis at micro-cap scale. Connection "
                              "to USIO is investor profile rather than sector: these are funds comfortable with "
                              "$50-200M market cap technology platforms pre-profitability. USIO's EPS inflection "
                              "story fits that risk appetite.",
                    "shared_dna": "Micro-cap SaaS/tech · Pre-profitability growth · Scott Buck Buy",
                },
                {
                    "ticker": "AEYE", "name": "AudioEye", "pt": 12.00, "rating": "Buy",
                    "sector": "Digital Accessibility SaaS",
                    "relevance": 60,
                    "bridge": "AudioEye holders buy B2B SaaS platforms at the inflection from negative to positive "
                              "EBITDA. That is exactly the USIO story right now. Same market cap range, same "
                              "analyst, same inflection thesis. Investor profile match is strong even with sector "
                              "difference.",
                    "shared_dna": "B2B SaaS · EBITDA inflection · Micro-cap · Scott Buck Buy",
                },
                {
                    "ticker": "VERI", "name": "Veritone", "pt": 9.00, "rating": "Buy", "sector": "AI / SaaS",
                    "relevance": 50,
                    "bridge": "Veritone holders are buyers of Scott Buck-covered micro-cap tech at large implied "
                              "upside (200%+ to PT). The connection to USIO is the analyst relationship and upside "
                              "profile, not the sector. These funds trust Buck's research process — they will see "
                              "his USIO upgrade in their morning feed.",
                    "shared_dna": "Scott Buck Buy · Large implied upside · Micro-cap tech",
                },
                {
                    "ticker": "KSCP", "name": "Knightscope", "pt": 12.00, "rating": "Buy", "sector": "Security Robotics",
                    "relevance": 35,
                    "bridge": "Sector overlap with USIO is low (robotics vs payments). However, Knightscope holders "
                              "are buying deeply discounted micro-caps vs analyst PT — same investor psychology "
                              "applies to USIO's upside gap. Weak thesis bridge but shared analyst and valuation "
                              "profile.",
                    "shared_dna": "Scott Buck Buy · Deep discount to PT · Micro-cap",
                },
                {
                    "ticker": "DPRO", "name": "Draganfly", "pt": 14.00, "rating": "Buy", "sector": "Drone Technology",
                    "relevance": 25,
                    "bridge": "Minimal sector relevance to USIO. Draganfly holders are speculative micro-cap "
                              "technology buyers. Only connection is Scott Buck coverage and micro-cap risk "
                              "appetite. Low priority for USIO prospecting.",
                    "shared_dna": "Scott Buck Buy · Speculative micro-cap · High-upside thesis",
                },
                {
                    "ticker": "GCTS", "name": "GCT Semiconductor", "pt": 3.00, "rating": "Buy", "sector": "Semiconductor",
                    "relevance": 20,
                    "bridge": "Semiconductor sector has no direct payments overlap. GCTS holders are technology "
                              "hardware investors — different thesis entirely from USIO's payments software/services "
                              "model. Lowest priority in Scott Buck's network for USIO prospecting.",
                    "shared_dna": "Scott Buck Buy · Micro-cap tech",
                },
            ],
        },
        "Ladenburg Thalmann — Jon Hickman": {
            "analyst": "Jon Hickman",
            "firm": "Ladenburg Thalmann",
            "email": "jhickman@ladenburg.com",
            "coverage": [
                {
                    "ticker": "RPAY", "name": "Repay Holdings", "pt": 8.00, "rating": "Buy",
                    "sector": "ACH / Vertical Payments",
                    "relevance": 95,
                    "bridge": "Direct payments overlap — RPAY is ACH processing for vertical markets, exactly what "
                              "USIO does. RPAY holders already have the ACH payments thesis and trust Jon Hickman's "
                              "coverage. Highest-probability convert in Ladenburg's network.",
                    "shared_dna": "ACH payments · Vertical markets · Jon Hickman Buy",
                },
                {
                    "ticker": "PRTH", "name": "Priority Technology", "pt": 14.00, "rating": "Buy",
                    "sector": "PayFac / SMB",
                    "relevance": 90,
                    "bridge": "PayFac model is identical to USIO's PayFac-in-a-Box. PRTH holders understand the SMB "
                              "payment facilitation thesis deeply. Jon Hickman covers both — his USIO upgrade will "
                              "land in their inbox with immediate context.",
                    "shared_dna": "PayFac · SMB payments · Jon Hickman Buy",
                },
            ],
        },
    },
}


def get_seed_analyst_coverage(client_id):
    """Deep-ish copy (dict of dict of list-of-dicts) so callers mutating the
    returned structure (core.analyst_coverage.add_coverage_stock) never
    mutate the module-level seed constant."""
    seed = SEED_ANALYST_COVERAGE.get(client_id, {})
    return {
        key: {
            "analyst": data["analyst"], "firm": data["firm"], "email": data["email"],
            "coverage": [dict(stock) for stock in data["coverage"]],
        }
        for key, data in seed.items()
    }
