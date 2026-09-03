"""
scripts/seed_illustrative_tenant.py — build the ILLUSTRATIVE tenant used for
marketing screenshots.

WHY THIS EXISTS
The marketing site's product screenshots went stale because the data behind them
was hand-staged once and never reproducible — so after every UI change the shots
silently drifted from the product. This script makes the screenshot tenant a
build artifact: run it, open the app, re-shoot, done.

WHAT IT IS (AND ISN'T)
Every name here is INVENTED — issuer, funds, analysts, people. That is deliberate:
a screenshot must never imply a real client relationship or require a customer's
written permission to publish. It is illustrative data demonstrating REAL
capabilities, which is standard practice for product marketing.

It is NOT a fabrication risk in the sense the platform guards against elsewhere:
nothing here is presented to a client as their own computed number. It never
touches a real tenant — everything is written under client_id "demo".

RULE FOR WHOEVER EDITS THIS: only stage data for capabilities that actually
exist. Do not seed a field the product cannot populate for a real customer (e.g.
earnings-call listen duration or IR website visits — there is no call-listener or
web-analytics integration, so those stay None and the UI honestly says so).
Showing a capability we don't have is the one thing a screenshot must never do.

Run:  python scripts/seed_illustrative_tenant.py
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The status prints below use Unicode (arrows, en-dashes); the default Windows console is cp1252
# and raises UnicodeEncodeError on them. Force UTF-8 output so the seeder runs on any console.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

from core.security import load_environment  # noqa: E402

load_environment()

from config.client_config import reload_registry  # noqa: E402
from core import client_store, db  # noqa: E402

CID = "demo"
TICKER = "NLKP"
# A $2 stock reads as distressed and throws absurd upside percentages (+85%).
# Repriced to a credible small-cap. OLD_PX is what the position values in HOLDERS
# were struck at, so BOOK_SCALE keeps every holder's position-as-%-of-their-own-book
# — and therefore every conviction score — exactly where it was.
PRICE = 32.84
PREV_CLOSE = 32.26
OLD_PX = 2.84
BOOK_SCALE = PRICE / OLD_PX
CUSIP = "66512X104"          # invented
TODAY = datetime.now()
FILE_DATE = TODAY.strftime("%d-%b-%Y").upper()

# ── The issuer ───────────────────────────────────────────────────────────────
# A micro-cap payments processor: the same shape the platform's peer/comp logic
# is tuned for, so every screen behaves exactly as it does for a real client.
RECORD = {
    "ticker": TICKER,
    "name": "Northlake Payments, Inc.",
    # FULLY ILLUSTRATIVE, SELF-CONTAINED tenant. This flag makes the demo inherit NOTHING
    # cross-client — in particular it is gated OUT of the global curated house book
    # (core.curated_targets.merged / _is_illustrative), so real hand-entered targets never
    # bleed onto the public demo. Everything the demo shows comes from THIS seeder. See
    # [[illustrative-demo-tenant]].
    "illustrative": True,
    "exchange": "NASDAQ",
    "email_domain": "northlakepay.com",
    "sector": "Fintech / Payments",
    "market_cap_m": 920,
    "ev_m": 975,
    # Curated Q2 street consensus ($M) — the beat/miss calc in the Guidance
    # Decision Engine compares Q2 actual ($102.5M) against this. Without it the
    # engine falls back to an unverified live value (None) and shows the Q2
    # actual as the entire "beat vs street".
    "q2_consensus_rev": 25.7,   # Northlake Q2 Street consensus; the $25.9M actual reads as a modest beat
    "last_price": PRICE,
    "price_date": TODAY.strftime("%b %d, %Y"),
    "fy_guidance": "9-12% revenue growth",
    "peer_median_ev_rev": 2.4,
    "bar_risk_level": "MODERATE",
    "bar_risk_note": "Stock +18% YTD vs sector +6%",
    "ir_contact": {
        "name": "Dana Whitfield", "title": "VP, Investor Relations",
        "email": "dwhitfield@northlakepay.com",
    },
    "executives": {
        "CEO": {"name": "Marcus Ellery", "title": "Chief Executive Officer",
                "email": "mellery@northlakepay.com"},
        "CFO": {"name": "Priya Raman", "title": "Chief Financial Officer",
                "email": "praman@northlakepay.com"},
        "CRO": {"name": "Tom Vance", "title": "Chief Revenue Officer",
                "email": "tvance@northlakepay.com"},
    },
    "analysts": [
        {"name": "Ellis Grant", "firm": "Ashfield Research", "pt": 43.00, "rating": "Buy",
         "email": "egrant@ashfieldresearch.com", "covering": True},
        {"name": "Marta Reyes", "firm": "Denby Securities", "pt": 45.00, "rating": "Buy",
         "email": "mreyes@denbysec.com", "covering": True},
        {"name": "Owen Pike", "firm": "Westmark Partners", "pt": 38.00, "rating": "Hold",
         "email": "opike@westmarkpartners.com", "covering": True},
        {"name": "Neil Barrow", "firm": "Calder & Co.", "pt": 42.00, "rating": "Buy",
         "email": "nbarrow@calderco.com", "covering": True},
        {"name": "Sara Lindqvist", "firm": "Brightwater Equity", "pt": 45.50, "rating": "Buy",
         "email": "slindqvist@brightwatereq.com", "covering": True},
    ],
    "peers": [
        {"ticker": "PYRA", "name": "Pyramid Pay Holdings", "ev_rev": 2.9, "tier": "core"},
        {"ticker": "CLRT", "name": "Clarity Payment Systems", "ev_rev": 2.2, "tier": "core"},
        {"ticker": "VNTG", "name": "Vantage Processing Group", "ev_rev": 1.8, "tier": "close"},
    ],
    "earnings": {
        "current_quarter": "Q2 2026",
        # 35 days out, not 21: the Today "consensus lock" countdown is
        # (days_to_earnings − 20), so a 21-day window collapsed to "0 days to
        # consensus lock" once the seed date aged. 35 keeps a healthy ~15-day lock
        # runway and reads sensibly on the demo whenever it's shot.
        "earnings_date": (TODAY + timedelta(days=35)).strftime("%Y-%m-%d"),
        "call_time": "5:00 PM ET",
    },
    # Q1 2026 reported actuals — full line so the FY roll-up (Q1 actual + Q2-Q4
    # guidance) computes EPS/EBITDA, not just revenue. Q1+Q2+Q3+Q4 ties to the
    # $410M / $1.30 / $58M FY guide.
    "financials": {"last_quarter": "Q1 2026", "last_rev": 25.3, "last_eps": 0.12,
                   "last_ebitda": 5.1, "last_rev_yoy": 19.0},   # Northlake Q1 2026, from the transcript
    "guidance": {"Revenue Est ($M)": 104.0, "EPS Est": 0.54, "EBITDA Est ($M)": 22.0},
    # Guidance-policy inputs for the seasonality-adjusted Decision Engine
    # (core.guidance_engine.seasonal_read) — Northlake scale, consistent with the Q1 transcript.
    # Prior FY2025 quarters sum to ~$91M; a 13–15% range implies an FY2026 range of ~$103–105M,
    # matching the guide. Weights derive from those quarters (slightly H2-weighted as new-partner
    # go-lives ramp) and sum to 1.0.
    "guidance_policy": {
        "prior_fy_label": "FY2025",
        "prior_fy_quarterly_revenue": {"Q1": 21.3, "Q2": 21.9, "Q3": 23.2, "Q4": 24.6},
        "seasonal_weights": {"Q1": 0.234, "Q2": 0.241, "Q3": 0.255, "Q4": 0.270},
        "fy_growth_low": 0.13, "fy_growth_high": 0.15,
        "range_deltas_m": {"raise_low": 1.0, "raise_mid": 2.0, "narrow": 0.5},
        "known_h2_catalysts": [
            "New-partner go-lives — back-half weighted as ISV partners finish integration and turn on",
            "Gross-to-net revenue bridge published this quarter — closes the valuation gap vs net-revenue peers",
            "Continued net take-rate expansion as integrated mix moves toward 65%+ of net revenue",
            "Adjacent-vertical entry (property management, membership/recreation) via anchor ISV partners",
            "Net revenue retention holding above 110% — installed-base attach compounding",
        ],
        "closing_line": "We remain focused on the attach motion and the durable, recurring economics it creates for Northlake.",
        "operator_handoff": "Operator, we are ready to open the call for questions.",
    },
}

# ── Holders and peer-owners ──────────────────────────────────────────────────
# (fund, city, state, shares, value, book_total, book_positions)
# Cities are real because the roadshow-metro clustering is the point: a day's-drive
# NDR map only reads as a capability if the geography is real. The FUNDS are invented.
HOLDERS = [
    # Book totals on the top names are sized so the position is ~1%+ of the holder's
    # OWN book — that is what "conviction" means to the model, and it's what separates
    # a real owner from an index sliver.
    ("Halewood Capital Management",  "NEW YORK",      "NY", 1_420_000, 4_032_800,    340_000_000,  38),
    ("Corveth Advisors",             "GREENWICH",     "CT",   960_000, 2_726_400,    235_000_000,  31),
    ("Brentmoor Capital Management", "BOSTON",        "MA",   735_000, 2_087_400,    178_000_000,  24),
    ("Ashcombe Partners",            "STAMFORD",      "CT",   612_000, 1_738_080,    920_000_000, 130),
    ("Reddington Asset Management",  "CHICAGO",       "IL",   580_000, 1_647_200,  3_400_000_000, 210),
    ("Thornbury Investment Partners","SAN FRANCISCO", "CA",   455_000, 1_292_200,  1_800_000_000, 155),
    ("Marchmont Capital",            "DALLAS",        "TX",   402_000, 1_141_680,    540_000_000,  72),
    ("Fairmount Ridge Capital",      "PHILADELPHIA",  "PA",   455_000, 1_292_200,     92_000_000,  27),
    ("Baldwin Creek Capital",        "SEATTLE",       "WA",   318_000,   903_120,    205_000_000,  31),
    ("Longmere Trust Company",       "PASADENA",      "CA",   295_000,   837_800,  6_200_000_000, 940),
    ("Ferncliff Capital Group",      "SHORT HILLS",   "NJ",   271_000,   769_640,    480_000_000,  88),
    ("Sandhurst Equity Partners",    "AUSTIN",        "TX",   244_000,   692_960,    175_000_000,  26),
    ("Windgate Asset Management",    "MILWAUKEE",     "WI",   228_000,   647_520,    390_000_000,  64),
    ("Calloway Bridge Advisors",     "ATLANTA",       "GA",   188_000,   533_920,    620_000_000, 101),
    ("Straiton Global Investors",    "TORONTO",       "A6",   174_000,   494_160,  2_700_000_000, 240),
    ("Aldergate Asset Management",   "LONDON",        "X0",   162_000,   460_080,  4_100_000_000, 310),
    ("Rheinfeld Privatbank",         "ZURICH",        "V8",   149_000,   423_160,  1_150_000_000, 118),
    ("Cambourne Capital",            "CAMBRIDGE",     "MA",   137_000,   389_080,    215_000_000,  40),
    ("Vessley Point Partners",       "SAN MATEO",     "CA",   124_000,   352_160,     96_000_000,  18),
    ("Oakhurst Lane Capital",        "EVANSTON",      "IL",   112_000,   318_080,    130_000_000,  29),
    ("Deerfield Row Advisors",       "PITTSBURGH",    "PA",   103_000,   292_520,    240_000_000,  52),
    ("Northgate Meridian Capital",   "DENVER",        "CO",    94_000,   266_960,    310_000_000,  58),
    ("Harlow Bay Investment Co",     "MIAMI",         "FL",    86_000,   244_240,    175_000_000,  35),
    ("Kirkstone Advisors",           "REDMOND",       "WA",    78_000,   221_520,     88_000_000,  16),
]

# Type / turnover / active-passive per holder — a realistic mix so the cards, the Turnover filter,
# and the Active/Passive filter all read like a real book: concentrated hedge funds run HIGH turnover
# and Active; the big multi-hundred-position books read index-like / Passive; the Philadelphia
# showcase (Fairmount Ridge) is a LOW-turnover value believer. Read by targets_as_institutions via
# holder_profiles.json (client-scoped — real clients have none, so this never touches them).
HOLDER_PROFILES = {
    "Halewood Capital Management":   ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Corveth Advisors":              ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Brentmoor Capital Management":  ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Ashcombe Partners":             ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Reddington Asset Management":   ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Thornbury Investment Partners": ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Marchmont Capital":             ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Fairmount Ridge Capital":       ("Value Boutique",  "Low (Long-Term Value)", "Active"),
    "Baldwin Creek Capital":         ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Longmere Trust Company":        ("Bank / Trust",    "Low (Long-Term Value)", "Passive"),
    "Ferncliff Capital Group":       ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Sandhurst Equity Partners":     ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Windgate Asset Management":     ("Asset Manager",   "Low (Long-Term Value)", "Active"),
    "Calloway Bridge Advisors":      ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Straiton Global Investors":     ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Aldergate Asset Management":    ("Asset Manager",   "Medium (Growth/GARP)",  "Passive"),
    "Rheinfeld Privatbank":          ("Private Bank",    "Low (Long-Term Value)", "Active"),
    "Cambourne Capital":             ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Vessley Point Partners":        ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Oakhurst Lane Capital":         ("Growth Boutique", "Medium (Growth/GARP)",  "Active"),
    "Deerfield Row Advisors":        ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Northgate Meridian Capital":    ("Asset Manager",   "Medium (Growth/GARP)",  "Active"),
    "Harlow Bay Investment Co":      ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
    "Kirkstone Advisors":            ("Hedge Fund",      "High (Hedge/Trading)",  "Active"),
}

# Street addresses for the Philadelphia-corridor funds (13F filings don't carry a street address).
# These let the NDR "fill open slots" rows show WHERE a candidate is, and — when one is added to the
# trip — feed the itinerary's real routed driving-time calc (Philadelphia ↔ Main Line ↔ Conshohocken).
# Written to fund_addresses.json and read by the Investor Targeting page.
FUND_ADDRESSES = {
    "Cooke & Bieler L.P.":               "2001 Market St, Philadelphia, PA 19103",
    "Penn Capital Management":           "1200 Intrepid Ave, Philadelphia, PA 19112",
    "Chartwell Investment Partners":     "1205 Westlakes Dr, Berwyn, PA 19312",
    "Conestoga Capital Advisors":        "201 King of Prussia Rd, Radnor, PA 19087",
    "Glenmede Investment Management":    "1650 Market St, Philadelphia, PA 19103",
    "Brandywine Global Investment Mgmt": "1735 Market St, Philadelphia, PA 19103",
    "abrdn Inc.":                        "1176 W Swedesford Rd, Conshohocken, PA 19428",
    "Fairmount Ridge Capital":           "1818 Market St, Philadelphia, PA 19103",
    "Schuylkill Row Advisors":           "100 N 18th St, Philadelphia, PA 19103",
    "Rittenhouse Broad Market Advisors": "1 Logan Sq, Philadelphia, PA 19103",
    "Main Line Wealth Advisors":         "150 N Radnor Chester Rd, Radnor, PA 19087",
    "Rittenhouse Private Wealth":        "1919 Market St, Philadelphia, PA 19103",
    "Conshohocken Wealth Partners":      "4 Tower Bridge, Conshohocken, PA 19428",
    "Delaware Valley Financial Advisors":"1601 Cherry St, Philadelphia, PA 19102",
    "Schuylkill Wealth Management":      "150 Monument Rd, Bala Cynwyd, PA 19004",
}

# Own a PEER but not NLKP → these are what the prospect engine surfaces, and what
# fills the roadshow-metro map with non-holders.
PEER_OWNERS = [
    # New York metro — the deepest concentration (Manhattan + Fairfield County + Westchester,
    # all inside a one-day roadshow radius, so the map unifies them into "New York, NY").
    ("Ridgeline Park Capital",       "NEW YORK",      "NY", "PYRA",  8_100_000,   740_000_000, 96),
    ("Hudson Yard Advisors",         "NEW YORK",      "NY", "CLRT",  6_900_000,   620_000_000, 88),
    ("Ansonia Wealth Partners",      "GREENWICH",     "CT", "VNTG",  5_400_000,   410_000_000, 71),
    ("Bellhaven Capital Group",      "STAMFORD",      "CT", "PYRA",  4_950_000,   295_000_000, 44),
    ("Gramercy Bend Management",     "WHITE PLAINS",  "NY", "CLRT",  4_300_000,   360_000_000, 58),
    ("Half Moon Point Capital",      "PURCHASE",      "NY", "VNTG",  3_800_000,   240_000_000, 39),
    # Boston
    ("Coldwater Bay Advisors",       "BOSTON",        "MA", "PYRA",  6_200_000,   880_000_000, 128),
    ("Charles Basin Partners",       "BOSTON",        "MA", "CLRT",  5_100_000,   470_000_000, 84),
    ("Wellsbrook Investment Mgmt",   "CAMBRIDGE",     "MA", "VNTG",  3_700_000,   190_000_000, 33),
    ("Beacon Fen Capital",           "WELLESLEY",     "MA", "PYRA",  3_050_000,   210_000_000, 41),
    # San Francisco / Bay Area
    ("Presidio Gate Advisors",       "SAN FRANCISCO", "CA", "CLRT",  9_200_000, 2_400_000_000, 305),
    ("Alder Creek Capital",          "SAN FRANCISCO", "CA", "VNTG",  4_100_000,   340_000_000, 62),
    ("Marin Reach Partners",         "SAN FRANCISCO", "CA", "PYRA",  3_400_000,   280_000_000, 47),
    # Chicago
    ("Lakeshore Meridian Partners",  "CHICAGO",       "IL", "CLRT",  7_450_000, 1_250_000_000, 174),
    ("Oak Brook Equity Advisors",    "OAK BROOK",     "IL", "PYRA",  2_900_000,   165_000_000, 27),
    # Los Angeles
    ("Verdugo Hills Partners",       "LOS ANGELES",   "CA", "VNTG",  3_350_000,   210_000_000, 41),
    ("Arroyo Vista Capital",         "LOS ANGELES",   "CA", "CLRT",  2_700_000,   175_000_000, 34),
    # Single-metro stops
    ("Sturgis Lake Capital",         "DENVER",        "CO", "PYRA",  3_100_000,   118_000_000, 21),
    ("Schuylkill Row Advisors",      "PHILADELPHIA",  "PA", "VNTG",  2_600_000,   150_000_000, 28),
    ("Trinity Fork Capital",         "DALLAS",        "TX", "CLRT",  5_800_000,   620_000_000, 89),
    # International hubs
    ("Thames Meridian Asset Mgmt",   "LONDON",        "X0", "PYRA",  6_700_000, 1_900_000_000, 268),
    ("Cheapside Row Capital",        "LONDON",        "X0", "CLRT",  4_500_000,   910_000_000, 140),
    ("Kingsway Bay Capital",         "TORONTO",       "A6", "VNTG",  5_100_000,   980_000_000, 142),

    # ── Philadelphia / Main Line corridor — the roadshow IRconnect recommends (Big Picture "Top
    # opportunity"). Each owns ALL THREE tight comps (PYRA/CLRT/VNTG) at high concentration in a
    # focused book → Tier-1 conviction (~91), and the suburbs (Berwyn/Radnor/Conshohocken) fold into
    # the Philadelphia ~60-mile metro — so one click surfaces the whole corridor. Powers the
    # "plan an NDR on day one" demo; keep these together. See [[illustrative-demo-tenant]].
    ("Cooke & Bieler L.P.",              "PHILADELPHIA",  "PA", "PYRA", 55_000_000, 1_050_000_000, 16),
    ("Cooke & Bieler L.P.",              "PHILADELPHIA",  "PA", "CLRT", 54_000_000, 1_050_000_000, 16),
    ("Cooke & Bieler L.P.",              "PHILADELPHIA",  "PA", "VNTG", 53_000_000, 1_050_000_000, 16),
    ("Penn Capital Management",          "PHILADELPHIA",  "PA", "PYRA", 52_000_000, 1_100_000_000, 18),
    ("Penn Capital Management",          "PHILADELPHIA",  "PA", "CLRT", 51_000_000, 1_100_000_000, 18),
    ("Penn Capital Management",          "PHILADELPHIA",  "PA", "VNTG", 50_000_000, 1_100_000_000, 18),
    ("Chartwell Investment Partners",    "BERWYN",        "PA", "PYRA", 49_000_000, 1_150_000_000, 19),
    ("Chartwell Investment Partners",    "BERWYN",        "PA", "CLRT", 48_000_000, 1_150_000_000, 19),
    ("Chartwell Investment Partners",    "BERWYN",        "PA", "VNTG", 47_000_000, 1_150_000_000, 19),
    ("Glenmede Investment Management",   "PHILADELPHIA",  "PA", "PYRA", 46_000_000, 1_200_000_000, 20),
    ("Glenmede Investment Management",   "PHILADELPHIA",  "PA", "CLRT", 45_000_000, 1_200_000_000, 20),
    ("Glenmede Investment Management",   "PHILADELPHIA",  "PA", "VNTG", 44_000_000, 1_200_000_000, 20),
    ("Conestoga Capital Advisors",       "RADNOR",        "PA", "PYRA", 43_000_000, 1_050_000_000, 17),
    ("Conestoga Capital Advisors",       "RADNOR",        "PA", "CLRT", 42_000_000, 1_050_000_000, 17),
    ("Conestoga Capital Advisors",       "RADNOR",        "PA", "VNTG", 41_000_000, 1_050_000_000, 17),
    ("Brandywine Global Investment Mgmt","PHILADELPHIA",  "PA", "PYRA", 40_000_000, 1_250_000_000, 22),
    ("Brandywine Global Investment Mgmt","PHILADELPHIA",  "PA", "CLRT", 39_000_000, 1_250_000_000, 22),
    ("Brandywine Global Investment Mgmt","PHILADELPHIA",  "PA", "VNTG", 38_000_000, 1_250_000_000, 22),
    ("abrdn Inc.",                       "CONSHOHOCKEN",  "PA", "PYRA", 37_000_000, 1_300_000_000, 24),
    ("abrdn Inc.",                       "CONSHOHOCKEN",  "PA", "CLRT", 36_000_000, 1_300_000_000, 24),
    ("abrdn Inc.",                       "CONSHOHOCKEN",  "PA", "VNTG", 35_000_000, 1_300_000_000, 24),
    # Fairmount Ridge is our Philadelphia HOLDER — but it also owns comp CLRT, and BIGGER than it
    # owns us (CLRT ~2.8% of its book vs our 1.4%). Drives the holder "Underweight vs CLRT" read —
    # the quantified upsell case for the roadshow. (Suppressed as a peer-owner since it holds us.)
    ("Fairmount Ridge Capital",          "PHILADELPHIA",  "PA", "CLRT", 30_000_000, 1_064_000_000, 27),
    # ── Diversified & Market-maker peer-owners (illustrative) — so the metro table's Divsfd / MM
    #    buckets are populated and the segmentation (Inst / RIA / Diversified / MM / Curated) is
    #    demoable. Diversified = broad, index-like books (book_positions > the small-cap breadth_max
    #    of 1200 → routed to the Diversified review bucket, any name). Market makers = names matched
    #    by peer_prospects._MARKET_MAKER (fictional demo names added there). All fictional holdings.
    #    One of each sits in Philadelphia (Bala Cynwyd folds into the Philadelphia metro) so the
    #    showcase metro shows every bucket.
    ("Rittenhouse Broad Market Advisors","PHILADELPHIA",  "PA", "PYRA",  7_500_000,  85_000_000_000, 1_450),
    ("Ironwood Index Partners",          "NEW YORK",      "NY", "CLRT",  9_000_000, 120_000_000_000, 1_620),
    ("Lakeshore Multi-Strategy Group",   "CHICAGO",       "IL", "VNTG",  6_000_000,  60_000_000_000, 1_310),
    ("Tessera Markets LLC",              "BALA CYNWYD",   "PA", "PYRA",  3_500_000,   9_000_000_000,    320),
    ("Flowstone Securities",             "NEW YORK",      "NY", "CLRT",  4_500_000,  14_000_000_000,    410),
    # ── RIA / wealth peer-owners (illustrative) — the advisory channel: they own you/your comps via
    #    client accounts, with no PM to pitch, so they get their own bucket. Names carry a wealth/
    #    advisory pattern so peer_prospects.is_ria routes them to RIA (book < breadth_max so they
    #    don't fall to Diversified). All fold into the Philadelphia metro → RIA populated in the showcase.
    ("Main Line Wealth Advisors",        "RADNOR",        "PA", "PYRA",  1_800_000,    900_000_000,  95),
    ("Rittenhouse Private Wealth",       "PHILADELPHIA",  "PA", "CLRT",  1_200_000,    650_000_000,  70),
    ("Conshohocken Wealth Partners",     "CONSHOHOCKEN",  "PA", "VNTG",    950_000,    480_000_000,  55),
    ("Delaware Valley Financial Advisors","PHILADELPHIA", "PA", "PYRA",  1_500_000,  1_100_000_000, 110),
    ("Schuylkill Wealth Management",     "BALA CYNWYD",   "PA", "CLRT",    780_000,    520_000_000,  60),
]


def _cik_for(filer):
    """Stable synthetic CIK per fund. Needed because position history and contacts
    are both keyed by CIK — with a blank one every holder reads "No history pulled
    yet" and every Engagement Score collapses to the same number."""
    return str(1_400_000 + (abs(hash(filer)) % 500_000))


