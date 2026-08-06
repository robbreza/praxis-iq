"""core/sales_pipeline.py — Praxis Point's OWN sales pipeline for IRconnect prospects.

Two lead sources feed one board, under the internal 'praxis' tenant (the same tenant the
website-traffic analyzer writes to):

  * INBOUND  — someone came to praxispointir.com and identified themselves (a demo request,
               a gated download). These are the hottest leads and always sort to the top.
  * OUTBOUND — a company we went and found via the prospect screener → IR-contact flow.

Each lead moves through explicit stages (identified → contacted → replied → meeting → demo →
won / lost). Reply detection is MANUAL by design — a human marks "Replied" (no inbox scraping).
Every stage that expects a next action carries a follow-up date; overdue ones surface as
reminders. Nothing here sends email; the Console email dialogs do that and log a touch back.
"""
from datetime import date, datetime, timezone

from core import db, web_flow

PRAXIS_TENANT = "praxis"
_KEY = "sales_pipeline.json"

# Ordered lifecycle. 'won'/'lost' are terminal (drop out of the active board + reminders).
STAGES = ["identified", "contacted", "replied", "meeting", "demo", "won", "lost"]
OPEN_STAGES = ["identified", "contacted", "replied", "meeting", "demo"]
_STAGE_ORDER = {s: i for i, s in enumerate(STAGES)}

# Default days until the next nudge, per stage. Terminal stages get no follow-up.
FOLLOWUP_DAYS = {"contacted": 5, "replied": 2, "meeting": 3, "demo": 3}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _today():
    return date.today().isoformat()


def _load():
    rows = db.load_json(_KEY, default=[], client_id=PRAXIS_TENANT)
    return rows if isinstance(rows, list) else []


def _save(rows):
    db.save_json(_KEY, rows, client_id=PRAXIS_TENANT)


def _company_key(company, ticker=None):
    if ticker:
        return ticker.upper()
    return web_flow._org_key(company or "") or (company or "").strip().lower()


def lead_id(source, company, ticker=None):
    """Stable id so re-syncing inbound traffic or re-tracking a prospect updates the same row."""
    return f"{'in' if source == 'inbound' else 'out'}:{_company_key(company, ticker)}"


def _plus_days(days):
    from datetime import timedelta
    return (date.today() + timedelta(days=days)).isoformat()


def _find(rows, lid):
    return next((r for r in rows if r.get("id") == lid), None)


def _upsert_into(rows, source, company, ticker=None, email=None, contact_name=None,
                 contact_title=None, demo_request=False, notes=None, domain=None,
                 market_cap=None):
    """Add/merge a lead in the given `rows` list (no I/O). Returns the lead dict."""
    lid = lead_id(source, company, ticker)
    lead = _find(rows, lid)
    if lead is None:
        lead = {
            "id": lid, "source": source, "company": company, "ticker": ticker,
            "email": email, "contact_name": contact_name, "contact_title": contact_title,
            "domain": domain, "market_cap": market_cap,
            "demo_request": bool(demo_request), "stage": "identified", "owner": None,
            "created_at": _now(), "last_touch": None, "next_follow_up": None,
            "notes": notes or "", "activity": [], "onboarded_cid": None,
        }
        rows.append(lead)
    else:
        # refresh facts, keep the more specific value if we already had one
        lead["company"] = company or lead.get("company")
        lead["ticker"] = ticker or lead.get("ticker")
        lead["email"] = email or lead.get("email")
        lead["contact_name"] = contact_name or lead.get("contact_name")
        lead["contact_title"] = contact_title or lead.get("contact_title")
        lead["domain"] = domain or lead.get("domain")
        lead["market_cap"] = market_cap if market_cap is not None else lead.get("market_cap")
        lead["demo_request"] = bool(lead.get("demo_request")) or bool(demo_request)
        if notes:
            lead["notes"] = notes
    return lead


def upsert_lead(source, company, ticker=None, email=None, contact_name=None,
                contact_title=None, demo_request=False, notes=None, domain=None,
                market_cap=None):
    """Add a lead, or merge fresh facts into an existing one, and persist. Never disturbs a
    lead's stage / owner / follow-up / activity — those are workflow state, not facts."""
    rows = _load()
    lead = _upsert_into(rows, source, company, ticker, email, contact_name,
                        contact_title, demo_request, notes, domain, market_cap)
    _save(rows)
    return lead


def add_outbound(enrich):
    """Track a prospect from core.ir_contact.enrich() output (the screener detail dialog)."""
    return upsert_lead(
        "outbound",
        company=enrich.get("company") or enrich.get("ticker"),
        ticker=enrich.get("ticker"),
        email=enrich.get("suggested_email"),
        contact_name=enrich.get("ir_name"),
        contact_title=enrich.get("ir_title") or (
            "CFO (default IR contact)" if enrich.get("ir_kind") == "cfo" else None),
        domain=enrich.get("domain"),
        market_cap=enrich.get("market_cap"),
    )


def mark_onboarded(lid, cid):
    """Record that a won lead was onboarded as client tenant `cid` (so the board shows it and
    the hand-off can't be triggered twice). Ensures the stage is 'won'."""
    rows = _load()
    lead = _find(rows, lid)
    if lead is None:
        return None
    lead["onboarded_cid"] = cid
    lead["stage"] = "won"
    lead["next_follow_up"] = None
    lead["activity"] = (lead.get("activity") or []) + [
        {"ts": _now(), "kind": "onboarded", "note": f"onboarded as client '{cid}'"}]
    _save(rows)
    return lead


