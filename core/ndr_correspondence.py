"""core/ndr_correspondence.py — the reply/correspondence trail on an inbound NDR request.

Answers "did we get back to this analyst?" INSIDE the app. Each inbound NDR request
(ndr_requests.json) carries a `correspondence` list of messages sent (and, later, received) plus
a `response_status`, so the Inbound NDR/Meeting Requests list shows Replied / Awaiting at a glance
and the full thread on the item — instead of the IR person hunting through their own Sent folder
(and an app SMTP send never lands in Sent anyway; see core/zoho_mail._append_to_sent).

This module owns only the trail on the request record; sending is done by the caller (zoho_mail /
the reply dialog), which then calls record_reply() to log what went out. The in-app trail is the
authoritative record regardless of whether the Zoho Sent-folder copy succeeds.
"""
from datetime import datetime

from core import activity_log, db

_KEY = "ndr_requests.json"


def _cid(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def _load(cid):
    return db.load_json(_KEY, default=[], client_id=cid) or []


def _save(rows, cid):
    db.save_json(_KEY, rows, client_id=cid)


def _find(rows, request_id):
    return next((r for r in rows if str(r.get("id")) == str(request_id)), None)


def record_reply(request_id, to, subject, body, via="zoho", message_id=None, client_id=None):
    """Log a sent reply onto the NDR request: append to its correspondence trail, flip it to
    'replied', and record an activity event. `message_id` is the sent email's Message-ID, kept so
    an inbound reply can be threaded back to this request. Returns the updated request (or None)."""
    cid = _cid(client_id)
    rows = _load(cid)
    req = _find(rows, request_id)
    if req is None:
        return None
    entry = {
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"), "direction": "out",
        "to": to, "subject": subject, "body": (body or "")[:4000], "via": via,
        "message_id": message_id,
    }
    req.setdefault("correspondence", []).append(entry)
    req["response_status"] = "replied"
    req["replied_at"] = entry["ts"]
    _save(rows, cid)
    activity_log.log_event("email_sent", entity=req.get("firm") or req.get("analyst"),
                           contact=req.get("analyst"), client_id=cid, subject=subject)
    return req


def record_inbound(request_id, sender, subject, body, message_id=None, client_id=None):
    """Log an inbound reply from the analyst onto the request (the IMAP capture path). Kept
    symmetric with record_reply so the trail shows both sides. Does NOT change response_status (a
    reply from them isn't OUR response). Idempotent on message_id — a re-poll won't duplicate."""
    cid = _cid(client_id)
    rows = _load(cid)
    req = _find(rows, request_id)
    if req is None:
        return None
    if message_id and any(c.get("message_id") == message_id
                          for c in (req.get("correspondence") or [])):
        return req                               # already recorded this inbound message
    req.setdefault("correspondence", []).append({
        "ts": datetime.now().strftime("%Y-%m-%d %H:%M"), "direction": "in",
        "from": sender, "subject": subject, "body": (body or "")[:4000], "via": "inbound",
        "message_id": message_id,
    })
    _save(rows, cid)
    return req


def seen_inbound_ids(client_id=None):
    """All inbound Message-IDs already recorded across this client's requests (for poll dedupe)."""
    cid = _cid(client_id)
    ids = set()
    for r in _load(cid):
        for c in (r.get("correspondence") or []):
            if c.get("direction") == "in" and c.get("message_id"):
                ids.add(c["message_id"])
    return ids


def status(req):
    """'replied' if we've sent at least one reply, else 'awaiting'."""
    if req.get("response_status") == "replied" or any(
            c.get("direction") == "out" for c in (req.get("correspondence") or [])):
        return "replied"
    return "awaiting"


def trail(req):
    """The correspondence entries on a request, oldest first (as recorded)."""
    return req.get("correspondence") or []