# Quant/systematic managers — tracked, but NOT 1x1-invitable (they don't take management
# meetings). Tag the broad, index-like books so the NDR "invite holders UNLESS a quant shop"
# rule has real names to demo. Philadelphia's holder (Fairmount Ridge) is deliberately NOT here,
# so the Philly showcase shows an invitable holder to defend.
_QUANT = {"Longmere Trust Company", "Aldergate Asset Management", "Straiton Global Investors"}

# How each holder weights our tight comps (PYRA/CLRT/VNTG) as a % of THEIR OWN book. Drives the
# holder-vs-comp upsell read on the prep card ("Underweight vs CLRT — get to peer weight") WITHOUT
# injecting these holders into the comps' 13F books (which would inflate peer holder-counts / the
# peer-average stability signal). Keys must be comps the holder also owns (its Peer_Overlap). NLKP
# weights for reference: Halewood 1.2% / Brentmoor 1.2% of their book — so these read Underweight.
COMP_WEIGHTS = {
    "Halewood Capital Management":  {"CLRT": 2.6, "PYRA": 1.5, "VNTG": 0.9},   # Underweight vs CLRT
    "Brentmoor Capital Management": {"PYRA": 1.9, "VNTG": 1.0},                # Underweight vs PYRA
    "Corveth Advisors":             {"PYRA": 2.3, "CLRT": 1.4},                # Underweight vs PYRA
    "Fairmount Ridge Capital":      {"CLRT": 2.8, "VNTG": 1.1},                # keeps the Philly showcase read
}


def _holder(filer, city, state, shares, value, book_total, positions, cusip=CUSIP):
    # `value` in the table was struck at OLD_PX; recompute at the new price and scale
    # the book by the same factor, so position-as-%-of-book (conviction) is untouched.
    if cusip == CUSIP:
        value = round(shares * PRICE)
        book_total = round(book_total * BOOK_SCALE)
    return {
        "cik": _cik_for(filer), "city": city, "state": state, "cusip": cusip, "filer": filer,
        "value": value, "shares": shares, "filename": "", "accession": "",
        "file_date": FILE_DATE, "book_total": book_total, "size_known": True,
        "book_positions": positions,
        "style": "Quant/Systematic" if filer in _QUANT else "Active",
        "comp_weight_pcts": COMP_WEIGHTS.get(filer),
    }


def _cache(ticker, holders, cusip=CUSIP):
    return {
        "cusip": cusip, "_error": None, "source": "illustrative-seed",
        "holders": holders, "quarter": "Q1 2026",
        "_fetched_at": TODAY.isoformat(timespec="seconds"),
    }


