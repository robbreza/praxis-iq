"""
core/email_classifier.py — decides what kind of inbound IR email this is,
and pulls out the handful of fields a human needs to act on it, so
core/inbox_queue.py's review cards start pre-filled instead of blank.

Categories (the ones asked for when this was built):
    model               — a covering analyst's updated financial model
    research_note       — a covering analyst's written research note/report.
                          Extraction here is deliberately a "CFA-lens" pass,
                          not just a summary: rating/PT (and whether that's
                          actually a change), valuation method and key
                          assumptions, whether the thesis is in-line with
                          consensus or a variant view, catalysts/risks
                          management should be ready for, and sentiment.
                          The idea is the reviewer (Head of IR) gets enough
                          to decide in seconds whether this is worth
                          circulating further internally, not just "reviewed
                          / not reviewed" — see investors_page.py's
                          _render_pending_inbox_items() for how this renders
                          and what "Internal Use Only" means there. Note:
                          sell-side research is licensed content — that
                          "further circulation" is understood to mean
                          internal (CFO/CEO/board), not external
                          redistribution, which the bank's license won't
                          allow anyway.
    ndr_request         — an analyst asking to slot a management meeting
                          into a non-deal-roadshow city
    conference_invite   — an invitation to present at / attend a conference
    speak_to_management — a request (usually buy-side) for a call/meeting
                          with management
    meeting_confirmation — a reply confirming/scheduling a meeting or call
                          that's already been arranged (as opposed to
                          speak_to_management, which is the initial ask).
                          Ported from app.py's "Scan IRConnect Inbox for
                          Meeting Confirmations" — that version was a
                          bare keyword search over subject lines only, with
                          an ad hoc password prompt on every scan instead of
                          the .env-based IMAP credentials core/mail_gateway.py
                          already uses everywhere else. Folded into this
                          classifier instead so it goes through the same
                          "🔄 Sync IR Inbox" pipeline, gets real field
                          extraction, and is queued for human confirmation
                          like every other category — not auto-logged from a
                          keyword match.
    general             — everything else; not queued for review, filed the
                          same way this module always has (see
                          core/mail_gateway.py)

Same "real logic, graceful degradation" policy as every other AI-assisted
feature in this app (investors_page.py's note structuring, earnings_page.py's
script drafting, core/transcripts.py's call summaries): one Claude call does
BOTH the classification and the field extraction in a single pass (cheaper
and more consistent than two separate calls), using the same urllib.request
+ core.security.get_anthropic_api_key() pattern, same ```json-fence-stripping
defense. If no API key is configured, or the call/parse fails for any
reason, classify_and_extract() falls back to a deterministic keyword
classifier with empty `extracted` — the item still gets queued under the
right category, a human just fills in the fields by hand instead of
reviewing a pre-filled guess. It never raises and never blocks a sync.

Why extraction from a sell-side model is done via an LLM rather than
opening the spreadsheet with a fixed set of cell references: every bank
formats its model differently (that's the whole reason the confirm step
exists at all — see core/consensus.py's docstring). Dumping the sheet's
text and asking a model that's good at reading tables to find "the revenue
estimate for the next unreported quarter" generalizes across bank templates
in a way a hardcoded cell lookup can't. It's still explicitly a guess that
a human confirms or corrects — never written to consensus unattended.
"""

import json
import re
import urllib.request

from core.security import get_anthropic_api_key

CATEGORIES = ("model", "research_note", "ndr_request", "conference_invite",
              "speak_to_management", "meeting_confirmation", "general")

