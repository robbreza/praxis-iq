"""
core/script_scorecard.py — the Script Effectiveness Scorecard, computed live.

Replaces the static Q1 2026 image (a picture of a spreadsheet: "Score 61/100 ·
+24.22% AH reaction · Pre-empt score 8/12") with a scorecard that recomputes from
the actual script on file — the same treatment core/benchmarking_engine.py gave
the Peer Benchmarking report.

WHAT THIS HONESTLY MEASURES, AND WHAT IT DOESN'T
The original scorecard's two headline numbers are NOT derivable from anything we
hold:
  * "Pre-empt score 8/12" needs the call transcript's Q&A topics. There are zero
    transcripts ingested (core.transcripts.list_transcripts() is empty), so
    compute_qa_preemption_delta() returns None. Rather than print a number we
    can't stand behind, the scorecard reports this as a gap and tells the user
    exactly what to upload to unlock it.
  * "+24.22% after-hours reaction" needs the prior call's date and intraday
    history. We don't store the Q1 earnings date, so it is not reconstructed.
What IS real and computable from script_workflow_state.json:
  * Section speaking time — word count ÷ speaking rate. This is the direct
    answer to Q1's actual finding ("Business Review ran 2 min over at 12 min").
  * Carry-over closure — whether this cycle's script text now contains the
    topics last cycle's post-mortem said were missed, with the matching excerpt
    shown as evidence so the IR lead can judge the match rather than trust it.
  * FLS discipline — [FLS]-tagged forward-looking language in the guidance.
  * Workflow completeness — drafted sections and stage progress.

The composite score is built ONLY from those measurable components, and the
scorecard states its own methodology and what it excludes.

_CARRYOVER is hand-maintained IR judgment for one cycle — exactly like
earnings_page._Q1_TO_Q2_ACTIONS, which its topics mirror. Replace it each
quarter; it is not assumed to hold forward.
"""

import re

from config.client_config import get_active_client_id
from core import db

_WPM = 140.0  # measured earnings-call delivery pace, words per minute

# Persona section -> (label, target minutes). Targets come from Q1's own
# post-mortem: the CEO open at 6.5 min "worked"; Business Review "ran 2 min over
# at 12 min", so its target is 10.
_SECTIONS = [
    ("ir_open", "IR Opening", 2.0),
    ("ceo_narrative", "CEO Narrative", 6.5),
    ("cfo_fin", "CFO Financials", 8.0),
    ("cro_ops", "Business Operations", 10.0),
]

# Q1 2026 -> Q2 2026 carry-over topics. Mirrors earnings_page._Q1_TO_Q2_ACTIONS.
_CARRYOVER = [
    {"topic": "Interest income bridge", "terms": ["interest income"], "priority": "CRITICAL",
     "q1": "NOT pre-empted — drew 3 analyst questions in Q1 Q&A", "target": "CFO Financials"},
    {"topic": "PayFac narration discipline", "terms": ["payfac"], "priority": "IMPROVE",
     "q1": "Business Review ran 2 min over at 12 min — PayFac over-narrated", "target": "Business Operations"},
    {"topic": "Operating leverage framing", "terms": ["operating leverage"], "priority": "KEEP",
     "q1": "CEO framing worked at 6.5 min — analysts now track this narrative", "target": "CEO Narrative"},
    {"topic": "H2 margin pre-emption", "terms": ["margin"], "priority": "IMPROVE",
     "q1": "Margin expansion narrative analysts missed", "target": "Business Operations"},
]


def _state():
    return db.load_json("script_workflow_state.json", None) or {}


