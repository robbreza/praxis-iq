"""
scripts/seed_earnings_demo.py — populate the illustrative demo's Earnings Cycle so every tab tells a
coherent story. Fictional issuer NLKP (Northlake Payments); illustrative only. Idempotent.

Seeds three things:
  1. earnings_surprise_log.json — NLKP's beat/miss track record (Consensus Tracker tab). Without it the
     tab falls back to a hardcoded USIO default (wrong data for the demo).
  2. Q1 2026 + Q2 2026 call transcripts (Call Transcripts tab) with their AI-summary fields written
     directly — deterministic, no LLM call — matching what transcripts.summarize_transcript would store.
  3. (The Prior Qtr Review lookback reads #1 + the Q1 transcript's summary via an illustrative branch in
     earnings_page.py.)

Run: python scripts/seed_earnings_demo.py   ·   or import seed_earnings_demo(cid) from the main seed.
"""
import json

# ── 1. Surprise / beat-miss history — schema mirrors earnings_page._default_surprises() ──────────────
_SURPRISES = [
    {"quarter": "Q3 2025", "date": "2025-11-06", "rev_actual": 23.2, "rev_consensus": 22.7,
     "rev_whisper": 23.0, "eps_actual": 0.08, "eps_consensus": 0.06, "ah_move": 0.041,
     "implied_move": 0.060, "3day_move": 0.038, "sector_3day": 0.005, "stock_pre_close": 27.10,
     "guidance_vs_embedded": "In-line", "pt_changes": 1, "pt_change_avg": 1.00,
     "notes": "Solid quarter; PayFac attach +21%. Prepaid float stable. Guide reiterated — market wanted "
              "a raise and didn't get one, so a modest AH pop only.",
     "pre_empt_score": 7, "call_score": 58},
    {"quarter": "Q4 2025", "date": "2026-02-19", "rev_actual": 24.6, "rev_consensus": 24.1,
     "rev_whisper": 24.4, "eps_actual": 0.10, "eps_consensus": 0.09, "ah_move": 0.028,
     "implied_move": 0.055, "3day_move": 0.031, "sector_3day": -0.004, "stock_pre_close": 29.40,
     "guidance_vs_embedded": "Above", "pt_changes": 2, "pt_change_avg": 1.50,
     "notes": "Clean beat and an above-consensus FY26 initial guide. Take-rate expansion the story; two "
              "PT raises. Prepaid-float durability the lone pushback in Q&A.",
     "pre_empt_score": 8, "call_score": 63},
    {"quarter": "Q1 2026", "date": "2026-05-13", "rev_actual": 25.3, "rev_consensus": 24.4,
     "rev_whisper": 24.9, "eps_actual": 0.12, "eps_consensus": 0.09, "ah_move": 0.086,
     "implied_move": 0.060, "3day_move": 0.072, "sector_3day": 0.010, "stock_pre_close": 30.20,
     "guidance_vs_embedded": "Above", "pt_changes": 3, "pt_change_avg": 2.00,
     "notes": "Record Q1 — PayFac attach +28% drove the beat and net take-rate stepped up again. Prepaid "
              "float held despite the rate backdrop. Reiterated FY guide with an explicit upside bias into "
              "H2; three PT raises the next morning.",
     "pre_empt_score": 8, "call_score": 66},
]

# ── 2. Call transcripts — full_text (speaker turns) + the summary fields summarize_transcript writes ──
_Q1_TEXT = """Operator: Good afternoon, and welcome to Northlake Payments' first quarter 2026 earnings call. \
I will now turn the call over to Dana Whitfield, Director of Investor Relations.

Dana Whitfield: Thank you, and good afternoon everyone. With me today are Marcus Ellery, our Chief \
Executive Officer, and Priya Raman, our Chief Financial Officer. Before we begin, a reminder that today's \
call contains forward-looking statements. Actual results may differ materially. With that, I'll hand it to Marcus.

Marcus Ellery: Thanks, Dana. Q1 was a record quarter for Northlake. Revenue of $25.3 million was up 19% \
year over year and above the high end of our guidance. The story remains PayFac attach — integrated \
payments volume grew 28%, and as that mix builds, our net take-rate steps up. We are converting software \
partners into payments relationships faster than we modeled.

Priya Raman: Thank you, Marcus. Net revenue was $25.3 million and adjusted EPS was $0.12, ahead of the \
$0.09 consensus. Gross profit margin expanded 180 basis points as the revenue mix shifted toward \
integrated acquiring. On prepaid float — a topic I know is top of mind — balances were stable despite the \
rate environment, and we do not model float as a growth driver. We are reiterating our full-year guidance \
and, given the Q1 trajectory, we see the bias to the upside into the second half.

Operator: We will now begin the question-and-answer session. Our first question comes from Ellis Grant of \
Ashfield Research.

Ellis Grant: Congrats on the quarter. Can you frame the sustainability of the PayFac attach rate — is 28% \
a new baseline or a pull-forward?

Marcus Ellery: Fair question. We see it as structural, not a pull-forward. The ISV pipeline supports it, \
and attach improves as each partner matures on the platform.

Ellis Grant: And the gross-to-net revenue bridge versus the net-revenue peers?

Priya Raman: We'll put a clean bridge in the deck. The short version: benchmark us on gross profit, not \
gross revenue — that's where the model's economics show up.

Operator: Our next question comes from Owen Pike of Westmark Partners.

Owen Pike: On prepaid float — if rates normalize, how much is at risk?

Priya Raman: Limited. Float is a small, stable contributor and we don't guide to it. The growth is the \
attach motion.

Marcus Ellery: Thank you all. We look forward to updating you on our second quarter."""

