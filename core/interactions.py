"""core/interactions.py — the append-only interaction log (CRM data model, layer 3).

"Touches" and "last contact" are NOT editable numbers — they're derived from what
actually happened. Every call, meeting, email or NDR touch is one event; you never
overwrite history, you append to it, so two people logging the same day can't collide.

Interactions are CLIENT-SCOPED (you met a firm *about this issuer*), unlike the global
relationship opinion (quality/note). They key off the canonical account id
(core.accounts), so they line up with the relationship layer on the same account.

Two sources, merged on read:
  • Manual events — logged by the user (a call, an ad-hoc meeting), stored here.
  • NDR-derived events — computed live from ndr_trips (invited / met / declined), so
    the NDR pipeline stays the single source of truth for those and nothing is
    double-materialized.
"""
import uuid
from datetime import date, datetime

from core import db, accounts
from config.client_config import get_active_client_id

_KEY = "crm_interactions"          # per-client list of manually logged events

TYPES = {"meeting": "Meeting", "call": "Call", "email": "Email", "note": "Note"}


def _today():
    return date.today().isoformat()


def _manual(cid):
    return db.load_json(_KEY, [], client_id=cid) or []


def log(account_key, type="note", date=None, who=None, summary=None, source="manual", cid=None):
    """Append one interaction event for an account. Returns the event."""
    cid = cid or get_active_client_id()
    ev = {"id": uuid.uuid4().hex[:12], "account": account_key,
          "type": type if type in TYPES else "note",
          "date": (date or _today()), "who": who or "", "summary": summary or "",
          "source": source, "created_at": datetime.now().isoformat()}
    lst = _manual(cid)
    lst.append(ev)
    db.save_json(_KEY, lst, client_id=cid)
    return ev


def delete(event_id, cid=None):
    """Remove a manually-logged event (NDR-derived events can't be deleted here —
    they follow the pipeline)."""
    cid = cid or get_active_client_id()
    lst = [e for e in _manual(cid) if e.get("id") != event_id]
    db.save_json(_KEY, lst, client_id=cid)


def _ndr_events(account_key, cid):
    """NDR-pipeline touches for this account, derived live from ndr_trips so they're
    never double-stored. A shortlist entry that reached invited+ (or a scheduled
    meeting) is a real touch; a bare 'shortlisted' target is not."""
    out = []
    for t in db.load_json("ndr_trips.json", [], client_id=cid) or []:
        tname = t.get("name") or "NDR"
        tdate = t.get("dates") or t.get("created") or ""
        seen = set()

        def _add(typ, dt, summary, who=""):
            if (tname, typ) in seen:
                return
            seen.add((tname, typ))
            out.append({"id": f"ndr:{tname}:{typ}", "account": account_key, "type": typ,
                        "date": dt or tdate, "who": who, "summary": summary,
                        "source": "ndr", "created_at": ""})

        for s in t.get("shortlist", []):
            nm = s.get("institution")
            if not nm or accounts.resolve(nm, register=False) != account_key:
                continue
            st = (s.get("status") or "").lower()
            if st in ("met", "slotted", "confirmed"):
                _add("meeting", s.get("added_at"), f"{st.title()} — {tname}")
            elif st == "invited":
                _add("email", s.get("added_at"), f"Invited — {tname}")
            elif st == "declined":
                _add("note", s.get("added_at"), f"Declined — {tname}")

        for m in t.get("meetings", []):
            nm = m.get("institution")
            if not nm or accounts.resolve(nm, register=False) != account_key:
                continue
            who = ", ".join(m.get("attendees", []) or []) if isinstance(m.get("attendees"), list) else ""
            day = f" (day {m.get('day')})" if m.get("day") else ""
            _add("meeting", m.get("date"), f"Meeting — {tname}{day}", who)
    return out


def for_account(account_key, cid=None):
    """All events for an account (manual + NDR-derived), newest first."""
    if not account_key:
        return []
    cid = cid or get_active_client_id()
    evs = [e for e in _manual(cid) if e.get("account") == account_key] + _ndr_events(account_key, cid)
    return sorted(evs, key=lambda e: (e.get("date") or ""), reverse=True)


def summary(account_key, cid=None):
    """Derived relationship metrics: {touches, last_contact, events}. This is where
    'touches' and 'last contact' come from — computed, never stored."""
    evs = for_account(account_key, cid)
    dates = [e.get("date") for e in evs if e.get("date")]
    return {"touches": len(evs), "last_contact": max(dates) if dates else None, "events": evs}
