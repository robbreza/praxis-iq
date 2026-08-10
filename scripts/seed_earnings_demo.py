"""
scripts/seed_earnings_demo.py — populate the illustrative demo's Earnings Cycle so every tab tells a
coherent story. Fictional issuer NLKP (Northlake Payments); illustrative only. Idempotent.

Seeds three things:
  1. earnings_surprise_log.json — NLKP's beat/miss track record (Consensus Tracker tab). Without it the
     tab falls back to a hardcoded USIO default (wrong data for the demo).
  2. The Q1 2026 call transcript (Call Transcripts tab) with its AI-summary fields written directly —
     deterministic, no LLM call. The full_text is assembled from speaker/body turns with timestamps at a
     realistic ~130 wpm, in the vendor format core/morning_after.py parses, so the Morning After tab's
     section-timing works off the tape (not an estimate). Only Q1 is ingested — the Q2 call hasn't
     happened (it lives in Script Generation as a draft), so any Q2 "transcript" stub is deleted.
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

# ── 2. Call transcript ───────────────────────────────────────────────────────────────────────────────
# Stored as (speaker, body) turns; _assemble() stamps each with an HH:MM:SS timestamp derived from the
# body's word count at ~130 wpm (operator turns get a short fixed duration), so the Morning After tab's
# section timing AND its wpm readout are internally consistent and realistic. The header format
# ("Speaker, Role\nHH:MM:SS\nbody") is exactly what core/morning_after.py's _TURN regex matches.
_WPM = 130

_Q1_TURNS = [
    ("Operator",
     "Good afternoon, and welcome to Northlake Payments' first quarter fiscal 2026 earnings conference "
     "call. All participants will be in a listen-only mode. After today's presentation, there will be an "
     "opportunity to ask questions. Please note this event is being recorded. I would now like to turn the "
     "conference over to Dana Whitfield, Director of Investor Relations. Please go ahead."),

    ("Dana Whitfield, Investor Relations",
     "Thank you, operator, and good afternoon, everyone. Welcome to Northlake Payments' first quarter 2026 "
     "earnings call. With me today are Marcus Ellery, our Chief Executive Officer, and Priya Raman, our "
     "Chief Financial Officer. Marcus will begin with a review of the quarter and our strategy, Priya will "
     "walk through the financial results and our outlook, and then we'll open the line for your questions. "
     "Before we begin, I'd like to remind everyone that today's call contains forward-looking statements "
     "within the meaning of the Private Securities Litigation Reform Act. These statements are subject to "
     "risks and uncertainties that could cause actual results to differ materially, and we refer you to the "
     "risk factors in our most recent SEC filings. We will also discuss certain non-GAAP financial "
     "measures; a reconciliation to the most comparable GAAP measures is available in today's press "
     "release, which is posted to the investor relations section of our website. With that, I'll turn the "
     "call over to Marcus."),

    ("Marcus Ellery, Chief Executive Officer",
     "Thank you, Dana, and good afternoon, everyone. Thank you all for joining us. The first quarter was a "
     "record for Northlake across the metrics that matter most to this business. Total revenue of $25.3 "
     "million grew 19% year over year and came in above the high end of the guidance range we gave you in "
     "February. Adjusted EPS was $0.12, up from $0.03 in the prior-year quarter. But as I told our team the "
     "morning the quarter closed, the number I care most about is not the revenue line — it's the mix. "
     "Integrated payments volume grew 28% year over year, and as that mix continues to build, our net "
     "take-rate steps up. We are converting software partners into full payments relationships faster than "
     "we modeled at the start of the year, and that is the single most important trend in our story. "
     "Let me put the quarter in context, because I think the transformation of this company is still "
     "underappreciated. Two years ago, Northlake was, for all practical purposes, a payment processor "
     "competing on price. We moved transactions, we charged a spread, and we lived and died on volume. "
     "Today we are an embedded-payments platform for vertical software companies. When one of our ISV "
     "partners — a practice-management system, a field-services platform, a nonprofit CRM — turns on "
     "integrated payments, we don't simply process a transaction. We become the payments infrastructure "
     "inside their product. We own the acquiring relationship, we manage the underwriting and risk, and we "
     "keep the net spread. That is a structurally better business than the one we ran two years ago, and "
     "the first quarter is the clearest evidence yet that the strategy is compounding. "
     "I'll walk you through the three drivers of the quarter. The first is PayFac attach, which is the core "
     "of everything we do. New-partner onboarding accelerated — we brought on a record number of new "
     "integrated partners in the quarter — and just as importantly, attach among our existing partners "
     "improved as those partners matured on the platform. This is the flywheel we've described: a partner "
     "integrates, their merchants adopt payments, adoption deepens over the following quarters, and our "
     "revenue per partner climbs without us adding a single new logo. The installed base is doing more of "
     "the work every quarter. The second driver is retention. Net revenue retention was above 110% for the "
     "fourth consecutive quarter. In this business, retention is destiny — the cost to acquire a partner is "
     "real, and the return on that acquisition is entirely a function of how long they stay and how much "
     "they grow. Above-110% net retention means our existing book is expanding faster than any churn, and "
     "our churn stays low because, frankly, once payments are embedded in a partner's workflow, we are very "
     "difficult to remove. The third driver is discipline. We delivered this record quarter while expanding "
     "margins, which Priya will detail in a moment. We are not buying growth, we are not subsidizing "
     "merchants to inflate a headline, and we are not chasing gross volume for its own sake. Every dollar of "
     "revenue growth this quarter carried incremental margin, because the attach motion has software-like "
     "economics. "
     "Before I hand it to Priya, a word on where we go from here. Our strategy has not changed and it will "
     "not change: we are focused on the attach motion, because that is where durable, recurring economics "
     "live. We will keep investing in partner onboarding and in the platform capabilities that make us the "
     "easiest payments provider to turn on and the hardest to turn off. We see a long runway in our "
     "existing verticals and a real opportunity in adjacent ones, and the pipeline of ISV partners we're in "
     "conversations with is the strongest it has been in the company's history. I am more confident in this "
     "model today than at any point since we began the transformation. With that, I'll turn it over to "
     "Priya to walk through the financials and our outlook."),

    ("Priya Raman, Chief Financial Officer",
     "Thank you, Marcus, and good afternoon, everyone. I'll cover the first-quarter results and then our "
     "outlook. First-quarter net revenue was $25.3 million, up 19% year over year and above the high end of "
     "our $24.6 to $25.0 million guidance range. The growth was led by integrated payments, where volume "
     "grew 28% and net revenue grew faster than volume as take-rate expanded. Our transaction-based revenue "
     "grew in the mid-single digits, consistent with our expectation that the legacy processing book grows "
     "slowly while the integrated book compounds. Adjusted EPS was $0.12, ahead of the $0.09 consensus and "
     "up from $0.03 a year ago. "
     "Turning to margins. Gross profit margin expanded 180 basis points year over year, to the high-fifties, "
     "as the revenue mix shifted toward integrated acquiring, which carries a structurally higher margin "
     "than our legacy processing. Adjusted EBITDA was $5.1 million, a margin of roughly 20%, up more than "
     "300 basis points year over year, as we held operating expense growth well below revenue growth. And we "
     "generated positive free cash flow in the quarter, which funds the partner-onboarding investment Marcus "
     "described without drawing on the balance sheet. We ended the quarter with $41 million in cash and no "
     "debt. "
     "Let me address prepaid float directly, because I know it's a topic for several of you. Float balances "
     "were stable in the quarter despite the rate environment, and the contribution to revenue was "
     "consistent with prior quarters. To be very clear: we do not model float as a growth driver, it is a "
     "small and stable contributor to the P&L, and the growth in this business is the attach motion, full "
     "stop. If rates normalize from here, the sensitivity to our model is modest and well within the range "
     "we plan for. "
     "Now to guidance. For the second quarter, we expect net revenue of $25.6 to $26.0 million. For the "
     "full year, we are reiterating our guidance of $103 to $105 million in net revenue and adjusted EBITDA "
     "margin of approximately 20%. Given the first-quarter trajectory, we see the bias to the upside on the "
     "full-year range, and we expect the second half to be stronger than the first as new-partner go-lives "
     "weight toward the back half. We are not raising the formal range today — it is early in the year — but "
     "I want to be direct that the momentum we are seeing supports the high end. With that, operator, we are "
     "ready to open the call for questions."),

    ("Operator",
     "Thank you. We will now begin the question-and-answer session. Our first question comes from Ellis "
     "Grant with Ashfield Research. Please go ahead."),

    ("Ellis Grant, Ashfield Research",
     "Good afternoon, and congratulations on the quarter. Marcus, can you frame the sustainability of the "
     "PayFac attach rate? Is the 28% a new baseline we should carry forward, or is there an element of "
     "pull-forward in the number we should be aware of?"),

    ("Marcus Ellery, Chief Executive Officer",
     "Thanks, Ellis. We see it as structural, not a pull-forward. There are two things supporting it. "
     "First, the pipeline of new ISV partners is strong, so new-logo attach continues. But second, and more "
     "importantly, attach improves as each existing partner matures on the platform — their merchants keep "
     "adopting payments over the quarters following integration. So even if we brought on zero new partners, "
     "the installed base would keep contributing attach growth. That's the durability. We'd rather "
     "under-promise on the exact percentage, because it will move quarter to quarter, but the trend line is "
     "real and we expect it to persist."),

    ("Ellis Grant, Ashfield Research",
     "That's helpful. And a follow-up for Priya — can you give us the gross-to-net revenue bridge versus the "
     "net-revenue peers? It's the piece the buy-side keeps asking us about."),

    ("Priya Raman, Chief Financial Officer",
     "Fair question, and we're going to put a clean bridge in the deck this quarter so it's easy to follow. "
     "The short version is this: benchmark us on gross profit, not gross revenue — that's where the model's "
     "economics show up. Because we report net revenue rather than gross, a simple revenue-multiple "
     "comparison to the gross-revenue names understates us. On a gross-profit basis, we compare very "
     "favorably to the net-revenue peers you're thinking of, and the bridge we'll publish walks from our "
     "reported net revenue to gross profit so you can line us up apples-to-apples. I think it will make the "
     "comparison obvious."),

    ("Operator",
     "The next question comes from Owen Pike with Westmark Partners. Please go ahead."),

    ("Owen Pike, Westmark Partners",
     "Thanks for taking my question. Priya, staying on prepaid float — if rates normalize from here, how "
     "much is actually at risk to the model, and how should we think about it in our estimates?"),

    ("Priya Raman, Chief Financial Officer",
     "It's limited, Owen. Float is a small and stable contributor and we don't guide to it. If rates move a "
     "hundred basis points, the impact to full-year revenue is modest — low single-digit millions at the "
     "extreme — and it's well within the range we plan for in our guidance. I'd encourage you not to model "
     "float as a swing factor, because in our P&L it isn't one. The growth story is attach, and attach is "
     "not rate-sensitive."),

    ("Operator",
     "The next question comes from Marta Reyes with Denby Securities. Please go ahead."),

    ("Marta Reyes, Denby Securities",
     "Congrats on the print. Marcus, on capital allocation — with free cash flow turning positive, how are "
     "you thinking about reinvestment versus returning capital, and does M&A factor in at all?"),

    ("Marcus Ellery, Chief Executive Officer",
     "Right now the highest-return use of our capital is investing in partner onboarding and in the "
     "platform, because the attach motion compounds — a dollar we put into bringing on and ramping partners "
     "returns for years. So that's the priority. We'll be disciplined; we have no plans to chase M&A for "
     "scale, and we're not interested in buying revenue that doesn't fit the attach model. If we generate "
     "cash beyond what the organic opportunity can absorb, we'll evaluate returning it to shareholders, but "
     "we're not there yet, and the bar for any alternative use is the return we get on the attach motion."),

    ("Operator",
     "The next question comes from Neil Barrow with Calder and Company. Please go ahead."),

    ("Neil Barrow, Calder & Co.",
     "Thanks. Can you size the ISV pipeline heading into the second half, and help us understand the cadence "
     "of new-partner go-lives — is it linear, or should we expect it back-half weighted?"),

    ("Priya Raman, Chief Financial Officer",
     "The pipeline is the strongest it's been, and I'd point you to the back half for the cadence. We won't "
     "give a specific partner-count number, but go-lives tend to be back-half weighted because partners "
     "take a quarter or two to finish integration and testing before they turn on. That timing is a big part "
     "of why we're pointing to a stronger second half and why we see the bias to the upside on the full-year "
     "range. As those partners go live, they contribute attach growth into next year as well."),

    ("Operator",
     "The next question comes from Sara Lindqvist with Brightwater Equity. Please go ahead."),

    ("Sara Lindqvist, Brightwater Equity",
     "Thank you. A bigger-picture question for Marcus — what is the competitive moat here? What stops a "
     "larger processor from replicating the attach motion with your partners?"),

    ("Marcus Ellery, Chief Executive Officer",
     "It's integration depth and switching cost, Sara. Once payments are embedded in a partner's software "
     "workflow — the way funds move, the way reconciliation works, the way their merchants get onboarded — "
     "ripping that out is painful and risky for the partner, and it puts their own merchant relationships at "
     "risk. We win by being the easiest to turn on and the least likely to be turned off. A larger "
     "processor can match us on price, but price isn't what keeps a partner; the embedded workflow and the "
     "trust that we'll manage the risk correctly is what keeps them. Scale doesn't replicate that — depth of "
     "integration and years of a working relationship do."),

    ("Operator",
     "This concludes our question-and-answer session. I would like to turn the conference back over to "
     "Marcus Ellery for any closing remarks."),

    ("Marcus Ellery, Chief Executive Officer",
     "Thank you all for joining us today. The first quarter was a record, the attach strategy is clearly "
     "working, and we are carrying real momentum into the second half of the year. Thank you to our team and "
     "to our partners for the quarter, and thank you to our shareholders for your continued support. We look "
     "forward to updating you on our second quarter. Have a good evening."),

    ("Operator",
     "The conference has now concluded. Thank you for attending today's presentation. You may now disconnect."),
]


def _assemble(turns, wpm=_WPM):
    """Join (speaker, body) turns into the vendor transcript format morning_after parses, stamping each
    turn with an HH:MM:SS timestamp so the elapsed time matches the body length at ~`wpm` (operator
    turns get a short fixed duration). Deterministic — same input, same tape."""
    lines, t = [], 0
    for spk, body in turns:
        lines.append(f"{spk}\n{t//3600:02d}:{(t % 3600)//60:02d}:{t % 60:02d}\n{body}")
        if spk.startswith("Operator"):
            dur = 60 if t == 0 else 18          # intro runs longer; transitions are brief
        else:
            dur = max(20, round(len(body.split()) / wpm * 60))
        t += dur
    return "\n\n".join(lines)


_TRANSCRIPTS = {
    "Q1 2026": {
        "call_date": "2026-05-13",
        "full_text": _assemble(_Q1_TURNS),
        "ai_summary": ("Record Q1: net revenue $25.3M (+19% YoY, above the high end of guidance) and adj. "
                       "EPS $0.12 vs $0.09 consensus. The beat was driven by PayFac attach (integrated "
                       "volume +28%) lifting net take-rate, with 180 bps of gross-margin expansion and "
                       "adjusted EBITDA margin near 20%. Management framed attach as structural, not a "
                       "pull-forward, guided Q2 net revenue to $25.6–26.0M, reiterated the $103–105M FY "
                       "range with an explicit upside bias into H2, and pushed back on prepaid-float "
                       "concerns (stable balances, not modeled as a growth driver)."),
        "key_quotes": [
            {"quote": "Integrated payments volume grew 28%, and as that mix continues to build, our net take-rate steps up.",
             "speaker": "Marcus Ellery, CEO"},
            {"quote": "We are reiterating our guidance and, given the first-quarter trajectory, we see the bias to the upside on the full-year range.",
             "speaker": "Priya Raman, CFO"},
            {"quote": "Benchmark us on gross profit, not gross revenue — that's where the model's economics show up.",
             "speaker": "Priya Raman, CFO"},
        ],
        "guidance_language": [
            "Q2 net revenue guided to $25.6–26.0M.",
            "Reiterated full-year FY2026 net revenue of $103–105M and ~20% adj. EBITDA margin.",
            "Explicit upside bias to the full-year range; second half expected stronger than the first.",
            "Do not model prepaid float as a growth driver — modest, well-planned rate sensitivity.",
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
}
_STALE_TRANSCRIPTS = ["Q2 2026"]   # a future call has no transcript — remove any seeded stub


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
    for quarter in _STALE_TRANSCRIPTS:                 # a future call has no transcript
        try:
            transcripts.delete_transcript(quarter, client_id=cid)
        except Exception:
            pass
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
    print(f"Earnings demo seeded: {out['surprises']} surprise quarters, {out['transcripts']} transcript(s).")