_Q2_TEXT = """Operator: Good afternoon, and welcome to Northlake Payments' second quarter 2026 earnings \
call. I'll turn it over to Dana Whitfield, Investor Relations.

Dana Whitfield: Thank you. With me are Marcus Ellery, CEO, and Priya Raman, CFO. Today's remarks include \
forward-looking statements subject to risk. Marcus?

Marcus Ellery: Thanks, Dana. This is our upcoming-quarter script draft placeholder for the demo; the Q2 \
call has not yet occurred. Our prepared remarks will lead with PayFac attach durability, the gross-to-net \
bridge we promised last quarter, and prepaid-float context.

Priya Raman: We will present the gross-to-net revenue bridge, reiterate the framework of benchmarking on \
gross profit, and address float sensitivity directly. [Draft — to be finalized on the Script Generation tab.]

Operator: The question-and-answer session will follow management's prepared remarks."""

_TRANSCRIPTS = {
    "Q1 2026": {
        "call_date": "2026-05-13",
        "full_text": _Q1_TEXT,
        "ai_summary": ("Record Q1: net revenue $25.3M (+19% YoY, above the high end of guidance) and adj. "
                       "EPS $0.12 vs $0.09 consensus. The beat was driven by PayFac attach (integrated "
                       "volume +28%) lifting net take-rate, with 180 bps of gross-margin expansion. "
                       "Management framed attach as structural, not a pull-forward, reiterated FY guidance "
                       "with an explicit upside bias into H2, and pushed back on prepaid-float concerns "
                       "(stable balances, not modeled as a growth driver)."),
        "key_quotes": [
            {"quote": "Integrated payments volume grew 28%, and as that mix builds, our net take-rate steps up.",
             "speaker": "Marcus Ellery, CEO"},
            {"quote": "We are reiterating our full-year guidance and… we see the bias to the upside into the second half.",
             "speaker": "Priya Raman, CFO"},
            {"quote": "Benchmark us on gross profit, not gross revenue — that's where the model's economics show up.",
             "speaker": "Priya Raman, CFO"},
        ],
        "guidance_language": [
            "Reiterated full-year FY2026 revenue guidance.",
            "Explicit upside bias to guidance into the second half.",
            "Do not model prepaid float as a growth driver.",
        ],
        "qa_risk_topics": [
            {"severity": "MEDIUM", "topic": "PayFac attach sustainability",
             "why": "Analysts pressed whether 28% attach growth is a durable baseline or a pull-forward."},
            {"severity": "MEDIUM", "topic": "Gross-to-net revenue bridge",
             "why": "Repeated ask for a clean bridge vs net-revenue peers — commitment made to add it to the deck."},
            {"severity": "LOW", "topic": "Prepaid float rate sensitivity",
             "why": "Recurring concern on float durability if rates normalize; management framed exposure as limited."},
        ],
    },
    "Q2 2026": {
        "call_date": None,
        "full_text": _Q2_TEXT,
        "ai_summary": None,     # upcoming call — not yet held; left unsummarized on purpose
        "key_quotes": None, "guidance_language": None, "qa_risk_topics": None,
    },
}


def seed_surprise_log(cid="demo"):
    from core import db
    db.save_json("earnings_surprise_log.json", _SURPRISES, client_id=cid)
    return len(_SURPRISES)


def _write_summary(cid, quarter, rec):
    """Write the AI-summary fields directly (deterministic; no LLM), mirroring the UPDATE in
    transcripts.summarize_transcript."""
    if rec.get("ai_summary") is None:
        return
    from core import db
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        if pg:
            from psycopg2.extras import Json
            cur.execute(
                "UPDATE call_transcripts SET ai_summary=%s, key_quotes=%s, qa_risk_topics=%s, "
                "guidance_language=%s, summarized_at=now() WHERE client_id=%s AND quarter=%s",
                (rec["ai_summary"], Json(rec["key_quotes"]), Json(rec["qa_risk_topics"]),
                 Json(rec["guidance_language"]), cid, quarter))
        else:
            import datetime as _dt
            cur.execute(
                "UPDATE call_transcripts SET ai_summary=?, key_quotes=?, qa_risk_topics=?, "
                "guidance_language=?, summarized_at=? WHERE client_id=? AND quarter=?",
                (rec["ai_summary"], json.dumps(rec["key_quotes"]), json.dumps(rec["qa_risk_topics"]),
                 json.dumps(rec["guidance_language"]), _dt.datetime.now().isoformat(), cid, quarter))
        conn.commit()
    finally:
        conn.close()


def seed_transcripts(cid="demo"):
    from core import transcripts
    for quarter, rec in _TRANSCRIPTS.items():
        transcripts.ingest_transcript(rec["full_text"], quarter, call_date=rec["call_date"],
                                      source="illustrative-demo", client_id=cid)
        _write_summary(cid, quarter, rec)
    return len(_TRANSCRIPTS)


def seed_earnings_demo(cid="demo"):
    n_s = seed_surprise_log(cid)
    n_t = seed_transcripts(cid)
    return {"surprises": n_s, "transcripts": n_t}


if __name__ == "__main__":
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from config.client_config import reload_registry, set_active_client_id
    reload_registry()
    set_active_client_id("demo")
    out = seed_earnings_demo("demo")
    print(f"Earnings demo seeded: {out['surprises']} surprise quarters, {out['transcripts']} transcripts.")
