"""
core/inbox_queue.py — the one pending-items list for everything
core/mail_gateway.py routes out of the IR inbox: sell-side models, research
notes, NDR requests, conference invites, and speak-to-management requests
(see core/email_classifier.py for how a message lands in one of those
buckets). One shared queue rather than a separate JSON blob per category,
so investors_page.py has a single "here's what's waiting on you" list to
render instead of five.

Each item is intentionally generic — category, who it's from, what arrived
(if a file was attached), and whatever core/email_classifier.py managed to
extract — because what "confirm" means is different per category and
belongs to whichever page/module already owns that destination data, not
to this module:
    model                -> core/consensus.py's confirm_model_review()
                             writes into consensus estimates
    research_note        -> investors_page.py just marks it reviewed
    ndr_request           -> investors_page.py appends into ndr_requests.json
                             (the existing Inbound NDR/Meeting Requests list)
    conference_invite     -> investors_page.py appends into the Calendar's
                             own conference list
    speak_to_management  -> investors_page.py appends into
                             scheduled_meetings.json (Meeting Hub)
This module only owns the queue itself: enqueue, list pending, mark
confirmed (with whatever free-form outcome the caller wants recorded, e.g.
"created NDR request for Boston"), and dismiss. Backed by
core.db.load_json/save_json("inbox_queue.json") — the same lightweight
JSON-blob convention as scheduled_meetings.json / post_meeting_notes.json /
script_workflow_state.json elsewhere in this app; a few dozen entries at a
time doesn't need its own SQL table.
"""

import uuid
from datetime import datetime

from core import activity_log, db

_QUEUE_KEY = "inbox_queue.json"


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def _load_queue(client_id):
    return db.load_json(_QUEUE_KEY, [], client_id=client_id) or []


def _save_queue(queue, client_id):
    db.save_json(_QUEUE_KEY, queue, client_id=client_id)


def _find(queue, item_id):
    return next((q for q in queue if q.get("id") == item_id), None)


def list_pending_items(category=None, client_id=None):
    """Pending (not yet confirmed/dismissed) items, newest first. Filter to
    one category, or leave None for everything."""
    cid = _resolve_client_id(client_id)
    queue = _load_queue(cid)
    pending = [q for q in queue if q.get("status") == "pending" and (category is None or q.get("category") == category)]
    return list(reversed(pending))


def get_item(item_id, client_id=None):
    cid = _resolve_client_id(client_id)
    return _find(_load_queue(cid), item_id)


def list_items_by_category(category, client_id=None):
    """Every item ever received in this category — pending, confirmed, AND
    dismissed — newest first. Unlike list_pending_items (which is for the
    "waiting on you" review queue and deliberately drops anything already
    actioned), this is for features that want the historical record, e.g.
    earnings_page.py's Q&A prep pulling every research_note's extracted
    catalysts/risks regardless of whether that note has since been marked
    reviewed."""
    cid = _resolve_client_id(client_id)
    queue = _load_queue(cid)
    items = [q for q in queue if q.get("category") == category]
    return list(reversed(items))


def enqueue_item(category, contact, firm, subject, extracted=None, doc_id=None,
                  filename=None, source="email_sync", client_id=None):
    """Called by core/mail_gateway.py once per routed message. `extracted`
    is whatever core/email_classifier.py pulled out (may be {} if no API
    key was configured or nothing could be found) — the review UI prefills
    from it and a human corrects/confirms rather than this ever writing
    anywhere unattended."""
    cid = _resolve_client_id(client_id)
    queue = _load_queue(cid)
    entry = {
        "id": str(uuid.uuid4()), "category": category, "contact": contact, "firm": firm,
        "subject": subject, "extracted": extracted or {}, "doc_id": doc_id, "filename": filename,
        "source": source, "status": "pending", "received_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    queue.append(entry)
    _save_queue(queue, cid)
    activity_log.log_event(f"{category}_email_received", entity=firm or contact, contact=contact, filename=filename)
    return entry["id"]


def mark_confirmed(item_id, outcome=None, client_id=None):
    """Caller (investors_page.py, or core/consensus.py for the model
    category) has already written the confirmed data into wherever it
    belongs — this just closes out the queue entry. `outcome` is a free-text
    note of what was done with it (e.g. "Added to Calendar as Sep 8 event"),
    kept for the audit trail but not required. Returns False if item_id
    doesn't exist or was already actioned."""
    cid = _resolve_client_id(client_id)
    queue = _load_queue(cid)
    entry = _find(queue, item_id)
    if entry is None or entry.get("status") != "pending":
        return False
    entry.update({"status": "confirmed", "outcome": outcome,
                  "confirmed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
    _save_queue(queue, cid)
    return True


def dismiss_item(item_id, client_id=None):
    cid = _resolve_client_id(client_id)
    queue = _load_queue(cid)
    entry = _find(queue, item_id)
    if entry is None or entry.get("status") != "pending":
        return False
    entry.update({"status": "dismissed", "dismissed_at": datetime.now().strftime("%Y-%m-%d %H:%M")})
    _save_queue(queue, cid)
    return True