def close_to_open_reaction(earnings_date, ticker=None):
    """The market's verdict on a call, measured CLOSE → NEXT OPEN.

    Deliberately NOT after-hours. On a micro-cap like this, the after-hours tape
    is not a real price: when market makers go home they park wide, non-executable
    quotes that still print and still register on a chart. An AH "reaction" built
    on those is noise dressed up as a number (the old static scorecard's
    "+24.22% AH reaction" is exactly that artifact). The last real, executable
    print of the day is the CLOSE, and the next real one is the following OPEN —
    so the honest measure of how the call landed is close → next open.

    `earnings_date`: date/datetime of the call (a post-close call means the
    reaction lands on the NEXT session's open). Returns a dict or None if the
    history isn't available — never a fabricated figure.
    """
    from datetime import datetime as _dt, timedelta
    if isinstance(earnings_date, str):
        try:
            earnings_date = _dt.strptime(earnings_date[:10], "%Y-%m-%d").date()
        except Exception:
            return None
    if hasattr(earnings_date, "date"):
        earnings_date = earnings_date.date()
    from config.client_config import CT
    tk = ticker or CT("ticker")
    try:
        import yfinance as yf
        # Pull a window around the call; we need the close ON the call day and
        # the open of the next SESSION (skips weekends/holidays naturally).
        hist = yf.Ticker(tk).history(
            start=(earnings_date - timedelta(days=5)).isoformat(),
            end=(earnings_date + timedelta(days=8)).isoformat(),
            interval="1d", auto_adjust=False)
        if hist is None or hist.empty:
            return None
        rows = [(i.date(), float(r["Open"]), float(r["Close"]), int(r["Volume"]))
                for i, r in hist.iterrows()]
    except Exception:
        return None

    on_or_before = [r for r in rows if r[0] <= earnings_date]
    after = [r for r in rows if r[0] > earnings_date]
    if not on_or_before or not after:
        return None
    call_day, next_day = on_or_before[-1], after[0]
    close_px, open_px = call_day[2], next_day[1]
    if not close_px:
        return None
    pct = (open_px - close_px) / close_px * 100.0
    return {
        "ticker": tk, "call_date": call_day[0], "reaction_date": next_day[0],
        "close": round(close_px, 4), "next_open": round(open_px, 4),
        "pct": round(pct, 2), "next_close": round(next_day[2], 4),
        "next_day_pct": round((next_day[2] - close_px) / close_px * 100.0, 2),
        "next_volume": next_day[3],
        "basis": "close-to-next-open (executable prints only; after-hours excluded)",
    }


def _words(text):
    return len(re.findall(r"\b[\w'-]+\b", text or ""))


def _full_script(ss):
    """Every piece of script prose on file, for topic search."""
    parts = list((ss.get("script_text") or {}).values())
    if ss.get("full_script_override"):
        parts.append(ss["full_script_override"])
    gd = ss.get("guidance_decision") or {}
    if gd.get("text"):
        parts.append(gd["text"])
    for v in (ss.get("persona_notes") or {}).values():
        if isinstance(v, str):
            parts.append(v)
    return "\n".join(p for p in parts if isinstance(p, str))


