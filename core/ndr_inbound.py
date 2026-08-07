"""core/ndr_inbound.py — capture analyst REPLIES to NDR replies we sent, and thread them back
onto the originating request (closing the loop the correspondence trail opened).

We send NDR replies from the Zoho account (core/zoho_mail), so the analyst's reply lands in that
same mailbox. This polls it over IMAP and matches each inbound message to a request:
  1. by THREADING — the reply's In-Reply-To / References carry the Message-ID we stamped on our
     sent reply (the reliable path);
  2. failing that, by SENDER — the from-address matches someone we replied to, or the request's
     own recorded sender/analyst email.
Matched messages are logged via ndr_correspondence.record_inbound (idempotent on Message-ID), so
the request's trail shows both sides. The matching is pure and unit-tested; the IMAP fetch is a
thin wrapper. Assumes the single shared Zoho mailbox receives these replies (true in the current
single-account setup; a per-client IR mailbox would key off MAIL_IMAP_* instead).
"""
import email.utils
import re
from datetime import datetime, timedelta

from core import ndr_correspondence, zoho_mail

_MSGID_RE = re.compile(r"<[^>]+>")


def _ids(*headers):
    """All <...> message-ids across the given header strings."""
    out = []
    for h in headers:
        if h:
            out.extend(_MSGID_RE.findall(h))
    return out


def build_index(client_ids):
    """Cross-tenant lookup for matching inbound replies:
      sent_by_msgid: {our_sent_Message-ID: (client_id, request_id)}
      req_by_sender: {sender_email_lower: (client_id, request_id)}  (who we replied to, or the
                     request's own recorded email)
      seen:          {inbound Message-IDs already recorded}  (dedupe)."""
    sent_by_msgid, req_by_sender, seen = {}, {}, set()
    for cid in client_ids:
        for r in ndr_correspondence._load(cid):
            rid = r.get("id")
            for e in (r.get("email") or r.get("sender_email") or r.get("analyst_email") or "",):
                if e:
                    req_by_sender.setdefault(e.strip().lower(), (cid, rid))
            for c in (r.get("correspondence") or []):
                if c.get("direction") == "out":
                    if c.get("message_id"):
                        sent_by_msgid[c["message_id"]] = (cid, rid)
                    if c.get("to"):
                        req_by_sender.setdefault(c["to"].strip().lower(), (cid, rid))
                elif c.get("direction") == "in" and c.get("message_id"):
                    seen.add(c["message_id"])
    return {"sent_by_msgid": sent_by_msgid, "req_by_sender": req_by_sender, "seen": seen}


def match(fields, index):
    """Resolve one inbound message to (client_id, request_id), or None. `fields` carries
    message_id, in_reply_to, references, from_email."""
    if fields.get("message_id") and fields["message_id"] in index["seen"]:
        return None                              # already recorded — skip
    for ref in _ids(fields.get("in_reply_to"), fields.get("references")):
        hit = index["sent_by_msgid"].get(ref)
        if hit:
            return hit
    frm = (fields.get("from_email") or "").strip().lower()
    return index["req_by_sender"].get(frm)


def _fields_from_message(msg):
    _, from_email = email.utils.parseaddr(msg.get("From", ""))
    return {
        "message_id": (msg.get("Message-ID") or "").strip() or None,
        "in_reply_to": msg.get("In-Reply-To"),
        "references": msg.get("References"),
        "from_email": from_email,
        "subject": msg.get("Subject") or "",
    }


def _body_text(msg):
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain" and "attachment" not in str(
                    part.get("Content-Disposition", "")):
                try:
                    return part.get_content()
                except Exception:
                    return part.get_payload(decode=True).decode(errors="replace")
        return ""
    try:
        return msg.get_content()
    except Exception:
        return msg.get_payload(decode=True).decode(errors="replace") if msg.get_payload() else ""


def poll_replies(client_ids=None, since_days=14):
    """IMAP-poll the Zoho mailbox and thread analyst replies onto their NDR requests. Returns
    {ok, checked, matched} (or {ok: False, reason} when Zoho/IMAP isn't available). Best-effort
    and idempotent — safe to run on a timer or a manual button."""
    if not zoho_mail.is_configured():
        return {"ok": False, "reason": "zoho_not_configured", "matched": 0}
    if client_ids is None:
        from config.client_config import CLIENT_REGISTRY
        client_ids = list(CLIENT_REGISTRY)
    index = build_index(client_ids)

    im, err = zoho_mail.imap_login()
    if not im:
        return {"ok": False, "reason": "imap_login_failed", "error": err, "matched": 0}
    checked = matched = 0
    try:
        im.select("INBOX")
        since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        typ, data = im.search(None, f'(SINCE "{since}")')
        if typ != "OK":
            return {"ok": False, "reason": "search_failed", "matched": 0}
        for num in (data[0].split() if data and data[0] else []):
            typ, raw = im.fetch(num, "(RFC822)")
            if typ != "OK" or not raw or not raw[0]:
                continue
            checked += 1
            msg = email.message_from_bytes(raw[0][1])
            f = _fields_from_message(msg)
            hit = match(f, index)
            if not hit:
                continue
            cid, rid = hit
            ndr_correspondence.record_inbound(rid, f["from_email"], f["subject"],
                                              _body_text(msg), message_id=f["message_id"], client_id=cid)
            index["seen"].add(f["message_id"])   # in case two messages share (they shouldn't)
            matched += 1
    finally:
        try:
            im.logout()
        except Exception:
            pass
    return {"ok": True, "checked": checked, "matched": matched}