def seed_inbox_model(cid=CID):
    """Seed the IR-Inbox model-ingestion demo: one clean, pending analyst-model attachment plus its
    stored document, so a fresh reseed reproduces "an analyst emailed a model -> we parsed it ->
    confirm the numbers", and clicking the attachment pulls up a legible model (not a binary dump).
    Idempotent — clears any prior copy of this illustrative NLKP self-model (its queue items and
    documents, matched by filename) so re-running doesn't pile up duplicates; other inbox items
    (conference invites, shareholder inquiries, the already-filed Meridian model) are left alone."""
    from core import demo_model, documents, inbox_queue

    # Purge any NON-illustrative inbox item — the live mail poller used to route real inbound mail
    # (real personal email, TEST senders) into this demo tenant. Only items this seeder writes
    # ("illustrative-*" source) belong here; everything else is a leak.
    _q0 = db.load_json("inbox_queue.json", [], client_id=cid) or []
    _q1 = [it for it in _q0 if str(it.get("source", "")).startswith("illustrative")]
    if len(_q1) != len(_q0):
        db.save_json("inbox_queue.json", _q1, client_id=cid)
        print(f"[demo] purged {len(_q0) - len(_q1)} leaked (non-illustrative) inbox item(s)")

    # Clear prior copies of THIS model — queue items and their documents (by filename).
    queue = db.load_json("inbox_queue.json", [], client_id=cid) or []
    stale = {it.get("doc_id") for it in queue
             if it.get("category") == "model" and it.get("filename") == demo_model.FILENAME
             and it.get("doc_id") is not None}
    for existing in documents.list_documents(doc_type="model", client_id=cid):
        if existing.get("filename") == demo_model.FILENAME:
            stale.add(existing["id"])
    for did in stale:
        documents.delete_document(did, client_id=cid)
    queue = [it for it in queue
             if not (it.get("category") == "model" and it.get("filename") == demo_model.FILENAME)]
    db.save_json("inbox_queue.json", queue, client_id=cid)

    # Save the clean document, then enqueue the pending review item pointing at it.
    doc_id = documents.save_document(
        contact=demo_model.ANALYST, firm=demo_model.FIRM, doc_type="model",
        filename=demo_model.FILENAME, file_bytes=demo_model.build_model_xlsx(),
        content_type=demo_model.CONTENT_TYPE, source="illustrative-demo", client_id=cid)
    inbox_queue.enqueue_item(
        category="model", contact=demo_model.ANALYST, firm=demo_model.FIRM,
        subject="NLKP — updated Q2 2026 model",
        extracted=dict(demo_model.EXTRACTED), doc_id=doc_id, filename=demo_model.FILENAME,
        source="illustrative-demo", sender_email=demo_model.SENDER_EMAIL, client_id=cid,
        body=("Refreshed our NLKP model into the Q2 print — reiterate BUY, PT $42.70. "
              "We model Q2 revenue of $25.9M and EPS $0.13. Full model attached."))
    return doc_id


def seed_ndr_replies(cid=CID):
    """Seed inbound REPLIES to the Philadelphia NDR invites, filed in the IR Inbox, so the demo shows
    responses coming back through IRconnect (confirm / reschedule / pass). The inbox has no native
    'NDR reply' category, so these are filed items (came in → parsed → filed), shown in the inbox's
    'Recently filed' history with subject / sender / body. Idempotent — clears prior copies by source tag."""
    import uuid
    key = "inbox_queue.json"
    queue = [q for q in (db.load_json(key, [], client_id=cid) or [])
             if q.get("source") != "illustrative-ndr-reply"]
    def _reply(firm, contact, sender, subject, body, outcome, days_ago):
        ts = (TODAY - timedelta(days=days_ago)).strftime("%Y-%m-%d %H:%M")
        return {"id": str(uuid.uuid4()), "category": "ndr_request", "contact": contact, "firm": firm,
                "subject": subject, "extracted": {"city": "Philadelphia", "metro": "Philadelphia, PA"},
                "doc_id": None, "filename": None, "body": body, "sender_email": sender,
                "source": "illustrative-ndr-reply", "status": "confirmed", "outcome": outcome,
                "received_at": ts, "confirmed_at": ts}
    queue += [
        _reply("Cooke & Bieler L.P.", "Andrew Armstrong", "aarmstrong@cooke-bieler.com",
               "Re: NLKP Philadelphia NDR — glad to host",
               "Priya — yes, we'd be glad to host you. Tuesday morning at our Market St office works; "
               "we'll have two PMs and an analyst in the room.",
               "Confirmed → slotted Day 1, 9:00 AM", 3),
        _reply("Chartwell Investment Partners", "Megan Ferrell", "mferrell@chartwellip.com",
               "Re: NLKP Philadelphia NDR — timing",
               "Thanks for the invite — morning is tight for us. Could we do early afternoon in Berwyn "
               "instead? Happy to make it work.",
               "Reschedule requested — awaiting new slot", 2),
        _reply("abrdn Inc.", "David Hutchins", "dhutchins@abrdn.com",
               "Re: NLKP Philadelphia NDR — passing this round",
               "Appreciate the outreach. We'll pass this cycle, but keep us on the list for the next print.",
               "Declined — kept on list for next cycle", 2),
    ]
    db.save_json(key, queue, client_id=cid)
    return len(queue)


def seed_nobo(cid=CID):
    """Seed TWO illustrative NOBO pulls (prior + current) so the NOBO Ownership report renders the
    FULL engine — Institutional/Retail categorization, size sort + top-10 concentration + HHI, the
    13D/G threshold bands, the tracked cross-reference, and the flow read (accumulate / distribute /
    new / exited) between the two pulls (the 'compare'). Fictional beneficial owners: retail = made-up
    individuals; institutional reuses the fictional tracked-13F names so the cross-reference lights up.
    Demo tenant only (a real client must never see fabricated NOBO — see markets_page._render_nobo)."""
    import copy
    _cur = TODAY.strftime("%Y-%m-%d")
    _pri = (TODAY - timedelta(days=91)).strftime("%Y-%m-%d")
    def _h(name, typ, shares, city, st):
        return {"name": name, "type": typ, "shares": shares, "city": city, "state": st}
    # Institutional beneficial owners — a variety (custody/broker, bank trust, family office, RIAs,
    # 401k trust) with a couple crossing the 13D/G thresholds; the first six reuse tracked-13F names.
    inst = [
        _h("Keystone Brokerage & Custody",   "Institutional", 1_650_000, "Philadelphia",   "PA"),  # >5% -> 13D/G
        _h("Delaware Valley Trust Company",  "Institutional", 1_300_000, "Wilmington",     "DE"),  # ~4.6% -> watch
        _h("Halewood Capital Management",    "Institutional", 1_100_000, "New York",       "NY"),  # tracked
        _h("Fairmount Ridge Capital",        "Institutional",   640_000, "Philadelphia",   "PA"),  # tracked
        _h("Windgate Asset Management",      "Institutional",   520_000, "Milwaukee",      "WI"),  # tracked
        _h("Brentmoor Capital Management",   "Institutional",   430_000, "Boston",         "MA"),  # tracked
        _h("Radnor Family Office LLC",       "Institutional",   380_000, "Radnor",         "PA"),
        _h("Schuylkill Wealth Management",   "Institutional",   260_000, "Bala Cynwyd",    "PA"),
        _h("Liberty Bell Advisors",          "Institutional",   210_000, "Philadelphia",   "PA"),  # NEW this pull
        _h("Cascade Employee 401(k) Trust",  "Institutional",   175_000, "Denver",         "CO"),
        _h("Main Line Wealth Advisors",      "Institutional",   150_000, "Radnor",         "PA"),
        _h("Conshohocken Capital Partners",  "Institutional",   120_000, "Conshohocken",   "PA"),
    ]
    # Retail beneficial owners — a long tail of made-up individuals (broad, sticky float), varied geo.
    _ret = [
        ("Robert A. Chen", 82_000, "Wayne", "PA"), ("Margaret S. Whitfield", 54_000, "Villanova", "PA"),
        ("James P. Delgado", 38_000, "Philadelphia", "PA"), ("Patricia Nowak", 31_000, "Berwyn", "PA"),
        ("David R. Feldman", 27_500, "Cherry Hill", "NJ"), ("Susan M. Bianchi", 22_000, "Malvern", "PA"),
        ("Thomas O'Rourke", 19_800, "King of Prussia", "PA"), ("Angela Reyes", 16_400, "Media", "PA"),
        ("Kevin Zhao", 14_200, "Princeton", "NJ"), ("Barbara Klein", 12_900, "Doylestown", "PA"),
        ("Michael Sanders", 11_300, "Wilmington", "DE"), ("Jennifer Alvarez", 9_800, "West Chester", "PA"),
        ("Richard Boyle", 8_600, "Lancaster", "PA"), ("Nancy Whitman", 7_400, "Newtown", "PA"),
        ("Paul Genovese", 6_200, "Haddonfield", "NJ"), ("Karen Fitzpatrick", 5_500, "Ardmore", "PA"),
        ("Steven Park", 4_800, "Conshohocken", "PA"), ("Donna Russo", 4_100, "Phoenixville", "PA"),
        ("Gregory Hahn", 3_600, "Wayne", "PA"), ("Michelle Carter", 3_050, "Chester", "PA"),
        ("Andrew Meyer", 2_700, "Reading", "PA"), ("Laura Simmons", 2_300, "Doylestown", "PA"),
        ("Brian Kelly", 1_900, "Trenton", "NJ"), ("Emily Watson", 1_500, "Norristown", "PA"),
        ("Frank DiNardo", 1_150, "Camden", "NJ"), ("Rachel Green", 900, "Allentown", "PA"),
    ]
    current = inst + [_h(n, "Retail", s, c, st) for (n, s, c, st) in _ret]
    # PRIOR pull — same base with deltas so the flow read tells a story vs current:
    #   accumulators (prior had fewer), distributors (prior had more), NEW (absent in prior),
    #   EXITED (present in prior only).
    _acc  = {"Keystone Brokerage & Custody": 250_000, "Radnor Family Office LLC": 80_000, "Robert A. Chen": 12_000}
    _dist = {"Halewood Capital Management": 150_000, "Brentmoor Capital Management": 70_000}
    _new  = {"Liberty Bell Advisors", "Margaret S. Whitfield"}          # in current, not prior
    prior = [copy.deepcopy(h) for h in current if h["name"] not in _new]
    for h in prior:
        if h["name"] in _acc:  h["shares"] -= _acc[h["name"]]
        if h["name"] in _dist: h["shares"] += _dist[h["name"]]
    prior += [_h("Northgate Meridian Capital", "Institutional", 240_000, "Denver", "CO"),   # exited (tracked)
              _h("Edwin R. Kowalski", "Retail", 21_000, "Cherry Hill", "NJ")]                # exited (retail)
    store = {"shares_outstanding": 28_400_000,
             "pulls": [{"record_date": _pri, "holders": prior},
                       {"record_date": _cur, "holders": current}]}
    db.save_json("nobo_pulls.json", store, client_id=cid)
    return len(current), len(prior)


def seed_financials(cid=CID):
    """Seed the EDGAR financial-summary cache for the fictional NLKP ticker. Without it,
    financial_summary('NLKP') can't fetch (no real EDGAR filing) and the WHOLE Reports stack dies:
    Board IR Package renders 'Financials unavailable from EDGAR', its PDF raises, Company Financial
    Analysis fails, and Benchmarking's headline is blank (NLKP has no gross-profit leg to rank).
    Numbers tie to the seeded Q2 2026 actuals / guidance. Stored UNSCOPED (global) — the exact key
    financial_summary() reads — which is safe because NLKP is unique to the demo."""
    from core import edgar_financials as ef
    M = 1_000_000

    def pct(n, d):
        return round(n / d * 100, 1) if (n is not None and d) else None

    rev, gp, oi, ni = 102.5 * M, 24.6 * M, 12.0 * M, 9.656 * M          # ties to q2_numbers
    ebitda, dna, adj = 14.5 * M, 2.5 * M, 15.5 * M
    assets, liab, eq, ac, lc = 362 * M, 197 * M, 165 * M, 180 * M, 140 * M
    cash, restr, cust, debt = 42 * M, 82 * M, 100 * M, 8 * M
    ocf, cppe, csw = 13 * M, 1 * M, 2 * M
    capex, fcf = cppe + csw, ocf - (cppe + csw)
    summary = {
        "ticker": TICKER, "entity": RECORD["name"], "cik": "0001999001",
        "quarter_end": "2026-06-30", "bs_end": "2026-06-30",
        "income": {"revenue": rev, "cogs": rev - gp, "gross_profit": gp, "operating_income": oi,
                   "net_income": ni, "ebitda": ebitda, "dna": dna, "eps": 0.34, "adjusted_ebitda": adj,
                   "ebitda_adjustments": {"Stock-based compensation": 1 * M},
                   "gross_margin": pct(gp, rev), "operating_margin": pct(oi, rev), "net_margin": pct(ni, rev),
                   "ebitda_margin": pct(ebitda, rev), "adj_ebitda_margin": pct(adj, rev),
                   "rev_growth_yoy": 13.9, "rev_prior_year": 90 * M, "ttm_revenue": 394 * M},
        "balance": {"assets": assets, "liabilities": liab, "equity": eq, "assets_current": ac,
                    "liabilities_current": lc, "cash": cash, "restricted_cash": restr, "customer_deposits": cust,
                    "debt": debt, "net_cash": cash - debt, "cash_and_restricted": 124 * M,
                    "working_capital": ac - lc, "current_ratio": round(ac / lc, 2),
                    "debt_to_equity": pct(debt, eq), "book_value": eq},
        "cashflow": {"operating_cf": ocf, "capex": capex, "capex_ppe": cppe, "capex_software": csw,
                     "fcf": fcf, "fcf_margin": pct(fcf, rev), "ocf_margin": pct(ocf, rev)},
        "shares_out": 28_400_000, "_fetched_at": datetime.now().isoformat(),
    }
    db.save_json(ef._SUMMARY_KEY.format(ticker=TICKER), summary)   # unscoped, as financial_summary reads it
    print(f"[demo] seeded EDGAR financial summary for {TICKER} (Board Package / financials / benchmarking)")


