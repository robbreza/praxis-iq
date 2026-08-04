"""data/seed/web_flow.py — ILLUSTRATIVE IR-website visitor data for the demo tenant
ONLY (Northlake Payments, client_id "demo").

This is representative, not real: it exists so the web-flow capability (who DOWNLOADS
material vs who just READS) is demonstrable in the demo. core/web_flow.py serves it
ONLY for client_id "demo"; every real client shows a Waiting signal until a genuine
web-analytics export is uploaded — no fabricated numbers. See [[illustrative-demo-tenant]].

Assets use the names core.web_flow.ASSET_INTENT scores:
Earnings model / Investor deck / 10-Q / 10-K / Fact sheet / Transcript / Press release.
"""

# org, category, is_holder, pages, minutes, visits, last_visit, downloads[]
_DEMO_NLKP = [
    # ── High-intent downloaders ────────────────────────────────────────────────────
    {"org": "Wellington Management", "category": "Existing Holder", "is_holder": True,
     "pages": 9, "minutes": 24, "visits": 3, "last_visit": "2026-08-03",
     "downloads": ["Investor deck", "Earnings model", "10-Q"]},
    {"org": "Kayne Anderson Rudnick", "category": "Known Fund", "is_holder": False,
     "pages": 7, "minutes": 19, "visits": 2, "last_visit": "2026-08-02",
     "downloads": ["Investor deck", "Earnings model"]},
    {"org": "Cannell Capital", "category": "Known Fund", "is_holder": False,
     "pages": 5, "minutes": 12, "visits": 2, "last_visit": "2026-08-01",
     "downloads": ["Earnings model", "10-Q"]},
    {"org": "Fidelity — Small Cap Discovery", "category": "Existing Holder", "is_holder": True,
     "pages": 6, "minutes": 15, "visits": 2, "last_visit": "2026-07-31",
     "downloads": ["Investor deck", "Fact sheet"]},
    {"org": "Meridian Microcap Partners", "category": "Known Fund", "is_holder": False,
     "pages": 4, "minutes": 9, "visits": 1, "last_visit": "2026-07-30",
     "downloads": ["Fact sheet", "Investor deck"]},
    {"org": "Granite Point Capital", "category": "Call Attendee", "is_holder": False,
     "pages": 3, "minutes": 8, "visits": 1, "last_visit": "2026-07-29",
     "downloads": ["Earnings model"]},
    # A juicy unknown — someone doing real diligence but not yet identified.
    {"org": "New — unidentified (Chicago)", "category": "New — unidentified", "is_holder": False,
     "pages": 5, "minutes": 13, "visits": 2, "last_visit": "2026-08-02",
     "downloads": ["Investor deck"]},

    # ── Engaged readers (browsing hard, no downloads yet) ──────────────────────────
    {"org": "T. Rowe Price", "category": "Existing Holder", "is_holder": True,
     "pages": 6, "minutes": 16, "visits": 2, "last_visit": "2026-08-01", "downloads": []},
    {"org": "Royce Investment Partners", "category": "Known Fund", "is_holder": False,
     "pages": 7, "minutes": 18, "visits": 2, "last_visit": "2026-07-30", "downloads": []},
    {"org": "New — unidentified (Boston)", "category": "New — unidentified", "is_holder": False,
     "pages": 8, "minutes": 21, "visits": 1, "last_visit": "2026-07-31", "downloads": []},
    {"org": "Eagle Asset Management", "category": "Existing Holder", "is_holder": True,
     "pages": 4, "minutes": 11, "visits": 1, "last_visit": "2026-07-28", "downloads": []},

    # ── Browsers (light touch — passive/index/retail/market-maker) ─────────────────
    {"org": "BlackRock (index)", "category": "Existing Holder", "is_holder": True,
     "pages": 2, "minutes": 3, "visits": 1, "last_visit": "2026-07-27", "downloads": []},
    {"org": "Vanguard (index)", "category": "Existing Holder", "is_holder": True,
     "pages": 1, "minutes": 2, "visits": 1, "last_visit": "2026-07-26", "downloads": []},
    {"org": "Susquehanna (market maker)", "category": "Known Fund", "is_holder": False,
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
