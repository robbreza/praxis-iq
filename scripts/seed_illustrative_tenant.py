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

from core.security import load_environment  # noqa: E402

load_environment()

from config.client_config import reload_registry  # noqa: E402
from core import client_store, db  # noqa: E402

CID = "demo"
TICKER = "NLKP"
CUSIP = "66512X104"          # invented
TODAY = datetime.now()
FILE_DATE = TODAY.strftime("%d-%b-%Y").upper()

# ── The issuer ───────────────────────────────────────────────────────────────
# A micro-cap payments processor: the same shape the platform's peer/comp logic
# is tuned for, so every screen behaves exactly as it does for a real client.
RECORD = {
    "ticker": TICKER,
    "name": "Northlake Payments, Inc.",
    "exchange": "NASDAQ",
    "email_domain": "northlakepay.com",
    "sector": "Fintech / Payments",
    "market_cap_m": 78,
    "ev_m": 91,
    "last_price": 2.84,
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
        {"name": "Ellis Grant", "firm": "Ashfield Research", "pt": 5.50, "rating": "Buy",
         "email": "egrant@ashfieldresearch.com", "covering": True},
        {"name": "Marta Reyes", "firm": "Denby Securities", "pt": 6.00, "rating": "Buy",
         "email": "mreyes@denbysec.com", "covering": True},
        {"name": "Owen Pike", "firm": "Westmark Partners", "pt": 4.25, "rating": "Hold",
         "email": "opike@westmarkpartners.com", "covering": True},
        # Deliberately no model on file — this is what makes the "we don't guess"
        # discipline visible in a screenshot.
        {"name": "Neil Barrow", "firm": "Calder & Co.", "pt": None, "rating": None,
         "email": "nbarrow@calderco.com", "covering": True},
        {"name": "Sara Lindqvist", "firm": "Brightwater Equity", "pt": None, "rating": None,
         "email": "slindqvist@brightwatereq.com", "covering": True},
    ],
    "peers": [
        {"ticker": "PYRA", "name": "Pyramid Pay Holdings", "ev_rev": 2.9, "tier": "core"},
        {"ticker": "CLRT", "name": "Clarity Payment Systems", "ev_rev": 2.2, "tier": "core"},
        {"ticker": "VNTG", "name": "Vantage Processing Group", "ev_rev": 1.8, "tier": "close"},
    ],
    "earnings": {
        "current_quarter": "Q2 2026",
        "earnings_date": (TODAY + timedelta(days=21)).strftime("%Y-%m-%d"),
        "call_time": "5:00 PM ET",
    },
    "financials": {"last_quarter": "Q1 2026", "last_rev": 28.4, "last_rev_yoy": 11.0},
    "guidance": {"Revenue Est ($M)": 118.0, "EPS Est": 0.24, "EBITDA Est ($M)": 9.1},
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
    ("Kestrel Ridge Capital",        "MINNEAPOLIS",   "MN",   498_000, 1_414_320,    126_000_000,  21),
    ("Thornbury Investment Partners","SAN FRANCISCO", "CA",   455_000, 1_292_200,  1_800_000_000, 155),
    ("Marchmont Capital",            "DALLAS",        "TX",   402_000, 1_141_680,    540_000_000,  72),
    ("Ellinwood Advisors",           "PHILADELPHIA",  "PA",   361_000, 1_025_240,    310_000_000,  55),
    ("Baldwin Creek Capital",        "SEATTLE",       "WA",   318_000,   903_120,    205_000_000,  31),
    ("Longmere Trust Company",       "PASADENA",      "CA",   295_000,   837_800,  6_200_000_000, 940),
    ("Ferncliff Capital Group",      "SHORT HILLS",   "NJ",   271_000,   769_640,    480_000_000,  88),
    ("Sandhurst Equity Partners",    "AUSTIN",        "TX",   244_000,   692_960,    175_000_000,  26),
    ("Windgate Asset Management",    "MILWAUKEE",     "WI",   228_000,   647_520,    390_000_000,  64),
    ("Pemberton Hill Capital",       "WAYZATA",       "MN",   206_000,   585_040,    142_000_000,  22),
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