# Per-category extraction schema, spelled out in the prompt so Claude knows
# exactly which keys to fill in (and to use null rather than inventing a
# value) for whichever category it lands on.
_EXTRACTED_SCHEMA_BY_CATEGORY = {
    "model": '{"rating": "Buy"|"Hold"|"Sell"|"Not Rated"|null, "price_target": number|null, '
             '"eps_est": number|null, "revenue_est": number|null (in $M), "ebitda_est": number|null (in $M), '
             '"period": string|null (e.g. "Q2 2026")}',
    "research_note": '{"rating": "Buy"|"Hold"|"Sell"|"Not Rated"|null, "price_target": number|null, '
                      '"prior_price_target": number|null (only if the note explicitly says it is changing from a prior PT), '
                      '"period": string|null (e.g. "Q2 2026", if the note ties its numbers to a forward period), '
                      '"thesis_summary": string|null (2-3 sentence summary of the core thesis/takeaway), '
                      '"valuation_method": string|null (e.g. "DCF", "EV/EBITDA multiple", "sum-of-parts"), '
                      '"key_assumptions": string|null (1-2 sentences on the key assumptions driving the valuation/thesis), '
                      '"variant_view": "in-line with consensus"|"variant/contrarian"|null, '
                      '"catalysts_risks": string|null (catalysts or risks the analyst flags that management should be ready to address), '
                      '"sentiment": "Bullish"|"Neutral"|"Bearish"|null}',
    "ndr_request": '{"city": string|null, "metro": string|null (broader metro/region name if identifiable), '
                    '"reason": string|null (why they want the meeting)}',
    "conference_invite": '{"event_name": string|null, "date": string|null (YYYY-MM-DD if identifiable), '
                          '"location": string|null, "organizer": string|null}',
    "speak_to_management": '{"requested_contact": string|null (e.g. "CFO", "CEO", "IR"), '
                            '"topic": string|null, "urgency": string|null}',
    "meeting_confirmation": '{"contact_or_fund": string|null (who the meeting is with, if not already clear from '
                             'sender), "date": string|null (YYYY-MM-DD if identifiable), "time": string|null, '
                             '"meeting_type": string|null (e.g. "1x1 call", "conference call", "video call"), '
                             '"notes": string|null}',
    "general": "{}",
}

def _build_prompt(sender_kind, subject, attachment_names, body, attachment_text):
    """Built at call time (not as a module-level .format() template) — the
    per-category schemas below contain their own literal `{`/`}` characters
    (they're JSON-shape descriptions), so chaining this through a second
    str.format() pass would misparse them as format placeholders. An
    f-string sidesteps that entirely: every value here is substituted
    exactly once, schema braces included, with no risk of a stray
    placeholder being interpreted twice."""
    s = _EXTRACTED_SCHEMA_BY_CATEGORY
    return f"""You are triaging one email received in a public company's investor-relations inbox (IRConnect@<company>).

Sender kind: {sender_kind} (an "analyst" is sell-side equity research covering the stock; "institution" is a buy-side investor/prospect; "unknown" means neither list matched).
Subject: {subject}
Attachment filename(s): {attachment_names}
Body (may be truncated):
---
{body}
---

Classify this email into exactly one category:
- "model": a covering analyst's updated financial model (spreadsheet of estimates), or its content is clearly financial-model data.
- "research_note": a covering analyst's written research note/report (thesis, commentary, rating/PT change) — not a model.
  If you classify as research_note, read it the way a CFA charterholder would: pull out the rating and price target
  (and note the prior PT only if the note itself says it's changing from one), the valuation method and the key
  assumptions behind it, whether the thesis is in-line with consensus or a variant/contrarian view, any catalysts or
  risks flagged that management should be ready to address, and the overall sentiment. Never invent a rating, PT, or
  method that isn't actually stated or clearly implied in the text.
- "ndr_request": an analyst asking to arrange a management meeting/roadshow stop in a specific city for their clients.
- "conference_invite": an invitation to present at, attend, or confirm attendance at a conference/event.
- "speak_to_management": a request for a call or meeting with company management (not tied to a roadshow or conference).
- "meeting_confirmation": confirms, schedules, or reschedules a meeting/call that's already been arranged (e.g.
  "confirming our call for Tuesday at 2pm", a calendar invite reply, "looking forward to the 1x1 next week") —
  distinct from speak_to_management, which is the initial request for a meeting, not a confirmation of one already set up.
- "general": anything else (routine correspondence, thank-yous, out-of-office, unrelated).

Attachment content, if any was extracted (may be empty or truncated):
---
{attachment_text}
---

Respond with ONLY strict JSON, no markdown fence, no commentary, in exactly this shape:
{{"category": "<one of the seven category strings above>", "extracted": <the fields object for that category, following its schema below — use null for anything not clearly present, never invent a number>}}

Schemas per category (use the one matching your chosen category):
model: {s['model']}
research_note: {s['research_note']}
ndr_request: {s['ndr_request']}
conference_invite: {s['conference_invite']}
speak_to_management: {s['speak_to_management']}
meeting_confirmation: {s['meeting_confirmation']}
general: {{}}
"""