def seed_lighthouse(cid=CID):
    """Seed the Lighthouse quant engine for the fictional ticker so the page renders live (it computes
    'why did the stock move' verdicts from a factor model over price history). We synthesize daily
    OHLCV for the issuer + comps (real factor/benchmark ETFs are reused if already loaded), seed peers
    + a couple of events, then RUN the shadow engine to persist real verdicts. No network — fully
    self-contained and deterministic."""
    import psycopg2
    import numpy as np
    import pandas as pd
    from datetime import time as _time
    from psycopg2.extras import execute_values
    from core.security import get_database_url
    from lighthouse.factors import FACTOR_ETFS
    from lighthouse.weekly import BENCHMARK_TICKERS
    from lighthouse import data as _lhdata, ceo as _ceo
    from lighthouse.factor_model import attribution
    from config.client_config import CP

    peers = [p["ticker"] for p in CP()]                     # PYRA / CLRT / VNTG (fictional)
    fict = [TICKER] + peers
    etfs = sorted(set(FACTOR_ETFS) | set(BENCHMARK_TICKERS))  # real market factor ETFs
    all_t = fict + etfs
    conn = psycopg2.connect(get_database_url()); cur = conn.cursor()
    cur.execute("DELETE FROM lh_verdict WHERE client_id=%s", (cid,))
    cur.execute("DELETE FROM lh_ohlcv WHERE ticker = ANY(%s)", (fict,))
    cur.execute("DELETE FROM lh_event WHERE client_id=%s", (cid,))
    cur.execute("DELETE FROM lh_peer WHERE client_id=%s", (cid,))
    conn.commit()

    rng = np.random.default_rng(7)                          # deterministic
    # End the synthetic history on a FRIDAY so the model's latest ISO week is a COMPLETE 5-day week.
    # weekly_digest() reads the latest ISO week; a mid-week end (a Mon TODAY produced a 1-DAY "week")
    # yields a partial that the Today-page gate now suppresses as misleading. Ending on Friday also
    # lands the seeded notable up-move (r[-1] below) inside that complete week, so the weekly card
    # tells its intended story. See page_modules_nicegui/today_page._weekly_context_data.
    _last_friday = (TODAY - timedelta(days=(TODAY.weekday() - 4) % 7)).date()
    days = pd.bdate_range(end=_last_friday, periods=320)
    kts = datetime.now(timezone.utc)
    for t in all_t:
        cur.execute("SELECT 1 FROM lh_ohlcv WHERE ticker=%s LIMIT 1", (t,))
        if cur.fetchone() and t not in fict:
            continue                                        # real ETF already loaded — reuse it
        mu, sig = (0.0005, 0.021) if t == TICKER else (0.0003, 0.014)
        r = rng.normal(mu, sig, len(days))
        if t == TICKER:
            r[-1] = 0.058                                   # a notable recent up-move to attribute
        px = 30.0 * np.cumprod(1 + r)
        vals = [(t, d.date(), float(p * 0.995), float(p * 1.012), float(p * 0.988), float(p), float(p),
                 int(4e5 + rng.integers(0, 3e5)), kts, "synthetic") for d, p in zip(days, px)]
        execute_values(cur,
            "INSERT INTO lh_ohlcv (ticker,d,open,high,low,close,adj_close,volume,knowledge_ts,source) "
            "VALUES %s ON CONFLICT (ticker,d) DO UPDATE SET adj_close=EXCLUDED.adj_close, "
            "close=EXCLUDED.close, volume=EXCLUDED.volume", vals, page_size=500)
    conn.commit()

    for pt in peers:
        cur.execute("INSERT INTO lh_peer (client_id,ticker,peer_ticker,peer_kind,weight,effective_from,knowledge_ts) "
                    "VALUES (%s,%s,%s,'business',%s,%s,%s) ON CONFLICT DO NOTHING",
                    (cid, TICKER, pt, 1.0 / len(peers), "2000-01-01", kts))
    for kind, head, ago in [("earnings", "Q2 2026 results — revenue $102.5M, ahead of the $100M guide", 6),
                            ("8-K", "New PayFac agreement with a regional QSR chain (~600 locations)", 4),
                            ("rating", "Ashfield Research reiterates Buy, price target $43", 6)]:
        cur.execute("INSERT INTO lh_event (client_id,ticker,kind,headline,published_at,materiality,url) "
                    "VALUES (%s,%s,%s,%s,%s,'confirmed','')",
                    (cid, TICKER, kind, head,
                     datetime.combine((TODAY - timedelta(days=ago)).date(), _time.min, tzinfo=timezone.utc)))
    conn.commit()

    rets = _lhdata.returns_frame(all_t, conn=conn)
    model = attribution(rets, issuer=TICKER, window=126)
    n = 0
    for d in list(model.index)[-30:]:
        v = _ceo.build_verdict(cid, TICKER, d, model.loc[d], conn=conn)
        _ceo.persist_verdict(v, conn=conn); n += 1
    # Save the weekly-context cache too, so the Today-page "This Week in Context" band and the Mobile
    # pulse render without the user first opening the Lighthouse page (which is what normally writes it).
    try:
        from lighthouse import weekly as _weekly
        _wk = _weekly.weekly_digest(model, TICKER, conn=conn)
        _weekly.save_context_cache(cid, TICKER, _wk)
    except Exception as _e:
        print(f"[demo] lighthouse weekly-cache warning: {_e!r}")
    conn.commit(); conn.close()
    print(f"[demo] seeded Lighthouse: synthetic OHLCV ({len(fict)} fictional tickers) + engine run -> {n} verdicts")


def seed_ndr_crm_extras(cid=CID):
    """Fill the Meeting Hub Post-Meeting Notes tab (was 0 records) and the Accounts (CRM) relationship
    book (quality/notes were blank for demo funds)."""
    from core import relationship_notes

    def _note(contact, firm, side, days_ago, typ, raw, structured):
        return {"Contact": contact, "Firm": firm, "Side": side,
                "Date": (TODAY - timedelta(days=days_ago)).strftime("%Y-%m-%d"), "Type": typ,
                "Raw": raw, "Structured": structured}
    notes = [
        _note("Andrew Armstrong", "Cooke & Bieler L.P.", "Buy-side", 2, "1x1",
              "Met at their Market St office. Liked the PayFac attach story, pushed on prepaid float "
              "sustainability. Asked for the gross-to-net revenue bridge. Building conviction; wants the Q2 model.",
              {"key_questions": ["How sustainable is the PayFac attach rate?",
                                 "What's the gross-to-net revenue bridge vs net-revenue peers?"],
               "concerns_raised": ["Prepaid float is rate-sensitive and may be declining"],
               "positive_signals": ["Liked the PayFac attach trajectory", "Actively building conviction"],
               "commitments_made": ["IR to send the Q2 model and the gross-to-net bridge"],
               "follow_up_actions": ["Send Q2 model", "Prepare a one-page gross-to-net bridge", "Schedule CFO follow-up"],
               "financial_kpi_takeaways": ["Revenue mix: focused on PayFac attach vs prepaid float",
                                           "Margins: benchmark on gross profit, not gross revenue"],
               "sentiment": "Positive",
               "summary": "Cooke & Bieler is warming to the story on PayFac attach but needs a clean gross-to-net "
                          "revenue bridge and reassurance on prepaid-float durability before initiating."}),
        _note("Ellis Grant", "Ashfield Research", "Sell-side", 5, "Analyst call",
              "Pre-print check-in. Reiterated Buy, PT $43. Wants Q2 detail on take-rate and PayFac volume. Modeling ~$102M Q2.",
              {"key_questions": ["What drove the take-rate trajectory in Q2?", "PayFac volume growth?"],
               "concerns_raised": ["Wants confirmation the guide isn't conservative"],
               "positive_signals": ["Reiterated Buy, PT $43", "Constructive into the print"],
               "commitments_made": ["IR to confirm segment detail post-print"],
               "follow_up_actions": ["Share segment breakout after earnings"],
               "financial_kpi_takeaways": ["Revenue growth: modeling ~$102M Q2, in line with guide",
                                           "Guidance: watching for a low-end raise"],
               "sentiment": "Positive",
               "summary": "Ashfield is constructive into Q2, modeling ~$102M with a possible low-end guidance raise; "
                          "wants post-print segment detail."}),
        _note("Sarah Whitfield", "Halewood Capital Management", "Buy-side", 9, "1x1",
              "Existing holder, adding. Comfortable with the story. Asked about capital allocation and buyback "
              "appetite. No major objections.",
              {"key_questions": ["Capital allocation priorities?", "Any buyback appetite?"],
               "concerns_raised": [],
               "positive_signals": ["Existing holder actively adding", "Comfortable with the narrative"],
               "commitments_made": ["IR to share the capital-allocation framework"],
               "follow_up_actions": ["Send capital-allocation framework"],
               "financial_kpi_takeaways": ["Capital allocation: interested in buyback vs reinvestment mix"],
               "sentiment": "Positive",
               "summary": "Halewood is a happy, adding holder focused on capital allocation; low-maintenance "
                          "relationship — share the buyback framework."}),
    ]
    db.save_json("post_meeting_notes.json", notes, client_id=cid)

    # Accounts (CRM): relationship quality + a note for marquee FICTIONAL demo funds (skip the real
    # corridor firm names — the relationship store is global). Makes Quality/Cadence columns and the
    # "Good to deal with" tile populate.
    _quality = [
        ("Halewood Capital Management", "good", "Long-time holder, adding. Very responsive, straightforward."),
        ("Corveth Advisors", "responsive", "Trimmed last quarter — worth a call to understand why."),
        ("Brentmoor Capital Management", "good", "New position this quarter; engaged and constructive."),
        ("Fairmount Ridge Capital", "good", "Philadelphia believer — defend and grow. Hosts easily."),
        ("Windgate Asset Management", "good", "Milwaukee value shop; patient, high-quality holder."),
        ("Reddington Asset Management", "low_touch", "Large index-adjacent book; low-touch."),
        ("Ashcombe Partners", "responsive", "Growing interest; met at the last conference."),
        ("Marchmont Capital", "good", "Dallas hedge fund; sharp, engaged, quick to respond."),
    ]
    for nm, q, note in _quality:
        relationship_notes.save(nm, quality=q, note=note)
    print(f"[demo] seeded {len(notes)} post-meeting notes + {len(_quality)} CRM relationship records")


def seed_targeting_extras(cid=CID):
    """Fill the Target Database + Consensus targeting surfaces that read empty:
      1. Consensus 'Last Updated' per covering firm (column was '—' for every analyst).
      2. The ISSUER's own news feed (Today's Peer Watch / top story showed 'No NLKP headlines').
      3. The transfer-agent NOBO cross-reference list (Target DB tool was blank).
      4. The analyst coverage network (mine covered stocks -> auto-generate prospects)."""
    from core import prospecting

    # 1. Consensus "Last Updated" per covering firm.
    _dates = {a["firm"]: (TODAY - timedelta(days=d)).strftime("%b %d %Y")
              for a, d in zip(RECORD["analysts"], (3, 6, 9, 12, 15))}
    db.save_json("analyst_dates_override.json", _dates, client_id=cid)

    # 2. Issuer's OWN news headlines (parked; idempotent on the illustrative-own source).
    news = [n for n in (db.load_json("peer_news.json", [], client_id=cid) or [])
            if n.get("source") != "illustrative-own"]
    _own = [
        ("Northlake Payments sets Q2 2026 earnings for August 30", 1,
         "The company will report second-quarter results after market close on August 30; a call follows."),
        ("Northlake Payments expands PayFac platform with regional QSR chain", 4,
         "A multi-year agreement adds embedded-payments volume across ~600 quick-service locations."),
        ("Ashfield Research reiterates Buy on Northlake Payments, PT $43", 6,
         "Analyst Ellis Grant cites PayFac attach and prepaid float ahead of the Q2 print."),
    ]
    news += [{"id": f"nlkp-own-{i}", "ticker": TICKER, "title": t, "url": "", "summary": s,
              "source": "illustrative-own", "pub": (TODAY - timedelta(days=d)).strftime("%Y-%m-%d")}
             for i, (t, d, s) in enumerate(_own, 1)]
    db.save_json("peer_news.json", news, client_id=cid)

    # 3. Transfer-agent NOBO list (a spread of tracked/illustrative names so the cross-ref lights up).
    _nobo = [{"holder_name": f, "shares": sh} for f, sh in [
        ("Halewood Capital Management", 1_420_000), ("Corveth Advisors", 960_000),
        ("Brentmoor Capital Management", 735_000), ("Fairmount Ridge Capital", 455_000),
        ("Windgate Asset Management", 228_000), ("Cooke & Bieler L.P.", 610_000),
        ("Ridge & Vale Capital", 180_000), ("Charter Oak Equity", 150_000),
        ("Presidio Reach Capital", 120_000), ("Schuylkill Vale Capital", 90_000)]]
    prospecting.save_nobo_list(_nobo, "Transfer agent — Q2 2026 NOBO (illustrative)", client_id=cid)

    # 4. Analyst coverage network — each covering analyst also rates 2 comps, whose 13F holders the
    #    coverage-network prospecting pipeline can mine into new prospects.
    _peers = [("PYRA", "Pyramid Pay Holdings", 40.0), ("CLRT", "Clarity Payment Systems", 31.0),
              ("VNTG", "Vantage Processing Group", 22.0)]
    _cov = {}
    for i, a in enumerate(RECORD["analysts"]):
        stocks = [{"ticker": TICKER, "name": RECORD["name"], "pt": a["pt"], "rating": a["rating"],
                   "sector": "Payments / Fintech", "relevance": 100,
                   "bridge": "Covers the issuer directly.", "shared_dna": "payments processing"}]
        for tk, nm, ppt in (_peers[i % 3], _peers[(i + 1) % 3]):   # 2 rotated comps per analyst
            stocks.append({"ticker": tk, "name": nm, "pt": ppt, "rating": "Buy",
                           "sector": "Payments / Fintech", "relevance": 85,
                           "bridge": f"Direct payments comp — same coverage lens as {TICKER}.",
                           "shared_dna": "payments processing"})
        _cov[a["name"]] = {"analyst": a["name"], "firm": a["firm"], "email": a["email"], "coverage": stocks}
    db.save_json("analyst_coverage_network.json", _cov, client_id=cid)
    print("[demo] seeded consensus dates, issuer news, transfer-agent NOBO, and analyst coverage network")


