"""
core/transcripts.py — earnings call transcript ingestion, storage, search,
and AI summarization. Backs the Earnings page's "Call Transcripts" tab.

Where these come from: USIO's calls are hosted on ChorusCall
(choruscall.com), like most small/mid-cap issuers use. ChorusCall has no
public API for pulling historical call archives, and pulling from it would
need an authenticated portal session this app has no way to hold — so
ingestion here is deliberately upload-based, not a fetcher like
core/sec_filings.py or core/market_data.py. A user downloads/exports the
PDF (or copies the transcript text) from ChorusCall and brings it in
through the Earnings page; this module takes it from there.

One transcript per (client_id, quarter) — call_transcripts table, see
core/db.py. Re-ingesting the same quarter overwrites it (upsert), same
convention as every other table in this app.

Three layers, same shape as core/sec_filings.py / core/market_data.py:
  1. extract_text_from_pdf() — pulls plain text out of an uploaded PDF
     (pypdf). Never raises; returns None on any failure so a bad/scanned
     PDF degrades to "please paste the text" instead of crashing the page.
  2. ingest_transcript() / list_transcripts() / get_transcript() /
     delete_transcript() / search_transcripts() — pure storage + a simple
     substring search across full_text. No network involved.
  3. summarize_transcript() — the one network-dependent piece. Calls the
     Claude API (same urllib.request + core.security.get_anthropic_api_key
     pattern already used in earnings_page.py's script-drafting feature
     and investors_page.py's meeting-notes feature — no new dependency
     needed) to produce a short summary, key quotes, the guidance language
     management used, and a list of Q&A topics analysts pressed on that
     read as risk signals. Returns None on any failure (no key configured,
     no network, bad response) — callers must handle that, never assume
     summarization succeeded. core/risk_scorecard.py's "Q&A Risk Topics"
     indicator reads qa_risk_topics from here when present, and stays GRAY
     when it isn't (no transcript ingested yet, or summarization hasn't
     been run) — same "don't invent it" policy as every other GRAY
     indicator in that module.

Network note: like sec_filings.py and market_data.py, the Claude API call
below has not been exercised against the real network in this sandbox (no
route to api.anthropic.com — only pypi.org is reachable). The parsing/
storage/search logic is unit-tested against a stubbed API response
instead; live behavior needs verifying on a machine with normal internet
access.
"""

import json
import re
import urllib.request
from datetime import datetime

from core import db
from core.security import get_anthropic_api_key


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


# ─────────────────────────────────────────────────────────────────────────
# PDF text extraction
# ─────────────────────────────────────────────────────────────────────────
def extract_text_from_docx(file_bytes):
    """Plain text from a .docx's raw bytes. A .docx is a zip containing
    word/document.xml, so this needs no third-party library (python-docx isn't
    installed) — just stdlib zipfile + ElementTree. Returns None (never raises)
    on any failure, same contract as extract_text_from_pdf.

    Paragraph boundaries are preserved because a call transcript's speaker turns
    are paragraphs; losing them would run every speaker together and make the
    Q&A section unparseable.
    """
    try:
        import io
        import zipfile
        from xml.etree import ElementTree as ET
        ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
        with zipfile.ZipFile(io.BytesIO(file_bytes)) as z:
            root = ET.fromstring(z.read("word/document.xml"))
        paras = []
        for p in root.iter(f"{{{ns}}}p"):
            t = "".join(n.text or "" for n in p.iter(f"{{{ns}}}t")).strip()
            if t:
                paras.append(t)
        text = "\n".join(paras).strip()
        return text or None
    except Exception as e:
        print(f"[transcripts] .docx extraction failed: {e}")
        return None


def extract_text(file_bytes, filename=""):
    """Route to the right extractor by extension; .docx and .pdf both land as
    plain text for ingest_transcript()."""
    low = (filename or "").lower()
    if low.endswith(".docx"):
        return extract_text_from_docx(file_bytes)
    if low.endswith(".pdf"):
        return extract_text_from_pdf(file_bytes)
    try:
        return file_bytes.decode("utf-8", errors="replace").strip() or None
    except Exception:
        return None


