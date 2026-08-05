"""core/shareholder_reply.py — a Regulation FD-guarded draft reply to a retail /
individual shareholder email.

Responding to shareholders is compliance-sensitive: Reg FD prohibits selective
disclosure of material non-public information. This never sends anything — it drafts a
reply grounded ONLY in publicly disclosed facts, flags the compliance-sensitive cases
(a shareholder fishing for undisclosed/forward numbers, or the pre-earnings quiet
period), and hands an editable draft to the IR person to review and send themselves.

Public facts it will reference: the company name/ticker, the next scheduled earnings
date, quiet-period status, and that filings live on EDGAR / the IR site. It will not
state a number, a dividend policy, or any forward view that isn't already public.
"""
import re
from datetime import date, datetime

from config.client_config import CE, CF, CT, get_active_client_id


# Forward-looking / possibly-material-non-public language patterns, used to scan an
# answer BEFORE it's promoted into the public-facing approved-answer KB. Each is a
# (regex, human-readable reason). Heuristic — it flags for human review, never blocks.
_MNPI_PATTERNS = [
    (r"\bon track to\b", "forward commitment"),
    (r"\bwe (?:expect|anticipate|intend|plan|aim)\b", "forward-looking statement"),
    (r"\bwe(?:'re| are) (?:targeting|guiding)\b", "forward target"),
    (r"\b(?:should|will|expect to) (?:reach|grow|deliver|exceed|hit|improve|increase|accelerate)\b",
     "forward projection"),
    (r"\b(?:next|coming|upcoming|following) (?:quarter|year|month|period|half)\b", "future period"),
    (r"\b(?:second half|first half|h2|h1)\b", "half-year outlook"),
    (r"\b(?:guidance|outlook|forecast|projected|projection)\b", "guidance / outlook reference"),
    (r"\b(?:this|current) quarter\b", "current (unreleased) quarter"),
    (r"\bquarter[- ]to[- ]date\b", "quarter-to-date figure"),
    (r"\bso far (?:this|in the)\b", "intra-period progress"),
    (r"\bbefore we report\b", "pre-release reference"),
    (r"\bpreliminary\b", "preliminary / unreleased figure"),
    (r"\bwe(?:'re| are) (?:seeing|tracking)\b", "intra-period trend"),
]


def scan_mnpi(text):
    """Scan a would-be-public answer for forward-looking / possibly material non-public
    language, so the Promote-to-KB flow can WARN before an unreleased statement lands in
    the public-facing knowledge base. Heuristic — flags for human review, does NOT block.
    Returns {flagged, reasons, phrases}."""
    src = text or ""
    reasons, phrases, seen = [], [], set()
    for pat, why in _MNPI_PATTERNS:
        m = re.search(pat, src, re.IGNORECASE)
        if not m:
            continue
        if why not in reasons:
            reasons.append(why)
        ph = m.group(0).strip()
        if ph.lower() not in seen:
            seen.add(ph.lower())
            phrases.append(ph)
    return {"flagged": bool(phrases), "reasons": reasons, "phrases": phrases}


def quiet_period_status(client_id=None):
    """Is the client currently in its pre-earnings quiet period? From the earnings
    calendar's quiet_start / quiet_end (config)."""
    ce = CE()
    qs, qe = ce.get("quiet_start"), ce.get("quiet_end")
    out = {"in_quiet": False, "start": qs, "end": qe}
    try:
        today = date.today()
        s = datetime.strptime(qs, "%Y-%m-%d").date() if qs else None
        e = datetime.strptime(qe, "%Y-%m-%d").date() if qe else None
        if s and e and s <= today <= e:
            out["in_quiet"] = True
    except Exception:
        pass
    return out


def public_facts(client_id=None):
    ce = CE()
    return {
        "name": CT("name"), "ticker": CT("ticker"),
        "next_quarter": ce.get("current_quarter"),
        "earnings_date": ce.get("earnings_date"),
        "last_reported": CF().get("last_quarter"),
        "quiet": quiet_period_status(client_id),
    }


def is_sensitive(extracted, client_id=None):
    """Compliance-sensitive when the shareholder is fishing for material non-public /
    forward info, OR the company is currently in its quiet period."""
    if (extracted or {}).get("seeks_material_nonpublic"):
        return True
    return quiet_period_status(client_id).get("in_quiet", False)