def seed():
    # 1. Register the tenant
    client_store.upsert_client(CID, RECORD, active=True, merge=False)
    reload_registry()
    print(f"[demo] registered tenant '{CID}' -> {RECORD['name']} ({TICKER})")

    # 2. Our own 13F holder book (drives Target Database + the holder side of the metro map)
    own = [_holder(*h) for h in HOLDERS]
    db.save_json(f"sec_13f_holders_{TICKER}.json", _cache(TICKER, own), client_id=CID)
    print(f"[demo] seeded {len(own)} holders of {TICKER}")

    # Per-holder type / turnover / active-passive (13F filings don't carry these) so the demo cards
    # and the Turnover / Active-Passive filters read like a real book. targets_as_institutions folds
    # these in by exact fund name; a client without this store is unaffected.
    db.save_json("holder_profiles.json",
                 {f: {"type": t, "turnover": tv, "ownership": o}
                  for f, (t, tv, o) in HOLDER_PROFILES.items()}, client_id=CID)
    print(f"[demo] seeded type/turnover profiles for {len(HOLDER_PROFILES)} holders")

    # Street addresses for the Philadelphia-corridor funds — powers the NDR fill-slot location read
    # and the itinerary's routed driving time when a filler is added to the trip.
    db.save_json("fund_addresses.json", FUND_ADDRESSES, client_id=CID)
    print(f"[demo] seeded street addresses for {len(FUND_ADDRESSES)} corridor funds")

    # 3. Peer books (drives Peer Prospects + the non-holder side of the metro map)
    by_peer = {}
    for filer, city, state, peer, value, book_total, positions in PEER_OWNERS:
        shares = round(value / 3.10)  # peer positions, unrelated to NLKP's price
        by_peer.setdefault(peer, []).append(
            _holder(filer, city, state, shares, value, book_total, positions, cusip=f"{peer}00000")
        )
    for peer, hs in by_peer.items():
        db.save_json(f"sec_13f_holders_{peer}.json", _cache(peer, hs, cusip=f"{peer}00000"), client_id=CID)
        print(f"[demo] seeded {len(hs):>2} holders of peer {peer}")

    # 3b. Position history — the add/trim/new/exit read behind each holder's "Action".
    # Without this every card reads "No history pulled yet".
    directions = ["adding", "trimming", "new", "flat", "adding", "trimming", "flat", "exited"]
    # Pin specific showcase holders regardless of their slot in the cycle. The Philadelphia
    # holder (Fairmount Ridge) should read "Adding" — a believer you defend and grow.
    _dir_override = {"Fairmount Ridge Capital": "adding"}
    hist = {}
    for i, h in enumerate(HOLDERS):
        filer = h[0]
        d = _dir_override.get(filer, directions[i % len(directions)])
        qoq = {"adding": 42_000, "trimming": -31_000, "new": 96_000,
               "flat": 0, "exited": -120_000}[d]
        # Peer overlap drives the Peer Ownership pillar. Varied deliberately: the top
        # holders own most of the comp set (the strongest signal), the tail owns none —
        # an empty list is a measured zero, not missing data.
        _overlap = [["PYRA", "CLRT", "VNTG"], ["PYRA", "CLRT"], ["PYRA", "VNTG"],
                    ["CLRT"], ["PYRA", "CLRT", "VNTG"], ["VNTG"], [], ["PYRA"]][i % 8]
        hist[_cik_for(filer).lstrip("0")] = {
            "as_of": TODAY.isoformat(timespec="seconds"), "direction": d, "continuous": d != "new",
            "peer_overlap": _overlap, "quarters_held": 1 if d == "new" else 4,
            "net_change_shares": qoq * 2, "qoq_change_shares": qoq, "quarters_examined": 4,
            "held_since_at_least": "2025-07-31",
        }
    db.save_json(f"holder_history_{TICKER}.json", hist, client_id=CID)
    print(f"[demo] seeded position history for {len(hist)} holders (add/trim/new/flat/exit)")

    # 3c. Meeting history — differentiates the Engagement Scores on Today's pipeline.
    # All dated >7 days back on purpose: top_engagement_targets() drops any fund
    # contacted inside 7 days, so recent entries would empty the widget.
    meetings = [
        # A worked relationship stacks: several logged outcomes over a couple of quarters
        # is what a genuinely engaged holder looks like in the model.
        ("Halewood Capital Management",  32, "1x1 — Investor Conference", "CFO follow-up required",
         "Michael Hale", "Wants FY guidance bridge and segment detail ahead of the print."),
        ("Halewood Capital Management",  78, "NDR meeting", "Positive — follow up",
         "Michael Hale", "Second meeting this year; added on the Q4 print."),
        ("Halewood Capital Management", 121, "Intro call", "Warm — send materials",
         "Rebecca Ilves", "Initial diligence — sent the comp sheet and 10-K walk."),
        ("Corveth Advisors",             26, "NDR meeting", "Positive — follow up",
         "Frederick Marsh", "Building a position; asked for the gross-margin walk."),
        ("Corveth Advisors",             94, "Follow-up call", "Positive — follow up",
         "Frederick Marsh", "Followed up on take-rate trajectory; constructive."),
        ("Corveth Advisors",            140, "Intro call", "Warm — send materials",
         "Frederick Marsh", "First contact via the payments conference."),
        ("Brentmoor Capital Management", 19, "Follow-up call", "Warm — send materials",
         "Alice Kenner", "Requested the investor deck and peer comp sheet."),
        ("Brentmoor Capital Management", 86, "1x1 — Investor Conference", "Positive — follow up",
         "Alice Kenner", "Micro-cap specialist; understands the gross-vs-net reporting."),
        ("Windgate Asset Management",     68, "NDR meeting", "CFO follow-up required",
         "Sofia Braun", "Asked for time with the CFO on capital allocation."),
        ("Ashcombe Partners",            41, "Intro call", "Neutral — maintain",
         "Rahul Menon", "Introductory; tracking the story, no position change signalled."),
        ("Reddington Asset Management",  55, "Earnings call Q&A", "Flag — possible exit",
         "Dana Kirby", "Pressed on take rate compression twice — watch the next 13F."),
        ("Windgate Asset Management",     12, "1x1 — Investor Conference", "Positive — follow up",
         "Sofia Braun", "Micro-cap specialist, added on the last print."),
    ]
    db.save_json("meeting_log.csv", [
        {"Fund": f, "Date": (TODAY - timedelta(days=ago)).strftime("%Y-%m-%d"), "Type": typ,
         "Attendees": who, "Notes": note, "Outcome": outcome,
         "Logged By": RECORD["ir_contact"]["name"], "Source": "Manual"}
        for f, ago, typ, outcome, who, note in meetings
    ], client_id=CID)
    print(f"[demo] seeded {len(meetings)} logged meetings (varied outcomes → differentiated scores)")

    # 3d. Inbound NDR requests from THIS client's own analysts, and logged NDR trips.
    # A demo must show a workspace being actively coordinated — an account with zeros
    # across the headline tiles reads as "this system is empty", which is the opposite
    # of the point. These are ordinary records the product manages for real clients.
    reqs = [
        ("Ellis Grant",    "Ashfield Research",  "New York",    "New York, NY",
         "Ashfield's payments conference is in three weeks — Ellis wants to slot NLKP 1x1s with "
         "attending funds while management is already in the city.", 6),
        ("Marta Reyes",    "Denby Securities",   "Boston",      "Boston, MA",
         "Marta is bringing two institutional accounts through Boston and wants to add an NLKP "
         "management meeting to that itinerary.", 4),
        ("Owen Pike",      "Westmark Partners",  "Philadelphia", "Philadelphia, PA",
         "Owen wants to introduce two Philadelphia value accounts post-print — lines up with the "
         "corridor's Tier-1 non-holders (see the Philadelphia peer-owner block).", 9),
    ]
    db.save_json("ndr_requests.json", [
        {"id": f"req-{i+1}", "analyst": a, "firm": f, "city": c, "metro": m, "reason": why,
         "received": (TODAY - timedelta(days=d)).strftime("%b %d, %Y"), "resolved": False}
        for i, (a, f, c, m, why, d) in enumerate(reqs)
    ], client_id=CID)
    trips = [
        ("New York, NY",              38, "Ashfield Research", 6),
        ("Boston, MA",                61, "Denby Securities",  5),
        ("San Francisco, CA",         96, "Westmark Partners", 4),
    ]
    _ndr_trips = [
        # Full trip shape the NDR Planner panels expect (name + meetings as a LIST, not a count) —
        # the old compact {"meetings": n, "status": "complete"} shape crashed _active_ndrs_panel.
        {"id": f"trip-{i+1}", "name": f"{sp} — {c}", "city": c, "metro": c,
         "date": (TODAY - timedelta(days=d)).strftime("%Y-%m-%d"),
         "dates": (TODAY - timedelta(days=d)).strftime("%Y-%m-%d"),
         "time": "Full day", "ndr_type": "in_person", "sponsor": sp, "sponsor_bank": sp,
         "meetings": [], "team": [], "shortlist": [], "notes": "", "focus": "", "debrief": {},
         "status": "Completed"}
        for i, (c, d, sp, n) in enumerate(trips)
    ]
    # The New York completed trip keeps its held meetings AND a fully-filled debrief, so the
    # Post-NDR Debrief tab shows a real worked example instead of an empty shell.
    _ndr_trips[0]["meetings"] = [
        {"institution": "Halewood Capital Management", "day": 1, "time": "9:00 AM", "type": "1x1",
         "format": "In-person", "status": "held", "address": "", "non_holder": False, "score": 61,
         "contact": "", "notes": "Existing holder — adding"},
        {"institution": "Ridgeline Park Capital", "day": 1, "time": "10:30 AM", "type": "1x1",
         "format": "In-person", "status": "held", "address": "", "non_holder": True, "score": 88,
         "contact": "", "notes": "Owns PYRA — top conversion target"},
        {"institution": "Hudson Yard Advisors", "day": 1, "time": "1:00 PM", "type": "1x1",
         "format": "In-person", "status": "held", "address": "", "non_holder": True, "score": 84,
         "contact": "", "notes": "Owns CLRT"},
    ]
    _ndr_trips[0]["debrief"] = {
        "meetings_held": 3, "effectiveness": 82, "best_meeting": "Ridgeline Park Capital",
        "follow_ups": "Send Ridgeline the Q2 model and the PayFac attach detail; book a CFO call in ~2 weeks.",
        "new_positions": "Ridgeline Park indicated they are building a starter position.",
        "key_objection": "Prepaid float seen as a declining, rate-sensitive revenue line.",
        "narrative_gap": "Need a cleaner bridge from gross (interchange-inclusive) revenue to net revenue for peer comparability.",
        "next_targets": "Marrow Point Capital, Sutton Yard Management (both NY, screened, not yet met).",
    }
    # Two PAST corridors (Completed + fully debriefed) and the ACTIVE New York showcase. Seeded here so
    # the whole invite→scope→run→debrief loop is demoable out of the box AND survives reseeds (a
    # hand-built NDR is wiped by the next reseed). Every meeting carries a street address so the
    # itinerary routes real driving miles/time.
    _ts = TODAY.strftime("%Y-%m-%d %H:%M")
    def _mtg(inst, day, slot, time, score, address, status="completed"):
        return {"institution": inst, "day": day, "slot_index": slot, "time": time, "type": "1x1",
                "format": "In-person", "status": status, "address": address, "notes": "Owns PYRA, CLRT, VNTG",
                "non_holder": True, "score": score, "contact": "", "confirmed_at": _ts, "source": "outbound"}

    # PAST 1 — Philadelphia Value Corridor (Completed, fully debriefed).
    _ndr_trips.append({
        "id": "trip-philly", "name": "Philadelphia Value Corridor NDR", "city": "Philadelphia, PA",
        "metro": "Philadelphia, PA", "sponsor_bank": "Westmark Partners", "sponsor": "Westmark Partners",
        "dates": (TODAY - timedelta(days=15)).strftime("%b %d") + "–" + (TODAY - timedelta(days=14)).strftime("%d, %Y"),
        "date": (TODAY - timedelta(days=15)).strftime("%Y-%m-%d"), "time": "Full day", "ndr_type": "in_person",
        "focus": "Pre-earnings — build anticipation", "team": ["Priya Raman (CFO)", "Marcus Ellery (CEO)"],
        "notes": "Convert the Main Line value corridor; defend Fairmount.", "status": "Completed",
        "days": 2, "slots_per_day": 6, "created": (TODAY - timedelta(days=22)).strftime("%Y-%m-%d"),
        "day_start": "8:00 AM", "day_end": "5:00 PM",
        "hotel": "The Rittenhouse Hotel, 210 W Rittenhouse Sq, Philadelphia, PA 19103",
        "meetings": [
            _mtg("Cooke & Bieler L.P.", 1, 0, "9:00 AM", 93, "2001 Market St, Philadelphia, PA 19103"),
            _mtg("Penn Capital Management", 1, 1, "10:30 AM", 92, "1200 Intrepid Ave, Philadelphia, PA 19112"),
            {"institution": "Glenmede Investment Management", "day": 1, "slot_index": 2, "time": "11:45 AM",
             "type": "1x1", "format": "In-person", "status": "completed",
             "address": "1650 Market St, Philadelphia, PA 19103", "notes": "Owns PYRA, CLRT, VNTG",
             "non_holder": True, "score": 92, "contact": "", "confirmed_at": _ts, "source": "outbound",
             "lunch": True, "dietary": "2 vegetarian, 1 gluten-free (Glenmede team)"},
            _mtg("Chartwell Investment Partners", 1, 3, "1:00 PM", 92, "1205 Westlakes Dr, Berwyn, PA 19312"),
            _mtg("Conestoga Capital Advisors", 1, 4, "1:30 PM", 93, "550 E Swedesford Rd, Wayne, PA 19087"),
        ],
        "shortlist": [],
        "debrief": {
            "meetings_held": 5, "effectiveness": 78, "best_meeting": "Cooke & Bieler L.P.",
            "follow_ups": "Send the updated net-take-rate bridge to Cooke & Bieler and Glenmede; both asked for the PayFac cohort detail.",
            "new_positions": "Fairmount Ridge Capital opened a starter position post-visit (per NOBO).",
            "key_objection": "Skepticism on the durability of net take-rate expansion beyond the integrated-mix shift.",
            "narrative_gap": "The deck does not quantify PayFac attach economics per merchant — funds kept asking.",
            "next_targets": "Aristotle Capital (Wayne), Miller/Howard — Philadelphia value names not yet met.",
        },
    })

    # PAST 2 — Mid-Atlantic Corridor (Completed): Baltimore anchor (T. Rowe, catered BREAKFAST) → Philly.
    def _mam(inst, time, contact, score, address, city, state, note, non_holder=True, **extra):
        m = {"institution": inst, "day": 1, "time": time, "type": "1x1", "format": "In-person",
             "status": "completed", "address": address, "city": city, "state": state,
             "metro": "Baltimore, MD", "non_holder": non_holder, "score": score, "contact": contact,
             "notes": note, "confirmed_at": _ts, "source": "outbound"}
        m.update(extra); return m
    _ndr_trips.append({
        "id": "trip-midatl", "name": "Mid-Atlantic Corridor NDR", "city": "Baltimore, MD",
        "metro": "Baltimore, MD", "sponsor_bank": "Cascade Securities", "sponsor": "Cascade Securities",
        "dates": (TODAY - timedelta(days=9)).strftime("%b %d, %Y"),
        "date": (TODAY - timedelta(days=9)).strftime("%Y-%m-%d"), "time": "Full day", "ndr_type": "in_person",
        "focus": "Baltimore–Philadelphia day's-drive corridor, anchored by T. Rowe Price.",
        "team": ["Priya Raman (CFO)", "Dana Whitfield (IR Director)"],
        "notes": "One-day corridor: Baltimore morning (T. Rowe breakfast + Brown funds) → Philadelphia afternoon.",
        "status": "Completed", "days": 1, "slots_per_day": 8,
        "created": (TODAY - timedelta(days=16)).strftime("%Y-%m-%d"),
        "day_start": "7:15 AM", "day_end": "6:00 PM", "hotel": "",
        "meetings": [
            _mam("T. Rowe Price Group", "8:00 AM", "Tom Watson, Director of Research", 95,
                 "100 E Pratt St, Baltimore, MD 21202", "Baltimore", "MD",
                 "Baltimore anchor — catered breakfast; the must-see that justifies the corridor.",
                 lunch=True, dietary="continental breakfast (T. Rowe team)"),
            _mam("Brown Advisory", "9:30 AM", "Ellen Marsh, Portfolio Manager", 84,
                 "901 S Bond St, Baltimore, MD 21231", "Baltimore", "MD", "Baltimore value — strong fit."),
            _mam("Brown Capital Management", "10:45 AM", "Gerald Pittman, Analyst", 80,
                 "1201 N Calvert St, Baltimore, MD 21202", "Baltimore", "MD", "Baltimore small-cap growth."),
            _mam("Cooke & Bieler L.P.", "1:00 PM", "Andrew Armstrong, Portfolio Manager", 93,
                 "2001 Market St, Philadelphia, PA 19103", "Philadelphia", "PA", "Philadelphia value corridor."),
            _mam("Glenmede Investment Management", "2:15 PM", "Allison Donnelly, Managing Director", 92,
                 "1650 Market St, Philadelphia, PA 19103", "Philadelphia", "PA", "Owns peers; convert."),
            _mam("Fairmount Ridge Capital", "3:30 PM", "Thomas Sorensen, Portfolio Manager", 68,
                 "1818 Market St, Philadelphia, PA 19103", "Philadelphia", "PA", "Holder — defend the position.", non_holder=False),
            _mam("Chartwell Investment Partners", "4:45 PM", "David Bright, Head of IR", 82,
                 "1205 Westlakes Dr, Berwyn, PA 19312", "Berwyn", "PA", "Main Line value close-out."),
        ],
        "shortlist": [],
        "debrief": {
            "meetings_held": 7, "effectiveness": 82, "best_meeting": "T. Rowe Price Group",
            "follow_ups": "T. Rowe (Tom Watson) wants the segment-KPI file; Brown Advisory requested a pre-earnings follow-up call.",
            "new_positions": "Brown Capital Management indicated they are building a position.",
            "key_objection": "Concentration risk in the top-3 merchant accounts.",
            "narrative_gap": "No clear framing of the Ion float-monetization upside — the story management tells but the deck does not.",
            "next_targets": "Legg Mason successors and additional Main Line value funds via the Baltimore–Philly corridor.",
        },
    })

    # ACTIVE showcase — New York · Ashfield Payments Conference (built from inbound req-1). Opens with a
    # Point72 field visit in Stamford, CT (the routing engine schedules the car out of the NYC hotel),
    # then the conference block: 2 current owners deepened + 6 new NY accounts, incl. a catered lunch.
    _HOTEL = "The Pierre, 2 E 61st St, New York, NY 10065"
    def _nym(inst, time, contact, nh, score, note, address=None, city="New York", state="NY", **extra):
        m = {"institution": inst, "day": 1, "time": time, "type": "1x1", "format": "In-person",
             "status": "scheduled", "address": address or _HOTEL, "city": city, "state": state,
             "metro": "New York, NY", "non_holder": nh, "score": score, "contact": contact,
             "notes": note, "confirmed_at": _ts, "source": "conference"}
        m.update(extra); return m
    _ndr_trips.append({
        "id": "trip-ny-ashfield", "name": "New York — Ashfield Payments Conference", "city": "New York, NY",
        "metro": "New York, NY", "sponsor_bank": "Ashfield Research", "sponsor": "Ashfield Research",
        "dates": (TODAY + timedelta(days=13)).strftime("%Y-%m-%d"),
        "date": (TODAY + timedelta(days=13)).strftime("%Y-%m-%d"), "time": "Full day", "ndr_type": "in_person",
        "focus": "Ashfield Payments Conference (NYC) — Ellis Grant's invite; slot 1x1s with attending funds while management is in the city.",
        "team": ["Priya Raman (CFO)", "Dana Whitfield (IR Director)"],
        "objectives": "Deepen 2 current owners (Halewood, Brentmoor) and open 6 new NY accounts at the Ashfield conference.",
        "notes": "Built from inbound request req-1 (Ellis Grant, Ashfield Research).", "request_id": "req-1",
        "status": "Planning", "debrief": {}, "days": 1, "slots_per_day": 8,
        "created": TODAY.strftime("%Y-%m-%d"), "day_start": "8:00 AM", "day_end": "5:00 PM",
        "hotel": _HOTEL, "lodging": _HOTEL,
        "meetings": [
            _nym("Point72 Asset Management", "8:00 AM", "Adam Feldman, Sector PM", True, 92,
                 "CT marquee — field visit; depart the hotel early, the must-do that opens the day.",
                 address="72 Cummings Point Rd, Stamford, CT 06902", city="Stamford", state="CT"),
            _nym("Halewood Capital Management", "10:00 AM", "Peter Vance, Portfolio Manager", False, 74,
                 "CURRENT OWNER — adding; deepen the relationship."),
            _nym("Ruane, Cunniff & Goldfarb", "11:00 AM", "Elena Marsh, Research Analyst", True, 86,
                 "New — marquee value shop, concentrated long-hold."),
            _nym("GAMCO Investors (Gabelli)", "12:00 PM", "Frank DeLaria, Portfolio Manager", True, 80,
                 "New — catered working lunch; classic value buyer.", lunch=True, dietary="2 vegetarian (Gabelli team)"),
            _nym("Brentmoor Capital Management", "1:00 PM", "Julia Reyes, Senior Analyst", False, 69,
                 "CURRENT OWNER — maintain; watch for trims."),
            _nym("Neuberger Berman", "2:00 PM", "Amira Osei, Portfolio Manager", True, 83,
                 "New — broad platform, small-cap sleeve."),
            _nym("First Eagle Investment Management", "3:00 PM", "Daniel Okafor, Research Analyst", True, 82,
                 "New — value discipline, patient capital."),
            _nym("Royce Investment Partners", "4:00 PM", "Steven Kohl, Portfolio Manager", True, 91,
                 "New — small-cap specialist; strong NLKP fit."),
        ],
        "shortlist": [],
    })
    db.save_json("ndr_trips.json", _ndr_trips, client_id=CID)
    print(f"[demo] seeded {len(reqs)} inbound NDR requests + {len(trips)} legacy completed NDRs "
          f"+ 2 debriefed past corridors (Philadelphia, Mid-Atlantic) + 1 ACTIVE NY Ashfield conference NDR "
          f"(Point72 field visit + 8 meetings, 2 owners + 6 new)")

    # 3d-bis. A few UPCOMING scheduled meetings so the Mobile "On the road → Your meetings" hero
    # has something to lead with in the demo (illustrative buy-side names; the tenant stays fully
    # illustrative). Shape matches investors_page's scheduled_meetings.json record.
    _mtgs = [
        (0,  "10:30", "Blue Harbor Capital",  "Dana Whitfield", "1x1",         "Buy-side",  "Q3 outlook + take-rate trajectory"),
        (0,  "14:00", "Cedar Grove Advisors", "Marcus Lin",     "Callback",    "Buy-side",  "Follow-up on interchange questions"),
        (1,  "09:30", "Ashfield Research",    "Ellis Grant",    "Analyst call","Sell-side", "Pre-print check-in — model refresh"),
        (3,  "09:00", "Westline Asset Mgmt",  "Priya Nair",     "NDR meeting",  "Buy-side",  "Intro — new coverage"),
        (5,  "15:00", "Denby Securities",     "Marta Reyes",    "Analyst call","Sell-side", "Coverage catch-up + estimate review"),
        (8,  "11:15", "Marchmont Capital",    "Tom Alvarez",    "1x1",         "Buy-side",  "Prepaid float + capital allocation"),
    ]
    db.save_json("scheduled_meetings.json", [
        {"id": f"mtg-{i+1}", "Contact": who, "Firm": firm, "Side": side,
         "Date": (TODAY + timedelta(days=d)).strftime("%Y-%m-%d"), "Time": t, "Type": typ,
         "Topic": topic, "Status": "Confirmed", "Priority": "High" if d == 0 else "Medium"}
        for i, (d, t, firm, who, typ, side, topic) in enumerate(_mtgs)
    ], client_id=CID)
    print(f"[demo] seeded {len(_mtgs)} upcoming scheduled meetings")

    # 3e. A curated target of this client's own, so the house book isn't the only entry.
    from core import curated_targets
    # Clear any client-scoped curated first so a reseed can't accumulate stale/imported
    # rows on this illustrative tenant (it must stay fully illustrative — no real contacts).
    db.save_json("curated_targets.json", [], client_id=CID)
    for nm, city, st, why in [
        ("Wissahickon Trust Advisors", "PHILADELPHIA", "PA",
         "CFO relationship from a prior seat; not a peer-holder today — wants the corridor swing."),
        ("Bracken Hill Advisors", "BOSTON", "MA",
         "Relationship carried from the CFO's prior seat; not a peer-holder today."),
    ]:
        curated_targets.add(nm, city, st, why, scope="client", cid=CID)
    print("[demo] seeded 2 client-scoped curated targets")

    # 3f. New-investor PROSPECT pipeline (prospects.json) — the platform's whole point is
    # surfacing NEW investors, so an empty pipeline made the demo read "0% new / 100% existing
    # — needs more prospecting", i.e. the tool looking broken. Seed a believable, NY-led book of
    # promoted non-holders (~28 -> a healthy ~50/50 mix vs 26 holders). All illustrative, all with
    # a real hub metro so nothing lands in a vague "International" bucket. (Call-listen & IR-web
    # signals stay unseeded on purpose — those need live integrations we don't claim.)
    _PROSPECTS = [
        # Philadelphia corridor — the funds slotted on the showcase NDR, promoted so the Prep Cards
        # tab resolves them into the tracked universe (holder status + conviction + talking points)
        # instead of a generic "discovery meeting".
        ("Cooke & Bieler L.P.","Fundamental value","Philadelphia, PA","Holds 3 peers (13F)",93,"Owns PYRA, CLRT, VNTG — deepest corridor overlap; hosting the NDR."),
        ("Penn Capital Management","Small-cap value","Philadelphia, PA","Holds 3 peers (13F)",92,"Owns PYRA, CLRT, VNTG; met on the Philadelphia NDR."),
        ("Chartwell Investment Partners","Value","Philadelphia, PA","Holds 3 peers (13F)",92,"Owns PYRA, CLRT, VNTG; Berwyn — Main Line corridor."),
        ("Glenmede Investment Management","GARP","Philadelphia, PA","Holds 3 peers (13F)",92,"Owns PYRA, CLRT, VNTG; catered-lunch meeting on the NDR."),
        ("Conestoga Capital Advisors","Small-cap growth","Philadelphia, PA","Holds 3 peers (13F)",93,"Owns PYRA, CLRT, VNTG; Radnor."),
        # New York conference swing — the non-holder funds slotted on the showcase NY NDR (Ashfield
        # Payments Conference). Promoted so the Prep Cards tab resolves each into the tracked universe
        # (holder status + conviction + talking points) instead of "not in tracked list — added by hand".
        # Fund names MUST match the meeting `institution` values seeded in seed() exactly.
        ("Point72 Asset Management","Multi-strategy","Stamford, CT","Conference",92,"Marquee multi-strat; sector PM engaged — the Connecticut anchor that opens the NY swing."),
        ("Ruane, Cunniff & Goldfarb","Concentrated value","New York, NY","Conference",86,"Classic long-hold value shop; 1x1 on the NY conference."),
        ("GAMCO Investors (Gabelli)","Fundamental value","New York, NY","Conference",80,"Deep-value buyer; catered-lunch meeting on the NY NDR."),
        ("Neuberger Berman","Broad platform","New York, NY","Conference",83,"Small-cap sleeve is the fit; 1x1 on the NY swing."),
        ("First Eagle Investment Management","Value / patient capital","New York, NY","Conference",82,"Patient value discipline; met on the NY conference."),
        ("Royce Investment Partners","Small-cap specialist","New York, NY","Conference",91,"Small-cap specialist — one of the cleanest fits in the book."),
        ("Ridge & Vale Capital","Small-cap growth","New York, NY","Holds 2 peers (13F)",88,"Owns PYRA and CLRT; no position in you — clean fit."),
        ("Hanover Reed Partners","GARP","New York, NY","Conference",83,"Met at the Q2 micro-cap conference; requested the model."),
        ("Ellison Park Advisors","Fundamental value","New York, NY","Holds peer (13F)",80,"Holds VNTG; rotating into payments."),
        ("Marrow Point Capital","Small-cap core","New York, NY","Screen",77,"Style and market-cap fit; cash to deploy."),
        ("Sutton Yard Management","Growth","New York, NY","Inbound",75,"Reached out after the earnings call."),
        ("Delancey Vale Partners","GARP","New York, NY","Holds peer (13F)",72,"Owns CLRT; conviction-add candidate."),
        ("Corbin Hollow Advisors","Value","New York, NY","Screen",69,"Deep-value mandate; watching the multiple."),
        ("Weybridge Capital","Small-cap growth","New York, NY","Conference",67,"Early interest; needs a follow-up."),
        ("Charter Oak Equity","Small-cap growth","Boston, MA","Holds 2 peers (13F)",86,"Owns PYRA and VNTG; strong overlap."),
        ("Nashoba Ridge Capital","Fundamental","Boston, MA","Conference",81,"Met on the road; asked for a call-back."),
        ("Winthrop Fen Partners","GARP","Boston, MA","Screen",76,"Fit on cap and sector."),
        ("Blackstone Brook Advisors","Value","Boston, MA","Holds peer (13F)",73,"Holds CLRT."),
        ("Merrimack Point Capital","Core","Boston, MA","Inbound",70,"Requested the deck."),
        ("Presidio Reach Capital","Growth","San Francisco, CA","Holds peer (13F)",84,"Owns PYRA; rotating into fintech."),
        ("Marin Vale Partners","Small-cap growth","San Francisco, CA","Screen",78,"Cap and style fit."),
        ("Cypress Point Advisors","GARP","San Francisco, CA","Conference",74,"West-coast swing candidate."),
        ("Sausalito Bay Capital","Core","San Francisco, CA","Screen",68,"Watching."),
        ("Prairie State Capital","Value","Chicago, IL","Holds peer (13F)",80,"Owns CLRT."),
        ("Lakefront Ridge Partners","GARP","Chicago, IL","Conference",75,"Midwest swing."),
        ("Wacker Bend Advisors","Small-cap growth","Chicago, IL","Screen",70,"Cap and sector fit."),
        ("Arroyo Reach Capital","Growth","Los Angeles, CA","Screen",76,"Style fit; cash to deploy."),
        ("Silverlake Vale Partners","GARP","Los Angeles, CA","Conference",71,"Interest at the conference."),
        ("Schuylkill Vale Capital","Value","Philadelphia, PA","Holds peer (13F)",72,"Owns VNTG."),
        ("Front Range Partners","Growth","Denver, CO","Conference",70,"Met on the road."),
        ("Thames Reach Capital","International small-cap","London, UK","Holds peer (13F)",78,"Owns PYRA; UK swing candidate."),
        ("Bay Street Vale Partners","Growth","Toronto, Canada","Conference",73,"Canadian swing; met at the conference."),
    ]
    _prospect_rows = [
        {"fund": fn, "style": stl, "metro": mt, "source": src, "score": sc, "notes": nt}
        for fn, stl, mt, src, sc, nt in _PROSPECTS
    ]
    db.save_json("prospects.json", _prospect_rows, client_id=CID)
    print(f"[demo] seeded {len(_prospect_rows)} new-investor prospects (NY-led) -> healthy new/existing mix")

    # 4. Consensus — a WORKED book: every covering analyst's model is on file. The
    # "we don't guess" discipline still shows through the unscored call pillar and the
    # provenance notes; it does not need a permanently-broken consensus to make the point.
    # Per-firm (EPS, Revenue $M, EBITDA $M) for EACH horizon period the Consensus
    # Matrix shows. Quarters are quarterly-scale; FY periods are full-year — the
    # earlier version reused the QUARTERLY estimates for FY 2026E, so the FY card
    # showed street $102M vs $410M guidance and flagged "beat/miss bar too wide".
    # FY 2027E is the roll-forward year: this is where street re-rates first, so an
    # IR team needs the view before management ever guides it.
    # Northlake scale (~$26M/quarter, ~$104M FY). Q2 consensus averages ~$25.7M, just below the $25.9M
    # actual the CFO enters, so the guidance engine reads a modest beat → "RAISE LOW END".
    _est_by_period = {
        "Q2 2026E": {
            "Ashfield Research": (0.12, 25.7, 5.3), "Denby Securities": (0.13, 25.9, 5.4),
            "Westmark Partners": (0.11, 25.3, 5.0), "Calder & Co.":     (0.12, 25.6, 5.2),
            "Brightwater Equity": (0.13, 25.8, 5.4),
        },
        "Q3 2026E": {
            "Ashfield Research": (0.13, 26.4, 5.6), "Denby Securities": (0.14, 26.7, 5.8),
            "Westmark Partners": (0.12, 26.0, 5.4), "Calder & Co.":     (0.13, 26.3, 5.5),
            "Brightwater Equity": (0.14, 26.6, 5.7),
        },
        "Q4 2026E": {
            "Ashfield Research": (0.14, 27.8, 5.9), "Denby Securities": (0.15, 28.2, 6.1),
            "Westmark Partners": (0.13, 27.3, 5.7), "Calder & Co.":     (0.14, 27.7, 5.9),
            "Brightwater Equity": (0.15, 28.0, 6.0),
        },
        "FY 2026E": {
            "Ashfield Research": (0.52, 103.5, 22.0), "Denby Securities": (0.55, 104.5, 22.6),
            "Westmark Partners": (0.49, 102.5, 21.2), "Calder & Co.":     (0.52, 103.6, 22.0),
            "Brightwater Equity": (0.54, 104.2, 22.4),
        },
        "FY 2027E": {
            "Ashfield Research": (0.62, 118.0, 26.0), "Denby Securities": (0.66, 120.0, 27.0),
            "Westmark Partners": (0.58, 116.0, 25.0), "Calder & Co.":     (0.62, 118.5, 26.2),
            "Brightwater Equity": (0.65, 119.5, 26.8),
        },
    }

    def _ests_for(table):
        out = {}
        for a in RECORD["analysts"]:
            eps, rev, ebitda = table[a["firm"]]
            out[a["firm"]] = {
                "Rating": a["rating"] or "Buy", "Price Target": a["pt"] or 42.0,
                "EPS Est": eps, "Revenue Est ($M)": rev, "EBITDA Est ($M)": ebitda,
            }
        return out

    db.save_json("period_estimates.json",
                 {p: _ests_for(t) for p, t in _est_by_period.items()}, client_id=CID)
    db.save_json("period_guidance.json", {
        "Q2 2026E": {"Revenue Est ($M)": 25.8, "EPS Est": 0.13, "EBITDA Est ($M)": 5.4},
        "Q3 2026E": {"Revenue Est ($M)": 26.4, "EPS Est": 0.135, "EBITDA Est ($M)": 5.6},
        # Q4 completes the quarterly book: Q1a 25.3 + Q2 25.8 + Q3 26.4 + Q4 26.5 = 104.0
        # ties the four-quarter roll-up to the standing FY 2026E guide (the script raises it to $104–106M).
        "Q4 2026E": {"Revenue Est ($M)": 26.5, "EPS Est": 0.14, "EBITDA Est ($M)": 5.8},
        "FY 2026E": {"Revenue Est ($M)": 104.0, "EPS Est": 0.53, "EBITDA Est ($M)": 22.0},
        # FY 2027E: preliminary framework — low-teens growth off FY26 — so the roll-forward card renders.
        "FY 2027E": {"Revenue Est ($M)": 118.0, "EPS Est": 0.62, "EBITDA Est ($M)": 25.8},
    }, client_id=CID)
    print("[demo] seeded consensus + guidance across 4 horizon periods (Q2, Q3, FY26, FY27) — full book")

    # 4b. Confirm the Q2 2026 speaker lineup. Without this, Script Generation shows
    # the "Confirm the speaker lineup" gate instead of the actual workflow — so the
    # tab looks empty, AND the persona canvases (which hold the Guidance & Outlook
    # Decision Engine the Markets deep-link scrolls to) never render.
    from core import speakers as _speakers
    _period = _speakers.current_period(CID)
    if _period:
        _speakers.confirm(_period, _speakers.default_lineup(CID), client_id=CID)
        print(f"[demo] confirmed {_period} speaker lineup (Script Generation renders the workflow, not the gate)")

    # 5. Dated analyst rating actions → the real PT drift chart
    actions = [
        ("2026-01-22", "Ashfield Research",  "Buy",  37.00, 39.00, "Raises"),
        ("2026-02-14", "Denby Securities",   "Buy",  40.00, 42.00, "Raises"),
        ("2026-03-19", "Westmark Partners",  "Hold", 40.00, 38.00, "Lowers"),
        ("2026-04-24", "Ashfield Research",  "Buy",  39.00, 41.00, "Raises"),
        ("2026-05-20", "Denby Securities",   "Buy",  42.00, 45.00, "Raises"),
        ("2026-06-18", "Ashfield Research",  "Buy",  41.00, 43.00, "Raises"),
    ]
    db.save_json("rating_actions.json", [
        {"id": f"{TICKER}|{firm}|{d}|{grade}|{pt}", "date": d, "firm": firm, "action": "main",
         "ticker": TICKER, "pt_prior": prior, "to_grade": grade, "from_grade": grade,
         "pt_action": act, "pt_current": pt}
        for d, firm, grade, prior, pt, act in actions
    ], client_id=CID)
    print(f"[demo] seeded {len(actions)} dated rating actions")

    # 6. Earnings script workflow — mid-flight, so readiness shows a real mix.
    # NOTE: this writes a USIO-scale placeholder; scripts/seed_earnings_demo.seed_script_workflow()
    # (called later in this seed) OVERWRITES it with Northlake-scale numbers, the three Street KPIs
    # (TPV / NRR / take-rate) developed from the Q1 transcript, and NLKP persona scripts. Kept as a
    # fallback so the workflow still exists if the earnings-demo seed is skipped.
    db.save_json("script_workflow_state.json", {
        "version": 1,
        "current_stage": "exec_review",
        "q2_numbers": {
            "rev": 102.5, "ach": 41.0, "card": 44.5, "prepaid": 11.0, "output": 6.0,
            "gp": 24.6, "gm": 24.0, "ebitda": 14.5, "eps": 0.34, "sga": 18.4,
            "vol": 8.9, "vol_yoy": 12.0, "txn": 118.0, "cash": 42.0, "buyback": 0.0,
            "what_new": "Q2 closed at $102.5M, ahead of the $100M guide and $102M Street. "
                        "PayFac attach and Prepaid float drove the beat; margin held at 24%.",
            "submitted_by": "Priya Raman (CFO)",
            "submitted_at": (TODAY - timedelta(days=6)).strftime("%Y-%m-%d %H:%M"),
        },
        "stages": {
            "cfo_numbers":   {"status": "complete", "completed_at": (TODAY - timedelta(days=6)).strftime("%Y-%m-%d %H:%M"), "notes": ""},
            "ir_review":     {"status": "complete", "completed_at": (TODAY - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"), "notes": ""},
            "exec_review":   {"status": "active",   "completed_at": None, "notes": ""},
            "consolidate":   {"status": "pending",  "completed_at": None, "notes": ""},
            "legal_signoff": {"status": "pending",  "completed_at": None, "notes": ""},
        },
        # Illustrative adversarial-Q&A predictions (normally produced by the AI pass on the
        # Script Generation tab) — seeded so the Morning-After "Prep vs. Actual" loop-closer
        # has predictions to grade against the seeded Q2 transcript below.
        "adversarial_qa": {
            "generated_at": (TODAY - timedelta(days=2)).strftime("%Y-%m-%d %H:%M"),
            "items": [
                {"question": "The $2.5M beat is attributed to stronger PayFac attach — is that improvement "
                             "sustainable or a pull-forward?", "why": "", "angle": ""},
                {"question": "Prepaid float drove the quarter, but prepaid was flagged as declining — is the "
                             "softness structural or temporary?", "why": "", "angle": ""},
                {"question": "Interest income is absent from the revenue and margin commentary despite being "
                             "material — did it stabilize?", "why": "", "angle": ""},
                {"question": "Hitting the guidance low end implies a sharp H2 deceleration from the H1 run-rate "
                             "— walk us through the cadence.", "why": "", "angle": ""},
                {"question": "Cash improved to $42M but there's no mention of capital allocation — buyback, "
                             "M&A, or reinvestment?", "why": "", "angle": ""},
                {"question": "You're maintaining the high end to preserve conservatism around H2 execution — "
                             "what specifically are you hedging?", "why": "", "angle": ""},
                {"question": "Operating margin held flat at 24% despite a $2.5M revenue beat — why no "
                             "incremental-margin flow-through?", "why": "", "angle": ""},
            ],
        },
        # Illustrative prep-vs-actual history so the Morning-After "Prediction accuracy
        # over time" trend shows the loop compounding (Q1 17% -> Q2 29%). The Q2 record
        # is regenerated for real when the user runs the comparison against the transcript.
        "prep_vs_actual": {
            "Q1 2026": {
                "generated_at": (TODAY - timedelta(days=83)).strftime("%Y-%m-%d %H:%M"),
                "script": {"delivered": ["Revenue and margin walk", "Volume growth commentary"],
                           "dropped": ["Interest-income sensitivity"], "improvised": ["Board refresh mention"]},
                "qa": {"hits": [{"pred": "Take-rate durability", "actual": "asked about attach sustainability"}],
                       "misses": ["Prepaid mix shift", "Interest income", "Opex leverage", "Churn by cohort",
                                  "FX exposure"],
                       "surprises": ["Regulatory exposure to interchange caps", "Data-center cost inflation"],
                       "hit_rate": 17},
                "had_predictions": True, "accrued": {"new_global": 0, "new_client": 3}},
            "Q2 2026": {
                "generated_at": (TODAY - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"),
                "script": {"delivered": ["Revenue $102.5M", "Margin 24%", "Volume $8.9B +12%"],
                           "dropped": ["Prepaid float driver"], "improvised": ["QSR partnership"]},
                "qa": {"hits": [{"pred": "H2 deceleration cadence", "actual": "asked about the back-half step-down"},
                                {"pred": "Capital allocation priority", "actual": "buyback vs M&A"}],
                       "misses": ["PayFac attach sustainability", "Prepaid softness", "Interest income",
                                  "High-end conservatism", "Flat operating margin"],
                       "surprises": ["Big-tech competitive positioning", "QSR partnership economics"],
                       "hit_rate": 29},
                "had_predictions": True, "accrued": {"new_global": 0, "new_client": 4}},
        },
    }, client_id=CID)
    print("[demo] seeded script workflow (2 of 5 stages complete, Q2 actuals in -> engine computes)")

    # 6b. Illustrative Q2 2026 call transcript — so the Morning-After tab can demonstrate the
    # "Prep vs. Actual" loop-closer end to end: the prepared remarks drop the prepaid-float
    # driver and improvise a QSR partnership; the Q&A hits two predictions (H2 cadence, capital
    # allocation), misses the rest, and throws two surprises (big-tech competition, the
    # partnership's economics). Illustrative demo content only.
    from core import transcripts as _transcripts
    _q2_transcript = """Operator
Operator
Conference Operator
00:00:00
Good afternoon and welcome to the Northlake Payments, Inc. Second Quarter 2026 Earnings Conference Call. All participants are in a listen-only mode. After management's prepared remarks there will be a question-and-answer session. I will now turn the call over to Dana Whitfield, Investor Relations.

Dana Whitfield
Dana Whitfield
Investor Relations
00:01:10
Thank you, operator, and good afternoon everyone. With me today are Marcus Ellery, Chief Executive Officer, and Priya Raman, Chief Financial Officer. Before we begin, I'd remind you that today's call contains forward-looking statements subject to risks and uncertainties, and I refer you to our SEC filings. With that, I'll turn it to Marcus.

Marcus Ellery
Marcus Ellery
Chief Executive Officer
00:02:30
Thank you, Dana. We delivered a strong second quarter and are raising our full-year revenue guidance to a range of $405.9 million to $413.3 million. I'm also very pleased to announce today that we have signed a multi-year processing partnership with a leading national quick-service restaurant brand, which we expect to begin contributing in the fourth quarter. Our strategy of deepening enterprise relationships is working.

Priya Raman
Priya Raman
Chief Financial Officer
00:06:15
Thank you, Marcus. Second quarter revenue was $102.5 million, gross margin was 24 percent, and adjusted EBITDA was $14.5 million. We ended the quarter with $42 million of cash on the balance sheet. Our results reflect disciplined execution across the business.

Tom Vance
Tom Vance
Chief Revenue Officer
00:11:40
Thanks, Priya. Transaction volume reached $8.9 billion in the quarter, up 12 percent year over year, and our PayFac attach rates continued to improve across the merchant base.

Operator
Operator
Conference Operator
00:15:00
We will now begin the question-and-answer session. Our first question comes from an analyst.

Analyst - William Rourke, Cedar Point Securities
00:15:20
Thanks for taking my question. Your full-year guidance implies a meaningful step-down in the second half growth rate versus the first half run-rate. Can you walk us through the cadence and what gives you confidence in the back half?

Marcus Ellery
Chief Executive Officer
00:16:05
Sure. We expect steady sequential execution and the new partnership ramps in Q4, which underpins our confidence.

Analyst - Priya Nadar, Kingsbridge Research
00:18:40
With $42 million of cash and improving free cash flow, how are you thinking about capital allocation - buybacks, M&A, or continued reinvestment?

Priya Raman
Chief Financial Officer
00:19:20
For now our priority remains organic reinvestment, though we continuously evaluate the landscape.

Analyst - Greg Molina, Fairhaven Partners
00:22:10
Can you talk about the competitive environment, particularly with the larger technology platforms moving further into embedded payments? How defensible is your position?

Marcus Ellery
Chief Executive Officer
00:23:00
We believe our vertical specialization and service model differentiate us, and we feel well positioned.

Analyst - Sarah Kwon, Delphi Equity
00:26:30
On the new QSR partnership you announced - can you give any sense of the size or the economics, and whether it's exclusive?

Marcus Ellery
Chief Executive Officer
00:27:10
We're not disclosing specific terms today, but we view it as a strategically significant enterprise win.

Operator
00:31:00
That concludes today's question-and-answer session. Thank you for joining.
"""
    _transcripts.ingest_transcript(_q2_transcript, "Q2 2026", call_date=(TODAY - timedelta(days=3)).strftime("%Y-%m-%d"),
                                   source="illustrative-demo", source_filename="NLKP_Q2_2026_call.txt", client_id=CID)
    print("[demo] seeded illustrative Q2 2026 transcript (Morning-After prep-vs-actual demo)")

    # 7. Form 4 insider activity — a real capability (SEC EDGAR), so it may be shown.
    ins = [
        ("Ellery Marcus A",  "Chief Executive Officer", "P", 12_000, 31.40, "2026-06-24"),
        ("Raman Priya",      "Chief Financial Officer", "P",  7_500, 31.28, "2026-06-24"),
        ("Vance Thomas R",   "Chief Revenue Officer",   "P",  4_500, 31.55, "2026-06-25"),
        ("Okafor Adaeze",    "Director",                "P",  3_600, 31.90, "2026-06-26"),
        ("Raman Priya",      "Chief Financial Officer", "F",  1_450, 32.40, "2026-07-01"),
        ("Lindgren Erik",    "Director",                "S",  5_200, 33.10, "2026-07-08"),
    ]
    # `open_market` is what net_open_market() filters on — P/S are open-market,
    # grants/exercises/withholdings are routine comp and must not count as signal.
    db.save_json("insider_txns.json", [
        {"id": f"{TICKER}|{o}|{d}|{c}|{float(s)}", "ad": "A" if c == "P" else "D",
         "owner": o, "role": r, "code": c, "shares": float(s), "price": p,
         "date": d, "filed": d, "ticker": TICKER, "open_market": c in ("P", "S"),
         "shares_after": None}
        for o, r, c, s, p, d in ins
    ], client_id=CID)
    print(f"[demo] seeded {len(ins)} Form 4 transactions")

    # 8. Price snapshots. Invented tickers resolve to nothing at SEC/Yahoo, so without
    # a warm cache every render burns ~20s per ticker on lookups that can only fail.
    # Seeding the cache keeps the screenshot tenant fast and deterministic.
    from core import market_data
    prices = {TICKER: (PRICE, PREV_CLOSE, 1.80, 412_000, 355_000),
              "PYRA": (18.40, 18.62, -1.18, 1_240_000, 1_100_000),
              "CLRT": (9.15, 9.02, 1.44, 880_000, 795_000),
              "VNTG": (5.62, 5.71, -1.58, 615_000, 560_000)}
    for tk, (last, prev, pct, vol, avg) in prices.items():
        market_data._save_snapshot(tk, {
            "last_price": last, "prev_close": prev, "pct_change": pct,
            "volume": vol, "avg_volume_10d": avg,
            "as_of": TODAY.isoformat(timespec="seconds"),
        }, client_id=CID)
    # Same reason: park the invented tickers in the CIK map so EDGAR lookups short-circuit.
    db.save_json("sec_cik_fallback.json",
                 {tk: None for tk in [TICKER] + list(by_peer)}, client_id=CID)
    print(f"[demo] seeded price snapshots for {len(prices)} tickers + CIK short-circuit")

    # Peer news — illustrative headlines for the fictional peers, so the demo's
    # "top story" reads real without pulling live news for invented tickers. The
    # news_feed refresh skips these parked tickers, so nothing overwrites them.
    _newsdt = lambda n: (TODAY - timedelta(days=n)).isoformat() + "T13:30:00+00:00"
    db.save_json("peer_news.json", [
        {"id": "demo-vntg-q2", "ticker": "VNTG",
         "title": "Vantage Processing Group posts Q2 revenue beat, reaffirms full-year outlook",
         "provider": "Industry Wire", "url": None,
         "summary": "The payments processor reported quarterly revenue ahead of Street expectations and held its full-year guidance.",
         "pub": _newsdt(1)},
        {"id": "demo-pyra-net", "ticker": "PYRA",
         "title": "Pyramid Pay Holdings expands merchant network through regional bank partnership",
         "provider": "Industry Wire", "url": None,
         "summary": "The agreement adds mid-market merchant volume across the Southeast.",
         "pub": _newsdt(2)},
        {"id": "demo-clrt-cfo", "ticker": "CLRT",
         "title": "Clarity Payment Systems names new CFO ahead of Q2 results",
         "provider": "Industry Wire", "url": None,
         "summary": "The appointment comes as the company prepares to report second-quarter earnings.",
         "pub": _newsdt(3)},
    ], client_id=CID)
    print("[demo] seeded 3 illustrative peer-news headlines")

    # 9. Calendar — an IR year actually has things on it.
    _d = lambda n: (TODAY + timedelta(days=n)).strftime("%Y-%m-%d")
    db.save_json("ir_conference_calendar.csv", [
        {"Event": "Q2 2026 Earnings Call", "Type": "Earnings", "Date": _d(21),
         "Location": "Virtual / Conference Bridge", "Organizer": "Northlake Internal",
         "Status": "Confirmed", "Deadline": _d(20),
         "Notes": "5:00 PM ET · webcast at northlakepay.com/events/", "Source": "Press Release",
         "Attending": "Marcus Ellery, Priya Raman, Dana Whitfield", "Priority": "High"},
        {"Event": "Ashfield Research Payments & Fintech Conference", "Type": "Conference",
         "Date": _d(34), "Location": "New York, NY", "Organizer": "Ashfield Research",
         "Status": "Invited — pending confirmation", "Deadline": _d(12),
         "Notes": "1x1 track; Ellis Grant hosting.", "Source": "Analyst invite",
         "Attending": "Marcus Ellery, Dana Whitfield", "Priority": "High"},
        {"Event": "Denby Small-Cap Growth Forum", "Type": "Conference", "Date": _d(56),
         "Location": "Boston, MA", "Organizer": "Denby Securities", "Status": "Confirmed",
         "Deadline": _d(28), "Notes": "Fireside + six 1x1s.", "Source": "Analyst invite",
         "Attending": "Priya Raman, Dana Whitfield", "Priority": "Medium"},
        {"Event": "Chicago Institutional NDR", "Type": "NDR", "Date": _d(47),
         "Location": "Chicago, IL", "Organizer": "Halbrook Securities",
         "Status": "Needs to be Scheduled", "Deadline": _d(25),
         "Notes": "Four accounts identified in the region; sequencing around the fall swing.",
         "Source": "Internal", "Attending": "Marcus Ellery, Dana Whitfield", "Priority": "High"},
        {"Event": "Q3 2026 Earnings Call", "Type": "Earnings", "Date": _d(112),
         "Location": "Virtual / Conference Bridge", "Organizer": "Northlake Internal",
         "Status": "Not yet contacted", "Deadline": _d(111), "Notes": "Date provisional.",
         "Source": "Internal", "Attending": "Management + IR", "Priority": "Medium"},
    ], client_id=CID)
    print("[demo] seeded 5 calendar events (earnings, conferences, an NDR to schedule)")

    # 10. Activity ledger — the platform's own record of work done, so Today reads
    # "N tasks automated today" instead of "no activity logged yet".
    from core import activity_log
    for et, ent, det in [
        ("email_sent", "Ellis Grant", {"launched_from": "Consensus · model request"}),
        ("email_sent", "Marta Reyes", {"launched_from": "Consensus · model request"}),
        ("model_ingested", "Calder & Co.", {"period": "Q2 2026E"}),
        ("model_ingested", "Brightwater Equity", {"period": "Q2 2026E"}),
        ("signal_resolved", "guidance_gap", {"note": "CFO briefed; guidance language tightened"}),
        ("meeting_logged", "Halewood Capital Management", {"type": "1x1 — Investor Conference"}),
        ("ndr_trip_logged", "New York, NY", {"meetings": 6}),
        ("report_generated", "Quarterly Board Package", {"format": "pdf"}),
    ]:
        try:
            activity_log.log_event(et, entity=ent, client_id=CID, **det)
        except Exception as exc:
            print(f"   (activity_log {et} skipped: {exc})")
    print("[demo] seeded 8 activity-ledger events")

    # 11. IR Inbox — a freshly arrived analyst model awaiting review, so the inbox demo shows the
    # parse -> confirm flow and its attachment pulls up a clean, legible model (not a binary dump).
    from core import demo_model
    seed_inbox_model(CID)
    print(f"[demo] seeded 1 pending analyst-model inbox item + document ({demo_model.FILENAME})")
    seed_ndr_replies(CID)
    print("[demo] seeded 3 filed NDR-invite replies in the IR Inbox (confirm / reschedule / pass)")
    _n_cur, _n_pri = seed_nobo(CID)
    print(f"[demo] seeded 2 NOBO pulls (current {_n_cur} holders, prior {_n_pri}) — inst/retail mix, "
          "13D/G thresholds, tracked cross-ref, and flow for the compare")
    seed_financials(CID)
    seed_targeting_extras(CID)
    seed_ndr_crm_extras(CID)
    seed_lighthouse(CID)
    # Analyst research notes (PDF) into the documents store, so IR Inbox → Research Library shows a
    # believable mix alongside the seeded models. Idempotent; safe to re-run.
    try:
        from scripts.seed_research_library import dedupe_documents, seed_research_inbox, seed_research_library
        _n = seed_research_library(CID)
        _d = dedupe_documents(CID)
        _q = seed_research_inbox(CID)
        print(f"  seeded {_n} research note(s); removed {_d} duplicate doc(s) from the Research Library; "
              f"enqueued {_q} research_note inbox item(s) (lights up loop-readiness Research stage)")
    except Exception as _e:
        print(f"  [warn] research-library seed skipped: {_e}")
    # Earnings cycle: beat/miss history + summarized prior-quarter transcript so the Earnings tabs
    # (Prior Qtr Review, Consensus Tracker, Call Transcripts) tell a story instead of sitting empty.
    try:
        from scripts.seed_earnings_demo import seed_earnings_demo
        _e = seed_earnings_demo(CID)
        print(f"  seeded earnings demo: {_e['surprises']} surprise quarters, {_e['transcripts']} transcripts, "
              f"{_e['script_sections']} NLKP script sections")
    except Exception as _ex:
        print(f"  [warn] earnings-demo seed skipped: {_ex}")
    # Earnings PRESS RELEASES — the OTHER place guidance lives (formal, verbatim), so the prior guide is
    # authoritative and this quarter's decision can be verified consistent across release AND transcript.
    try:
        from scripts.seed_press_release import seed_press_release
        _pr = seed_press_release(CID)
        print(f"  seeded {_pr} earnings press release(s) (formal guidance, matches the transcripts)")
    except Exception as _ex:
        print(f"  [warn] press-release seed skipped: {_ex}")

    # NOTE: deliberately NOT seeded — no integration exists, so the UI should keep
    # saying so: earnings-call listen duration, IR website visit counts, short
    # interest, activist screening. See this module's docstring.
    print("[demo] (left unseeded on purpose: call-listen, IR web visits, short interest)")
    print("\nDone. Switch to 'Northlake Payments, Inc.' in the client picker and re-shoot.")


if __name__ == "__main__":
    seed()
