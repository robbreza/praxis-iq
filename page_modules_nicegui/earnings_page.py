"""
page_modules_nicegui/earnings_page.py — Earnings (prior-quarter review,
script approval workflow, consensus tracker), NiceGUI version.

Tab labels (Prior Qtr Review / Script Generation / Consensus Tracker / Call
Transcripts) were renamed from their original working names (Q1 Lookback /
Script Workflow / Surprise Tracker) for a more professional, institutional-
IR-facing toolbar — the underlying functions/constants below still use the
original names (_render_lookback_tab, _Q1_TO_Q2_ACTIONS, etc.) since
renaming those would be a much larger, purely-cosmetic diff for no
behavioral benefit; only user-facing strings changed.

The original Earnings section of app.py is ~3,000 lines split across three
tabs. Ported here with these documented simplifications:

- Prior Qtr Review ("Q1 Lookback" in app.py, "Learn Before You Write") is
  ported with full fidelity: the call-replay callout, the reaction summary
  strip, script section timing vs. history, word count by section, Q&A
  pre-emption analysis, analyst note alignment, and the Q1→Q2 action
  launcher. This tab is almost entirely a static analysis report, so it
  carries over cleanly.
- Script Generation ("Script Workflow" in app.py) is now ported with full fidelity to the 5-stage pipeline
  itself: Stage 1 CFO Numbers In (the core financial-results intake form —
  revenue breakdown, profitability, volume/cash), Stage 2 IR Review, Stage
  3 CFO+CEO+CRO simultaneous review (CRO added as a formal reviewer Jul 10,
  2026 — the original demo never gave Greg Carter/CRO a sign-off
  checkpoint, only IR/CFO/CEO/Legal; the user asked for one explicitly,
  beyond parity with the demo), Stage 4 Consolidation, and Stage 5 Legal
  Sign-Off with a real Forward-Looking-Statements checklist (10 items,
  individually clearable), each gated on the prior stage completing. Every
  stage shows the same per-persona script canvas (IR/CFO/CRO/CEO tabs +
  full-script view). Each persona panel now has the original's full 3-step
  drafting flow, not just a bare "Generate with AI" button (that flat
  version was a real, previously-undocumented simplification from an
  earlier pass at this port — flagged and rebuilt after the user caught it
  while sitting on Stage 2): Step 1 shows what that persona actually said
  last quarter (verbatim Q1 2026 quotes and/or a key-facts table, plus tone
  annotations — see _PERSONA_LAST_QUARTER, necessarily hardcoded since it's
  one specific quarter's real transcript content, not reusable config);
  Step 2 is a persona-specific "what's new this quarter" textarea (see
  _PERSONA_WHATS_NEW for the question/placeholder each role gets), saved
  per-persona to "persona_notes"; Step 3 combines Step 2 + an optional
  final-notes input into a single context string and generates via the
  Claude API (same core.security.get_anthropic_api_key() pattern as
  investors_page.py's meeting-notes AI feature, with the same kind of
  rule-based fallback template if the API call fails or no key is
  configured) — text is editable either way. IR/CFO/CEO prompts and their
  fallback templates both apply the same beat/in-line/miss tone-signaling
  rules the original used (_tone_context/_TONE_RULES), computed from Stage
  1 revenue vs. Street consensus; CRO's section stays metrics-driven rather
  than tone-driven, matching the original. The CEO tab now also has the
  Guidance & Outlook Decision Engine (_render_guidance_decision), ported
  from app.py after an earlier pass at this port flagged it as a gap and
  the user confirmed it needed to be built: seasonality-adjusted YTD-pace
  math (_guidance_math, using Usio's real quarterly seasonality — Q2 is the
  heaviest quarter at ~35% of FY, Q3 the lightest at ~18%, so a naive
  equal-split H2 read would misstate the pace), a RAISE/REITERATE/NARROW
  recommendation, the same 4-option guidance-action radio the original
  used, the verbatim "IR Guidance Protocol" education panel, a per-action
  templated fallback draft, and an AI-drafted version that feeds in the
  CEO's actual prior-quarter guidance quotes plus the known H2 catalysts —
  this is a separate signaling system from the beat/in-line/miss _tone_
  rules above (that one governs word-choice register across all four
  drafts; this one governs the guidance-range decision itself), though the
  two do interact at generation time the same way the original's guidance
  prompt pulled in its global tone read. It renders ahead of the CEO's own
  Step 1 review, and the decision it produces feeds directly into the CEO
  persona draft's prompt/fallback (see the "gd" wiring in
  _generate_persona_draft/_fallback_draft) instead of the generic static
  "10-12% revenue growth" placeholder used before. Its state persists to
  script_workflow_state.json under "guidance_decision", and its finished
  text is appended as its own section in the Full Script tab (after the
  CEO narrative, matching the original's ordering). Persona names/emails
  come from
  config.client_config.C()["executives"] / CI() instead of being
  hardcoded, so a client without a CRO configured gets a graceful
  placeholder instead of assuming "Greg Carter" belongs to every tenant.
  One deliberate improvement over the original: the persona script text
  (and now Step 2/3 inputs) persists to script_workflow_state.json
  (core.db/SQLite) instead of living only in Streamlit session_state — in
  app.py a browser refresh mid-draft silently lost whatever was typed into
  the CEO/CFO/CRO/IR canvases, since only the stage metadata was ever
  written to disk.
  Stage 1B "Operating Metrics & Disclosure Consistency Check" is now also
  ported (_render_stage1b, rendered directly under Stage 1 in the same tab —
  it was a side-by-side column in the original, not a separate page): the
  19 Card/PayFac/PayFac-pipeline/Usio-ONE/ACH/Prepaid metrics, the 9-item
  disclosure-gap check against what was disclosed last quarter, and the
  disclosure-omission notes field. Submitted independently of Stage 1's own
  numbers (doesn't gate the Stage 2 transition) and persists to the same
  script_workflow_state.json under "q2_ops_metrics". Its data now also feeds
  the CRO/Business-Operations persona draft (_generate_persona_draft) so that
  card/PayFac/RTP/Usio-ONE detail shows up in the AI-drafted paragraph and
  its numbers-based fallback, not just the core Stage 1 financials. Dropped
  the original's quarter-specific historical placeholder hints (e.g. "Q1
  2026: +23% YoY to record $9.7M") since those were a one-time snapshot of
  that specific quarter, not something to hardcode into a reusable form.
  NOT ported: the "Parse from IRConnect Email" intake tab — superseded by
  the real email-routing pipeline built this session (core/mail_gateway.py,
  core/email_classifier.py, core/inbox_queue.py), which already gets a
  CFO's model/numbers email into a review queue; still available in app.py
  if the old flow is ever needed for reference.
- Consensus Tracker ("Surprise Tracker" in app.py; Beat/Miss History, Log
  Quarter, Pre-Call Assessment) is ported with full fidelity: the Log Quarter form captures every field the original
  did (pre-earnings close, 3-day move, avg PT change $, pre-empt score
  0-12, alongside the fields already here), and Pre-Call Assessment's "Guidance
  midpoint" and "Bar risk" cards show the same point-in-time assessment
  app.py hardcoded, now sourced from the client record (CT()) instead of
  being duplicated inline, so it stays client-agnostic.

Client-scoped persistence via core.db (SQLite): script_workflow_state.json,
earnings_surprise_log.json, q2_precall.json — same pattern as every other
ported page. (These key names are inherited from the pre-SQLite file-based
version — core.db imports any pre-existing file under that name on first
read, so nothing from earlier testing is lost. See core/db.py.)
"""

import asyncio
import json
import urllib.request
from datetime import datetime

import pandas as pd
from nicegui import ui

from config.client_config import C, CE, CF, CGP, CI, CT, get_active_client_id, team_labels
from config.theme_tokens import ACTIVE as COLORS
from core import activity_log, consensus, db, guidance_engine, inbox_queue, market_data, transcripts
from core.security import get_anthropic_api_key
from page_modules_nicegui import nav

STAGES = [
    {"id": "cfo_numbers", "label": "Stage 1", "name": "CFO Numbers In", "icon": ""},
    {"id": "ir_review", "label": "Stage 2", "name": "IR Review", "icon": ""},
    {"id": "exec_review", "label": "Stage 3", "name": "CFO+CEO+CRO Review", "icon": ""},
    {"id": "consolidate", "label": "Stage 4", "name": "Consolidation", "icon": ""},
    {"id": "legal_signoff", "label": "Stage 5", "name": "Legal Sign-Off", "icon": ""},
]

# Forward-Looking Statements checklist for the Script Generation tab's
# Legal Sign-Off stage — moved from a hardcoded module constant into
# CLIENT_REGISTRY's "fls_items" 2026-07-12 (multi-client refactor; this
# constant was flagged, when originally built, as needing exactly this
# treatment for a future client with different guidance language — see
# config/client_config.py's docstring gap-inventory). _fls_items() is the
# single read point every consumer below calls instead of touching CT()
# directly, so the "no items configured" case (empty checklist rather than
# USIO's items leaking into another tenant) is handled in one place.
def _fls_items():
    return CT("fls_items", [])

# Q1 2026 Q&A pre-emption record — which analyst questions were addressed
# proactively in the script vs. surfaced live in Q&A. Un-pre-empted topics
# feed the Q&A Prep tab below (task: predict what analysts will ask again
# this quarter). Like _Q1_TO_Q2_ACTIONS, replace this each cycle — once a
# real Q2 transcript is ingested and summarized, core/transcripts.py's
# qa_risk_topics should replace this hardcoded list entirely (see
# core.transcripts.compute_qa_preemption_delta).
_Q1_QA_TOPICS = [
    ("PayFac growth trajectory", True, "Pre-empted — CEO led with it"),
    ("ACH volume acceleration", True, "Pre-empted in CFO section"),
    ("Gross margin improvement path", True, "Pre-empted — specific H2 commentary"),
    ("Interest income headwind", False, "3 questions — NOT pre-empted · Fix for Q2"),
    ("Prepaid decline — how long?", False, "2 questions — partial pre-emption only"),
    ("SG&A leverage timeline", True, "Pre-empted — Louis was explicit"),
    ("M&A / capital allocation", False, "1 question — outside script · deflected well"),
    ("FY2026 guidance confidence", True, "Pre-empted — held guidance range firm"),
]

# Q1 2026 section timing (actual vs. historical norm) and word counts — same
# one-time-snapshot caveat as above. The word-count/minute pairs below give
# a real, client-derived speaking rate (~124 wpm across CEO/Business/CFO/
# Guidance sections) rather than an assumed generic rate, used by the
# pacing estimate in the Script Canvas.
_Q1_SECTION_TIMING = [
    ("CEO Opening", 6.5, 8.0, "#3B82F6", "On track — tight and thematic"),
    ("Business Review", 12.0, 10.0, "#B45309", "Ran 2 min over — PayFac detail was dense"),
    ("CFO Financial Review", 9.5, 10.0, "#15803D", "Under budget — well-structured"),
    ("Guidance & Outlook", 4.0, 4.0, "#15803D", "Exactly on — Louis was disciplined"),
    ("Q&A Session", 40.0, 35.0, "#B91C1C", "Ran 5 min over — interest income bridge took 3 questions"),
]
_Q1_SECTION_WORDCOUNT = [
    ("CEO Opening", 820, 900), ("Business Review", 1450, 1200), ("CFO Financial Review", 1180, 1150),
    ("Guidance & Outlook", 510, 520), ("Prepared Q&A", 2200, 1800),
]
_HISTORICAL_WPM = round(
    sum(wc for _, wc, _ in _Q1_SECTION_WORDCOUNT[:4])
    / sum(actual for _, actual, _, _, _ in _Q1_SECTION_TIMING[:4])
)  # ~124 wpm, derived from Q1 2026's actual word counts / actual minutes (CEO/Business/CFO/Guidance only)
# Historical norm minutes per persona/section, for the live pacing estimate
# below — IR has no separate historical entry (the opening/handoff is brief
# and wasn't separately timed in the Q1 breakdown), so it's omitted rather
# than guessed.
_SECTION_HISTORICAL_MINUTES = {"CRO": 10.0, "CFO": 10.0, "CEO": 8.0, "guidance": 4.0}


def _pacing_estimate(text, hist_key=None):
    """Estimated speaking time from word count, using the real Q1-derived
    _HISTORICAL_WPM rather than a generic assumption, compared against that
    section's actual historical norm (_SECTION_HISTORICAL_MINUTES) when one
    exists. A ±15% band around the historical norm reads as "on pace" —
    same style of tolerance band as _tone_context's ±$0.5M."""
    words = len((text or "").split())
    est_min = (words / _HISTORICAL_WPM) if _HISTORICAL_WPM else 0.0
    hist = _SECTION_HISTORICAL_MINUTES.get(hist_key) if hist_key else None
    if not hist:
        return f"~{est_min:.1f} min ({words} words)", COLORS["text_muted"]
    delta = est_min - hist
    if delta > hist * 0.15:
        return f"~{est_min:.1f} min ({words} words) — running long vs. the ~{hist:.1f} min historical norm", "#B91C1C"
    if delta < -hist * 0.15:
        return f"~{est_min:.1f} min ({words} words) — shorter than the ~{hist:.1f} min historical norm", "#1E40AF"
    return f"~{est_min:.1f} min ({words} words) — on pace vs. the ~{hist:.1f} min historical norm", "#15803D"


# Q1 → Q2 Script Actions — the concrete, specific critique from the Q1
# post-mortem (Prior Qtr Review tab), each item tagged with which persona's
# script section it applies to. Pulled out to a module constant (was a
# local list inside _render_lookback_tab only) so Step 2 of the script
# canvas can seed each persona's "what's new" with the actual finding from
# last quarter instead of a generic placeholder — the user's specific ask.
# "Q&A Prep" items have no persona_role (no script-canvas tab for it yet).
# Like _PERSONA_LAST_QUARTER, this is one quarter's real critique — replace
# it each cycle rather than assuming it holds going forward.
_Q1_TO_Q2_ACTIONS = [
    {"priority": "CRITICAL", "clr": "#EF4444", "icon": "", "persona_role": "CFO",
     "q1_finding": "Interest income — NOT pre-empted · 3 analyst questions in Q1 Q&A",
     "action": "Write interest income bridge in CFO section",
     "where": "Script Generation → CFO Financials", "impact": "Eliminates ~3 questions from covering analysts"},
    {"priority": "IMPROVE", "clr": "#B45309", "icon": "", "persona_role": "CRO",
     "q1_finding": "Business Review ran 2 min over at 12 min · PayFac over-narrated",
     "action": "Cap Business Operations section at 90 sec on PayFac · add H2 margin pre-emption",
     "where": "Script Generation → Business Operations", "impact": "Reclaims 2 min for margin expansion narrative analysts missed"},
    {"priority": "NEW", "clr": "#1E40AF", "icon": "", "persona_role": None,
     "q1_finding": "No Q&A prep section existed in Q1 · 3 off-script questions",
     "action": "Build analyst-specific Q&A prep",
     "where": "Script Generation → Q&A Prep", "impact": "Pre-empts analysts on interest income and margin mix"},
    {"priority": "KEEP", "clr": "#15803D", "icon": "", "persona_role": "CEO",
     "q1_finding": "CEO opening tone — 6.5 min · 'operating leverage inflection' framing worked",
     "action": "Reprise CEO framing in Q2 · same length · update numbers only",
     "where": "Script Generation → CEO Narrative", "impact": "Analysts are now tracking this narrative — reinforce it"},
]


def _get_current_qa_actions():
    """Prefer a critique computed from the two most-recently ingested +
    summarized call transcripts (core.transcripts.compute_qa_preemption_
    delta) over the hand-maintained _Q1_TO_Q2_ACTIONS snapshot, once real
    data exists for two quarters. Falls back to the Q1 2026 snapshot
    otherwise. This is the "auto-refresh post-mortem" mechanism — it can't
    actually exercise the computed path yet since only Q1 2026 has been
    ingested so far; it will start returning computed critiques the moment
    a second quarter's transcript is ingested and summarized, with no code
    change needed here."""
    records = transcripts.list_transcripts()
    summarized = [r for r in records if r.get("qa_risk_topics")]
    if len(summarized) >= 2:
        summarized.sort(key=lambda r: r.get("uploaded_at") or "", reverse=True)
        current_q, prior_q = summarized[0]["quarter"], summarized[1]["quarter"]
        computed = transcripts.compute_qa_preemption_delta(prior_q, current_q)
        if computed:
            return computed
    return _Q1_TO_Q2_ACTIONS


# Script-canvas personas — role key, script_text sub-key, display label.
# Ordered to match how the call is actually SPOKEN (the transcript order): operator/IR opens, the CEO
# gives the narrative, the CFO details the financials + outlook, a business leader (if speaking) follows,
# then Q&A. The old order (IR, CFO, CRO, CEO) put the CEO last, which no earnings call does.
PERSONAS = [
    ("IR", "ir_open", "IR Opening"),
    ("CEO", "ceo_narrative", "CEO Narrative"),
    ("CRO", "cro_ops", "Business Operations"),
    ("CFO", "cfo_fin", "CFO Financial Review"),
]


def _active_personas():
    """PERSONAS filtered to the roles actually DELIVERING prepared remarks this quarter, per the
    confirmed speaker lineup (see core.speakers). Drives auto-drafting, the canvas render, and the
    assembled full script — so no section is drafted or shown for a role that isn't speaking (e.g.
    a vacant IR seat mid-transition). Falls back to all four personas when nothing is confirmed
    (the workflow gate normally prevents that, but callers stay safe)."""
    contacts = _contacts()
    return [(role, key, label) for role, key, label in PERSONAS
            if contacts.get(role, {}).get("speaking") is not False]

# Call Opening — the operator's introduction plus IR's welcome/participant-
# roster paragraph and the forward-looking-statements/safe-harbor reading
# (the mechanism by which the call opens with a Reg FD-safe disclosure that
# what follows may include forward-looking statements). This was present in
# the original app.py demo, explicitly marked "reads verbatim, do not edit"
# (operator) and "DO NOT EDIT — Legal-approved language, verbatim from prior
# calls" (the FLS/safe-harbor paragraph) — flagged as missing from this port
# and rebuilt here to match. Rendered read-only (see _render_call_opening),
# not as an editable AI draft like the rest of the canvas, and always
# prepended to the assembled Full Script (see _assembled_script_text) so
# it's actually part of what CFO/CEO/Legal review and what gets downloaded.
#
# Exec titles and Q&A-only participants moved out of module constants into
# CLIENT_REGISTRY 2026-07-12 (multi-client refactor) — each executive's
# "title" key (config/client_config.py) and the client-level
# "qa_only_participants" string are read directly in _call_opening_text
# below instead of the old _CALL_OPENING_EXEC_TITLES/
# _CALL_OPENING_QA_ONLY_PARTICIPANTS constants. The FLS/safe-harbor
# paragraph below is still a plain module constant — it's generic legal
# boilerplate with no client-specific text today, but it's still a
# per-client legal sign-off in practice, so it belongs in CLIENT_REGISTRY
# too once a second client needs its own Legal-approved wording.
_CALL_OPENING_FLS_TEXT = (
    "Let me remind our listeners that certain statements made during the call today constitute "
    "forward-looking statements made pursuant to the safe harbor provisions of the Private Securities "
    "Litigation Reform Act of 1995 as amended and as more fully discussed in our press release and in "
    "our filings with the SEC. Following our prepared remarks, there will be a question-and-answer "
    "session for those who registered as a financial professional."
)


_CALL_OPENING_KEY = "call_opening.json"   # per-client, per-period overrides of the opening


def _call_opening_store(cid=None):
    from config.client_config import get_active_client_id
    return db.load_json(_CALL_OPENING_KEY, {}, client_id=cid or get_active_client_id()) or {}


def _call_opening_effective(period, defaults, cid=None):
    """(operator, welcome, fls) for `period`: this period's saved edit if any, else the MOST
    RECENT prior period's edit carried forward ("similar to last quarter, never exact"), else the
    templated defaults. A blank field falls back too, so a partial edit still fills the rest."""
    store = _call_opening_store(cid)
    src = store.get(period)
    if not src and store:
        src = max(store.values(), key=lambda v: v.get("_saved_at", ""))
    src = src or {}
    return ((src.get("operator") or "").strip() or defaults[0],
            (src.get("welcome") or "").strip() or defaults[1],
            (src.get("fls") or "").strip() or defaults[2])


def _save_call_opening(period, operator, welcome, fls, cid=None):
    from config.client_config import get_active_client_id
    cid = cid or get_active_client_id()
    store = db.load_json(_CALL_OPENING_KEY, {}, client_id=cid) or {}
    store[period] = {"operator": operator, "welcome": welcome, "fls": fls,
                     "_saved_at": datetime.now().isoformat(timespec="seconds")}
    db.save_json(_CALL_OPENING_KEY, store, client_id=cid)


def _clear_call_opening(period, cid=None):
    from config.client_config import get_active_client_id
    cid = cid or get_active_client_id()
    store = db.load_json(_CALL_OPENING_KEY, {}, client_id=cid) or {}
    store.pop(period, None)
    db.save_json(_CALL_OPENING_KEY, store, client_id=cid)


def _call_opening_defaults(ss):
    """Returns (operator_line, welcome_line, fls_line) — the three paragraphs that open every
    call, templated from client config (ticker/company/quarter/IR contact/exec roster). These are
    the CARRY-OVER baseline; the client's per-quarter edits overlay them (see _call_opening_text)."""
    ticker = CT("ticker", "")
    company = CT("name", ticker) or ticker
    quarter = CE().get("current_quarter", "this quarter")
    ir = CI()
    execs = C().get("executives", {})

    # The OPERATOR reads the logistics and (below) the safe harbor, THEN hands to the host — so the
    # operator intro no longer ends with the handoff; the handoff moves to the end of the FLS reading.
    operator_line = (
        f"Hello, and welcome to the {company} {quarter} Earnings Conference Call. All participants will "
        f"be in a listen-only mode. After today's presentation, there will be an opportunity to ask "
        f"questions. Please note today's event is being recorded."
    )

    intro_bits = []
    for role in ("CEO", "CRO", "CFO"):
        e = execs.get(role)
        if e and e.get("name"):
            title = e.get("title") or f"our {role}"
            intro_bits.append(f"{e['name']}, {title}")
    intro_line = ", ".join(intro_bits) if intro_bits else "our management team"

    qa_only = CT("qa_only_participants", "")
    qa_only_clause = f"In addition, {qa_only} will be made " \
                      "available during the question-and-answer session at the end of our call." \
        if qa_only else ""

    welcome_line = (
        f"Thank you, operator, and thank you for joining our call today. Welcome to {company}'s "
        f"{quarter} conference call. The earnings release, which we issued today after the market "
        f"closed, is available on our website under the Investor Relations tab. On this call with me "
        f"today are {intro_line}. {qa_only_clause}"
    ).strip()

    # Operator-read safe harbor, closing with the handoff to the host.
    fls_line = (
        f"{_CALL_OPENING_FLS_TEXT} I would now like to turn the conference over to your host, "
        f"{ir.get('name', 'the host')}. Please go ahead."
    )
    return operator_line, welcome_line, fls_line


def _call_opening_text(ss):
    """The EFFECTIVE Call Opening used in the assembled script and downloads: the client's saved
    per-quarter edits (or last quarter's, carried forward) over the templated defaults."""
    period = (CE().get("current_quarter") or "").strip()
    return _call_opening_effective(period, _call_opening_defaults(ss))


def _render_call_opening(ss):
    """Editable Call Opening — operator intro, IR welcome, and the Reg FD / safe-harbor reading.
    Pre-filled from last quarter (carry-over), editable, saved per quarter, and always prepended to
    the assembled Full Script and every download. Legal-approved wording: a material change to the
    safe-harbor paragraph needs Legal to re-sign-off — but the client owns the pivot (e.g. an IR
    departure, handing lines to the operator)."""
    period = (CE().get("current_quarter") or "").strip()
    ir = _contacts().get("IR", CI())   # confirmed IR speaker for this quarter, not the static registry
    with ui.card().classes("w-full").style(
            "background:rgba(180,83,9,.06);border:2px solid #B45309;border-radius:8px;"
            "padding:12px 14px;margin-bottom:12px;"):
        ui.label("Call Opening — Operator (intro + Reg FD / Safe Harbor) · Host Welcome").classes("font-bold").style(
            "color:#B45309;font-size:var(--fs-base);")
        ui.label("Carried over from last quarter — edit or add as needed. Similar every quarter, never "
                 "identical: a lineup change (e.g. an IR head handing lines to the operator) is a common "
                 "pivot. Legal-approved wording — a material change to the safe-harbor paragraph should go "
                 "back to Legal. Always included at the very start of the assembled Full Script and every "
                 "download.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-bottom:8px;")

        @ui.refreshable
        def _body():
            op, wel, fls = _call_opening_effective(period, _call_opening_defaults(ss))
            # Order matches delivery: operator intro → operator reads the safe harbor (+ handoff) → host welcome.
            op_in = ui.textarea("Operator — opening", value=op).classes("w-full").props("outlined autogrow")
            fls_in = ui.textarea("Operator — Forward-Looking Statements / Safe Harbor (Legal-approved)",
                                 value=fls).classes("w-full").props("outlined autogrow")
            wel_in = ui.textarea(f"{ir.get('name', 'IR')} — Welcome & Participants", value=wel).classes(
                "w-full").props("outlined autogrow")

            def _save():
                _save_call_opening(period, op_in.value, wel_in.value, fls_in.value)
                ui.notify(f"Call opening saved for {period}.", type="positive")

            def _reset():
                _clear_call_opening(period)
                _body.refresh()
                ui.notify("Reverted to the carried-over / default wording.", type="info")
            with ui.row().classes("gap-2").style("margin-top:4px;"):
                ui.button("Save call opening", icon="save", on_click=_save).props("dense color=primary")
                ui.button("Reset to carry-over", icon="restart_alt", on_click=_reset).props("flat dense").tooltip(
                    "Clear this quarter's edits and fall back to last quarter's (or the template)")
        _body()
    ui.markdown("---")


# Step 1 reference — what each persona actually said last quarter, shown so
# whoever drafts this quarter's section can see the exact prior language
# before deciding what to change. This is real historical content tied to
# one specific quarter's call, not reusable client config, so unlike
# CLIENT_REGISTRY's contacts/fls_items fields it isn't expected to carry forward untouched — the
# next quarter's version of this workflow should replace these with that
# quarter's own transcript excerpts (see the Call Transcripts tab / a
# future core.transcripts-backed lookup once more than one quarter is on
# file).
_PERSONA_LAST_QUARTER = {
    "IR": {
        "quote": ("It was a record quarter for Usio, with very strong growth leading to record "
                  "processing volumes and quarterly revenues. We also saw similar records achieved "
                  "across many of our business units. On the bottom line, we achieved positive "
                  "adjusted EBITDA and GAAP net income. We also generated positive operating cash "
                  "flow. We are executing on all of our objectives and remain on pace to achieve our "
                  "guidance for the year as we continue to succeed in converting pipeline to "
                  "implementations to volumes, and volumes into revenue."),
        "prior_quotes": [
            ("Q4 2025", "It was a solid quarter in line with our commitment..."),
            ("Q3 2025", "Q3 was a solid quarter and in line with our commitment..."),
        ],
        "rows": [],
        "tags": ["Tone: BEAT — used ‘record’ language 4×",
                 "Closed with the pipeline → implementations → volumes formula",
                 "Handed off directly to the CFO"],
    },
    "CFO": {
        "quote": "Thank you, Paul, and good afternoon. It's nice to be with you today.",
        "prior_quotes": [],
        "rows": [
            ("Revenue", "$25.47M (+16% YoY) — record quarter"),
            ("ACH YoY", "+25% revenue · +34% transactions · +31% dollar volume"),
            ("Card YoY", "+23% revenue · +22% transactions · +16% dollar volume"),
            ("Output Solutions", "+19% — accelerating"),
            ("Gross margin", "Somewhat lower — interest income decline (100%-margin line)"),
        ],
        "tags": ["Interest income decline was NOT pre-empted last quarter — "
                 "drew 3 analyst Q&A follow-ups"],
    },
    "CRO": {
        "quote": None,
        "prior_quotes": [],
        "rows": [
            ("Card revenue YoY", "+23% — record $9.7M"),
            ("PayFac % of card", "78% — fastest-growing segment"),
            ("Filtered Spend", "2,000+ merchants live · 8,000+ in pipeline · expanding beyond Northeast"),
            ("Real-Time Payments", "Grew from 2,000 to 200,000+ transactions/month during the quarter"),
            ("Usio ONE case study", "Custom payout provider — came in for card, now also on RTP + Output + prepaid"),
            ("New enterprise", "Building-supply and online-sporting-goods accounts (first full quarter)"),
        ],
        "tags": ["Everything above must be disclosed again this quarter, or explicitly "
                 "explained if it's being dropped"],
    },
    "CEO": {
        "quote": "After a record 2025, this year is off to a record start.",
        "prior_quotes": [],
        "rows": [
            ("Usio ONE", "Cross-sell producing results · mining existing relationships · first wins disclosed"),
            ("New products", "PostCredit market-ready soon · RTP explosive growth · school voucher program"),
            ("Closing", "“We remain committed to building a stronger, more innovative, and more valuable Usio.”"),
        ],
        "tags": ["Signature phrase: “Converting pipeline to implementations to volumes, and volumes into revenue.”",
                 "Guidance stance: “Prudent to be cautious early in the year” — reiterated 10-12% growth"],
    },
}

# Step 2 "What's new" prompt — persona-specific question + illustrative
# placeholder text, so each persona is asked about what's actually within
# their own remit rather than one generic "what's new" box.
_PERSONA_WHATS_NEW = {
    "IR": ("What should the IR opening signal differently this quarter?",
           "e.g. Second consecutive beat but smaller than Q1 — use 'solid' not 'record' language · "
           "best-ever ACH month · RTP volume surged · PayFac now a larger share of card"),
    "CFO": ("What should the CFO address proactively or add for this quarter?",
            "e.g. Interest income change vs last quarter — address before Q&A this time · "
            "gross margin move · SG&A · cash use (buybacks, etc.)"),
    "CRO": ("What should Business Operations highlight that's new or different from last quarter?",
            "e.g. Filtered Spend expanded into a new region · new enterprise accounts signed · "
            "RTP volume milestone · new Usio ONE cross-sell win"),
    "CEO": ("What should the CEO narrative emphasize that's new or has evolved since last quarter?",
            "e.g. New product now market-ready · new bank sponsor signed · guidance stance evolving · "
            "notable new win or partnership"),
}

# Tone-signaling rules — ported from app.py's beat/in-line/miss branching
# (there, computed from a multi-quarter "trend-aware tone system"; here
# simplified to a single-quarter read since only Q1 2026 actuals are on
# file). Applied to IR/CFO/CEO prompts — CRO's section is metrics-driven
# rather than tone-driven in the original, so it's left out of this table
# on purpose.
_TONE_RULES = {
    "beat": "Open with confident, 'record'-style language and cite the specific number(s) that set a record. "
            "Close by reinforcing execution against plan (e.g. 'on pace' / 'executing on all objectives').",
    "inline": "Open with steady, 'solid quarter, in line with our commitment' language. Cite sequential "
              "improvement rather than YoY records. Close with 'on pace to achieve guidance.'",
    "miss": "Open with a sequential-improvement narrative rather than dwelling on the shortfall — never use "
            "the word 'miss.' Pivot quickly to forward catalysts and close with forward-looking, "
            "confidence-building language (e.g. 'positions us for' / 'inflection point').",
}


def _tone_context(ss):
    """Beat/in-line/miss read vs Street consensus, computed from the Stage 1
    revenue number — drives _TONE_RULES above. The $ band around consensus
    treated as "in line" is a per-client value (CLIENT_REGISTRY's
    "tone_band_m", default 0.5) rather than a hardcoded module constant —
    the right order of magnitude for USIO's ~$60M market cap is wrong for a
    company 10-100x the size."""
    n = ss.get("q2_numbers", {})
    band = CT("tone_band_m", 0.5) or 0.5
    delta = (n.get("rev", 0) or 0) - (market_data.consensus_rev_value() or 0)
    if delta > band:
        return {"bucket": "beat", "label": f"BEAT +${delta:.2f}M vs Street", "delta": delta}
    if delta < -band:
        return {"bucket": "miss", "label": f"MISS ${delta:.2f}M vs Street", "delta": delta}
    return {"bucket": "inline", "label": "\U0001f7e1 IN LINE vs Street", "delta": delta}


def _load_json(name, default):
    return db.load_json(name, default)


def _save_json(name, data):
    db.save_json(name, data)


def _refresh():
    nav.go_to("Earnings")


def _contacts():
    """Role -> {name, email} for the script workflow's reviewers/personas.
    IR comes from CI() (every client has this — it's the whole point of
    the platform); CFO/CEO/CRO/Legal come from C()['executives']. A client
    whose executives dict omits a role (e.g. no CRO configured yet) gets a
    graceful placeholder instead of this crashing or silently borrowing
    another tenant's name."""
    ir = CI()
    execs = C().get("executives", {})
    out = {"IR": {"name": ir.get("name", "IR Contact"), "email": ir.get("email", ""),
                  "title": ir.get("title", "")}}
    for role in ("CFO", "CEO", "CRO", "Legal"):
        e = execs.get(role)
        out[role] = dict(e) if e else {"name": f"— {role} not configured —", "email": ""}
    # Overlay the CONFIRMED lineup for the current quarter: a confirmed speaker's name/title WINS
    # (this is how a departure/replacement flows through — e.g. a new IR head), and `speaking`
    # marks who delivers prepared remarks. Email stays from the registry, since the confirmation
    # form doesn't capture it and the reviewer-routing still needs it.
    try:
        from core import speakers
        confirmed = speakers.get_confirmed(speakers.current_period()) or {}
        lineup = confirmed.get("speakers") or []
        if lineup:
            confirmed_roles = {s.get("role") for s in lineup}
            for s in lineup:
                role = s.get("role")
                if not role:
                    continue
                base = dict(out.get(role, {"email": ""}))
                base["name"] = s.get("name") or base.get("name")
                if s.get("title"):
                    base["title"] = s["title"]
                base["speaking"] = bool(s.get("speaking", True))
                out[role] = base
            # A role absent from the confirmed lineup is NOT speaking this quarter.
            for role in out:
                out[role].setdefault("speaking", role in confirmed_roles)
    except Exception:
        pass
    return out


def _blank_script_state():
    return {
        "current_stage": "cfo_numbers",
        "stages": {s["id"]: {"status": "pending", "completed_at": None, "notes": ""} for s in STAGES},
        "versions": [],
        "version": 0,
        "q2_numbers": {},
        "q2_ops_metrics": {},
        "guidance_decision": {},
        "fls_checklist": {},
        # Persona draft text — persisted here (unlike app.py, where this
        # only ever lived in Streamlit session_state; see module docstring).
        "script_text": {key: "" for _, key, _ in PERSONAS},
        # Per-persona Step 2/Step 3 inputs (What's New + final notes) —
        # also persisted here rather than only in-memory, same rationale.
        "persona_notes": {key: {"whats_new": "", "final_notes": ""} for _, key, _ in PERSONAS},
        # CRO added to formal reviewers Jul 10, 2026 — the original demo
        # (app.py) never gave Greg Carter/CRO a sign-off checkpoint either
        # (only IR/CFO/CEO/Legal tracked sent/received/status there), but
        # the user asked for one explicitly, beyond parity with the demo.
        # Folded into Stage 3 alongside CFO+CEO — see _render_stage3 and
        # _check_stage3_advance.
        "reviewers": {r: {"status": "pending", "sent": None, "received": None, "notes": ""} for r in ("IR", "CFO", "CEO", "CRO", "Legal")},
        # Direct edits made in the "Full Script (assembled)" box itself
        # (e.g. smoothing a transition between two speakers' sections) —
        # kept separate from script_text because splitting an edited
        # combined document back into 4 persona sections isn't reliable.
        # Once set, this is the authoritative full script everywhere
        # (_full_script_text prefers it) — autosaves as you type, but
        # full_script_override_saved_at only updates on an explicit Save
        # click, so the "Saved ..." confirmation means what it says.
        "full_script_override": "",
        "full_script_override_saved_at": None,
        "first_pass_complete": None,
    }


def _render_prep_brief_tab():
    """Earnings Prep Brief — moved here from Board IR Reports; it's an earnings-cycle
    document, not a board report. Shares the same live renderer in reports_page."""
    ui.label("Earnings Prep Brief").classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
    ui.label("What management needs in the room — composed live from the consensus file, the "
             "CFO’s guidance decision, the risk scorecard, and the last transcript.").style(
             f"color:{COLORS['text_muted']}")
    from page_modules_nicegui.reports_page import _render_earnings_prep
    _render_earnings_prep()


def render_earnings_page():
    earnings = CE()
    ui.label(f"Earnings Cycle · {earnings.get('current_quarter','')} · "
             f"{earnings.get('earnings_date','')} {earnings.get('call_time','')}").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    # Deep-link from elsewhere in the app — consumed once per page visit,
    # same nav.highlights pattern markets_page.py uses for its Today ->
    # Markets analyst jump. "transcripts" is set by the Prior Qtr Review
    # tab's "Go to Call Transcripts" button; "script" is set by Today's
    # "Open Script Generation" button (added after that button was found
    # to silently land on the default Prior Qtr Review tab instead of
    # actually opening Script Generation — see chat from Jul 10, 2026).
    _earnings_tab_target = nav.pop_highlight("earnings_tab", None)
    jump_to_transcripts = _earnings_tab_target == "transcripts"
    # "guidance" (Markets "Open the Guidance Decision Engine" buttons) lands on
    # the Script Generation tab AND scrolls to the Decision Engine, so the
    # button opens the engine itself rather than the top of the tab.
    jump_to_script = _earnings_tab_target in ("script", "guidance")
    scroll_to_guidance = _earnings_tab_target == "guidance"

    # The visible tab strip is REDUNDANT on desktop — the sidebar lists all seven of these under
    # Earnings Cycle (Prep / The Call / After), and each sidebar sub-item deep-links straight to its
    # tab via nav.consume_target_tab() below. So hide the strip on desktop (≥1024px) via the
    # .page-tabstrip CSS rule, exactly like the drawer-toggle: the tab_panels still switch, driven
    # by the sidebar. Kept below 1024px, where there's no docked sidebar and this is the tab nav.
    with ui.tabs().classes("w-full page-tabstrip") as tabs:
        # Tab order mirrors the sidebar's Prep / The Call / After grouping (NAV_SUBGROUPS):
        #   Prep      → Prior Qtr Review · Script Generation · Prep Brief · Consensus Tracker
        #   The Call  → Call Transcripts
        #   After     → Narrative Momentum · Morning After
        t1 = ui.tab("Prior Qtr Review")
        t2 = ui.tab("Script Generation")
        t_prep = ui.tab("Prep Brief")
        t3 = ui.tab("Consensus Tracker")
        t4 = ui.tab("Call Transcripts")
        # Narrative Momentum — "is the story landing?" A post-call read (same shared renderer,
        # narrative_engine via markets_page._render_narrative_momentum), so it groups under After
        # with Morning After and sits after Call Transcripts in the tab order.
        t5 = ui.tab("Narrative Momentum")
        # Morning After — the post-call critique (core.morning_after). Sits last
        # because it's the end of the cycle: the call has happened, the tape has
        # voted, and this is what feeds next quarter's Prior Qtr Review (t1).
        t6 = ui.tab("Morning After")

    # Lazy tab loading — all 4 tabs used to build eagerly on every page
    # load (this page's Script Generation tab alone builds a 15-field intake
    # form plus 5 nested sub-stage panels), which was blocking the event
    # loop long enough to trip NiceGUI's "Connection lost, trying to
    # reconnect" websocket timeout the moment someone opened this page.
    # Same fix already applied to investors_page.py's render_investors_page
    # — only the default-open tab renders immediately; the rest render a
    # spinner and build for real the first time they're actually selected.
    # A sidebar sub-item deep-links straight to a tab (nav.consume_target_tab);
    # it wins over the guidance/transcript jump logic. Map the label back to its
    # tab object so the lazy-load default and eager-render branches still work.
    _by_name = {t.props["name"]: t for t in (t1, t2, t_prep, t3, t4, t5, t6)}
    default_tab = _by_name.get(nav.consume_target_tab()) or (
        t4 if jump_to_transcripts else (t2 if jump_to_script else t1))
    with ui.tab_panels(tabs, value=default_tab).classes("w-full"):
        with ui.tab_panel(t1) as p1:
            if default_tab is t1:
                _render_lookback_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t2) as p2:
            if default_tab is t2:
                _render_script_workflow_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t_prep) as p_prep:
            if default_tab is t_prep:
                _render_prep_brief_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t3) as p3:
            if default_tab is t3:
                _render_surprise_tracker_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t4) as p4:
            if default_tab is t4:
                _render_transcripts_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t5) as p5:
            if default_tab is t5:
                _render_narrative_momentum_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t6) as p6:
            if default_tab is t6:
                _render_morning_after_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")

    if scroll_to_guidance:
        # Land on the Guidance & Outlook Decision Engine. It lives in the Script
        # Canvas, which only renders under a REVIEW stage sub-tab (IR Review and
        # later) — never under the default Stage 1 (CFO Numbers intake). So the
        # deep-link must first activate a review stage, then scroll to the anchor.
        # Each retry: if the anchor isn't in the DOM yet, click the "IR Review"
        # stage tab; once it is, scroll to it. Retries a handful of times because
        # the heavy tab reflows as forms/charts settle. No-op if neither exists.
        ui.timer(0.2, lambda: ui.run_javascript(
            "(function(){var n=0;function go(){"
            "var el=document.getElementById('guidance-engine-anchor');"
            "if(el){el.scrollIntoView({block:'start'});}"
            "else{var t=[].slice.call(document.querySelectorAll('[role=\"tab\"],.q-tab'))"
            ".find(function(x){return /IR Review/i.test(x.textContent);});if(t){t.click();}}"
            "if(++n<9){setTimeout(go,450);}}setTimeout(go,250);})()"), once=True)

    lazy_panels = {
        t1.props["name"]: (p1, _render_lookback_tab),
        t2.props["name"]: (p2, _render_script_workflow_tab),
        t_prep.props["name"]: (p_prep, _render_prep_brief_tab),
        t3.props["name"]: (p3, _render_surprise_tracker_tab),
        t4.props["name"]: (p4, _render_transcripts_tab),
        t5.props["name"]: (p5, _render_narrative_momentum_tab),
        t6.props["name"]: (p6, _render_morning_after_tab),
    }
    from core import lazy_tab_probe
    lazy_tab_probe.register("Earnings", lazy_panels)   # no-op unless smoke is capturing
    loaded_tabs = {default_tab.props["name"]}

    async def _load_tab_on_demand(e):
        name = e.value
        # Keep the sidebar's sub-item highlight in sync with in-page tab clicks.
        nav.tab_changed(name)
        if name not in lazy_panels or name in loaded_tabs:
            return
        container, build_fn = lazy_panels[name]
        await asyncio.sleep(0)
        container.clear()
        # Previously: no try/except here. If build_fn() raised, the
        # container had already been cleared (spinner gone) and the
        # exception had nowhere to go but NiceGUI's own console logging —
        # the tab just stayed permanently blank with no on-screen sign
        # anything had gone wrong. Mirrors app_nicegui.py's page-level
        # "failed to load" banner (see render_page()) for the same failure
        # mode one level down, at the tab level. Only mark the tab as
        # loaded on SUCCESS, so switching away and back retries the build
        # instead of leaving a permanently-blank tab for the rest of the
        # session.
        try:
            with container:
                build_fn()
            loaded_tabs.add(name)
        except Exception:
            import traceback
            traceback.print_exc()
            container.clear()
            with container:
                ui.label("This tab failed to load").classes("text-lg font-bold").style(f"color:{COLORS['danger']};")
                ui.label("Something broke while rendering this tab. The exact error is in the server "
                         "console (the terminal window running app_nicegui.py) — copy it from there.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            ui.notify(f"{name} failed to load — see server console for the error.", type="negative")

    tabs.on_value_change(_load_tab_on_demand)


# ─────────────────────────────────────────────────────────────────────────
# Tab 0 — Prior Qtr Review
# ─────────────────────────────────────────────────────────────────────────
def _render_illustrative_lookback(prior_q, rec):
    """Prior Qtr Review post-mortem for illustrative demo tenants — driven entirely by the client's OWN
    seeded data (prior-quarter transcript summary + beat/miss log), never USIO's hardcoded numbers.
    See scripts/seed_earnings_demo.py."""
    surp = next((s for s in (_load_json("earnings_surprise_log.json", []) or [])
                 if s.get("quarter") == prior_q), None)
    if surp:
        ui.label(f"{prior_q} · as reported").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);letter-spacing:.05em;margin-top:2px;")
        _G, _B, _N, _R = "#15803D", "#1E40AF", "#64748B", "#B91C1C"
        beat = surp["rev_actual"] > surp["rev_consensus"]
        # EPS card carries YoY growth (needs a prior-year EPS on the record; omit the clause if absent).
        _epy = surp.get("eps_prior_year")
        _eps_yoy = f" · {(surp['eps_actual'] - _epy) / _epy * 100:+.0f}% YoY" if _epy else ""
        # Guidance card leads with the ACTION in professional IR terms (Raised / Maintained / Lowered /
        # Initiated), with the vs-Street read demoted to the subtitle. Falls back to the old vs-embedded
        # value if a record predates the guidance_action field.
        _gact = surp.get("guidance_action") or surp.get("guidance_vs_embedded") or "—"
        _gclr = {"Raised": _G, "Initiated": _G, "Maintained": _B, "Reiterated": _B, "Lowered": _R}.get(_gact, _B)
        _gsub = (f"{surp['guidance_vs_embedded']} the embedded bar"
                 if surp.get("guidance_vs_embedded") else "vs embedded bar")
        cards = [
            (f"{'+' if surp['ah_move'] >= 0 else ''}{surp['ah_move']*100:.1f}%", "AH Reaction",
             f"{surp['date']} · vs {surp['implied_move']*100:.0f}% implied", _G if surp["ah_move"] >= 0 else _R),
            (f"${surp['rev_actual']:.1f}M", "Revenue", f"vs ${surp['rev_consensus']:.1f}M cons "
             f"({'+' if beat else ''}{(surp['rev_actual']-surp['rev_consensus'])/surp['rev_consensus']*100:.1f}%)", _G if beat else _R),
            (f"${surp['eps_actual']:.2f}", "Adj. EPS", f"vs ${surp['eps_consensus']:.2f} cons{_eps_yoy}", _G),
            (_gact, "Guidance", _gsub, _gclr),
            (f"{surp['pt_changes']} PT raises", "Sell-side", f"avg +${surp['pt_change_avg']:.2f}", _N),
        ]
        with ui.row().classes("w-full gap-3"):
            for val, lbl, sub, clr in cards:
                with ui.card().classes("flex-1 text-center").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                    ui.label(val).classes("text-lg font-bold").style(f"color:{clr};")
                    ui.label(lbl).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);font-weight:600;")
                    ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

    _card_style = f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:10px;"

    with ui.card().classes("w-full").style(f"{_card_style}margin-top:12px;"):
        ui.label(f"{prior_q} call summary").classes("font-bold").style(
            f"color:{COLORS['accent_light']};font-size:var(--fs-md);")
        ui.label(rec["ai_summary"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);line-height:1.5;")

    with ui.row().classes("w-full gap-4 items-stretch").style("margin-top:4px;"):
        with ui.card().classes("flex-1").style(_card_style):
            kqs = rec.get("key_quotes") or []
            if kqs:
                ui.label("What management said").classes("font-bold").style(
                    f"color:{COLORS['accent_light']};font-size:var(--fs-base);")
                for kq in kqs:
                    ui.label(f"“{kq.get('quote','')}” — {kq.get('speaker','')}").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;")
            guid = rec.get("guidance_language") or []
            if guid:
                ui.label("Guidance language").classes("font-bold").style(
                    f"color:{COLORS['accent_light']};font-size:var(--fs-sm);margin-top:8px;")
                for g in guid:
                    ui.label(f"• {g}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
        with ui.card().classes("flex-1").style(_card_style):
            topics = rec.get("qa_risk_topics") or []
            if topics:
                ui.label("What analysts pressed on — carry into the Q2 script").classes("font-bold").style(
                    f"color:{COLORS['accent_light']};font-size:var(--fs-base);")
                sev = {"HIGH": "#B91C1C", "MEDIUM": "#B45309", "LOW": "#64748B"}
                for t in topics:
                    clr = sev.get(t.get("severity"), "#64748B")
                    with ui.row().classes("w-full items-start gap-2").style(
                            f"border-bottom:1px solid {COLORS['border']};padding:5px 0;"):
                        ui.label(t.get("severity", "?")).style(
                            f"background:{clr}22;color:{clr};font-size:var(--fs-2xs);font-weight:700;"
                            "padding:1px 7px;border-radius:9px;white-space:nowrap;")
                        with ui.column().classes("gap-0 flex-1"):
                            ui.label(t.get("topic", "")).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-weight:600;")
                            ui.label(t.get("why", "")).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    with ui.row().classes("gap-2").style("margin-top:8px;"):
        ui.button("Carry these into the Q2 script →",
                  on_click=lambda: nav.go_to("Earnings", "Script Generation")).props("flat dense color=primary")


def _render_lookback_tab():
    # Prior quarter + its real call date, derived — not hardcoded "Q1 2026 · May 13
    # · 72 minutes" (the 72-min length was invented; the date comes from the
    # ingested transcript when present).
    import re
    from core import transcripts
    _m = re.match(r"Q([1-4])\s+(\d{4})", CE().get("current_quarter", "") or "")
    if _m:
        _qn, _yr = int(_m.group(1)), int(_m.group(2))
        prior_q = f"Q{_qn-1} {_yr}" if _qn > 1 else f"Q4 {_yr-1}"
    else:
        prior_q = "the prior quarter"
    _rec = transcripts.get_transcript(prior_q) if prior_q != "the prior quarter" else None
    call_meta = "Chorus Call archive"
    if _rec and _rec.get("call_date"):
        try:
            _d = datetime.strptime(_rec["call_date"], "%Y-%m-%d")
            call_meta = f"{_d.strftime('%B')} {_d.day}, {_d.year} · Chorus Call archive"
        except ValueError:
            call_meta = f"{_rec['call_date']} · Chorus Call archive"

    ui.label(f"{prior_q} Call Post-Mortem — What the Script Taught Us").classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};")
    ui.label("Every Q2 script decision should start here. What worked, what was missed, and what analysts actually cared about.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    # Two ways to revisit last quarter's call, each a single clickable card (was: a replay card + a
    # separate "Play on Chorus Call" link doing the same thing + a text blurb with a "Go to Call
    # Transcripts" button). The whole card is the action now — think a big link.
    with ui.row().classes("w-full gap-3 items-stretch"):
        # LISTEN — the whole card opens the Chorus Call replay (folds in the old separate Play link).
        _listen = ui.card().classes("flex-1 cursor-pointer click-card").style(
            "background:#E8EEF7;border:1px solid #D3DBE4;border-radius:10px;")
        _listen.on("click", lambda: ui.navigate.to("https://www.choruscall.com", new_tab=True))
        _listen.tooltip("Play the replay on Chorus Call")
        with _listen, ui.row().classes("items-center gap-3 w-full no-wrap"):
            ui.icon("play_circle").style(f"color:{COLORS['accent']};font-size:var(--fs-3xl);")
            with ui.column().classes("gap-0"):
                ui.label(f"Listen — {prior_q} earnings call replay").classes("font-bold").style("color:#0F172A;")
                ui.label(f"{call_meta}  ·  Play on Chorus Call ↗").style("color:#475569;font-size:var(--fs-sm);")
        # READ — the whole card opens Call Transcripts (full-text search + the AI summary live there).
        _read = ui.card().classes("flex-1 cursor-pointer click-card").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:10px;")
        _read.on("click", lambda: nav.go_to("Earnings", "Call Transcripts"))
        _read.tooltip("Open the Call Transcripts tab — full-text search + AI summary")
        with _read, ui.row().classes("items-center gap-3 w-full no-wrap"):
            ui.icon("description").style(f"color:{COLORS['accent']};font-size:var(--fs-3xl);")
            with ui.column().classes("gap-0"):
                ui.label("Read the transcript").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                ui.label("Full-text search + AI summary  ·  Go to Call Transcripts ↗").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    # Everything below (reaction stats, section timing, Q&A topics, note alignment) is USIO's real,
    # ingested Q1 2026 transcript analysis — one specific quarter's data, NOT per-tenant config. It
    # must NOT render for another client: it would assert USIO's +24.22% / $25.47M as theirs. Until a
    # client's own prior call is ingested, show an honest waiting state instead of someone else's data.
    # Illustrative demo tenants get a data-driven post-mortem from their OWN seeded prior-quarter
    # transcript summary + beat/miss log — never USIO's hardcoded numbers (scripts/seed_earnings_demo.py).
    from config.client_config import get_active_client_id
    from core.curated_targets import _is_illustrative
    if _is_illustrative(get_active_client_id()) and _rec and _rec.get("ai_summary"):
        _render_illustrative_lookback(prior_q, _rec)
        return

    if CT("ticker") != "USIO":
        from page_modules_nicegui.signals import waiting_signal
        waiting_signal(
            f"{prior_q} post-mortem",
            f"Upload {CT('ticker')}'s {prior_q} earnings-call transcript (Call Transcripts tab) and its "
            "after-hours reaction to populate the reaction stats, section timing, Q&A topics and "
            "analyst-note alignment for this quarter.",
            "what the last script taught you — reaction, timing, and what analysts actually asked")
        return

    ui.label("Q1 2026 · as reported (ingested transcript)").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);letter-spacing:.05em;margin-top:2px;")
    with ui.row().classes("w-full gap-3"):
        for val, lbl, sub, clr in [
            ("+24.22%", "AH Reaction", "May 13 · record session", "#15803D"),
            ("$25.47M", "Q1 Revenue", "+16% YoY · record quarter", "#15803D"),
            ("$0.00 EPS", "First B/E quarter", "vs −$0.01 guided", "#15803D"),
            ("2.4x", "Volume vs avg", "Analyst interest spiked", "#1E40AF"),
            ("72 min", "Call length", "vs 65 min Q4 2025", "#64748B"),
        ]:
            with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                ui.label(val).classes("text-lg font-bold").style(f"color:{clr};")
                ui.label(lbl).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);font-weight:600;")
                ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

    with ui.row().classes("w-full gap-4 items-start"):
        with ui.column().classes("flex-[6]"):
            ui.label("Script Section Timing — Q1 2026 Actual").classes("font-bold").style("font-size:var(--fs-md);")
            ui.label("Compare against Q2 script once drafted. CEO historically runs long; CFO has tightened.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            for sec, actual, hist, clr, note in _Q1_SECTION_TIMING:
                delta = actual - hist
                delta_str = f"+{delta:.0f} min" if delta > 0 else (f"{delta:.0f} min" if delta < 0 else "on time")
                delta_clr = "#B91C1C" if delta > 0 else ("#15803D" if delta < 0 else COLORS["text_muted"])
                with ui.row().classes("w-full items-center gap-3").style(f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                    ui.label(sec).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);min-width:150px;")
                    ui.label(f"{actual:.0f} min").style(f"color:{clr};font-weight:bold;min-width:60px;")
                    ui.label(delta_str).style(f"color:{delta_clr};font-size:var(--fs-sm);min-width:70px;")
                    ui.label(note).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

            ui.label("Script Word Count — Q1 2026").classes("font-bold").style("margin-top:12px;")
            for sec, wc, hist_wc in _Q1_SECTION_WORDCOUNT:
                pct = min(int(wc / 2500 * 100), 100)
                vs_clr = "#B45309" if wc > hist_wc * 1.15 else COLORS["text_muted"]
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label(sec).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);min-width:150px;")
                    with ui.element("div").classes("flex-1").style(f"background:{COLORS['canvas_bg']};border-radius:4px;height:8px;overflow:hidden;"):
                        ui.element("div").style(f"width:{pct}%;height:100%;background:#3B82F6;")
                    ui.label(f"{wc:,}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);min-width:50px;")
                    ui.label(f"vs {hist_wc:,} hist").style(f"color:{vs_clr};font-size:var(--fs-xs);min-width:70px;")

            # Moved up into this column (was previously its own full-width
            # section below the row) — the left column ran noticeably
            # shorter than "Q&A Analysis + Post-Call Analyst Note Alignment"
            # on the right, leaving a large empty gap above where this used
            # to start. Stacking it here fills that space. The per-action
            # "impact" caption also moved from beside each card to beneath
            # it, since a side-by-side layout doesn't have room in a
            # 6/10-width column the way it did at full page width.
            ui.markdown("---")
            ui.label("Q1 → Q2 Script Actions").classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
            ui.label("Each item below is a direct fix from Q1 post-mortem.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

            for a in _get_current_qa_actions():
                with ui.row().classes("w-full items-start gap-3"):
                    ui.label(a["icon"]).style("font-size:var(--fs-hero);")
                    with ui.column().classes("flex-1 gap-1"):
                        with ui.card().classes("w-full").style(f"background:rgba(0,0,0,.15);border:1px solid {a['clr']};"):
                            ui.label(f"{a['priority']} · Q1 FINDING").style(f"color:{a['clr']};font-size:var(--fs-xs);font-weight:bold;text-transform:uppercase;")
                            ui.label(a["q1_finding"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                            ui.label(a["action"]).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:var(--fs-md);")
                            ui.label(f"{a['where']}").style(f"color:{a['clr']};font-size:var(--fs-sm);")
                        ui.label(a["impact"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;padding:0 4px;")
            ui.label("These same items now auto-seed Step 2 of each relevant persona's Script Canvas tab — "
                      "click Script Generation above to see them there, pre-filled and editable.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-top:6px;")

        with ui.column().classes("flex-[4]"):
            ui.label("Q&A Analysis — What Did Analysts Ask?").classes("font-bold").style("font-size:var(--fs-md);")
            ui.label("Pre-emption score: was this addressed proactively in the script, or did it surface as a question?").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            qa_topics = _Q1_QA_TOPICS
            for topic, preempted, note in qa_topics:
                clr = "#15803D" if preempted else "#B91C1C"
                icon = "" if preempted else ""
                with ui.row().classes("w-full items-start gap-2").style(f"padding:4px 0;"):
                    ui.label(icon)
                    with ui.column().classes("gap-0"):
                        ui.label(topic).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-weight:600;")
                        ui.label(note).style(f"color:{clr};font-size:var(--fs-sm);")

            preempted_count = sum(1 for _, p, _ in qa_topics if p)
            score = round(preempted_count / len(qa_topics) * 100)
            with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                ui.label("Pre-emption score — Q1 2026").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;")
                ui.label(f"{score}% · {preempted_count} of {len(qa_topics)} topics addressed proactively").classes("font-bold").style("color:#15803D;font-size:var(--fs-xl);")
                ui.label("Target for Q2: 90%+ · Key fix: interest income bridge language").style("color:#B45309;font-size:var(--fs-sm);")

            ui.label("Post-Call Analyst Note Alignment").classes("font-bold").style("margin-top:10px;")
            alignment = [
                ("Record revenue momentum", "HCW · Ladenburg both highlighted", "#15803D"),
                ("First B/E quarter", "HCW flagged as positive inflection", "#15803D"),
                ("PayFac growth conviction", "Ladenburg led note with PayFac thesis", "#15803D"),
                ("Interest income drag", "Ladenburg flagged as lingering uncertainty", "#B91C1C"),
                ("H2 margin expansion", "Neither analyst modeled the H2 improvement explicitly", "#B45309"),
            ]
            for takeaway, view, clr in alignment:
                icon = "" if clr == "#15803D" else ("" if clr == "#B45309" else "")
                with ui.column().classes("gap-0").style(f"border-bottom:1px solid {COLORS['border']};padding:5px 0;"):
                    ui.label(f"{icon} {takeaway}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-weight:600;")
                    ui.label(view).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")


def _metric(label, value, sub):
    with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(value).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);font-weight:600;")
        ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")


def _add_version(ss, tag, label, by):
    # Dedup guard — Stage 1-5 submit actions can in principle fire more than
    # once (e.g. a double-click); only record a version tag the first time.
    if not any(v.get("version") == tag for v in ss["versions"]):
        ss["versions"].append({"version": tag, "label": label, "created": datetime.now().strftime("%Y-%m-%d %H:%M"), "by": by})


# ─────────────────────────────────────────────────────────────────────────
# AI script drafting — same call pattern as investors_page.py's
# _structure_notes_with_ai (urllib.request + core.security.get_anthropic_
# api_key, claude-haiku-4-5), with a rule-based fallback per persona if the
# API call fails or no key is configured, so a draft is always available.
# ─────────────────────────────────────────────────────────────────────────
def _call_claude_script(prompt, max_tokens=500):
    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json", "x-api-key": get_anthropic_api_key(),
                     "anthropic-version": "2023-06-01"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
            return result["content"][0]["text"].strip()
    except Exception:
        return None


def _fallback_draft(role, n, what_new, ticker, ops=None, gd=None):
    """Built directly from the Stage 1 numbers (and, for CRO, Stage 1B
    operating metrics; for CEO, the Guidance & Outlook decision when
    available) — used whenever the Claude call fails or no API key is
    configured, so drafting never just breaks. IR/CFO/CEO openers reflect
    the same beat/in-line/miss read as the AI prompt's _TONE_RULES, so the
    fallback stays consistent even without the API."""
    ops = ops or {}
    gd = gd or {}
    contacts = _contacts()
    delta = (n.get("rev", 0) or 0) - (market_data.consensus_rev_value() or 0)
    bucket = "beat" if delta > 0.5 else ("miss" if delta < -0.5 else "inline")
    if role == "IR":
        opener = {"beat": "It was a record quarter",
                  "inline": "It was a solid quarter, in line with our commitment",
                  "miss": "We made continued sequential progress this quarter"}[bucket]
        return (f"Good afternoon, and thank you for joining {ticker}'s {CE().get('current_quarter','')} "
                f"earnings call. {opener}. Joining me today are {contacts['CEO']['name']} and {contacts['CFO']['name']}. "
                f"Before we begin, I'll remind everyone that today's call includes forward-looking statements "
                f"subject to risks and uncertainties described in our SEC filings.")
    if role == "CFO":
        beat = {"beat": "above", "inline": "in line with", "miss": "below"}[bucket]
        draft = (f"Total revenue for the quarter was ${n.get('rev',0):.1f}M, which came in {beat} Street "
                 f"consensus of ${market_data.consensus_rev_value() or 0:.1f}M. Gross margin was {n.get('gm',0):.1f}%, and "
                 f"Adjusted EBITDA was ${n.get('ebitda',0):.1f}M. GAAP EPS was ${n.get('eps',0):.2f}. SG&A "
                 f"totaled ${n.get('sga',0):.1f}M. We ended the quarter with ${n.get('cash',0):.1f}M in cash.")
        # Factual segment mix + sequential (QoQ) revenue trend, both from the filing's XBRL
        # (core.segments / core.edgar_financials). The segment mix frames payments vs print; the
        # sequential read gives the Q3→Q4→Q1 momentum the single-quarter number can't. Valuation
        # ARGUMENT stays in the prep-brief Q&A, not the spoken script.
        try:
            from core import earnings_prep
            seg = earnings_prep.segment_story()
            seq = earnings_prep.sequential_read()
        except Exception:
            seg = seq = None
        from core.curated_targets import _is_illustrative
        _illus = _is_illustrative(get_active_client_id())
        if seq and not _illus:
            draft += " " + seq
        if _illus and (n.get("integrated") or n.get("legacy")):
            _tot = (n.get("integrated", 0) or 0) + (n.get("legacy", 0) or 0)
            _mix = (n.get("integrated", 0) / _tot * 100) if _tot else 0
            draft += (f" Integrated payments contributed ${n.get('integrated',0):.1f}M — roughly {_mix:.0f}% of "
                      f"net revenue — with legacy processing of ${n.get('legacy',0):.1f}M the balance.")
        elif seg and not _illus:
            draft += (f" By segment, {seg['payments_label']} — our payments business — represented "
                      f"approximately {seg['payments_gp_share']:.0f}% of gross profit, with "
                      f"{', '.join(seg['other_labels'])}, our print-and-mail operations, making up the balance.")
        return draft
    if role == "CRO":
        from core.curated_targets import _is_illustrative
        if _is_illustrative(get_active_client_id()):
            # Northlake operates on the Street KPIs, not USIO's card/ACH/prepaid volume metrics.
            sentences = [
                f"On the operational metrics the Street tracks: integrated payments volume — our TPV — was "
                f"${n.get('tpv',0):.2f} billion, up {n.get('tpv_yoy',0):.0f}% year over year, as new-partner "
                f"go-lives and rising attach across the installed base both contributed.",
                f"Net revenue retention was {n.get('nrr',0):.0f}%, reflecting the durability of the partner book, "
                f"and net take-rate expanded to {n.get('take_rate',0):.0f} basis points — entirely from the mix "
                f"shift toward integrated acquiring, not pricing.",
                what_new or "Partner onboarding continued at a strong pace this quarter.",
            ]
            return " ".join(sentences)
        sentences = [f"Transaction volume processed grew {n.get('vol_yoy',0):.0f}% year-over-year to "
                     f"${n.get('vol',0):.1f}B, on {n.get('txn',0):.1f}M transactions."]
        if ops.get("card_yoy"):
            sentences.append(
                f"Card revenue grew {ops['card_yoy']:.0f}% year-over-year"
                + (f", with PayFac now representing {ops['payfac_pct']:.0f}% of card revenue" if ops.get("payfac_pct") else "")
                + (f" and card transactions up {ops['card_txn_yoy']:.0f}%" if ops.get("card_txn_yoy") else "")
                + "."
            )
        if ops.get("new_enterprise"):
            sentences.append(f"We completed implementations for {int(ops['new_enterprise'])} new enterprise "
                              f"account(s) this quarter.")
        if ops.get("rtp_txn_k"):
            sentences.append(f"Real-Time Payments processed approximately {int(ops['rtp_txn_k']):,}K "
                              f"transactions per month.")
        if ops.get("filtered_merchants"):
            sentences.append(f"Filtered Spend now has roughly {int(ops['filtered_merchants']):,} merchants live.")
        if ops.get("usio_one_example"):
            sentences.append(ops["usio_one_example"])
        sentences.append(what_new or "Operationally, the quarter continued the momentum from prior periods.")
        return " ".join(sentences)
    if role == "CEO":
        opener = {"beat": "This was a record quarter", "inline": "This was a solid, steady quarter",
                  "miss": "This quarter reflected continued progress against our long-term plan"}[bucket]
        if gd.get("action") and gd.get("new_low") is not None and gd.get("new_hi") is not None:
            action_lbl = {"raise_low": "raising the low end of our full-year guidance",
                          "raise_mid": "raising our full-year guidance",
                          "narrow": "narrowing our full-year guidance range",
                          "reiterate": "reiterating our full-year guidance"}.get(gd["action"], "updating our guidance")
            guidance_sentence = (f"Looking ahead, we are {action_lbl} to ${gd['new_low']:.1f}M to ${gd['new_hi']:.1f}M. "
                                  f"{gd.get('rationale','')}")
        else:
            guidance_sentence = (f"Looking ahead, we are reaffirming our full-year guidance of "
                                  f"{C().get('fy_guidance','10-12% revenue growth')}.")
        return (f"{opener} for {ticker}. "
                f"{what_new or 'We continue to execute against our long-term strategy.'} {guidance_sentence}")
    return ""


def _prior_year_quarters(cq, back=2):
    """['Q2 2025', 'Q2 2024'] from 'Q2 2026' — the SAME quarter across the prior `back` years. Onboarding
    downloads two years of transcripts per client, so the script generator frames YoY and pre-empts topics
    that recur year after year, not just react to last quarter."""
    import re as _re
    m = _re.match(r"Q([1-4])\s+(\d{4})", cq or "")
    if not m:
        return []
    qn, yr = int(m.group(1)), int(m.group(2))
    return [f"Q{qn} {yr - i}" for i in range(1, back + 1)]


def _prior_year_context():
    """Prompt context from the SAME quarter over the prior two years — summaries for YoY framing, plus the
    Q&A topics that RECUR across those calls (the persistent analyst concerns to pre-empt). Empty for a
    newly-onboarded client with no prior-year transcripts on file yet."""
    from core import transcripts
    cq = CE().get("current_quarter", "")
    ctx, topic_years = [], {}
    for pyq in _prior_year_quarters(cq, back=2):
        rec = transcripts.get_transcript(pyq)
        if rec and rec.get("ai_summary"):
            ctx.append(f"{pyq} — {rec['ai_summary']}")
            for t in (rec.get("qa_risk_topics") or []):
                _t = (t.get("topic") or "").strip()
                if _t:
                    topic_years.setdefault(_t, set()).add(pyq)
    if not ctx:
        return ""
    line = " Same quarter over the prior two years, for YoY framing: " + "  ||  ".join(ctx)
    recurring = [t for t, yrs in topic_years.items() if len(yrs) >= 2]
    if recurring:
        line += (" Q&A topics that RECUR in this quarter year after year — pre-empt them proactively rather "
                 "than let them surface: " + ", ".join(recurring[:5]) + ".")
    return line


def _generate_persona_draft(role, ss, context=""):
    """context is the combined Step 2 ("what's new") + Step 3 (final notes)
    text from that persona's script-canvas panel; falls back to Stage 1's
    shared what_new field if a persona hasn't filled in its own yet, so
    generation never has literally nothing to work with."""
    n = ss.get("q2_numbers", {})
    ops = ss.get("q2_ops_metrics", {})
    gd = ss.get("guidance_decision", {})
    what_new = context or n.get("what_new", "")
    ticker = CT("ticker", "")
    contacts = _contacts()
    tone = _tone_context(ss)
    tone_rule = _TONE_RULES.get(tone["bucket"], "")
    from core.curated_targets import _is_illustrative
    _illus = _is_illustrative(get_active_client_id())   # Northlake uses its Street KPIs, not USIO metrics

    if gd.get("action") and gd.get("new_low") is not None and gd.get("new_hi") is not None:
        guidance_line = (f"guidance action decided: {gd['action'].replace('_',' ')} to ${gd['new_low']:.1f}M-"
                          f"${gd['new_hi']:.1f}M ({gd.get('rationale','')})")
    else:
        guidance_line = f"reaffirming guidance of {C().get('fy_guidance','10-12% revenue growth')} (no formal guidance decision recorded yet — see the Guidance & Outlook Decision Engine above)"

    ops_bits = []
    if ops.get("card_yoy"):
        ops_bits.append(f"card revenue +{ops['card_yoy']:.0f}% YoY")
    if ops.get("payfac_pct"):
        ops_bits.append(f"PayFac {ops['payfac_pct']:.0f}% of card revenue")
    if ops.get("card_txn_yoy"):
        ops_bits.append(f"card transactions +{ops['card_txn_yoy']:.0f}% YoY")
    if ops.get("new_enterprise"):
        ops_bits.append(f"{int(ops['new_enterprise'])} new enterprise account(s) added")
    if ops.get("rtp_txn_k"):
        ops_bits.append(f"Real-Time Payments ~{int(ops['rtp_txn_k'])}K txn/month")
    if ops.get("filtered_merchants"):
        ops_bits.append(f"Filtered Spend ~{int(ops['filtered_merchants']):,} merchants live")
    if ops.get("usio_one_wins"):
        ops_bits.append(f"{int(ops['usio_one_wins'])} Usio ONE cross-sell win(s)")
    if ops.get("usio_one_example"):
        ops_bits.append(f"cross-sell example: {ops['usio_one_example']}")
    if ops.get("ach_txn_yoy"):
        ops_bits.append(f"ACH transactions +{ops['ach_txn_yoy']:.0f}% YoY")
    ops_text = "; ".join(ops_bits) if ops_bits else "no additional operating-metrics detail provided (Stage 1B not yet filled in)"

    # Consensus clause — a client with no sell-side coverage on file (a private-info
    # gap, common for micro-caps and any newly-onboarded tenant) has q2_consensus_rev
    # as None, not a number. Formatting None as ${:.1f} crashes, and printing "$0.0M
    # consensus" would fabricate a false zero. Say plainly there is none instead.
    # Consensus and the "tone vs Street" framing. A client with no sell-side coverage
    # on file (q2_consensus_rev is None — common for micro-caps and any newly-onboarded
    # tenant) breaks this two ways: formatting None as ${:.1f} crashes, and — subtler,
    # caught by running the WRAP demo — every prompt that carried "Tone read vs Street
    # consensus: ..." induced the model to FABRICATE a consensus beat out of the revenue
    # number (e.g. "$1.1M revenue ahead of consensus" when no consensus exists). So when
    # there is no consensus, drop the framing entirely and hard-forbid the comparison,
    # for EVERY persona prompt (IR/CFO/CEO all referenced it), not just the CFO's.
    _cons = market_data.consensus_rev_value()
    if isinstance(_cons, (int, float)) and _cons:
        cons_clause = f"Street consensus revenue was ${_cons:.1f}M. "
        tone_line = f"Tone read vs Street consensus: {tone['label']}. {tone_rule} "
    else:
        cons_clause = ""
        tone_line = ("No published sell-side consensus is on file for this name; do NOT state or "
                     "imply any beat, miss, or comparison versus consensus, and do not invent a "
                     "consensus figure. ")

    # Segment mix — factual, from the filing's XBRL segment data (core.segments). Gives the CFO a
    # line that frames the payments-vs-print mix so analysts value it correctly; the valuation
    # ARGUMENT (blended vs pure-play) stays in the prep brief's Q&A, out of the spoken script.
    seg_fact = seq_fact = ""
    if _illus:
        # Northlake's segments are integrated payments vs legacy processing (from the CFO numbers),
        # not USIO's payments/print XBRL — and the demo has no XBRL segment/sequential data anyway.
        _tot = (n.get("integrated", 0) or 0) + (n.get("legacy", 0) or 0)
        if _tot:
            seg_fact = (f" Segment mix to state factually: integrated payments ~{n.get('integrated',0)/_tot*100:.0f}% "
                        f"of net revenue (${n.get('integrated',0):.1f}M), legacy processing the balance "
                        f"(${n.get('legacy',0):.1f}M).")
    else:
        try:
            from core import earnings_prep as _ep
            _seg = _ep.segment_story()
            if _seg:
                seg_fact = (f" Segment mix to state factually (do NOT argue the valuation multiple): "
                            f"{_seg['payments_label']} ~{_seg['payments_gp_share']:.0f}% of gross profit — the "
                            f"payments business — with {', '.join(_seg['other_labels'])} (print-and-mail) the balance.")
            _seq = _ep.sequential_read()
            if _seq:
                seq_fact = f" Sequential (QoQ) revenue trend to weave in: {_seq}"
        except Exception:
            seg_fact = seq_fact = ""

    prompts = {
        "IR": f"Write a 2-3 sentence IR opening for {ticker}'s earnings call, introducing the speakers "
              f"({contacts['CEO']['name']} CEO, {contacts['CFO']['name']} CFO) and the standard "
              f"forward-looking-statements reminder. {tone_line}"
              f"What should change from last quarter's opening (see Step 1 review): "
              f"{what_new or 'no specific updates provided — keep the tone consistent with last quarter'}. "
              f"Professional, concise, plain text (no markdown).",
        "CFO": f"Write a CFO financial-review paragraph for an earnings call using these Q2 actuals: revenue "
               f"${n.get('rev',0):.1f}M, gross margin {n.get('gm',0):.1f}%, Adjusted EBITDA ${n.get('ebitda',0):.1f}M, "
               f"GAAP EPS ${n.get('eps',0):.2f}, SG&A ${n.get('sga',0):.1f}M, cash ${n.get('cash',0):.1f}M.{seq_fact}{seg_fact} "
               f"{cons_clause}{tone_line}What to address proactively this quarter (pre-empt any "
               f"prior-quarter item that previously drew analyst follow-up): "
               f"{what_new or 'no specific updates provided'}. Professional tone, plain text (no markdown), "
               f"4-6 sentences.",
        "CRO": (
            f"Write a business-operations paragraph for {ticker}'s earnings call covering the operational KPIs "
            f"the Street tracks: integrated payments volume (TPV) ${n.get('tpv',0):.2f}B, up "
            f"{n.get('tpv_yoy',0):.0f}% year over year; net revenue retention {n.get('nrr',0):.0f}%; and net "
            f"take-rate {n.get('take_rate',0):.0f} basis points (expanding on the mix shift toward integrated "
            f"acquiring, NOT pricing). What's new this quarter: {what_new or 'no specific updates provided'}. "
            f"Professional tone, plain text (no markdown), 3-5 sentences."
            if _illus else
            f"Write a business-operations paragraph for an earnings call covering: transaction volume "
            f"${n.get('vol',0):.1f}B (+{n.get('vol_yoy',0):.0f}% YoY), {n.get('txn',0):.1f}M transactions. "
            f"Additional operating detail from this quarter (Stage 1B): {ops_text}. "
            f"What's new this quarter: {what_new or 'no specific updates provided'}. Professional tone, plain "
            f"text (no markdown), 3-5 sentences."),
        "CEO": f"Write a CEO narrative paragraph for {ticker}'s earnings call covering strategic highlights, then "
               f"the guidance stance: {guidance_line}. {tone_line}"
               f"What's new/evolved since last quarter (see Step 1 review): "
               f"{what_new or 'continued execution against the long-term plan'}. Confident but not "
               f"promotional, plain text (no markdown), 4-6 sentences.",
    }
    # Prior TWO years of the same quarter (onboarding downloads two years of transcripts) — YoY framing +
    # recurring-topic pre-emption, appended to every persona prompt so the script isn't just reacting to
    # last quarter. Empty (no-op) for a client with no prior-year transcripts on file.
    _pyc = _prior_year_context()
    if _pyc:
        prompts = {k: v + _pyc for k, v in prompts.items()}
    draft = _call_claude_script(prompts.get(role, ""), 500)
    if draft:
        return draft, True
    return _fallback_draft(role, n, what_new, ticker, ops, gd), False


def _refine_persona_draft(current_text, instruction, role, ss):
    """Revise an EXISTING (possibly hand-edited) draft per a free-text instruction,
    in place — the conversational-editing counterpart to _generate_persona_draft's
    cold start. Same factual guardrails: it may reword, restructure, shorten, or
    change tone, but must not invent or alter financial figures, and must not
    manufacture a consensus beat when none is on file. Returns (text, was_ai).

    There is deliberately NO keyword fallback: a non-AI heuristic can't follow an
    arbitrary instruction, so when the model is unavailable we return the draft
    unchanged with was_ai=False and let the caller tell the user refine needs AI."""
    current_text = current_text or ""
    if not current_text.strip() or not (instruction or "").strip():
        return current_text, False

    # Reuse the same no-fabricated-consensus guardrail generation uses.
    _cons = market_data.consensus_rev_value()
    if isinstance(_cons, (int, float)) and _cons:
        cons_rule = (f"Street consensus revenue on file is ${_cons:.1f}M — reference it only if the draft "
                     f"already does; do not newly introduce a beat/miss framing.")
    else:
        cons_rule = ("No published sell-side consensus is on file for this name; do NOT state or imply any "
                     "beat, miss, or comparison versus consensus, and do not invent a consensus figure.")
    role_label = {"IR": "IR opening", "CFO": "CFO financial review",
                  "CRO": "business-operations section", "CEO": "CEO narrative"}.get(role, role)
    prompt = (
        f"You are refining the {role_label} of an earnings-call script for {CT('ticker', '')}. Below is the "
        f"CURRENT draft. Revise it to satisfy the INSTRUCTION, changing only what the instruction asks for and "
        f"preserving the rest.\n\n"
        f"STRICT RULES — these OVERRIDE the instruction wherever they conflict:\n"
        f"- Do NOT add, remove, or change any financial figure, percentage, or dollar amount already in the "
        f"draft, and do NOT introduce new numbers that aren't already there.\n"
        f"- Never state or imply that results beat, met, or missed analyst/Street consensus, estimates, or "
        f"expectations — or any comparison of the actuals to a target/prior period — unless that exact framing "
        f"is ALREADY present in the draft. {cons_rule} If the instruction asks you to add a beat/miss/exceeded/"
        f"in-line claim, silently OMIT that part and refine the rest.\n"
        f"- Do not fabricate figures, metrics, events, or quotes. You MAY incorporate a specific fact the "
        f"instruction ITSELF supplies (e.g. a customer name the user tells you to mention), phrased plainly and "
        f"not embellished beyond what the user gave. But if the instruction asks for a fact it does NOT supply, "
        f"insert a clearly bracketed [placeholder] for the IR person to fill rather than inventing it.\n"
        f"- Keep it professional and plain text (no markdown).\n\n"
        f"INSTRUCTION: {instruction.strip()}\n\n"
        f"CURRENT DRAFT:\n{current_text}\n\n"
        f"Return ONLY the revised section text — no preamble, no commentary, no explanation of what you changed."
    )
    revised = _call_claude_script(prompt, 600)
    if revised and revised.strip():
        return revised.strip(), True
    return current_text, False


def _refine_all_sections(ss, instruction):
    """Apply ONE free-text instruction across every prepared-remarks section at once —
    each active persona section AND the Guidance & Outlook section — running each
    through _refine_persona_draft so the same per-section, figure-protecting,
    no-fabrication guardrails apply everywhere. Non-destructive per section: a section
    with no draft yet, or one where the AI is unavailable, is left untouched. Returns a
    summary dict {changed, unchanged, skipped_empty, skipped_ai, sections[]} for the
    caller to report; persists once at the end if anything changed."""
    instruction = (instruction or "").strip()
    summary = {"changed": 0, "unchanged": 0, "skipped_empty": 0, "skipped_ai": 0, "sections": []}
    if not instruction:
        return summary

    def _apply(cur, role, label, setter):
        cur = cur or ""
        if not cur.strip():
            summary["skipped_empty"] += 1
            return
        revised, was_ai = _refine_persona_draft(cur, instruction, role, ss)
        if not was_ai:
            summary["skipped_ai"] += 1
            return
        if revised.strip() and revised.strip() != cur.strip():
            setter(revised)
            summary["changed"] += 1
            summary["sections"].append(label)
        else:
            summary["unchanged"] += 1

    for role, key, label in _active_personas():
        _apply(ss["script_text"].get(key), role, label,
                lambda v, key=key: ss["script_text"].__setitem__(key, v))

    # The Guidance & Outlook section is spoken by the CEO; refine it as a CEO section so
    # a script-wide tone/style instruction reaches it too (figure protection keeps the
    # guidance range intact). It lives in guidance_decision["text"], not script_text.
    gd = ss.get("guidance_decision") or {}

    def _set_guidance(v, gd=gd):
        gd["text"] = v
        ss["guidance_decision"] = gd
    _apply(gd.get("text"), "CEO", "Guidance & Outlook", _set_guidance)

    if summary["changed"]:
        _save_json("script_workflow_state.json", ss)
    return summary


# ─────────────────────────────────────────────────────────────────────────
# Guidance & Outlook Decision Engine — ported from app.py. This was flagged
# in an earlier pass of this port as a deliberate gap ("no such stage exists
# yet in this port") and the user confirmed it needed to be built. In the
# original, the CEO's narrative tone/H2-confidence language/closing are all
# supposed to flow from whichever guidance action (raise/reiterate/narrow)
# is decided here, so it renders ahead of the CEO's Step 1 review in
# _render_persona_steps below, and its decision feeds _generate_persona_draft's
# CEO prompt/fallback above (see the "gd"/guidance_line wiring there).
#
# FY prior-year quarterly actuals, seasonality weights, growth-range
# assumption, per-action range deltas, known H2 catalysts, and the closing/
# operator-handoff lines all moved from hardcoded module constants into
# CLIENT_REGISTRY's "guidance_policy" (config/client_config.py, CGP()
# accessor) 2026-07-12 — this is USIO's real business shape (Q2 heaviest,
# Q3 lightest, its own 10-12% growth policy, its own named H2 initiatives),
# not portable to another tenant as-is. _guidance_math/_guidance_range_for_
# action/_guidance_writing_rules below read CGP() at call time instead. A
# client with no "guidance_policy" configured gets an empty dict back and
# the math honestly reads as zeros rather than silently reusing USIO's
# numbers — same "disclosed approximation" philosophy as core/risk_scorecard.py.
#
# Louis Hoch's prior guidance quotes (_GUIDANCE_PRIOR_QUOTES) are still a
# one-time historical snapshot (like _PERSONA_LAST_QUARTER above) — this is
# category 2 from config/client_config.py's docstring gap-inventory
# (verbatim historical call content), which needs a transcript-driven
# extraction feature, not a config move; left as-is intentionally.
#
# Q2 2025 was depressed ~$2M by a one-time amusement-park card-issuing loss
# (normalized Q2 2025 ~$21.9M) — the Q2 2026 YoY comp will look inflated as
# a result; the guidance AI prompt below is told to acknowledge the easy comp.
#
# The scenario recommendation and per-action range math are a SEPARATE
# signaling system from _TONE_RULES/_tone_context above (that one governs
# word-choice register across all four persona drafts; this one governs the
# guidance-range decision and its own script language) — the two do
# interact at generation time (the AI prompt below imports the tone read),
# matching how the original's guidance prompt pulled in its global tone
# selector too.
# ─────────────────────────────────────────────────────────────────────────
_GUIDANCE_ACTIONS = [
    ("raise_low", "RAISE — Increase the low end of the range (most common beat action at Q2)"),
    ("raise_mid", "RAISE — Increase the midpoint (strong beat + strong H2 visibility required)"),
    ("reiterate", "REITERATE — Maintain full range (conservative; appropriate after Q1-level beat at Q2)"),
    ("narrow", "NARROW — Tighten the range without raising (signals H2 visibility but not confidence)"),
]
_GUIDANCE_ACK = {
    "raise_low": "Raise low end selected — script will bank the Q2 beat into the guidance floor.",
    "raise_mid": "Raise midpoint selected — strongest signal; requires strong H2 visibility confirmation.",
    "reiterate": "Reiterate selected — conservative; Street will accept given Q1-level beat already banked.",
    "narrow": "Narrow selected — signals H2 visibility improving without committing to a higher midpoint.",
}
_GUIDANCE_PRIOR_QUOTES = [
    ("Q1 2026", "We have every reason to be optimistic about 2026. We currently are. At the same time, we also "
                "believe it's prudent to be cautious early in the year. For that reason, we're reiterating our "
                "guidance. We expect 10%-12% revenue growth in 2026, while also anticipating continued positive "
                "adjusted EBITDA."),
    ("Q4 2025", "We've got a lot in motion, so it'll be critical this year to focus on completing those tasks that "
                "offer the most immediate return on our investment. For that reason, we're being careful on our "
                "guidance."),
    ("Q3 2025", "There is a great sense that we're on the verge of a potential inflection point that should follow "
                "the momentum that we've been building."),
]


# ── Tenant gates for the two hardcoded USIO snapshots above ──
# _PERSONA_LAST_QUARTER and _GUIDANCE_PRIOR_QUOTES are USIO's real, one-quarter
# content. They are hardcoded because the proper source — transcript-driven
# extraction from an ingested/summarized call (core.transcripts key_quotes /
# guidance_language) — is not built yet. Until it is, render them ONLY for USIO;
# for any other tenant they would be a leak (USIO's words on someone else's
# script), so these accessors return empty and the consuming UI shows a clean
# "nothing on file" state instead. Every consumer reads through these, never the
# constants directly — the single-read-point pattern used for _fls_items().
def _persona_last_quarter():
    # USIO's curated constants win (hand-tuned tone tags, rows, prior_quotes). Every other
    # tenant is transcript-driven: persona quotes extracted from its OWN latest summarized
    # call, or empty if none is on file. See core.transcripts.script_inputs().
    if get_active_client_id() == "usio":
        return _PERSONA_LAST_QUARTER
    from core import transcripts
    return transcripts.script_inputs().get("persona_refs", {})


def _guidance_prior_quotes():
    if get_active_client_id() == "usio":
        return _GUIDANCE_PRIOR_QUOTES
    from core import transcripts
    return transcripts.script_inputs().get("guidance_quotes", [])


def _guidance_writing_rules():
    """AI-prompt writing rules for the Guidance & Outlook draft — built from
    the active client's seasonal_weights/closing_line/operator_handoff
    (CGP()) instead of a hardcoded module string, so the seasonal framing
    and exact closing/handoff lines are correct for whichever client is
    active. Falls back to generic phrasing for any piece a client hasn't
    configured, rather than silently inheriting USIO's."""
    policy = CGP()
    weights = policy.get("seasonal_weights", {})
    company = CT("name", CT("ticker", "the company"))
    seasonal_line = (
        f"Always reference seasonal targets, not naive quarterly averages — Q3 is {company}'s lightest quarter "
        f"(~{weights['Q3']*100:.0f}% of FY), Q2 its heaviest (~{weights['Q2']*100:.0f}%). "
        if weights.get("Q1") is not None and weights.get("Q2") and weights.get("Q3")
        else "Always reference seasonal targets, not naive quarterly averages. "
    )
    closing_line = policy.get("closing_line", "").strip()
    handoff = policy.get("operator_handoff", "").strip()
    closing_bit = f"Close with the exact line: '{closing_line}' " if closing_line else ""
    handoff_bit = f"End with the exact operator handoff: '{handoff}'" if handoff else ""
    return (
        f"{seasonal_line}Cite at least 2 named H2 catalysts from the list provided, not generic optimism. Mark "
        f"every specific forward-looking numeric claim with [FLS] ... [/FLS] for Legal review. Never use the word "
        f"'cautious' when raising guidance — that undercuts the raise. {closing_bit}{handoff_bit}"
    ).strip()


def _guidance_math(ss):
    """Thin wrapper — the seasonal read now lives in core.guidance_engine, the
    single source of truth shared with the Markets 'Update guidance' impact
    panel so the two screens can never compute different numbers. Kept as a
    named function here because other modules already import it."""
    return guidance_engine.seasonal_read(ss)


def _guidance_range_for_action(action, math_):
    """Thin wrapper — the verb→numbers translation now lives in
    core.guidance_engine.apply_action so the write-through to period_guidance
    and any other consumer share one definition."""
    return guidance_engine.apply_action(action, math_)


_VERDICT_STYLE = {
    "material_gap": ("#B91C1C", "MATERIAL GAP"),
    "unaddressed": ("#B45309", "NOT ADDRESSED"),
    "probing": ("#1E40AF", "PROBING"),
    "ritual": ("#64748B", "RITUAL"),
}


def _prep_vs_actual(quarter, ss, force=False):
    """Loop-closer: grade THIS quarter's prep against what actually happened on the call.
    (a) Script fidelity — our drafted prepared remarks vs the transcript's prepared section:
        which planned points were delivered, dropped/softened, or improvised.
    (b) Q&A prediction accuracy — our adversarial-Q&A predictions vs the actual analyst
        questions: hits, misses, and surprises, with a hit rate.
    Two on-demand model calls comparing the two given texts (it summarizes/compares what's
    there — it does not assert company facts of its own). Cached in ss['prep_vs_actual']
    [quarter]. Returns the dict, or None if there's no transcript or no drafted script."""
    cache = (ss.get("prep_vs_actual") or {}).get(quarter)
    if cache and not force:
        return cache
    from core import morning_after, transcripts
    rec = transcripts.get_transcript(quarter)
    if not rec or not (rec.get("full_text") or "").strip():
        return None
    planned_script = _assembled_script_text(ss)
    if not planned_script.strip():
        return None
    predictions = [it.get("question", "") for it in (ss.get("adversarial_qa") or {}).get("items", [])
                   if it.get("question")]
    prepared_actual, qa_actual, _ = morning_after.split_prepared_qa(rec["full_text"])

    out = {"generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
           "script": {"delivered": [], "dropped": [], "improvised": []},
           "qa": {"hits": [], "misses": [], "surprises": [], "hit_rate": None},
           "had_predictions": bool(predictions)}

    # (a) Script fidelity — planned prepared remarks vs actual prepared remarks.
    sp = (f"You are comparing an IR team's PLANNED earnings-call prepared remarks against what management "
          f"ACTUALLY said. Base everything ONLY on the two texts below; do not infer facts not present.\n\n"
          f"PLANNED SCRIPT:\n{planned_script[:6000]}\n\n"
          f"ACTUAL PREPARED REMARKS (from the transcript):\n{(prepared_actual or '')[:6000]}\n\n"
          f"List, each on its own line, using EXACTLY these prefixes:\n"
          f"DELIVERED: <a substantive planned point management did make>\n"
          f"DROPPED: <a substantive planned point that was NOT made or was materially softened — and why it matters>\n"
          f"IMPROVISED: <a substantive point management made that was NOT in the plan>\n"
          f"Up to 5 of each, most important first. Output only those lines, nothing else.")
    raw = _call_claude_script(sp, 900)
    for line in (raw or "").splitlines():
        s = line.strip()
        for pref, key in (("DELIVERED:", "delivered"), ("DROPPED:", "dropped"), ("IMPROVISED:", "improvised")):
            if s.upper().startswith(pref):
                v = s[len(pref):].strip()
                if v:
                    out["script"][key].append(v)
                break

    # (b) Q&A prediction accuracy — our predicted questions vs the actual Q&A.
    if predictions and (qa_actual or "").strip():
        pred_block = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(predictions))
        qp = (f"An IR team PREDICTED the tough analyst questions below before the call. Compare them to the "
              f"ACTUAL Q&A from the transcript. Base everything ONLY on the texts.\n\n"
              f"PREDICTED QUESTIONS:\n{pred_block}\n\n"
              f"ACTUAL Q&A (transcript):\n{qa_actual[:6000]}\n\n"
              f"Output lines using EXACTLY these prefixes:\n"
              f"HIT: <the predicted question, briefly> || <how the analyst actually framed it, brief>\n"
              f"MISS: <the predicted question, briefly>\n"
              f"SURPRISE: <an actual analyst question the prediction list did NOT anticipate>\n"
              f"You MUST output exactly one HIT or MISS line for EACH of the {len(predictions)} numbered "
              f"predicted questions above — no prediction may be left out. Then up to 5 SURPRISE lines. "
              f"Output only those lines.")
        raw2 = _call_claude_script(qp, 900)
        for line in (raw2 or "").splitlines():
            s = line.strip()
            if s.upper().startswith("HIT:"):
                q, _, framed = s[4:].strip().partition("||")
                out["qa"]["hits"].append({"pred": q.strip(), "actual": framed.strip()})
            elif s.upper().startswith("MISS:"):
                out["qa"]["misses"].append(s[5:].split("||")[0].strip())
            elif s.upper().startswith("SURPRISE:"):
                out["qa"]["surprises"].append(s[9:].split("||")[0].strip())
        h, m = len(out["qa"]["hits"]), len(out["qa"]["misses"])
        if h + m:
            out["qa"]["hit_rate"] = round(100 * h / (h + m))

    # Accrue this call's outcomes into the house Q&A bank — surprises (questions we
    # didn't predict) feed BOTH this client's history and the global house book, so
    # they seed every future adversarial pass. Idempotent per question text.
    try:
        from core import qa_bank
        from config.client_config import get_active_client_id
        hit_texts = [x.get("pred", "") for x in out["qa"]["hits"] if x.get("pred")]
        out["accrued"] = qa_bank.accrue(get_active_client_id(), quarter, out["qa"]["surprises"], hit_texts)
    except Exception as exc:
        print(f"[prep_vs_actual] qa_bank accrual skipped: {exc}")
        out["accrued"] = {"new_global": 0, "new_client": 0}

    ss.setdefault("prep_vs_actual", {})[quarter] = out
    _save_json("script_workflow_state.json", ss)
    return out


def _quarter_sort_key(q):
    """Chronological sort key for a quarter label like 'Q2 2026' -> (2026, 2)."""
    import re
    yr = re.search(r"(20\d\d)", q or "")
    qn = re.search(r"[Qq]\s*([1-4])", q or "")
    return (int(yr.group(1)) if yr else 9999, int(qn.group(1)) if qn else 9)


def _prep_accuracy_series(ss):
    """Every quarter with a recorded prep-vs-actual hit rate, chronologically —
    the cross-quarter prediction-accuracy trend."""
    pts = []
    for q, rec in (ss.get("prep_vs_actual") or {}).items():
        qa = (rec or {}).get("qa") or {}
        hr = qa.get("hit_rate")
        if hr is None:
            continue
        h, m = len(qa.get("hits") or []), len(qa.get("misses") or [])
        pts.append({"quarter": q, "rate": hr, "hits": h, "total": h + m,
                    "surprises": len(qa.get("surprises") or [])})
    pts.sort(key=lambda p: _quarter_sort_key(p["quarter"]))
    return pts


def _render_prep_accuracy_trend(ss):
    """A compact cross-quarter trend of the adversarial pass's prediction accuracy —
    shows the loop compounding as the house bank learns. Rendered only with 2+ quarters."""
    pts = _prep_accuracy_series(ss)
    if len(pts) < 2:
        return
    latest, prev = pts[-1], pts[-2]
    delta = latest["rate"] - prev["rate"]
    dclr = "#15803D" if delta > 0 else ("#B91C1C" if delta < 0 else COLORS["text_muted"])
    arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")

    ui.label("Prediction accuracy over time").classes("section-head").style("margin-top:14px;")
    ui.label("How often the adversarial pass predicted the questions analysts actually asked. It should climb "
             "as the house Q&A bank accrues each call's surprises and seeds the next pass.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    ui.label(f"{arrow} {abs(delta)} pts vs {prev['quarter']} — now {latest['rate']}% ({latest['hits']} of "
             f"{latest['total']} predicted).").style(f"color:{dclr};font-size:var(--fs-sm);font-weight:600;margin-top:2px;")

    for p in pts:
        is_latest = p is latest
        bar_clr = COLORS["accent"] if is_latest else COLORS["accent_light2"]
        with ui.row().classes("w-full items-center").style("gap:8px;margin-top:3px;"):
            ui.label(p["quarter"]).style(
                f"color:{COLORS['text_body']};font-size:var(--fs-sm);width:84px;"
                f"font-weight:{'700' if is_latest else '400'};")
            with ui.element("div").style(
                    f"flex:1;height:12px;background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                    "border-radius:6px;overflow:hidden;"):
                ui.element("div").style(f"height:100%;width:{max(2, min(100, p['rate']))}%;background:{bar_clr};")
            ui.label(f"{p['rate']}%  ·  {p['hits']}/{p['total']}").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);width:96px;text-align:right;"
                "font-variant-numeric:tabular-nums;")


def _render_prep_vs_actual(ss, quarter):
    """Render the prep-vs-actual loop-closer (see _prep_vs_actual) — an on-demand,
    cached comparison of this quarter's drafted script + predicted Q&A against the call."""
    ui.label("Prep vs. Actual — how good was our prep?").classes("section-head").style("margin-top:12px;")
    ui.label("Closes the loop: your drafted script and the tough questions you predicted, graded against what "
             "management actually said and what analysts actually asked on this call.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    box = ui.column().classes("w-full")

    def _paint(data):
        box.clear()
        with box:
            if not data:
                ui.label("Run it to compare your prep against the call. Needs a drafted script (Script "
                         "Generation) and this quarter's transcript; predicted questions come from the "
                         "Adversarial analyst pass.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                return
            ui.label(f"Generated {data['generated_at']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            sc = data["script"]
            with ui.row().classes("w-full gap-3").style("margin-top:4px;"):
                _metric_card("Delivered", str(len(sc["delivered"])), "planned points that landed", "#15803D")
                _metric_card("Dropped", str(len(sc["dropped"])), "planned but not said",
                             "#B91C1C" if sc["dropped"] else "#15803D")
                _metric_card("Improvised", str(len(sc["improvised"])), "said, not planned",
                             "#B45309" if sc["improvised"] else COLORS["text_muted"])
            for title, key, clr in (("Dropped from the plan", "dropped", "#B91C1C"),
                                    ("Improvised — off script", "improvised", "#B45309"),
                                    ("Delivered as planned", "delivered", "#15803D")):
                for v in sc[key]:
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                            f"border-left:3px solid {clr};padding:5px 10px;margin-top:3px;"):
                        ui.label(f"{title}").style(f"color:{clr};font-size:var(--fs-xs);font-weight:700;")
                        ui.label(v).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")

            qa = data["qa"]
            if data.get("had_predictions"):
                ui.label("Q&A predictions — did we see them coming?").classes("section-head").style("margin-top:10px;")
                total = len(qa["hits"]) + len(qa["misses"])
                hr = qa["hit_rate"]
                hr_clr = "#15803D" if (hr or 0) >= 60 else ("#B45309" if (hr or 0) >= 30 else "#B91C1C")
                with ui.row().classes("w-full gap-3"):
                    _metric_card("Hit rate", f"{hr}%" if hr is not None else "—",
                                 f"{len(qa['hits'])} of {total} predicted", hr_clr)
                    _metric_card("Predicted & asked", str(len(qa["hits"])), "we saw it coming", "#15803D")
                    _metric_card("Missed", str(len(qa["misses"])), "predicted, didn't come up",
                                 COLORS["text_muted"])
                    _metric_card("Surprises", str(len(qa["surprises"])), "asked, we didn't predict",
                                 "#B91C1C" if qa["surprises"] else "#15803D")
                acc = data.get("accrued") or {}
                if acc.get("new_global"):
                    ui.label(f"✓ {acc['new_global']} new surprise(s) added to the house Q&A bank — they'll seed "
                             "future adversarial passes for every client.").style(
                        "color:#15803D;font-size:var(--fs-xs);font-weight:600;margin-top:2px;")
                elif acc.get("new_client"):
                    ui.label(f"✓ {acc['new_client']} new question(s) banked for this client — they'll seed future "
                             "adversarial passes here.").style(
                        "color:#15803D;font-size:var(--fs-xs);font-weight:600;margin-top:2px;")
                for h in qa["hits"]:
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                            "border-left:3px solid #15803D;padding:5px 10px;margin-top:3px;"):
                        ui.label(f"HIT · {h['pred']}").style("color:#15803D;font-size:var(--fs-sm);font-weight:600;")
                        if h.get("actual"):
                            ui.label(f"Asked as: {h['actual']}").style(
                                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;")
                for s in qa["surprises"]:
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                            "border-left:3px solid #B91C1C;padding:5px 10px;margin-top:3px;"):
                        ui.label(f"SURPRISE · {s}").style("color:#B91C1C;font-size:var(--fs-sm);font-weight:600;")
                        ui.label("Banked → seeds next quarter's adversarial pass.").style(
                            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                for mtext in qa["misses"]:
                    ui.label(f"Missed (predicted, not asked): {mtext}").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            else:
                ui.label("No adversarial-Q&A predictions on file — run the Adversarial analyst pass on the "
                         "Script Generation tab to also grade Q&A prediction accuracy.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:6px;")

    _paint((ss.get("prep_vs_actual") or {}).get(quarter))

    async def _run():
        ui.notify("Comparing your prep against the call — two model passes…", type="info")
        try:
            data = await asyncio.to_thread(_prep_vs_actual, quarter, ss, True)
        except Exception as e:
            ui.notify(f"Comparison failed: {e}", type="negative")
            return
        if not data:
            ui.notify("Needs a drafted script and a transcript for this quarter.", type="warning")
            return
        _paint(data)
        ui.notify("Done — see how the prep held up.", type="positive")

    have = bool((ss.get("prep_vs_actual") or {}).get(quarter))
    ui.button("Re-run prep comparison" if have else "Compare prep vs. this call",
              icon="compare_arrows", on_click=_run).props("color=primary dense").style("margin-top:4px;")


def _render_morning_after_tab():
    """Post-call critique (core.morning_after): what the tape did, how the call
    was delivered, and what the Q&A actually exposed — material gaps first."""
    from core import morning_after, transcripts
    ss = _load_json("script_workflow_state.json", None) or {}

    ui.label("Morning After — post-call critique").classes("text-lg font-bold")
    ui.label("What the tape did, how the call ran, and what the Q&A exposed. The Q&A is an arena: "
             "analysts must ask something to be on record, and most questions fish for incremental "
             "colour you can't pre-empt. Only questions with evidence behind them — management "
             "couldn't answer, conceded something the script framed as upside, or the topic recurs — "
             "count against the script.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    quarters = [t["quarter"] for t in sorted((transcripts.list_transcripts() or []),
                                             key=lambda x: x.get("call_date") or "", reverse=True)]
    if not quarters:
        ui.label("No transcripts ingested yet — add one on the Call Transcripts tab.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-top:8px;")
        return

    state = {"q": quarters[0]}
    with ui.row().classes("items-center gap-2").style("margin-top:6px;"):
        ui.label("Quarter").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        sel = ui.select(quarters, value=quarters[0]).props("dense outlined").classes("min-w-[130px]")

    @ui.refreshable
    def _body():
        # Loop-closer first: how did this quarter's prep hold up against the call?
        _render_prep_vs_actual(ss, state["q"])
        # …and the cross-quarter arc, so the compounding is visible (2+ quarters).
        _render_prep_accuracy_trend(ss)
        ui.markdown("---")
        try:
            c = morning_after.critique(state["q"])
        except Exception as e:
            ui.label(f"Critique unavailable: {e}").style("color:#B45309;font-size:var(--fs-sm);")
            return
        if not c:
            ui.label("Nothing to critique for that quarter.").style(f"color:{COLORS['text_muted']};")
            return
        r, t, p = c.get("reaction"), c.get("timing"), c.get("preempt")

        # ── The tape ────────────────────────────────────────────────────────
        if r:
            drift = r["next_day_pct"] - r["pct"]
            gap_clr = "#15803D" if r["pct"] >= 0 else "#B91C1C"
            close_clr = "#15803D" if r["next_day_pct"] >= 0 else "#B91C1C"
            with ui.row().classes("w-full gap-3").style("margin-top:8px;"):
                _metric_card("Call-day close", f"${r['close']:.2f}", "last print before they digested it")
                _metric_card("Overnight gap", f"{r['pct']:+.2f}%", f"opened ${r['next_open']:.2f}", gap_clr)
                _metric_card("Next close", f"{r['next_day_pct']:+.2f}%", f"cumulative · {r['next_volume']:,} sh", close_clr)
                _metric_card("Moved after open", f"{drift:+.2f}pp",
                             "digested through the session" if abs(drift) > abs(r["pct"]) else "verdict was at the bell")
            ui.label("Close-to-next-open. After-hours is excluded: on a micro-cap those are market-maker "
                     "quotes that print but can't be traded.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

        # ── Delivery ────────────────────────────────────────────────────────
        if t:
            ui.label("Delivery (measured from the transcript's own timestamps)").classes(
                "section-head").style("margin-top:12px;")
            if not t.get("reliable"):
                with ui.card().classes("w-full").style(
                        f"background:{COLORS['surface_bg']};border:1px solid #B45309;"
                        "border-left:3px solid #B45309;padding:6px 10px;"):
                    ui.label("Timing withheld — this transcript's labelling can't support it").style(
                        "color:#B45309;font-size:var(--fs-sm);font-weight:700;")
                    for w in t["warnings"]:
                        ui.label("• " + w).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    ui.label("The tape and Q&A findings below are unaffected — they come from the text "
                             "and the market, not the speaker labels.").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            else:
                with ui.row().classes("w-full gap-3"):
                    _metric_card("Prepared", f"{t['prepared_minutes']} min", "management only")
                    _metric_card("Q&A", f"{t['qa_minutes']} min", "")
                    _metric_card("Total", f"{t['total_minutes']} min", f"operator {t['operator_minutes']} min")
                for s in t["by_speaker"]:
                    with ui.row().classes("w-full items-center gap-2").style(
                            f"border-bottom:1px solid {COLORS['border']};padding:3px 0;"):
                        ui.label(s["speaker"]).style(
                            f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-weight:600;width:110px;")
                        ui.label(f"{s['minutes']} min").style(f"color:{COLORS['accent']};font-size:var(--fs-sm);width:70px;")
                        ui.label(f"{s['wpm']} wpm").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);width:70px;")
                        ui.label(", ".join(s.get("raw", []))[:70]).style(
                            f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")

        # ── Non-answers (published classifier + base rate) ───────────────────
        na = c.get("non_answers")
        if na:
            ui.label("Non-answers — did management actually answer?").classes(
                "section-head").style("margin-top:12px;")
            ui.label("Gow, Larcker & Zakolyukina (2021), J. Accounting Research 59(4) — their regex "
                     "classifier (78.9% out-of-sample true-positive, 89.2% accuracy). The number only "
                     "means something against their benchmark: ~11% of responses across all firms are "
                     "non-answers, stable over time and across industries. 11% is NORMAL.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            rate_pct = na["rate"] * 100
            if not na["labels_reliable"]:
                rate_clr = "#B45309"
            elif rate_pct > 14:
                rate_clr = "#B91C1C"
            elif rate_pct < 7:
                rate_clr = "#15803D"
            else:
                rate_clr = COLORS["accent"]
            with ui.row().classes("w-full gap-3").style("margin-top:4px;"):
                _metric_card("Non-answer rate", f"{rate_pct:.0f}%",
                             f"{na['non_answers']} of {na['responses']} responses", rate_clr)
                _metric_card("vs 11% norm",
                             (f"{na['vs_benchmark_pp']:+.1f}pp" if na["vs_benchmark_pp"] is not None else "—"),
                             "p25 7% · p75 14%", rate_clr)
                _metric_card("Refuse / Unable / Offline",
                             f"{na['by_type']['REFUSE']} / {na['by_type']['UNABLE']} / {na['by_type']['AFTERCALL']}",
                             "won't / can't / deflect")
            if not na["labels_reliable"]:
                ui.label("⚠ Rate is indicative only — this transcript mis-attributes management turns, "
                         "so the denominator mixes speakers. The flagged phrases below are still real.").style(
                    "color:#B45309;font-size:var(--fs-xs);")
            ui.label(na["read"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);margin-top:2px;")
            for f in na["flagged"]:
                with ui.card().classes("w-full").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                        "border-left:3px solid #B45309;padding:6px 10px;margin-top:3px;"):
                    ui.label(f"{' + '.join(f['types'])} · {f['speaker']}").style(
                        "color:#B45309;font-size:var(--fs-sm);font-weight:700;")
                    ui.label(f"flagged phrase: \"{f['hits'][0]['phrase']}\"").style(
                        f"color:{COLORS['text_body']};font-size:var(--fs-xs);")
                    ui.label(f["excerpt"]).style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;")
            if not na["flagged"]:
                ui.label("No non-answers detected — management engaged every question. Against an ~11% "
                         "norm that is genuinely unusual, and worth protecting.").style(
                    "color:#15803D;font-size:var(--fs-xs);margin-top:2px;")

        # ── What the Q&A DEMANDED (number_frame) ────────────────────────────
        ui.label("What the Q&A demanded — and whether you delivered it").classes(
            "section-head").style("margin-top:12px;")
        ui.label("Every analyst question anchors on a number, and the analyst has ALREADY judged it. "
                 "The valence sets what the answer owes: a GOOD number must be shown to REPEAT "
                 "(run-rate or one-timer?); a BAD number needs CONTROL and TIMING (yours to fix, and "
                 "by when?); a CLAIM or guide needs BACKING (what's signed vs assumed?). A mismatch "
                 "isn't evasion — it's usually a good answer to a question nobody asked.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

        fr = c.get("frames")
        fbox = ui.column().classes("w-full")

        def _render_frames(f):
            fbox.clear()
            with fbox:
                if not f:
                    ui.label("Not analysed yet — this runs a model call per exchange, so it's on "
                             "demand and the result is stored.").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                    return
                with ui.row().classes("w-full gap-3").style("margin-top:4px;"):
                    _metric_card("Pressed & unmet", str(f.get("mismatches", 0)),
                                 "they pushed back — fix first",
                                 "#B91C1C" if f.get("mismatches") else "#15803D")
                    _metric_card("Deferred", str(f.get("deferred", 0)),
                                 "they'll get it on the callback — the market won't", "#B45309")
                    _metric_card("Withheld", str(f.get("withheld", 0)),
                                 "competitive — correct to refuse")
                    _metric_card("Discharged", str(f.get("discharged", 0)),
                                 f"of {f.get('numeric_questions',0)} numeric", "#15803D")
                ui.label("DEFERRED is the cheap one: nobody pushed back, so nobody in the room knows "
                         "it's missing — the analyst simply picks it up on the callback afterwards, "
                         "and every other holder is left without it. WITHHELD is competitively "
                         "sensitive and correct to refuse; the cost is market uncertainty, which is a "
                         "trade rather than a mistake.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                order = {"MISMATCH": 0, "DEFERRED": 1, "WITHHELD": 2, "DISCHARGED": 3, "NOT_NUMERIC": 4}
                for x in sorted(f.get("frames", []), key=lambda z: order.get(z.get("verdict"), 9)):
                    if x.get("verdict") == "NOT_NUMERIC":
                        continue
                    v = x.get("verdict")
                    clr = {"MISMATCH": "#B91C1C", "DEFERRED": "#B45309",
                           "WITHHELD": "#64748B"}.get(v, "#15803D")
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                            f"border-left:3px solid {clr};padding:6px 10px;margin-top:3px;"):
                        ui.label(f"{v} · anchor: {x.get('anchor')} "
                                 f"({x.get('valence')} → owes {x.get('demand')})").style(
                            f"color:{clr};font-size:var(--fs-sm);font-weight:700;")
                        if v in ("MISMATCH", "DEFERRED") and x.get("missing"):
                            ui.label(f"OMITTED: {x['missing']}").style(
                                f"color:{clr};font-size:var(--fs-sm);font-weight:600;")
                        if v == "WITHHELD" and x.get("competitive_why"):
                            ui.label(f"Correctly withheld — {x['competitive_why']}").style(
                                "color:#64748B;font-size:var(--fs-xs);")
                        ui.label(x.get("why") or "").style(
                            f"color:{COLORS['text_body']};font-size:var(--fs-xs);")
                        # Evidence, so a verdict can be checked rather than trusted.
                        with ui.expansion("show the exchange").classes("w-full").style("font-size:var(--fs-xs);"):
                            for lbl, key in (("Q", "question"), ("A", "answer"), ("Then", "reaction")):
                                if x.get(key):
                                    ui.label(f"{lbl}: {x[key]}").style(
                                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                ui.label("Each verdict names the anchor, the demand and the omission so you can check "
                         "it against the transcript. No accuracy rate is claimed — it hasn't been "
                         "validated against human labels.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);margin-top:4px;")

        async def _run_frames():
            ui.notify("Framing the Q&A — one model call per exchange, ~1 min…")
            try:
                f = await asyncio.to_thread(morning_after.frame_qa, state["q"], None, True)
            except Exception as e:
                ui.notify(f"Failed: {e}", type="negative")
                return
            _render_frames(f)
            ui.notify("Done." if f else "Nothing to frame.", type="positive" if f else "warning")

        ui.button("Analyse the Q&A" if not fr else "Re-analyse", icon="troubleshoot",
                  on_click=_run_frames).props("color=primary dense")
        _render_frames(fr)

        # ── What the Q&A exposed ────────────────────────────────────────────
        if p and p.get("error"):
            ui.label(p["error"]).style("color:#B45309;font-size:var(--fs-sm);margin-top:10px;")
        elif p:
            ui.label("What the Q&A exposed").classes("section-head").style("margin-top:12px;")
            with ui.row().classes("w-full gap-3"):
                _metric_card("Material gaps", str(p["material_gaps"]), "these cost money",
                             "#B91C1C" if p["material_gaps"] else "#15803D")
                _metric_card("Not addressed", str(p["unaddressed"]), "they'd have asked anyway")
                _metric_card("Probing", str(p["probing"]), "wanted more — opportunity")
                _metric_card("Ritual", str(p["ritual"]), "on-record questions")
            # Material first — that's the whole point of the ordering.
            order = {"material_gap": 0, "unaddressed": 1, "probing": 2, "ritual": 3}
            for x in sorted(p["topics"], key=lambda x: order.get(x["verdict"], 9)):
                clr, lbl = _VERDICT_STYLE.get(x["verdict"], (COLORS["border"], x["verdict"]))
                with ui.card().classes("w-full").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                        f"border-left:3px solid {clr};padding:6px 10px;margin-top:3px;"):
                    flags = " · ".join(f for f, on in [("management conceded", x["conceded"]),
                                                       ("pressed", x["pressed"]),
                                                       ("recurs", x["recurs"])] if on)
                    ui.label(f"{lbl} · {x['severity']} — {x['topic']}").style(
                        f"color:{clr};font-size:var(--fs-sm);font-weight:700;")
                    if flags:
                        ui.label(flags).style(f"color:{clr};font-size:var(--fs-2xs);")
                    ui.label(x["read"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);")
                    if x.get("why"):
                        ui.label(x["why"][:260]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    if x.get("evidence"):
                        ui.label(f"Script said: {x['evidence'][:190]}").style(
                            f"color:{COLORS['text_secondary']};font-size:var(--fs-2xs);font-style:italic;")

        # ── Written critique ────────────────────────────────────────────────
        ui.markdown("---")
        out = {"box": None}

        async def _write():
            ui.notify("Writing the critique…")
            try:
                text, was_ai, unverified = await asyncio.to_thread(
                    morning_after.narrative, state["q"])
            except Exception as e:
                ui.notify(f"Failed: {e}", type="negative")
                return
            if out["box"]:
                out["box"].clear()
            with out["box"]:
                if unverified:
                    with ui.card().classes("w-full").style(
                            "background:#FEF2F2;border:1px solid #B91C1C;padding:6px 10px;"):
                        ui.label(f"{len(unverified)} number(s) in this draft could not be traced to the "
                                 "transcript or the measured facts — verify before using:").style(
                            "color:#B91C1C;font-size:var(--fs-sm);font-weight:700;")
                        for u in unverified:
                            ui.label(f"• {u['value']} — {u['context']}").style(
                                "color:#B91C1C;font-size:var(--fs-xs);")
                ui.markdown(text)
                ui.label("Written from the measured facts above; every figure must carry the sentence it "
                         "came from. Numbers are auto-checked against the transcript — but that only "
                         "catches invention, not a real number attached to the wrong thing. Read it."
                         + ("" if was_ai else "  [model unavailable — deterministic summary]")).style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);margin-top:6px;")

        def _dl_pdf():
            from core import report_pdf
            try:
                ui.download(report_pdf.morning_after_pdf(state["q"]),
                            f"{CT('ticker')}_Morning_After_{state['q'].replace(' ', '_')}.pdf")
                ui.notify("Downloaded — the tape, the delivery, and every unmet demand.")
            except Exception as e:
                ui.notify(f"PDF failed: {e}", type="negative")

        with ui.row().classes("gap-2"):
            ui.button("Write the critique", icon="rate_review", on_click=_write).props("color=primary dense")
            ui.button("Download report (PDF)", icon="picture_as_pdf",
                      on_click=_dl_pdf).props("outline dense")
        ui.label("The PDF is the script-writing report: what the tape did, how the call ran, whether "
                 "you answered, and what each question demanded — unmet demands first, because that's "
                 "what tells you what next quarter's script has to say.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        out["box"] = ui.column().classes("w-full")

    sel.on_value_change(lambda e: (state.update(q=e.value), _body.refresh()))
    _body()


def _metric_card(label, value, sub="", color=None):
    with ui.card().classes("flex-1").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "min-width:120px;padding:8px 10px;"):
        ui.label(value).classes("font-bold").style(f"color:{color or COLORS['accent']};font-size:var(--fs-xl);")
        ui.label(label).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);font-weight:600;")
        if sub:
            ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")


def _guidance_template_draft(action, new_low, new_hi, rationale, other_guidance="", h2_comp="", catalysts=None):
    """Rule-based fallback if the Claude call fails/no key.

    Now a thin delegate to core.guidance_engine.render_guidance_prose(), which
    owns the deterministic rendering so the decision path (set_decision) and this
    page render the SAME words from the SAME inputs. Two copies of this template
    is how the prose and the decision drifted apart in the first place.
    `other_guidance` carries the EPS/EBITDA guided lines; `h2_comp` carries the
    derived, calendar-aware remaining-period comp language; `catalysts` are the
    H2 drivers derived from Stage 1 — so the fallback states every guided number,
    frames the base effect, AND cites this quarter's actual pipeline."""
    return guidance_engine.render_guidance_prose(
        action, new_low, new_hi, rationale, other_guidance=other_guidance, h2_comp=h2_comp, catalysts=catalysts)


def _guidance_template_draft_legacy(action, new_low, new_hi, rationale):
    """Superseded by render_guidance_prose() in core — kept only for reference."""
    policy = CGP()
    catalysts = policy.get("known_h2_catalysts", [])
    closing_line = policy.get("closing_line", "").strip()
    handoff = policy.get("operator_handoff", "").strip()
    growth_low = policy.get("fy_growth_low")
    growth_high = policy.get("fy_growth_high")
    growth_pct = (f"{growth_low*100:.0f}%–{growth_high*100:.0f}%"
                  if growth_low is not None and growth_high is not None else "our stated")

    range_str = f"${new_low:.1f}M to ${new_hi:.1f}M"
    openers = {
        "raise_low": "Based on our strong first-half performance, we are raising the low end of our full-year revenue guidance.",
        "raise_mid": "Based on our strong first-half performance and improving second-half visibility, we are raising our full-year revenue guidance.",
        "narrow": "Based on improving visibility into the second half, we are narrowing our full-year revenue guidance range.",
        "reiterate": "We are reiterating our full-year revenue guidance.",
    }
    ranges = {
        "raise_low": f"[FLS] We now expect full-year revenue in the range of {range_str}, reflecting the Q1 and Q2 performance now banked into the year. [/FLS]",
        "raise_mid": f"[FLS] We now expect full-year revenue in the range of {range_str}. [/FLS]",
        "narrow": f"[FLS] We now expect full-year revenue in the range of {range_str}. [/FLS]",
        "reiterate": f"The company continues to expect {growth_pct} growth in revenue this year, while also anticipating continued positive adjusted EBITDA.",
    }
    tones = {
        "raise_low": "This raise reflects the beat delivered through the first half of the year. The high end of our range is maintained, as significant H2 implementations are still ramping and we believe it is appropriate to retain some conservatism ahead of Q3 and Q4 execution.",
        "raise_mid": "This raise reflects confidence in our second-half execution across pipeline conversion, new implementations, and program ramps.",
        "narrow": "Narrowing the range reflects improving visibility without getting ahead of H2 execution.",
        "reiterate": "We believe it is prudent to maintain our full range as key H2 implementations continue to scale.",
    }
    h2_signal = ("[FLS] We expect the second half of the year to be sequentially stronger than the first half as "
                 "implementations currently in progress begin to scale and as newer initiatives contribute more "
                 "meaningfully to our revenue base. [/FLS]")
    catalysts_block = "\n".join(f"  {c}" for c in catalysts) or "  [No H2 catalysts configured for this client]"
    closing_bit = f"I thank our shareholders for their trust and support. {closing_line}\n\n" if closing_line else ""
    handoff_bit = handoff or ""
    return (
        f"{openers[action]}\n\n{ranges[action]}\n\n{tones[action]}\n\n{h2_signal}\n\n"
        f"[SPECIFIC H2 CATALYST LANGUAGE — reference at least 2 named catalysts here]\n"
        f"[CFO to confirm which are disclosure-appropriate before delivery:]\n{catalysts_block}\n"
        f"  [Add any Q2-specific new wins from Stage 1 notes]\n\n"
        f"{closing_bit}{handoff_bit}"
    )


def _generate_guidance_draft(ss, action, new_low, new_hi, rationale, extra_context=""):
    math_ = _guidance_math(ss)
    tone = _tone_context(ss)
    policy = CGP()
    weights = policy.get("seasonal_weights", {})
    quotes_block = "; ".join(f'{q}: "{t}"' for q, t in _guidance_prior_quotes())
    # H2 catalysts DERIVED from this quarter's Stage-1 operating detail (falls back to policy only if Stage 1
    # is empty) — so the drafted language cites the actual pipeline, not a static list.
    _cats, _cats_from_stage1 = guidance_engine.catalysts_from_stage1(ss)
    catalysts_block = "; ".join(_cats) or "none configured"
    range_str = f"${new_low:.1f}M to ${new_hi:.1f}M"
    # The OTHER guided lines (EPS, EBITDA) the company also gives — so the drafted language states EVERY
    # guided number, not just revenue (the analysis feeds the language for all three).
    _other = guidance_engine.guidance_other_lines_sentence((ss.get("guidance_inputs") or {}).get("metrics"))
    # The DERIVED, calendar-aware comp read — the exact remaining-period framing the CFA analysis produces
    # (organic ex-comp growth + two-year stack), so the spoken language carries it instead of a generic line.
    _h2 = guidance_engine.guidance_h2_comp_language(ss.get("guidance_inputs"), new_low, new_hi)
    seasonal_note = (
        f"IMPORTANT: Do NOT reference an equal quarterly split — Q3 is the lightest quarter "
        f"(~{weights['Q3']*100:.0f}% of FY), Q2 the heaviest (~{weights['Q2']*100:.0f}%). Always reference "
        f"seasonal targets, not naive averages. "
        if weights.get("Q2") and weights.get("Q3") else
        "Always reference seasonal targets, not naive quarterly averages. "
    )
    prompt = (
        f"Write the Guidance & Outlook section of {CT('ticker','')}'s earnings call script. "
        f"Decided action: {action.replace('_',' ').upper()}. New full-year guidance range: {range_str}. "
        f"Rationale: {rationale} {seasonal_note}"
        f"Seasonality math: YTD revenue ${math_['ytd_rev']:.1f}M is {math_['ytd_pct_of_mid']:.1f}% of the "
        f"${math_['fy_mid']:.1f}M guidance midpoint (pace vs seasonal norm: {math_['pace_vs_seasonal']:+.1f}pp). "
        f"H2 needed to hit the low end: ${math_['h2_needed_low']:.1f}M ({math_['h2_growth_needed']:+.1f}% YoY vs "
        f"prior H2's ${math_['h2_2025_rev']:.1f}M). "
        f"How the CEO has talked about guidance in prior quarters (match this voice): {quotes_block}. "
        + (f"ALSO state these other full-year guided lines the company gives, verbatim: {_other} " if _other else "")
        + (f"CRITICAL — frame the remaining-period comp exactly as this analysis concludes (do not call it a "
           f"deceleration; it is a prior-year base effect): {_h2} " if _h2 else "")
        + f"H2 catalysts from this quarter's operating detail, reference at least 2 (mark speculative specifics "
        f"as [FLS]...[/FLS]): {catalysts_block}. Writing rules: {_guidance_writing_rules()} "
        f"Additional context: {extra_context or 'none provided'}. "
        f"Tone: {tone['label']}. Target 300-350 words, plain text (no markdown)."
    )
    draft = _call_claude_script(prompt, 700)
    if draft:
        return draft, True
    return _guidance_template_draft(action, new_low, new_hi, rationale,
                                    other_guidance=_other, h2_comp=_h2, catalysts=_cats), False


def _guidance_prior_language():
    """The prior quarter's FULL-YEAR guidance sentence, verbatim — so this quarter's guidance matches the
    SAME structure quarter over quarter (only the verb + numbers change). Scores candidates so the FY
    range sentence wins over a next-quarter guide. Sourced from the prior call's recorded language."""
    import re
    cands = []
    prior_q = None
    try:
        m = re.match(r"Q([1-4])\s+(\d{4})", CE().get("current_quarter", "") or "")
        if m:
            _qn, _yr = int(m.group(1)), int(m.group(2))
            prior_q = f"Q{_qn - 1} {_yr}" if _qn > 1 else f"Q4 {_yr - 1}"
    except Exception:
        prior_q = None
    if prior_q:
        # AUTHORITATIVE source first: the prior quarter's PRESS RELEASE Outlook statement — the formal,
        # verbatim guidance the Street quotes, not a transcript paraphrase. Return it directly if present.
        try:
            from core import press_release
            _ps = press_release.guidance_statement(prior_q)
            if _ps:
                return _ps
        except Exception:
            pass
        try:
            rec = transcripts.get_transcript(prior_q)
            if rec:
                cands += [g for g in (rec.get("guidance_language") or []) if isinstance(g, str)]
        except Exception:
            pass
    for item in (_guidance_prior_quotes() or []):
        _t = item[1] if isinstance(item, (list, tuple)) and len(item) > 1 else (item if isinstance(item, str) else "")
        if _t:
            cands.append(_t)
    if not cands:
        return None

    def _score(t):
        tl, s = t.lower(), 0
        if any(k in tl for k in ("full-year", "full year", "fy20", " fy ")):
            s += 3                                            # FY guidance beats a quarterly guide
        if re.search(r"\$\d{2,3}(?:\.\d+)?\s*[–\-]\s*\d", t):
            s += 2                                            # states a $NNN–NNN range
        if "guidance" in tl or "reiterat" in tl or "rais" in tl:
            s += 1
        return s
    return max(cands, key=_score)


def _guidance_consistency(gd):
    """Verify the guidance LANGUAGE states the DECIDED range. The deterministic template can't drift, but
    an AI draft or a human edit can — so check the words actually carry the decided numbers. The script
    must never quote a range nobody decided. Returns None when there isn't enough to check."""
    import re
    txt = (gd.get("text") or "").strip()
    lo, hi = gd.get("new_low"), gd.get("new_hi")
    if not txt or lo is None or hi is None:
        return None
    nums = [float(x) for x in re.findall(r"(\d{2,3}(?:\.\d+)?)", txt)]
    lo_ok = any(abs(n - float(lo)) < 0.15 for n in nums)
    hi_ok = any(abs(n - float(hi)) < 0.15 for n in nums)
    return {"ok": lo_ok and hi_ok, "low": float(lo), "high": float(hi), "low_ok": lo_ok, "high_ok": hi_ok}


def _fmt_metric(v, fmt):
    if v is None:
        return "—"
    if fmt == "eps":
        return f"${v:.2f}"
    if fmt == "pct":
        return f"{v:.0f}%"
    if fmt == "bps":
        return f"{v:.0f} bps"
    if fmt == "volume":
        return f"${v:.2f}B"
    return f"${v:.1f}M"


def _qa_anchor(m):
    """One-line callback prep for a metric's DIRECTION question — what management should anchor to if an
    analyst asks 'how is X trending?'. Speaks in the growth-RATE trend, not the rising level: a $ line whose
    LEVEL climbs every quarter can still be DECELERATING on a YoY basis, and the RATE is what the analyst
    tracks and what re-rates the multiple. Ratio KPIs (bps/%) are levels with no meaningful growth rate, so
    for those the level direction (expansion/compression) is the correct read."""
    f = m["fmt"]
    src = "your guidance implies" if m.get("range") else "the Street models"

    # Ratio levels (take-rate bps, NRR %) — read the LEVEL direction.
    if f in ("bps", "pct"):
        path = (m.get("implied", {}) or {}).get("by_quarter") or m.get("path")
        if not path or len(path) < 2:
            return None
        vals = [(q.get("implied") if q.get("implied") is not None else q.get("value")) for q in path]
        if any(v is None for v in vals):
            return None
        rising = vals[-1] - vals[0] > abs(vals[0]) * 0.004
        falling = vals[-1] - vals[0] < -abs(vals[0]) * 0.004
        dirn = (("continued expansion" if rising else "compression" if falling else "roughly stable")
                if f == "bps" else ("stepping higher" if rising else "slipping" if falling else "holding the level"))
        seq = " → ".join(f"{q['q']} {_fmt_metric(vals[i], f)}" for i, q in enumerate(path))
        warn = ("keep the answer consistent — an off-hand “it's flattening” undercuts the guide" if rising
                else "flag the change proactively so it doesn't read later as a miss")
        return (f"“How is {m['label']} trending?” — {src} {dirn} ({seq}). {warn}.")

    # $/volume metrics — read the growth-RATE trend from the YoY sequence (the level rises every quarter;
    # the RATE is the signal). Same accelerate/decelerate/inflect logic as the bridge's trend read.
    fp = [x for x in (m.get("full_path") or []) if x.get("yoy_pct") is not None]
    if len(fp) < 2:
        return None
    rates = [x["yoy_pct"] for x in fp]
    sig = [d for d in (rates[i + 1] - rates[i] for i in range(len(rates) - 1)) if abs(d) >= 0.5]  # drop <0.5pp noise
    if any(sig[i] * sig[i + 1] < 0 for i in range(len(sig) - 1)):
        dirn, warn = ("an inflecting growth rate",
                      "own the inflection — it's the first thing they re-rate on")
    elif rates[-1] - rates[0] > 1.0:
        dirn, warn = ("an accelerating growth rate", "lead with the acceleration — it earns the multiple")
    elif rates[-1] - rates[0] < -1.0:
        dirn, warn = ("a decelerating growth rate",
                      "have the reason ready (comp vs demand) — a bare “it's slowing” invites a downgrade")
    else:
        dirn, warn = ("a steady growth rate", "reinforce the consistency — steadiness supports the multiple")
    seq = " → ".join(f"{x['q']} {x['yoy_pct']:+.0f}%" for x in fp)
    return (f"“How is {m['label']} trending?” — {src} {dirn} ({seq}). {warn}.")


def _bridge_chip(label, val, good=None):
    clr = COLORS["text_muted"] if good is None else (COLORS["positive"] if good else COLORS["danger"])
    with ui.row().classes("items-baseline gap-1 no-wrap").style(
            f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};border-radius:7px;padding:2px 9px;"):
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);text-transform:uppercase;letter-spacing:.03em;")
        ui.label(val).style(f"color:{clr};font-size:var(--fs-sm);font-weight:700;font-variant-numeric:tabular-nums;")


def _bridge_rangebar(m):
    """Full-year range bridge as a picture: prior guide range vs new range, with a Street marker — reads
    'parallel shift up, now above Street' in a glance instead of a sentence."""
    r = m.get("range")
    if not r:
        return
    f = m["fmt"]
    pl, ph = r["prior"]
    nl, nh = r["new"]
    street = (m.get("vs_street_fy") or {}).get("street_fy")
    pts = [pl, ph, nl, nh] + ([street] if street is not None else [])
    lo, hi = min(pts), max(pts)
    pad = ((hi - lo) or 1.0) * 0.18
    axmin, axspan = lo - pad, ((hi - lo) + 2 * pad) or 1.0
    _p = lambda x: max(0.0, min(100.0, (x - axmin) / axspan * 100))

    def _track(label, lo_v, hi_v, filled, val_txt):
        with ui.row().classes("items-center w-full no-wrap").style("gap:8px;margin:2px 0;"):
            ui.label(label).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);width:74px;text-align:right;flex:none;")
            with ui.element("div").classes("flex-1").style("position:relative;height:18px;"):
                ui.element("div").style(f"position:absolute;top:50%;left:0;right:0;height:1px;background:{COLORS['border']};")
                _bs = f"position:absolute;top:3px;left:{_p(lo_v):.1f}%;width:{max(1.0,_p(hi_v)-_p(lo_v)):.1f}%;height:12px;border-radius:4px;"
                ui.element("div").style(_bs + (f"background:{COLORS['accent']};opacity:.9;" if filled
                                               else f"background:transparent;border:1.5px dashed {COLORS['text_muted']};"))
                if street is not None:
                    ui.element("div").style(f"position:absolute;top:-3px;bottom:-3px;left:{_p(street):.1f}%;width:0;border-left:2px dotted {COLORS['warning']};")
            ui.label(val_txt).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);width:112px;flex:none;font-variant-numeric:tabular-nums;")

    with ui.column().classes("w-full").style("gap:0;margin-top:8px;"):
        _track("Prior guide", pl, ph, False, f"{_fmt_metric(pl,f)}–{_fmt_metric(ph,f)}")
        _track("New guide", nl, nh, True, f"{_fmt_metric(nl,f)}–{_fmt_metric(nh,f)}")
        if street is not None:
            ui.label(f"┊ dotted line = Street FY {_fmt_metric(street,f)}").style(
                f"color:{COLORS['warning']};font-size:var(--fs-2xs);margin-left:82px;")


def _classify_trend(vals, tol=0.5):
    """Direction of a growth-rate sequence. tol (pp) filters rounding-level wiggle from a real turn."""
    if len(vals) < 2:
        return None
    diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
    delta = vals[-1] - vals[0]
    if any(diffs[i] * diffs[i + 1] < 0 and abs(diffs[i]) > tol and abs(diffs[i + 1]) > tol
           for i in range(len(diffs) - 1)):
        return "inflecting"
    if delta > 1.0 and all(d >= -tol for d in diffs):
        return "accelerating"
    if delta < -1.0 and all(d <= tol for d in diffs):
        return "decelerating"
    return "steady"


def _bridge_trend_read(full_path, comp_note=None, comp_adjust=None):
    """The trend IS the signal — but a YoY rate is current ÷ prior-year, so a step-down can be the numerator
    (real demand slowing) OR the denominator (a prior-year comp inflating the base). We DO NOT call it a
    deceleration until we've ruled it out with TWO independent legs: (1) ORGANIC YoY — strip the flagged
    one-time from the prior-year base and recompute; (2) the two-year STACKED CAGR — model-free, needs no
    comp assumption, because a spike that inflates the base also inflated the prior-year growth. Only a
    step-down that survives these is a genuine slowdown. YoY already nets out seasonality; QoQ confirms
    sequential momentum. Returns up to two (color, text) lines, most-important first."""
    rows = [x for x in full_path if x.get("value") is not None]
    if len(rows) < 2:
        return []
    out = []
    ys = [(x.get("q"), x["yoy_pct"]) for x in rows if x.get("yoy_pct") is not None]
    yoy_kind = None
    if len(ys) >= 2:
        rep_vals = [y for _, y in ys]
        rep_kind = _classify_trend(rep_vals)
        seq = " → ".join(f"{y:+.0f}%" for y in rep_vals)
        # Leg 1 — ORGANIC (ex-comp) YoY: the recomputed rate where the engine stripped a one-time, else the
        # reported rate for unaffected quarters.
        _orgmap = {x.get("q"): x.get("yoy_organic_pct") for x in rows}
        has_org = any(v is not None for v in _orgmap.values())
        org_vals = [(_orgmap.get(q) if _orgmap.get(q) is not None else y) for q, y in ys]
        org_kind = _classify_trend(org_vals) if has_org else None
        org_seq = " → ".join(f"{v:+.0f}%" for v in org_vals) if has_org else None
        # Leg 2 — two-year STACKED CAGR: model-free, no comp assumption.
        _stk = [x.get("two_yr_cagr_pct") for x in rows if x.get("two_yr_cagr_pct") is not None]
        has_stk = len(_stk) >= 2
        stk_kind = _classify_trend(_stk) if has_stk else None
        stk_seq = " → ".join(f"{v:+.0f}%" for v in _stk) if has_stk else None
        stk_avg = (sum(_stk) / len(_stk)) if has_stk else None
        _stk_word = {"steady": "flat", "accelerating": "rising", "inflecting": "holding",
                     "decelerating": "falling"}.get(stk_kind, "")

        # Build the independent proof legs (each holds if it does NOT itself decelerate).
        _legs, _fail = [], False
        if has_org:
            if org_kind != "decelerating":
                _amt = (comp_adjust or {}).get("amount"); _lbl = (comp_adjust or {}).get("label", "a prior-year one-time")
                _amt_s = f"~${_amt:.0f}M " if _amt else ""
                _legs.append(f"strip the {_amt_s}{_lbl} and organic YoY holds ({org_seq})")
            else:
                _fail = True
        if has_stk:
            if stk_kind != "decelerating":
                _legs.append(f"the model-free 2-yr stacked CAGR is {_stk_word} at ~{stk_avg:.0f}% ({stk_seq})")
            else:
                _fail = True

        if rep_kind == "decelerating" and _legs and not _fail:
            # PROVEN base effect on every available leg — reported falls but the normalized trend holds.
            _hdr = ("Two independent checks confirm" if len(_legs) >= 2 else "The comp check confirms")
            out.append((COLORS["positive"],
                        f"Reported YoY steps down ({seq}) — but that's the COMP, not demand. {_hdr} the underlying "
                        f"trend holds: " + "; ".join(_legs) + ". YoY already nets out seasonality, so the residual "
                        f"is the base — lead with these and the Street can't re-rate a comp as a slowdown."))
            yoy_kind = "comp_driven"
        elif rep_kind == "decelerating" and _fail and not _legs:
            # Every available leg ALSO decelerates — the slowdown survives normalization. It's real.
            _proof = (f"the 2-yr stacked CAGR ({stk_seq})" if has_stk and stk_kind == "decelerating"
                      else f"ex-comp organic YoY ({org_seq})")
            out.append((COLORS["warning"],
                        f"YoY trend — decelerating: {seq}. And {_proof} steps down too — the slowdown survives the "
                        f"comp adjustment, so it's real demand. Caps the multiple."))
            yoy_kind = "decelerating"
        elif rep_kind == "decelerating" and _legs and _fail:
            # Legs disagree — one normalizes the step-down away, another doesn't. Don't assert; flag the split.
            out.append((COLORS["warning"],
                        f"Reported YoY steps down ({seq}) and the normalization is mixed — one check clears it "
                        f"({'; '.join(_legs)}) but another still declines. Resolve which base is right before "
                        f"concluding; don't cap the multiple on an unresolved comp."))
            yoy_kind = "comp_flagged"
        elif rep_kind == "decelerating" and (comp_note or comp_adjust):
            # A comp is flagged but not quantified — refuse the wrong conclusion; demand the normalization.
            out.append((COLORS["warning"],
                        f"Reported YoY steps down ({seq}), but a prior-year comp is flagged — normalize the base "
                        f"before concluding. A comp-driven step-down does NOT cap the multiple; only one that "
                        f"survives the comp adjustment does."))
            yoy_kind = "comp_flagged"
        else:
            yoy_kind = rep_kind
            _clr = {"accelerating": COLORS["positive"], "decelerating": COLORS["warning"],
                    "inflecting": COLORS["accent"], "steady": COLORS["text_muted"]}[rep_kind]
            _con = {"accelerating": "expands the multiple — lead with it",
                    "decelerating": "caps the multiple — survives the comp check, so it's real demand",
                    "inflecting": "is what analysts re-rate on — own the reason",
                    "steady": "holds the multiple — reinforce the consistency"}[rep_kind]
            out.append((_clr, f"YoY trend — {rep_kind}: {seq}. {_con}."))
            if has_stk and stk_kind and stk_kind != rep_kind:
                out.append((COLORS["text_muted"], f"2-yr stacked CAGR: {stk_seq} — {_stk_word}."))
            elif has_org and org_kind and org_kind != rep_kind:
                out.append((COLORS["text_muted"], f"Ex-comp (organic) YoY: {org_seq} — {org_kind}."))
    # ── QoQ (sequential momentum) — confirms the underlying read ──
    qs = []
    for i in range(1, len(rows)):
        p, c = rows[i - 1]["value"], rows[i]["value"]
        if p:
            qs.append((c - p) / p * 100)
    if qs and len(out) < 2:
        qseq = " → ".join(f"{v:+.1f}%" for v in qs)
        seq_pos = all(v > -0.5 for v in qs)
        if yoy_kind in ("comp_driven", "comp_flagged") and seq_pos:
            out.append((COLORS["positive"], f"Sequentially still growing (QoQ {qseq}) — the step-down is in the "
                        "year-ago base, not this year's momentum."))
        elif yoy_kind == "accelerating" and seq_pos:
            out.append((COLORS["positive"], f"Confirmed sequentially (QoQ {qseq}) — both lenses point up; "
                        "the highest-conviction setup."))
        elif yoy_kind == "decelerating" and seq_pos:
            out.append((COLORS["text_muted"], f"Still growing sequentially (QoQ {qseq}) — a slowdown in the "
                        "rate, not a contraction."))
        elif yoy_kind:
            out.append((COLORS["text_muted"], f"Sequentially (QoQ): {qseq}."))
    return out


def _bridge_quarterbars(full_path, fmt, comp_note=None, comp_adjust=None):
    """The quarter path as bars, with the YoY growth RATE on every quarter (H1 reported, H2 implied), and
    the TREND read underneath — analysts read the direction of the rate, not just the level: decelerating
    caps the multiple, accelerating expands it, a break re-rates the stock. Where a prior-year comp is
    stripped, the organic (ex-comp) rate is shown under the reported one so the base effect is visible."""
    rows = [x for x in full_path if x.get("value") is not None]
    if len(rows) < 2:
        return
    vmax = max(x["value"] for x in rows) or 1.0
    ui.label("Per-quarter path — growth rate on every quarter (H1 reported · H2 implied)").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.05em;"
        "font-weight:700;margin-top:12px;")
    with ui.row().classes("w-full items-end no-wrap").style("gap:12px;height:150px;padding-top:4px;"):
        for x in rows:
            h = max(8.0, x["value"] / vmax * 72)
            filled = not x["actual"]
            col = COLORS["accent"] if filled else COLORS["text_muted"]
            with ui.column().classes("items-center").style("flex:1;height:100%;justify-content:flex-end;gap:3px;"):
                ui.label(_fmt_metric(x["value"], fmt)).style(
                    f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-weight:700;font-variant-numeric:tabular-nums;")
                ui.element("div").style(f"width:100%;max-width:46px;height:{h:.0f}px;background:{col};"
                                        f"opacity:{'0.9' if filled else '0.45'};border-radius:5px 5px 0 0;")
                ui.label(x["q"] or "").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-weight:600;")
                if x.get("yoy_pct") is not None:
                    _yc = COLORS["positive"] if x["yoy_pct"] >= 0 else COLORS["danger"]
                    ui.label(f"{x['yoy_pct']:+.0f}% YoY").style(f"color:{_yc};font-size:var(--fs-xs);font-weight:700;")
                    if x.get("yoy_organic_pct") is not None:
                        ui.label(f"{x['yoy_organic_pct']:+.0f}% ex-comp").style(
                            f"color:{COLORS['positive']};font-size:var(--fs-xs);font-weight:700;")
                else:
                    ui.label("reported" if x["actual"] else "est.").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")
    # The trend read — YoY + QoQ, the signal that matters more than any single number.
    for _i, (_clr, _txt) in enumerate(_bridge_trend_read(rows, comp_note, comp_adjust)):
        with ui.row().classes("w-full items-start no-wrap").style(
                f"gap:8px;background:{_clr}12;border-left:3px solid {_clr};border-radius:6px;padding:7px 11px;"
                f"margin-top:{'8px' if _i == 0 else '4px'};"):
            ui.label("📈" if _i == 0 else "↔").style("flex:none;font-size:var(--fs-sm);")
            ui.label(_txt).style(f"color:{_clr};font-size:var(--fs-sm);font-weight:600;line-height:1.45;")


_BR_TAG = {"RAISED": "positive", "RAISED LOW END": "positive", "RAISED HIGH END": "positive",
           "REITERATED": "warning", "MAINTAINED": "warning", "CUT": "danger"}


def _bridge_tag(tag):
    if not tag:
        return
    clr = COLORS[_BR_TAG.get(tag, "text_muted")] if _BR_TAG.get(tag) else COLORS["text_muted"]
    ui.label(tag).style(f"background:{clr}22;color:{clr};font-size:var(--fs-xs);font-weight:800;"
                        "letter-spacing:.03em;padding:2px 11px;border-radius:999px;white-space:nowrap;")


def _bridge_measure_chips(m):
    f = m["fmt"]
    if "qoq" in m and m["qoq"]["pct"] is not None:
        _bridge_chip("QoQ", f"{m['qoq']['pct']:+.1f}%", m["qoq"]["pct"] >= 0)
    if "yoy" in m and m["yoy"]["pct"] is not None:
        _bridge_chip("YoY", f"{m['yoy']['pct']:+.1f}%", m["yoy"]["pct"] >= 0)
    if "vs_street" in m and m["vs_street"]["beat_pct"] is not None:
        _bridge_chip("vs Street", f"{m['vs_street']['beat_pct']:+.1f}%", m["vs_street"]["beat"] >= 0)
    if "accel_pp" in m:
        _bridge_chip("accel", f"{m['accel_pp']:+.1f}pp", m["accel_pp"] >= 0)


def _bridge_detail_lines(m):
    """The full measurement, one line each — the wall, now behind a click. DELTAS are shown SIGNED so a
    change is never misread as a level (the "New mid vs Street FY" line used to print the +$0.01 delta with
    no sign, which read like the new mid itself was $0.01)."""
    f = m["fmt"]
    _sgn = lambda v: (("+" if v >= 0 else "−") + _fmt_metric(abs(v), f))  # a delta, shown as a change
    out = []
    r = m.get("range")
    if r:
        out.append(("Range flow-through", f"low {_sgn(r['d_low'])} · mid {_sgn(r['d_mid'])} · "
                    f"high {_sgn(r['d_high'])} — {m.get('pass_through',{}).get('characterization','')}"))
    imp = m.get("implied", {})
    if imp.get("implied_growth_low") is not None:
        out.append(("Implied remaining", f"{_fmt_metric(imp['remaining_low'],f)}–{_fmt_metric(imp['remaining_high'],f)} "
                    f"(+{imp['implied_growth_low']:.0f}% to +{imp['implied_growth_high']:.0f}% vs prior-year) — "
                    f"{imp.get('read','')} vs the current run-rate"))
    vf = m.get("vs_street_fy")
    if vf:
        out.append(("New mid vs Street FY", f"new mid {_fmt_metric(vf['new_mid'],f)} vs Street "
                    f"{_fmt_metric(vf['street_fy'],f)} ({_sgn(vf['delta'])}) → {vf['revision']} estimate revisions"))
    ny = m.get("next_year")
    if ny:
        _n = f"Street {_fmt_metric(ny['street'],f)} (+{ny.get('growth_off_guide_pct',0):.0f}% off the raised guide)"
        if ny.get("exit_run_rate") is not None:
            _n += f" · Q4 exit run-rate {_fmt_metric(ny['exit_run_rate'],f)} → +{ny.get('growth_off_exit_pct',0):.0f}% off exit"
        if ny.get("roll_forward_lift"):
            _n += f" · roll-forward lift {_sgn(ny['roll_forward_lift'])}"
        out.append(("Next year (FY+1)", _n))
        if ny.get("read"):
            out.append(("Implication", ny["read"]))
    if "vs_whisper" in m and m["vs_whisper"]["beat_pct"] is not None:
        out.append(("vs Whisper", f"{_sgn(m['vs_whisper']['beat'])} ({m['vs_whisper']['beat_pct']:+.1f}%) · "
                    f"2-yr stack {m.get('two_yr_stack_pct','—')}%"))
    return out


def _bridge_metric_full(m):
    """Primary metric — the full answer-first card: verdict · measure (chips + range bar + quarter bars) ·
    collapsed detail. The comp-watch flag stays loud; the neutral math goes behind the click."""
    f = m["fmt"]
    rec = m.get("recommendation") or {}
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:10px;padding:0;margin:6px 0;"):
        # Verdict zone
        with ui.column().classes("w-full").style("gap:6px;padding:13px 16px 12px;"):
            with ui.row().classes("w-full items-center gap-2 no-wrap"):
                ui.label(m["label"].upper()).style(f"color:{COLORS['text_heading']};font-weight:800;font-size:var(--fs-sm);letter-spacing:.01em;")
                ui.label(_fmt_metric(m["actual"], f)).style(
                    f"color:{COLORS['accent_light']};font-weight:800;font-size:var(--fs-xl);font-variant-numeric:tabular-nums;")
                ui.space()
                _bridge_tag(rec.get("tag"))
            if rec.get("note"):
                ui.label(rec["note"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);line-height:1.5;")
        # Measure zone
        with ui.column().classes("w-full").style(
                f"gap:0;padding:12px 16px 14px;background:{COLORS['surface_hover_bg']};border-top:1px solid {COLORS['border']};"):
            with ui.row().classes("gap-2 flex-wrap").style("margin-bottom:2px;"):
                _bridge_measure_chips(m)
            _bridge_rangebar(m)
            if m.get("full_path"):
                _bridge_quarterbars(m["full_path"], f, m.get("comp_note"), m.get("comp_adjust"))
            if m.get("comp_note"):
                with ui.row().classes("w-full items-start no-wrap").style(
                        f"gap:8px;background:{COLORS['surface_bg']};border-radius:8px;padding:8px 11px;margin-top:12px;"):
                    ui.label("⚠").style(f"color:{COLORS['warning']};flex:none;")
                    ui.label(f"Comp watch — {m['comp_note']}").style(f"color:{COLORS['warning']};font-size:var(--fs-sm);line-height:1.45;")
        # Detail zone (collapsed)
        _lines = _bridge_detail_lines(m)
        if _lines:
            with ui.expansion("Show the full bridge — range math, Street revisions, next year").classes(
                    "w-full panel-tinted").props("dense").style("border-top:1px solid " + COLORS["border"] + ";"):
                for k, v in _lines:
                    with ui.row().classes("w-full items-start no-wrap").style("gap:10px;padding:4px 0;"):
                        ui.label(k).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-weight:600;width:150px;flex:none;")
                        ui.label(v).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);line-height:1.5;")


def _bridge_metric_compact(m):
    """Secondary guided metric — one compact line (name · value · action · so-what · 2 chips), with the
    full bridge tucked behind a click. Triage by weight: not every metric earns the big card."""
    f = m["fmt"]
    rec = m.get("recommendation") or {}
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:10px;padding:0;margin:6px 0;"):
        with ui.row().classes("w-full items-center gap-2 flex-wrap").style("padding:11px 16px;"):
            ui.label(m["label"].upper()).style(f"color:{COLORS['text_heading']};font-weight:800;font-size:var(--fs-sm);width:78px;flex:none;")
            ui.label(_fmt_metric(m["actual"], f)).style(
                f"color:{COLORS['accent_light']};font-weight:800;font-size:var(--fs-md);font-variant-numeric:tabular-nums;width:66px;flex:none;")
            _bridge_tag(rec.get("tag"))
            if rec.get("note"):
                ui.label(rec["note"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);flex:1;min-width:180px;line-height:1.4;")
            with ui.row().classes("gap-2 no-wrap"):
                _bridge_measure_chips(m)
        _lines = _bridge_detail_lines(m)
        if _lines or m.get("full_path"):
            with ui.expansion("Show the full bridge").classes("w-full panel-tinted").props("dense").style(
                    "border-top:1px solid " + COLORS["border"] + ";"):
                if m.get("full_path"):
                    _bridge_quarterbars(m["full_path"], f, m.get("comp_note"), m.get("comp_adjust"))
                for k, v in _lines:
                    with ui.row().classes("w-full items-start no-wrap").style("gap:10px;padding:4px 0;"):
                        ui.label(k).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-weight:600;width:150px;flex:none;")
                        ui.label(v).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);line-height:1.5;")


_KPI_ROLE = {"demand": "demand driver", "pricing": "pricing / mix", "retention": "retention",
             "efficiency": "efficiency", "volume": "volume driver"}


def _kpi_trend(m):
    """Read a KPI's trend the way an analyst does — on the growth RATE where the metric has a YoY comp
    (volume/dollar KPIs), or on the LEVEL direction where it's a ratio (NRR, take-rate). Returns
    (forward_rows, headline_word, detail_seq, color)."""
    f = m["fmt"]
    path = m.get("full_path") or []
    fwd = [x for x in path if not x.get("actual") and x.get("value") is not None]
    yoys = [x["yoy_pct"] for x in path if x.get("yoy_pct") is not None]
    dk = m.get("driver_kind")
    if len(yoys) >= 2:                                   # growth-rate trend (same honest classifier as revenue)
        kind = _classify_trend(yoys)
        word = {"accelerating": "Accelerating", "decelerating": "Decelerating",
                "steady": "Steady", "inflecting": "Inflecting"}[kind]
        detail = "YoY " + " → ".join(f"{y:+.0f}%" for y in yoys)
        clr = {"accelerating": COLORS["positive"], "decelerating": COLORS["warning"],
               "steady": COLORS["text_muted"], "inflecting": COLORS["accent"]}[kind]
        return fwd, word, detail, clr
    lvls = [v for v in ([m.get("actual")] + [x["value"] for x in fwd]) if v is not None]
    if len(lvls) >= 2:                                   # level metric — direction of the ratio
        d = lvls[-1] - lvls[0]
        kind = "rising" if d > 1e-9 else "easing" if d < -1e-9 else "holding"
        word = ({"pricing": {"rising": "Expanding"}, "retention": {"rising": "Stepping higher"}}
                .get(dk, {}).get(kind) or {"rising": "Rising", "easing": "Easing", "holding": "Holding"}[kind])
        detail = " → ".join(_fmt_metric(v, f) for v in lvls)
        clr = COLORS["positive"] if kind == "rising" else COLORS["warning"] if kind == "easing" else COLORS["text_muted"]
        return fwd, word, detail, clr
    return fwd, None, "", COLORS["text_muted"]


def _bridge_kpi_strip(kpis):
    """Street KPIs — the operating drivers. Each card is a mini-analysis, not a bare number: the reported
    level, its TREND (growth-rate for volume metrics, level direction for ratios), the modeled forward path
    (clearly Street estimates — NOT a counterfactual), and how that driver UNDERPINS the guide."""
    if not kpis:
        return
    ui.label("Street KPIs — the operating drivers (what moves the guide)").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.05em;font-weight:700;margin:12px 0 4px;")
    with ui.row().classes("w-full gap-3 flex-wrap items-stretch"):
        for m in kpis:
            f = m["fmt"]
            _rqs = ((m.get("position") or {}).get("reporting_q") or m.get("reporting_q") or "").split()
            rq = _rqs[0] if _rqs else "current"
            fwd, word, detail, clr = _kpi_trend(m)
            yoy = (m.get("yoy") or {}).get("pct")
            with ui.column().classes("flex-1").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:9px;"
                    "min-width:270px;padding:12px 14px;gap:6px;"):
                with ui.row().classes("w-full items-center no-wrap").style("gap:6px;"):
                    ui.label(m["label"].upper()).style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.03em;font-weight:700;")
                    ui.space()
                    if m.get("driver_kind"):
                        ui.label(_KPI_ROLE.get(m["driver_kind"], m["driver_kind"])).style(
                            f"background:{COLORS['accent']}18;color:{COLORS['accent']};font-size:var(--fs-2xs);"
                            "font-weight:700;padding:1px 8px;border-radius:999px;white-space:nowrap;")
                # A ratio (NRR, take-rate) moves in POINTS, not percent — an analyst says "+3 bps", never
                # "+7% YoY". So show pp/bps for ratios and percent growth for volume/dollar KPIs.
                _yd = (m.get("yoy") or {}).get("delta")
                if f == "bps" and _yd is not None:
                    _suf = f" · {_yd:+.0f} bps YoY"
                elif f == "pct" and _yd is not None:
                    _suf = f" · {_yd:+.0f} pp YoY"
                elif yoy is not None:
                    _suf = f" · {yoy:+.0f}% YoY"
                else:
                    _suf = ""
                with ui.row().classes("items-baseline no-wrap").style("gap:8px;"):
                    ui.label(_fmt_metric(m["actual"], f)).style(
                        f"color:{COLORS['text_heading']};font-weight:800;font-size:var(--fs-lg);font-variant-numeric:tabular-nums;")
                    ui.label(f"{rq} actual{_suf}").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);white-space:nowrap;")
                if word:
                    ui.label(f"{word} — {detail}").style(
                        f"color:{clr};font-size:var(--fs-sm);font-weight:700;font-variant-numeric:tabular-nums;")
                if fwd:
                    _mp = " → ".join(f"{x['q']} {_fmt_metric(x['value'], f)}" for x in fwd)
                    ui.label(f"Modeled {_mp} · Street estimates (not guided)").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                if m.get("supports"):
                    ui.label(m["supports"]).style(
                        f"color:{COLORS['text_body']};font-size:var(--fs-xs);line-height:1.45;margin-top:1px;")


def _bridge_verdict(metrics, syn):
    """Answer-first banner: the recommended action + how many metrics back it + the synthesis tally
    (credibility · flow-through · cash conversion), so the CFO decides before reading a single ratio."""
    guided = [m for m in metrics if m.get("range")]
    if not guided:
        return
    anchor = next((m for m in guided if m.get("key") == "rev"), guided[0])
    action = (anchor.get("recommendation") or {}).get("tag") or "REVIEW"
    n_raise = sum(1 for m in guided if str((m.get("recommendation") or {}).get("tag", "")).startswith("RAISED"))
    watch = [m for m in guided if m.get("comp_note")]
    accent = COLORS[_BR_TAG.get(action, "warning")] if _BR_TAG.get(action) else COLORS["accent"]
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:5px solid {accent};"
            "border-radius:10px;padding:15px 18px;margin:6px 0;"):
        with ui.row().classes("w-full items-center gap-3 flex-wrap"):
            ui.label("Recommended:").style(f"color:{COLORS['text_heading']};font-weight:800;font-size:var(--fs-md);")
            ui.label(action).style(f"color:{accent};font-weight:800;font-size:var(--fs-md);letter-spacing:.01em;")
            ui.space()
            ui.label(f"{n_raise} of {len(guided)} P&L metrics support a raise").style(
                f"background:{COLORS['positive']}18;color:{COLORS['positive']};font-size:var(--fs-xs);font-weight:700;padding:3px 10px;border-radius:999px;")
            if watch:
                ui.label(f"{len(watch)} watch item{'s' if len(watch) > 1 else ''}").style(
                    f"background:{COLORS['warning']}18;color:{COLORS['warning']};font-size:var(--fs-xs);font-weight:700;padding:3px 10px;border-radius:999px;")
        _so = (anchor.get("recommendation") or {}).get("note")
        if _so:
            ui.label(_so).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);line-height:1.5;margin-top:8px;")
        # Each signal carries its COMPARISON + what it means — a bare "32%" or "76%" tells the reader
        # nothing. Value is measured against its benchmark (corporate margin, prior quarter, Street), and
        # the interpretation says why it matters (whisper, operating leverage, earnings quality).
        tally = []
        cr, ft, cc = syn.get("credibility"), syn.get("flow_through"), syn.get("cash_conversion")
        if cr and cr.get("avg_beat_pct") is not None:
            _wh = (" — and why the buy-side whisper sits above published consensus"
                   if cr["avg_beat_pct"] > 0 else "")
            tally.append(("Credibility", f"beat {cr['beat_rate']} quarters, avg +{cr['avg_beat_pct']:.1f}% vs Street",
                          f"a consistent sandbag → the raised guide is likely still conservative{_wh}"))
        if ft and ft.get("quarter_incremental_margin_pct") is not None:
            _im, _sm = ft["quarter_incremental_margin_pct"], ft.get("steady_margin_pct")
            if _sm is not None:
                _val = f"incremental margin {_im:.0f}% vs ~{_sm:.0f}% corporate"
                _rd = ("operating leverage → the beat is margin-accretive" if _im > _sm + 2
                       else "below corporate → the beat isn't fully dropping to profit" if _im < _sm - 2
                       else "roughly in line with the corporate margin")
            else:
                _val, _rd = f"incremental margin {_im:.0f}%", ""
            tally.append(("Flow-through", _val, _rd))
        if cc and cc.get("conversion_pct") is not None:
            _cv, _pv = cc["conversion_pct"], cc.get("prior_conversion_pct")
            _tr = (f", {'up' if _cv > _pv + 1 else 'down' if _cv < _pv - 1 else 'steady'} from {_pv:.0f}%"
                   if _pv is not None else "")
            _q = "high" if _cv >= 70 else "moderate" if _cv >= 45 else "weak"
            tally.append(("Cash conversion", f"FCF/EBITDA {_cv:.0f}%{_tr}",
                          f"{_q} conversion → the raise is funded internally, real cash not accrual"))
        if tally:
            with ui.column().classes("w-full").style(
                    f"gap:4px;margin-top:11px;padding-top:11px;border-top:1px dashed {COLORS['border']};"):
                for k, v, rd in tally:
                    with ui.row().classes("w-full items-baseline gap-2 flex-wrap"):
                        ui.label(k).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-weight:700;width:112px;flex:none;")
                        ui.label(v).style(f"color:{COLORS['text_heading']};font-size:var(--fs-xs);font-weight:600;font-variant-numeric:tabular-nums;")
                        if rd:
                            ui.label("— " + rd).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")


def _render_guidance_bridge(ss):
    """The CFA guidance read: every reported number measured QoQ / YoY / vs Street / vs its own guide,
    then the beat/miss flowed through the full-year range (low·mid·high each), and what the new guide
    implies for the rest of the year. Driven by core.guidance_engine.guidance_bridge."""
    inputs = ss.get("guidance_inputs")
    if not inputs:
        return
    from core import guidance_engine
    # SINGLE SOURCE OF TRUTH: once a guidance range is decided in Step 2 (guidance_decision.new_low/hi),
    # THAT range drives this analysis — not a separately-seeded number. Input the range → the bridge
    # re-analyzes it. (Revenue is the guided line; EPS/EBITDA keep their own ranges.)
    gd = ss.get("guidance_decision") or {}
    if gd.get("new_low") is not None and gd.get("new_hi") is not None:
        import copy as _copy
        inputs = _copy.deepcopy(inputs)
        _rev = (inputs.get("metrics") or {}).get("rev")
        if _rev is not None:
            _rev["new_fy_range"] = [float(gd["new_low"]), float(gd["new_hi"])]
    _surprises = _load_json("earnings_surprise_log.json", None)   # for the credibility / beat-track-record read
    b = guidance_engine.guidance_bridge(inputs, surprises=_surprises)
    meta = b["meta"]

    ui.label("Guidance Bridge — the decision, then the evidence").classes(
        "font-bold").style("font-size:var(--fs-md);margin-top:8px;")
    ui.label(f"{meta['reporting_quarter']} vs {meta['prior_quarter']} (QoQ) and {meta['prior_year_quarter']} (YoY), "
             "vs Street and the company's own guide — the full-year range bridge and what it implies for the rest "
             "of the year. Answer first; the full measurement is one click away.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-bottom:4px;")

    metrics = b["metrics"]
    syn = b.get("synthesis", {})
    guided = [m for m in metrics if m.get("range")]
    kpis = [m for m in metrics if m.get("path") and not m.get("range")]

    _bridge_verdict(metrics, syn)          # the answer: recommended action + backing + synthesis tally
    if guided:
        _bridge_metric_full(guided[0])     # primary metric (revenue) — full card with range + quarter visuals
        for _m in guided[1:]:
            _bridge_metric_compact(_m)      # EPS, EBITDA — compact rows, full bridge behind a click
    _bridge_kpi_strip(kpis)                # Street KPIs — the operating-driver strip
    # NOTE: the "Callback Q&A prep" block moved to the Q&A Prep tab (_render_callback_qa_prep) — it's prep
    # for the call, not part of the guidance decision. See _render_qa_prep_tab.


def _callback_qa_anchors(ss):
    """Build the callback Q&A direction anchors from the live guidance bridge (same single-source-of-truth
    range the bridge uses). Returns a list of anchor strings, one per number that has a trend to defend."""
    inputs = ss.get("guidance_inputs")
    if not inputs:
        return []
    from core import guidance_engine
    gd = ss.get("guidance_decision") or {}
    if gd.get("new_low") is not None and gd.get("new_hi") is not None:
        import copy as _copy
        inputs = _copy.deepcopy(inputs)
        _rev = (inputs.get("metrics") or {}).get("rev")
        if _rev is not None:
            _rev["new_fy_range"] = [float(gd["new_low"]), float(gd["new_hi"])]
    b = guidance_engine.guidance_bridge(inputs, surprises=_load_json("earnings_surprise_log.json", None))
    return [a for a in (_qa_anchor(m) for m in b["metrics"]) if a]


def _render_callback_qa_prep(ss):
    """Callback Q&A prep — what to say if asked how each number is trending. Analysts probe metric/KPI
    DIRECTION on callbacks ("how's take-rate trending?") and pause; management must anchor to what the
    guidance implies or they answer inconsistently and hand over a downgrade angle. Lives in the Q&A Prep
    area (moved out of the guidance bridge — it's call prep, not part of the decision)."""
    _anchors = _callback_qa_anchors(ss)
    if not _anchors:
        return
    with ui.card().classes("w-full").style(
            f"background:rgba(37,99,235,.06);border:1px solid {COLORS['accent']};border-radius:9px;margin:4px 0 8px;"):
        ui.label("Callback Q&A prep — what to say if asked how each number is trending").style(
            f"color:{COLORS['text_heading']};font-weight:700;font-size:var(--fs-sm);")
        ui.label("On analyst callbacks the direction question comes with a pause. Anchor every answer to "
                 "what the guidance / model implies — a casual “it's flattening” contradicts the raise "
                 "and hands the analyst a downgrade angle.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-bottom:2px;")
        for _a in _anchors:
            ui.label(_a).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);margin-top:2px;line-height:1.4;")


def _render_guidance_drafter(ss, on_submit=None):
    """The WRITING surface for the Guidance & Outlook section of the Script Canvas — prior-quarter wording
    to match, the optional H2-context input, the AI drafter, the editable draft box with a length read, and
    the live consistency check. Self-contained (recomputes the decided range from ss, the single source) so
    the section canvas can render it stand-alone, beside its analysis rail. The stacked Decision Engine
    (_render_guidance_decision) still renders the same drafting UI inline for the Markets page."""
    from core import guidance_engine as _ge
    gd = ss.setdefault("guidance_decision", {})
    math_ = _guidance_math(ss)
    _prior = ((((ss.get("guidance_inputs") or {}).get("metrics") or {}).get("rev") or {}).get("prior_fy_range")
              or [math_["fy_low"], math_["fy_hi"]])
    if gd.get("new_low") is not None and gd.get("new_hi") is not None:
        _new = [float(gd["new_low"]), float(gd["new_hi"])]
    else:
        _dl, _dh, _ = _ge.apply_action(
            {"RAISE_MID": "raise_mid", "RAISE_LOW": "raise_low"}.get(math_["scenario"], "reiterate"), math_)
        _new = [round(_dl, 1), round(_dh, 1)]

    _prior_guid = _guidance_prior_language()
    _cons = _guidance_consistency(gd)
    if _prior_guid or _cons:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;padding:10px 14px;"):
            if _prior_guid:
                ui.label(f"Prior quarter's wording (match this structure): “{_prior_guid}”").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;")
            if _cons:
                _c = COLORS["positive"] if _cons["ok"] else COLORS["warning"]
                if _cons["ok"]:
                    _m = f"✓ The drafted language states the decided ${_cons['low']:.1f}–{_cons['high']:.1f}M range."
                else:
                    _miss = ", ".join(x for x, ok in (("low end", _cons["low_ok"]), ("high end", _cons["high_ok"])) if not ok)
                    _m = (f"⚠ The drafted language does NOT state the decided ${_cons['low']:.1f}–{_cons['high']:.1f}M "
                          f"range ({_miss} missing) — regenerate before it ships.")
                ui.label(_m).style(f"color:{_c};font-size:var(--fs-sm);font-weight:600;margin-top:2px;")

    with ui.row().classes("w-full items-center no-wrap").style(
            f"background:{COLORS['accent']}14;border:1px solid {COLORS['accent']};border-radius:8px;"
            "padding:9px 12px;margin-top:8px;gap:10px;"):
        ui.icon("edit_note").style(f"color:{COLORS['accent']};font-size:22px;flex:none;")
        with ui.column().classes("flex-1").style("gap:3px;"):
            ui.label("Add any H2 visibility or context before drafting (optional)").style(
                f"color:{COLORS['text_heading']};font-size:var(--fs-xs);font-weight:700;")
            guidance_context_input = ui.input(
                placeholder="e.g. H2 visibility good — new-partner go-lives ramp in Q3.",
                value=gd.get("context", "")).props("outlined dense").classes("w-full")

    def render_guidance_draft_box(text):
        draft_area.clear()
        with draft_area:
            ui.label("Guidance draft — edit as needed, then submit (all [FLS] blocks need Legal review):").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            box = ui.textarea(value=text).classes("w-full").props("rows=10 outlined")
            _pn, _pcl = _pacing_estimate(text)
            pace_label = ui.label(_pn).style(f"color:{_pcl};font-size:var(--fs-xs);")

            def save_edit(e, pace_label=pace_label):
                gd["text"] = e.value
                ss["guidance_decision"] = gd
                _save_json("script_workflow_state.json", ss)
                _n, _cl = _pacing_estimate(e.value)
                pace_label.text = _n
                pace_label.style(f"color:{_cl};font-size:var(--fs-xs);")
            box.on_value_change(save_edit)

            def submit(box=box):
                gd["text"] = box.value
                ss["guidance_decision"] = gd
                _save_json("script_workflow_state.json", ss)
                fy = (_ge.commit_fy_guidance(gd.get("new_low"), gd.get("new_hi"))
                      if gd.get("new_low") is not None else None)
                if on_submit:
                    on_submit()            # re-assemble the Full Script panel so this edit shows immediately
                ui.notify("Guidance submitted to script." + (f" {fy} updated across the platform." if fy else ""),
                          type="positive")
            ui.button("Submit to Script", on_click=submit).props("color=primary dense").style("margin-top:4px;")

    def generate_guidance(guidance_context_input=guidance_context_input):
        ui.notify("Generating guidance draft…", type="info")
        try:
            nl2, nh2 = gd.get("new_low"), gd.get("new_hi")
            if nl2 is None:
                nl2, nh2 = _new
            _ch2 = _ge.characterize_range_change(_prior, [nl2, nh2])
            action, rationale = _ch2["action_key"], _ch2["signal"]
            draft, was_ai = _generate_guidance_draft(ss, action, nl2, nh2, rationale, guidance_context_input.value)
            gd.update({"action": action, "new_low": nl2, "new_hi": nh2, "rationale": rationale,
                       "context": guidance_context_input.value, "text": draft})
            ss["guidance_decision"] = gd
            _save_json("script_workflow_state.json", ss)
            render_guidance_draft_box(draft)
            ui.notify("Drafted — review below, then Submit." if was_ai else
                      "AI unavailable — templated draft. Review, then Submit.",
                      type="positive" if was_ai else "warning")
        except Exception as exc:
            ui.notify(f"Guidance draft generation failed: {exc}", type="negative")
            raise

    ui.button("Draft the guidance language with AI", icon="auto_awesome",
              on_click=generate_guidance).props("color=primary dense").style("margin-top:4px;")
    draft_area = ui.column().classes("w-full").style("margin-top:8px;")
    if gd.get("text"):
        render_guidance_draft_box(gd["text"])


def _render_guidance_decision(ss, context="script", on_submit=None):
    """Guidance & Outlook Decision Engine — renders ahead of the CEO's own
    Step 1 review in _render_persona_steps, since the CEO narrative's tone/
    H2-confidence language/closing are all supposed to flow from whichever
    guidance action is decided here (matching app.py's "Workflow note" —
    aspirational there since the widgets sat below the CEO editor in the
    same tab; enforced by placement here instead).

    context="markets" is passed when this same engine is rendered inline on
    the Consensus & Estimates guidance card (so the CFO can set the decision
    there and have it write through to the script) — it only adjusts the
    Workflow note, which otherwise refers to the CEO narrative "below" that
    exists on the script page but not on Markets."""
    gd = ss.setdefault("guidance_decision", {})
    math_ = _guidance_math(ss)
    from core import guidance_engine as _ge

    # Deep-link anchor — Markets "Open the Guidance Decision Engine" scrolls here.
    ui.html('<div id="guidance-engine-anchor" style="scroll-margin-top:80px"></div>')

    # WAS (prior guide) and IS (the decided range, else the recommended action's range as a starting point).
    _prior = ((((ss.get("guidance_inputs") or {}).get("metrics") or {}).get("rev") or {}).get("prior_fy_range")
              or [math_["fy_low"], math_["fy_hi"]])
    if gd.get("new_low") is not None and gd.get("new_hi") is not None:
        _new = [float(gd["new_low"]), float(gd["new_hi"])]
    else:
        _dl, _dh, _ = _ge.apply_action(
            {"RAISE_MID": "raise_mid", "RAISE_LOW": "raise_low"}.get(math_["scenario"], "reiterate"), math_)
        _new = [round(_dl, 1), round(_dh, 1)]
    _ch = _ge.characterize_range_change(_prior, _new)          # the numbers → the action (calculated, not picked)
    _iu = _ge.implied_upside(_new, _load_json("earnings_surprise_log.json", None))   # the sandbag gap

    # NEXT YEAR (FY+1) — companies guide ONE year out, so FY27 is the STREET's number plus what the FY26
    # raise implies for it (roll-forward lifts the base). Never presented as company guidance.
    _rev_in = (((ss.get("guidance_inputs") or {}).get("metrics") or {}).get("rev") or {})
    _nfs = _rev_in.get("next_fy_street")
    _new_mid = (_new[0] + _new[1]) / 2
    _prior_mid = (_prior[0] + _prior[1]) / 2
    _goff = (_nfs - _new_mid) / _new_mid * 100 if _nfs else None
    _rfl = (_new_mid * (_nfs / _prior_mid) - _nfs) if (_nfs and _prior_mid) else None

    # NEXT QUARTER (Q3) — a company can guide the year AND get asked "what's next quarter?". Show the next
    # quarter IMPLIED by the full-year guide: remaining-to-midpoint split by seasonal weight, YoY vs the
    # prior-year same quarter. Derived from the FY decision, so it recalculates when the range changes.
    _ytd = _rev_in.get("ytd")
    _rqs = _rev_in.get("remaining_quarters") or []
    _q3 = next((q for q in _rqs if str(q.get("q")).upper() == "Q3"), None) or (_rqs[0] if _rqs else None)
    _tw = sum(q.get("weight", 0) for q in _rqs) or 1
    _q3_impl = _q3_yoy = _q3_lbl = None
    if _ytd is not None and _q3:
        _q3_impl = (_new_mid - _ytd) * (_q3.get("weight", 0) / _tw)
        _q3_lbl = _q3.get("q")
        if _q3.get("prior_yr"):
            _q3_yoy = (_q3_impl / _q3["prior_yr"] - 1) * 100

    # Implied YoY growth at each end of the range vs prior-year FY revenue — the number the guide really
    # states (a $M level is meaningless without its growth rate). Trend = is the new guide raising or
    # lowering the implied growth rate vs the prior guide.
    _pfr = sum((CGP().get("prior_fy_quarterly_revenue") or {}).values()) or None
    _g = (lambda x: f"{(x / _pfr - 1) * 100:+.0f}%") if _pfr else (lambda x: "—")

    def _grow_line(rng):
        lo, hi = rng[0], rng[1]
        return f"growth: low {_g(lo)} · mid {_g((lo + hi) / 2)} · high {_g(hi)}"
    _pm_g = ((_prior[0] + _prior[1]) / 2 / _pfr - 1) * 100 if _pfr else None
    _nm_g = ((_new[0] + _new[1]) / 2 / _pfr - 1) * 100 if _pfr else None
    _trend_pp = round(_nm_g - _pm_g, 1) if (_pm_g is not None and _nm_g is not None) else None

    # ── ① SET GUIDANCE — the first thing on the page; the whole script derives from it ──
    _gim = ((ss.get("guidance_inputs") or {}).get("metrics") or {})

    def _mrange(key):
        m = _gim.get(key, {}) or {}
        return m.get("prior_fy_range"), (m.get("new_fy_range") or m.get("prior_fy_range"))
    _eps_pr, _eps_nw = _mrange("eps")
    _ebd_pr, _ebd_nw = _mrange("ebitda")

    ui.label("① Guidance analysis — the guided quarter, the year, and next year").classes("font-bold").style(
        "font-size:var(--fs-lg);")
    ui.label("The ranges are set on the CFO screen (Stage 1); this reads what they mean for each period and "
             "feeds the guidance language in the script below.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

    # Per-metric FY guided analysis (every line the company gives) + the Q3 range from the FY guide.
    def _fyg(rng, base):   # YoY growth of the guide range vs prior-year FY actual, at low/mid/high
        return None if not base else [(rng[0] / base - 1) * 100, ((rng[0] + rng[1]) / 2 / base - 1) * 100,
                                      (rng[1] / base - 1) * 100]
    _guided = []
    for _gk, _gn, _gf in (("rev", "Revenue", "money"), ("eps", "Adj. EPS", "eps"), ("ebitda", "Adj. EBITDA", "money")):
        _gm = _gim.get(_gk, {})
        _gp, _gw = _gm.get("prior_fy_range"), (_gm.get("new_fy_range") or _gm.get("prior_fy_range"))
        if not (_gp and _gw and _gp[0] is not None and _gw[0] is not None):
            continue
        _gbase = _gm.get("prior_fy_actual") or (_pfr if _gk == "rev" else None)
        _guided.append({"nm": _gn, "fmt": _gf, "pr": _gp, "nw": _gw, "ch": _ge.characterize_range_change(_gp, _gw),
                        "g": _fyg(_gw, _gbase), "nfs": _gm.get("next_fy_street"), "mid": (_gw[0] + _gw[1]) / 2})
    _q3rng = None
    if _q3 and _ytd is not None and _q3.get("prior_yr"):
        _fr3, _py3 = _q3.get("weight", 0) / _tw, _q3["prior_yr"]
        _lo3, _mi3, _hi3 = (_new[0] - _ytd) * _fr3, (_new_mid - _ytd) * _fr3, (_new[1] - _ytd) * _fr3
        _q3rng = {"q": _q3.get("q"), "rows": [("Low", _lo3, (_lo3 / _py3 - 1) * 100),
                                              ("Mid", _mi3, (_mi3 / _py3 - 1) * 100),
                                              ("High", _hi3, (_hi3 / _py3 - 1) * 100)]}
    _hcell = (f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;"
              "letter-spacing:.03em;font-weight:700;")

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:5px solid {COLORS['accent']};border-radius:10px;padding:14px 16px;"):
        with ui.row().classes("w-full gap-4 items-stretch flex-wrap"):
            # ── NEXT QUARTER (Q3) — the revenue RANGE the FY guide implies (low/mid/high), YoY on each.
            with ui.column().classes("flex-[2]").style(
                    f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};border-radius:8px;"
                    "padding:11px 14px;min-width:210px;gap:4px;"):
                ui.label(f"Next Quarter — {(_q3rng or {}).get('q', 'Q3')} · from the FY guide").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.04em;font-weight:700;")
                if _q3rng:
                    with ui.element("div").style("display:grid;grid-template-columns:auto auto auto;gap:2px 12px;align-items:baseline;"):
                        for _lb, _vv, _yy in _q3rng["rows"]:
                            ui.label(_lb).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                            ui.label(f"${_vv:.1f}M").style(
                                f"color:{COLORS['text_heading']};font-size:var(--fs-sm);font-weight:700;font-variant-numeric:tabular-nums;")
                            _yc = COLORS["positive"] if _yy >= 0 else COLORS["danger"]
                            ui.label(f"{_yy:+.0f}% YoY").style(
                                f"color:{_yc};font-size:var(--fs-xs);font-weight:700;font-variant-numeric:tabular-nums;")
                    ui.label("Revenue — the Q3 seasonal share of your full-year guide; a range, not a point.").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.4;margin-top:2px;")
                else:
                    ui.label("No seasonal split on file.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            # ── FULL YEAR (FY26) — TABLE: every guided line, Prior → New (each on ONE line), action, YoY low·mid·high.
            # One compact range per cell (Prior in its own column, New in its own) so a row never stacks four
            # numbers into a wrapped pile — Prior range → New range → three growth numbers, left to right.
            def _rngc(rng, fmt):
                lo, hi = rng
                if fmt == "eps":
                    return f"${lo:.2f}–{hi:.2f}"
                _n = lambda v: (f"{v:.1f}".rstrip("0").rstrip("."))   # 104.0→"104", 21.5→"21.5"
                return f"${_n(lo)}–{_n(hi)}M"
            with ui.column().classes("flex-[3]").style(
                    f"background:{COLORS['accent']}0F;border:1.5px solid {COLORS['accent']};border-radius:8px;"
                    "padding:11px 14px;min-width:250px;gap:3px;"):
                ui.label("Full Year — FY2026 · the guide").style(
                    f"color:{COLORS['accent_light']};font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.04em;font-weight:700;")
                # Stacked per-metric blocks — each guided line labels its OWN fields inline (Prior → New, YoY
                # growth), so the header travels WITH the value instead of sitting in a distant top row. Reads
                # top-to-bottom per line, no eye-mapping back to a column header.
                for _e in _guided:
                    _tc2 = COLORS[_BR_TAG.get(_e["ch"]["tag"], "warning")] if _BR_TAG.get(_e["ch"]["tag"]) else COLORS["accent"]
                    with ui.column().classes("w-full").style(
                            f"gap:3px;padding:7px 0 5px;border-top:1px solid {COLORS['border']};"):
                        with ui.row().classes("w-full items-center no-wrap").style("gap:8px;"):
                            ui.label(_e["nm"]).style(
                                f"color:{COLORS['text_heading']};font-size:var(--fs-sm);font-weight:700;")
                            ui.space()
                            ui.label(_e["ch"]["tag"]).style(
                                f"background:{_tc2}22;color:{_tc2};font-size:var(--fs-2xs);font-weight:700;"
                                "padding:1px 8px;border-radius:8px;white-space:nowrap;")
                        with ui.row().classes("items-baseline no-wrap flex-wrap").style("gap:5px;"):
                            ui.label("PRIOR").style(_hcell)
                            ui.label(_rngc(_e["pr"], _e["fmt"])).style(
                                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-weight:600;font-variant-numeric:tabular-nums;")
                            ui.label("→").style(f"color:{COLORS['accent']};font-size:var(--fs-xs);font-weight:800;")
                            ui.label("NEW").style(_hcell)
                            ui.label(_rngc(_e["nw"], _e["fmt"])).style(
                                f"color:{COLORS['text_heading']};font-size:var(--fs-xs);font-weight:800;font-variant-numeric:tabular-nums;")
                        with ui.row().classes("items-baseline no-wrap flex-wrap").style("gap:5px;"):
                            ui.label("YoY GROWTH").style(_hcell)
                            ui.label((f"+{_e['g'][0]:.0f}% · +{_e['g'][1]:.0f}% · +{_e['g'][2]:.0f}%") if _e["g"] else "—").style(
                                f"color:{COLORS['positive']};font-size:var(--fs-xs);font-weight:700;font-variant-numeric:tabular-nums;")
                            if _e["g"]:
                                ui.label("low·mid·high").style(
                                    f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")
            # ── NEXT YEAR (FY27) — TABLE: carry ALL three lines' Street out-year + growth off the FY26 mid.
            with ui.column().classes("flex-[3]").style(
                    f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};border-radius:8px;"
                    "padding:11px 14px;min-width:240px;gap:4px;"):
                ui.label("Next Year — FY2027 · Street (not guided)").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;letter-spacing:.04em;font-weight:700;")
                with ui.element("div").style(
                        "display:grid;grid-template-columns:auto auto auto;gap:4px 12px;align-items:baseline;width:100%;"):
                    for _h in ("Line", "Street FY27", "off FY26 mid"):
                        ui.label(_h).style(_hcell)
                    for _e in _guided:
                        ui.label(_e["nm"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);font-weight:600;")
                        if _e["nfs"]:
                            ui.label(_fmt_metric(_e["nfs"], _e["fmt"])).style(
                                f"color:{COLORS['text_heading']};font-size:var(--fs-xs);font-weight:700;font-variant-numeric:tabular-nums;")
                            _go2 = (_e["nfs"] - _e["mid"]) / _e["mid"] * 100 if _e["mid"] else None
                            ui.label((f"+{_go2:.0f}%") if _go2 is not None else "—").style(
                                f"color:{COLORS['positive']};font-size:var(--fs-xs);font-weight:700;font-variant-numeric:tabular-nums;")
                        else:
                            ui.label("—").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                            ui.label("").style("color:transparent;")
                if _rfl is not None:
                    ui.label(f"Your FY26 raise lifts the FY27 base ~${_rfl:+.1f}M (roll-forward).").style(
                        f"color:{COLORS['positive']};font-size:var(--fs-2xs);font-weight:600;line-height:1.4;")
                ui.label("Street's number, not yours — the read is whether the trend makes it a low bar (② below).").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.4;")
        _tagclr = COLORS[_BR_TAG.get(_ch["tag"], "warning")] if _BR_TAG.get(_ch["tag"]) else COLORS["accent"]
        # ONE green paragraph: what you did + the single insight that adds value (consensus re-anchors above
        # your high end → the guide is a floor). Condensed from the old grey "You did" line + "signal" line +
        # long upside callout, which restated "you raised" three ways.
        if _iu:
            _str = f"; {_ch['strength']}" if _ch.get("strength") else ""
            _one = (f"<b>{_ch['action']}</b> — midpoint {_ch['d_mid']:+.1f}M, range {_ch['width_change']}{_str}. "
                    f"You've cleared Street {_iu['beat_rate']} quarters (avg +{_iu['avg_beat_pct']:.1f}%), so "
                    f"consensus re-anchors near ~${_iu['street_implied']:.1f}M — about ${_iu['above_high']:.1f}M "
                    f"above your ${_iu['new_high']:.1f}M high end. The guide is a floor; that's where the whisper sits.")
            with ui.row().classes("w-full items-start no-wrap").style(
                    f"gap:8px;background:{COLORS['positive']}12;border-left:3px solid {COLORS['positive']};"
                    "border-radius:6px;padding:9px 12px;margin-top:10px;"):
                ui.label("↗").style(f"color:{COLORS['positive']};flex:none;font-weight:800;")
                ui.html(_one).style(f"color:{COLORS['positive']};font-size:var(--fs-sm);line-height:1.5;font-weight:500;")
        else:
            with ui.row().classes("w-full items-baseline gap-2 flex-wrap").style("margin-top:10px;"):
                ui.label("You did:").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                ui.label(_ch["action"]).style(f"color:{_tagclr};font-weight:800;font-size:var(--fs-sm);")
                ui.label(f"· midpoint {_ch['d_mid']:+.1f}M · range {_ch['width_change']}").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-variant-numeric:tabular-nums;")

    # ── ② READ THE IMPACT — the bridge, driven by the range set above ──
    ui.label("② Read the impact").classes("font-bold").style("font-size:var(--fs-lg);margin-top:12px;")
    _render_guidance_bridge(ss)

    # ── ③ DRAFT THE LANGUAGE — from the decision, matched to last quarter, numbers verified ──
    ui.label("③ Draft the language").classes("font-bold").style("font-size:var(--fs-lg);margin-top:12px;")
    _prior_guid = _guidance_prior_language()
    _cons = _guidance_consistency(gd)
    if _prior_guid or _cons:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;padding:10px 14px;"):
            if _prior_guid:
                ui.label(f"Prior quarter's wording (match this structure): “{_prior_guid}”").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;")
            if _cons:
                _c = COLORS["positive"] if _cons["ok"] else COLORS["warning"]
                if _cons["ok"]:
                    _m = f"✓ The drafted language states the decided ${_cons['low']:.1f}–{_cons['high']:.1f}M range."
                else:
                    _miss = ", ".join(x for x, ok in (("low end", _cons["low_ok"]), ("high end", _cons["high_ok"])) if not ok)
                    _m = (f"⚠ The drafted language does NOT state the decided ${_cons['low']:.1f}–{_cons['high']:.1f}M "
                          f"range ({_miss} missing) — regenerate before it ships.")
                ui.label(_m).style(f"color:{_c};font-size:var(--fs-sm);font-weight:600;margin-top:2px;")

    # Surfaced input — this optional field was too easy to miss as a bare underline. Tinted, bordered
    # container + a bold label + icon so it reads clearly as an actionable input.
    with ui.row().classes("w-full items-center no-wrap").style(
            f"background:{COLORS['accent']}14;border:1px solid {COLORS['accent']};border-radius:8px;"
            "padding:9px 12px;margin-top:8px;gap:10px;"):
        ui.icon("edit_note").style(f"color:{COLORS['accent']};font-size:22px;flex:none;")
        with ui.column().classes("flex-1").style("gap:3px;"):
            ui.label("Add any H2 visibility or context before drafting (optional)").style(
                f"color:{COLORS['text_heading']};font-size:var(--fs-xs);font-weight:700;")
            guidance_context_input = ui.input(
                placeholder="e.g. H2 visibility good — new-partner go-lives ramp in Q3.",
                value=gd.get("context", "")).props("outlined dense").classes("w-full")

    def render_guidance_draft_box(text):
        draft_area.clear()
        with draft_area:
            ui.label("Guidance draft — edit as needed, then submit (all [FLS] blocks need Legal review):").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            box = ui.textarea(value=text).classes("w-full").props("rows=10 outlined")
            _pn, _pcl = _pacing_estimate(text)   # neutral length only — a guidance STATEMENT is a tight
            #                                       paragraph, not a 4-min spoken section, so no norm comparison
            pace_label = ui.label(_pn).style(f"color:{_pcl};font-size:var(--fs-xs);")

            def save_edit(e, pace_label=pace_label):
                gd["text"] = e.value
                ss["guidance_decision"] = gd
                _save_json("script_workflow_state.json", ss)
                _n, _cl = _pacing_estimate(e.value)
                pace_label.text = _n
                pace_label.style(f"color:{_cl};font-size:var(--fs-xs);")
            box.on_value_change(save_edit)

            def submit(box=box):
                gd["text"] = box.value
                ss["guidance_decision"] = gd
                _save_json("script_workflow_state.json", ss)
                fy = (_ge.commit_fy_guidance(gd.get("new_low"), gd.get("new_hi"))
                      if gd.get("new_low") is not None else None)
                if on_submit:
                    on_submit()            # re-assemble the Full Script panel so this edit shows immediately
                ui.notify("Guidance submitted to script." + (f" {fy} updated across the platform." if fy else ""),
                          type="positive")
            ui.button("Submit to Script", on_click=submit).props("color=primary dense").style("margin-top:4px;")

    def generate_guidance(guidance_context_input=guidance_context_input):
        ui.notify("Generating guidance draft…", type="info")
        try:
            nl2, nh2 = gd.get("new_low"), gd.get("new_hi")
            if nl2 is None:
                nl2, nh2 = _new
            _ch2 = _ge.characterize_range_change(_prior, [nl2, nh2])
            action, rationale = _ch2["action_key"], _ch2["signal"]
            draft, was_ai = _generate_guidance_draft(ss, action, nl2, nh2, rationale, guidance_context_input.value)
            gd.update({"action": action, "new_low": nl2, "new_hi": nh2, "rationale": rationale,
                       "context": guidance_context_input.value, "text": draft})
            ss["guidance_decision"] = gd
            _save_json("script_workflow_state.json", ss)
            render_guidance_draft_box(draft)
            ui.notify("Drafted — review below, then Submit." if was_ai else
                      "AI unavailable — templated draft. Review, then Submit.",
                      type="positive" if was_ai else "warning")
        except Exception as exc:
            ui.notify(f"Guidance draft generation failed: {exc}", type="negative")
            raise

    ui.button("Draft the guidance language with AI", icon="auto_awesome",
              on_click=generate_guidance).props("color=primary dense").style("margin-top:4px;")
    draft_area = ui.column().classes("w-full").style("margin-top:8px;")
    if gd.get("text"):
        render_guidance_draft_box(gd["text"])

    # Reference — what the Street expects each quarter (collapsed; an IR pro rarely needs it open).
    with ui.expansion("Reference — what the Street expects at each quarter").classes(
            "w-full panel-tinted").props("dense").style("margin-top:10px;"):
        _rh = lambda t: ui.label(t).classes("font-bold").style(
            f"color:{COLORS['text_heading']};font-size:var(--fs-sm);margin-top:8px;")
        _rp = lambda t: ui.label(t).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);line-height:1.55;")
        _rh("Q1 — the Street expects reiteration")
        _rp("Raising after one quarter signals a sandbagged range or getting ahead of the data.")
        _rh("Q2 — the first real decision point")
        _rp("H1 is banked, so a raise is expected if the beat is meaningful: beat + YTD>50% of midpoint → raise the "
            "low end; beat + strong H2 visibility → raise the midpoint; in-line → reiterate with specific H2 "
            "language; miss → hold with a recovery bridge, never cut without one.")
        _rh("The phrases signal intent")
        _rp("“Raising” = max positive · “Narrowing to reflect improved visibility” = positive but measured · "
            "“Continue to expect / reiterating” = conservative · “Updating our guidance” = usually precedes a cut.")

    ui.markdown("---")


def _render_persona_steps(ss, role, key, on_submit=None):
    """Step 1 (review last quarter) / Step 2 (what's new) / Step 3 (generate)
    for one persona's script-canvas panel — ported from app.py's per-persona
    3-step drafting pattern (previously collapsed into a single bare
    "Generate with AI" button in this port). The generated/edited draft now
    lives in its own box directly under Step 3 (previously it silently
    overwrote a text box up at the top of the tab, off-screen from Step 3's
    Generate button — from the user's seat that looked exactly like nothing
    had happened) with an explicit "Submit to Script" action, rather than
    relying purely on autosave-on-edit to make the update feel confirmed.
    CEO gets an extra Guidance & Outlook Decision Engine ahead of Step 1 —
    see _render_guidance_decision. IR gets the locked Call Opening (operator
    + Reg FD/safe-harbor reading) ahead of Step 1 — see _render_call_opening."""
    # The Guidance & Outlook Decision Engine used to render here, inside the IR and CEO persona panels
    # (twice on the page, buried three screens down). It's the keystone the whole script derives from, so
    # it now renders ONCE at the top of the Script Canvas (_render_script_canvas), ahead of every persona.
    # Call Opening moved to the TOP of ④ (_render_script_canvas), ahead of the "Refine every section" tool —
    # it's the fixed operator+welcome+safe-harbor that opens the call, so it reads first, not buried in IR's panel.
    ref = _persona_last_quarter().get(role, {})
    notes = ss.setdefault("persona_notes", {}).setdefault(key, {"whats_new": "", "final_notes": ""})

    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};padding:10px;box-shadow:none;border:1px solid {COLORS['border']};"):
        ui.label("Step 1 — Review: What Was Said Last Quarter").classes("font-bold").style("font-size:var(--fs-base);")
        _shown = False
        # VERBATIM — the speaker's actual prior-quarter transcript turn, word for word (not the AI summary),
        # in a scrollable box so a long turn doesn't dominate the section. This is what you reprise/update.
        if ref.get("verbatim"):
            ui.label("Verbatim — exactly what was said last quarter" + (f" ({ref['speaker']})" if ref.get("speaker") else "")).style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:2px;")
            with ui.element("div").style(
                    f"max-height:150px;overflow-y:auto;background:{COLORS['surface_hover_bg']};"
                    f"border:1px solid {COLORS['border']};border-radius:6px;padding:8px 11px;margin-top:3px;"):
                ui.label(f"“{ref['verbatim']}”").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);line-height:1.55;")
            _shown = True
        elif ref.get("quote"):
            ui.label(f"“{ref['quote']}”").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-style:italic;margin-top:4px;")
            _shown = True
        for q_label, q_text in ref.get("prior_quotes", []):
            ui.label(f"{q_label}: “{q_text}”").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;")
            _shown = True
        if ref.get("rows"):
            with ui.column().classes("w-full gap-0").style("margin-top:4px;"):
                for r_label, r_val in ref["rows"]:
                    ui.label(f"{r_label}: {r_val}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
            _shown = True
        for tag in ref.get("tags", []):
            ui.label(f"• {tag}").style(f"color:{COLORS['accent_light']};font-size:var(--fs-xs);margin-top:2px;")
        if not _shown:
            ui.label("No prior-quarter reference on file yet for this persona.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    question, placeholder = _PERSONA_WHATS_NEW.get(role, ("What's new this quarter?", ""))
    ui.label(f"Step 2 — {question}").classes("font-bold").style("font-size:var(--fs-base);margin-top:8px;")

    # Seed from the actual Q1 post-mortem critique for this persona's
    # section, instead of leaving Step 2 a blank box with just an
    # illustrative placeholder — the user's specific ask. Shown as a visible
    # reference card (not just a silent prefill) so it's clear WHY the text
    # is there, and only auto-seeded once (via "whats_new_seeded") so a
    # deliberate clear by the user later doesn't keep getting overwritten.
    # Deliberately NOT _get_current_qa_actions() here: which persona should
    # own a given finding is a curatorial judgment call the hand-authored
    # _Q1_TO_Q2_ACTIONS makes explicitly (via "persona_role"), but
    # transcripts.compute_qa_preemption_delta can't infer that from raw
    # qa_risk_topics text without guessing — its items all carry
    # persona_role=None by design (see core/transcripts.py) and surface
    # instead in the Q&A Prep tab, which isn't persona-scoped. Once a
    # second quarter exists, someone should hand-curate persona_role
    # assignments the same way this quarter's list was, rather than have
    # this silently guess.
    critique_items = [a for a in _Q1_TO_Q2_ACTIONS if a.get("persona_role") == role]
    if critique_items:
        ui.label("From the Q1 post-mortem — carry forward unless already addressed:").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        for a in critique_items:
            with ui.card().classes("w-full").style(f"background:rgba(0,0,0,.15);border:1px solid {a['clr']};margin-bottom:4px;padding:6px 10px;"):
                ui.label(f"{a['icon']} {a['priority']} · {a['q1_finding']}").style(f"color:{a['clr']};font-size:var(--fs-xs);font-weight:bold;")
                ui.label(a["action"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                ui.label(a["impact"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;")
        if not notes.get("whats_new") and not notes.get("whats_new_seeded"):
            notes["whats_new"] = "; ".join(a["action"] for a in critique_items)
            notes["whats_new_seeded"] = True
            _save_json("script_workflow_state.json", ss)

    ui.label("Your instruction for this section — this is what the AI uses to draft Step 3 (edit freely):").style(
        f"color:{COLORS['text_heading']};font-size:var(--fs-xs);font-weight:600;margin-top:6px;")
    whats_new_input = ui.textarea(placeholder=placeholder, value=notes.get("whats_new", "")).classes("w-full").props("rows=2 outlined")

    def save_whats_new(e, notes=notes):
        notes["whats_new"] = e.value
        _save_json("script_workflow_state.json", ss)

    whats_new_input.on_value_change(save_whats_new)

    ui.label("Step 3 — Generate Draft").classes("font-bold").style("font-size:var(--fs-base);margin-top:8px;")
    if role in ("IR", "CFO", "CEO"):
        tone = _tone_context(ss)
        ui.label(f"Tone read from Stage 1 numbers: {tone['label']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    final_notes_input = ui.input("Additional notes for this draft (optional)", value=notes.get("final_notes", "")).props("outlined dense").classes("w-full")

    def save_final_notes(e, notes=notes):
        notes["final_notes"] = e.value
        _save_json("script_workflow_state.json", ss)

    final_notes_input.on_value_change(save_final_notes)

    # render_draft_box/generate are defined here but the "Generate with AI"
    # button and draft_area's actual placement (below) are what determine
    # visual order — draft_area is created AFTER the button now, not
    # before, so the box (and its Submit button) appears under Generate
    # instead of above it. Previously draft_area was created first (to
    # satisfy an "area=draft_area" default-argument trick), which put an
    # empty box above the Generate button — read top-to-bottom, it looked
    # like Submit came before Generate. Fixed by having render_draft_box
    # read draft_area as a normal closure variable (resolved when it's
    # actually called, not when it's defined) instead of a default arg.
    def render_draft_box(text, key=key, role=role):
        draft_area.clear()
        with draft_area:
            ui.label("Draft — edit as needed, then submit it into the script:").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            box = ui.textarea(value=text).classes("w-full").props("rows=8 outlined")
            pace_note, pace_clr = _pacing_estimate(text, role)
            pace_label = ui.label(pace_note).style(f"color:{pace_clr};font-size:var(--fs-xs);")

            def save_edit(e, key=key, pace_label=pace_label, role=role):
                ss["script_text"][key] = e.value
                _save_json("script_workflow_state.json", ss)
                note, clr = _pacing_estimate(e.value, role)
                pace_label.text = note
                pace_label.style(f"color:{clr};font-size:var(--fs-xs);")

            box.on_value_change(save_edit)

            # Refine with AI — revise the CURRENT (possibly hand-edited) draft per a
            # free-text instruction, in place, keeping the edits. Iterative: the
            # instruction box stays so the user can keep nudging the same draft.
            # This is the non-destructive counterpart to "Generate with AI" (which
            # starts over from the numbers); it reads box.value, so whatever the
            # user has typed/edited is what gets refined.
            with ui.row().classes("w-full items-end gap-2").style("margin-top:6px;"):
                refine_input = ui.input(
                    label="Refine with AI — instruction (your edits are kept)",
                    placeholder="e.g. tighten to 4 sentences · less promotional · work in the RTP win · firmer guidance",
                ).classes("flex-grow").props("dense outlined")

                def refine(box=box, key=key, role=role, refine_input=refine_input, pace_label=pace_label):
                    instr = (refine_input.value or "").strip()
                    if not instr:
                        ui.notify("Type an instruction first — what should change?", type="warning")
                        return
                    if not (box.value or "").strip():
                        ui.notify("Nothing to refine yet — generate a draft first.", type="warning")
                        return
                    ui.notify("Refining draft…", type="info")
                    try:
                        revised, was_ai = _refine_persona_draft(box.value, instr, role, ss)
                        if not was_ai:
                            ui.notify("Refine needs the AI (ANTHROPIC_API_KEY) — draft left unchanged.",
                                      type="warning")
                            return
                        box.value = revised
                        ss["script_text"][key] = revised
                        _save_json("script_workflow_state.json", ss)
                        note, clr = _pacing_estimate(revised, role)
                        pace_label.text = note
                        pace_label.style(f"color:{clr};font-size:var(--fs-xs);")
                        ui.notify("Refined — review above; refine again or Submit.", type="positive")
                    except Exception as exc:
                        ui.notify(f"Refine failed: {exc}", type="negative")
                        raise

                ui.button("Refine", icon="auto_fix_high", on_click=refine).props(
                    "color=primary dense outline")

            def submit_to_script(box=box, key=key, role=role):
                ss["script_text"][key] = box.value
                _save_json("script_workflow_state.json", ss)
                if on_submit:
                    on_submit()            # re-assemble the Full Script panel so this edit shows immediately
                ui.notify(f"Submitted to script — {role} section updated.", type="positive")

            ui.button("Submit to Script", on_click=submit_to_script).props("color=primary dense").style("margin-top:4px;")

    def _do_generate(role=role, key=key, whats_new_input=whats_new_input, final_notes_input=final_notes_input):
        # Wrapped in try/except + an immediate "Generating…" notify — a bare
        # click that produces neither a draft nor an error is exactly what a
        # silent server-side exception looks like from the browser (NiceGUI
        # logs it to the console, not the UI). This makes failures visible
        # instead of looking like the button did nothing.
        ui.notify("Generating draft…", type="info")
        try:
            combined = " | ".join(filter(None, [whats_new_input.value, final_notes_input.value]))
            draft, was_ai = _generate_persona_draft(role, ss, combined)
            if not draft:
                ui.notify("Generation returned nothing — check Stage 1 numbers were submitted.", type="warning")
                return
            render_draft_box(draft)
            ui.notify("Drafted with AI — review below, then Submit." if was_ai else
                      "AI unavailable — used a numbers-based fallback draft. Review below, then Submit.",
                      type="positive" if was_ai else "warning")
        except Exception as exc:
            ui.notify(f"Draft generation failed: {exc}", type="negative")
            raise

    def generate(key=key):
        # "Generate with AI" starts OVER from the numbers + notes and replaces the
        # draft box wholesale. If a draft already exists (a prior generate, a manual
        # edit, or a refine), confirm first so a stray click can't wipe that work —
        # the non-destructive path is "Refine" on the draft itself.
        if (ss["script_text"].get(key) or "").strip():
            with ui.dialog() as _dlg, ui.card():
                ui.label("Regenerate from scratch?").classes("font-bold").style(
                    f"color:{COLORS['text_heading']};")
                ui.label("This replaces the current draft — including your edits — with a fresh AI draft built "
                         "from the numbers and notes. To keep your text and adjust it instead, use “Refine” on "
                         "the draft below.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);max-width:420px;")
                with ui.row().classes("justify-end w-full gap-2").style("margin-top:6px;"):
                    ui.button("Cancel", on_click=_dlg.close).props("flat dense")

                    def _go():
                        _dlg.close()
                        _do_generate()
                    ui.button("Regenerate", icon="refresh", on_click=_go).props("color=primary dense")
            _dlg.open()
        else:
            _do_generate()

    ui.button("Generate with AI", on_click=generate).props("color=primary dense").style("margin-top:6px;")

    draft_area = ui.column().classes("w-full").style("margin-top:8px;")

    # If this persona already has saved script text (from a prior session or
    # a previous Submit), show it immediately rather than requiring a fresh
    # Generate click just to see/edit existing content.
    existing = ss["script_text"].get(key, "")
    if existing:
        render_draft_box(existing)


def _build_qa_prep(ss):
    """Predicted Q&A for this quarter's call — deterministic (no AI call, so
    it's always available), combining two real sources: (a) topics that
    were NOT pre-empted last quarter (_Q1_QA_TOPICS — a question that
    already surfaced once is likely to resurface if it's still not
    addressed head-on), and (b) catalysts/risks flagged in every ingested
    sell-side research note (core/inbox_queue.py's research_note items,
    CFA-lens extracted by core/email_classifier.py), regardless of whether
    that note has since been marked reviewed. This is the "Build
    analyst-specific Q&A prep" item the Q1 post-mortem flagged as never
    built in the original app.py."""
    items = []
    for topic, preempted, note in _Q1_QA_TOPICS:
        if not preempted:
            items.append({
                "topic": topic, "severity": "HIGH" if "NOT pre-empted" in note else "MEDIUM",
                "source": "Recurring from last quarter", "detail": note,
                "suggested_angle": f"Address \"{topic}\" proactively in the relevant section this time — "
                                    f"it already drew live questions once.",
            })
    seen_topics = {i["topic"] for i in items}
    for note_item in inbox_queue.list_items_by_category("research_note"):
        extracted = note_item.get("extracted") or {}
        catalysts_risks = extracted.get("catalysts_risks")
        if not catalysts_risks or catalysts_risks in seen_topics:
            continue
        seen_topics.add(catalysts_risks)
        firm = note_item.get("firm") or "an analyst"
        sentiment = extracted.get("sentiment", "")
        items.append({
            "topic": catalysts_risks, "severity": "MEDIUM",
            "source": f"Flagged by {firm}" + (f" ({sentiment})" if sentiment else ""),
            "detail": extracted.get("thesis_summary", ""),
            "suggested_angle": f"{firm} is watching this — consider addressing it directly in the script "
                                f"rather than waiting for it to come up in Q&A.",
        })
    return items


def _adversarial_qa(ss):
    """AI 'skeptical analyst' pass over the ASSEMBLED script: the toughest follow-up
    questions the prepared remarks LEAVE EXPOSED — a number stated but unexplained, a
    claim without support, a soft spot glossed over — each with why the script invites
    it and a Regulation FD-safe answer angle (public info only; never a new number,
    never guidance, never MNPI). Grounded in the deterministic Q&A prep (research-note
    catalysts + last quarter's un-pre-empted topics) so it reflects what analysts have
    actually flagged. Returns a list of {question, why, angle}; [] if no script / no AI."""
    script = _assembled_script_text(ss)
    if not script.strip():
        return []
    ticker = CT("ticker", "")
    prep = _build_qa_prep(ss)
    grounding = "\n".join(f"- {i['topic']} ({i['source']})" for i in prep) or "(none on file)"
    # Seed with the house Q&A bank — recurring questions analysts have actually asked
    # (accrued from prior calls' surprises, across every client), so a question that
    # blindsided us once gets checked against every future script.
    try:
        from core import qa_bank
        _house = qa_bank.questions(get_active_client_id(), limit=25)
    except Exception:
        _house = []
    house_block = "\n".join(f"- {q}" for q in _house) or "(none on file)"
    _cons = market_data.consensus_rev_value()
    cons_line = (f"Street consensus revenue was ${_cons:.1f}M." if isinstance(_cons, (int, float)) and _cons
                 else "No published sell-side consensus is on file for this name.")
    prompt = f"""You are a SKEPTICAL, well-prepared sell-side analyst covering {ticker}. Below is the FULL \
prepared-remarks script the company will read on its upcoming earnings call. Find the toughest follow-up \
questions the script LEAVES EXPOSED — a figure it states but doesn't explain, a claim it makes without \
support, a trend it doesn't address, a soft spot it glosses over, a comparison it invites.

{cons_line}

Topics analysts have ALREADY flagged (ingested research notes + last quarter's unanswered questions) — weave \
these in where the script fails to pre-empt them:
{grounding}

Recurring questions from the HOUSE Q&A BANK — analysts have asked versions of these on prior calls (across \
issuers). For any that THIS script does not clearly pre-empt, surface it as a likely question:
{house_block}

===== BEGIN PREPARED-REMARKS SCRIPT =====
{script}
===== END PREPARED-REMARKS SCRIPT =====

Give 5-8 questions, HARDEST first. For EACH, output EXACTLY this block and nothing else:
Q: <the pointed question an analyst would actually ask on the call>
WHY: <what in THIS script invites it — quote or paraphrase the exposed line>
ANGLE: <a Regulation FD-SAFE way for management to answer: PUBLIC information only. Do NOT invent a number, do \
NOT provide guidance or any unreleased figure, do NOT promise a call/meeting. If an honest answer would need \
undisclosed info, the angle is to acknowledge the question and defer to the next scheduled disclosure.>
---

Rules: base every question on THIS script's actual content — do not fabricate facts about the company, and the \
ANGLE must never manufacture a figure or a forward-looking number."""
    raw = _call_claude_script(prompt, 1400)
    if not raw or not raw.strip():
        return []
    items = []
    for block in raw.split("---"):
        q = why = angle = ""
        for line in block.strip().splitlines():
            s = line.strip()
            if s.lower().startswith("q:"):
                q = s[2:].strip()
            elif s.lower().startswith("why:"):
                why = s[4:].strip()
            elif s.lower().startswith("angle:"):
                angle = s[6:].strip()
        if q:
            items.append({"question": q, "why": why, "angle": angle})
    return items


def _fmt_val(v, label):
    """Format a tie-out figure the way it reads in the script, inferred from the metric label."""
    lo = label.lower()
    if "margin" in lo or "growth" in lo or "yoy" in lo:
        return f"{v:g}%"
    if "eps" in lo:
        return f"${v:.2f}"
    if "volume processed" in lo:
        return f"${v:g}B"
    return f"${v:g}M"


def _number_tieout(ss):
    """Deterministic (no-AI) audit of the ASSEMBLED script against the source-of-truth
    numbers — the CFO's Stage-1 actuals (q2_numbers) and the recorded guidance range.
    Every figure spoken in the script is classified:
      - matched:    equals a submitted value (ties out).
      - mismatches: keyword-anchored NEAR-MISS on a HEADLINE metric — the script states a
                    figure close to (but not equal to) e.g. revenue, right where it talks
                    about revenue. This is the classic stale-number / fat-finger slip.
      - unverified: a figure that doesn't tie to any submitted value (YoY %, prior-year,
                    derived) — usually fine, surfaced for a human eyeball.
      - omitted:    a headline actual that never appears in the script (informational).
    Returns {present, matched[], mismatches[], unverified[], omitted[]}."""
    import math
    import re
    script = _assembled_script_text(ss)
    out = {"present": bool(script.strip()), "matched": [], "mismatches": [], "unverified": [], "omitted": []}
    if not out["present"]:
        return out
    n = ss.get("q2_numbers", {}) or {}
    gd = ss.get("guidance_decision", {}) or {}

    # Source of truth: (label, value, class, keywords, is_headline)
    sources = []

    def add(label, val, cls, kws, headline=False):
        if isinstance(val, (int, float)):
            sources.append((label, float(val), cls, kws, headline))

    add("Revenue", n.get("rev"), "money_m", ["revenue", "top line", "top-line"], True)
    add("Adjusted EBITDA", n.get("ebitda"), "money_m", ["ebitda"], True)
    add("Gross profit", n.get("gp"), "money_m", ["gross profit"])
    add("SG&A", n.get("sga"), "money_m", ["sg&a", "operating expense"])
    add("Cash", n.get("cash"), "money_m", ["cash"])
    add("ACH revenue", n.get("ach"), "money_m", ["ach"])
    add("Card/PayFac revenue", n.get("card"), "money_m", ["card", "payfac"])
    add("Prepaid revenue", n.get("prepaid"), "money_m", ["prepaid"])
    add("Output Solutions revenue", n.get("output"), "money_m", ["output"])
    add("Transactions", n.get("txn"), "money_m", ["transaction"])
    add("Gross margin", n.get("gm"), "pct", ["margin"], True)
    add("Volume growth (YoY)", n.get("vol_yoy"), "pct", ["volume", "grew", "growth", "year-over-year", "yoy"])
    add("Volume processed", n.get("vol"), "money_b", ["volume", "processed"], True)
    add("GAAP EPS", n.get("eps"), "dollars", ["eps", "per share", "earnings per share"], True)
    add("FY guidance — low end", gd.get("new_low"), "money_m",
        ["guidance", "full-year", "full year", "raising", "reaffirm"], True)
    add("FY guidance — high end", gd.get("new_hi"), "money_m",
        ["guidance", "full-year", "full year", "raising", "reaffirm"], True)
    # Street consensus is a legitimate comparison figure the script may cite ("$102M Street") —
    # recognize it as a source so it ties out instead of looking like a misstated revenue.
    add("Street consensus", market_data.consensus_rev_value(), "money_m", ["consensus", "street", "estimate"])

    def _cround(x, nd):  # commercial (round-half-up) rounding, unlike Python's banker's round()
        f = 10 ** nd
        return math.floor(abs(x) * f + 0.5) / f * (1 if x >= 0 else -1)

    def eq(a, b):
        # Exact to a tenth, OR a legitimate rounding of the submitted value (so "$103M"
        # for a submitted 102.5 ties out, but a typo'd "$102.3M" does not).
        if abs(a - b) <= 0.05:
            return True
        return any(abs(a - _cround(b, nd)) <= 0.001 for nd in (0, 1))

    def near(a, b):
        return abs(b) > 0 and not eq(a, b) and abs(a - b) <= 0.12 * abs(b)

    num_re = re.compile(
        r'(\$)?\s?(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+(?:\.\d+)?)\s?(billion|million|percent|bps|%|\bB\b|\bM\b|\bK\b)?',
        re.I)
    # Comparison cues that mark a figure as a reference (a guide, the Street, a prior period),
    # NOT the metric itself — if one sits just before the figure, it's never a "mismatch".
    _COMPARE_CUES = ("guide", "street", "consensus", "estimate", "expectation", "versus", " vs ",
                     "ahead of", "compared", "prior", "year-ago", "year ago", "a year", "up from",
                     "down from", "from $", " than ", "above", "below", "beat", "target", "outlook", "forecast")
    matched_labels, mismatch_labels, seen = set(), set(), set()
    for m in num_re.finditer(script):
        dollar, raw, suf = m.group(1), m.group(2), (m.group(3) or "").lower()
        try:
            val = float(raw.replace(",", ""))
        except ValueError:
            continue
        if suf in ("%", "percent"):
            cls = "pct"
        elif suf in ("billion", "b"):
            cls = "money_b"
        elif suf in ("million", "m"):
            cls = "money_m"
        elif dollar and val < 20 and "." in raw:
            cls = "dollars"
        else:
            continue  # plain integers ("20 years", "3 questions") — too noisy to audit
        snippet = script[max(0, m.start() - 45):min(len(script), m.end() + 30)].replace("\n", " ").strip()
        pre = script[max(0, m.start() - 30):m.start()].lower()  # tight window immediately before the figure
        same = [s for s in sources if s[2] == cls]
        if any(eq(val, s[1]) for s in same):
            for s in same:
                if eq(val, s[1]):
                    matched_labels.add(s[0])
            continue
        # Keyword-anchored near-miss on a HEADLINE metric: the metric word must sit in the tight
        # window right BEFORE the figure, with no comparison cue there — so "$100M guide",
        # "$102M Street" and "up from $88M" read as comparisons, not misstatements of the metric.
        flagged = False
        if not any(c in pre for c in _COMPARE_CUES):
            for label, sval, _cls, kws, headline in same:
                if headline and near(val, sval) and any(k in pre for k in kws):
                    out["mismatches"].append({"label": label, "source": sval, "script": val, "snippet": snippet})
                    mismatch_labels.add(label)
                    flagged = True
                    break
        if flagged:
            continue
        dedup = (round(val, 3), snippet[:24])
        if dedup not in seen:
            seen.add(dedup)
            out["unverified"].append({"value": val, "cls": cls, "snippet": snippet})
    out["matched"] = sorted(matched_labels)
    # A headline metric is "omitted" only if it's neither tied out NOR flagged as a
    # mismatch — a mismatched metric IS mentioned (just wrong), not missing.
    out["omitted"] = [s[0] for s in sources if s[4] and s[0] not in matched_labels and s[0] not in mismatch_labels]
    out["unverified"] = out["unverified"][:15]
    return out


def _render_number_tieout(ss):
    """Render the deterministic number tie-out audit (see _number_tieout)."""
    t = _number_tieout(ss)
    if not t["present"]:
        return
    ui.separator().style("margin:10px 0 4px;")
    ui.label("Number tie-out — does the script match the submitted numbers?").classes("font-bold").style(
        f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
    ui.label("Deterministic check (no AI, always on): every figure spoken in the assembled script tied back to "
             "the CFO's Stage-1 actuals and the recorded guidance range. A mismatch is a stated figure CLOSE to "
             "a headline number but not equal to it — the classic stale-number slip.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    if t["mismatches"]:
        for m in t["mismatches"]:
            with ui.card().classes("w-full").style(
                    "background:rgba(185,28,28,.08);border:1px solid #B91C1C;border-left:4px solid #B91C1C;"
                    "margin:4px 0;"):
                ui.label(f"⚠ Possible mismatch — {m['label']}").classes("font-bold").style(
                    "color:#B91C1C;font-size:var(--fs-sm);")
                ui.label(f"Script states {_fmt_val(m['script'], m['label'])}, but the submitted {m['label']} is "
                         f"{_fmt_val(m['source'], m['label'])}.").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                ui.label(f"…{m['snippet']}…").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;")
    else:
        ui.label("✓ No conflicting headline figures — every headline number stated ties to the submitted "
                 "actuals.").style("color:#15803D;font-size:var(--fs-sm);font-weight:600;")
    if t["matched"]:
        ui.label("Ties out: " + ", ".join(t["matched"])).style("color:#15803D;font-size:var(--fs-xs);")
    if t["omitted"]:
        ui.label("Submitted but not stated in the script (informational): " + ", ".join(t["omitted"])).style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    if t["unverified"]:
        with ui.expansion(f"{len(t['unverified'])} other figure(s) not tied to a submitted number — review",
                          icon="fact_check").classes("w-full").style("margin-top:4px;"):
            ui.label("Figures in the script (YoY %, prior-year, derived) that don't match a Stage-1 actual — "
                     "usually fine, just confirm each is right.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            for u in t["unverified"]:
                unit = "%" if u["cls"] == "pct" else ""
                ui.label(f"• {u['value']:g}{unit}  —  …{u['snippet']}…").style(
                    f"color:{COLORS['text_body']};font-size:var(--fs-xs);")


# Historical minutes per prepared-remarks section, from the Q1 2026 actuals
# (_Q1_SECTION_TIMING) — the budget the live estimate is measured against.
_SECTION_BUDGET_MIN = {"CEO": 8.0, "CFO": 10.0, "CRO": 10.0}
_QA_ALLOTMENT_MIN = 40.0      # historical Q&A length (Q1 2026 ran 40 min)
_HIST_CALL_MIN = 72.0         # historical total call length (Q1 2026)


def _call_time_budget(ss):
    """Roll the per-section word counts into a projected call length, at the client's
    OWN Q1-derived speaking rate (_HISTORICAL_WPM), each prepared section measured
    against its historical minutes and the whole thing added to the historical Q&A
    allotment. Deterministic. Returns {rows, prepared, qa, total, hist_total, wpm}."""
    wpm = _HISTORICAL_WPM or 130

    def est(txt):
        w = len((txt or "").split())
        return w, (w / wpm if wpm else 0.0)

    rows = []
    op, welcome, fls = _call_opening_text(ss)
    ow, om = est(" ".join(x for x in (op, welcome, fls) if x))
    rows.append({"label": "Call opening (operator intro + safe harbor + host welcome)", "words": ow, "est": om, "budget": None})
    for role, key, label in _active_personas():
        w, mn = est(ss["script_text"].get(key, ""))
        rows.append({"label": label, "words": w, "est": mn, "budget": _SECTION_BUDGET_MIN.get(role)})
    gtext = (ss.get("guidance_decision") or {}).get("text", "")
    if gtext.strip():
        w, mn = est(gtext)
        rows.append({"label": "Guidance & Outlook", "words": w, "est": mn, "budget": 4.0})
    prepared = sum(r["est"] for r in rows)
    return {"rows": rows, "prepared": prepared, "qa": _QA_ALLOTMENT_MIN,
            "total": prepared + _QA_ALLOTMENT_MIN, "hist_total": _HIST_CALL_MIN, "wpm": wpm}


def _render_time_budget(ss):
    """Render the whole-call time budget (see _call_time_budget)."""
    b = _call_time_budget(ss)
    if not any(r["words"] for r in b["rows"]):
        return
    ui.separator().style("margin:10px 0 4px;")
    ui.label("Call time budget — how long will this run?").classes("font-bold").style(
        f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
    ui.label(f"Estimated speaking time at the client's own Q1-derived pace (~{b['wpm']} words/min), each prepared "
             f"section against its historical minutes, rolled up with the historical ~{b['qa']:.0f}-min Q&A. "
             "Deterministic — no AI.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

    over = b["total"] - b["hist_total"]
    band = b["hist_total"] * 0.06
    hl_clr = "#B91C1C" if over > band else ("#1E40AF" if over < -band else "#15803D")
    verdict = ("runs long" if over > band else ("runs short" if over < -band else "on pace"))
    with ui.card().classes("w-full").style(
            f"background:rgba(0,0,0,.12);border:1px solid {hl_clr};border-left:4px solid {hl_clr};margin:4px 0;"):
        ui.label(f"Projected call ≈ {b['total']:.0f} min").classes("font-bold").style(
            f"color:{hl_clr};font-size:var(--fs-md);")
        ui.label(f"Prepared remarks ≈ {b['prepared']:.1f} min  +  ~{b['qa']:.0f} min Q&A (historical). "
                 f"vs ~{b['hist_total']:.0f} min historical (Q1 2026) — {verdict} by {abs(over):.0f} min.").style(
            f"color:{COLORS['text_body']};font-size:var(--fs-sm);")

    for r in b["rows"]:
        if r["budget"]:
            d = r["est"] - r["budget"]
            fclr = "#B91C1C" if d > r["budget"] * 0.15 else ("#1E40AF" if d < -r["budget"] * 0.15 else "#15803D")
            note = f"budget {r['budget']:.0f} min · {'+' if d >= 0 else ''}{d:.1f} min"
        else:
            fclr, note = COLORS["text_muted"], "no historical budget"
        with ui.row().classes("w-full items-center").style("gap:8px;padding:1px 0;"):
            ui.label(r["label"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);flex:1;")
            ui.label(f"≈ {r['est']:.1f} min ({r['words']}w)").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);min-width:130px;text-align:right;")
            ui.label(note).style(f"color:{fclr};font-size:var(--fs-sm);min-width:150px;text-align:right;font-weight:600;")


def _script_blocks(ss):
    """Structured (speaker, label, text) blocks in speaking order — the same content
    _assembled_script_text flattens, kept per-speaker for the teleprompter export."""
    contacts = _contacts()
    op, welcome, fls = _call_opening_text(ss)
    blocks = []
    # Operator delivers the intro AND the safe harbor (with the handoff); the host then welcomes.
    op_full = "\n\n".join(x for x in (op, fls) if x and x.strip())
    if op_full:
        blocks.append(("Operator", "Call opening & safe harbor", op_full))
    ir_name = contacts.get("IR", {}).get("name", "Investor Relations")
    if welcome and welcome.strip():
        blocks.append((ir_name, "Welcome & participants", welcome))
    for role, key, label in _active_personas():
        txt = ss["script_text"].get(key, "")
        if txt and txt.strip():
            blocks.append((contacts.get(role, {}).get("name", role), label, txt))
    gtext = (ss.get("guidance_decision") or {}).get("text", "")
    if gtext.strip():
        blocks.append((contacts.get("CEO", {}).get("name", "CEO"), "Guidance & outlook", gtext))
    return blocks


_TELEPROMPTER_CSS = """<style>
:root{--fs:30px;--accent:#4aa3ff}
*{box-sizing:border-box}
body{margin:0;background:#0b0f14;color:#eef2f7;font-family:Georgia,'Times New Roman',serif;line-height:1.75}
.bar{position:fixed;inset:0 0 auto 0;display:flex;gap:8px;align-items:center;padding:8px 14px;
 background:linear-gradient(#0b0f14,rgba(11,15,20,.9) 70%,transparent);z-index:10}
.bar .title{margin-right:auto;font:600 13px system-ui;color:#8aa0b6;letter-spacing:.03em}
.bar button{font:600 14px system-ui;background:#1b2430;color:#eef2f7;border:1px solid #2c3a4a;border-radius:6px;
 padding:6px 11px;cursor:pointer}
.bar button:hover{background:#243244}
main{max-width:900px;margin:0 auto;padding:60px 28px 80vh;font-size:var(--fs)}
section{margin:0}
h2{position:sticky;top:42px;background:#0b0f14;margin:26px 0 12px;padding:8px 0;border-bottom:2px solid var(--accent);
 display:flex;justify-content:space-between;align-items:baseline;gap:12px;font-family:system-ui}
h2 .role{font-size:var(--fs-md);font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--accent)}
h2 .who{font-size:var(--fs-md);color:#8aa0b6;white-space:nowrap}
p{margin:0 0 .7em}
.handoff{text-align:center;color:#5f7488;font:600 15px system-ui;letter-spacing:.1em;margin:22px 0}
@media print{.bar{display:none}body{background:#fff;color:#000}h2{background:#fff}main{padding-top:12px}}
</style>"""

_TELEPROMPTER_JS = """<script>
var fs=30,auto=false,tid=null;
function setFs(d){fs=Math.max(16,Math.min(80,fs+d));document.documentElement.style.setProperty('--fs',fs+'px');}
function toggle(){auto=!auto;var b=document.getElementById('auto');b.textContent=auto?'\\u23F8 Stop':'\\u25B6 Auto-scroll';
 if(auto){tid=setInterval(function(){window.scrollBy(0,1);},40);}else{clearInterval(tid);}}
</script>"""


def _teleprompter_html(ss):
    """A self-contained, dark, large-type teleprompter page of the assembled script —
    per speaker, with handoff cues, font-size controls and an auto-scroll toggle.
    Downloaded (not an Artifact), so inline CSS/JS is fine."""
    import html as _html
    ticker, quarter = CT("ticker", ""), CE().get("current_quarter", "")
    title = f"{ticker} {quarter} — Teleprompter".strip()
    blocks = _script_blocks(ss)
    secs = []
    for i, (speaker, label, text) in enumerate(blocks):
        paras = "".join(f"<p>{_html.escape(p.strip())}</p>" for p in text.split("\n") if p.strip())
        handoff = "" if i == len(blocks) - 1 else '<div class="handoff">▼  pause — hand off  ▼</div>'
        secs.append(f'<section><h2><span class="role">{_html.escape(label)}</span>'
                    f'<span class="who">{_html.escape(speaker)}</span></h2>{paras}</section>{handoff}')
    bar = (f'<div class="bar"><span class="title">{_html.escape(title)}</span>'
           '<button onclick="setFs(-2)">A−</button><button onclick="setFs(2)">A+</button>'
           '<button id="auto" onclick="toggle()">▶ Auto-scroll</button></div>')
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_html.escape(title)}</title>' + _TELEPROMPTER_CSS + '</head><body>'
            + bar + '<main id="doc">' + "\n".join(secs) + '</main>' + _TELEPROMPTER_JS + '</body></html>')


def _promote_answer_to_kb(item):
    """Connector: promote a prepared Q&A answer into the approved-answer KB
    (core.ir_knowledge), where the shareholder-reply drafter may state it directly.
    Opens a confirm dialog (topic + answer, both editable) with an explicit Reg FD
    reminder — the KB is public-facing, so only publicly disclosed info belongs here.
    Reads the item's CURRENT (possibly hand-edited) question/answer."""
    from core import ir_knowledge, shareholder_reply
    from config.client_config import get_active_client_id
    cid = get_active_client_id()
    default_topic = (item.get("question") or "").strip()
    default_answer = (item.get("angle") or "").strip()

    with ui.dialog() as dlg, ui.card().style("min-width:440px;max-width:560px;"):
        ui.label("Promote to approved answers").classes("font-bold").style(
            f"color:{COLORS['text_heading']};font-size:var(--fs-md);")
        ui.label("This becomes an APPROVED answer the shareholder-reply drafter may state directly to "
                 "shareholders. Promote it ONLY if the answer contains publicly disclosed information — never "
                 "anything unreleased or forward-looking that hasn't been said publicly.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);max-width:520px;")
        _topic = ui.input("Topic (short label)", value=default_topic[:90]).props("outlined dense").classes(
            "w-full").style("font-size:var(--fs-sm);")
        _ans = ui.textarea("Approved answer (public info only)", value=default_answer).props(
            "outlined autogrow dense").classes("w-full").style("font-size:var(--fs-sm);")

        # Active MNPI check — scan the answer for forward-looking / possibly-non-public
        # language and warn (live, as the text is edited) before it lands in the public KB.
        _warn = ui.column().classes("w-full").style("margin-top:2px;")

        with ui.row().classes("justify-end w-full gap-2").style("margin-top:6px;"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")

            def _confirm(_topic=_topic, _ans=_ans, cid=cid):
                if not (_topic.value or "").strip() or not (_ans.value or "").strip():
                    ui.notify("Topic and answer are both required.", type="warning")
                    return
                ir_knowledge.add_entry(_topic.value, _ans.value, cid)
                flagged = shareholder_reply.scan_mnpi(_ans.value).get("flagged")
                ui.notify(("Added to the approved-answer KB (you promoted despite the forward-looking flag) — "
                           "available to the shareholder-reply drafter." if flagged else
                           "Added to the approved-answer KB — available to the shareholder-reply drafter "
                           "(IR Inbox)."), type="warning" if flagged else "positive")
                dlg.close()
            _confirm_btn = ui.button("Add to approved answers", icon="menu_book", on_click=_confirm).props("dense")

        def _scan():
            res = shareholder_reply.scan_mnpi(_ans.value or "")
            _warn.clear()
            if res["flagged"]:
                with _warn:
                    with ui.card().classes("w-full").style(
                            "background:rgba(185,28,28,.08);border:1px solid #B91C1C;border-left:4px solid #B91C1C;"
                            "padding:6px 10px;"):
                        ui.label("⚠ Possible material non-public / forward-looking language").classes(
                            "font-bold").style("color:#B91C1C;font-size:var(--fs-sm);")
                        ui.label("The KB is public-facing. Confirm every statement here is ALREADY publicly "
                                 "disclosed before promoting — flagged: " + ", ".join(res["reasons"])).style(
                            f"color:{COLORS['text_body']};font-size:var(--fs-xs);")
                        for p in res["phrases"][:6]:
                            ui.label(f"• “{p}”").style(
                                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;")
            _confirm_btn.text = "Promote anyway" if res["flagged"] else "Add to approved answers"
            _confirm_btn.props(f'color={"warning" if res["flagged"] else "primary"}')

        _ans.on_value_change(lambda e: _scan())
        _scan()  # initial scan of the prefilled answer
    dlg.open()


def _qa_key(q):
    """Normalized dedup key for a Q&A question."""
    import re
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", (q or "").lower())).strip()[:90]


# Source metadata for a unified Q&A prep item: (border color, editor tag, sheet heading).
_QA_SOURCES = {
    "recurring": ("#0F766E", "Recurring — from research / last quarter", "From analyst research & last quarter"),
    "ai": ("#B45309", "AI-drafted — edit freely", "Surfaced from the script (AI)"),
    "manual": ("#1E40AF", "Added by IR", "Added by IR"),
}


def _qa_item_source(it):
    return it.get("source") or ("manual" if it.get("manual") else "ai")


# Keyword hints for who fields a given Q&A: CFO takes the financial/numbers questions,
# CEO takes strategy/competition/positioning. Ambiguous ones default to the CEO.
_QA_CFO_KWS = ("revenue", "margin", "ebitda", "eps", "cash", "sg&a", "guidance", "take rate", "interest income",
               "float", "capital allocation", "buyback", "expense", "tax", "balance sheet", "free cash flow",
               "consensus", "deceleration", "run-rate", "run rate", "cadence", "seasonality", "opex")
_QA_CEO_KWS = ("strateg", "competit", "market", "product", "partnership", "m&a", "acquisition", "vision",
               "long-term", "long term", "expansion", "positioning", "moat", "roadmap", "pipeline", "vertical")


def _responder_options():
    """The pool of call responders — the CONFIRMED speaker lineup for the reporting
    period (role — name), falling back to the client's role roster before confirmation."""
    from core import speakers
    period = speakers.current_period()
    rec = speakers.get_confirmed(period) if period else None
    opts, seen = [], set()

    def _add(role, nm):
        nm = (nm or "").strip()
        if not nm:
            return
        label = f"{(role or '').strip()} — {nm}" if (role or "").strip() else nm
        if label not in seen:
            seen.add(label)
            opts.append(label)

    if rec and rec.get("speakers"):
        for s in rec["speakers"]:
            _add(s.get("role"), s.get("name"))
    else:
        from config.client_config import role_roster
        for e in (role_roster() or []):
            _add(e.get("role_key"), e.get("name"))
    return opts


def _role_of_option(opt):
    return opt.split("—")[0].strip().upper() if "—" in (opt or "") else ""


def _suggest_responder(question, opts):
    """Best-guess responder for a question from the keyword hints; '' if no roster."""
    if not opts:
        return "Unassigned"
    q = (question or "").lower()

    def _match(role):
        return next((o for o in opts if _role_of_option(o) == role), None)

    if any(k in q for k in _QA_CFO_KWS):
        m = _match("CFO")
        if m:
            return m
    if any(k in q for k in _QA_CEO_KWS):
        m = _match("CEO")
        if m:
            return m
    return _match("CEO") or opts[0]  # default general/strategic asks to the CEO


def _ensure_responder(it, opts):
    """Fill a suggested responder if none is set (persisted so it flows to the export)."""
    if not it.get("responder"):
        it["responder"] = _suggest_responder(it.get("question", ""), opts)


def _sync_recurring_into_prep(ss):
    """Fold the deterministic recurring Q&A (research-note catalysts + last quarter's
    un-pre-empted topics, from _build_qa_prep) into the single editable prep list as
    source='recurring' — unless already present or previously dismissed. This unifies
    the two Q&A sources into ONE editable/promotable/exportable list. Idempotent."""
    data = ss.setdefault("adversarial_qa", {})
    items = data.setdefault("items", [])
    dismissed = set(data.get("dismissed_recurring", []))
    have = {_qa_key(it.get("question")) for it in items}
    opts = _responder_options()
    added = 0
    for d in _build_qa_prep(ss):
        k = _qa_key(d.get("topic"))
        if not k or k in have or k in dismissed:
            continue
        why = d.get("source", "")
        if d.get("detail"):
            why = f"{why} — {d['detail']}" if why else d["detail"]
        new = {"question": d.get("topic", ""), "why": why,
               "angle": d.get("suggested_angle", ""), "source": "recurring",
               "severity": d.get("severity")}
        _ensure_responder(new, opts)
        items.append(new)
        have.add(k)
        added += 1
    # Backfill a suggested responder on any item still missing one (e.g. AI items
    # generated before responder assignment existed), so the whole list is assigned.
    resp_backfill = 0
    for it in items:
        if not it.get("responder"):
            it["responder"] = _suggest_responder(it.get("question", ""), opts)
            resp_backfill += 1
    if added or resp_backfill:
        data.setdefault("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
        _save_json("script_workflow_state.json", ss)
    return added


_QA_SHEET_CSS = """<style>
:root{--ink:#1a2230;--muted:#5c6b80;--line:#dfe4ea;--teal:#0F766E;--amber:#B45309;--blue:#1E40AF;--bg:#fbfcfe}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:36px 30px 80px}
header{border-bottom:2px solid var(--ink);padding-bottom:10px;margin-bottom:8px}
header h1{margin:0;font-size:var(--fs-3xl)}
header .meta{color:var(--muted);font-size:var(--fs-base);margin-top:2px}
.note{color:var(--muted);font-size:var(--fs-sm);margin:8px 0 20px}
h2{font-size:var(--fs-base);text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:26px 0 8px;
   border-bottom:1px solid var(--line);padding-bottom:5px}
.qa{border-left:3px solid var(--line);padding:8px 0 10px 14px;margin:0 0 12px;break-inside:avoid}
.qa.recurring{border-left-color:var(--teal)} .qa.ai{border-left-color:var(--amber)} .qa.manual{border-left-color:var(--blue)}
.qa .q{font-weight:700;font-size:var(--fs-lg)}
.qa .resp{display:inline-block;font-size:var(--fs-xs);font-weight:600;color:var(--teal);
   border:1px solid var(--teal);border-radius:10px;padding:0 8px;margin:4px 0 2px}
.qa .why{color:var(--muted);font-size:var(--fs-sm);font-style:italic;margin:2px 0 6px}
.qa .a{font-size:var(--fs-md);white-space:pre-wrap}
.qa .todo{color:#B91C1C;font-style:italic}
footer{margin-top:34px;color:var(--muted);font-size:var(--fs-xs);border-top:1px solid var(--line);padding-top:8px}
@media print{body{background:#fff}.wrap{padding:0}}
</style>"""


def _qa_prep_sheet_html(ss):
    """Self-contained, print-friendly Q&A prep sheet — every prepared question and
    answer, grouped by source, for management to carry into the call. Downloaded."""
    import html as _html
    ticker, quarter = CT("ticker", ""), CE().get("current_quarter", "")
    title = f"{ticker} {quarter} — Q&A Prep Sheet".strip()
    items = (ss.get("adversarial_qa") or {}).get("items", [])
    secs = []
    for src, (_clr, _tag, heading) in _QA_SOURCES.items():
        group = [it for it in items if _qa_item_source(it) == src]
        if not group:
            continue
        rows = []
        for it in group:
            q = _html.escape((it.get("question") or "").strip())
            why = _html.escape((it.get("why") or "").strip())
            resp = (it.get("responder") or "").strip()
            resp_html = (f'<div class="resp">→ {_html.escape(resp)}</div>'
                         if resp and resp.lower() != "unassigned" else "")
            a_raw = (it.get("angle") or "").strip()
            a = _html.escape(a_raw) if a_raw else '<span class="todo">[ answer to prepare ]</span>'
            rows.append(f'<div class="qa {src}"><div class="q">{q}</div>' + resp_html
                        + (f'<div class="why">{why}</div>' if why else "")
                        + f'<div class="a">{a}</div></div>')
        secs.append(f'<section><h2>{_html.escape(heading)}</h2>{"".join(rows)}</section>')
    body = "".join(secs) or '<p class="note">No Q&A prepared yet.</p>'
    gen = (ss.get("adversarial_qa") or {}).get("generated_at") or ""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width, initial-scale=1">'
            f'<title>{_html.escape(title)}</title>' + _QA_SHEET_CSS + '</head><body><div class="wrap">'
            f'<header><h1>{_html.escape(title)}</h1><div class="meta">Prepared answers use publicly '
            f'disclosed information only.{(" · compiled " + _html.escape(gen)) if gen else ""}</div></header>'
            '<div class="note">Reference for management during Q&A. Each answer is Regulation FD-safe — do not '
            'volunteer unreleased or forward-looking specifics.</div>'
            + body +
            '<footer>Generated by IRconnect · internal prep — not for distribution.</footer>'
            '</div></body></html>')


def _render_qa_prep_tab(ss):
    ui.label("Q&A Prep").classes("font-bold").style("font-size:var(--fs-md);")
    ui.label("One editable prep list from three sources: recurring questions (ingested research notes + last "
             "quarter's open topics), the AI adversarial pass over your script, and your own additions. Edit any "
             "answer, add your own, promote a good answer to the approved-answer KB, or export the sheet for the "
             "call.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    # Callback direction anchors — how to answer "which way is each number trending?" consistently with the
    # guide. Moved here from the guidance bridge: it's call prep, and this is where prep lives.
    _render_callback_qa_prep(ss)
    # Unify the sources: fold the deterministic recurring questions into the single editable list.
    _sync_recurring_into_prep(ss)

    from core import ui_context
    _adv_ro = ui_context.is_read_only()  # capture once — a rebuild fires from callbacks (unbound context)
    adv_box = ui.column().classes("w-full gap-1").style("margin-top:4px;")

    _resp_opts = _responder_options()

    def _render_adv():
        adv_box.clear()
        # Live reference into ss so in-place edits (question / prepared answer) persist.
        data = ss.get("adversarial_qa") or {} if _adv_ro else ss.setdefault("adversarial_qa", {})
        adv_items = data.get("items") or []
        with adv_box:
            if data.get("generated_at"):
                ui.label(f"Generated {data['generated_at']} — the AI-drafted answers are editable; your own "
                         "Q&A and edits are kept when you re-run.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            for it in adv_items:
                _src = _qa_item_source(it)
                clr, tag_txt, _heading = _QA_SOURCES.get(_src, _QA_SOURCES["ai"])
                with ui.card().classes("w-full").style(
                        f"background:rgba(0,0,0,.04);border:1px solid {clr}55;border-left:4px solid {clr};"
                        "margin-bottom:6px;"):
                    if _adv_ro:
                        ui.label("Q · " + it.get("question", "")).classes("font-bold").style(
                            f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
                        _resp = (it.get("responder") or "").strip()
                        if _resp and _resp.lower() != "unassigned":
                            ui.label("Responder: " + _resp).style(f"color:{clr};font-size:var(--fs-xs);font-weight:600;")
                        if it.get("why"):
                            ui.label("What invites it: " + it["why"]).style(
                                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                        if it.get("angle"):
                            ui.label("Prepared answer: " + it["angle"]).style(
                                f"color:{COLORS['accent_light']};font-size:var(--fs-sm);font-style:italic;")
                        continue
                    _q = ui.input("Question", value=it.get("question", "")).props("dense outlined").classes(
                        "w-full").style("font-size:var(--fs-sm);")
                    _q.on_value_change(lambda e, it=it: (it.__setitem__("question", e.value),
                                                         _save_json("script_workflow_state.json", ss)))
                    if it.get("why"):
                        ui.label("What invites it: " + it["why"]).style(
                            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    _a = ui.textarea("Prepared answer (Reg FD-safe — public info only)",
                                     value=it.get("angle", "")).props("dense autogrow outlined").classes(
                        "w-full").style("font-size:var(--fs-sm);")
                    _a.on_value_change(lambda e, it=it: (it.__setitem__("angle", e.value),
                                                         _save_json("script_workflow_state.json", ss)))
                    with ui.row().classes("w-full items-center").style("gap:6px;"):
                        ui.label(tag_txt).style(f"color:{clr};font-size:var(--fs-2xs);font-weight:600;")
                        _rchoices = ["Unassigned"] + _resp_opts
                        _rcur = (it.get("responder") or "Unassigned").strip() or "Unassigned"
                        if _rcur not in _rchoices:
                            _rchoices = _rchoices + [_rcur]  # keep a stale/departed responder selectable
                        _rsel = ui.select(_rchoices, value=_rcur, label="Responder").props(
                            "dense outlined").classes("min-w-[210px]").style("font-size:var(--fs-sm);")
                        _rsel.on_value_change(lambda e, it=it: (it.__setitem__("responder", e.value),
                                                                _save_json("script_workflow_state.json", ss)))
                        ui.space()
                        if it.get("banked"):
                            ui.label("Banked ✓").style("color:#15803D;font-size:var(--fs-xs);font-weight:600;")
                        else:
                            def _bank(it=it):
                                if not (it.get("question") or "").strip():
                                    ui.notify("Nothing to bank.", type="warning")
                                    return
                                from core import qa_bank
                                from config.client_config import get_active_client_id
                                res = qa_bank.bank(get_active_client_id(), it["question"], _qa_item_source(it))
                                it["banked"] = True
                                _save_json("script_workflow_state.json", ss)
                                where = ("house bank + this client" if res["new_global"]
                                         else ("this client's bank" if res["new_client"] else "already banked"))
                                ui.notify(f"Banked ({where}) — it'll seed future adversarial passes.",
                                          type="positive")
                                _render_adv()
                            ui.button("Bank", icon="savings", on_click=_bank).props("flat dense").style(
                                f"color:{COLORS['accent']};font-size:var(--fs-xs);")
                        ui.button("Promote to KB", icon="menu_book",
                                  on_click=lambda it=it: _promote_answer_to_kb(it)).props("flat dense").style(
                            f"color:{COLORS['accent']};font-size:var(--fs-xs);")

                        def _rm(it=it, adv_items=adv_items, data=data):
                            adv_items.remove(it)
                            if _qa_item_source(it) == "recurring":
                                k = _qa_key(it.get("question"))
                                dl = data.setdefault("dismissed_recurring", [])
                                if k and k not in dl:
                                    dl.append(k)  # so a removed recurring question doesn't re-fold
                            _save_json("script_workflow_state.json", ss)
                            _render_adv()
                        ui.button("Remove", icon="delete", on_click=_rm).props("flat dense").style(
                            f"color:{COLORS['danger']};font-size:var(--fs-xs);")
            if not adv_items and data.get("generated_at"):
                ui.label("No exposed questions surfaced — the script pre-empts the obvious ones.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

            # Add-your-own Q&A — a question you know will come up plus your prepared answer.
            if not _adv_ro:
                with ui.card().classes("w-full").style(
                        f"background:{COLORS['surface_hover_bg']};border:1px dashed {COLORS['accent']};"
                        "padding:8px 10px;margin-top:4px;"):
                    ui.label("Add your own Q&A").classes("font-bold").style(
                        f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                    _nq = ui.input("Question").props("dense outlined").classes("w-full").style("font-size:var(--fs-sm);")
                    _na = ui.textarea("Prepared answer (public info only)").props("dense autogrow outlined").classes(
                        "w-full").style("font-size:var(--fs-sm);")

                    def _add_qa(_nq=_nq, _na=_na):
                        if not (_nq.value or "").strip():
                            ui.notify("Enter a question.", type="warning")
                            return
                        _mi = {"question": _nq.value.strip(), "why": "", "angle": (_na.value or "").strip(),
                               "manual": True, "source": "manual"}
                        _ensure_responder(_mi, _resp_opts)
                        # A question the IR person adds by hand is inherently worth remembering —
                        # auto-bank it so it seeds future adversarial passes.
                        try:
                            from core import qa_bank
                            from config.client_config import get_active_client_id
                            qa_bank.bank(get_active_client_id(), _mi["question"], "manual")
                            _mi["banked"] = True
                        except Exception as exc:
                            print(f"[qa add] auto-bank skipped: {exc}")
                        data.setdefault("items", []).append(_mi)
                        data.setdefault("generated_at", datetime.now().strftime("%Y-%m-%d %H:%M"))
                        _save_json("script_workflow_state.json", ss)
                        _render_adv()
                        ui.notify("Added to prep and banked for future passes.", type="positive")
                    ui.button("Add Q&A", icon="add", on_click=_add_qa).props("color=primary dense").style(
                        "margin-top:4px;")

    _render_adv()

    def _run_adv():
        ui.notify("Reading the script as a skeptical analyst…", type="info")
        try:
            adv_items = _adversarial_qa(ss)
        except Exception as exc:
            ui.notify(f"Adversarial pass failed: {exc}", type="negative")
            raise
        if not adv_items:
            ui.notify("Needs the AI (ANTHROPIC_API_KEY) and a drafted script — nothing generated.", type="warning")
            return
        _opts = _responder_options()
        for it in adv_items:
            it["source"] = "ai"
            _ensure_responder(it, _opts)
        # Regenerate only the AI items — keep recurring and the IR person's own Q&A (and
        # the dismissed_recurring set, by updating the dict in place rather than replacing).
        data = ss.setdefault("adversarial_qa", {})
        keep = [it for it in data.get("items", []) if _qa_item_source(it) != "ai"]
        data["items"] = adv_items + keep
        data["generated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        _save_json("script_workflow_state.json", ss)
        _render_adv()
        ui.notify(f"Surfaced {len(adv_items)} exposed question(s) — review and edit the answers, or add your own.",
                  type="positive")

    _have = bool(any(_qa_item_source(it) == "ai" for it in (ss.get("adversarial_qa") or {}).get("items", [])))
    with ui.row().classes("items-center gap-2").style("margin-top:4px;"):
        ui.button("Re-run adversarial pass" if _have else "Generate tough questions from the script",
                  icon="gavel", on_click=_run_adv).props("color=primary dense")

        def _export_qa_sheet():
            html = _qa_prep_sheet_html(ss)
            fname = f"{CT('ticker')}_{CE().get('current_quarter','')}_QA_Prep_Sheet.html".replace(" ", "_")
            ui.download(html.encode("utf-8"), fname)
        ui.button("Q&A prep sheet (HTML)", icon="print", on_click=_export_qa_sheet).props("flat")

    _render_qa_bank_editor()


def _render_qa_bank_editor():
    """The house Q&A bank — questions analysts have actually asked (accrued from prior
    calls' surprises + the code-seeded defaults), which seed every adversarial pass.
    Merged view (global house book ∪ this client); add/remove client entries."""
    from core import qa_bank, ui_context
    from config.client_config import get_active_client_id
    cid = get_active_client_id()
    _ro = ui_context.is_read_only()  # capture once — a rebuild fires from callbacks (unbound context)

    with ui.expansion("House Q&A bank — recurring questions that seed the adversarial pass",
                      icon="quiz").classes("w-full").style("margin-top:10px;"):
        _csec = qa_bank.client_sector(cid)
        ui.label(f"Questions analysts have actually asked — accrued automatically from Morning-After "
                 f"surprises (tagged by the source client's sector) plus a seeded set of recurring asks. "
                 f"Every adversarial pass is seeded with the questions relevant to this client's sector "
                 f"(here: {_csec}) plus universal ones — so a payments question never seeds an aerospace "
                 f"client.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        _box = ui.column().classes("w-full gap-1").style("margin-top:6px;")

        def _rebuild():
            _box.clear()
            with _box:
                entries = qa_bank.merged(cid)
                if not entries:
                    ui.label("Bank is empty.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                for e in entries:
                    kind = e.get("kind") or "manual"
                    sector = e.get("sector") or "universal"
                    src = f" · from {e.get('source_client')} {e.get('source_quarter') or ''}".rstrip() \
                        if e.get("source_client") else (" · house seed" if e.get("seed") else "")
                    with ui.card().classes("w-full").style(
                            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                            "padding:5px 10px;"):
                        with ui.row().classes("w-full items-center justify-between gap-2"):
                            ui.label(e.get("question", "")).style(
                                f"color:{COLORS['text_body']};font-size:var(--fs-sm);flex:1;")
                            tag_clr = "#B91C1C" if kind == "surprise" else (
                                "#15803D" if kind == "asked" else COLORS["text_muted"])
                            ui.label(f"{kind} · {sector}{src}").style(
                                f"color:{tag_clr};font-size:var(--fs-2xs);white-space:nowrap;")
                            if not _ro and not e.get("seed"):
                                def _del(k=e.get("key")):
                                    # Remove from whichever scope holds it (client first, else global).
                                    qa_bank.remove(k, scope="client", cid=cid)
                                    qa_bank.remove(k, scope="global")
                                    ui.notify("Removed from the bank.")
                                    _rebuild()
                                ui.button(icon="close", on_click=_del).props("flat dense round size=sm").style(
                                    f"color:{COLORS['danger']};")
                if not _ro:
                    with ui.row().classes("w-full items-end gap-2").style("margin-top:4px;"):
                        _nq = ui.input(label="Add a question to the house bank",
                                       placeholder="e.g. How exposed are you to interchange-fee regulation?").classes(
                            "flex-grow").props("dense outlined")
                        _sec_sel = ui.select({_csec: f"{_csec} only", "universal": "All sectors"},
                                             value=_csec, label="Applies to").props("dense outlined").classes(
                            "min-w-[150px]")

                        def _add(_nq=_nq, _sec_sel=_sec_sel):
                            if not (_nq.value or "").strip():
                                ui.notify("Type a question first.", type="warning")
                                return
                            qa_bank.add(_nq.value, kind="manual", scope="global", added_by="user",
                                        sector=_sec_sel.value or "universal")
                            ui.notify("Added to the house bank — it'll seed future adversarial passes.",
                                      type="positive")
                            _rebuild()
                        ui.button("Add", icon="add", on_click=_add).props("color=primary dense")
        _rebuild()


def _ensure_script_drafted(ss):
    """Fill in any persona section (and the guidance section) that's still
    blank, using the same auto-draft logic Stage 1's submit() runs on first
    numbers-submission. Called every time the Script Canvas renders — not
    just at Stage 1 submit — as a safety net for any session that reached
    Stage 2/3/4 before this auto-drafting existed (or before Stage 1 numbers
    were ever submitted at all in this session), where script_text/
    guidance_decision would otherwise stay empty forever with nothing to
    review. No-op once every section already has text; never overwrites
    anything a human has already drafted or edited."""
    if not ss.get("q2_numbers"):
        return  # nothing to draft from yet — Stage 1 hasn't been submitted
    changed = False
    for role, key, _label in _active_personas():
        if not ss["script_text"].get(key):
            p_notes = ss.setdefault("persona_notes", {}).setdefault(key, {"whats_new": "", "final_notes": ""})
            p_context = " | ".join(filter(None, [p_notes.get("whats_new"), p_notes.get("final_notes")]))
            p_draft, _was_ai = _generate_persona_draft(role, ss, p_context)
            ss["script_text"][key] = p_draft
            changed = True

    gd = ss.setdefault("guidance_decision", {})
    if not gd.get("text"):
        g_math = _guidance_math(ss)
        g_default_action = {"RAISE_MID": "raise_mid", "RAISE_LOW": "raise_low"}.get(g_math["scenario"], "reiterate")
        g_new_low, g_new_hi, g_rationale = _guidance_range_for_action(g_default_action, g_math)
        g_draft, _was_ai = _generate_guidance_draft(ss, g_default_action, g_new_low, g_new_hi, g_rationale)
        gd.update({"action": g_default_action, "new_low": g_new_low, "new_hi": g_new_hi,
                   "rationale": g_rationale, "text": g_draft})
        ss["guidance_decision"] = gd
        changed = True

    if changed:
        _save_json("script_workflow_state.json", ss)


def _assembled_script_text(ss):
    """Join the locked Call Opening (operator + IR's welcome/FLS reading —
    always included, never part of script_text) with every persona section
    and the guidance section, in speaker order (CEO's guidance text appended
    right after CEO's own section, since PERSONAS ends on CEO). This is
    always freshly recomputed from the individual persona sections, ignoring
    any full_script_override."""
    operator_line, welcome_line, fls_line = _call_opening_text(ss)
    # Operator reads the intro AND the safe harbor (with the handoff), THEN the host welcomes.
    full_parts = [operator_line, fls_line, welcome_line]
    full_parts += [ss["script_text"].get(key, "") for _, key, _ in _active_personas()]
    guidance_final_text = ss.get("guidance_decision", {}).get("text", "")
    if guidance_final_text:
        full_parts.append(guidance_final_text)
    return "\n\n".join(p for p in full_parts if p)


def _full_script_text(ss):
    """The full script as it should be shown/downloaded everywhere: the
    directly-edited full_script_override if one has been saved (from the
    "Full Script (assembled)" box itself), else freshly assembled from each
    persona's section. Shared by the Script Canvas's Full Script panel and
    Stage 1's script preview so both always show exactly the same text."""
    override = ss.get("full_script_override")
    if override:
        return override
    return _assembled_script_text(ss)


def _render_decision_bar(ss):
    """The keystone, pinned at the top of the Script Canvas — the guidance decision the whole script derives
    from, always in view instead of three screens up. One compact line: action · prior→new range · how many
    metrics back it · the strength read."""
    from core import guidance_engine as _ge
    gd = ss.get("guidance_decision", {}) or {}
    math_ = _guidance_math(ss)
    _prior = ((((ss.get("guidance_inputs") or {}).get("metrics") or {}).get("rev") or {}).get("prior_fy_range")
              or [math_["fy_low"], math_["fy_hi"]])
    if gd.get("new_low") is not None and gd.get("new_hi") is not None:
        _new = [float(gd["new_low"]), float(gd["new_hi"])]
    else:
        _dl, _dh, _ = _ge.apply_action(
            {"RAISE_MID": "raise_mid", "RAISE_LOW": "raise_low"}.get(math_["scenario"], "reiterate"), math_)
        _new = [round(_dl, 1), round(_dh, 1)]
    _ch = _ge.characterize_range_change(_prior, _new)
    n_raise = n_tot = 0
    try:
        br = _ge.guidance_bridge(ss.get("guidance_inputs") or {}, ss.get("surprise_log") or {})
        guided = [m for m in br["metrics"] if m.get("range")]
        n_tot = len(guided)
        n_raise = sum(1 for m in guided if str((m.get("recommendation") or {}).get("tag", "")).startswith("RAISED"))
    except Exception:
        pass
    tagclr = COLORS[_BR_TAG.get(_ch["tag"], "warning")] if _BR_TAG.get(_ch["tag"]) else COLORS["accent"]
    _m = lambda v: _fmt_metric(v, "money")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:5px solid {tagclr};"
            "border-radius:11px;padding:12px 16px;margin-bottom:10px;"):
        with ui.row().classes("w-full items-center gap-3 flex-wrap"):
            ui.label(_ch["tag"]).style(
                f"background:{tagclr}22;color:{tagclr};font-weight:800;font-size:var(--fs-xs);letter-spacing:.03em;padding:3px 10px;border-radius:999px;")
            ui.label(f"{_m(_prior[0])}–{_m(_prior[1])}").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-md);text-decoration:line-through;font-variant-numeric:tabular-nums;")
            ui.label("→").style(f"color:{tagclr};font-weight:800;")
            ui.label(f"{_m(_new[0])}–{_m(_new[1])}").style(
                f"color:{COLORS['text_heading']};font-weight:800;font-size:var(--fs-xl);font-variant-numeric:tabular-nums;")
            if n_tot:
                ui.label(f"{n_raise} of {n_tot} metrics support").style(
                    f"background:{COLORS['positive']}18;color:{COLORS['positive']};font-size:var(--fs-xs);font-weight:700;padding:3px 10px;border-radius:999px;")
            if _ch.get("strength"):
                ui.label(f"· {_ch['strength']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            ui.space()
            ui.label("Set on the CFO screen · drives every section").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")


def _render_section_editor(ss, sec, on_submit=None):
    """The drafting surface for one section — the existing per-section drafting tools, placed as the CENTER
    pane of the canvas. IR carries the fixed Call Opening ahead of its own remarks. on_submit refreshes the
    assembled Full Script panel when this section's draft is submitted."""
    kind, role = sec["kind"], sec.get("role")
    ui.label(sec["label"]).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:var(--fs-lg);")
    ui.label(sec.get("sub", "")).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    if kind == "guidance":
        _render_guidance_drafter(ss, on_submit=on_submit)
    elif kind == "qa":
        _render_qa_prep_tab(ss)
    elif kind == "persona":
        if role == "IR":
            _render_call_opening(ss)
        _render_persona_steps(ss, role, sec["key"], on_submit=on_submit)


def _rail_head(txt):
    ui.label(txt).style(f"color:{COLORS['text_muted']};font-size:var(--fs-micro);font-weight:700;"
                        "letter-spacing:.08em;text-transform:uppercase;")


def _rail_card(title, hi=False):
    bc = (f"color-mix(in srgb,{COLORS['accent']} 35%,{COLORS['border']})" if hi else COLORS["border"])
    c = ui.column().classes("w-full").style(
        f"background:{COLORS['surface_bg']};border:1px solid {bc};border-radius:9px;padding:10px 12px;gap:4px;")
    with c:
        ui.label(title).style(f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);font-weight:700;"
                              "letter-spacing:.05em;text-transform:uppercase;")
    return c


def _rail_row(label, value, vcolor=None):
    with ui.row().classes("items-baseline no-wrap flex-wrap").style("gap:6px;"):
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        ui.label(value).style(f"color:{vcolor or COLORS['text_heading']};font-size:var(--fs-xs);"
                              "font-weight:700;font-variant-numeric:tabular-nums;")


def _render_section_rail(ss, sec):
    """The analysis docked BESIDE the draft — only the read relevant to THIS section, so it travels with the
    work instead of sitting screens away. Pulls live numbers from the guidance bridge; every lookup is
    guarded so a missing value never breaks the pane."""
    from core import guidance_engine as _ge
    try:
        br = _ge.guidance_bridge(ss.get("guidance_inputs") or {}, ss.get("surprise_log") or {})
    except Exception:
        br = {"metrics": []}
    M = {m.get("key"): m for m in br.get("metrics", [])}
    role, kind = sec.get("role"), sec["kind"]
    _rail_head("◧ Context for this section")

    def _seq(rev, field):
        return " → ".join(f"{r[field]:+.0f}%" for r in (rev.get("full_path") or []) if r.get(field) is not None)

    if kind == "guidance" or role in ("CFO", "CEO"):
        rev = M.get("rev") or {}
        with _rail_card("The trend read — is it decelerating?", hi=True):
            rep = _seq(rev, "yoy_pct")
            org = " → ".join(f"{r['yoy_organic_pct']:+.0f}%" for r in (rev.get("full_path") or [])
                             if r.get("yoy_organic_pct") is not None)
            stk = [r["two_yr_cagr_pct"] for r in (rev.get("full_path") or []) if r.get("two_yr_cagr_pct") is not None]
            if rep:
                _rail_row("Reported YoY", rep, COLORS["text_muted"])
            if org:
                _rail_row("Organic (ex-comp)", org, COLORS["positive"])
            if len(stk) >= 2:
                _rail_row("2-yr stacked CAGR", f"flat ~{sum(stk) / len(stk):.0f}%", COLORS["positive"])
            ui.label("The step-down is the prior-year comp, not demand — so the H2 language says so.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.45;")
    if role == "CFO":
        kpis = [M[k] for k in ("tpv", "nrr", "take_rate") if k in M]
        if kpis:
            with _rail_card("Operating drivers"):
                for m in kpis:
                    yoy = (m.get("yoy") or {}).get("pct")
                    _rail_row(m.get("label", ""), _fmt_metric(m.get("actual"), m.get("fmt", "money"))
                              + (f" · {yoy:+.0f}% YoY" if yoy is not None else ""))
        with _rail_card("Tie-out"):
            ui.label("Every figure must reconcile to today's press release before it ships.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.45;")
    elif kind == "guidance":
        with _rail_card("Prior wording to match"):
            pg = _guidance_prior_language() or "—"
            ui.label(f"“{pg[:150]}{'…' if len(pg) > 150 else ''}”").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);font-style:italic;line-height:1.45;")
    elif role == "IR":
        with _rail_card("Fixed — read verbatim", hi=True):
            ui.label("The safe-harbor paragraph carries over each quarter. A material change goes back to "
                     "Legal before it ships — no ad-lib on Reg FD.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.45;")
        with _rail_card("Placement"):
            ui.label("Always first in the assembled full script and every download.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.45;")
    elif role == "CEO":
        with _rail_card("Narrative thread", hi=True):
            ui.label("Lead with the durable, recurring economics and the acceleration in the operating "
                     "drivers. Tone: confident but measured — a beat-and-raise, not a victory lap.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.45;")
    elif kind == "qa":
        rev = M.get("rev") or {}
        with _rail_card("What they'll probe — and the anchor", hi=True):
            org = " → ".join(f"{r['yoy_organic_pct']:+.0f}%" for r in (rev.get("full_path") or [])
                             if r.get("yoy_organic_pct") is not None)
            _rail_row("Don't lead with", _seq(rev, "yoy_pct") or "reported YoY", COLORS["text_muted"])
            if org:
                _rail_row("Anchor to", f"{org} organic", COLORS["positive"])
            ui.label("Analysts probe direction, not the printed number — every answer anchors to the trend "
                     "the guidance decision already established.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1.45;")


def _render_script_canvas(ss):
    _ensure_script_drafted(ss)
    # DRAFT-FIRST canvas: the decision is pinned on top, then a section workspace where each section's DRAFT
    # sits in the center with its ANALYSIS docked beside it, and the sections run in TRANSCRIPT order (IR →
    # CEO → CFO → Guidance → Q&A). Clicking a section swaps both the draft and its context together, so the
    # analysis travels with the work instead of stacking three screens above it.
    _render_decision_bar(ss)

    sections = []
    for role, key, label in _active_personas():           # IR, CEO, CFO, (CRO) — transcript order
        sections.append({"id": key, "kind": "persona", "role": role, "key": key, "label": label})
        if role == "CFO":                                  # the CFO delivers the outlook → guidance sits here
            sections.append({"id": "guidance", "kind": "guidance", "role": None, "key": "guidance",
                             "label": "Guidance & Outlook", "sub": "The spoken outlook — derives from the decision above"})
    sections.append({"id": "qa", "kind": "qa", "role": None, "key": "qa", "label": "Q&A Prep",
                     "sub": "Anticipated questions & answer frameworks"})

    nav_btns = {}
    with ui.row().classes("w-full").style(
            f"gap:0;align-items:stretch;flex-wrap:nowrap;border:1px solid {COLORS['border']};"
            f"border-radius:12px;overflow:hidden;background:{COLORS['surface_bg']};"):
        with ui.column().style(
                f"width:188px;flex:none;background:{COLORS['surface_hover_bg']};"
                f"border-right:1px solid {COLORS['border']};padding:10px 8px;gap:3px;"):
            ui.label("The script").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-micro);font-weight:700;letter-spacing:.08em;"
                "text-transform:uppercase;padding:4px 8px 2px;")
            for s in sections:
                nav_btns[s["id"]] = (
                    ui.button(s["label"], on_click=lambda _=None, sid=s["id"]: show(sid))
                    .props("flat no-caps dense align=left").classes("w-full")
                    .style("justify-content:flex-start;text-transform:none;border-radius:8px;"))
        editor = ui.column().classes("flex-1").style("min-width:0;padding:14px 18px;gap:7px;")
        # Sticky so the section's analysis stays in view as you scroll down through Steps 1–3 of a long
        # draft — the whole point is that the context is BESIDE the work, not scrolled away above it.
        rail = ui.column().style(
            f"width:400px;flex:none;background:{COLORS['surface_hover_bg']};"
            f"border-left:1px solid {COLORS['border']};padding:12px 14px;gap:9px;"
            "position:sticky;top:70px;align-self:flex-start;max-height:calc(100vh - 92px);overflow-y:auto;")

    # Holder for the assembled Full Script textarea (built below) so a section submit can refresh it live —
    # otherwise the panel keeps the stale text it was built with and the edit "doesn't show" until reload.
    _fullref = {}

    def _refresh_full():
        ta = _fullref.get("box")
        if ta is not None:
            ta.value = _full_script_text(ss)

    def show(sid):
        for s in sections:
            b = nav_btns[s["id"]]
            if s["id"] == sid:
                b.style(f"justify-content:flex-start;text-transform:none;border-radius:8px;"
                        f"background:{COLORS['accent']}18;color:{COLORS['accent']};font-weight:700;")
            else:
                b.style(f"justify-content:flex-start;text-transform:none;border-radius:8px;"
                        f"background:transparent;color:{COLORS['text_body']};font-weight:400;")
        editor.clear()
        rail.clear()
        sec = next(s for s in sections if s["id"] == sid)
        with editor:
            _render_section_editor(ss, sec, on_submit=_refresh_full)
        with rail:
            _render_section_rail(ss, sec)

    show(sections[0]["id"])

    # ── Global tools below the workspace: one-pass refine across every section, then the assembled script ──
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_hover_bg']};border:1px dashed {COLORS['accent']};"
            f"border-radius:8px;margin:12px 0 8px;"):
        ui.label("Refine every section at once").classes("font-bold").style(
            f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
        ui.label("Apply one instruction across all speakers and the Guidance section together — same "
                 "guardrails as a single section (figures and consensus framing are protected; nothing is "
                 "invented). Sections without a draft yet are skipped. Runs one AI pass per section.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        with ui.row().classes("w-full items-end gap-2").style("margin-top:4px;"):
            all_instr = ui.input(
                label="Instruction for every section",
                placeholder="e.g. make the whole script less promotional · tighten throughout · warmer, plainer tone",
            ).classes("flex-grow").props("dense outlined")

            def refine_all(all_instr=all_instr):
                instr = (all_instr.value or "").strip()
                if not instr:
                    ui.notify("Type an instruction to apply across every section.", type="warning")
                    return
                ui.notify("Refining every section — one AI pass per speaker, this takes a moment…", type="info")
                try:
                    s = _refine_all_sections(ss, instr)
                except Exception as exc:
                    ui.notify(f"Refine-all failed: {exc}", type="negative")
                    raise
                if s["changed"]:
                    parts = [f"Refined {s['changed']} section(s): {', '.join(s['sections'])}."]
                    if s["skipped_empty"]:
                        parts.append(f"{s['skipped_empty']} had no draft yet.")
                    if s["skipped_ai"]:
                        parts.append(f"{s['skipped_ai']} skipped — AI unavailable.")
                    ui.notify(" ".join(parts), type="positive")
                    _refresh()  # full re-render so every draft box shows the revised text
                elif s["skipped_ai"]:
                    ui.notify("Refine needs the AI (ANTHROPIC_API_KEY) — sections left unchanged.", type="warning")
                else:
                    ui.notify("No changes — nothing had a draft yet, or the sections already matched.",
                              type="info")

            ui.button("Refine all sections", icon="auto_fix_high", on_click=refine_all).props(
                "color=primary dense")

    with ui.expansion("Full Script (assembled)", value=True).classes("w-full").style(
            f"border:1px solid {COLORS['border']};border-radius:8px;"):
        ui.label("Editable — for final full-script-level tweaks (e.g. smoothing the handoff between two "
                  "speakers). Edits autosave as you type, but click Save for an explicit confirmation that "
                  "this exact text is the version moving forward to CFO/CEO review.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        full_box = ui.textarea("Full Script", value=_full_script_text(ss)).classes("w-full").props("rows=16 outlined")
        _fullref["box"] = full_box   # so a section submit refreshes this panel live (see _refresh_full)

        saved_at = ss.get("full_script_override_saved_at")
        status_label = ui.label(
            f"Saved {saved_at} — this is the version moving forward." if saved_at
            else "Not yet explicitly saved — click Save below."
        ).style(f"color:{'#15803D' if saved_at else COLORS['text_muted']};font-size:var(--fs-xs);font-weight:{'600' if saved_at else '400'};")

        def save_full_edit(e):
            # Autosave on every change so nothing is lost if the tab closes,
            # but this alone isn't what tells the user "this is final" — the
            # explicit Save button below does that with a clear confirmation.
            ss["full_script_override"] = e.value
            _save_json("script_workflow_state.json", ss)

        full_box.on_value_change(save_full_edit)

        def save_final(box=full_box, lbl=status_label):
            ss["full_script_override"] = box.value
            ts = datetime.now().strftime("%Y-%m-%d %H:%M")
            ss["full_script_override_saved_at"] = ts
            _save_json("script_workflow_state.json", ss)
            lbl.text = f"Saved {ts} — this is the version moving forward."
            lbl.style("color:#15803D;font-size:var(--fs-xs);font-weight:600;")
            ui.notify("Saved. This is the version that will go to CFO/CEO review.", type="positive")

        with ui.row().classes("w-full items-center gap-2").style("margin-top:6px;"):
            ui.button("Save", on_click=save_final).props("color=primary dense")

            def export_txt(box=full_box):
                fname = f"{CT('ticker')}_{CE().get('current_quarter','')}_Script_v{ss.get('version',1)}.txt".replace(" ", "_")
                ui.download(box.value.encode(), fname)

            ui.button("Download Current Draft", on_click=export_txt).props("flat")

            def export_teleprompter():
                html = _teleprompter_html(ss)
                fname = f"{CT('ticker')}_{CE().get('current_quarter','')}_Teleprompter.html".replace(" ", "_")
                ui.download(html.encode("utf-8"), fname)

            ui.button("Teleprompter (HTML)", icon="present_to_all", on_click=export_teleprompter).props("flat")

            fp = ss.get("first_pass_complete")
            if fp:
                ui.label(f"First Pass Completed — {fp}").style("color:#15803D;font-size:var(--fs-sm);font-weight:600;")
            else:
                def mark_first_pass(box=full_box, lbl=status_label):
                    ss["full_script_override"] = box.value
                    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
                    ss["full_script_override_saved_at"] = ts
                    ss["first_pass_complete"] = ts
                    _add_version(ss, "v1 — First Pass", "First Pass Complete — full script assembled and reviewed end-to-end", "IR")
                    _save_json("script_workflow_state.json", ss)
                    ui.notify("Saved and marked First Pass Completed.", type="positive")
                    _refresh()

                ui.button("Save & Mark First Pass Completed", on_click=mark_first_pass).props("color=primary dense")

        # Deterministic audits of the assembled script: numbers tie-out + call time budget.
        _render_number_tieout(ss)
        _render_time_budget(ss)


# ─────────────────────────────────────────────────────────────────────────
# Tab 1 — Script Generation: 5-stage pipeline (see module docstring)
# ─────────────────────────────────────────────────────────────────────────
def _render_stage1_illustrative(ss):
    """Stage 1 CFO Numbers for the illustrative demo (Northlake) — net-revenue segments, the standard
    profitability lines, and the three Street KPIs the CFO enters: Integrated Volume (TPV) + YoY, Net
    Revenue Retention, and Net Take-Rate. The baseline is carried forward from the prior quarter's
    transcript (Prior Qtr Review); this is developed for the first demo, not auto-extracted yet."""
    _hdr = lambda s: ui.label(s).classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:var(--fs-sm);")
    ui.label("Stage 1 — CFO Final Numbers").classes("font-bold").style("font-size:var(--fs-md);")
    ui.label("CFO submits Q2 actuals. Submitting activates Stage 2 (IR Review).").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
    n = ss.get("q2_numbers", {}) or {}
    prior = n.get("prior", {}) or {}
    ui.label("Baseline carried forward from the Q1 2026 earnings call (Prior Qtr Review) — update to Q2 actuals.").style(
        f"background:{COLORS['surface_hover_bg']};border-left:3px solid {COLORS['accent']};border-radius:6px;"
        f"padding:6px 10px;color:{COLORS['text_body']};font-size:var(--fs-xs);margin:6px 0;")
    def _num(label, key, step):
        return ui.number(label, value=n.get(key), step=step).props("outlined dense").classes("w-full")

    def _col():
        return ui.column().classes("flex-1 gap-2").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "border-radius:10px;padding:14px 16px;")

    with ui.row().classes("w-full gap-4 items-stretch"):
        with _col():
            _hdr("NET REVENUE ($M)")
            fn_rev = _num("Total Net Revenue", "rev", 0.1)
            fn_integ = _num("Integrated Payments", "integrated", 0.1)
            fn_legacy = _num("Legacy Processing", "legacy", 0.1)
            _hdr("CASH")
            fn_cash = _num("Cash ($M)", "cash", 0.1)
        with _col():
            _hdr("PROFITABILITY")
            fn_gp = _num("Gross Profit ($M)", "gp", 0.1)
            fn_gm = _num("Gross Margin (%)", "gm", 0.1)
            fn_ebitda = _num("Adj. EBITDA ($M)", "ebitda", 0.1)
            fn_eps = _num("Adj. EPS ($)", "eps", 0.01)
            fn_sga = _num("SG&A ($M)", "sga", 0.1)
        with _col():
            _hdr("STREET KPIs")
            fn_tpv = _num("Integrated Volume / TPV ($B)", "tpv", 0.01)
            fn_tpv_yoy = _num("TPV YoY (%)", "tpv_yoy", 0.5)
            fn_nrr = _num("Net Revenue Retention (%)", "nrr", 0.5)
            fn_take = _num("Net Take-Rate (bps)", "take_rate", 0.5)
            if prior:
                ui.label(f"Q1: TPV +{prior.get('tpv_yoy', 0):.0f}% · NRR {prior.get('nrr', 0):.0f}% · "
                         f"take-rate {prior.get('take_rate', 0):.0f} bps").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

    # ── FULL-YEAR GUIDANCE — the CFO sets the guided ranges HERE, at the source, alongside the actuals.
    # These are THE input for the Guidance Bridge and the script's guidance language — no seeded, un-
    # settable numbers (which is exactly why EPS guidance had "no input"). Revenue also drives the ①
    # decision + language; EPS and EBITDA drive their own bridge cards.
    _gi = (ss.get("guidance_inputs") or {}).get("metrics", {})

    def _grng(key):
        m = _gi.get(key, {}) or {}
        pr = m.get("prior_fy_range") or [None, None]
        return pr, (m.get("new_fy_range") or pr)
    _pr_rev, _nw_rev = _grng("rev")
    _pr_eps, _nw_eps = _grng("eps")
    _pr_ebd, _nw_ebd = _grng("ebitda")

    ui.markdown("---")
    _hdr("FULL-YEAR GUIDANCE — FY2026 (what the company will guide on the call)")
    ui.label("Set the guided ranges here, at the source — they drive the Guidance Bridge analysis and the "
             "script's guidance language.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
    with ui.row().classes("w-full gap-4 items-stretch"):
        with _col():
            _hdr("NET REVENUE ($M)")
            fg_rev_lo = ui.number("New low", value=_nw_rev[0], step=0.5).props("outlined dense").classes("w-full")
            fg_rev_hi = ui.number("New high", value=_nw_rev[1], step=0.5).props("outlined dense").classes("w-full")
            if _pr_rev[0] is not None:
                ui.label(f"Prior guide: ${_pr_rev[0]:.1f}–{_pr_rev[1]:.1f}M").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        with _col():
            _hdr("ADJ. EPS ($)")
            fg_eps_lo = ui.number("New low", value=_nw_eps[0], step=0.01).props("outlined dense").classes("w-full")
            fg_eps_hi = ui.number("New high", value=_nw_eps[1], step=0.01).props("outlined dense").classes("w-full")
            if _pr_eps[0] is not None:
                ui.label(f"Prior guide: ${_pr_eps[0]:.2f}–{_pr_eps[1]:.2f}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        with _col():
            _hdr("ADJ. EBITDA ($M)")
            fg_ebd_lo = ui.number("New low", value=_nw_ebd[0], step=0.1).props("outlined dense").classes("w-full")
            fg_ebd_hi = ui.number("New high", value=_nw_ebd[1], step=0.1).props("outlined dense").classes("w-full")
            if _pr_ebd[0] is not None:
                ui.label(f"Prior guide: ${_pr_ebd[0]:.1f}–{_pr_ebd[1]:.1f}M").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

    fn_new = ui.textarea("What's new this quarter", value=n.get("what_new", "")).props(
        "outlined autogrow").classes("w-full").style("margin-top:12px;")
    _team_opts = team_labels()
    _default_by = n.get("submitted_by")
    if _default_by not in _team_opts:
        _default_by = _team_opts[0] if _team_opts else None
    fn_by = ui.select(_team_opts, value=_default_by, label="Submitted by").props(
        "outlined dense").classes("w-full").style("max-width:340px;margin-top:8px;")

    def submit():
        if fn_rev.value is None:
            ui.notify("Total Net Revenue is required.", type="warning")
            return
        nz = lambda v: v if v is not None else 0.0
        ss["q2_numbers"] = {
            "rev": nz(fn_rev.value), "integrated": nz(fn_integ.value), "legacy": nz(fn_legacy.value),
            "gp": nz(fn_gp.value), "gm": nz(fn_gm.value), "ebitda": nz(fn_ebitda.value),
            "eps": nz(fn_eps.value), "sga": nz(fn_sga.value),
            "tpv": nz(fn_tpv.value), "tpv_yoy": nz(fn_tpv_yoy.value), "nrr": nz(fn_nrr.value),
            "take_rate": nz(fn_take.value), "cash": nz(fn_cash.value), "prior": prior,
            "what_new": fn_new.value, "submitted_by": fn_by.value,
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        # Full-year guidance -> the bridge's source (each guided line) + the revenue decision (gd).
        _gim = ss.setdefault("guidance_inputs", {}).setdefault("metrics", {})

        def _set_new_range(key, lo, hi):
            if lo is not None and hi is not None:
                _gim.setdefault(key, {})["new_fy_range"] = [float(lo), float(hi)]
        _set_new_range("rev", fg_rev_lo.value, fg_rev_hi.value)
        _set_new_range("eps", fg_eps_lo.value, fg_eps_hi.value)
        _set_new_range("ebitda", fg_ebd_lo.value, fg_ebd_hi.value)
        if fg_rev_lo.value is not None and fg_rev_hi.value is not None:
            _gd = ss.setdefault("guidance_decision", {})
            _gd["new_low"], _gd["new_hi"] = float(fg_rev_lo.value), float(fg_rev_hi.value)
            try:
                from core import guidance_engine as _ge2
                _prv = (_gim.get("rev", {}) or {}).get("prior_fy_range") or [fg_rev_lo.value, fg_rev_hi.value]
                _gd["action"] = _ge2.characterize_range_change(_prv, [fg_rev_lo.value, fg_rev_hi.value])["action_key"]
            except Exception:
                pass
        ss["version"] = 1
        ss["stages"]["cfo_numbers"].update({"status": "complete", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
        ss["stages"]["ir_review"]["status"] = "active"
        ss["current_stage"] = "ir_review"
        _ensure_script_drafted(ss)   # fills only EMPTY sections — the seeded NLKP script is preserved
        _add_version(ss, "v1", "Draft v1 — CFO numbers populated", fn_by.value)
        _save_json("script_workflow_state.json", ss)
        ui.notify("Numbers submitted. Stage 2 (IR Review) active.")
        _refresh()

    ui.button("Submit for Draft Generation", on_click=submit).props("color=primary").style("margin-top:8px;")

    if ss["stages"]["cfo_numbers"]["status"] == "complete":
        _ensure_script_drafted(ss)
        ui.markdown("---")
        ui.label("Auto-Generated Script — one last look before it moves to IR").classes("font-bold").style(
            f"color:{COLORS['accent_light']};font-size:var(--fs-md);")
        ui.textarea("Script preview", value=_full_script_text(ss)).classes("w-full").props("rows=14 readonly outlined")


def _render_stage1(ss):
    from config.client_config import get_active_client_id
    from core.curated_targets import _is_illustrative
    if _is_illustrative(get_active_client_id()):
        _render_stage1_illustrative(ss)   # Northlake schema: net-revenue segments + the 3 Street KPIs
        return
    ui.label("Stage 1 — CFO Final Numbers").classes("font-bold").style("font-size:var(--fs-md);")
    ui.label("CFO submits Q2 actuals. Submitting activates Stage 2 (IR Review).").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
    n = ss.get("q2_numbers", {})
    _hdr = lambda s: ui.label(s).classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:var(--fs-sm);")

    def _num(label, key, step):
        return ui.number(label, value=n.get(key), step=step).props("outlined dense").classes("w-full")

    def _col():
        return ui.column().classes("flex-1 gap-2").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "border-radius:10px;padding:14px 16px;")

    with ui.row().classes("w-full gap-4 items-stretch"):
        with _col():
            _hdr("REVENUE ($M)")
            fn_rev = _num("Total Revenue", "rev", 0.1)
            fn_ach = _num("ACH Revenue", "ach", 0.1)
            fn_card = _num("Card / PayFac", "card", 0.1)
            fn_prepaid = _num("Prepaid Revenue", "prepaid", 0.1)
            fn_output = _num("Output Solutions", "output", 0.1)
        with _col():
            _hdr("PROFITABILITY")
            fn_gp = _num("Gross Profit ($M)", "gp", 0.1)
            fn_gm = _num("Gross Margin (%)", "gm", 0.1)
            fn_ebitda = _num("Adj. EBITDA ($M)", "ebitda", 0.1)
            fn_eps = _num("GAAP EPS ($)", "eps", 0.01)
            fn_sga = _num("Total SG&A ($M)", "sga", 0.1)
        with _col():
            _hdr("VOLUME & CASH")
            fn_vol = _num("Vol Processed ($B)", "vol", 0.1)
            fn_vol_yoy = _num("Volume YoY (%)", "vol_yoy", 0.5)
            fn_txn = _num("Transactions (M)", "txn", 0.1)
            fn_cash = _num("Cash ($M)", "cash", 0.1)
            fn_buyback = _num("Buyback ($K)", "buyback", 10.0)

    fn_new = ui.textarea("What's new this quarter", value=n.get("what_new", "")).props(
        "outlined autogrow").classes("w-full").style("margin-top:12px;")
    # Roster comes from the active client's profile, not hardcoded USIO execs.
    _team_opts = team_labels()
    _default_by = n.get("submitted_by")
    if _default_by not in _team_opts:
        _default_by = _team_opts[0] if _team_opts else None
    fn_by = ui.select(_team_opts, value=_default_by, label="Submitted by").props(
        "outlined dense").classes("w-full").style("max-width:340px;margin-top:8px;")

    def submit():
        if fn_rev.value is None:
            ui.notify("Total Revenue is required.", type="warning")
            return
        nz = lambda v: v if v is not None else 0.0
        ss["q2_numbers"] = {
            "rev": nz(fn_rev.value), "ach": nz(fn_ach.value), "card": nz(fn_card.value),
            "prepaid": nz(fn_prepaid.value), "output": nz(fn_output.value),
            "gp": nz(fn_gp.value), "gm": nz(fn_gm.value), "ebitda": nz(fn_ebitda.value),
            "eps": nz(fn_eps.value), "sga": nz(fn_sga.value),
            "vol": nz(fn_vol.value), "vol_yoy": nz(fn_vol_yoy.value), "txn": nz(fn_txn.value),
            "cash": nz(fn_cash.value), "buyback": nz(fn_buyback.value),
            "what_new": fn_new.value, "submitted_by": fn_by.value,
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        ss["version"] = 1
        ss["stages"]["cfo_numbers"].update({"status": "complete", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
        ss["stages"]["ir_review"]["status"] = "active"
        ss["current_stage"] = "ir_review"

        # Auto-draft every persona section + guidance now, so "Draft v1" is
        # genuinely a complete script by the time Stage 2 opens — not just
        # whichever persona tab someone happened to visit and manually
        # generate. (_ensure_script_drafted also runs on every Script Canvas
        # render as a safety net, so this call here isn't strictly load-
        # bearing, but doing it immediately means the "Draft v1 generated"
        # notification below is accurate right away.)
        _ensure_script_drafted(ss)

        _add_version(ss, "v1", "Draft v1 — CFO numbers populated, all sections auto-drafted", fn_by.value)
        _save_json("script_workflow_state.json", ss)
        ui.notify("Numbers submitted. Draft v1 generated for all sections. Stage 2 active.")
        _refresh()

    ui.button("Submit for Draft Generation", on_click=submit).props("color=primary").style("margin-top:8px;")

    # CFO's own "one last look" — previously Stage 1 only ever showed the
    # numbers form, and the generated script itself only appeared several
    # tabs later once IR had already had a pass at it. This shows the actual
    # script content right here, right after submission, so CFO isn't
    # seeing it for the first time downstream. Formal sign-off (with a
    # notes box) still happens on the CEO+CFO Review tab once IR is done —
    # this is a preview, not a second approval gate.
    if ss["stages"]["cfo_numbers"]["status"] == "complete":
        _ensure_script_drafted(ss)
        ui.markdown("---")
        ui.label("Auto-Generated Script — one last look before it moves to IR").classes("font-bold").style(
            f"color:{COLORS['accent_light']};font-size:var(--fs-md);")
        ui.label("This is the draft that was just generated from the numbers above. You'll formally sign off "
                  "on it (with a notes box) on the \"3 · CEO+CFO Review\" tab after IR's pass.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        ui.textarea("Script preview", value=_full_script_text(ss)).classes("w-full").props("rows=14 readonly outlined")


# The 9 Q1-disclosed metrics the Disclosure Consistency Rule tracks — if any
# of these come back empty/zero on submit, they're flagged as a gap unless
# disclosure_notes explains the omission. Matches app.py's original _gaps.
_OPS_METRIC_LABELS = {
    "card_yoy": "Card YoY %",
    "payfac_pct": "PayFac % of card",
    "payfac_growth_rate": "PayFac growth characterization",
    "card_txn_yoy": "Card transactions YoY",
    "filtered_merchants": "Filtered Spend merchant count",
    "rtp_txn_k": "RTP transaction volume",
    "ach_txn_yoy": "ACH transactions YoY",
    "prepaid_load_yoy": "Prepaid load volume YoY",
    "usio_one_example": "Usio ONE case study",
}


_OPS_LABELS_ILLUS = {
    "tpv": "Integrated Volume (TPV)", "tpv_yoy": "TPV YoY", "nrr": "Net Revenue Retention",
    "take_rate": "Net Take-Rate", "integrated_mix": "Integrated Mix",
    "new_partner_golives": "New Partner Go-Lives", "isv_in_impl": "ISV Partners in Implementation",
}


def _render_stage1b_illustrative(ss):
    """Stage 1B for the illustrative demo (Northlake) — the operating KPIs the Street tracks each
    quarter plus the partner-pipeline detail, not USIO's card/PayFac/ACH/prepaid metrics."""
    _h = lambda s: ui.label(s).classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:var(--fs-sm);")
    ui.markdown("---")
    ui.label("Stage 1B — Operating Metrics & Disclosure Consistency Check").classes("font-bold").style("font-size:var(--fs-md);")
    ui.label("Every metric disclosed last quarter should be disclosed again this quarter, or explicitly "
             "explained if it's being dropped — silence here is exactly what prompts analyst follow-up "
             "questions. This feeds the Business Operations draft below in addition to the gap check.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
    ops = ss.get("q2_ops_metrics", {}) or {}

    def _onum(label, key, step):
        return ui.number(label, value=ops.get(key), step=step).props("outlined dense").classes("w-full")

    def _ocol():
        return ui.column().classes("flex-1 gap-2").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "border-radius:10px;padding:14px 16px;")

    with ui.row().classes("w-full gap-4 items-stretch"):
        with _ocol():
            _h("INTEGRATED PAYMENTS KPIs")
            om_tpv = _onum("Integrated Volume / TPV ($B)", "tpv", 0.01)
            om_tpv_yoy = _onum("TPV YoY (%)", "tpv_yoy", 0.5)
            om_nrr = _onum("Net Revenue Retention (%)", "nrr", 0.5)
            om_take = _onum("Net Take-Rate (bps)", "take_rate", 0.5)
            om_mix = _onum("Integrated Mix (% of net revenue)", "integrated_mix", 0.5)
        with _ocol():
            _h("PARTNER PIPELINE & GO-LIVES")
            om_golives = _onum("New Partner Go-Lives (this qtr)", "new_partner_golives", 1.0)
            om_isv = _onum("ISV Partners in Implementation", "isv_in_impl", 1.0)
            om_live = _onum("Total Integrated Partners Live", "partners_live", 1.0)
            om_merch = _onum("Active Merchants (K)", "active_merchants_k", 1.0)
        with _ocol():
            _h("LEGACY & OUTLOOK")
            om_legacy = _onum("Legacy Processing Revenue YoY (%)", "legacy_rev_yoy", 0.5)
            om_float = ui.select(["Stable", "Declining", "Growing"],
                                 value=ops.get("prepaid_float", "Stable"), label="Prepaid Float Balances").props(
                "outlined dense").classes("w-full")
            om_vert = ui.textarea("New-Vertical Progress", value=ops.get("new_verticals", "")).props(
                "outlined autogrow").classes("w-full")

    missing_now = [lbl for key, lbl in _OPS_LABELS_ILLUS.items() if ops.get(key) in (None, "", 0)]
    if missing_now:
        with ui.card().classes("w-full").style(f"background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.3);"):
            ui.label(f"{len(missing_now)} metric(s) disclosed last quarter aren't entered yet:").style(
                f"color:#92400E;font-size:var(--fs-sm);font-weight:600;")
            for _m in missing_now:
                ui.label(f"• {_m}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
    om_notes = ui.textarea("Explain any intentional metric omissions (reviewed in Stage 2)",
                           value=ops.get("disclosure_notes", "")).props("outlined autogrow").classes(
        "w-full").style("margin-top:8px;")

    def submit_ops():
        new_ops = {
            "tpv": om_tpv.value, "tpv_yoy": om_tpv_yoy.value, "nrr": om_nrr.value, "take_rate": om_take.value,
            "integrated_mix": om_mix.value, "new_partner_golives": om_golives.value, "isv_in_impl": om_isv.value,
            "partners_live": om_live.value, "active_merchants_k": om_merch.value, "legacy_rev_yoy": om_legacy.value,
            "prepaid_float": om_float.value, "new_verticals": om_vert.value, "disclosure_notes": om_notes.value,
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        missing = [lbl for key, lbl in _OPS_LABELS_ILLUS.items() if new_ops.get(key) in (None, "", 0)]
        new_ops["missing_count"] = len(missing)
        new_ops["missing_items"] = missing
        ss["q2_ops_metrics"] = new_ops
        _save_json("script_workflow_state.json", ss)
        if missing and not new_ops["disclosure_notes"]:
            ui.notify(f"Saved — {len(missing)} metric(s) from last quarter aren't filled in and no explanation "
                      f"was given. Stage 2 IR review will flag these.", type="warning")
        else:
            ui.notify(f"Operating metrics submitted. {len(missing)} disclosure gap(s) noted.")
        _refresh()

    ui.button("Submit Operating Metrics", on_click=submit_ops).props("color=primary").style("margin-top:8px;")


def _render_stage1b(ss):
    """Stage 1B — Operating Metrics & Disclosure Consistency Check. Ported
    from app.py's second Stage 1 input column (see this module's docstring
    for why it was skipped in the first pass). Submitted independently of
    _render_stage1() above — it doesn't gate the Stage 2 transition, it just
    feeds richer detail into the CRO/business-ops persona draft (see
    _generate_persona_draft) and surfaces any metric that quietly dropped
    out of disclosure versus last quarter."""
    from config.client_config import get_active_client_id
    from core.curated_targets import _is_illustrative
    if _is_illustrative(get_active_client_id()):
        _render_stage1b_illustrative(ss)   # Northlake operating KPIs, not USIO card/ACH/prepaid metrics
        return
    ui.markdown("---")
    ui.label("Stage 1B — Operating Metrics & Disclosure Consistency Check").classes("font-bold").style("font-size:var(--fs-md);")
    ui.label("Every metric disclosed last quarter should be disclosed again this quarter, or explicitly "
              "explained if it's being dropped — silence here is exactly what prompts analyst follow-up "
              "questions. This feeds the Business Operations draft below in addition to the gap check.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    ops = ss.get("q2_ops_metrics", {})

    def _onum(label, key, step):
        return ui.number(label, value=ops.get(key), step=step).props("outlined dense").classes("w-full")

    def _ocol():
        return ui.column().classes("flex-1 gap-2").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "border-radius:10px;padding:14px 16px;")

    def _oh(s):
        return ui.label(s).classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:var(--fs-sm);")

    with ui.row().classes("w-full gap-4 items-stretch").style("margin-top:8px;"):
        with _ocol():
            _oh("CARD REVENUE METRICS")
            om_card_yoy = _onum("Card Revenue YoY (%)", "card_yoy", 0.5)
            om_payfac_pct = _onum("PayFac % of Card Revenue", "payfac_pct", 0.5)
            om_payfac_yoy = _onum("PayFac Revenue YoY (%)", "payfac_yoy", 0.5)
            om_card_txn_yoy = _onum("Card Transactions YoY (%)", "card_txn_yoy", 0.5)
            om_card_vol_yoy = _onum("Card Dollar Volume YoY (%)", "card_vol_yoy", 0.5)
        with _ocol():
            _oh("PAYFAC PIPELINE & IMPLEMENTATIONS")
            om_isv_impl = _onum("ISVs in Implementation", "isv_impl", 1.0)
            om_new_enterprise = _onum("New Enterprise Accounts (this qtr)", "new_enterprise", 1.0)
            om_filtered_merchants = _onum("Filtered Spend Merchants Live", "filtered_merchants", 100.0)
            om_rtp_txn = _onum("Real-Time Payments Txn/Month (K)", "rtp_txn_k", 1.0)
            om_payfac_growth_rate = ui.select(
                ["Growing >20% (consistent)", "Growing 15-20%", "Growing 10-15%", "Growing <10%", "Decelerating — explain in notes"],
                value=ops.get("payfac_growth_rate"), label="PayFac Growth Rate Characterization").props(
                "outlined dense").classes("w-full")
        with _ocol():
            _oh("USIO ONE & CROSS-SELL")
            om_usio_one_wins = _onum("Usio ONE Cross-Sell Wins (this qtr)", "usio_one_wins", 1.0)
            om_usio_one_example = ui.textarea("Usio ONE Case Study", value=ops.get("usio_one_example", "")).props(
                "outlined autogrow").classes("w-full")
            om_new_leads = ui.select(
                ["G2 / Online influencer sites", "SEO / Digital marketing", "Trade shows",
                 "Usio ONE cross-sell", "Referral agents", "Direct outbound"],
                value=ops.get("new_leads", []), label="New Lead Sources Active", multiple=True).props(
                "outlined dense").classes("w-full")

    ui.markdown("---")
    _oh("ACH & PAYMENTS")
    with ui.row().classes("w-full gap-4 items-stretch"):
        with _ocol():
            om_ach_txn_yoy = _onum("ACH Transactions YoY (%)", "ach_txn_yoy", 0.5)
            om_ach_dollar_yoy = _onum("ACH Dollar Volume YoY (%)", "ach_dollar_yoy", 0.5)
            om_ach_best_month = ui.select(
                ["Yes — best-ever month", "Yes — different month", "No — but strong", "No — slower than prior quarter"],
                value=ops.get("ach_best_month"), label="Best-Ever ACH Month This Quarter?").props(
                "outlined dense").classes("w-full")
        with _ocol():
            om_prepaid_load_yoy = _onum("Prepaid Load Volume YoY (%)", "prepaid_load_yoy", 0.5)
            om_prepaid_txn_yoy = _onum("Prepaid Transactions YoY (%)", "prepaid_txn_yoy", 0.5)
            om_prepaid_purchase_yoy = _onum("Prepaid Purchase Volume YoY (%)", "prepaid_purchase_yoy", 0.5)

    if ops:
        missing = [label for key, label in _OPS_METRIC_LABELS.items() if ops.get(key) in (None, "", 0)]
        if missing:
            with ui.card().classes("w-full").style("background:rgba(252,211,77,.08);border:1px solid rgba(252,211,77,.25);margin-top:8px;"):
                ui.label(f"{len(missing)} metric(s) disclosed last quarter aren't entered yet:").style(
                    "color:#A16207;font-weight:bold;font-size:var(--fs-base);")
                for m in missing:
                    ui.label(f"• {m}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    om_disclosure_notes = ui.textarea("Explain any intentional metric omissions (reviewed in Stage 2)",
                                       value=ops.get("disclosure_notes", "")).props("outlined autogrow").classes(
        "w-full").style("margin-top:8px;")

    def submit_ops():
        new_ops = {
            "card_yoy": om_card_yoy.value, "payfac_pct": om_payfac_pct.value, "payfac_yoy": om_payfac_yoy.value,
            "card_txn_yoy": om_card_txn_yoy.value, "card_vol_yoy": om_card_vol_yoy.value,
            "isv_impl": om_isv_impl.value, "new_enterprise": om_new_enterprise.value,
            "filtered_merchants": om_filtered_merchants.value, "rtp_txn_k": om_rtp_txn.value,
            "payfac_growth_rate": om_payfac_growth_rate.value,
            "usio_one_wins": om_usio_one_wins.value, "usio_one_example": om_usio_one_example.value,
            "new_leads": om_new_leads.value, "ach_txn_yoy": om_ach_txn_yoy.value,
            "ach_dollar_yoy": om_ach_dollar_yoy.value, "ach_best_month": om_ach_best_month.value,
            "prepaid_load_yoy": om_prepaid_load_yoy.value, "prepaid_txn_yoy": om_prepaid_txn_yoy.value,
            "prepaid_purchase_yoy": om_prepaid_purchase_yoy.value,
            "disclosure_notes": om_disclosure_notes.value,
            "submitted_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        missing = [label for key, label in _OPS_METRIC_LABELS.items() if new_ops.get(key) in (None, "", 0)]
        new_ops["missing_count"] = len(missing)
        new_ops["missing_items"] = missing
        ss["q2_ops_metrics"] = new_ops
        _save_json("script_workflow_state.json", ss)
        if missing and not new_ops["disclosure_notes"]:
            ui.notify(f"Saved — {len(missing)} metric(s) from last quarter aren't filled in and no explanation "
                      f"was given. Stage 2 IR review will flag these.", type="warning")
        else:
            ui.notify(f"Operating metrics submitted. {len(missing)} disclosure gap(s) noted.")
        _refresh()

    ui.button("Submit Operating Metrics", on_click=submit_ops).props("color=primary").style("margin-top:8px;")


def _check_script_consistency(ss):
    """Lightweight cross-persona consistency checks — not full NLP, just
    the highest-value, cheaply-detectable mismatches: does the CEO
    narrative actually use language matching the recorded Guidance
    Decision, and does the CFO section mention the actual Stage 1 revenue
    figure. Non-blocking — these surface as warnings in Stage 2, the human
    still decides whether to proceed to Stage 3."""
    warnings = []
    texts = ss.get("script_text", {})
    gd = ss.get("guidance_decision", {})
    n = ss.get("q2_numbers", {})

    ceo_text = (texts.get("ceo_narrative") or "").lower()
    cfo_text = (texts.get("cfo_fin") or "").lower()

    action_keywords = {
        "raise_low": ["raising", "raise"], "raise_mid": ["raising", "raise"],
        "narrow": ["narrowing", "narrow"], "reiterate": ["reiterat"],
    }
    if ceo_text:
        if not gd.get("action"):
            warnings.append("CEO narrative has been drafted, but no Guidance Decision has been recorded yet — "
                             "its tone/H2 language may not reflect an actual decision.")
        else:
            expected = action_keywords.get(gd["action"], [])
            matched_other = [a for a, kws in action_keywords.items()
                              if a != gd["action"] and any(kw in ceo_text for kw in kws)
                              and not any(kw in ceo_text for kw in expected)]
            if matched_other:
                warnings.append(
                    f"CEO narrative reads like '{matched_other[0].replace('_',' ')}' language, but the recorded "
                    f"Guidance Decision is '{gd['action'].replace('_',' ')}' — these should match."
                )
            elif expected and not any(kw in ceo_text for kw in expected):
                warnings.append(
                    f"CEO narrative doesn't clearly use '{gd['action'].replace('_',' ')}' language, matching the "
                    f"recorded Guidance Decision — double-check the tone lines up."
                )

    if cfo_text and n.get("rev") is not None:
        if f"{n['rev']:.1f}" not in cfo_text and f"{n['rev']:.0f}" not in cfo_text:
            warnings.append(
                f"CFO section doesn't appear to mention the Stage 1 revenue figure (${n['rev']:.1f}M) — verify "
                f"the drafted numbers match what was actually submitted."
            )
    return warnings


def _render_stage2(ss):
    ui.label("Stage 2 — IR Review").classes("font-bold").style("font-size:var(--fs-md);")
    if ss["stages"]["cfo_numbers"]["status"] != "complete":
        ui.label("Nothing here yet — go to the \"1 · CFO Numbers\" tab and click \"Submit for Draft "
                  "Generation\" first.").style(f"color:{COLORS['warning']};")
        return
    # (Removed the top actuals-metric cards — they restated Stage-1 inputs and duplicated the far richer
    # read in the guidance bridge below. This is the ANALYSIS view; it leads with the guidance analysis.)
    _render_script_canvas(ss)

    consistency_warnings = _check_script_consistency(ss)
    if consistency_warnings:
        ui.markdown("---")
        with ui.card().classes("w-full").style("background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.35);"):
            ui.label("Consistency check — review before advancing to Stage 3").classes("font-bold").style(
                "color:#A16207;font-size:var(--fs-base);")
            for w in consistency_warnings:
                ui.label(f"• {w}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")

    ui.markdown("---")
    contacts = _contacts()
    rv = ss["reviewers"]["IR"]
    c = contacts["IR"]
    with ui.row().classes("w-full gap-6"):
        with ui.column().classes("flex-[2]"):
            ui.label(f"{c['name']} — {c['email']}").classes("font-bold")
            if rv["status"] == "pending":
                ui.label("Generate Script v1 with numbers populated and send to IR.").style(f"color:{COLORS['text_muted']};")

                def send_ir():
                    rv["status"] = "sent"
                    rv["sent"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    _save_json("script_workflow_state.json", ss)
                    ui.notify(f"Script v1 queued for {c['email']}")
                    _refresh()

                ui.button("Generate v1 + Send to IR", on_click=send_ir).props("color=primary")
            elif rv["status"] == "sent":
                sent_dt = datetime.strptime(rv["sent"], "%Y-%m-%d %H:%M")
                hrs = (datetime.now() - sent_dt).total_seconds() / 3600
                if hrs >= 24:
                    ui.label(f"Overdue — {hrs:.0f}h since sent.").style(f"color:{COLORS['danger']};")
                else:
                    ui.label(f"Sent {hrs:.0f}h ago — awaiting return").style(f"color:{COLORS['accent_light']};")
                notes_in = ui.textarea("IR edit notes", value=rv.get("notes", "")).props("outlined autogrow").classes("w-full")

                def mark_complete():
                    rv.update({"status": "complete", "received": datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": notes_in.value})
                    ss["stages"]["ir_review"].update({"status": "complete", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": notes_in.value})
                    ss["stages"]["exec_review"]["status"] = "active"
                    ss["current_stage"] = "exec_review"
                    ss["version"] = 2
                    _add_version(ss, "v2", "Script v2 — IR reviewed", c["name"])
                    _save_json("script_workflow_state.json", ss)
                    ui.notify("IR review complete. Stage 3 active.")
                    _refresh()

                ui.button("Mark IR Complete", on_click=mark_complete).props("color=primary")
            else:
                ui.label("IR review complete").style("color:#15803D;")
        with ui.column().classes("flex-1"):
            ui.label("IR Review Checklist").classes("font-bold").style("font-size:var(--fs-md);")
            for item in ["Numbers match exactly", "Beat/miss language correct", "All fields populated", "Tone calibrated", "FLS flagged", "Talking points approved"]:
                ui.checkbox(item)


def _check_stage3_advance(ss):
    # CRO added to the gate Jul 10, 2026, alongside CFO/CEO — all three
    # must sign off before Stage 4 opens. See _blank_script_state's comment
    # on why this goes beyond what the original demo ever required.
    if (ss["reviewers"]["CFO"]["status"] == "complete"
            and ss["reviewers"]["CEO"]["status"] == "complete"
            and ss["reviewers"]["CRO"]["status"] == "complete"):
        if ss["stages"]["exec_review"]["status"] != "complete":
            ss["stages"]["exec_review"].update({"status": "complete", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
            ss["stages"]["consolidate"]["status"] = "active"
            ss["current_stage"] = "consolidate"
            _save_json("script_workflow_state.json", ss)
            ui.notify("All three reviews complete. Stage 4 active.")


def _render_stage3(ss):
    ui.label("Stage 3 — CFO + CEO + CRO Simultaneous Review").classes("font-bold").style("font-size:var(--fs-md);")
    if ss["stages"]["ir_review"]["status"] != "complete":
        ui.label("Nothing here yet — go to the \"2 · IR Review\" tab and click \"Mark IR Complete\" "
                  "first (the tabs above aren't locked, so it's easy to land here before that step).").style(
            f"color:{COLORS['warning']};")
        return
    # Open by default — this used to be a collapsed ui.expansion, which meant
    # CFO/CEO/CRO landing on this stage saw no script at all unless they
    # thought to click it open. It's the whole point of this stage, so show it.
    with ui.expansion("Script Canvas — View & Edit", value=True).classes("w-full"):
        _render_script_canvas(ss)
    ui.markdown("---")
    contacts = _contacts()
    with ui.row().classes("w-full gap-6"):
        for role in ("CFO", "CEO", "CRO"):
            rv = ss["reviewers"][role]
            c = contacts[role]
            with ui.column().classes("flex-1"):
                ui.label(f"{role} — {c['name']}").classes("font-bold")
                ui.label(c["email"]).style(f"color:{COLORS['accent_light']};font-size:var(--fs-sm);")
                if rv["status"] == "complete":
                    ui.label("Review complete").style("color:#15803D;")
                    if rv.get("notes"):
                        ui.label(f"Notes: {rv['notes']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                else:
                    # Notes box + Mark Complete are always available — "Send"
                    # is just an optional notification/overdue-timer, not a
                    # gate. Previously the notes textarea only appeared after
                    # clicking Send, so a reviewer working directly in-app saw
                    # nothing to write in and no way to sign off.
                    if rv["status"] == "sent":
                        sent_dt = datetime.strptime(rv["sent"], "%Y-%m-%d %H:%M")
                        hrs = (datetime.now() - sent_dt).total_seconds() / 3600
                        if hrs >= 24:
                            ui.label(f"Overdue {hrs:.0f}h — send reminder").style(f"color:{COLORS['danger']};")
                        else:
                            ui.label(f"Sent {hrs:.0f}h ago").style(f"color:{COLORS['accent_light']};")
                    else:
                        def send(role=role):
                            ss["reviewers"][role].update({"status": "sent", "sent": datetime.now().strftime("%Y-%m-%d %H:%M")})
                            _save_json("script_workflow_state.json", ss)
                            _refresh()

                        ui.button(f"Send v2 to {c['name']}", on_click=send).props("color=primary dense outline")

                    notes_in = ui.textarea(f"{role} comments", value=rv.get("notes", "")).props("outlined autogrow").classes("w-full")

                    def mark(role=role, notes_in=notes_in):
                        ss["reviewers"][role].update({"status": "complete", "received": datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": notes_in.value})
                        _save_json("script_workflow_state.json", ss)
                        _check_stage3_advance(ss)
                        _refresh()

                    ui.button(f"Mark {role} Complete", on_click=mark).props("dense")


def _render_stage4(ss):
    ui.label("Stage 4 — Consolidation").classes("font-bold").style("font-size:var(--fs-md);")
    if ss["stages"]["exec_review"]["status"] != "complete":
        ui.label("Nothing here yet — go to the \"3 · CEO+CFO Review\" tab and get both \"Mark CFO "
                  "Complete\" and \"Mark CEO Complete\" clicked first.").style(f"color:{COLORS['warning']};")
        return
    with ui.expansion("Script Canvas — View & Edit", value=True).classes("w-full"):
        _render_script_canvas(ss)
    ui.markdown("---")
    ui.label("Comments Side-by-Side").classes("font-bold").style("font-size:var(--fs-md);")
    contacts = _contacts()
    with ui.row().classes("w-full gap-4"):
        for role in ("IR", "CFO", "CEO"):
            with ui.column().classes("flex-1"):
                ui.label(contacts[role]["name"]).classes("font-bold")
                notes = ss["reviewers"][role].get("notes") or "(no notes logged)"
                ui.textarea("Comments", value=notes).classes("w-full").props("readonly rows=6 outlined")
    ui.markdown("---")
    cons_summary = ui.textarea("Changes incorporated into v3 (IR final decisions)").props("outlined autogrow").classes("w-full")
    cons_confirm = ui.checkbox("v3 incorporates all approved changes and is ready for legal")

    def generate_v3():
        if not cons_confirm.value:
            ui.notify("Check the confirmation box before advancing.", type="warning")
            return
        ss["stages"]["consolidate"].update({"status": "complete", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": cons_summary.value})
        ss["stages"]["legal_signoff"]["status"] = "active"
        ss["current_stage"] = "legal_signoff"
        ss["version"] = 3
        _add_version(ss, "v3", "Script v3 — Consolidated, pre-legal", "IR")
        _save_json("script_workflow_state.json", ss)
        ui.notify("v3 ready. Stage 5 active.")
        _refresh()

    ui.button("Generate v3 — Pre-Legal Clean Copy", on_click=generate_v3).props("color=primary")


def _render_stage5(ss):
    ui.label("Stage 5 — Legal Sign-Off").classes("font-bold").style("font-size:var(--fs-md);")
    if ss["stages"]["consolidate"]["status"] != "complete":
        ui.label("Nothing here yet — go to the \"4 · Consolidation\" tab, check the confirmation box, and "
                  "click \"Generate v3 — Pre-Legal Clean Copy\" first.").style(f"color:{COLORS['warning']};")
        return
    with ui.expansion("Script Canvas — View & Edit", value=True).classes("w-full"):
        _render_script_canvas(ss)
    ui.markdown("---")
    fls_items = _fls_items()
    with ui.row().classes("w-full gap-6"):
        with ui.column().classes("flex-[2]"):
            ui.label("Forward-Looking Statements Checklist").classes("font-bold").style("font-size:var(--fs-md);")
            if not fls_items:
                ui.label("No FLS checklist items configured for this client — add them to CLIENT_REGISTRY's "
                          "\"fls_items\" in config/client_config.py.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            ui.label("Every item must be individually cleared by legal before the script is finalized.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            for fls_id, fls_text in fls_items:
                cleared = ss["fls_checklist"].get(fls_id, False)
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label("" if cleared else "")
                    ui.label(f"{fls_id} {fls_text}").classes("flex-1").style(
                        f"color:{COLORS['text_body'] if cleared else COLORS['text_muted']};font-size:var(--fs-base);")
                    if cleared:
                        def reopen(fls_id=fls_id):
                            ss["fls_checklist"][fls_id] = False
                            _save_json("script_workflow_state.json", ss)
                            _refresh()
                        ui.button("Reopen", on_click=reopen).props("flat dense")
                    else:
                        def clear(fls_id=fls_id):
                            ss["fls_checklist"][fls_id] = True
                            _save_json("script_workflow_state.json", ss)
                            _refresh()
                        ui.button("Clear", on_click=clear).props("dense")
        with ui.column().classes("flex-1"):
            cleared_n = sum(1 for v in ss["fls_checklist"].values() if v)
            all_clear = cleared_n == len(fls_items)
            _metric("FLS Cleared", f"{cleared_n}/{len(fls_items)}", "Ready!" if all_clear else f"{len(fls_items)-cleared_n} remaining")
            contacts = _contacts()
            rv = ss["reviewers"]["Legal"]
            c = contacts["Legal"]
            if rv["status"] == "pending":
                def send_legal():
                    rv.update({"status": "sent", "sent": datetime.now().strftime("%Y-%m-%d %H:%M")})
                    _save_json("script_workflow_state.json", ss)
                    _refresh()
                ui.button("Send v3 + FLS Memo to Legal", on_click=send_legal).props("color=primary")
            elif rv["status"] == "sent":
                ui.label(f"Sent {rv['sent']}").style(f"color:{COLORS['text_muted']};")
                leg_notes = ui.textarea("Legal comments", value=rv.get("notes", "")).props("outlined autogrow").classes("w-full")
                if all_clear:
                    def finalize():
                        rv.update({"status": "complete", "received": datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": leg_notes.value})
                        ss["stages"]["legal_signoff"].update({"status": "complete", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
                        ss["current_stage"] = "FINAL"
                        ss["version"] = 4
                        _add_version(ss, "FINAL", f"FINAL — Legal cleared {datetime.now().strftime('%Y-%m-%d %H:%M')}", "Legal")
                        _save_json("script_workflow_state.json", ss)
                        ui.notify("SCRIPT FINALIZED — Legal cleared.")
                        _refresh()
                    ui.button("MARK FINAL — Legal Cleared", on_click=finalize).props("color=primary")
                else:
                    ui.label(f"Clear all {len(fls_items)-cleared_n} remaining FLS items first").style(f"color:{COLORS['warning']};font-size:var(--fs-sm);")
            elif rv["status"] == "complete":
                ui.label("FINAL — Legal Cleared").style("color:#15803D;")
                ui.label(f"Cleared: {rv['received']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
    if ss.get("current_stage") == "FINAL":
        ui.markdown("---")
        with ui.card().classes("w-full text-center").style("background:#E9F6EF;border:2px solid #15803D;"):
            ui.label("Script finalized — legal cleared").classes("font-bold").style("color:#15803D;font-size:var(--fs-xl);")
            ui.label("This is the approved earnings call script. Do not use any other version.").style("color:#15803D;font-size:var(--fs-base);")


def _render_narrative_momentum_tab():
    """Standalone Narrative Momentum tab (promoted from a section inside
    Tomorrow's Setup). Same shared renderer the Setup view uses — narrative_engine
    via markets_page._render_narrative_momentum — reached directly here. Lazy
    import: markets_page pulls from this module too (guidance-stance fallback), so
    a top-level import would risk a circular dependency."""
    from core import consensus as consensus_store
    from page_modules_nicegui.markets_page import _render_narrative_momentum
    seed = consensus_store.get_consensus(get_active_client_id())
    _render_narrative_momentum(seed)


def _render_tomorrow_setup(ss):
    """The forward bookend to Prior-Quarter Review. Given the guidance decided
    and the H2 catalysts named in the script above, this shows what the print
    likely brings: the guidance morning-after read (shared guidance_engine, same
    as the Decision Engine's inline read). The full Narrative Momentum signal is
    now its own tab — this view links to it rather than re-rendering it."""
    ui.markdown("---")
    ui.label("Tomorrow's Setup — what the print likely brings").classes("text-lg font-bold").style(
        f"color:{COLORS['text_heading']};")
    ui.label("The forward bookend to Prior-Quarter Review. Given the guidance you've decided and the H2 "
             "catalysts you're naming above, here is the market setup the morning after the print.").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    # 1) Guidance morning-after read — same shared engine as the Decision
    #    Engine (above) and the Markets 'Update guidance' panel.
    math_ = _guidance_math(ss)
    q2_actual = ss.get("q2_numbers", {}).get("rev") or 0
    street_q2 = round(q2_actual - math_["beat_vs_street"], 2)
    backend = guidance_engine.backend_weighting(math_["fy_implied_from_h1"], math_["ytd_rev"])
    parts = guidance_engine.morning_read_parts(
        "Q2 2026E", "FY 2026E", q2_actual, street_q2,
        round(math_["fy_implied_from_h1"], 1), math_["fy_mid"], backend)
    if parts:
        with ui.card().classes("w-full").style(
                "background:rgba(30,64,175,.06);border:1.5px solid #1E40AF;border-left:6px solid #1E40AF;"
                "border-radius:8px;margin-top:6px;"):
            ui.label("THE MORNING-AFTER READ — what the buy-side detects first").style(
                "color:#1E3A8A;font-size:var(--fs-xs);font-weight:700;letter-spacing:.04em;")
            ui.label(" ".join(parts)).style(
                f"color:{COLORS['text_heading']};font-size:var(--fs-base);line-height:1.65;font-weight:500;margin-top:4px;")

    # 2) Narrative Momentum now has its own tab (promoted out of this synthesis
    #    view) — link to it instead of re-rendering the full read here.
    ui.button("Open Narrative Momentum →",
              on_click=lambda: nav.go_to("Earnings", "Narrative Momentum")).props(
        "flat dense color=primary").style("margin-top:10px;")
    ui.label("The full narrative read — signal, guidance stance, analyst-PT direction, and the named H2 "
             "catalysts — is now its own tab.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")


def _render_script_workflow_tab():
    """Speaker-confirmation gate in front of the script workflow. Script generation is BLOCKED
    until the reporting quarter's speaker lineup is confirmed, so a stale name (e.g. a departed IR
    head) can never reach a client-facing draft, and a quarter rollover forces a re-confirm."""
    from core import speakers
    period = speakers.current_period()
    st = {"editing": False}
    box = ui.column().classes("w-full")

    def _paint():
        box.clear()
        with box:
            # Loop-readiness overview is a STATUS widget (what's ready across the whole loop) — orientation,
            # not working-page content. It buried the actual work (Set guidance / draft), so it's no longer
            # rendered here. _render_loop_readiness() is kept for a future prep/dashboard surface.
            # No configured reporting period -> nothing to gate on; render the workflow.
            if period and (not speakers.is_confirmed(period) or st["editing"]):
                def _done():
                    st["editing"] = False
                    _paint()
                _render_speaker_gate(period, on_done=_done, editing=st["editing"])
                return
            if period:
                def _edit():
                    st["editing"] = True
                    _paint()
                _render_confirmed_speaker_bar(period, on_edit=_edit)
            _render_workflow_content()

    _paint()


def _render_speaker_gate(period, on_done, editing=False):
    """The blocking confirmation card: confirm who is speaking on `period`'s call before any script
    is generated. Prefilled from the last confirmed lineup (or the registry roster on first use),
    fully editable — the mechanism for a departure like an IR head leaving, without touching the
    base config or a prior quarter's record."""
    from core import speakers
    from config.client_config import ROLE_PERMISSIONS
    # Speaker roles = the permission/login roles PLUS speaker-only roles that aren't app logins.
    # Operator (reads the pre-call disclosure / opening) and Guest (a one-off, e.g. a division head)
    # are call participants, not seats with page permissions — so they live here, not in ROLE_PERMISSIONS.
    role_opts = list(ROLE_PERMISSIONS.keys()) + ["Operator", "Guest"]
    rows = speakers.get_confirmed(period)["speakers"] if editing else speakers.default_lineup()
    rows = [dict(r) for r in rows] or [{"role": role_opts[0], "name": "", "title": "", "speaking": True}]

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid #B45309;border-left:4px solid #B45309;"):
        ui.label(f"Confirm the speaker lineup for {period}").classes("text-lg font-bold").style(
            f"color:{COLORS['text_heading']};")
        ui.label("Earnings-call lineups change quarter to quarter — departures, new execs, a guest. "
                 "Confirm who is speaking before generating this quarter's script. Prepared-remarks "
                 "speakers drive the persona canvases and the Call Opening; uncheck 'speaking' for "
                 "someone who's on the call for Q&A only.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-bottom:4px;")
        msg = ui.label("").style("color:#B91C1C;font-size:var(--fs-sm);min-height:15px;")

        @ui.refreshable
        def _rows():
            for r in rows:
                # no-wrap so the Remove button never gets pushed onto its own line (NiceGUI rows
                # wrap by default, which buried the delete control under the next speaker). Each
                # field is directly editable; Remove is an explicit, labelled, red button.
                with ui.row().classes("w-full items-center no-wrap").style("gap:8px;"):
                    ui.select(role_opts, value=r.get("role") if r.get("role") in role_opts else role_opts[0],
                              label="Role") \
                        .props("outlined dense").style("min-width:104px;") \
                        .bind_value(r, "role")
                    ui.input("Name", value=r.get("name", "")).props("outlined dense clearable") \
                        .style("flex:1;min-width:150px;").bind_value(r, "name") \
                        .tooltip("Type to rename, or clear and enter a replacement")
                    ui.input("Title", value=r.get("title", "")).props("outlined dense") \
                        .style("flex:1;min-width:150px;").bind_value(r, "title")
                    ui.switch("Speaking", value=r.get("speaking", True)).props("dense") \
                        .bind_value(r, "speaking").tooltip("Delivers prepared remarks (vs Q&A-only)")
                    ui.button("Remove", icon="person_remove",
                              on_click=lambda r=r: (rows.remove(r), _rows.refresh())) \
                        .props("flat dense color=negative").style("flex-shrink:0;") \
                        .tooltip("Remove this person from the lineup (e.g. a departure)")
        _rows()

        with ui.row().classes("w-full items-center").style("gap:8px;margin-top:6px;"):
            def _add():
                rows.append({"role": role_opts[0], "name": "", "title": "", "speaking": True})
                _rows.refresh()
            ui.button("Add speaker / replacement", icon="person_add", on_click=_add).props(
                "flat dense color=primary")
            ui.space()
            if editing:
                ui.button("Cancel", on_click=on_done).props("flat")

            def _confirm():
                if not any((r.get("name") or "").strip() for r in rows):
                    msg.set_text("Add at least one speaker."); return
                if not any(r.get("speaking") and (r.get("name") or "").strip() for r in rows):
                    msg.set_text("At least one speaker must deliver prepared remarks."); return
                speakers.confirm(period, rows)
                ui.notify(f"Speaker lineup confirmed for {period}.", type="positive")
                on_done()
            ui.button("Confirm lineup", icon="check", on_click=_confirm).props("color=primary")


def _render_confirmed_speaker_bar(period, on_edit):
    """Compact confirmed-lineup bar shown above the workflow once confirmed, with an Edit that
    re-opens the gate (e.g. to swap in a new IR head mid-transition)."""
    from core import speakers
    rec = speakers.get_confirmed(period) or {}
    spk = rec.get("speakers", [])
    talking = [s for s in spk if s.get("speaking")]
    qa_only = [s for s in spk if not s.get("speaking")]
    with ui.row().classes("w-full items-center").style(
            "gap:8px;background:rgba(21,128,61,.08);border:1px solid #15803D40;border-radius:8px;"
            "padding:6px 12px;margin-bottom:6px;"):
        ui.label(f"✓ {period} speakers confirmed").style("color:#15803D;font-size:var(--fs-sm);font-weight:700;")
        names = " · ".join(f"{s['name']} ({s['role']})" for s in talking)
        ui.label(names).style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
        if qa_only:
            ui.label("Q&A only: " + ", ".join(s["name"] for s in qa_only)).style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        ui.space()
        ui.button("Edit lineup", icon="edit", on_click=on_edit).props("flat dense").style(
            f"color:{COLORS['text_muted']};")


def _render_loop_readiness(client_id=None):
    """Per-client 'what's lighting up / what's waiting' strip for the earnings-script /
    Q&A loop — the ready inputs summarized, each still-missing input shown as a shared
    waiting_signal card naming what to provide and what it unlocks (see core.loop_readiness)."""
    from core import loop_readiness
    from page_modules_nicegui.signals import waiting_signal
    r = loop_readiness.assess(client_id)
    stages = r["stages"]
    head = (f"Loop readiness — {r['ready_required']}/{r['total_required']} inputs ready"
            + ("  ·  fully lit ✓" if r["fully_lit"] else ""))
    hclr = "#15803D" if r["fully_lit"] else "#B45309"
    with ui.expansion(head, icon="checklist", value=not r["fully_lit"]).classes("w-full").style(
            f"border:1px solid {hclr}55;border-radius:8px;margin:6px 0;"):
        ui.label("What the full earnings-script / Q&A loop needs for this client — provide a waiting input to "
                 "light up the next stage.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        ready = [s for s in stages if s["ready"]]
        if ready:
            ui.label("✓ Ready: " + "  ·  ".join(f"{s['label']} ({s['detail']})" for s in ready)).style(
                "color:#15803D;font-size:var(--fs-xs);font-weight:600;margin-top:2px;")
        for s in stages:
            if not s["ready"]:
                what = s["waiting_for"] + (" (optional — enrichment)" if s.get("optional") else "")
                waiting_signal(what, s["todo"], s["unlocks"], compact=True)
        if r["fully_lit"]:
            ui.label("Every input is in — the loop runs end to end: predict → grade → accrue → seed → "
                     "promote → trend.").style("color:#15803D;font-size:var(--fs-xs);margin-top:2px;")


def _render_workflow_content():
    ss = _load_json("script_workflow_state.json", None)
    if ss is None:
        ss = _blank_script_state()
    else:
        # Backward-compat: fill in any keys an older saved state (from the
        # earlier simplified port) might be missing.
        blank = _blank_script_state()
        for k, v in blank.items():
            ss.setdefault(k, v)
        # setdefault above only fills in a whole top-level key if it's
        # entirely absent — "reviewers" already exists in any state saved
        # before CRO became a formal reviewer (Jul 10, 2026), so it needs
        # its own backfill for just the new "CRO" sub-key.
        ss["reviewers"].setdefault("CRO", {"status": "pending", "sent": None, "received": None, "notes": ""})
        for _, key, _label in PERSONAS:
            ss["script_text"].setdefault(key, "")
            ss.setdefault("persona_notes", {}).setdefault(key, {"whats_new": "", "final_notes": ""})

    # Narration removed (title + "5-stage approval pipeline · …" description): the clickable stage cards
    # below ARE the pipeline and its status — they show it, so we don't also have to say it.
    # The stage cards below ARE the navigation now — each is clickable and drives these tab_panels —
    # so the plain tab bar that used to sit under them is redundant. Keep the ui.tabs element in the
    # DOM (the tab_panels model needs it) but hide it entirely via .hidden-tabstrip; the cards carry
    # both the status AND the "click to open" affordance. FINAL (post legal sign-off) has no tab of
    # its own — it maps to Legal Sign-Off, where the finalized-script card renders.
    with ui.tabs().classes("w-full hidden-tabstrip") as sw_tabs:
        sw1 = ui.tab("1 · CFO Numbers")
        sw2 = ui.tab("2 · IR Review")
        sw3 = ui.tab("3 · CEO+CFO+CRO Review")
        sw4 = ui.tab("4 · Consolidation")
        sw5 = ui.tab("5 · Legal Sign-Off")
    _stage_to_tab = {
        "cfo_numbers": sw1, "ir_review": sw2, "exec_review": sw3,
        "consolidate": sw4, "legal_signoff": sw5, "FINAL": sw5,
    }
    default_sw_tab = _stage_to_tab.get(ss.get("current_stage"), sw1)

    with ui.row().classes("w-full gap-2"):
        for stage in STAGES:
            status = ss["stages"][stage["id"]]["status"]
            # bc (card background) is a fixed dark green/navy for
            # complete/active regardless of which app theme (light or dark)
            # is active — config/theme_tokens.py's light theme has
            # near-black text_heading (#211D17), which is illegible against
            # that fixed dark background. label_tc/name_tc are fixed light
            # colors for exactly those two states so the card stays
            # readable no matter which theme is active; the pending state
            # keeps using the theme's own surface_bg/text_heading pair,
            # which are always coherent with each other by construction.
            if status == "complete":
                bc, tc, ico, label_tc, name_tc = "#E9F6EF", "#15803D", "", "#15803D", "#0F172A"
            elif status == "active":
                bc, tc, ico, label_tc, name_tc = "#E8EEF7", "#1E40AF", "", "#1E3A8A", "#0F172A"
            else:
                bc, tc, ico, label_tc, name_tc = COLORS["surface_bg"], COLORS["text_muted"], "", COLORS["accent_light2"], COLORS["text_heading"]
            _card = ui.card().classes("flex-1 text-center cursor-pointer click-card").style(
                f"background:{bc};border:1px solid {COLORS['border']};")
            _card.on("click", lambda _e, t=_stage_to_tab.get(stage["id"]): sw_tabs.set_value(t))
            _card.tooltip(f"Open {stage['name']}")
            with _card:
                ui.label(stage["icon"]).style("font-size:var(--fs-2xl);")
                ui.label(stage["label"]).style(f"color:{label_tc};font-size:var(--fs-xs);font-weight:bold;text-transform:uppercase;")
                ui.label(stage["name"]).classes("font-bold").style(f"color:{name_tc};font-size:var(--fs-base);")
                ui.label(f"{ico} {status.capitalize()}").style(f"color:{tc};font-size:var(--fs-sm);font-weight:600;")
    with ui.tab_panels(sw_tabs, value=default_sw_tab).classes("w-full"):
        with ui.tab_panel(sw1):
            _render_stage1(ss)
            _render_stage1b(ss)
        with ui.tab_panel(sw2):
            _render_stage2(ss)
        with ui.tab_panel(sw3):
            _render_stage3(ss)
        with ui.tab_panel(sw4):
            _render_stage4(ss)
        with ui.tab_panel(sw5):
            _render_stage5(ss)

    _render_tomorrow_setup(ss)

    if ss.get("versions"):
        ui.markdown("---")
        ui.label("Version History").classes("font-bold").style("font-size:var(--fs-md);")
        for v in reversed(ss["versions"]):
            if "version" in v:
                icon = "" if v["version"] == "FINAL" else ""
                ui.label(f"{icon} {v['version']} — {v.get('label','')} · {v.get('created','')} · {v.get('by','—')}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            else:
                # Legacy shape from the earlier simplified port
                ui.label(f"{v.get('completed','')} — {v.get('stage','')}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    ui.markdown("---")
    with ui.expansion("Reset Workflow — Start New Quarter").classes("w-full"):
        def reset():
            _save_json("script_workflow_state.json", _blank_script_state())
            ui.notify("Reset. Ready for next quarter.")
            _refresh()
        ui.button("Reset All Stages", on_click=reset).props("color=negative")


# ─────────────────────────────────────────────────────────────────────────
# Tab 2 — Consensus Tracker
# ─────────────────────────────────────────────────────────────────────────
def _default_surprises():
    return [{"quarter": "Q1 2026", "date": "2026-05-13", "rev_actual": 25.47, "rev_consensus": 23.42,
             "rev_whisper": 24.5, "eps_actual": 0.00, "eps_consensus": -0.01, "ah_move": 0.2422,
             "implied_move": 0.20, "3day_move": 0.195, "sector_3day": -0.02, "stock_pre_close": 1.28,
             "guidance_vs_embedded": "In-line", "pt_changes": 1, "pt_change_avg": 0.50,
             "notes": "Record Q1. +24.22% AH. Beat driven by ACH +25%, PayFac +23%. Stock near 52-wk low — "
                      "embedded bar was very low. Prepaid anniversary now fully reflected.",
             "pre_empt_score": 8, "call_score": 61}]


def _render_consensus_rollup():
    """Praxis Consensus — our vetted revenue consensus rolled up from the analyst models we've
    collected (median headline, robust to a rough analyst), with the street/override as a labeled
    provisional fallback, a reconciliation vs that fallback, and the list of analysts still owed a
    model. This is the working surface for keeping the street in line."""
    GREEN, RED, AMBER, MUT = "#15803D", "#B91C1C", "#B45309", COLORS["text_muted"]
    # De-dup the "which Consensus?" confusion: this is the canonical BUILD/maintain home; the
    # analyst matrix vs. guidance lives in Markets → Consensus / Guidance.
    with ui.row().classes("items-center w-full").style(
            "gap:6px;background:rgba(37,99,235,.06);border:1px solid rgba(37,99,235,.18);"
            "border-radius:8px;padding:6px 10px;margin-bottom:8px;"):
        ui.icon("tune").style(f"color:{COLORS['text_muted']};font-size:var(--fs-md);")
        ui.label("Build & maintain the Praxis consensus here.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        ui.button("See the analyst matrix in Markets → Consensus / Guidance →",
                  on_click=lambda: nav.go_to("Markets", "Consensus / Guidance")).props(
            "flat dense no-caps").style(f"color:{COLORS['accent']};font-size:var(--fs-xs);")
    cid = get_active_client_id()
    cq = (CE().get("current_quarter") or "").strip()
    period = f"{cq}E" if cq else "Q2 2026E"
    r = consensus.rolled_consensus(period, client_id=cid, include_street=True)

    def _m(v):
        return f"${v:,.1f}M" if isinstance(v, (int, float)) else "—"

    src_label = {"models": "Praxis · models", "street": "Live street",
                 "override": "IR override", "none": "—"}.get(r["source"], r["source"])
    auth = r["status"] == "authoritative"
    on_street = r["source"] == "street"
    on_override = r["source"] == "override"

    # SURFACE-FIRST: with no collected models yet, this IS the live public street consensus — a real,
    # sourced number, not a deficiency. Lead with it confidently and frame model collection as the
    # UPGRADE to an IR-vetted median (dispersion, outlier flags, drift you can manage), not a missing
    # prerequisite. See memory: surface-first-then-refine.
    ui.label("Consensus — street now, your vetted median once models are in").classes("text-lg font-bold")
    if r["source"] == "models":
        _sub = "your IR-vetted consensus from collected models; the median resists a rough analyst."
    elif on_street:
        _sub = ("live public street consensus, straight from the market feed. Collect your analysts' models to "
                "upgrade this into your own vetted median — with dispersion, outlier flags, and drift to manage.")
    else:  # override / none
        _sub = ("a curated street estimate on file. Collect your analysts' models to upgrade this into your own "
                "vetted median — with dispersion, outlier flags, and drift to manage.")
    ui.label(f"{CT('ticker')} · {period} · {_sub}").style(f"color:{MUT};font-size:var(--fs-sm);")

    if auth:
        badge_txt, badge_col, badge_bg = "AUTHORITATIVE", GREEN, "rgba(21,128,61,.12)"
    elif on_street:
        badge_txt, badge_col, badge_bg = "LIVE STREET", "#1E40AF", "rgba(30,64,175,.10)"
    elif on_override:
        badge_txt, badge_col, badge_bg = "IR OVERRIDE", AMBER, "rgba(180,83,9,.12)"
    else:
        badge_txt, badge_col, badge_bg = "PROVISIONAL", AMBER, "rgba(180,83,9,.12)"

    # ── headline card ───────────────────────────────────────────────────────
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};margin-top:6px;"):
        with ui.row().classes("w-full items-center").style("gap:12px;"):
            ui.label(_m(r["headline"])).classes("text-3xl font-bold").style(
                f"color:{COLORS['text_heading']};")
            ui.label(badge_txt).style(
                f"background:{badge_bg};color:{badge_col};font-size:var(--fs-2xs);font-weight:800;"
                "letter-spacing:.04em;padding:3px 9px;border-radius:6px;")
            ui.label(src_label).style(f"color:{MUT};font-size:var(--fs-base);")
            ui.space()
            if r["n_models"]:
                ui.label(f"{r['n_models']} of {r['n_covering']} models · {r['coverage']:.0%} coverage").style(
                    f"color:{MUT};font-size:var(--fs-sm);")
            else:
                ui.label(f"upgrade available — collect {r['n_covering']} analyst models").style(
                    f"color:#1E40AF;font-size:var(--fs-sm);font-weight:600;")
        if r["median"] is not None:
            with ui.row().classes("w-full").style("gap:26px;margin-top:8px;"):
                for lbl, val in [("Median", _m(r["median"])), ("Mean", _m(r["mean"])),
                                 ("Low", _m(r["low"])), ("High", _m(r["high"]))]:
                    with ui.column().style("gap:0;"):
                        ui.label(val).style(f"color:{COLORS['text_body']};font-weight:700;font-size:var(--fs-md);")
                        ui.label(lbl).style(f"color:{MUT};font-size:var(--fs-2xs);letter-spacing:.03em;")

    # ── reconciliation ──────────────────────────────────────────────────────
    rc = r["reconciliation"]
    if rc:
        pct = rc["ref_vs_model_pct"]
        against = {"street": "the street", "override": "the IR override"}.get(rc["ref_source"], rc["ref_source"])
        col = AMBER if abs(pct) >= 3 else MUT
        ui.label(f"Reconciliation — our median {_m(rc['model_median'])} vs {against} {_m(rc['ref'])}: "
                 f"{against} is {abs(pct):.1f}% {'above' if pct > 0 else 'below'} our models.").style(
            f"color:{col};font-size:var(--fs-base);font-weight:600;margin-top:8px;")
    elif r["fallback"]:
        fb = r["fallback"]
        extra = (f" · {fb['n']} analysts" if fb.get("n") else "") + (" · period-verified" if fb.get("verified") else "")
        ui.label(f"{'Live street' if fb['source'] == 'street' else 'IR override'} {_m(fb['value_m'])}{extra} — a real "
                 "public number today; collect your analysts' models to build your own vetted median from it.").style(
            f"color:{MUT};font-size:var(--fs-base);margin-top:8px;")

    ui.markdown("---")

    # ── per-analyst models ──────────────────────────────────────────────────
    ui.label("Analyst models").classes("font-bold").style("font-size:var(--fs-md);")
    if r["per_firm"]:
        for f in r["per_firm"]:
            dv = (f["value"] - r["median"]) / r["median"] * 100 if r["median"] else 0
            with ui.row().classes("w-full items-center").style("gap:12px;"):
                ui.label(f["firm"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);min-width:210px;")
                ui.label(_m(f["value"])).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);font-weight:600;")
                ui.label(f"{dv:+.1f}% vs median").style(f"color:{MUT};font-size:var(--fs-sm);")
                if f["is_outlier"]:
                    ui.label("OUTLIER").style(
                        f"background:rgba(180,83,9,.12);color:{AMBER};font-size:var(--fs-2xs);font-weight:700;"
                        "padding:1px 7px;border-radius:8px;").tooltip(">10% from median — kept in the math, flagged for you")
    else:
        ui.label("No models received yet for this period.").style(f"color:{MUT};font-size:var(--fs-base);")

    # ── who still owes a model (active coverage) ────────────────────────────
    received = {f["firm"] for f in r["per_firm"]}
    missing = [a for a in (C().get("analysts", []) or [])
               if a.get("covering", True) and a.get("firm") and a.get("firm") not in received]
    if missing:
        ui.markdown("---")
        ui.label("Collect these covering analysts' models to upgrade from street to your own vetted consensus:").style(
            f"color:{MUT};font-size:var(--fs-sm);")
        for a in missing:
            ui.label(f"· {a.get('firm')}" + (f" — {a.get('name')}" if a.get("name") else "")).style(
                f"color:{AMBER};font-size:var(--fs-sm);")


def _render_model_intake_tab(cid, on_saved=None, refresh_self=None):
    """Log analyst models into the consensus roll-up. Two paths:
      A) parsed from the IRconnect mailbox (inbox_queue 'model' items) — review the extracted
         numbers and confirm to integrate; and
      B) MANUAL entry — to get a client started, and for the common case of a model sent to the
         wrong person / outside the mailbox. Optional file attach for the record.
    Both write via core.consensus, so the Praxis Consensus tab reflects them immediately."""
    MUT = COLORS["text_muted"]
    ratings = ["Buy", "Hold", "Sell", "Not Rated"]
    period_keys = list((consensus.get_consensus(cid).get("period_estimates") or {}).keys())
    cq = (CE().get("current_quarter") or "").strip()
    if not period_keys:
        period_keys = [f"{cq}E" if cq else "Q2 2026E"]
    default_period = f"{cq}E" if cq and f"{cq}E" in period_keys else period_keys[0]
    firms = [a.get("firm") for a in (C().get("analysts", []) or []) if a.get("firm")]
    domain = C().get("email_domain") or "your-domain.com"

    def _norm_period(p):
        p = (p or "").strip()
        if not p:
            return default_period
        p = p if p.endswith("E") else p + "E"
        return p if p in period_keys else default_period

    ui.label("Model Intake").classes("text-lg font-bold")
    ui.label(f"Analysts send models to irconnect@{domain}; parsed emails land below for review. "
             "Use manual entry to get started, or when a model was sent to the wrong person.").style(
        f"color:{MUT};font-size:var(--fs-sm);")

    # ── A) parsed from the IRconnect mailbox ────────────────────────────────
    ui.markdown("---")
    ui.label("From IRconnect email — pending review").classes("font-bold").style("font-size:var(--fs-md);")
    pending = inbox_queue.list_pending_items(category="model", client_id=cid)
    if not pending:
        ui.label("Nothing pending. Parsed models from the IRconnect mailbox appear here once it's "
                 "connected.").style(f"color:{MUT};font-size:var(--fs-base);")
    for item in pending:
        ex = item.get("extracted") or {}
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            ui.label(f"{item.get('firm') or item.get('contact') or 'Unknown sender'} · "
                     f"{item.get('subject', '(no subject)')}").classes("font-bold").style(
                f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
            ui.label(f"Received {item.get('received_at', '')}"
                     + (f" · {item.get('filename')}" if item.get("filename") else "")).style(
                f"color:{MUT};font-size:var(--fs-xs);")
            with ui.row().classes("w-full").style("gap:8px;flex-wrap:wrap;margin-top:4px;"):
                q_firm = ui.input("Firm", value=item.get("firm") or "").props("outlined dense").style("min-width:160px;")
                q_period = ui.select(period_keys, value=_norm_period(ex.get("period")), label="Period").props("outlined dense").style("min-width:120px;")
                q_rev = ui.number("Rev ($M)", value=ex.get("revenue_est"), step=0.1).props("outlined dense").style("width:110px;")
                q_eps = ui.number("EPS ($)", value=ex.get("eps_est"), step=0.01).props("outlined dense").style("width:100px;")
                q_ebitda = ui.number("EBITDA ($M)", value=ex.get("ebitda_est"), step=0.1).props("outlined dense").style("width:120px;")
                q_pt = ui.number("PT ($)", value=ex.get("price_target"), step=0.25).props("outlined dense").style("width:95px;")
                q_rating = ui.select(ratings, value=ex.get("rating") if ex.get("rating") in ratings else "Not Rated", label="Rating").props("outlined dense").style("min-width:110px;")
            with ui.row().style("gap:8px;"):
                def _confirm(it=item, qf=q_firm, qp=q_period, qr=q_rev, qe=q_eps, qb=q_ebitda, qt=q_pt, qra=q_rating):
                    firm = (qf.value or "").strip()
                    if not firm:
                        ui.notify("Firm is required to integrate.", type="warning"); return
                    consensus.confirm_model_review(it["id"], qp.value, firm, rating=qra.value,
                                                   price_target=qt.value, eps_est=qe.value,
                                                   revenue_est=qr.value, ebitda_est=qb.value, client_id=cid)
                    ui.notify(f"Integrated {firm} model for {qp.value}.", type="positive")
                    if on_saved:
                        on_saved()
                    if refresh_self:
                        refresh_self()
                ui.button("Confirm & integrate", on_click=_confirm).props("color=primary dense")

                def _dismiss(it=item):
                    inbox_queue.dismiss_item(it["id"], client_id=cid)
                    ui.notify("Dismissed.", type="info")
                    if refresh_self:
                        refresh_self()
                ui.button("Dismiss", on_click=_dismiss).props("flat dense")

    # ── B) manual entry ─────────────────────────────────────────────────────
    ui.markdown("---")
    ui.label("Manual model entry").classes("font-bold").style("font-size:var(--fs-md);")
    ui.label("To get started, or for a model that arrived outside the IRconnect mailbox.").style(
        f"color:{MUT};font-size:var(--fs-sm);")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        with ui.row().classes("w-full").style("gap:8px;flex-wrap:wrap;"):
            firm_in = ui.select(firms, label="Analyst / firm", with_input=True,
                                new_value_mode="add-unique").props("outlined dense").style("min-width:200px;")
            period_in = ui.select(period_keys, value=default_period, label="Period").props("outlined dense").style("min-width:120px;")
            rev_in = ui.number("Revenue Est ($M)", value=None, step=0.1).props("outlined dense").style("width:150px;")
            eps_in = ui.number("EPS Est ($)", value=None, step=0.01).props("outlined dense").style("width:120px;")
            ebitda_in = ui.number("EBITDA Est ($M)", value=None, step=0.1).props("outlined dense").style("width:150px;")
            pt_in = ui.number("Price Target ($)", value=None, step=0.25).props("outlined dense").style("width:130px;")
            rating_in = ui.select(ratings, value="Not Rated", label="Rating").props("outlined dense").style("min-width:120px;")

        def _on_upload(e):
            from core import documents
            try:
                data = e.content.read()
            except Exception:
                data = e.content
            firm = (firm_in.value or "").strip() or "Unknown"
            documents.save_document(contact=firm, firm=firm, doc_type="model", filename=e.name,
                                    file_bytes=data, source="manual_intake", client_id=cid)
            ui.notify(f"Attached {e.name}.", type="positive")
        ui.upload(on_upload=_on_upload, auto_upload=True).props(
            "accept='.xlsx,.xls,.xlsm,.csv,.pdf' flat max-files=1").classes("w-full").style("max-width:340px;")

        msg = ui.label("").style("color:#B91C1C;font-size:var(--fs-sm);min-height:16px;")

        def _save():
            firm = (firm_in.value or "").strip()
            if not firm:
                msg.set_text("Pick or type the analyst / firm."); return
            if all(v is None for v in (rev_in.value, eps_in.value, ebitda_in.value, pt_in.value)):
                msg.set_text("Enter at least one estimate (revenue, EPS, EBITDA, or PT)."); return
            consensus.update_estimate(period_in.value, firm, rating=rating_in.value,
                                      price_target=pt_in.value, eps_est=eps_in.value,
                                      revenue_est=rev_in.value, ebitda_est=ebitda_in.value,
                                      source="manual_intake", client_id=cid)
            ui.notify(f"Logged {firm} model for {period_in.value}.", type="positive", timeout=5000)
            firm_in.value = None
            for f in (rev_in, eps_in, ebitda_in, pt_in):
                f.value = None
            msg.set_text("")
            if on_saved:
                on_saved()
        ui.button("Log model", icon="save", on_click=_save).props("color=primary").style("margin-top:6px;")


def _render_surprise_tracker_tab():
    surprises = _load_json("earnings_surprise_log.json", None)
    if surprises is None:
        # _default_surprises() is a hardcoded USIO Q1 beat ($25.47 rev, +24.22% AH). Two bugs it
        # used to cause: (1) it was shown for ANY tenant, so SARO displayed USIO's earnings
        # history; (2) it was PERSISTED on first view, contaminating the real store with demo data.
        # Now: only USIO gets the demo, and it is NOT written — an empty history stays empty until a
        # real quarter is logged via "Log Quarter".
        surprises = _default_surprises() if get_active_client_id() == "usio" else []

    from page_modules_nicegui.signals import capability_banner
    capability_banner(
        "Build the number you're judged against",
        "Collect your covering analysts' models here; the platform composes your consensus and "
        "grades every quarter's actual against it — the estimate you own, not a licensed feed.",
        tag="Proprietary consensus")
    ui.label("Actual vs consensus vs embedded expectation · Guidance credibility database").style(
        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-top:8px;")

    _cid = get_active_client_id()

    @ui.refreshable
    def _praxis_panel():
        _render_consensus_rollup()

    @ui.refreshable
    def _intake_panel():
        _render_model_intake_tab(_cid, on_saved=_praxis_panel.refresh, refresh_self=_intake_panel.refresh)

    with ui.tabs().classes("w-full") as es_tabs:
        e0 = ui.tab("Praxis Consensus")
        eI = ui.tab("Model Intake")
        e1 = ui.tab("Beat/Miss History")
        e2 = ui.tab("Log Quarter")
        e3 = ui.tab("Pre-Call Assessment")
    with ui.tab_panels(es_tabs, value=e0).classes("w-full"):
        with ui.tab_panel(e0):
            _praxis_panel()
        with ui.tab_panel(eI):
            _intake_panel()
        with ui.tab_panel(e1):
            if surprises:
                df = pd.DataFrame(surprises)
                avg_surp = ((df["rev_actual"] - df["rev_consensus"]) / df["rev_consensus"] * 100).mean()
                beat_q = int((df["rev_actual"] > df["rev_consensus"]).sum())
                with ui.row().classes("w-full gap-3"):
                    for label, value in [
                        ("Quarters tracked", str(len(df))),
                        ("Avg revenue beat", f"+{avg_surp:.1f}%"),
                        ("Avg AH move", f"{df['ah_move'].mean()*100:+.1f}%"),
                        ("Beat quarters", f"{beat_q}/{len(df)}"),
                    ]:
                        with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                            ui.label(value).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
                            ui.label(label).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

                ui.markdown("---")
                for row in surprises:
                    surp = (row["rev_actual"] - row["rev_consensus"]) / row["rev_consensus"] * 100
                    whisper = row.get("rev_whisper", row["rev_consensus"])
                    wh_s = (row["rev_actual"] - whisper) / whisper * 100 if whisper else 0
                    ah = row["ah_move"] * 100
                    beat = surp > 0
                    with ui.card().classes("w-full").style(
                            f"background:{'rgba(74,222,128,.08)' if beat else 'rgba(239,68,68,.08)'};border:1px solid {COLORS['border']};"):
                        with ui.row().classes("w-full justify-between"):
                            ui.label(f"{row['quarter']} · {row['date']}").classes("font-bold").style(f"color:{COLORS['accent_light']};")
                            ui.label("BEAT" if beat else "MISS").style(f"color:{'#15803D' if beat else '#B91C1C'};font-weight:bold;")
                        with ui.row().classes("w-full gap-4"):
                            ui.label(f"Actual: ${row['rev_actual']}M").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                            ui.label(f"vs Consensus: {surp:+.1f}%").style(f"color:{'#15803D' if surp>0 else '#B91C1C'};font-size:var(--fs-sm);")
                            ui.label(f"vs Whisper: {wh_s:+.1f}%").style(f"color:{'#15803D' if wh_s>0 else '#B91C1C'};font-size:var(--fs-sm);")
                            ui.label(f"AH Move: {ah:+.1f}%").style(f"color:{'#15803D' if ah>0 else '#B91C1C'};font-size:var(--fs-sm);")
                            ui.label(f"Implied ±{row['implied_move']*100:.1f}%").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                        ui.label(f"Guidance vs embedded: {row.get('guidance_vs_embedded','—')} · "
                                 f"PT changes: {row.get('pt_changes',0)} · Call score: {row.get('call_score','—')}/100").style(
                            f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                        if row.get("notes"):
                            ui.label(row["notes"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;")

                ui.markdown("---")
                ui.label("Guidance Credibility").classes("font-bold").style("font-size:var(--fs-md);")
                for row in surprises:
                    gve = row.get("guidance_vs_embedded", "—")
                    excess = (row["ah_move"] - row["implied_move"]) * 100
                    icon = "" if gve in ["Beat", "Above"] else "" if gve == "In-line" else ""
                    ui.label(f"{icon} {row['quarter']}: Guidance {gve} embedded · AH "
                             f"{'exceeded' if excess>0 else 'undershot'} implied by {abs(excess):.1f}pp").style(
                        f"color:{COLORS['text_body']};font-size:var(--fs-base);")
            else:
                ui.label("No quarters logged yet.").style(f"color:{COLORS['text_muted']};")

        with ui.tab_panel(e2):
            def _scol():
                return ui.column().classes("flex-1 gap-2").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                    "border-radius:10px;padding:14px 16px;")

            def _sh(s):
                return ui.label(s).classes("font-bold").style(
                    f"color:{COLORS['accent_light']};font-size:var(--fs-sm);")

            with ui.row().classes("w-full gap-4 items-stretch"):
                with _scol():
                    _sh("QUARTER & SETUP")
                    s_q = ui.input("Quarter", placeholder="Q2 2026").props("outlined dense").classes("w-full")
                    s_dt = ui.input("Date (YYYY-MM-DD)", value=CE().get("earnings_date", "")).props("outlined dense").classes("w-full")
                    s_pc = ui.number("Pre-earnings close ($)", value=0.0, step=0.01).props("outlined dense").classes("w-full")
                    s_imp = ui.number("Implied move %", value=0.0, step=0.5).props("outlined dense").classes("w-full")
                with _scol():
                    _sh("RESULTS vs STREET")
                    s_ra = ui.number("Actual revenue ($M)", value=0.0, step=0.1).props("outlined dense").classes("w-full")
                    s_rc = ui.number("Consensus ($M)", value=25.1, step=0.1).props("outlined dense").classes("w-full")
                    s_rw = ui.number("Whisper ($M)", value=24.5, step=0.1).props("outlined dense").classes("w-full")
                    s_ea = ui.number("Actual EPS ($)", value=0.0, step=0.01).props("outlined dense").classes("w-full")
                    s_ec = ui.number("EPS consensus ($)", value=0.01, step=0.01).props("outlined dense").classes("w-full")
                with _scol():
                    _sh("STOCK REACTION")
                    s_ah = ui.number("AH move (%)", value=0.0, step=0.1).props("outlined dense").classes("w-full")
                    s_3d = ui.number("3-day move (%)", value=0.0, step=0.1).props("outlined dense").classes("w-full")
                    s_ptn = ui.number("PT changes", value=0).props("outlined dense").classes("w-full")
                    s_pta = ui.number("Avg PT change ($)", value=0.0, step=0.25).props("outlined dense").classes("w-full")
            with ui.row().classes("w-full gap-4"):
                s_gve = ui.select(["Beat", "In-line", "Below"], value="In-line").classes("flex-1").props("outlined dense label='Guidance vs embedded'")
                s_pre = ui.number("Pre-empt score (0-12)", value=0, min=0, max=12).props("outlined dense").classes("flex-1")
                s_cs = ui.number("Call score (0-100)", value=0, min=0, max=100).props("outlined dense").classes("flex-1")
            s_notes = ui.textarea("Notes").props("outlined autogrow").classes("w-full")

            def log_quarter():
                if not s_q.value:
                    ui.notify("Quarter is required.", type="warning")
                    return
                # Start from real history only. Falling back to _default_surprises() here would
                # prepend USIO's fabricated Q1 beat to a non-USIO client's first real logged
                # quarter — the same demo-leak, now written permanently.
                data = _load_json("earnings_surprise_log.json", None) or []
                data.append({
                    "quarter": s_q.value, "date": s_dt.value, "rev_actual": s_ra.value, "rev_consensus": s_rc.value,
                    "rev_whisper": s_rw.value, "eps_actual": s_ea.value, "eps_consensus": s_ec.value,
                    "ah_move": (s_ah.value or 0) / 100, "implied_move": (s_imp.value or 0) / 100,
                    "3day_move": (s_3d.value or 0) / 100, "stock_pre_close": s_pc.value,
                    "guidance_vs_embedded": s_gve.value, "pt_changes": s_ptn.value, "pt_change_avg": s_pta.value,
                    "notes": s_notes.value, "pre_empt_score": s_pre.value, "call_score": s_cs.value,
                })
                _save_json("earnings_surprise_log.json", data)
                ui.notify(f"{s_q.value} logged.")
                _refresh()

            ui.button("Log Quarter", on_click=log_quarter).props("color=primary")

        with ui.tab_panel(e3):
            ui.label(f"Pre-Call Assessment — {CE().get('current_quarter','')}").classes("font-bold")
            ui.label(f"Fill BEFORE {CE().get('earnings_date','')} earnings. Captures the embedded expectation for post-call scoring.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

            # ── The bar, live. Every field here used to be wrong in a way that only
            # showed up on the morning of the call:
            #   * "Street consensus" read CT('q2_consensus_rev') — a HARDCODED config
            #     constant of $25.1M. The real street is $23.67M from the market feed.
            #   * "Guidance midpoint" read get_seed_consensus() DIRECTLY, bypassing the
            #     period_guidance.json override. Invisible while the override matched the
            #     seed; the moment the CFO revises guidance, this panel keeps the old number
            #     while every other surface updates.
            #   * The comparison note was the literal string "-$0.6M below street" — which
            #     is the demo framing. On real numbers the guide is ABOVE the street, so the
            #     panel asserted the exact inverse of the truth, right before the call.
            #   * The period was hardcoded "Q2 2026E" and would silently break at Q3.
            _period = CE().get("current_quarter") or ""
            _period_key = _period if _period.endswith("E") else f"{_period}E"
            _cons = consensus.get_consensus(get_active_client_id())
            _guide = (_cons.get("period_guidance", {}) or {}).get(_period_key, {}) or {}
            guidance_rev = _guide.get("Revenue Est ($M)")

            _street = None
            try:
                _fin = CF()
                _street = market_data.street_for_quarter(
                    CT("ticker"),
                    fy_revenue_actual=_fin.get("fy_revenue") or 85.4,
                    q_year_ago_actual=_fin.get("q_year_ago_rev") or 19.90)
            except Exception:
                _street = None
            _st_ok = bool(_street and _street.get("verified") and _street.get("avg_m") is not None)

            if _st_ok and guidance_rev is not None:
                _gap = guidance_rev - _street["avg_m"]
                _above_all = _street.get("high_m") is not None and guidance_rev > _street["high_m"]
                _note = (f"${abs(_gap):.2f}M {'ABOVE' if _gap > 0 else 'below'} street"
                         + (" — above EVERY published estimate" if _above_all else ""))
                _risk = ("LOW" if _above_all else "MEDIUM" if _gap > 0 else "HIGH")
                _risk_note = ("delivering the guide beats the whole street"
                              if _above_all else
                              "we can hit the guide and still miss the street" if _gap < 0 else
                              "guide sits above the street mean")
            else:
                _note, _risk, _risk_note = "street not sourced", "—", "market feed unavailable"

            with ui.row().classes("w-full gap-3"):
                _pc_metric("Street consensus",
                           f"${_street['avg_m']:.2f}M" if _st_ok else "—",
                           f"mean of {_street['n']} analysts · market feed" if _st_ok
                           else "not sourced — no beat bar shown")
                _pc_metric("Guidance midpoint",
                           f"${guidance_rev}M" if guidance_rev is not None else "—", _note)
                _pc_metric("Bar risk", _risk, _risk_note)
            if _st_ok:
                ui.label(f"Street range ${_street['low_m']:.2f}–{_street['high_m']:.2f}M. Street and "
                         f"guidance are both live — the street from the market feed with its period "
                         f"mapping reconciled against filed actuals, the guidance from the CFO's "
                         f"decision. Neither is a stored constant.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

            precall = _load_json("q2_precall.json", {})
            with ui.row().classes("w-full gap-4"):
                pc_imp = ui.number("Options implied move %", value=precall.get("implied", 0.0), step=0.5).props("outlined dense").classes("flex-1")
                pc_wh = ui.number("Whisper ($M)", value=precall.get("whisper", 24.5), step=0.1).props("outlined dense").classes("flex-1")
                pc_30d = ui.number(f"{CT('ticker')} 30d vs FINX (%)", value=precall.get("30d_sector", 0.0), step=0.5).props("outlined dense").classes("flex-1")
                pc_si = ui.number("Short interest % float", value=precall.get("short", 0.02), step=0.01).props("outlined dense").classes("flex-1")
            pc_notes = ui.textarea("Positioning notes", value=precall.get("notes", "")).props("outlined autogrow").classes("w-full")

            def save_precall():
                data = {"implied": pc_imp.value, "whisper": pc_wh.value, "30d_sector": pc_30d.value,
                        "short": pc_si.value, "notes": pc_notes.value, "saved": datetime.now().strftime("%Y-%m-%d %H:%M")}
                _save_json("q2_precall.json", data)
                ui.notify("Saved. Compare to actuals after earnings.")
                _refresh()

            ui.button("Save Pre-Call Assessment", on_click=save_precall).props("color=primary")
            if precall:
                ui.label(f"Pre-call logged {precall.get('saved','')} · Implied ±{precall.get('implied',0):.1f}% · "
                         f"Whisper ${precall.get('whisper',0):.1f}M · 30d vs sector {precall.get('30d_sector',0):+.1f}%").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")


def _pc_metric(label, value, sub):
    with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(str(value)).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);font-weight:600;")
        ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")


# ─────────────────────────────────────────────────────────────────────────
# Tab 3 — Call Transcripts
#
# ChorusCall (the vendor USIO's calls are hosted on) has no public API, so
# there's no automated fetch here — a user downloads/exports the PDF (or
# copies the text) from ChorusCall and brings it in below. See
# core/transcripts.py's module docstring for the full architecture: one
# transcript per quarter, PDF text extraction via pypdf, AI summary/key
# quotes/Q&A-risk-topics/guidance-language via the Claude API (same
# urllib.request + core.security.get_anthropic_api_key pattern as this
# page's own script-drafting feature above). Once summarized, a
# transcript's Q&A risk topics feed core/risk_scorecard.py's "Q&A Risk
# Topics" indicator on the Markets page automatically — see that module.
# ─────────────────────────────────────────────────────────────────────────
def _render_transcripts_tab():
    ui.label("Call Transcripts").classes("text-lg font-bold")
    ui.label(
        "Archive of ingested earnings call transcripts — full-text searchable, with an AI summary, key quotes, "
        "guidance language, and flagged Q&A risk topics per call. ChorusCall has no public API, so bring the PDF "
        "or pasted text in by hand below; that Q&A risk read then feeds the Markets → IR Risk Dashboard scorecard."
    ).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

    ui.markdown("---")
    with ui.expansion("Ingest a transcript", value=True).classes("w-full"):
        with ui.row().classes("w-full gap-4"):
            t_quarter = ui.input("Quarter", placeholder="Q1 2026", value=CE().get("current_quarter", "")).props("outlined dense").classes("flex-1")
            t_date = ui.input("Call date (YYYY-MM-DD)").props("outlined dense").classes("flex-1")
        ui.label("Upload the PDF exported from ChorusCall:").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);margin-top:6px;")
        pdf_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        pasted_text_holder = {"text": None, "filename": None}

        async def handle_pdf_upload(e):
            pdf_status.text = "Extracting text…"
            content = await e.file.read()
            extracted = transcripts.extract_text_from_pdf(content)
            if extracted:
                pasted_text_holder["text"] = extracted
                pasted_text_holder["filename"] = e.file.name
                pdf_status.text = f"Extracted {len(extracted.split()):,} words from {e.file.name}. Click Ingest below."
                pdf_status.style("color:#15803D;font-size:var(--fs-sm);")
            else:
                pdf_status.text = ("Couldn't extract text from that PDF (it may be scanned/image-only). "
                                    "Paste the transcript text below instead.")
                pdf_status.style("color:#B45309;font-size:var(--fs-sm);")

        ui.upload(on_upload=handle_pdf_upload, auto_upload=True).props("accept=.pdf").classes("w-full")

        ui.label("...or paste the transcript text directly:").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);margin-top:6px;")
        t_paste = ui.textarea(placeholder="Paste the full call transcript text here").classes("w-full").props("rows=6 outlined")

        def ingest():
            if not t_quarter.value:
                ui.notify("Quarter is required.", type="warning")
                return
            text = (t_paste.value or "").strip() or pasted_text_holder["text"]
            if not text:
                ui.notify("Upload a PDF or paste the transcript text first.", type="warning")
                return
            transcripts.ingest_transcript(
                text, t_quarter.value, call_date=t_date.value or None,
                source="upload", source_filename=pasted_text_holder["filename"],
            )
            activity_log.log_event("transcript_ingested", entity=t_quarter.value, word_count=len(text.split()))
            ui.notify(f"{t_quarter.value} transcript ingested ({len(text.split()):,} words). "
                      f"Click Generate AI Summary below to analyze it.")
            _refresh()

        ui.button("Ingest Transcript", on_click=ingest).props("color=primary").style("margin-top:8px;")

    ui.markdown("---")
    ui.label("Search across all calls").classes("font-bold").style("font-size:var(--fs-md);")
    with ui.row().classes("w-full gap-2"):
        search_input = ui.input(placeholder="e.g. margin, PayFac, guidance").props("outlined dense").classes("flex-1")
        search_results = ui.column().classes("w-full")

        def do_search():
            search_results.clear()
            hits = transcripts.search_transcripts(search_input.value)
            with search_results:
                if not search_input.value:
                    return
                if not hits:
                    ui.label("No matches.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                for h in hits:
                    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                        ui.label(f"{h['quarter']} ({h['match_count']} match{'es' if h['match_count'] != 1 else ''})").classes("font-bold").style(f"color:{COLORS['accent_light']};")
                        for snip in h["snippets"]:
                            ui.label(snip).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;")

        search_input.on("keydown.enter", do_search)
        ui.button("Search", on_click=do_search).props("dense")

    ui.markdown("---")
    ui.label("Ingested transcripts").classes("font-bold").style("font-size:var(--fs-md);")
    records = transcripts.list_transcripts()
    if not records:
        ui.label("No transcripts ingested yet — use the form above.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        return

    for rec in records:
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label(f"{rec['quarter']} · {rec.get('call_date') or 'date not set'}").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                    ui.label(f"{rec['word_count']:,} words · uploaded {rec['uploaded_at'][:16].replace('T',' ')}"
                              + (f" · {rec['source_filename']}" if rec.get("source_filename") else "")).style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                with ui.row().classes("gap-2"):
                    def delete_this(q=rec["quarter"]):
                        transcripts.delete_transcript(q)
                        ui.notify(f"{q} transcript deleted.")
                        _refresh()
                    ui.button("", on_click=delete_this).props("flat dense")

            if not rec.get("ai_summary"):
                summary_area = ui.column().classes("w-full")

                async def generate_summary(q=rec["quarter"], area=summary_area):
                    with area:
                        area.clear()
                        ui.label("Generating AI summary…").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                    result = transcripts.summarize_transcript(q)
                    area.clear()
                    with area:
                        if result:
                            ui.notify(f"{q} summarized.")
                            activity_log.log_event("transcript_summarized", entity=q)
                            _refresh()
                        else:
                            ui.label(
                                "Couldn't generate a summary — check that ANTHROPIC_API_KEY is set in .env, "
                                "and that this machine has network access to api.anthropic.com. Try again, or "
                                "review the transcript manually."
                            ).style("color:#B45309;font-size:var(--fs-sm);")

                ui.button("Generate AI Summary", on_click=generate_summary).props("flat dense").style("margin-top:6px;")
            else:
                ui.markdown("---")
                ui.label(rec["ai_summary"]).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")

                key_quotes = rec.get("key_quotes") or []
                if key_quotes:
                    ui.label("Key quotes").classes("font-bold").style("font-size:var(--fs-sm);margin-top:6px;")
                    for kq in key_quotes:
                        ui.label(f"“{kq.get('quote','')}” — {kq.get('speaker','')}").style(
                            f"color:{COLORS['text_muted']};font-size:var(--fs-sm);font-style:italic;")

                guidance = rec.get("guidance_language") or []
                if guidance:
                    ui.label("Guidance language").classes("font-bold").style("font-size:var(--fs-sm);margin-top:6px;")
                    for g in guidance:
                        ui.label(f"• {g}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")

                topics = rec.get("qa_risk_topics") or []
                if topics:
                    ui.label("Q&A risk topics").classes("font-bold").style("font-size:var(--fs-sm);margin-top:6px;")
                    sev_color = {"HIGH": "#B91C1C", "MEDIUM": "#B45309", "LOW": "#64748B"}
                    for t in topics:
                        clr = sev_color.get(t.get("severity"), "#64748B")
                        ui.label(f"{t.get('severity','?')} · {t.get('topic','')} — {t.get('why','')}").style(f"color:{clr};font-size:var(--fs-sm);")
                else:
                    ui.label("No Q&A risk topics flagged by AI review.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

                ui.label(f"Summarized {rec['summarized_at'][:16].replace('T',' ') if rec.get('summarized_at') else ''}").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:4px;")

                rerun_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

                async def rerun_summary(q=rec["quarter"], status=rerun_status):
                    status.text = "Regenerating…"
                    result = transcripts.summarize_transcript(q)
                    if result:
                        activity_log.log_event("transcript_summarized", entity=q)
                        ui.notify(f"{q} summary regenerated.")
                        _refresh()
                    else:
                        status.text = ("Couldn't regenerate — check that ANTHROPIC_API_KEY is set in .env "
                                        "and this machine can reach api.anthropic.com.")
                        status.style("color:#B45309;font-size:var(--fs-sm);")

                ui.button("Re-run AI Summary", on_click=rerun_summary).props("flat dense")