def compliance_note(extracted, client_id=None):
    """Short amber note for the reviewer explaining WHY an item is flagged, or None."""
    q = quiet_period_status(client_id)
    if (extracted or {}).get("seeks_material_nonpublic"):
        return ("This inquiry asks for undisclosed or forward-looking specifics — a Regulation FD "
                "red flag. Do NOT share unreleased numbers or guidance; the draft declines and "
                "points to the next scheduled disclosure. Review before sending.")
    if q.get("in_quiet"):
        return (f"The company is in its pre-earnings quiet period ({q.get('start')} – {q.get('end')}). "
                "Keep the reply to public facts only and defer financial specifics to the release.")
    return None


def _fallback_draft(facts, sensitive):
    ed = facts.get("earnings_date") or "our next scheduled date"
    nq = facts.get("next_quarter") or "the upcoming quarter"
    lines = ["Dear Shareholder,", "",
             f"Thank you for reaching out and for your interest in {facts['name']} ({facts['ticker']})."]
    if sensitive:
        lines += ["",
                  f"As we are in our pre-earnings quiet period (or your question concerns results we have "
                  f"not yet released), we're not able to discuss financial specifics ahead of our next "
                  f"earnings release, scheduled for {ed} ({nq}). We appreciate your understanding."]
    else:
        lines += ["",
                  f"Our next earnings release is scheduled for {ed} ({nq}). Our most recent filings "
                  f"(10-Q / 10-K) and press releases are available on the SEC's EDGAR system and in the "
                  f"Investor Relations section of our website, which is the best source for details on the "
                  f"topics you raised."]
    lines += ["", "We appreciate your continued support.", "",
              "Best regards,", f"Investor Relations — {facts['name']} ({facts['ticker']})"]
    return "\n".join(lines)


def draft_reply(subject, body, extracted, client_id=None):
    """Return {"draft", "sensitive", "note"}. The draft uses public facts only and,
    for compliance-sensitive inquiries, politely declines financial specifics."""
    facts = public_facts(client_id)
    sensitive = is_sensitive(extracted, client_id)
    note = compliance_note(extracted, client_id)

    q = facts["quiet"]
    guardrail_quiet = (f"The company IS currently in its pre-earnings quiet period "
                       f"({q.get('start')}–{q.get('end')}) — politely decline any financial specifics and note "
                       f"results will be released on {facts.get('earnings_date')}." if q.get("in_quiet")
                       else "The company is not currently in a quiet period.")
    try:
        from core import ir_knowledge
        kb = ir_knowledge.context_block(client_id)
    except Exception:
        kb = ""
    prompt = f"""You are drafting a reply on behalf of the Investor Relations team of {facts['name']} \
({facts['ticker']}) to an email from an INDIVIDUAL / RETAIL shareholder.

STRICT REGULATION FD RULES — follow exactly:
- Use ONLY publicly disclosed information. Do NOT provide any material non-public information, forward
  guidance, unreleased quarterly figures, specific numbers, or any selective disclosure.
- If the shareholder asks about undisclosed or forward-looking specifics (e.g. how the current quarter is
  tracking before it is reported), politely DECLINE and point them to the company's next scheduled release.
- Do NOT promise a call or meeting with management, or commit to anything requiring approval.
- Warm, professional, concise (2–4 short paragraphs). Sign as "Investor Relations — {facts['name']}".

APPROVED ANSWERS — pre-vetted and approved by the IR team; you MAY state these directly and in full when
they address the shareholder's question (they are public and approved). For anything NOT covered here or in
the public facts below, do NOT invent — defer to the filings / next release:
{kb or '(none on file — defer substantive questions to the filings)'}

PUBLIC FACTS you may reference:
- Next earnings release: {facts.get('next_quarter')} on {facts.get('earnings_date')}.
- Last reported quarter: {facts.get('last_reported')}.
- Filings (10-Q/10-K, press releases) are on the SEC's EDGAR system and the company's IR website.
- {guardrail_quiet}

The shareholder's email:
Subject: {subject or '(no subject)'}
Body:
{(body or '')[:1500]}

Parsed topic: {(extracted or {}).get('topic')}

Write ONLY the reply body text — no subject line, no salutation placeholders to fill, no commentary."""

    draft = None
    try:
        from core.email_classifier import _call_claude
        raw = _call_claude(prompt, max_tokens=600)
        if raw and raw.strip():
            draft = raw.strip()
    except Exception as exc:
        print(f"[shareholder_reply] draft generation fell back to template: {exc}")
    if not draft:
        draft = _fallback_draft(facts, sensitive)
    return {"draft": draft, "sensitive": sensitive, "note": note}
