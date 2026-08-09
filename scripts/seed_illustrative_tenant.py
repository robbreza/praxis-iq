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
from datetime import datetime, timedelta

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
    "q2_consensus_rev": 102.0,
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
    "financials": {"last_quarter": "Q1 2026", "last_rev": 98.5, "last_eps": 0.29,
                   "last_ebitda": 13.5, "last_rev_yoy": 11.0},
    "guidance": {"Revenue Est ($M)": 410.0, "EPS Est": 1.30, "EBITDA Est ($M)": 58.0},
    # Guidance-policy inputs for the seasonality-adjusted Decision Engine
    # (core.guidance_engine.seasonal_read). Without these every figure in the
    # engine reads $0.0M. Prior FY2025 quarters sum to $369M; a 10-12% range
    # implies an FY2026 midpoint of ~$410M — matching the guide above. Weights
    # are payments-seasonal (Q4 heaviest) and sum to 1.0.
    "guidance_policy": {
        "prior_fy_label": "FY2025",
        "prior_fy_quarterly_revenue": {"Q1": 86.0, "Q2": 90.0, "Q3": 92.0, "Q4": 101.0},
        "seasonal_weights": {"Q1": 0.233, "Q2": 0.244, "Q3": 0.249, "Q4": 0.274},
        "fy_growth_low": 0.10, "fy_growth_high": 0.12,
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
        ("San Francisco / Bay Area",  96, "Westmark Partners", 4),
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
    # The SHOWCASE Philadelphia NDR, seeded MID-FLIGHT so the invite→response→scheduled loop is
    # demoable out of the box AND survives reseeds (a hand-built NDR is wiped by the next reseed).
    # The "reply came back" is represented by a target's status: Confirmed targets move OUT of the
    # shortlist INTO meetings[] (a filled capacity slot); Invited = awaiting; Declined = a no.
    _ts = TODAY.strftime("%Y-%m-%d %H:%M")
    def _sl(inst, conv, status, city="Philadelphia", bucket="Institutional", peers="CLRT, PYRA, VNTG"):
        r = {"institution": inst, "city": city, "state": "PA", "metro": "Philadelphia, PA",
             "conviction": conv, "peers": peers, "bucket": bucket, "status": status,
             "source": "outbound", "added_at": _ts}
        if status == "invited":  r["contacted_at"] = _ts
        if status == "declined": r["declined_at"] = _ts
        return r
    def _mtg(inst, day, slot, time, score, address):
        return {"institution": inst, "day": day, "slot_index": slot, "time": time, "type": "1x1",
                "format": "In-person", "status": "scheduled", "address": address, "notes": "Owns PYRA, CLRT, VNTG",
                "non_holder": True, "score": score, "contact": "", "confirmed_at": _ts, "source": "outbound"}
    _ndr_trips.append({
        "id": "trip-philly", "name": "Philadelphia Value Corridor NDR", "city": "Philadelphia, PA",
        "metro": "Philadelphia, PA", "sponsor_bank": "Westmark Partners", "sponsor": "Westmark Partners",
        "dates": "TBD", "date": "", "time": "Full day", "ndr_type": "in_person",
        "focus": "Pre-earnings — build anticipation", "team": ["Priya Raman (CFO)", "Marcus Ellery (CEO)"],
        "notes": "Convert the Main Line value corridor; defend Fairmount.", "status": "Planning",
        "debrief": {}, "days": 2, "slots_per_day": 6, "created": TODAY.strftime("%Y-%m-%d"),
        "meetings": [   # confirmed → slotted, WITH street addresses so the itinerary routes real
                        # driving miles/time across the corridor (Philadelphia → Berwyn → Wayne).
            _mtg("Cooke & Bieler L.P.", 1, 0, "9:00 AM", 93, "2001 Market St, Philadelphia, PA 19103"),
            _mtg("Penn Capital Management", 1, 1, "10:30 AM", 92, "1200 Intrepid Ave, Philadelphia, PA 19112"),
            _mtg("Chartwell Investment Partners", 1, 3, "1:00 PM", 92, "1205 Westlakes Dr, Berwyn, PA 19312"),
            # Deliberately tight after Chartwell (only 30 min for a ~5-mi Berwyn→Wayne hop + turnaround)
            # so the itinerary's feasibility check flags a REAL roadshow snag — the "see what happens".
            _mtg("Conestoga Capital Advisors", 1, 4, "1:30 PM", 93, "550 E Swedesford Rd, Wayne, PA 19087"),
        ],
        "shortlist": [  # still in the pipeline: awaiting replies, a decline, and not-yet-contacted
            _sl("Glenmede Investment Management", 92, "invited"),
            _sl("Main Line Wealth Advisors", 88, "invited", city="Radnor", bucket="RIA / wealth", peers="RIA — wealth channel"),
            _sl("abrdn Inc.", 91, "declined", city="Conshohocken"),
            _sl("Brandywine Global Investment Mgmt", 91, "shortlisted"),
            _sl("Fairmount Ridge Capital", None, "shortlisted", bucket="Holder", peers="Holder — defend"),
        ],
    })
    db.save_json("ndr_trips.json", _ndr_trips, client_id=CID)
    print(f"[demo] seeded {len(reqs)} inbound NDR requests + {len(trips)} completed NDR trips "
          f"+ 1 mid-flight Philadelphia NDR (4 confirmed/slotted w/ addresses, 2 invited, 1 declined, 2 shortlisted)")

    # 3d-bis. A few UPCOMING scheduled meetings so the Mobile "On the road → Your meetings" hero
    # has something to lead with in the demo (illustrative buy-side names; the tenant stays fully
    # illustrative). Shape matches investors_page's scheduled_meetings.json record.
    _mtgs = [
        (0,  "10:30", "Blue Harbor Capital",   "Dana Whitfield", "1x1",        "Q3 outlook + take-rate trajectory"),
        (0,  "14:00", "Cedar Grove Advisors",  "Marcus Lin",     "Callback",   "Follow-up on interchange questions"),
        (3,  "09:00", "Westline Asset Mgmt",   "Priya Nair",     "NDR meeting","Intro — new coverage"),
        (8,  "11:15", "Marchmont Capital",     "Tom Alvarez",    "1x1",        "Prepaid float + capital allocation"),
    ]
    db.save_json("scheduled_meetings.json", [
        {"id": f"mtg-{i+1}", "Contact": who, "Firm": firm, "Side": "Buy-side",
         "Date": (TODAY + timedelta(days=d)).strftime("%Y-%m-%d"), "Time": t, "Type": typ,
         "Topic": topic, "Status": "Confirmed", "Priority": "High" if d == 0 else "Medium"}
        for i, (d, t, firm, who, typ, topic) in enumerate(_mtgs)
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
    _est_by_period = {
        "Q2 2026E": {
            "Ashfield Research": (0.33, 102.4, 14.2), "Denby Securities": (0.35, 103.6, 14.8),
            "Westmark Partners": (0.30,  99.8, 13.4), "Calder & Co.":     (0.32, 101.5, 14.0),
            "Brightwater Equity": (0.34, 102.9, 14.5),
        },
        "Q3 2026E": {
            "Ashfield Research": (0.35, 104.6, 14.6), "Denby Securities": (0.37, 105.8, 15.1),
            "Westmark Partners": (0.32, 102.0, 13.8), "Calder & Co.":     (0.34, 103.8, 14.3),
            "Brightwater Equity": (0.36, 105.1, 14.9),
        },
        "Q4 2026E": {
            "Ashfield Research": (0.36, 109.0, 16.6), "Denby Securities": (0.38, 110.2, 17.0),
            "Westmark Partners": (0.34, 107.0, 15.9), "Calder & Co.":     (0.35, 108.3, 16.3),
            "Brightwater Equity": (0.37, 109.6, 16.8),
        },
        "FY 2026E": {
            "Ashfield Research": (1.30, 411.0, 57.5), "Denby Securities": (1.35, 415.0, 59.2),
            "Westmark Partners": (1.26, 406.0, 55.8), "Calder & Co.":     (1.31, 412.0, 57.9),
            "Brightwater Equity": (1.33, 414.0, 58.6),
        },
        "FY 2027E": {
            "Ashfield Research": (1.52, 458.0, 66.0), "Denby Securities": (1.60, 468.0, 68.5),
            "Westmark Partners": (1.46, 450.0, 63.5), "Calder & Co.":     (1.54, 461.0, 66.4),
            "Brightwater Equity": (1.58, 465.0, 67.6),
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
        "Q2 2026E": {"Revenue Est ($M)": 100.0, "EPS Est": 0.32, "EBITDA Est ($M)": 13.8},
        "Q3 2026E": {"Revenue Est ($M)": 103.0, "EPS Est": 0.34, "EBITDA Est ($M)": 14.2},
        # Q4 completes the quarterly book: Q1a 98.5 + Q2 100 + Q3 103 + Q4 108.5 = 410
        # ties the four-quarter roll-up to the FY 2026E guide exactly.
        "Q4 2026E": {"Revenue Est ($M)": 108.5, "EPS Est": 0.35, "EBITDA Est ($M)": 16.5},
        "FY 2026E": {"Revenue Est ($M)": 410.0, "EPS Est": 1.30, "EBITDA Est ($M)": 58.0},
        # FY 2027E: a preliminary long-term framework — low-teens growth off FY26 —
        # so the roll-forward card renders "in line" rather than blank.
        "FY 2027E": {"Revenue Est ($M)": 460.0, "EPS Est": 1.52, "EBITDA Est ($M)": 66.0},
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
    # q2_numbers holds the just-closed Q2 actuals the CFO entered at Stage 1; the
    # Guidance Decision Engine reads rev from here (YTD = Q1 actual + Q2). A Q2 of
    # $102.5M beats the $100M guide and the $102M street, and with YTD running
    # ~1.4pp above seasonal pace the engine lands on "RAISE LOW END" — a clean,
    # positive story. Detail lines sum to revenue so the Stage-1 form reads real.
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

    # NOTE: deliberately NOT seeded — no integration exists, so the UI should keep
    # saying so: earnings-call listen duration, IR website visit counts, short
    # interest, activist screening. See this module's docstring.
    print("[demo] (left unseeded on purpose: call-listen, IR web visits, short interest)")
    print("\nDone. Switch to 'Northlake Payments, Inc.' in the client picker and re-shoot.")


if __name__ == "__main__":
    seed()
