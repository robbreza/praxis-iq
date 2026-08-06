"""core/lead_outreach.py — a personalized outreach email draft for a website lead.

A visitor to praxispointir.com who self-identified (or whose company we resolved) is a
prospective CLIENT. This drafts a short, warm outreach email from what they actually did
on the site — company, whether they're public, the pages they viewed, what they downloaded,
whether they requested a demo — for the operator to review and SEND themselves from the
Console. IRconnect never auto-sends. AI-drafted, with a deterministic activity-aware fallback.

It also builds a compliant LinkedIn people-search URL for a manual lookup (LinkedIn has no
open API and scraping violates its terms — a search link is the honest, ToS-safe option).
"""
import re
from urllib.parse import quote

_PAGE_NAMES = {
    "/": "the homepage", "/index": "the homepage",
    "/product": "the product overview", "/services": "services",
    "/security": "security and data", "/customers": "customers",
    "/about": "about", "/demo": "the demo page", "/pricing": "pricing", "/privacy": "privacy",
}


def _page_name(path):
    p = (path or "").split("?")[0].rstrip("/") or "/"
    p = re.sub(r"\.html?$", "", p)
    return _PAGE_NAMES.get(p) or p


def pages_phrase(paths):
    """A human phrase for the distinct pages viewed, e.g. 'the product overview and pricing'."""
    names, seen = [], set()
    for p in (paths or []):
        n = _page_name(p)
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return ", ".join(names[:-1]) + f", and {names[-1]}"


def name_from_email(email):
    """Best-effort human name from an email local part (robert.breza -> Robert Breza)."""
    local = (email or "").split("@")[0]
    local = re.sub(r"\d+", "", re.sub(r"[._-]+", " ", local)).strip()
    return " ".join(w.capitalize() for w in local.split()) if local else ""


def linkedin_search_url(visitor):
    """A LinkedIn people-search URL for a MANUAL lookup (compliant — it's just a search link)."""
    who = name_from_email(visitor.get("email"))
    org = "" if visitor.get("org") in (None, "New — unidentified") else (visitor.get("org") or "")
    kw = " ".join(x for x in (who, org) if x).strip() or org or "IRconnect"
    return "https://www.linkedin.com/search/results/people/?keywords=" + quote(kw)


def _org(visitor):
    o = visitor.get("org")
    return None if o in (None, "New — unidentified") else o


def _fallback(visitor):
    org = _org(visitor)
    demo = visitor.get("demo_request")
    pages = pages_phrase(visitor.get("paths"))
    subject = ("Following up on your IRconnect demo request" if demo
               else (f"IRconnect for {org}" if org else "IRconnect — a quick hello"))
    opener = ("Thanks for requesting a demo of IRconnect." if demo
              else "Thanks for taking a look at IRconnect.")
    interest = f" It looked like {pages} caught your eye." if pages and not demo else ""
    body = (f"Hi,\n\n{opener}{interest} We help investor relations teams compute the work behind the "
            "IR calendar — investor targeting, guidance analytics, earnings-script prep, and risk "
            "monitoring — from real, disclosed data.\n\nI'd be glad to give you a short walkthrough. "
            "Do you have 20 minutes this week?\n\nBest regards,\nPraxis Point\npraxispointir.com")
    return {"subject": subject, "body": body}


def draft_email(visitor):
    """{subject, body} personalized to the lead's activity. AI-drafted; deterministic fallback."""
    org = _org(visitor)
    activity = []
    if org:
        activity.append(f"Company: {org}" + (f" (public, {visitor['ticker']})" if visitor.get("ticker") else ""))
    if visitor.get("demo_request"):
        activity.append("Requested a demo via the site form")
    pages = pages_phrase(visitor.get("paths"))
    if pages:
        activity.append(f"Pages viewed: {pages}")
    dls = [d for d in (visitor.get("downloads") or []) if d and d != "Demo request"]
    if dls:
        activity.append("Downloaded: " + ", ".join(dls))
    if visitor.get("intent_label"):
        activity.append(f"Engagement level: {visitor['intent_label']}")
    activity_str = "\n".join(f"- {a}" for a in activity) or "- (minimal activity on the site)"

    prompt = f"""Write a SHORT, warm B2B outreach email from the Praxis Point team to a prospective \
client who visited our marketing site praxispointir.com. praxispointir.com sells IRconnect, an \
investor-relations software platform. Here is what the visitor did on the site:
{activity_str}

Rules:
- 3-4 short sentences. Warm and professional, not salesy or pushy.
- If they requested a demo, thank them for that and offer to schedule it. Otherwise reference their \
interest naturally — do NOT be creepy or recite exactly which pages they visited as if you surveilled them.
- Do NOT invent facts about the company, and do not promise specific outcomes. No made-up names.
- End with a soft ask for a short call, and sign as "Praxis Point".
- Output EXACTLY: a first line "SUBJECT: <subject>", then a blank line, then the plain-text body."""
    try:
        from core.email_classifier import _call_claude
        raw = _call_claude(prompt, max_tokens=350)
        if raw and raw.strip():
            m = re.match(r"\s*subject:\s*(.+?)\n(.*)", raw.strip(), re.I | re.S)
            if m:
                return {"subject": m.group(1).strip(), "body": m.group(2).strip()}
            return {"subject": _fallback(visitor)["subject"], "body": raw.strip()}
    except Exception as exc:
        print(f"[lead_outreach] AI draft fell back to template: {exc}")
    return _fallback(visitor)
