"""scripts/seed_press_release.py — demo earnings PRESS RELEASES for Northlake (NLKP).

Companies state guidance in the press release (formal, verbatim) AND reiterate it on the call. The demo
had only transcripts; this adds the matching releases so guidance is grounded in BOTH artifacts and the
numbers agree across them:
  * Q1 2026 (prior) — REITERATED the $103–105M FY guide. This is the authoritative "prior guidance".
  * Q2 2026 (current draft) — RAISED to $104–106M. What this quarter's script/decision produces.

Full-year guide only (most companies guide one year out); FY+1 is left to the Street. Idempotent.
Run directly or import seed_press_release(cid). Illustrative NLKP — never real.
"""

# quarter -> release record. `guidance` is the structured Outlook block the workflow reads.
_RELEASES = {
    "Q1 2026": {
        "date": "2026-05-13",
        "headline": ("Northlake Payments Reports Record First-Quarter 2026 Results; "
                     "Reiterates Full-Year 2026 Guidance"),
        "subhead": "Net revenue of $25.3 million, up 19% year-over-year and above the high end of guidance",
        "highlights": [
            "Net revenue of $25.3 million, up 19% year-over-year",
            "Integrated payments net revenue up 27%, led by PayFac attach (integrated volume +28%)",
            "Net take-rate expanded to 46 bps; net revenue retention of 112%",
            "Adjusted EBITDA of $5.1 million (~20% margin); adjusted EPS of $0.12 vs. $0.09 consensus",
            "Ended the quarter with $42 million in cash and no debt",
        ],
        "ceo_quote": ("\"Record first quarter. Integrated payments volume grew 28%, and as that mix continues "
                      "to build, our net take-rate steps up — that is the compounding engine of this business.\" "
                      "— Marcus Ellery, Chief Executive Officer"),
        "cfo_quote": ("\"We are reiterating our full-year guidance and, given the first-quarter trajectory, we "
                      "see the bias to the upside on the full-year range.\" — Priya Raman, Chief Financial Officer"),
        "guidance": {
            "statement": ("For full-year 2026, Northlake continues to expect net revenue of $103 million to "
                          "$105 million and an adjusted EBITDA margin of approximately 20%. Given first-quarter "
                          "momentum, the Company sees an upward bias to the range."),
            "fy_low": 103.0, "fy_high": 105.0, "action": "reiterated",
            "ebitda_margin_pct": 20.0, "fiscal_year": "2026",
        },
    },
    "Q2 2026": {
        "date": "2026-08-12",
        "headline": ("Northlake Payments Reports Record Second-Quarter 2026 Results; "
                     "Raises Full-Year 2026 Revenue Guidance"),
        "subhead": "Net revenue of $25.9 million, up 18% year-over-year; raising the full-year range",
        "highlights": [
            "Net revenue of $25.9 million, up 18% year-over-year",
            "Integrated payments led again — integrated volume (TPV) up 27% to $3.42 billion",
            "Net take-rate of 47 bps; net revenue retention held above 110%",
            "Adjusted EBITDA of $5.4 million (~21% margin); adjusted EPS of $0.13",
            "First-half net revenue of $51.2 million, ~49% of the raised full-year midpoint",
        ],
        "ceo_quote": ("\"Another quarter of durable, software-like growth. Attach is structural, not a "
                      "pull-forward, and it continues to lift our net economics.\" — Marcus Ellery, CEO"),
        "cfo_quote": ("\"We are raising the low end of our full-year revenue range, reflecting first-half "
                      "momentum. As a reminder, our second-half year-over-year comparison reflects the unwind "
                      "of a prior-year government payments program; the underlying attach momentum continues.\" "
                      "— Priya Raman, CFO"),
        "guidance": {
            "statement": ("For full-year 2026, Northlake now expects net revenue of $104 million to $106 million "
                          "(previously $103 million to $105 million) and an adjusted EBITDA margin of "
                          "approximately 21%. The second-half year-over-year comparison reflects the unwind of a "
                          "prior-year government payments program; underlying integrated-payments momentum "
                          "continues."),
            "fy_low": 104.0, "fy_high": 106.0, "action": "raise_low",
            "ebitda_margin_pct": 21.0, "fiscal_year": "2026",
        },
    },
}


def _body(rec):
    """Assemble the human-readable release body from the structured fields (what a viewer reads)."""
    lines = [rec["headline"], "", rec.get("subhead", ""), "",
             f"NORTHLAKE, [State] — {rec['date']} — Northlake Payments, Inc. (NLKP) today reported financial "
             "results for the quarter.", "", "First-quarter highlights:" if "First" in rec["headline"]
             else "Second-quarter highlights:"]
    lines += [f"  • {h}" for h in rec["highlights"]]
    lines += ["", rec["ceo_quote"], "", rec["cfo_quote"], "",
              "Outlook", rec["guidance"]["statement"], "",
              "Northlake will host a conference call to discuss these results. This release contains "
              "forward-looking statements subject to risks and uncertainties.",
              "", "Illustrative release prepared for a product demonstration. NLKP is a fictional issuer."]
    return "\n".join(lines)


def seed_press_release(cid="demo"):
    from core import press_release
    made = 0
    existing = press_release.list_releases(cid)
    for q, rec in _RELEASES.items():
        if q in existing:
            continue                              # idempotent
        press_release.save(q, dict(rec, body=_body(rec)), client_id=cid)
        made += 1
    return made


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.client_config import reload_registry, set_active_client_id
    reload_registry()
    set_active_client_id("demo")
    n = seed_press_release("demo")
    print(f"Seeded {n} earnings press release(s) for demo.")