def _excerpt(hay, term, width=90):
    i = hay.lower().find(term.lower())
    if i < 0:
        return None
    s = max(0, i - width // 2)
    return ("…" if s else "") + " ".join(hay[s:i + len(term) + width // 2].split()) + "…"


def compose(client_id=None):
    cid = client_id or get_active_client_id()
    ss = _state()
    script = _full_script(ss)

    # ── Sections: drafted? how long will it actually take to say? ──────────
    sections, drafted, on_time = [], 0, 0
    st = ss.get("script_text") or {}
    for key, label, target in _SECTIONS:
        text = st.get(key) or ""
        w = _words(text)
        mins = w / _WPM if w else 0.0
        has = w > 0
        drafted += 1 if has else 0
        # Credit requires the section to be plausibly FINISHED, not merely short.
        # A naive `mins <= target` scored a 1.1-min skeleton against a 6.5-min
        # target as "on time" and handed out full marks for an undrafted script —
        # so the band is 50–100% of target: below it the prose doesn't exist yet,
        # above it the section will overrun (Q1's actual finding).
        ok = has and (target * 0.5) <= mins <= target
        on_time += 1 if ok else 0
        sections.append({
            "label": label, "words": w, "minutes": round(mins, 1), "target": target,
            "drafted": has,
            "status": ("not drafted" if not has
                       else "over target" if mins > target
                       else "under target — likely a skeleton" if mins < target * 0.5
                       else "on target"),
        })
    total_words = sum(s["words"] for s in sections)
    override_words = _words(ss.get("full_script_override"))

    # ── Carry-over closure: did this script fix what Q1 flagged? ───────────
    # USIO's hand-maintained Q1->Q2 topics win for USIO; every other tenant is
    # transcript-driven — carry-over topics extracted from its OWN latest summarized call's
    # Q&A risk topics (core.transcripts.script_inputs), or empty if none is on file.
    from config.client_config import CT as _CT
    if _CT("ticker") == "USIO":
        _carry_src = _CARRYOVER
    else:
        from core import transcripts
        _carry_src = transcripts.script_inputs().get("carryover_topics", [])
    carry = []
    for c in _carry_src:
        hit_term = next((t for t in c["terms"] if t.lower() in script.lower()), None)
        carry.append({
            "topic": c["topic"], "priority": c["priority"], "q1": c["q1"], "target": c["target"],
            "addressed": bool(hit_term),
            "evidence": _excerpt(script, hit_term) if hit_term else None,
        })
    closed = sum(1 for c in carry if c["addressed"])

    # ── FLS discipline ─────────────────────────────────────────────────────
    fls_tags = len(re.findall(r"\[FLS\]", script))
    gd = ss.get("guidance_decision") or {}
    fls_ok = bool(gd.get("text")) and "[FLS]" in (gd.get("text") or "")

    # ── Hedging: does the script commit, or only qualify? ──────────────────
    # Licence-gated (Loughran-McDonald is commercial-use-restricted) — returns
    # None until settings declares lm_license, so this can't reach a client
    # deliverable unlicensed. NOT scored: LM was validated on 10-K filings, not
    # spoken calls, and there is no published "normal" hedge rate for a script.
    # Reported as evidence for a human, not folded into the number.
    try:
        from core import lexicon
        hedge = lexicon.measure(script) if script else None
    except Exception:
        hedge = None

    # ── Guidance consistency: every stated range must match the ONE input ───
    try:
        from core import guidance_engine
        gc = guidance_engine.guidance_consistency(cid)
    except Exception:
        gc = {"conflicts": [], "needs_redraft": False, "ok": True, "input": {}}

    # ── Workflow ───────────────────────────────────────────────────────────
    stages = ss.get("stages") or {}
    done = sum(1 for v in stages.values() if v.get("status") == "complete")
    total_stages = len(stages)

    # ── Composite: ONLY measurable components, weights stated. ─────────────
    comp = []
    c1 = 40 * (closed / len(carry)) if carry else 0
    comp.append(("Carry-over closure", round(c1), 40, f"{closed}/{len(carry)} Q1 topics now in the script"))
    c2 = 25 * (drafted / len(_SECTIONS))
    comp.append(("Sections drafted", round(c2), 25, f"{drafted}/{len(_SECTIONS)} persona sections have prose"))
    c3 = 20 * (on_time / len(_SECTIONS))
    comp.append(("Timing vs target", round(c3), 20,
                 f"{on_time}/{len(_SECTIONS)} sections inside the 50–100%-of-target run-time band"))
    c4 = 15 if fls_ok else 0
    comp.append(("FLS discipline", c4, 15, f"{fls_tags} [FLS] tag(s); guidance "
                                           + ("is tagged" if fls_ok else "NOT tagged")))
    # A script that states a guidance range contradicting the CFO's decision is a
    # disclosure problem, not a style nit — it's scored, and hard.
    n_conf = len(gc.get("conflicts", []))
    c5 = 20 if gc.get("ok") else 0
    comp.append(("Guidance consistency", c5, 20,
                 "every stated range matches the decision" if gc.get("ok")
                 else f"{n_conf} range(s) contradict the CFO decision"
                      + ("; needs_redraft is set" if gc.get("needs_redraft") else "")))
    score = round(sum(c[1] for c in comp) / sum(c[2] for c in comp) * 100)

    # ── Last call's market verdict, and the Q&A pre-empt gap ───────────────
    gaps = []
    reaction, prior_call = None, None
    try:
        from core import transcripts
        tr = transcripts.list_transcripts(cid) or []
    except Exception:
        tr = []
    n_tr = len(tr)
    dated = sorted([t for t in tr if t.get("call_date")], key=lambda t: t["call_date"])
    if dated:
        prior_call = dated[-1]                      # most recent call on file
        reaction = close_to_open_reaction(prior_call["call_date"])
    n_summarized = sum(1 for t in tr if t.get("qa_risk_topics"))
    if n_summarized < 2:
        gaps.append(f"Q&A pre-empt score — {n_tr} transcript(s) ingested but {n_summarized} summarized. "
                    "compute_qa_preemption_delta() needs the prior AND current quarter summarized "
                    "(it extracts each call's qa_risk_topics). Run the summarizer on at least the two "
                    "most recent quarters to unlock it.")
    if not reaction:
        gaps.append("Market reaction — no price history resolved for the last call date on file.")

    return {
        "score": score, "components": comp, "sections": sections, "carryover": carry,
        "total_words": total_words, "override_words": override_words,
        "est_minutes": round(total_words / _WPM, 1),
        "override_minutes": round(override_words / _WPM, 1),
        "stage": ss.get("current_stage") or "not started",
        "stages_done": done, "stages_total": total_stages,
        "fls_tags": fls_tags, "fls_ok": fls_ok,
        "guidance": gc, "hedge": hedge,
        "reaction": reaction,
        "prior_call": ({"quarter": prior_call.get("quarter"), "call_date": prior_call.get("call_date")}
                       if prior_call else None),
        "gaps": gaps, "transcripts_on_file": n_tr, "transcripts_summarized": n_summarized,
        "method": ("Score = carry-over closure (40) + sections drafted (25) + timing inside the "
                   "50–100%-of-target band (20) + FLS discipline (15) + guidance consistency (20), "
                   "normalised to 100. Speaking time = words ÷ 140 wpm; a section far under target "
                   "counts as unwritten, not as 'on time'. Guidance consistency checks every range "
                   "stated in the prose against the CFO's decision (the one input). Excludes the Q&A "
                   "pre-empt score, which requires call transcripts, and measures market reaction "
                   "close-to-next-open rather than after-hours."),
    }