def extract_text_from_pdf(file_bytes):
    """Best-effort plain-text extraction from an uploaded PDF's raw bytes.
    Returns None (never raises) on any failure — a scanned/image-only PDF,
    a corrupt file, or pypdf not being installed all degrade to "ask the
    user to paste the text instead" rather than a crashed page."""
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = [p.extract_text() or "" for p in reader.pages]
        text = "\n\n".join(pages).strip()
        return text or None
    except Exception as e:
        print(f"[transcripts] PDF text extraction failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────────────────
def ingest_transcript(full_text, quarter, call_date=None, source="upload", source_filename=None, client_id=None):
    """Store (or overwrite) the transcript for one quarter. Clears any
    previous AI summary/key quotes/risk topics for that quarter, since
    they'd no longer match the new text — call summarize_transcript()
    again after re-ingesting."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        now = datetime.now()
        if pg:
            cur.execute(
                "INSERT INTO call_transcripts (client_id, quarter, call_date, source, source_filename, "
                "full_text, ai_summary, key_quotes, qa_risk_topics, guidance_language, summarized_at, uploaded_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,NULL,NULL,NULL,NULL,NULL,now()) "
                "ON CONFLICT (client_id, quarter) DO UPDATE SET call_date=EXCLUDED.call_date, "
                "source=EXCLUDED.source, source_filename=EXCLUDED.source_filename, full_text=EXCLUDED.full_text, "
                "ai_summary=NULL, key_quotes=NULL, qa_risk_topics=NULL, guidance_language=NULL, "
                "summarized_at=NULL, uploaded_at=EXCLUDED.uploaded_at",
                (cid, quarter, call_date, source, source_filename, full_text),
            )
        else:
            cur.execute(
                "INSERT INTO call_transcripts (client_id, quarter, call_date, source, source_filename, "
                "full_text, ai_summary, key_quotes, qa_risk_topics, guidance_language, summarized_at, uploaded_at) "
                "VALUES (?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,?) "
                "ON CONFLICT(client_id, quarter) DO UPDATE SET call_date=excluded.call_date, "
                "source=excluded.source, source_filename=excluded.source_filename, full_text=excluded.full_text, "
                "ai_summary=NULL, key_quotes=NULL, qa_risk_topics=NULL, guidance_language=NULL, "
                "summarized_at=NULL, uploaded_at=excluded.uploaded_at",
                (cid, quarter, call_date, source, source_filename, full_text, now.isoformat()),
            )
        conn.commit()
    finally:
        conn.close()


def _row_to_dict(row, include_full_text=True):
    (quarter, call_date, source, source_filename, full_text, ai_summary,
     key_quotes, qa_risk_topics, guidance_language, summarized_at, uploaded_at) = row
    out = {
        "quarter": quarter, "call_date": call_date, "source": source,
        "source_filename": source_filename, "ai_summary": ai_summary,
        "summarized_at": str(summarized_at) if summarized_at else None,
        "uploaded_at": str(uploaded_at),
        "key_quotes": key_quotes if isinstance(key_quotes, list) else _json_or_none(key_quotes),
        "qa_risk_topics": qa_risk_topics if isinstance(qa_risk_topics, list) else _json_or_none(qa_risk_topics),
        "guidance_language": guidance_language if isinstance(guidance_language, list) else _json_or_none(guidance_language),
    }
    if include_full_text:
        out["full_text"] = full_text
    else:
        out["word_count"] = len((full_text or "").split())
    return out


def _json_or_none(v):
    if v is None:
        return None
    try:
        return json.loads(v)
    except Exception:
        return None


def list_transcripts(client_id=None):
    """Metadata for every ingested transcript (no full_text — use
    get_transcript() for that), newest quarter first by upload time."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"SELECT quarter, call_date, source, source_filename, full_text, ai_summary, "
            f"key_quotes, qa_risk_topics, guidance_language, summarized_at, uploaded_at "
            f"FROM call_transcripts WHERE client_id = {ph} ORDER BY uploaded_at DESC",
            (cid,),
        )
        return [_row_to_dict(r, include_full_text=False) for r in cur.fetchall()]
    finally:
        conn.close()