def set_stage(lid, stage, save=True):
    """Move a lead to `stage`, log it, and (re)set the follow-up date from the stage default.
    Terminal stages clear the follow-up so they drop out of reminders."""
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    rows = _load()
    lead = _find(rows, lid)
    if lead is None:
        return None
    if lead.get("stage") != stage:
        lead["stage"] = stage
        lead["activity"] = (lead.get("activity") or []) + [
            {"ts": _now(), "kind": "stage", "note": f"→ {stage}"}]
        lead["next_follow_up"] = _plus_days(FOLLOWUP_DAYS[stage]) if stage in FOLLOWUP_DAYS else None
    if save:
        _save(rows)
    return lead


def mark_replied(lid):
    """Manual reply-marking — the honest alternative to scraping the inbox."""
    return set_stage(lid, "replied")


def log_touch(lid, kind="email", note=None, advance_to="contacted"):
    """Record an outbound touch (an email sent / a call). Stamps last_touch, appends to the
    activity log, and — if the lead is still merely 'identified' — advances it to 'contacted'
    and starts the follow-up clock. Reused by the Console email dialogs."""
    rows = _load()
    lead = _find(rows, lid)
    if lead is None:
        return None
    lead["last_touch"] = _now()
    lead["activity"] = (lead.get("activity") or []) + [
        {"ts": _now(), "kind": kind, "note": note or ""}]
    if advance_to and lead.get("stage") == "identified":
        lead["stage"] = advance_to
        if advance_to in FOLLOWUP_DAYS:
            lead["next_follow_up"] = _plus_days(FOLLOWUP_DAYS[advance_to])
    _save(rows)
    return lead


def set_follow_up(lid, when):
    """Set/snooze the next-follow-up date (ISO 'YYYY-MM-DD', or None to clear)."""
    rows = _load()
    lead = _find(rows, lid)
    if lead is None:
        return None
    lead["next_follow_up"] = when or None
    _save(rows)
    return lead


def set_owner(lid, owner):
    rows = _load()
    lead = _find(rows, lid)
    if lead is None:
        return None
    lead["owner"] = owner or None
    _save(rows)
    return lead


def ingest_inbound(save=True):
    """Fold identified praxispointir.com visitors (core.web_ingest / web_flow) into the pipeline
    as INBOUND leads. Idempotent: an existing lead keeps its stage/activity, only facts refresh.
    Returns the number of NEW leads created."""
    visitors = db.load_json("web_flow_visitors.json", default=[], client_id=PRAXIS_TENANT) or []
    rows = _load()
    existing = {r["id"] for r in rows}
    created = 0
    for v in visitors:
        if (v.get("category") or "") == "New — unidentified" or not (v.get("org") or "").strip():
            continue
        demo = bool(v.get("demo_request")) or ("Demo request" in (v.get("downloads") or []))
        lid = lead_id("inbound", v.get("org"), v.get("ticker"))
        if lid not in existing:
            created += 1
        _upsert_into(rows, "inbound", company=v.get("org"), ticker=v.get("ticker"),
                     email=v.get("email"), demo_request=demo)
    if save:
        _save(rows)
    return created


def is_overdue(lead, today=None):
    nf = lead.get("next_follow_up")
    if not nf or lead.get("stage") in ("won", "lost"):
        return False
    return nf <= (today or _today())


def _priority(lead, today=None):
    """Sort key (ascending = most urgent first). Inbound demo requests always win, then
    overdue follow-ups, then other open inbound, then other open, then terminal."""
    stage = lead.get("stage")
    if stage in ("won", "lost"):
        return (9, 0, "")
    open_early = stage in ("identified", "contacted")
    if lead.get("source") == "inbound" and lead.get("demo_request") and open_early:
        rank = 0
    elif is_overdue(lead, today):
        rank = 1
    elif lead.get("source") == "inbound":
        rank = 2
    else:
        rank = 3
    # within a rank: soonest follow-up first (blank sorts last), then stage order
    nf = lead.get("next_follow_up") or "9999-99-99"
    return (rank, _STAGE_ORDER.get(stage, 99), nf)


def list_leads(today=None):
    return sorted(_load(), key=lambda l: _priority(l, today))


def due_followups(today=None):
    """Open leads whose follow-up is due (reminders) OR inbound demo requests not yet contacted."""
    today = today or _today()
    out = []
    for l in _load():
        if l.get("stage") in ("won", "lost"):
            continue
        if is_overdue(l, today) or (
                l.get("source") == "inbound" and l.get("demo_request")
                and l.get("stage") == "identified"):
            out.append(l)
    return sorted(out, key=lambda l: _priority(l, today))


def summary(today=None):
    rows = _load()
    return {
        "total": len(rows),
        "open": sum(1 for r in rows if r.get("stage") in OPEN_STAGES),
        "inbound": sum(1 for r in rows if r.get("source") == "inbound"),
        "due": len(due_followups(today)),
        "won": sum(1 for r in rows if r.get("stage") == "won"),
        "by_stage": {s: sum(1 for r in rows if r.get("stage") == s) for s in STAGES},
    }