def _call_claude(prompt, max_tokens=600):
    """Same call shape as core/transcripts.py's _call_claude — urllib.request
    straight to the Messages API. Returns raw text, or None on any failure
    (no key configured, no network, non-2xx, malformed response)."""
    api_key = get_anthropic_api_key()
    if not api_key:
        return None
    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json", "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
            return result["content"][0]["text"].strip()
    except Exception as e:
        print(f"[email_classifier] Claude call failed: {e}")
        return None


def _parse_json(raw):
    text = raw.strip()
    fence_match = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1)
    try:
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except Exception as e:
        print(f"[email_classifier] Failed to parse AI classification JSON: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# Attachment -> text, so Claude has something to read for extraction.
# Best-effort, small char budgets — this is triage input, not a full ingest.
# ─────────────────────────────────────────────────────────────────────────
def _extract_attachment_text(filename, content_type, file_bytes, char_budget=4000):
    import os
    ext = os.path.splitext(filename or "")[1].lower()
    try:
        if ext in (".xlsx", ".xlsm"):
            return _dump_xlsx(file_bytes, char_budget)
        if ext == ".xls":
            return _dump_xlsx(file_bytes, char_budget)  # pandas picks the right engine
        if ext == ".csv":
            text = file_bytes.decode("utf-8", errors="replace")
            return text[:char_budget]
        if ext == ".pdf":
            from core.transcripts import extract_text_from_pdf
            text = extract_text_from_pdf(file_bytes)
            return (text or "")[:char_budget]
    except Exception as e:
        print(f"[email_classifier] Couldn't extract text from {filename}: {e}")
    return ""


def _dump_xlsx(file_bytes, char_budget):
    """Cell-by-cell text dump of every sheet — deliberately not trying to
    interpret layout (that's what Claude is for). Truncated hard at
    char_budget since a real model workbook can be huge and this is only
    ever used as triage input, not the AI note-ingestion path."""
    import io
    import pandas as pd
    buf = io.BytesIO(file_bytes)
    sheets = pd.read_excel(buf, sheet_name=None, header=None)
    lines = []
    for name, df in sheets.items():
        lines.append(f"[Sheet: {name}]")
        for _, row in df.iterrows():
            cells = [str(v) for v in row.tolist() if str(v) not in ("nan", "None", "")]
            if cells:
                lines.append(" | ".join(cells))
        if sum(len(l) for l in lines) > char_budget:
            break
    return "\n".join(lines)[:char_budget]


# ─────────────────────────────────────────────────────────────────────────
# Fallback — no API key / call failed. Deterministic keyword rules, no
# extraction (extracted stays {}). Ordered most-specific-first.
# ─────────────────────────────────────────────────────────────────────────
_MODEL_EXTENSIONS = (".xlsx", ".xls", ".xlsm", ".csv")


def _fallback_classify(subject, body, attachments, sender_kind):
    import os
    text = f"{subject}\n{body}".lower()
    filenames = [a[0] for a in attachments]
    has_model_ext = any(os.path.splitext(f or "")[1].lower() in _MODEL_EXTENSIONS for f in filenames)
    has_pdf = any(os.path.splitext(f or "")[1].lower() == ".pdf" for f in filenames)

    if sender_kind == "analyst" and has_model_ext:
        return "model", {}
    if sender_kind == "analyst" and has_pdf and "model" in text:
        return "model", {}
    if any(kw in text for kw in ("non-deal roadshow", "non deal roadshow", " ndr ", "ndr,", "ndr.", "roadshow")):
        return "ndr_request", {}
    if any(kw in text for kw in ("conference", "invite you to present", "investor day", "fireside chat")):
        return "conference_invite", {}
    if sender_kind == "analyst" and (has_pdf or "research note" in text or "initiating coverage" in text or "report attached" in text):
        return "research_note", {}
    if any(kw in text for kw in ("schedule a call", "speak with", "spe