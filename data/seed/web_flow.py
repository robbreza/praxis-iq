"""data/seed/web_flow.py — ILLUSTRATIVE IR-website visitor data for the demo tenant
ONLY (Northlake Payments, client_id "demo").

Representative, not real: it exists so the web-flow capability (who DOWNLOADS material
vs who just READS) is demonstrable in the demo, and so download-intent visibly folds
into the investor Engagement Score. core/web_flow.py serves it ONLY for client_id
"demo"; every real client shows a Waiting signal until a genuine web-analytics export
is uploaded — no fabricated numbers. See [[illustrative-demo-tenant]].

The holder orgs here match the demo's fictional 13F institution names (Halewood,
Corveth, Longmere…) on purpose, so the web-flow → engagement-score join lands. Two
deliberately TINY holders (Longmere, Aldergate) are heavy downloaders — that's the
showcase: a small position actively pulling the deck/model scores as engaged, which
raw position size alone would miss. Non-holder prospect names are fictional.

Assets use the names core.web_flow.ASSET_INTENT scores:
Earnings model / Investor deck / 10-Q / 10-K / Fact sheet / Transcript / Press release.
"""

# org, category, is_holder, pages, minutes, visits, last_visit, downloads[]
_DEMO_NLKP = [
    # ── Holders actively pulling diligence material (download-weighted intent) ──────
    {"org": "Halewood Capital Management", "category": "Existing Holder", "is_holder": True,
     "pages": 9, "minutes": 24, "visits": 3, "last_visit": "2026-08-03",
     "downloads": ["Investor deck", "Earnings model", "10-Q"]},
    {"org": "Corveth Advisors", "category": "Existing Holder", "is_holder": True,
     "pages": 6, "minutes": 15, "visits": 2, "last_visit": "2026-08-01",
     "downloads": ["Investor deck", "Earnings model"]},
    # The showcase: TINY positions doing real diligence — the fold boosts them.
    {"org": "Longmere Trust Company", "category": "Existing Holder", "is_holder": True,
     "pages": 7, "minutes": 18, "visits": 2, "last_visit": "2026-08-02",
     "downloads": ["Investor deck", "Earnings model"]},
    {"org": "Aldergate Asset Management", "category": "Existing Holder", "is_holder": True,
     "pages": 5, "minutes": 12, "visits": 2, "last_visit": "2026-07-31",
     "downloads": ["Earnings model", "10-Q"]},

    # ── Holders reading, not (yet) downloading ─────────────────────────────────────
    {"org": "Kestrel Ridge Capital", "category": "Existing Holder", "is_holder": True,
     "pages": 6, "minutes": 16, "visits": 2, "last_visit": "2026-07-30", "downloads": []},
    {"org": "Ellinwood Advisors", "category": "Existing Holder", "is_holder": True,
     "pages": 4, "minutes": 11, "visits": 1, "last_visit": "2026-07-29", "downloads": []},
    {"org": "Sandhurst Equity Partners", "category": "Existing Holder", "is_holder": True,
     "pages": 5, "minutes": 13, "visits": 1, "last_visit": "2026-07-28", "downloads": []},

    # ── Non-holder prospects downloading — the hot prospects the view surfaces ──────
    {"org": "Tamarack Peak Capital", "category": "Known Fund", "is_holder": False,
     "pages": 7, "minutes": 19, "visits": 2, "last_visit": "2026-08-02",
     "downloads": ["Investor deck", "Earnings model"]},
    {"org": "Fenwick Cove Partners", "category": "Known Fund", "is_holder": False,
     "pages": 5, "minutes": 12, "visits": 2, "last_visit": "2026-08-01",
     "downloads": ["Earnings model", "10-Q"]},
    {"org": "Holloway Bridge Advisors", "category": "Call Attendee", "is_holder": False,
     "pages": 4, "minutes": 9, "visits": 1, "last_visit": "2026-07-30",
     "downloads": ["Fact sheet", "Investor deck"]},
    {"org": "New — unidentified (Chicago)", "category": "New — unidentified", "is_holder": False,
     "pages": 5, "minutes": 13, "visits": 2, "last_visit": "2026-08-02",
     "downloads": ["Investor deck"]},

    # ── Engaged reader, unknown ────────────────────────────────────────────────────
    {"org": "New — unidentified (Boston)", "category": "New — unidentified", "is_holder": False,
     "pages": 8, "minutes": 21, "visits": 1, "last_visit": "2026-07-31", "downloads": []},

    # ── Browsers (light touch — small holder / market maker / retail) ──────────────
    {"org": "Straiton Global Investors", "category": "Existing Holder", "is_holder": True,
     "pages": 2, "minutes": 3, "visits": 1, "last_visit": "2026-07-27", "downloads": []},
    {"org": "Redstone Securities (market maker)", "category": "Known Fund", "is_holder": False,
     "pages": 2, "minutes": 2, "visits": 1, "last_visit": "2026-07-29", "downloads": []},
    {"org": "New — unidentified (New York)", "category": "New — unidentified", "is_holder": False,
     "pages": 2, "minutes": 4, "visits": 1, "last_visit": "2026-08-03", "downloads": []},
    {"org": "Retail (aggregated)", "category": "New — unidentified", "is_holder": False,
     "pages": 3, "minutes": 5, "visits": 4, "last_visit": "2026-08-03", "downloads": []},
]


def get_seed_web_flow(client_id="demo"):
    """Illustrative visitor rows for the demo tenant. Returns copies so callers can't
    mutate the module-level seed."""
    return [dict(v) for v in _DEMO_NLKP]