# Own a PEER but not NLKP → these are what the prospect engine surfaces, and what
# fills the roadshow-metro map with non-holders.
PEER_OWNERS = [
    ("Ridgeline Park Capital",       "NEW YORK",      "NY", "PYRA",  8_100_000,   740_000_000, 96),
    ("Ansonia Wealth Partners",      "WHITE PLAINS",  "NY", "CLRT",  5_400_000,   410_000_000, 71),
    ("Bellhaven Capital Group",      "RYE",           "NY", "PYRA",  4_950_000,   295_000_000, 44),
    ("Coldwater Bay Advisors",       "BOSTON",        "MA", "VNTG",  6_200_000,   880_000_000, 128),
    ("Wellsbrook Investment Mgmt",   "WELLESLEY",     "MA", "PYRA",  3_700_000,   190_000_000, 33),
    ("Lakeshore Meridian Partners",  "CHICAGO",       "IL", "CLRT",  7_450_000, 1_250_000_000, 174),
    ("Oak Brook Equity Advisors",    "OAK BROOK",     "IL", "PYRA",  2_900_000,   165_000_000, 27),
    ("Sturgis Lake Capital",         "ST. PAUL",      "MN", "VNTG",  3_100_000,   118_000_000, 21),
    ("Bryn Tarran Capital",          "PLYMOUTH",      "MN", "PYRA",  2_450_000,    92_000_000, 19),
    ("Presidio Gate Advisors",       "SAN FRANCISCO", "CA", "CLRT",  9_200_000, 2_400_000_000, 305),
    ("Alder Creek Capital",          "PALO ALTO",     "CA", "PYRA",  4_100_000,   340_000_000, 62),
    ("Verdugo Hills Partners",       "SANTA MONICA",  "CA", "VNTG",  3_350_000,   210_000_000, 41),
    ("Trinity Fork Capital",         "DALLAS",        "TX", "PYRA",  5_800_000,   620_000_000, 89),
    ("Bayou Bend Investors",         "HOUSTON",       "TX", "CLRT",  4_600_000,   455_000_000, 77),
    ("Schuylkill Row Advisors",      "PHILADELPHIA",  "PA", "PYRA",  3_900_000,   285_000_000, 54),
    ("Allegheny Point Capital",      "PITTSBURGH",    "PA", "VNTG",  2_750_000,   160_000_000, 30),
    ("Menomonee Valley Capital",     "MILWAUKEE",     "WI", "CLRT",  2_300_000,   135_000_000, 25),
    ("Cascadia Union Partners",      "SEATTLE",       "WA", "PYRA",  4_450_000,   510_000_000, 83),
    ("Kingsway Bay Capital",         "TORONTO",       "A6", "CLRT",  5_100_000,   980_000_000, 142),
    ("Thames Meridian Asset Mgmt",   "LONDON",        "X0", "PYRA",  6_700_000, 1_900_000_000, 268),
    ("Lac Leman Investment Partners","GENEVA",        "V8", "VNTG",  3_050_000,   720_000_000, 110),
    ("Ceresio Vista Privatbank",     "LUGANO",        "V8", "PYRA",  2_150_000,   395_000_000,  66),
]


def _cik_for(filer):
    """Stable synthetic CIK per fund. Needed because position history and contacts
    are both keyed by CIK — with a blank one every holder reads "No history pulled
    yet" and every Engagement Score collapses to the same number."""
    return str(1_400_000 + (abs(hash(filer)) % 500_000))


def _holder(filer, city, state, shares, value, book_total, positions, cusip=CUSIP):
    return {
        "cik": _cik_for(filer), "city": city, "state": state, "cusip": cusip, "filer": filer,
        "value": value, "shares": shares, "filename": "", "accession": "",
        "file_date": FILE_DATE, "book_total": book_total, "size_known": True,
        "book_positions": positions,
    }


def _cache(ticker, holders, cusip=CUSIP):
    return {
        "cusip": cusip, "_error": None, "source": "illustrative-seed",
        "holders": holders, "quarter": "Q1 2026",
        "_fetched_at": TODAY.isoformat(timespec="seconds"),
    }