def get_transcript(quarter, client_id=None):
    """Full record (including full_text) for one quarter, or None if
    nothing's been ingested for it yet."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"SELECT quarter, call_date, source, source_filename, full_text, ai_summary, "
            f"key_quotes, qa_risk_topics, guidance_language, summarized_at, uploaded_at "
            f"FROM call_transcripts WHERE client_id = {ph} AND quarter = {ph}",
            (cid, quarter),
        )
        row = cur.fetchone()
        return _row_to_dict(row, include_full_text=True) if row else None
    finally:
        conn.close()


def delete_transcript(quarter, client_id=None):
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"DELETE FROM call_transcripts WHERE client_id = {ph} AND quarter = {ph}", (cid, quarter))
        conn.commit()
    finally:
        conn.close()


def search_transcripts(query, client_id=None, context_chars=120):
    """Plain substring search (case-insensitive) across every ingested
    transcript's full_text. Returns one entry per matching quarter with up
    to 3 short snippets showing the match in context — deliberately simple
    (no Postgres full-text-search tsvector, no ranking) since this app's
    realistic volume is a handful of quarters, not an archive that needs a
    real search engine."""
    if not query or not query.strip():
        return []
    q = query.strip().lower()
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"SELECT quarter, call_date, full_text FROM call_transcripts WHERE client_id = {ph}",
            (cid,),
        )
        results = []
        for quarter, call_date, full_text in cur.fetchall():
            if not full_text:
                continue
            lower = full_text.lower()
            if q not in lower:
                continue
            snippets = []
            start = 0
            while len(snippets) < 3:
                idx = lower.find(q, start)
                if idx == -1:
                    break
                s = max(0, idx - context_chars)
                e = min(len(full_text), idx + len(q) + context_chars)
                snippet = full_text[s:e].strip()
                snippets.append(("…" if s > 0 else "") + snippet + ("…" if e < len(full_text) else ""))
                start = idx + len(q)
            results.append({"quarter": quarter, "call_date": call_date, "snippets": snippets,
                             "match_count": lower.count(q)})
        results.sort(key=lambda r: r["match_count"], reverse=True)
        return results
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# AI summarization
# ─────────────────────────────────────────────────────────────────────────
def _call_claude(prompt, max_tokens=1200):
    """Same call shape as earnings_page.py's _call_claude_script and
    investors_page.py's meeting-notes helper — urllib.request straight to
    the Messages API, no SDK dependency. Returns the raw text response, or
    None on any failure (no key configured, no network, non-2xx, malformed
    response)."""
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
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read())
            return result["content"][0]["text"].strip()
    except Exception as e:
        print(f"[transcripts] Claude API call failed: {e}")
        return None


_SUMMARY_PROMPT = """You are helping an Investor Relations team review an earnings call transcript. \
Read the transcript below and return ONLY a JSON object (no markdown fences, no commentary) with these exact keys:

{{
  "summary": "2-3 sentence plain-English summary of the call's key takeaways",
  "key_quotes": [{{"speaker": "name/role if identifiable, else 'Management' or 'Analyst'", "quote": "short verbatim or near-verbatim quote"}}],
  "guidance_language": ["short paraphrase of each specific forward-looking guidance statement management made"],
  "qa_risk_topics": [{{"topic": "short topic name", "severity": "LOW|MEDIUM|HIGH", "why": "one sentence on why this Q&A exchange reads as a risk signal for IR to track"}}]
}}

