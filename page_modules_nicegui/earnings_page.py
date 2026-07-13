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

from config.client_config import C, CE, CF, CGP, CI, CT, get_active_client_id
from config.theme_tokens import ACTIVE as COLORS
from core import activity_log, db, inbox_queue, transcripts
from core.security import get_anthropic_api_key
from data.seed.consensus_estimates import get_seed_consensus
from page_modules_nicegui import nav

STAGES = [
    {"id": "cfo_numbers", "label": "Stage 1", "name": "CFO Numbers In", "icon": "📥"},
    {"id": "ir_review", "label": "Stage 2", "name": "IR Review", "icon": "✏️"},
    {"id": "exec_review", "label": "Stage 3", "name": "CFO+CEO+CRO Review", "icon": "👔"},
    {"id": "consolidate", "label": "Stage 4", "name": "Consolidation", "icon": "🔀"},
    {"id": "legal_signoff", "label": "Stage 5", "name": "Legal Sign-Off", "icon": "⚖️"},
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
    ("Business Review", 12.0, 10.0, "#F59E0B", "Ran 2 min over — PayFac detail was dense"),
    ("CFO Financial Review", 9.5, 10.0, "#4ADE80", "Under budget — well-structured"),
    ("Guidance & Outlook", 4.0, 4.0, "#4ADE80", "Exactly on — Louis was disciplined"),
    ("Q&A Session", 40.0, 35.0, "#F87171", "Ran 5 min over — interest income bridge took 3 questions"),
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
        return f"~{est_min:.1f} min ({words} words) — running long vs. the ~{hist:.1f} min historical norm", "#F87171"
    if delta < -hist * 0.15:
        return f"~{est_min:.1f} min ({words} words) — shorter than the ~{hist:.1f} min historical norm", "#60A5FA"
    return f"~{est_min:.1f} min ({words} words) — on pace vs. the ~{hist:.1f} min historical norm", "#4ADE80"


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
    {"priority": "CRITICAL", "clr": "#EF4444", "icon": "🔴", "persona_role": "CFO",
     "q1_finding": "Interest income — NOT pre-empted · 3 analyst questions in Q1 Q&A",
     "action": "Write interest income bridge in CFO section",
     "where": "Script Generation → CFO Financials", "impact": "Eliminates ~3 questions from covering analysts"},
    {"priority": "IMPROVE", "clr": "#F59E0B", "icon": "🟠", "persona_role": "CRO",
     "q1_finding": "Business Review ran 2 min over at 12 min · PayFac over-narrated",
     "action": "Cap Business Operations section at 90 sec on PayFac · add H2 margin pre-emption",
     "where": "Script Generation → Business Operations", "impact": "Reclaims 2 min for margin expansion narrative analysts missed"},
    {"priority": "NEW", "clr": "#60A5FA", "icon": "💡", "persona_role": None,
     "q1_finding": "No Q&A prep section existed in Q1 · 3 off-script questions",
     "action": "Build analyst-specific Q&A prep",
     "where": "Script Generation → Q&A Prep", "impact": "Pre-empts analysts on interest income and margin mix"},
    {"priority": "KEEP", "clr": "#4ADE80", "icon": "🟢", "persona_role": "CEO",
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
PERSONAS = [
    ("IR", "ir_open", "IR Opening"),
    ("CFO", "cfo_fin", "CFO Financial Review"),
    ("CRO", "cro_ops", "Business Operations"),
    ("CEO", "ceo_narrative", "CEO Narrative + Guidance"),
]

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


def _call_opening_text(ss):
    """Returns (operator_line, welcome_line, fls_line) — the three fixed
    paragraphs that open every call, templated from client config (ticker/
    company name/quarter/IR contact/exec roster) rather than hardcoded
    per-quarter like the original demo's f-strings were."""
    ticker = CT("ticker", "")
    company = CT("name", ticker) or ticker
    quarter = CE().get("current_quarter", "this quarter")
    ir = CI()
    execs = C().get("executives", {})

    operator_line = (
        f"Hello, and welcome to the {company} {quarter} Earnings Conference Call. All participants will "
        f"be in a listen-only mode. After today's presentation, there will be an opportunity to ask "
        f"questions. Please note today's event is being recorded. Now, I would like to turn the "
        f"conference over to your host, {ir.get('name', 'the host')}. Please go ahead."
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

    return operator_line, welcome_line, _CALL_OPENING_FLS_TEXT


def _render_call_opening(ss):
    """Locked, read-only Call Opening card — see the module-level comment
    above _CALL_OPENING_FLS_TEXT for why this isn't an editable draft."""
    operator_line, welcome_line, fls_line = _call_opening_text(ss)
    ir = CI()
    with ui.card().classes("w-full").style(
            "background:rgba(248,113,113,.06);border:2px solid #F87171;border-radius:8px;"
            "padding:12px 14px;margin-bottom:12px;"):
        ui.label("🔒 Call Opening — Operator & Reg FD / Safe Harbor Reading").classes("font-bold").style(
            "color:#F87171;font-size:13px;")
        ui.label("Legal-approved, reads verbatim — not an editable AI draft like the sections below. Always "
                  "included at the very start of the assembled Full Script and every download.").style(
            f"color:{COLORS['text_muted']};font-size:11px;margin-bottom:8px;")

        ui.label("OPERATOR (reads verbatim, do not edit):").classes("font-bold").style(
            "color:#FCA5A5;font-size:11px;margin-top:6px;")
        ui.label(operator_line).style(f"color:{COLORS['text_body']};font-size:12.5px;")

        ui.label(f"{ir.get('name','IR')} — Welcome & Participants:").classes("font-bold").style(
            "color:#FCA5A5;font-size:11px;margin-top:8px;")
        ui.label(welcome_line).style(f"color:{COLORS['text_body']};font-size:12.5px;")

        ui.label("Forward-Looking Statements / Safe Harbor (DO NOT EDIT — Legal-approved language, "
                  "verbatim from prior calls):").classes("font-bold").style(
            "color:#FCA5A5;font-size:11px;margin-top:8px;")
        ui.label(fls_line).style(f"color:{COLORS['text_body']};font-size:12.5px;")
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
        "tags": ["⚠️ Interest income decline was NOT pre-empted last quarter — "
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
        "tags": ["⚠️ Everything above must be disclosed again this quarter, or explicitly "
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
    delta = (n.get("rev", 0) or 0) - (CT("q2_consensus_rev", 0) or 0)
    if delta > band:
        return {"bucket": "beat", "label": f"✅ BEAT +${delta:.2f}M vs Street", "delta": delta}
    if delta < -band:
        return {"bucket": "miss", "label": f"⚠️ MISS ${delta:.2f}M vs Street", "delta": delta}
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
    out = {"IR": {"name": ir.get("name", "IR Contact"), "email": ir.get("email", "")}}
    for role in ("CFO", "CEO", "CRO", "Legal"):
        e = execs.get(role)
        out[role] = e if e else {"name": f"— {role} not configured —", "email": ""}
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
        # click, so the "✅ Saved ..." confirmation means what it says.
        "full_script_override": "",
        "full_script_override_saved_at": None,
        "first_pass_complete": None,
    }


def render_earnings_page():
    earnings = CE()
    ui.label(f"Script Generation · {earnings.get('current_quarter','')} · "
             f"{earnings.get('earnings_date','')} {earnings.get('call_time','')}").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    # Deep-link from elsewhere in the app — consumed once per page visit,
    # same nav.highlights pattern markets_page.py uses for its Today ->
    # Markets analyst jump. "transcripts" is set by the Prior Qtr Review
    # tab's "Go to Call Transcripts" button; "script" is set by Today's
    # "Open Script Generation" button (added after that button was found
    # to silently land on the default Prior Qtr Review tab instead of
    # actually opening Script Generation — see chat from Jul 10, 2026).
    _earnings_tab_target = nav.highlights.pop("earnings_tab", None)
    jump_to_transcripts = _earnings_tab_target == "transcripts"
    jump_to_script = _earnings_tab_target == "script"

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("📊 Prior Qtr Review")
        t2 = ui.tab("📝 Script Generation")
        t3 = ui.tab("🎯 Consensus Tracker")
        t4 = ui.tab("🎙️ Call Transcripts")

    # Lazy tab loading — all 4 tabs used to build eagerly on every page
    # load (this page's Script Generation tab alone builds a 15-field intake
    # form plus 5 nested sub-stage panels), which was blocking the event
    # loop long enough to trip NiceGUI's "Connection lost, trying to
    # reconnect" websocket timeout the moment someone opened this page.
    # Same fix already applied to investors_page.py's render_investors_page
    # — only the default-open tab renders immediately; the rest render a
    # spinner and build for real the first time they're actually selected.
    default_tab = t4 if jump_to_transcripts else (t2 if jump_to_script else t1)
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
        with ui.tab_panel(t3) as p3:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t4) as p4:
            if default_tab is t4:
                _render_transcripts_tab()
            else:
                ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")

    lazy_panels = {
        t1.props["name"]: (p1, _render_lookback_tab),
        t2.props["name"]: (p2, _render_script_workflow_tab),
        t3.props["name"]: (p3, _render_surprise_tracker_tab),
        t4.props["name"]: (p4, _render_transcripts_tab),
    }
    loaded_tabs = {default_tab.props["name"]}

    async def _load_tab_on_demand(e):
        name = e.value
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
                ui.label("⚠️ This tab failed to load").classes("text-lg font-bold").style(f"color:{COLORS['danger']};")
                ui.label("Something broke while rendering this tab. The exact error is in the server "
                         "console (the terminal window running app_nicegui.py) — copy it from there.").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")
            ui.notify(f"{name} failed to load — see server console for the error.", type="negative")

    tabs.on_value_change(_load_tab_on_demand)


# ─────────────────────────────────────────────────────────────────────────
# Tab 0 — Prior Qtr Review
# ─────────────────────────────────────────────────────────────────────────
def _render_lookback_tab():
    ui.label("📊 Q1 2026 Call Post-Mortem — What the Script Taught Us").classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};")
    ui.label("Every Q2 script decision should start here. What worked, what was missed, and what analysts actually cared about.").style(f"color:{COLORS['text_muted']};font-size:12px;")

    with ui.row().classes("w-full gap-3 items-stretch"):
        with ui.card().classes("flex-[2]").style("background:linear-gradient(135deg,#1D4ED8,#1E3A5F);border-radius:10px;"):
            ui.label("🎧 Q1 2026 Earnings Call Replay").classes("font-bold").style("color:#F1F5F9;")
            ui.label("May 13, 2026 · 4:30 PM ET · 72 minutes · Chorus Call archive").style("color:#93C5FD;font-size:12px;")
        ui.link("▶️ Play on Chorus Call", "https://www.choruscall.com", new_tab=True).classes("flex-1 text-center").style(
            f"background:{COLORS['accent']};color:white;padding:10px;border-radius:8px;")
        with ui.column().classes("flex-1"):
            ui.label("📄 Upload the transcript PDF in the 🎙️ Call Transcripts tab for full-text search and AI summary.").style(f"color:{COLORS['text_muted']};font-size:11.5px;padding:8px;")
            ui.button("🎙️ Go to Call Transcripts", on_click=lambda: nav.go_to("Earnings", earnings_tab="transcripts")).props("flat dense")

    with ui.row().classes("w-full gap-3"):
        for val, lbl, sub, clr in [
            ("+24.22%", "AH Reaction", "May 13 · record session", "#4ADE80"),
            ("$25.47M", "Q1 Revenue", "+16% YoY · record quarter", "#4ADE80"),
            ("$0.00 EPS", "First B/E quarter", "vs −$0.01 guided", "#4ADE80"),
            ("2.4x", "Volume vs avg", "Analyst interest spiked", "#60A5FA"),
            ("72 min", "Call length", "vs 65 min Q4 2025", "#94A3B8"),
        ]:
            with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                ui.label(val).classes("text-lg font-bold").style(f"color:{clr};")
                ui.label(lbl).style(f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")
                ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:10.5px;")

    with ui.row().classes("w-full gap-4 items-start"):
        with ui.column().classes("flex-[6]"):
            ui.label("Script Section Timing — Q1 2026 Actual").classes("font-bold")
            ui.label("Compare against Q2 script once drafted. CEO historically runs long; CFO has tightened.").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
            for sec, actual, hist, clr, note in _Q1_SECTION_TIMING:
                delta = actual - hist
                delta_str = f"+{delta:.0f} min" if delta > 0 else (f"{delta:.0f} min" if delta < 0 else "on time")
                delta_clr = "#F87171" if delta > 0 else ("#4ADE80" if delta < 0 else COLORS["text_muted"])
                with ui.row().classes("w-full items-center gap-3").style(f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                    ui.label(sec).style(f"color:{COLORS['text_body']};font-size:12.5px;min-width:150px;")
                    ui.label(f"{actual:.0f} min").style(f"color:{clr};font-weight:bold;min-width:60px;")
                    ui.label(delta_str).style(f"color:{delta_clr};font-size:11.5px;min-width:70px;")
                    ui.label(note).style(f"color:{COLORS['text_muted']};font-size:11.5px;")

            ui.label("Script Word Count — Q1 2026").classes("font-bold").style("margin-top:12px;")
            for sec, wc, hist_wc in _Q1_SECTION_WORDCOUNT:
                pct = min(int(wc / 2500 * 100), 100)
                vs_clr = "#F59E0B" if wc > hist_wc * 1.15 else COLORS["text_muted"]
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label(sec).style(f"color:{COLORS['text_muted']};font-size:11.5px;min-width:150px;")
                    with ui.element("div").classes("flex-1").style(f"background:{COLORS['canvas_bg']};border-radius:4px;height:8px;overflow:hidden;"):
                        ui.element("div").style(f"width:{pct}%;height:100%;background:#3B82F6;")
                    ui.label(f"{wc:,}").style(f"color:{COLORS['text_body']};font-size:11.5px;min-width:50px;")
                    ui.label(f"vs {hist_wc:,} hist").style(f"color:{vs_clr};font-size:11px;min-width:70px;")

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
            ui.label("Each item below is a direct fix from Q1 post-mortem.").style(f"color:{COLORS['text_muted']};font-size:12px;")

            for a in _get_current_qa_actions():
                with ui.row().classes("w-full items-start gap-3"):
                    ui.label(a["icon"]).style("font-size:24px;")
                    with ui.column().classes("flex-1 gap-1"):
                        with ui.card().classes("w-full").style(f"background:rgba(0,0,0,.15);border:1px solid {a['clr']};"):
                            ui.label(f"{a['priority']} · Q1 FINDING").style(f"color:{a['clr']};font-size:11px;font-weight:bold;text-transform:uppercase;")
                            ui.label(a["q1_finding"]).style(f"color:{COLORS['text_muted']};font-size:12px;")
                            ui.label(a["action"]).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:14px;")
                            ui.label(f"📍 {a['where']}").style(f"color:{a['clr']};font-size:11.5px;")
                        ui.label(a["impact"]).style(f"color:{COLORS['text_muted']};font-size:11.5px;font-style:italic;padding:0 4px;")
            ui.label("These same items now auto-seed Step 2 of each relevant persona's Script Canvas tab — "
                      "click 📝 Script Generation above to see them there, pre-filled and editable.").style(
                f"color:{COLORS['text_muted']};font-size:11.5px;margin-top:6px;")

        with ui.column().classes("flex-[4]"):
            ui.label("Q&A Analysis — What Did Analysts Ask?").classes("font-bold")
            ui.label("Pre-emption score: was this addressed proactively in the script, or did it surface as a question?").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
            qa_topics = _Q1_QA_TOPICS
            for topic, preempted, note in qa_topics:
                clr = "#4ADE80" if preempted else "#F87171"
                icon = "✅" if preempted else "❌"
                with ui.row().classes("w-full items-start gap-2").style(f"padding:4px 0;"):
                    ui.label(icon)
                    with ui.column().classes("gap-0"):
                        ui.label(topic).style(f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
                        ui.label(note).style(f"color:{clr};font-size:11.5px;")

            preempted_count = sum(1 for _, p, _ in qa_topics if p)
            score = round(preempted_count / len(qa_topics) * 100)
            with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                ui.label("Pre-emption score — Q1 2026").style(f"color:{COLORS['text_muted']};font-size:11px;text-transform:uppercase;")
                ui.label(f"{score}% · {preempted_count} of {len(qa_topics)} topics addressed proactively").classes("font-bold").style("color:#4ADE80;font-size:18px;")
                ui.label("Target for Q2: 90%+ · Key fix: interest income bridge language").style("color:#F59E0B;font-size:11.5px;")

            ui.label("Post-Call Analyst Note Alignment").classes("font-bold").style("margin-top:10px;")
            alignment = [
                ("Record revenue momentum", "HCW · Ladenburg both highlighted", "#4ADE80"),
                ("First B/E quarter", "HCW flagged as positive inflection", "#4ADE80"),
                ("PayFac growth conviction", "Ladenburg led note with PayFac thesis", "#4ADE80"),
                ("Interest income drag", "Ladenburg flagged as lingering uncertainty", "#F87171"),
                ("H2 margin expansion", "Neither analyst modeled the H2 improvement explicitly", "#F59E0B"),
            ]
            for takeaway, view, clr in alignment:
                icon = "✅" if clr == "#4ADE80" else ("⚠️" if clr == "#F59E0B" else "❌")
                with ui.column().classes("gap-0").style(f"border-bottom:1px solid {COLORS['border']};padding:5px 0;"):
                    ui.label(f"{icon} {takeaway}").style(f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
                    ui.label(view).style(f"color:{COLORS['text_muted']};font-size:11.5px;")


def _metric(label, value, sub):
    with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(value).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")
        ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:10.5px;")


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
    delta = (n.get("rev", 0) or 0) - (CT("q2_consensus_rev", 0) or 0)
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
        return (f"Total revenue for the quarter was ${n.get('rev',0):.1f}M, which came in {beat} Street "
                f"consensus of ${CT('q2_consensus_rev',0):.1f}M. Gross margin was {n.get('gm',0):.1f}%, and "
                f"Adjusted EBITDA was ${n.get('ebitda',0):.1f}M. GAAP EPS was ${n.get('eps',0):.2f}. SG&A "
                f"totaled ${n.get('sga',0):.1f}M. We ended the quarter with ${n.get('cash',0):.1f}M in cash.")
    if role == "CRO":
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

    prompts = {
        "IR": f"Write a 2-3 sentence IR opening for {ticker}'s earnings call, introducing the speakers "
              f"({contacts['CEO']['name']} CEO, {contacts['CFO']['name']} CFO) and the standard "
              f"forward-looking-statements reminder. Tone read vs Street consensus: {tone['label']}. {tone_rule} "
              f"What should change from last quarter's opening (see Step 1 review): "
              f"{what_new or 'no specific updates provided — keep the tone consistent with last quarter'}. "
              f"Professional, concise, plain text (no markdown).",
        "CFO": f"Write a CFO financial-review paragraph for an earnings call using these Q2 actuals: revenue "
               f"${n.get('rev',0):.1f}M, gross margin {n.get('gm',0):.1f}%, Adjusted EBITDA ${n.get('ebitda',0):.1f}M, "
               f"GAAP EPS ${n.get('eps',0):.2f}, SG&A ${n.get('sga',0):.1f}M, cash ${n.get('cash',0):.1f}M. Street "
               f"consensus revenue was ${CT('q2_consensus_rev',0):.1f}M. Tone read vs Street consensus: "
               f"{tone['label']}. {tone_rule} What to address proactively this quarter (see Step 1 review — last "
               f"quarter's interest-income miss was not pre-empted and drew analyst follow-up): "
               f"{what_new or 'no specific updates provided'}. Professional tone, plain text (no markdown), "
               f"4-6 sentences.",
        "CRO": f"Write a business-operations paragraph for an earnings call covering: transaction volume "
               f"${n.get('vol',0):.1f}B (+{n.get('vol_yoy',0):.0f}% YoY), {n.get('txn',0):.1f}M transactions. "
               f"Additional operating detail from this quarter (Stage 1B): {ops_text}. "
               f"What's new this quarter: {what_new or 'no specific updates provided'}. Professional tone, plain "
               f"text (no markdown), 3-5 sentences.",
        "CEO": f"Write a CEO narrative paragraph for {ticker}'s earnings call covering strategic highlights, then "
               f"the guidance stance: {guidance_line}. Tone read vs Street consensus: {tone['label']}. {tone_rule} "
               f"What's new/evolved since last quarter (see Step 1 review): "
               f"{what_new or 'continued execution against the long-term plan'}. Confident but not "
               f"promotional, plain text (no markdown), 4-6 sentences.",
    }
    draft = _call_claude_script(prompts.get(role, ""), 500)
    if draft:
        return draft, True
    return _fallback_draft(role, n, what_new, ticker, ops, gd), False


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
    ("raise_low", "🟢 RAISE — Increase the low end of the range (most common beat action at Q2)"),
    ("raise_mid", "🔵 RAISE — Increase the midpoint (strong beat + strong H2 visibility required)"),
    ("reiterate", "🟡 REITERATE — Maintain full range (conservative; appropriate after Q1-level beat at Q2)"),
    ("narrow", "🔴 NARROW — Tighten the range without raising (signals H2 visibility but not confidence)"),
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
    """Seasonality-adjusted guidance dashboard numbers + scenario
    recommendation. The recommendation is informational only — the actual
    guidance action is still a human (CFO/CEO) radio-button decision.
    Every seasonal/growth/prior-FY input comes from the active client's
    guidance_policy (CGP()) — a client with none configured gets an honest
    all-zeros read here rather than USIO's numbers."""
    policy = CGP()
    prior_fy_rev = policy.get("prior_fy_quarterly_revenue", {})
    weights = policy.get("seasonal_weights", {})
    growth_low = policy.get("fy_growth_low", 0)
    growth_high = policy.get("fy_growth_high", 0)
    prior_fy_total = sum(prior_fy_rev.values())

    n = ss.get("q2_numbers", {})
    q2_actual = n.get("rev", 0) or 0
    q1_actual = CF().get("last_rev", 0) or 0  # same figure the Prior Qtr Review tab already uses
    ytd_rev = q1_actual + q2_actual
    fy_low = round(prior_fy_total * (1 + growth_low), 2)
    fy_hi = round(prior_fy_total * (1 + growth_high), 2)
    fy_mid = round((fy_low + fy_hi) / 2, 2)
    ytd_pct_of_mid = (ytd_rev / fy_mid * 100) if fy_mid else 0
    seasonal_h1_pct = (weights.get("Q1", 0) + weights.get("Q2", 0)) * 100
    pace_vs_seasonal = ytd_pct_of_mid - seasonal_h1_pct
    beat_vs_street = q2_actual - (CT("q2_consensus_rev", 0) or 0)
    h2_2025_rev = prior_fy_rev.get("Q3", 0) + prior_fy_rev.get("Q4", 0)
    h2_needed_low = fy_low - ytd_rev
    h2_growth_needed = ((h2_needed_low / h2_2025_rev) - 1) * 100 if h2_2025_rev else 0
    fy_implied_from_h1 = (ytd_rev / seasonal_h1_pct * 100) if seasonal_h1_pct else 0

    if pace_vs_seasonal >= 3.0 and beat_vs_street >= 1.0:
        scenario, label = "RAISE_MID", "RAISE MIDPOINT — Running materially above seasonal pace; beat supports full range shift"
    elif pace_vs_seasonal >= 1.0 and beat_vs_street >= 0:
        scenario, label = "RAISE_LOW", "RAISE LOW END — Above seasonal pace; bank the beat into the floor"
    elif pace_vs_seasonal >= -1.0 and beat_vs_street >= -0.5:
        scenario, label = "REITERATE", "REITERATE — On seasonal pace; H2 catalysts needed before raising"
    else:
        scenario, label = "REITERATE_CAUTIOUS", "REITERATE WITH CAUTION — Behind seasonal pace; Street will ask about H2 bridge"

    return {
        "ytd_rev": ytd_rev, "fy_low": fy_low, "fy_hi": fy_hi, "fy_mid": fy_mid,
        "ytd_pct_of_mid": ytd_pct_of_mid, "pace_vs_seasonal": pace_vs_seasonal,
        "beat_vs_street": beat_vs_street, "h2_2025_rev": h2_2025_rev,
        "h2_needed_low": h2_needed_low, "h2_growth_needed": h2_growth_needed,
        "fy_implied_from_h1": fy_implied_from_h1, "scenario": scenario, "scenario_label": label,
    }


def _guidance_range_for_action(action, math_):
    """Flat-dollar range nudges are a per-client policy value
    (guidance_policy.range_deltas_m) rather than hardcoded — sized for
    USIO's scale; a much larger client would need bigger (or %-of-revenue)
    moves here. Defaults to 0 (no-op nudge) for a client with none configured."""
    fy_low, fy_hi = math_["fy_low"], math_["fy_hi"]
    deltas = CGP().get("range_deltas_m", {})
    d_raise_low = deltas.get("raise_low", 0)
    d_raise_mid = deltas.get("raise_mid", 0)
    d_narrow = deltas.get("narrow", 0)
    if action == "raise_low":
        new_low, new_hi = round(fy_low + d_raise_low, 1), round(fy_hi, 1)
        rationale = (f"Raising the low end from ${fy_low:.1f}M to ${new_low:.1f}M reflects the Q2 beat now banked "
                     f"into the full year. The high end is maintained, preserving appropriate conservatism given "
                     f"H2 execution risk.")
    elif action == "raise_mid":
        new_low, new_hi = round(fy_low + d_raise_mid, 1), round(fy_hi + d_raise_mid, 1)
        rationale = (f"Raising both ends of the guidance range by approximately ${d_raise_mid:.1f}M reflects "
                     f"strong H1 performance and improving H2 visibility from pipeline, new implementations, and "
                     f"named H2 catalysts.")
    elif action == "narrow":
        new_low, new_hi = round(fy_low + d_narrow, 1), round(fy_hi - d_narrow, 1)
        rationale = ("Narrowing the guidance range reflects increased visibility into H2 without committing to "
                     "a higher midpoint ahead of key Q3 implementations.")
    else:  # reiterate
        new_low, new_hi = round(fy_low, 1), round(fy_hi, 1)
        rationale = ("Reiterating the full-year guidance range reflects management's confidence in the business "
                     "trajectory while maintaining appropriate conservatism given that significant H2 "
                     "implementations are still scaling.")
    return new_low, new_hi, rationale


def _guidance_template_draft(action, new_low, new_hi, rationale):
    """Rule-based fallback if the Claude call fails/no key — same role as
    _fallback_draft above, ported from app.py's 4 hardcoded script variants.
    Catalysts, closing line, and operator handoff now come from the active
    client's guidance_policy (CGP()) instead of hardcoded USIO text."""
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
    catalysts_block = "\n".join(f"  ☐ {c}" for c in catalysts) or "  ☐ [No H2 catalysts configured for this client]"
    closing_bit = f"I thank our shareholders for their trust and support. {closing_line}\n\n" if closing_line else ""
    handoff_bit = handoff or ""
    return (
        f"{openers[action]}\n\n{ranges[action]}\n\n{tones[action]}\n\n{h2_signal}\n\n"
        f"[SPECIFIC H2 CATALYST LANGUAGE — reference at least 2 named catalysts here]\n"
        f"[CFO to confirm which are disclosure-appropriate before delivery:]\n{catalysts_block}\n"
        f"  ☐ [Add any Q2-specific new wins from Stage 1 notes]\n\n"
        f"{closing_bit}{handoff_bit}"
    )


def _generate_guidance_draft(ss, action, new_low, new_hi, rationale, extra_context=""):
    math_ = _guidance_math(ss)
    tone = _tone_context(ss)
    policy = CGP()
    weights = policy.get("seasonal_weights", {})
    quotes_block = "; ".join(f'{q}: "{t}"' for q, t in _GUIDANCE_PRIOR_QUOTES)
    catalysts_block = "; ".join(policy.get("known_h2_catalysts", [])) or "none configured"
    range_str = f"${new_low:.1f}M to ${new_hi:.1f}M"
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
        f"Known H2 catalysts, reference at least 2 (mark speculative specifics as [FLS]...[/FLS]): "
        f"{catalysts_block}. Writing rules: {_guidance_writing_rules()} "
        f"Additional context: {extra_context or 'none provided'}. "
        f"Tone: {tone['label']}. Target 300-350 words, plain text (no markdown)."
    )
    draft = _call_claude_script(prompt, 700)
    if draft:
        return draft, True
    return _guidance_template_draft(action, new_low, new_hi, rationale), False


def _render_guidance_decision(ss):
    """Guidance & Outlook Decision Engine — renders ahead of the CEO's own
    Step 1 review in _render_persona_steps, since the CEO narrative's tone/
    H2-confidence language/closing are all supposed to flow from whichever
    guidance action is decided here (matching app.py's "Workflow note" —
    aspirational there since the widgets sat below the CEO editor in the
    same tab; enforced by placement here instead)."""
    gd = ss.setdefault("guidance_decision", {})
    math_ = _guidance_math(ss)

    with ui.card().classes("w-full").style("background:rgba(251,191,36,.08);border:1px solid rgba(251,191,36,.3);"):
        ui.label("⚡ Workflow note").classes("font-bold").style("color:#FDE68A;font-size:12.5px;")
        ui.label("Complete this Guidance Decision before drafting the CEO narrative below — the tone, H2 "
                  "confidence language, and closing should all flow from whichever action you pick here.").style(
            "color:#FDE68A;font-size:12px;")

    ui.label("📐 Guidance & Outlook Decision Engine").classes("font-bold").style("margin-top:8px;")
    ui.label("CFO and CEO decide · Platform drafts language for each scenario · Every word signals to the Street").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
        _metric("YTD vs seasonal pace", f"{math_['pace_vs_seasonal']:+.1f}pp", f"{math_['ytd_pct_of_mid']:.1f}% of midpoint banked")
        _metric("FY implied from H1", f"${math_['fy_implied_from_h1']:.1f}M", f"vs ${math_['fy_low']:.1f}-{math_['fy_hi']:.1f}M range")
        _metric("H2 needed (low end)", f"${math_['h2_needed_low']:.1f}M", f"{math_['h2_growth_needed']:+.1f}% YoY vs H2 2025")
        _metric("Beat vs Street", f"{math_['beat_vs_street']:+.2f}M", "")

    with ui.card().classes("w-full").style("background:rgba(59,130,246,.08);border:2px solid rgba(59,130,246,.3);margin-top:6px;"):
        ui.label(f"RECOMMENDED ACTION: {math_['scenario_label']}").classes("font-bold").style("color:#93C5FD;")
        ui.label("Based on YTD revenue as % of guidance midpoint, beat/miss vs Street, and H2 growth required vs "
                  "prior-year H2. CFO and CEO must confirm before finalizing script language.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")

    ui.label("Choose your guidance action — script adapts automatically:").classes("font-bold").style(
        "margin-top:8px;font-size:12.5px;")
    default_action = {"RAISE_MID": "raise_mid", "RAISE_LOW": "raise_low"}.get(math_["scenario"], "reiterate")
    action_select = ui.radio({a: lbl for a, lbl in _GUIDANCE_ACTIONS},
                              value=gd.get("action", default_action)).classes("w-full")
    ack_label = ui.label(_GUIDANCE_ACK.get(action_select.value, "")).style(
        f"color:{COLORS['accent_light']};font-size:11.5px;font-style:italic;")

    def on_action_change(e, ack_label=ack_label):
        ack_label.text = _GUIDANCE_ACK.get(e.value, "")

    action_select.on_value_change(on_action_change)

    with ui.expansion("📚 IR Guidance Protocol — What the Street Expects at Each Quarter (read before finalizing)").classes("w-full").style("margin-top:6px;"):
        ui.markdown(f"""
**Why guidance language is the most consequential section of the call**

Every institutional investor on this call is doing the same math in real time. They know your H1 numbers, they know your full-year range, and they're listening for one thing: does management have enough H2 visibility to justify their model, and is the tone confident or hedged?

**Q1 earnings — what the Street expects:** companies almost never raise full-year guidance after Q1. The standard is reiteration — raising after one quarter signals either management sandbagged the range or is getting ahead of data it doesn't have yet.

**Q2 earnings — the first real decision point:** H1 is complete and the Street has half-year data, so a raise is *expected* if the beat is meaningful.
- Beat > \\$1M vs Street and YTD > 50% of midpoint → raise the low end at minimum.
- Beat plus strong H2 catalyst visibility → raise the midpoint — the most powerful signal on the call.
- In line or a small beat → reiterate, but with *specific* H2 visibility language, not generic optimism.
- Miss → reiterate the range (widen slightly if needed) with a specific recovery narrative; never cut guidance at Q2 without a clear bridge.

**Current situation ({math_['scenario']}):** YTD banked \\${math_['ytd_rev']:.1f}M ({math_['ytd_pct_of_mid']:.1f}% of \\${math_['fy_mid']:.1f}M midpoint) · H2 needed for the low end \\${math_['h2_needed_low']:.1f}M ({math_['h2_growth_needed']:+.1f}% YoY vs H2 2025's \\${math_['h2_2025_rev']:.1f}M) · Beat vs Street {math_['beat_vs_street']:+.2f}M.

**Phrases that signal confidence vs. caution to the Street:**
- "We are raising our full-year revenue guidance..." → maximum positive signal
- "We are narrowing our guidance range to reflect improved H2 visibility..." → positive but measured
- "We continue to expect..." / "We are reiterating..." → neutral, read as conservative
- "We are updating our guidance to reflect..." → typically precedes a cut — Street will ask why immediately
""")

    guidance_context_input = ui.input(
        "Add any H2 visibility or guidance context before drafting:",
        placeholder="e.g. 'We are raising the low end. H2 visibility is good because school voucher starts Q3 "
                    "and PostCredit onboarding begins.'",
        value=gd.get("context", ""),
    ).classes("w-full").style("margin-top:8px;")

    # Same fix as _render_persona_steps's draft box: render_guidance_draft_box
    # reads draft_area as a plain closure variable (resolved when actually
    # called) instead of a default arg, so draft_area can be created AFTER
    # the Generate button below — Generate now visually comes first.
    def render_guidance_draft_box(text):
        draft_area.clear()
        with draft_area:
            ui.label("📄 Guidance draft — edit as needed, then submit to script (all [FLS] blocks need Legal review):").style(
                f"color:{COLORS['text_muted']};font-size:11px;")
            box = ui.textarea(value=text).classes("w-full").props("rows=10")
            pace_note, pace_clr = _pacing_estimate(text, "guidance")
            pace_label = ui.label(pace_note).style(f"color:{pace_clr};font-size:11px;")

            def save_edit(e, pace_label=pace_label):
                gd["text"] = e.value
                ss["guidance_decision"] = gd
                _save_json("script_workflow_state.json", ss)
                note, clr = _pacing_estimate(e.value, "guidance")
                pace_label.text = note
                pace_label.style(f"color:{clr};font-size:11px;")

            box.on_value_change(save_edit)

            def submit(box=box):
                gd["text"] = box.value
                ss["guidance_decision"] = gd
                _save_json("script_workflow_state.json", ss)
                ui.notify("Guidance & Outlook submitted to script.", type="positive")

            ui.button("✅ Submit to Script", on_click=submit).props("color=primary dense").style("margin-top:4px;")

    def generate_guidance(action_select=action_select, guidance_context_input=guidance_context_input):
        ui.notify("Generating guidance draft…", type="info")
        try:
            action = action_select.value
            new_low, new_hi, rationale = _guidance_range_for_action(action, math_)
            draft, was_ai = _generate_guidance_draft(ss, action, new_low, new_hi, rationale, guidance_context_input.value)
            gd.update({"action": action, "new_low": new_low, "new_hi": new_hi, "rationale": rationale,
                       "context": guidance_context_input.value, "text": draft})
            ss["guidance_decision"] = gd
            _save_json("script_workflow_state.json", ss)
            render_guidance_draft_box(draft)
            ui.notify("Drafted with AI — review below, then Submit." if was_ai else
                      "AI unavailable — used the templated draft for this action. Review below, then Submit.",
                      type="positive" if was_ai else "warning")
        except Exception as exc:
            ui.notify(f"Guidance draft generation failed: {exc}", type="negative")
            raise

    ui.button("🤖 Draft Guidance Section with AI", on_click=generate_guidance).props("color=primary dense").style("margin-top:8px;")

    draft_area = ui.column().classes("w-full").style("margin-top:8px;")

    existing_text = gd.get("text", "")
    if existing_text:
        render_guidance_draft_box(existing_text)

    ui.markdown("---")


def _render_persona_steps(ss, role, key):
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
    if role == "CEO":
        _render_guidance_decision(ss)
    if role == "IR":
        _render_call_opening(ss)

    ref = _PERSONA_LAST_QUARTER.get(role, {})
    notes = ss.setdefault("persona_notes", {}).setdefault(key, {"whats_new": "", "final_notes": ""})

    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};padding:10px;box-shadow:none;border:1px solid {COLORS['border']};"):
        ui.label("Step 1 — Review: What Was Said Last Quarter").classes("font-bold").style("font-size:12.5px;")
        if ref.get("quote"):
            ui.label(f"“{ref['quote']}”").style(f"color:{COLORS['text_body']};font-size:12px;font-style:italic;margin-top:4px;")
        for q_label, q_text in ref.get("prior_quotes", []):
            ui.label(f"{q_label}: “{q_text}”").style(f"color:{COLORS['text_muted']};font-size:11.5px;font-style:italic;")
        if ref.get("rows"):
            with ui.column().classes("w-full gap-0").style("margin-top:4px;"):
                for r_label, r_val in ref["rows"]:
                    ui.label(f"{r_label}: {r_val}").style(f"color:{COLORS['text_body']};font-size:11.5px;")
        for tag in ref.get("tags", []):
            ui.label(f"• {tag}").style(f"color:{COLORS['accent_light']};font-size:11px;margin-top:2px;")
        if not ref.get("quote") and not ref.get("rows"):
            ui.label("No prior-quarter reference on file yet for this persona.").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    question, placeholder = _PERSONA_WHATS_NEW.get(role, ("What's new this quarter?", ""))
    ui.label(f"Step 2 — {question}").classes("font-bold").style("font-size:12.5px;margin-top:8px;")

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
    # instead in the ❓ Q&A Prep tab, which isn't persona-scoped. Once a
    # second quarter exists, someone should hand-curate persona_role
    # assignments the same way this quarter's list was, rather than have
    # this silently guess.
    critique_items = [a for a in _Q1_TO_Q2_ACTIONS if a.get("persona_role") == role]
    if critique_items:
        ui.label("From the Q1 post-mortem — carry forward unless already addressed:").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        for a in critique_items:
            with ui.card().classes("w-full").style(f"background:rgba(0,0,0,.15);border:1px solid {a['clr']};margin-bottom:4px;padding:6px 10px;"):
                ui.label(f"{a['icon']} {a['priority']} · {a['q1_finding']}").style(f"color:{a['clr']};font-size:11px;font-weight:bold;")
                ui.label(a["action"]).style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(a["impact"]).style(f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")
        if not notes.get("whats_new") and not notes.get("whats_new_seeded"):
            notes["whats_new"] = "; ".join(a["action"] for a in critique_items)
            notes["whats_new_seeded"] = True
            _save_json("script_workflow_state.json", ss)

    whats_new_input = ui.textarea(placeholder=placeholder, value=notes.get("whats_new", "")).classes("w-full").props("rows=2")

    def save_whats_new(e, notes=notes):
        notes["whats_new"] = e.value
        _save_json("script_workflow_state.json", ss)

    whats_new_input.on_value_change(save_whats_new)

    ui.label("Step 3 — Generate Draft").classes("font-bold").style("font-size:12.5px;margin-top:8px;")
    if role in ("IR", "CFO", "CEO"):
        tone = _tone_context(ss)
        ui.label(f"Tone read from Stage 1 numbers: {tone['label']}").style(f"color:{COLORS['text_muted']};font-size:11px;")
    final_notes_input = ui.input("Additional notes for this draft (optional)", value=notes.get("final_notes", "")).classes("w-full")

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
            ui.label("📄 Draft — edit as needed, then submit it into the script:").style(
                f"color:{COLORS['text_muted']};font-size:11px;")
            box = ui.textarea(value=text).classes("w-full").props("rows=8")
            pace_note, pace_clr = _pacing_estimate(text, role)
            pace_label = ui.label(pace_note).style(f"color:{pace_clr};font-size:11px;")

            def save_edit(e, key=key, pace_label=pace_label, role=role):
                ss["script_text"][key] = e.value
                _save_json("script_workflow_state.json", ss)
                note, clr = _pacing_estimate(e.value, role)
                pace_label.text = note
                pace_label.style(f"color:{clr};font-size:11px;")

            box.on_value_change(save_edit)

            def submit_to_script(box=box, key=key, role=role):
                ss["script_text"][key] = box.value
                _save_json("script_workflow_state.json", ss)
                ui.notify(f"Submitted to script — {role} section updated.", type="positive")

            ui.button("✅ Submit to Script", on_click=submit_to_script).props("color=primary dense").style("margin-top:4px;")

    def generate(role=role, key=key, whats_new_input=whats_new_input, final_notes_input=final_notes_input):
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

    ui.button("🤖 Generate with AI", on_click=generate).props("color=primary dense").style("margin-top:6px;")

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


def _render_qa_prep_tab(ss):
    ui.label("❓ Q&A Prep — Predicted Questions").classes("font-bold")
    ui.label("Topics that weren't pre-empted last quarter, plus catalysts/risks flagged in ingested sell-side "
              "research notes. Deterministic — no AI call needed, always available.").style(
        f"color:{COLORS['text_muted']};font-size:11px;")
    items = _build_qa_prep(ss)
    if not items:
        ui.label("Nothing carried over from last quarter, and no research notes with catalysts/risks have "
                  "been ingested yet.").style(f"color:{COLORS['text_muted']};font-size:12px;")
        return
    sev_color = {"HIGH": "#F87171", "MEDIUM": "#F59E0B", "LOW": "#94A3B8"}
    for item in items:
        clr = sev_color.get(item["severity"], "#94A3B8")
        with ui.card().classes("w-full").style(f"background:rgba(0,0,0,.15);border:1px solid {clr};margin-bottom:6px;"):
            ui.label(f"{item['severity']} · {item['topic']}").classes("font-bold").style(f"color:{clr};font-size:13px;")
            ui.label(item["source"]).style(f"color:{COLORS['text_muted']};font-size:11.5px;")
            if item.get("detail"):
                ui.label(item["detail"]).style(f"color:{COLORS['text_body']};font-size:12px;")
            ui.label(f"💡 {item['suggested_angle']}").style(f"color:{COLORS['accent_light']};font-size:11.5px;font-style:italic;")


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
    for role, key, _label in PERSONAS:
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
    full_parts = [operator_line, welcome_line, fls_line]
    full_parts += [ss["script_text"].get(key, "") for _, key, _ in PERSONAS]
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


def _render_script_canvas(ss):
    _ensure_script_drafted(ss)
    ui.label("📝 Script Canvas").classes("font-bold")
    ui.label("Every speaker's section, in order — scroll through IR, then CFO, then Business Operations, then "
              "CEO, then Q&A Prep and the assembled Full Script at the bottom. Nothing is behind a tab click.").style(
        f"color:{COLORS['text_muted']};font-size:11px;")
    # Previously this was three levels of nested Quasar tabs deep (page tabs
    # -> 5-stage tabs -> these persona tabs), which on a normal window width
    # squeezed 6 tab labels into very little space — easy to only ever see
    # the first (IR Opening) tab and never notice the rest needed a scroll/
    # click to reach. Stacked, always-open expansion panels instead: every
    # section is on the page and reachable by scrolling, matching an actual
    # "IR reviews everything, then hands to CFO, then CEO" reading order.
    contacts = _contacts()
    for role, key, label in PERSONAS:
        c = contacts.get(role, {"name": f"— {role} not configured —"})
        with ui.expansion(f"{label} — {c['name']} ({role})", value=True).classes("w-full").style(
                f"border:1px solid {COLORS['border']};border-radius:8px;margin-bottom:8px;"):
            _render_persona_steps(ss, role, key)

    with ui.expansion("❓ Q&A Prep", value=True).classes("w-full").style(
            f"border:1px solid {COLORS['border']};border-radius:8px;margin-bottom:8px;"):
        _render_qa_prep_tab(ss)

    with ui.expansion("📋 Full Script (assembled)", value=True).classes("w-full").style(
            f"border:1px solid {COLORS['border']};border-radius:8px;"):
        ui.label("Editable — for final full-script-level tweaks (e.g. smoothing the handoff between two "
                  "speakers). Edits autosave as you type, but click Save for an explicit confirmation that "
                  "this exact text is the version moving forward to CFO/CEO review.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        full_box = ui.textarea("Full Script", value=_full_script_text(ss)).classes("w-full").props("rows=16")

        saved_at = ss.get("full_script_override_saved_at")
        status_label = ui.label(
            f"✅ Saved {saved_at} — this is the version moving forward." if saved_at
            else "Not yet explicitly saved — click 💾 Save below."
        ).style(f"color:{'#4ADE80' if saved_at else COLORS['text_muted']};font-size:11px;font-weight:{'600' if saved_at else '400'};")

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
            lbl.text = f"✅ Saved {ts} — this is the version moving forward."
            lbl.style("color:#4ADE80;font-size:11px;font-weight:600;")
            ui.notify("Saved. This is the version that will go to CFO/CEO review.", type="positive")

        with ui.row().classes("w-full items-center gap-2").style("margin-top:6px;"):
            ui.button("💾 Save", on_click=save_final).props("color=primary dense")

            def export_txt(box=full_box):
                fname = f"{CT('ticker')}_{CE().get('current_quarter','')}_Script_v{ss.get('version',1)}.txt".replace(" ", "_")
                ui.download(box.value.encode(), fname)

            ui.button("⬇️ Download Current Draft", on_click=export_txt).props("flat")

            fp = ss.get("first_pass_complete")
            if fp:
                ui.label(f"✅ First Pass Completed — {fp}").style("color:#4ADE80;font-size:12px;font-weight:600;")
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

                ui.button("✅ Save & Mark First Pass Completed", on_click=mark_first_pass).props("color=primary dense")


# ─────────────────────────────────────────────────────────────────────────
# Tab 1 — Script Generation: 5-stage pipeline (see module docstring)
# ─────────────────────────────────────────────────────────────────────────
def _render_stage1(ss):
    ui.label("Stage 1 — CFO Final Numbers").classes("font-bold")
    ui.label("CFO submits Q2 actuals. Submitting activates Stage 2 (IR Review).").style(f"color:{COLORS['text_muted']};font-size:12px;")
    n = ss.get("q2_numbers", {})
    with ui.row().classes("w-full gap-4"):
        with ui.column().classes("flex-1"):
            ui.label("REVENUE ($M)").classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:12px;")
            fn_rev = ui.number("Total Revenue", value=n.get("rev"), step=0.1).classes("w-full")
            fn_ach = ui.number("ACH Revenue", value=n.get("ach"), step=0.1).classes("w-full")
            fn_card = ui.number("Card / PayFac", value=n.get("card"), step=0.1).classes("w-full")
            fn_prepaid = ui.number("Prepaid Revenue", value=n.get("prepaid"), step=0.1).classes("w-full")
            fn_output = ui.number("Output Solutions", value=n.get("output"), step=0.1).classes("w-full")
        with ui.column().classes("flex-1"):
            ui.label("PROFITABILITY").classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:12px;")
            fn_gp = ui.number("Gross Profit ($M)", value=n.get("gp"), step=0.1).classes("w-full")
            fn_gm = ui.number("Gross Margin (%)", value=n.get("gm"), step=0.1).classes("w-full")
            fn_ebitda = ui.number("Adj. EBITDA ($M)", value=n.get("ebitda"), step=0.1).classes("w-full")
            fn_eps = ui.number("GAAP EPS ($)", value=n.get("eps"), step=0.01).classes("w-full")
            fn_sga = ui.number("Total SG&A ($M)", value=n.get("sga"), step=0.1).classes("w-full")
        with ui.column().classes("flex-1"):
            ui.label("VOLUME & CASH").classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:12px;")
            fn_vol = ui.number("Vol Processed ($B)", value=n.get("vol"), step=0.1).classes("w-full")
            fn_vol_yoy = ui.number("Volume YoY (%)", value=n.get("vol_yoy"), step=0.5).classes("w-full")
            fn_txn = ui.number("Transactions (M)", value=n.get("txn"), step=0.1).classes("w-full")
            fn_cash = ui.number("Cash ($M)", value=n.get("cash"), step=0.1).classes("w-full")
            fn_buyback = ui.number("Buyback ($K)", value=n.get("buyback"), step=10.0).classes("w-full")

    fn_new = ui.textarea("What's new this quarter", value=n.get("what_new", "")).classes("w-full")
    fn_by = ui.select(["Michael White (CFO)", "Louis Hoch (CEO)", "Paul Manley (IR)"],
                       value=n.get("submitted_by", "Michael White (CFO)"), label="Submitted by").classes("w-full")

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

    ui.button("📤 Submit for Draft Generation", on_click=submit).props("color=primary").style("margin-top:8px;")

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
        ui.label("📄 Auto-Generated Script — one last look before it moves to IR").classes("font-bold").style(
            f"color:{COLORS['accent_light']};font-size:14px;")
        ui.label("This is the draft that was just generated from the numbers above. You'll formally sign off "
                  "on it (with a notes box) on the \"👔 3 · CEO+CFO Review\" tab after IR's pass.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")
        ui.textarea("Script preview", value=_full_script_text(ss)).classes("w-full").props("rows=14 readonly")


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


def _render_stage1b(ss):
    """Stage 1B — Operating Metrics & Disclosure Consistency Check. Ported
    from app.py's second Stage 1 input column (see this module's docstring
    for why it was skipped in the first pass). Submitted independently of
    _render_stage1() above — it doesn't gate the Stage 2 transition, it just
    feeds richer detail into the CRO/business-ops persona draft (see
    _generate_persona_draft) and surfaces any metric that quietly dropped
    out of disclosure versus last quarter."""
    ui.markdown("---")
    ui.label("Stage 1B — Operating Metrics & Disclosure Consistency Check").classes("font-bold")
    ui.label("Every metric disclosed last quarter should be disclosed again this quarter, or explicitly "
              "explained if it's being dropped — silence here is exactly what prompts analyst follow-up "
              "questions. This feeds the Business Operations draft below in addition to the gap check.").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    ops = ss.get("q2_ops_metrics", {})

    with ui.row().classes("w-full gap-4").style("margin-top:8px;"):
        with ui.column().classes("flex-1"):
            ui.label("CARD REVENUE METRICS").classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:12px;")
            om_card_yoy = ui.number("Card Revenue YoY (%)", value=ops.get("card_yoy"), step=0.5).classes("w-full")
            om_payfac_pct = ui.number("PayFac % of Card Revenue", value=ops.get("payfac_pct"), step=0.5).classes("w-full")
            om_payfac_yoy = ui.number("PayFac Revenue YoY (%)", value=ops.get("payfac_yoy"), step=0.5).classes("w-full")
            om_card_txn_yoy = ui.number("Card Transactions YoY (%)", value=ops.get("card_txn_yoy"), step=0.5).classes("w-full")
            om_card_vol_yoy = ui.number("Card Dollar Volume YoY (%)", value=ops.get("card_vol_yoy"), step=0.5).classes("w-full")
        with ui.column().classes("flex-1"):
            ui.label("PAYFAC PIPELINE & IMPLEMENTATIONS").classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:12px;")
            om_isv_impl = ui.number("ISVs in Implementation", value=ops.get("isv_impl"), step=1.0).classes("w-full")
            om_new_enterprise = ui.number("New Enterprise Accounts (this qtr)", value=ops.get("new_enterprise"), step=1.0).classes("w-full")
            om_filtered_merchants = ui.number("Filtered Spend Merchants Live", value=ops.get("filtered_merchants"), step=100.0).classes("w-full")
            om_rtp_txn = ui.number("Real-Time Payments Txn/Month (K)", value=ops.get("rtp_txn_k"), step=1.0).classes("w-full")
            om_payfac_growth_rate = ui.select(
                ["Growing >20% (consistent)", "Growing 15-20%", "Growing 10-15%", "Growing <10%", "Decelerating — explain in notes"],
                value=ops.get("payfac_growth_rate"), label="PayFac Growth Rate Characterization").classes("w-full")
        with ui.column().classes("flex-1"):
            ui.label("USIO ONE & CROSS-SELL").classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:12px;")
            om_usio_one_wins = ui.number("Usio ONE Cross-Sell Wins (this qtr)", value=ops.get("usio_one_wins"), step=1.0).classes("w-full")
            om_usio_one_example = ui.textarea("Usio ONE Case Study", value=ops.get("usio_one_example", "")).classes("w-full")
            om_new_leads = ui.select(
                ["G2 / Online influencer sites", "SEO / Digital marketing", "Trade shows",
                 "Usio ONE cross-sell", "Referral agents", "Direct outbound"],
                value=ops.get("new_leads", []), label="New Lead Sources Active", multiple=True).classes("w-full")

    ui.markdown("---")
    ui.label("🏦 ACH & Payments").classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:12px;")
    with ui.row().classes("w-full gap-4"):
        with ui.column().classes("flex-1"):
            om_ach_txn_yoy = ui.number("ACH Transactions YoY (%)", value=ops.get("ach_txn_yoy"), step=0.5).classes("w-full")
            om_ach_dollar_yoy = ui.number("ACH Dollar Volume YoY (%)", value=ops.get("ach_dollar_yoy"), step=0.5).classes("w-full")
            om_ach_best_month = ui.select(
                ["Yes — best-ever month", "Yes — different month", "No — but strong", "No — slower than prior quarter"],
                value=ops.get("ach_best_month"), label="Best-Ever ACH Month This Quarter?").classes("w-full")
        with ui.column().classes("flex-1"):
            om_prepaid_load_yoy = ui.number("Prepaid Load Volume YoY (%)", value=ops.get("prepaid_load_yoy"), step=0.5).classes("w-full")
            om_prepaid_txn_yoy = ui.number("Prepaid Transactions YoY (%)", value=ops.get("prepaid_txn_yoy"), step=0.5).classes("w-full")
            om_prepaid_purchase_yoy = ui.number("Prepaid Purchase Volume YoY (%)", value=ops.get("prepaid_purchase_yoy"), step=0.5).classes("w-full")

    if ops:
        missing = [label for key, label in _OPS_METRIC_LABELS.items() if ops.get(key) in (None, "", 0)]
        if missing:
            with ui.card().classes("w-full").style("background:rgba(252,211,77,.08);border:1px solid rgba(252,211,77,.25);margin-top:8px;"):
                ui.label(f"⚠️ {len(missing)} metric(s) disclosed last quarter aren't entered yet:").style(
                    "color:#FCD34D;font-weight:bold;font-size:12.5px;")
                for m in missing:
                    ui.label(f"• {m}").style(f"color:{COLORS['text_muted']};font-size:12px;")

    om_disclosure_notes = ui.textarea("Explain any intentional metric omissions (reviewed in Stage 2)",
                                       value=ops.get("disclosure_notes", "")).classes("w-full").style("margin-top:8px;")

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

    ui.button("📊 Submit Operating Metrics", on_click=submit_ops).props("color=primary").style("margin-top:8px;")


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
    ui.label("Stage 2 — IR Review").classes("font-bold")
    if ss["stages"]["cfo_numbers"]["status"] != "complete":
        ui.label("⏳ Nothing here yet — go to the \"📥 1 · CFO Numbers\" tab and click \"📤 Submit for Draft "
                  "Generation\" first.").style(f"color:{COLORS['warning']};")
        return
    n = ss["q2_numbers"]
    beat = n.get("rev", 0) > CT("q2_consensus_rev", 0)
    with ui.row().classes("w-full gap-3"):
        _metric("Revenue", f"${n.get('rev',0):.1f}M", "✅ BEAT" if beat else "vs consensus")
        _metric("GAAP EPS", f"${n.get('eps',0):.2f}", "Positive" if n.get("eps", 0) >= 0.01 else "")
        _metric("Adj. EBITDA", f"${n.get('ebitda',0):.1f}M", "")
        _metric("Volume Growth", f"+{n.get('vol_yoy',0):.0f}% YoY", "")
    ui.markdown("---")
    _render_script_canvas(ss)

    consistency_warnings = _check_script_consistency(ss)
    if consistency_warnings:
        ui.markdown("---")
        with ui.card().classes("w-full").style("background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.35);"):
            ui.label("⚠️ Consistency check — review before advancing to Stage 3").classes("font-bold").style(
                "color:#FCD34D;font-size:13px;")
            for w in consistency_warnings:
                ui.label(f"• {w}").style(f"color:{COLORS['text_body']};font-size:12px;")

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

                ui.button("📤 Generate v1 + Send to IR", on_click=send_ir).props("color=primary")
            elif rv["status"] == "sent":
                sent_dt = datetime.strptime(rv["sent"], "%Y-%m-%d %H:%M")
                hrs = (datetime.now() - sent_dt).total_seconds() / 3600
                if hrs >= 24:
                    ui.label(f"🔴 Overdue — {hrs:.0f}h since sent.").style(f"color:{COLORS['danger']};")
                else:
                    ui.label(f"🔵 Sent {hrs:.0f}h ago — awaiting return").style(f"color:{COLORS['accent_light']};")
                notes_in = ui.textarea("IR edit notes", value=rv.get("notes", "")).classes("w-full")

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

                ui.button("✅ Mark IR Complete", on_click=mark_complete).props("color=primary")
            else:
                ui.label("✅ IR review complete").style("color:#4ADE80;")
        with ui.column().classes("flex-1"):
            ui.label("IR Review Checklist").classes("font-bold")
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
    ui.label("Stage 3 — CFO + CEO + CRO Simultaneous Review").classes("font-bold")
    if ss["stages"]["ir_review"]["status"] != "complete":
        ui.label("⏳ Nothing here yet — go to the \"✏️ 2 · IR Review\" tab and click \"✅ Mark IR Complete\" "
                  "first (the tabs above aren't locked, so it's easy to land here before that step).").style(
            f"color:{COLORS['warning']};")
        return
    # Open by default — this used to be a collapsed ui.expansion, which meant
    # CFO/CEO/CRO landing on this stage saw no script at all unless they
    # thought to click it open. It's the whole point of this stage, so show it.
    with ui.expansion("📝 Script Canvas — View & Edit", value=True).classes("w-full"):
        _render_script_canvas(ss)
    ui.markdown("---")
    contacts = _contacts()
    with ui.row().classes("w-full gap-6"):
        for role in ("CFO", "CEO", "CRO"):
            rv = ss["reviewers"][role]
            c = contacts[role]
            with ui.column().classes("flex-1"):
                ui.label(f"{role} — {c['name']}").classes("font-bold")
                ui.label(c["email"]).style(f"color:{COLORS['accent_light']};font-size:12px;")
                if rv["status"] == "complete":
                    ui.label("✅ Review complete").style("color:#4ADE80;")
                    if rv.get("notes"):
                        ui.label(f"Notes: {rv['notes']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
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
                            ui.label(f"🔴 Overdue {hrs:.0f}h — send reminder").style(f"color:{COLORS['danger']};")
                        else:
                            ui.label(f"🔵 Sent {hrs:.0f}h ago").style(f"color:{COLORS['accent_light']};")
                    else:
                        def send(role=role):
                            ss["reviewers"][role].update({"status": "sent", "sent": datetime.now().strftime("%Y-%m-%d %H:%M")})
                            _save_json("script_workflow_state.json", ss)
                            _refresh()

                        ui.button(f"📤 Send v2 to {c['name']}", on_click=send).props("color=primary dense outline")

                    notes_in = ui.textarea(f"{role} comments", value=rv.get("notes", "")).classes("w-full")

                    def mark(role=role, notes_in=notes_in):
                        ss["reviewers"][role].update({"status": "complete", "received": datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": notes_in.value})
                        _save_json("script_workflow_state.json", ss)
                        _check_stage3_advance(ss)
                        _refresh()

                    ui.button(f"✅ Mark {role} Complete", on_click=mark).props("dense")


def _render_stage4(ss):
    ui.label("Stage 4 — Consolidation").classes("font-bold")
    if ss["stages"]["exec_review"]["status"] != "complete":
        ui.label("⏳ Nothing here yet — go to the \"👔 3 · CEO+CFO Review\" tab and get both \"✅ Mark CFO "
                  "Complete\" and \"✅ Mark CEO Complete\" clicked first.").style(f"color:{COLORS['warning']};")
        return
    with ui.expansion("📝 Script Canvas — View & Edit", value=True).classes("w-full"):
        _render_script_canvas(ss)
    ui.markdown("---")
    ui.label("Comments Side-by-Side").classes("font-bold")
    contacts = _contacts()
    with ui.row().classes("w-full gap-4"):
        for role in ("IR", "CFO", "CEO"):
            with ui.column().classes("flex-1"):
                ui.label(contacts[role]["name"]).classes("font-bold")
                notes = ss["reviewers"][role].get("notes") or "(no notes logged)"
                ui.textarea("Comments", value=notes).classes("w-full").props("readonly rows=6")
    ui.markdown("---")
    cons_summary = ui.textarea("Changes incorporated into v3 (IR final decisions)").classes("w-full")
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

    ui.button("🔀 Generate v3 — Pre-Legal Clean Copy", on_click=generate_v3).props("color=primary")


def _render_stage5(ss):
    ui.label("Stage 5 — Legal Sign-Off").classes("font-bold")
    if ss["stages"]["consolidate"]["status"] != "complete":
        ui.label("⏳ Nothing here yet — go to the \"🔀 4 · Consolidation\" tab, check the confirmation box, and "
                  "click \"🔀 Generate v3 — Pre-Legal Clean Copy\" first.").style(f"color:{COLORS['warning']};")
        return
    with ui.expansion("📝 Script Canvas — View & Edit", value=True).classes("w-full"):
        _render_script_canvas(ss)
    ui.markdown("---")
    fls_items = _fls_items()
    with ui.row().classes("w-full gap-6"):
        with ui.column().classes("flex-[2]"):
            ui.label("Forward-Looking Statements Checklist").classes("font-bold")
            if not fls_items:
                ui.label("No FLS checklist items configured for this client — add them to CLIENT_REGISTRY's "
                          "\"fls_items\" in config/client_config.py.").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label("Every item must be individually cleared by legal before the script is finalized.").style(f"color:{COLORS['text_muted']};font-size:12px;")
            for fls_id, fls_text in fls_items:
                cleared = ss["fls_checklist"].get(fls_id, False)
                with ui.row().classes("w-full items-center gap-2"):
                    ui.label("✅" if cleared else "⬜")
                    ui.label(f"{fls_id} {fls_text}").classes("flex-1").style(
                        f"color:{COLORS['text_body'] if cleared else COLORS['text_muted']};font-size:12.5px;")
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
                ui.button("📤 Send v3 + FLS Memo to Legal", on_click=send_legal).props("color=primary")
            elif rv["status"] == "sent":
                ui.label(f"Sent {rv['sent']}").style(f"color:{COLORS['text_muted']};")
                leg_notes = ui.textarea("Legal comments", value=rv.get("notes", "")).classes("w-full")
                if all_clear:
                    def finalize():
                        rv.update({"status": "complete", "received": datetime.now().strftime("%Y-%m-%d %H:%M"), "notes": leg_notes.value})
                        ss["stages"]["legal_signoff"].update({"status": "complete", "completed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
                        ss["current_stage"] = "FINAL"
                        ss["version"] = 4
                        _add_version(ss, "FINAL", f"FINAL — Legal cleared {datetime.now().strftime('%Y-%m-%d %H:%M')}", "Legal")
                        _save_json("script_workflow_state.json", ss)
                        ui.notify("🎉 SCRIPT FINALIZED — Legal cleared.")
                        _refresh()
                    ui.button("⚖️ MARK FINAL — Legal Cleared", on_click=finalize).props("color=primary")
                else:
                    ui.label(f"Clear all {len(fls_items)-cleared_n} remaining FLS items first").style(f"color:{COLORS['warning']};font-size:12px;")
            elif rv["status"] == "complete":
                ui.label("✅ FINAL — Legal Cleared").style("color:#4ADE80;")
                ui.label(f"Cleared: {rv['received']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
    if ss.get("current_stage") == "FINAL":
        ui.markdown("---")
        with ui.card().classes("w-full text-center").style("background:#152A1E;border:2px solid #4ADE80;"):
            ui.label("✅").style("font-size:22px;")
            ui.label("SCRIPT FINALIZED — LEGAL CLEARED").classes("font-bold").style("color:#4ADE80;font-size:18px;")
            ui.label("This is the approved earnings call script. Do not use any other version.").style("color:#4ADE80;font-size:13px;")


def _render_script_workflow_tab():
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

    ui.label("📝 Earnings Script Approval Workflow").classes("text-lg font-bold")
    ui.label("5-stage approval pipeline · CFO numbers in → IR → CFO+CEO+CRO → Consolidation → Legal sign-off").style(f"color:{COLORS['text_muted']};font-size:12px;")

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
                bc, tc, ico, label_tc, name_tc = "#152A1E", "#4ADE80", "✅", "#86EFAC", "#F0FDF4"
            elif status == "active":
                bc, tc, ico, label_tc, name_tc = "#1E2D45", "#60A5FA", "🔵", "#93C5FD", "#EFF6FF"
            else:
                bc, tc, ico, label_tc, name_tc = COLORS["surface_bg"], COLORS["text_muted"], "⬜", COLORS["accent_light2"], COLORS["text_heading"]
            with ui.card().classes("flex-1 text-center").style(f"background:{bc};border:1px solid {COLORS['border']};"):
                ui.label(stage["icon"]).style("font-size:20px;")
                ui.label(stage["label"]).style(f"color:{label_tc};font-size:11px;font-weight:bold;text-transform:uppercase;")
                ui.label(stage["name"]).classes("font-bold").style(f"color:{name_tc};font-size:13px;")
                ui.label(f"{ico} {status.capitalize()}").style(f"color:{tc};font-size:12px;font-weight:600;")

    ui.markdown("---")
    with ui.tabs().classes("w-full") as sw_tabs:
        sw1 = ui.tab("📥 1 · CFO Numbers")
        sw2 = ui.tab("✏️ 2 · IR Review")
        sw3 = ui.tab("👔 3 · CEO+CFO+CRO Review")
        sw4 = ui.tab("🔀 4 · Consolidation")
        sw5 = ui.tab("⚖️ 5 · Legal Sign-Off")

    # Land on whichever tab is actually the workflow's current stage,
    # instead of always defaulting to Tab 1. Previously this was hardcoded
    # to sw1 regardless of ss["current_stage"] — so a CFO/CEO reviewer
    # opening the page while Stage 3 was active would see the read-only
    # Stage 1 numbers-entry form (which looks like a self-contained page,
    # nothing on it hints there's a Stage 3 tab to click) instead of
    # landing on the actual review work waiting for them. FINAL (post
    # legal sign-off) has no tab of its own — stays on Legal Sign-Off,
    # which is where the finalized-script card renders.
    _stage_to_tab = {
        "cfo_numbers": sw1, "ir_review": sw2, "exec_review": sw3,
        "consolidate": sw4, "legal_signoff": sw5, "FINAL": sw5,
    }
    default_sw_tab = _stage_to_tab.get(ss.get("current_stage"), sw1)
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

    if ss.get("versions"):
        ui.markdown("---")
        ui.label("📋 Version History").classes("font-bold")
        for v in reversed(ss["versions"]):
            if "version" in v:
                icon = "🔒" if v["version"] == "FINAL" else "📄"
                ui.label(f"{icon} {v['version']} — {v.get('label','')} · {v.get('created','')} · {v.get('by','—')}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            else:
                # Legacy shape from the earlier simplified port
                ui.label(f"{v.get('completed','')} — {v.get('stage','')}").style(f"color:{COLORS['text_muted']};font-size:12px;")

    ui.markdown("---")
    with ui.expansion("⚠️ Reset Workflow — Start New Quarter").classes("w-full"):
        def reset():
            _save_json("script_workflow_state.json", _blank_script_state())
            ui.notify("Reset. Ready for next quarter.")
            _refresh()
        ui.button("🔄 Reset All Stages", on_click=reset).props("color=negative")


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


def _render_surprise_tracker_tab():
    surprises = _load_json("earnings_surprise_log.json", None)
    if surprises is None:
        surprises = _default_surprises()
        _save_json("earnings_surprise_log.json", surprises)

    ui.label("🎯 Consensus Tracker").classes("text-lg font-bold")
    ui.label("Actual vs consensus vs embedded expectation · Guidance credibility database").style(f"color:{COLORS['text_muted']};font-size:12px;")

    with ui.tabs().classes("w-full") as es_tabs:
        e1 = ui.tab("📊 Beat/Miss History")
        e2 = ui.tab("➕ Log Quarter")
        e3 = ui.tab("🔮 Pre-Call Assessment")
    with ui.tab_panels(es_tabs, value=e1).classes("w-full"):
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
                            ui.label(label).style(f"color:{COLORS['text_muted']};font-size:10.5px;")

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
                            ui.label("✅ BEAT" if beat else "❌ MISS").style(f"color:{'#4ADE80' if beat else '#F87171'};font-weight:bold;")
                        with ui.row().classes("w-full gap-4"):
                            ui.label(f"Actual: ${row['rev_actual']}M").style(f"color:{COLORS['text_body']};font-size:12px;")
                            ui.label(f"vs Consensus: {surp:+.1f}%").style(f"color:{'#4ADE80' if surp>0 else '#F87171'};font-size:12px;")
                            ui.label(f"vs Whisper: {wh_s:+.1f}%").style(f"color:{'#4ADE80' if wh_s>0 else '#F87171'};font-size:12px;")
                            ui.label(f"AH Move: {ah:+.1f}%").style(f"color:{'#4ADE80' if ah>0 else '#F87171'};font-size:12px;")
                            ui.label(f"Implied ±{row['implied_move']*100:.1f}%").style(f"color:{COLORS['text_muted']};font-size:12px;")
                        ui.label(f"Guidance vs embedded: {row.get('guidance_vs_embedded','—')} · "
                                 f"PT changes: {row.get('pt_changes',0)} · Call score: {row.get('call_score','—')}/100").style(
                            f"color:{COLORS['text_muted']};font-size:12px;")
                        if row.get("notes"):
                            ui.label(row["notes"]).style(f"color:{COLORS['text_muted']};font-size:12px;font-style:italic;")

                ui.markdown("---")
                ui.label("Guidance Credibility").classes("font-bold")
                for row in surprises:
                    gve = row.get("guidance_vs_embedded", "—")
                    excess = (row["ah_move"] - row["implied_move"]) * 100
                    icon = "✅" if gve in ["Beat", "Above"] else "🟡" if gve == "In-line" else "⚠️"
                    ui.label(f"{icon} {row['quarter']}: Guidance {gve} embedded · AH "
                             f"{'exceeded' if excess>0 else 'undershot'} implied by {abs(excess):.1f}pp").style(
                        f"color:{COLORS['text_body']};font-size:12.5px;")
            else:
                ui.label("No quarters logged yet.").style(f"color:{COLORS['text_muted']};")

        with ui.tab_panel(e2):
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    s_q = ui.input("Quarter", placeholder="Q2 2026").classes("w-full")
                    s_dt = ui.input("Date (YYYY-MM-DD)", value=CE().get("earnings_date", "")).classes("w-full")
                    s_pc = ui.number("Pre-earnings close ($)", value=0.0, step=0.01)
                    s_imp = ui.number("Implied move %", value=0.0, step=0.5)
                with ui.column().classes("flex-1"):
                    s_ra = ui.number("Actual revenue ($M)", value=0.0, step=0.1)
                    s_rc = ui.number("Consensus ($M)", value=25.1, step=0.1)
                    s_rw = ui.number("Whisper ($M)", value=24.5, step=0.1)
                    s_ea = ui.number("Actual EPS ($)", value=0.0, step=0.01)
                    s_ec = ui.number("EPS consensus ($)", value=0.01, step=0.01)
                with ui.column().classes("flex-1"):
                    s_ah = ui.number("AH move (%)", value=0.0, step=0.1)
                    s_3d = ui.number("3-day move (%)", value=0.0, step=0.1)
                    s_ptn = ui.number("PT changes", value=0)
                    s_pta = ui.number("Avg PT change ($)", value=0.0, step=0.25)
            with ui.row().classes("w-full gap-4"):
                s_gve = ui.select(["Beat", "In-line", "Below"], value="In-line").classes("flex-1").props("label='Guidance vs embedded'")
                s_pre = ui.number("Pre-empt score (0-12)", value=0, min=0, max=12).classes("flex-1")
                s_cs = ui.number("Call score (0-100)", value=0, min=0, max=100).classes("flex-1")
            s_notes = ui.textarea("Notes").classes("w-full")

            def log_quarter():
                if not s_q.value:
                    ui.notify("Quarter is required.", type="warning")
                    return
                data = _load_json("earnings_surprise_log.json", _default_surprises())
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

            ui.button("💾 Log Quarter", on_click=log_quarter).props("color=primary")

        with ui.tab_panel(e3):
            ui.label(f"Pre-Call Assessment — {CE().get('current_quarter','')}").classes("font-bold")
            ui.label(f"Fill BEFORE {CE().get('earnings_date','')} earnings. Captures the embedded expectation for post-call scoring.").style(f"color:{COLORS['text_muted']};font-size:12px;")

            q2_guidance = get_seed_consensus(get_active_client_id()).get("period_guidance", {}).get("Q2 2026E", {})
            guidance_rev = q2_guidance.get("Revenue Est ($M)")

            with ui.row().classes("w-full gap-3"):
                _pc_metric("Street consensus", f"${CT('q2_consensus_rev', 0)}M", "Beat bar")
                _pc_metric("Guidance midpoint", f"${guidance_rev}M" if guidance_rev is not None else CT("fy_guidance", "—"),
                           CT("guidance_vs_street_note", "vs street consensus"))
                _pc_metric("Bar risk", CT("bar_risk_level", "—"), CT("bar_risk_note", "assess vs sector performance"))

            precall = _load_json("q2_precall.json", {})
            with ui.row().classes("w-full gap-4"):
                pc_imp = ui.number("Options implied move %", value=precall.get("implied", 0.0), step=0.5)
                pc_wh = ui.number("Whisper ($M)", value=precall.get("whisper", 24.5), step=0.1)
                pc_30d = ui.number(f"{CT('ticker')} 30d vs FINX (%)", value=precall.get("30d_sector", 0.0), step=0.5)
                pc_si = ui.number("Short interest % float", value=precall.get("short", 0.02), step=0.01)
            pc_notes = ui.textarea("Positioning notes", value=precall.get("notes", "")).classes("w-full")

            def save_precall():
                data = {"implied": pc_imp.value, "whisper": pc_wh.value, "30d_sector": pc_30d.value,
                        "short": pc_si.value, "notes": pc_notes.value, "saved": datetime.now().strftime("%Y-%m-%d %H:%M")}
                _save_json("q2_precall.json", data)
                ui.notify("Saved. Compare to actuals after earnings.")
                _refresh()

            ui.button("💾 Save Pre-Call Assessment", on_click=save_precall).props("color=primary")
            if precall:
                ui.label(f"Pre-call logged {precall.get('saved','')} · Implied ±{precall.get('implied',0):.1f}% · "
                         f"Whisper ${precall.get('whisper',0):.1f}M · 30d vs sector {precall.get('30d_sector',0):+.1f}%").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")


def _pc_metric(label, value, sub):
    with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(str(value)).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")
        ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:10.5px;")


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
    ui.label("🎙️ Call Transcripts").classes("text-lg font-bold")
    ui.label(
        "Archive of ingested earnings call transcripts — full-text searchable, with an AI summary, key quotes, "
        "guidance language, and flagged Q&A risk topics per call. ChorusCall has no public API, so bring the PDF "
        "or pasted text in by hand below; that Q&A risk read then feeds the Markets → IR Risk Dashboard scorecard."
    ).style(f"color:{COLORS['text_muted']};font-size:12px;")

    ui.markdown("---")
    with ui.expansion("➕ Ingest a transcript", value=True).classes("w-full"):
        with ui.row().classes("w-full gap-4"):
            t_quarter = ui.input("Quarter", placeholder="Q1 2026", value=CE().get("current_quarter", "")).classes("flex-1")
            t_date = ui.input("Call date (YYYY-MM-DD)").classes("flex-1")
        ui.label("Upload the PDF exported from ChorusCall:").style(f"color:{COLORS['text_body']};font-size:12px;margin-top:6px;")
        pdf_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
        pasted_text_holder = {"text": None, "filename": None}

        async def handle_pdf_upload(e):
            pdf_status.text = "Extracting text…"
            content = await e.file.read()
            extracted = transcripts.extract_text_from_pdf(content)
            if extracted:
                pasted_text_holder["text"] = extracted
                pasted_text_holder["filename"] = e.file.name
                pdf_status.text = f"✅ Extracted {len(extracted.split()):,} words from {e.file.name}. Click Ingest below."
                pdf_status.style("color:#4ADE80;font-size:11.5px;")
            else:
                pdf_status.text = ("⚠️ Couldn't extract text from that PDF (it may be scanned/image-only). "
                                    "Paste the transcript text below instead.")
                pdf_status.style("color:#F0A830;font-size:11.5px;")

        ui.upload(on_upload=handle_pdf_upload, auto_upload=True).props("accept=.pdf").classes("w-full")

        ui.label("...or paste the transcript text directly:").style(f"color:{COLORS['text_body']};font-size:12px;margin-top:6px;")
        t_paste = ui.textarea(placeholder="Paste the full call transcript text here").classes("w-full").props("rows=6")

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
                      f"Click 🤖 Generate AI Summary below to analyze it.")
            _refresh()

        ui.button("📥 Ingest Transcript", on_click=ingest).props("color=primary").style("margin-top:8px;")

    ui.markdown("---")
    ui.label("🔍 Search across all calls").classes("font-bold")
    with ui.row().classes("w-full gap-2"):
        search_input = ui.input(placeholder="e.g. margin, PayFac, guidance").classes("flex-1")
        search_results = ui.column().classes("w-full")

        def do_search():
            search_results.clear()
            hits = transcripts.search_transcripts(search_input.value)
            with search_results:
                if not search_input.value:
                    return
                if not hits:
                    ui.label("No matches.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                for h in hits:
                    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                        ui.label(f"{h['quarter']} ({h['match_count']} match{'es' if h['match_count'] != 1 else ''})").classes("font-bold").style(f"color:{COLORS['accent_light']};")
                        for snip in h["snippets"]:
                            ui.label(snip).style(f"color:{COLORS['text_muted']};font-size:11.5px;font-style:italic;")

        search_input.on("keydown.enter", do_search)
        ui.button("Search", on_click=do_search).props("dense")

    ui.markdown("---")
    ui.label("📚 Ingested transcripts").classes("font-bold")
    records = transcripts.list_transcripts()
    if not records:
        ui.label("No transcripts ingested yet — use the form above.").style(f"color:{COLORS['text_muted']};font-size:12px;")
        return

    for rec in records:
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("gap-0"):
                    ui.label(f"{rec['quarter']} · {rec.get('call_date') or 'date not set'}").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                    ui.label(f"{rec['word_count']:,} words · uploaded {rec['uploaded_at'][:16].replace('T',' ')}"
                              + (f" · {rec['source_filename']}" if rec.get("source_filename") else "")).style(
                        f"color:{COLORS['text_muted']};font-size:11px;")
                with ui.row().classes("gap-2"):
                    def delete_this(q=rec["quarter"]):
                        transcripts.delete_transcript(q)
                        ui.notify(f"{q} transcript deleted.")
                        _refresh()
                    ui.button("🗑️", on_click=delete_this).props("flat dense")

            if not rec.get("ai_summary"):
                summary_area = ui.column().classes("w-full")

                async def generate_summary(q=rec["quarter"], area=summary_area):
                    with area:
                        area.clear()
                        ui.label("Generating AI summary…").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    result = transcripts.summarize_transcript(q)
                    area.clear()
                    with area:
                        if result:
                            ui.notify(f"{q} summarized.")
                            activity_log.log_event("transcript_summarized", entity=q)
                            _refresh()
                        else:
                            ui.label(
                                "⚠️ Couldn't generate a summary — check that ANTHROPIC_API_KEY is set in .env, "
                                "and that this machine has network access to api.anthropic.com. Try again, or "
                                "review the transcript manually."
                            ).style("color:#F0A830;font-size:12px;")

                ui.button("🤖 Generate AI Summary", on_click=generate_summary).props("flat dense").style("margin-top:6px;")
            else:
                ui.markdown("---")
                ui.label(rec["ai_summary"]).style(f"color:{COLORS['text_body']};font-size:12.5px;")

                key_quotes = rec.get("key_quotes") or []
                if key_quotes:
                    ui.label("Key quotes").classes("font-bold").style("font-size:12px;margin-top:6px;")
                    for kq in key_quotes:
                        ui.label(f"“{kq.get('quote','')}” — {kq.get('speaker','')}").style(
                            f"color:{COLORS['text_muted']};font-size:11.5px;font-style:italic;")

                guidance = rec.get("guidance_language") or []
                if guidance:
                    ui.label("Guidance language").classes("font-bold").style("font-size:12px;margin-top:6px;")
                    for g in guidance:
                        ui.label(f"• {g}").style(f"color:{COLORS['text_body']};font-size:11.5px;")

                topics = rec.get("qa_risk_topics") or []
                if topics:
                    ui.label("Q&A risk topics").classes("font-bold").style("font-size:12px;margin-top:6px;")
                    sev_color = {"HIGH": "#F87171", "MEDIUM": "#F0A830", "LOW": "#94A3B8"}
                    for t in topics:
                        clr = sev_color.get(t.get("severity"), "#94A3B8")
                        ui.label(f"{t.get('severity','?')} · {t.get('topic','')} — {t.get('why','')}").style(f"color:{clr};font-size:11.5px;")
                else:
                    ui.label("No Q&A risk topics flagged by AI review.").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

                ui.label(f"Summarized {rec['summarized_at'][:16].replace('T',' ') if rec.get('summarized_at') else ''}").style(
                    f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:4px;")

                rerun_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

                async def rerun_summary(q=rec["quarter"], status=rerun_status):
                    status.text = "Regenerating…"
                    result = transcripts.summarize_transcript(q)
                    if result:
                        activity_log.log_event("transcript_summarized", entity=q)
                        ui.notify(f"{q} summary regenerated.")
                        _refresh()
                    else:
                        status.text = ("⚠️ Couldn't regenerate — check that ANTHROPIC_API_KEY is set in .env "
                                        "and this machine can reach api.anthropic.com.")
                        status.style("color:#F0A830;font-size:11.5px;")

                ui.button("🔄 Re-run AI Summary", on_click=rerun_summary).props("flat dense")