def seed():
    # 1. Register the tenant
    client_store.upsert_client(CID, RECORD, active=True, merge=False)
    reload_registry()
    print(f"[demo] registered tenant '{CID}' -> {RECORD['name']} ({TICKER})")

    # 2. Our own 13F holder book (drives Target Database + the holder side of the metro map)
    own = [_holder(*h) for h in HOLDERS]
    db.save_json(f"sec_13f_holders_{TICKER}.json", _cache(TICKER, own), client_id=CID)
    print(f"[demo] seeded {len(own)} holders of {TICKER}")

    # 3. Peer books (drives Peer Prospects + the non-holder side of the metro map)
    by_peer = {}
    for filer, city, state, peer, value, book_total, positions in PEER_OWNERS:
        shares = round(value / 3.10)
        by_peer.setdefault(peer, []).append(
            _holder(filer, city, state, shares, value, book_total, positions, cusip=f"{peer}00000")
        )
    for peer, hs in by_peer.items():
        db.save_json(f"sec_13f_holders_{peer}.json", _cache(peer, hs, cusip=f"{peer}00000"), client_id=CID)
        print(f"[demo] seeded {len(hs):>2} holders of peer {peer}")

    # 3b. Position history — the add/trim/new/exit read behind each holder's "Action".
    # Without this every card reads "No history pulled yet".
    directions = ["adding", "trimming", "new", "flat", "adding", "trimming", "flat", "exited"]
    hist = {}
    for i, h in enumerate(HOLDERS):
        filer = h[0]
        d = directions[i % len(directions)]
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
        ("Kestrel Ridge Capital",        68, "NDR meeting", "CFO follow-up required",
         "Sofia Braun", "Asked for time with the CFO on capital allocation."),
        ("Ashcombe Partners",            41, "Intro call", "Neutral — maintain",
         "Rahul Menon", "Introductory; tracking the story, no position change signalled."),
        ("Reddington Asset Management",  55, "Earnings call Q&A", "Flag — possible exit",
         "Dana Kirby", "Pressed on take rate compression twice — watch the next 13F."),
        ("Kestrel Ridge Capital",        12, "1x1 — Investor Conference", "Positive — follow up",
         "Sofia Braun", "Micro-cap specialist, added on the last print."),
    ]
    db.save_json("meeting_log.csv", [
        {"Fund": f, "Date": (TODAY - timedelta(days=ago)).strftime("%Y-%m-%d"), "Type": typ,
         "Attendees": who, "Notes": note, "Outcome": outcome,
         "Logged By": RECORD["ir_contact"]["name"], "Source": "Manual"}
        for f, ago, typ, outcome, who, note in meetings
    ], client_id=CID)
    print(f"[demo] seeded {len(meetings)} logged meetings (varied outcomes → differentiated scores)")

    # 4. Consensus: three analysts with models, two without (the honest gap, on purpose)
    period = "Q2 2026E"
    ests = {}
    for a in RECORD["analysts"]:
        ests[a["firm"]] = {
            "Rating": a["rating"], "Price Target": a["pt"],
            "EPS Est": 0.06 if a["pt"] else None,
            "Revenue Est ($M)": 29.6 if a["pt"] else None,
            "EBITDA Est ($M)": 2.3 if a["pt"] else None,
        }
    db.save_json("period_estimates.json", {period: ests, "FY 2026E": ests}, client_id=CID)
    db.save_json("period_guidance.json", {
        period: {"Revenue Est ($M)": 29.0, "EPS Est": 0.05, "EBITDA Est ($M)": 2.2},
        "FY 2026E": {"Revenue Est ($M)": 118.0, "EPS Est": 0.24, "EBITDA Est ($M)": 9.1},
    }, client_id=CID)
    print("[demo] seeded consensus + guidance (3 of 5 models on file)")

    # 5. Dated analyst rating actions → the real PT drift chart
    actions = [
        ("2026-01-22", "Ashfield Research",  "Buy",  4.75, 5.00, "Raises"),
        ("2026-02-14", "Denby Securities",   "Buy",  5.25, 5.50, "Raises"),
        ("2026-03-19", "Westmark Partners",  "Hold", 4.50, 4.25, "Lowers"),
        ("2026-04-24", "Ashfield Research",  "Buy",  5.00, 5.25, "Raises"),
        ("2026-05-20", "Denby Securities",   "Buy",  5.50, 6.00, "Raises"),
        ("2026-06-18", "Ashfield Research",  "Buy",  5.25, 5.50, "Raises"),
    ]
    db.save_json("rating_actions.json", [
        {"id": f"{TICKER}|{firm}|{d}|{grade}|{pt}", "date": d, "firm": firm, "action": "main",
         "ticker": TICKER, "pt_prior": prior, "to_grade": grade, "from_grade": grade,
         "pt_action": act, "pt_current": pt}
        for d, firm, grade, prior, pt, act in actions
    ], client_id=CID)
    print(f"[demo] seeded {len(actions)} dated rating actions")

    # 6. Earnings script workflow — mid-flight, so readiness shows a real mix
    db.save_json("script_workflow_state.json", {"stages": {
        "cfo_numbers":   {"status": "complete", "completed_at": (TODAY - timedelta(days=6)).strftime("%Y-%m-%d %H:%M"), "notes": ""},
        "ir_review":     {"status": "complete", "completed_at": (TODAY - timedelta(days=3)).strftime("%Y-%m-%d %H:%M"), "notes": ""},
        "exec_review":   {"status": "active",   "completed_at": None, "notes": ""},
        "consolidate":   {"status": "pending",  "completed_at": None, "notes": ""},
        "legal_signoff": {"status": "pending",  "completed_at": None, "notes": ""},
    }}, client_id=CID)
    print("[demo] seeded script workflow (2 of 5 stages complete)")

    # 7. Form 4 insider activity — a real capability (SEC EDGAR), so it may be shown.
    ins = [
        ("Ellery Marcus A",  "Chief Executive Officer", "P", 40_000, 2.71, "2026-06-24"),
        ("Raman Priya",      "Chief Financial Officer", "P", 25_000, 2.68, "2026-06-24"),
        ("Vance Thomas R",   "Chief Revenue Officer",   "P", 15_000, 2.70, "2026-06-25"),
        ("Okafor Adaeze",    "Director",                "P", 12_000, 2.74, "2026-06-26"),
        ("Raman Priya",      "Chief Financial Officer", "F",  4_800, 2.81, "2026-07-01"),
        ("Lindgren Erik",    "Director",                "S", 18_000, 2.92, "2026-07-08"),
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
    prices = {TICKER: (2.84, 2.79, 1.79, 412_000, 355_000),
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

    # NOTE: deliberately NOT seeded — no integration exists, so the UI should keep
    # saying so: earnings-call listen duration, IR website visit counts, short
    # interest, activist screening. See this module's docstring.
    print("[demo] (left unseeded on purpose: call-listen, IR web visits, short interest)")
    print("\nDone. Switch to 'Northlake Payments, Inc.' in the client picker and re-shoot.")


if __name__ == "__main__":
    seed()