Include at most 5 key_quotes, at most 8 guidance_language items, and at most 6 qa_risk_topics (only include topics that read as genuine analyst pushback, skepticism, or a repeated/pressed question — routine clarifying questions don't count).

Transcript:
{transcript}
"""


def summarize_transcript(quarter, client_id=None):
    """Runs the Claude summarization pass for an already-ingested
    transcript and saves the result back onto that row. Returns the parsed
    summary dict, or None if there's no transcript for this quarter, no
    API key configured, or the call/parse failed — callers should show a
    clear "couldn't generate a summary" state rather than assume this
    always succeeds."""
    cid = _resolve_client_id(client_id)
    record = get_transcript(quarter, client_id=cid)
    if not record or not record.get("full_text"):
        return None

    # Anthropic's context window comfortably fits a ~90-minute call
    # transcript, but truncate defensively in case of an unusually long
    # upload (multiple calls pasted together, etc.) rather than let an
    # oversized request just fail.
    text = record["full_text"]
    if len(text) > 60000:
        text = text[:60000] + "\n\n[...transcript truncated for length...]"

    raw = _call_claude(_SUMMARY_PROMPT.format(transcript=text))
    if not raw:
        return None

    parsed = _parse_summary_json(raw)
    if not parsed:
        return None

    cid = _resolve_client_id(cid)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        summary = parsed.get("summary", "")
        key_quotes = parsed.get("key_quotes", [])
        qa_risk_topics = parsed.get("qa_risk_topics", [])
        guidance_language = parsed.get("guidance_language", [])
        if pg:
            from psycopg2.extras import Json
            cur.execute(
                "UPDATE call_transcripts SET ai_summary=%s, key_quotes=%s, qa_risk_topics=%s, "
                "guidance_language=%s, summarized_at=now() WHERE client_id=%s AND quarter=%s",
                (summary, Json(key_quotes), Json(qa_risk_topics), Json(guidance_language), cid, quarter),
            )
        else:
            cur.execute(
                "UPDATE call_transcripts SET ai_summary=?, key_quotes=?, qa_risk_topics=?, "
                "guidance_language=?, summarized_at=? WHERE client_id=? AND quarter=?",
                (summary, json.dumps(key_quotes), json.dumps(qa_risk_topics), json.dumps(guidance_language),
                 datetime.now().isoformat(), cid, quarter),
            )
        conn.commit()
    finally:
        conn.close()

    return parsed


# ─────────────────────────────────────────────────────────────────────────
# Post-mortem critique — compares two summarized quarters' qa_risk_topics
# to see what recurred vs. what got fixed. Backs earnings_page.py's Q1
# Lookback tab / Script Canvas Step 2 seeding: today those still read from a
# hand-typed Q1 2026 snapshot (_Q1_TO_Q2_ACTIONS) because only one quarter's
# transcript exists so far; once a real second quarter is ingested and
# summarized, this function lets that critique regenerate automatically
# instead of needing another hand-edit of earnings_page.py every cycle.
# ─────────────────────────────────────────────────────────────────────────
def compute_qa_preemption_delta(prior_quarter, current_quarter, client_id=None):
    """Compare prior_quarter's and current_quarter's qa_risk_topics (both
    must already be ingested AND summarized). A topic present in both is a
    CRITICAL/IMPROVE carry-over (still not pre-empted in the script even
    after being flagged once already); a topic only in prior_quarter is a
    KEEP (whatever was said this time addressed it); a topic only in
    current_quarter is NEW. Returns a list shaped like earnings_page.py's
    _Q1_TO_Q2_ACTIONS (priority/clr/icon/persona_role/q1_finding/action/
    where/impact) so it can be dropped in as a direct replacement there.
    Returns None if either quarter hasn't been summarized yet — callers
    should fall back to a hand-maintained list in that case, not assume
    this always has data to work with."""
    cid = _resolve_client_id(client_id)
    prior = get_transcript(prior_quarter, client_id=cid)
    current = get_transcript(current_quarter, client_id=cid)
    if not prior or not current or not prior.get("qa_risk_topics") or not current.get("qa_risk_topics"):
        return None

    prior_topics = {(t.get("topic") or "").strip().lower(): t for t in prior["qa_risk_topics"]}
    current_topics = {(t.get("topic") or "").strip().lower(): t for t in current["qa_risk_topics"]}

    actions = []
    for key, t in current_topics.items():
        recurring = key in prior_topics
        sev = t.get("severity", "MEDIUM")
        critical = recurring and sev == "HIGH"
        actions.append({
            "priority": "CRITICAL" if critical else ("IMPROVE" if recurring else "NEW"),
            "clr": "#EF4444" if critical else ("#F59E0B" if recurring else "#60A5FA"),
            "icon": "🔴" if critical else ("🟠" if recurring else "💡"),
            # Topic -> persona-section mapping isn't inferable from
            # transcript data alone (that's IR judgment), so this is left
            # unassigned rather than guessed — Step 2 seeding in
            # earnings_page.py only auto-fills when persona_role is set.
            "persona_role": None,
            "q1_finding": t.get("why") or t.get("topic") or "",
            "action": f"Address \"{t.get('topic','')}\" proactively in the script this cycle"
                      + (" — recurring from last quarter" if recurring else ""),
            "where": "Script Generation",
            "impact": "Reduces live Q&A follow-up on this topic" if recurring else "Pre-empts a newly-flagged risk topic",
        })
    for key, t in prior_topics.items():
        if key not in current_topics:
            actions.append({
                "priority": "KEEP", "clr": "#4ADE80", "icon": "🟢", "persona_role": None,
                "q1_finding": f"\"{t.get('topic','')}\" did not recur this quarter",
                "action": "Keep whatever pre-emption language addressed this — it worked",
                "where": "Script Generation", "impact": "Confirms last cycle's fix held",
            })
    return actions


def _parse_summary_json(raw):
    """Claude is asked to return bare JSON but sometimes wraps it in a
    ```json fence anyway — strip that defensively before parsing. Returns
    None (never raises) on anything that doesn't parse into the expected
    shape."""
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
        print(f"[transcripts] Failed to parse AI summary JSON: {e}")
        return None
