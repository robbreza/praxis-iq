"""
core/mail_gateway.py - IR inbox sync (IMAP) + email tagging/routing,
stubbed until a real mailbox exists. See docstring in the deployed file
for full context; this sandbox copy exists only to exercise the logic in
tests (bash-mount sync lag on this project, not a real content issue -
verified against the authoritative Windows-side file).
"""

import email
import os
from datetime import datetime, timedelta
from email.header import decode_header

from core import documents, email_classifier, inbox_queue

_MODEL_ATTACHMENT_EXTENSIONS = (".xlsx", ".xls", ".xlsm", ".csv", ".pdf")
_RESEARCH_NOTE_EXTENSIONS = (".pdf", ".docx", ".doc")

_DOC_TYPE_BY_CATEGORY = {"model": "model", "research_note": "research_note"}


def get_imap_config():
    from core.security import load_environment
    load_environment()
    host = os.environ.get("MAIL_IMAP_HOST")
    port = os.environ.get("MAIL_IMAP_PORT")
    user = os.environ.get("MAIL_IMAP_USER")
    password = os.environ.get("MAIL_IMAP_PASSWORD")
    if not (host and port and user and password):
        return None, None, None, None
    try:
        port = int(port)
    except ValueError:
        return None, None, None, None
    return host, port, user, password


def is_configured():
    host, _port, _user, _password = get_imap_config()
    return host is not None


def _decode(value):
    if not value:
        return ""
    parts = decode_header(value)
    out = []
    for text, enc in parts:
        if isinstance(text, bytes):
            out.append(text.decode(enc or "utf-8", errors="replace"))
        else:
            out.append(text)
    return "".join(out)


def _extract_body_and_attachments(msg):
    body = ""
    attachments = []
    if msg.is_multipart():
        for part in msg.walk():
            disp = str(part.get("Content-Disposition") or "")
            ctype = part.get_content_type()
            if "attachment" in disp or (part.get_filename() and ctype != "text/plain"):
                filename = _decode(part.get_filename())
                if filename:
                    payload = part.get_payload(decode=True)
                    if payload:
                        attachments.append((filename, ctype, payload))
            elif ctype == "text/plain" and not body:
                payload = part.get_payload(decode=True)
                if payload:
                    body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    return body, attachments


def _primary_attachment_for(category, attachments):
    if not attachments:
        return None
    exts = _MODEL_ATTACHMENT_EXTENSIONS if category == "model" else _RESEARCH_NOTE_EXTENSIONS
    for att in attachments:
        if os.path.splitext(att[0] or "")[1].lower() in exts:
            return att
    return attachments[0]


def _save_attachments(match, attachments, category, save_attachments_as, client_id):
    doc_type = _DOC_TYPE_BY_CATEGORY.get(category, save_attachments_as)
    doc_ids = []
    for filename, content_type, file_bytes in attachments:
        doc_id = documents.save_document(
            contact=match.get("name"), firm=match.get("firm"), doc_type=doc_type,
            filename=filename, file_bytes=file_bytes, content_type=content_type,
            source="email_sync", client_id=client_id,
        )
        doc_ids.append(doc_id)
    return doc_ids


def _route_message(match, subject, body, attachments, client_id, save_attachments_as):
    result = email_classifier.classify_and_extract(
        subject, body, attachments, sender_kind=match.get("kind", "institution"),
    )
    category, extracted = result["category"], result["extracted"]

    doc_ids = _save_attachments(match, attachments, category, save_attachments_as, client_id)
    saved_filenames = [a[0] for a in attachments]

    if category != "general":
        primary = _primary_attachment_for(category, attachments)
        primary_doc_id = doc_ids[attachments.index(primary)] if primary is not None else None
        firm = match.get("firm")
        # A conference invite's "firm" is the host that's inviting (Baird, Denby Securities…),
        # not the sender's email domain — which is often a personal address (a corporate-access
        # person on gmail, or an IR contact forwarding it), so the domain resolves to no firm.
        # Fall back to the parsed organizer so the item is attributed to the conference.
        if not firm and category == "conference_invite" and (extracted or {}).get("organizer"):
            firm = extracted["organizer"]
        inbox_queue.enqueue_item(
            category=category, contact=match.get("name"), firm=firm, subject=subject,
            extracted=extracted, doc_id=primary_doc_id, filename=primary[0] if primary else None,
            source="email_sync", client_id=client_id,
        )
    return category, extracted, saved_filenames


# Free / consumer mail providers are never a firm's domain — an associate sends from
# the firm's domain, but a personal gmail/outlook must NOT be attributed to a firm.
_FREE_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com",
    "live.com", "aol.com", "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com",
    "msn.com", "gmx.com", "mail.com",
}


def _build_domain_lookup(contact_lookup):
    """Firm-level fallback so an ASSOCIATE at a covering firm (not just the named analyst)
    is recognized: map each analyst firm's email DOMAIN -> its firm. Skips free providers
    (gmail/outlook/...) and any domain shared by 2+ firms, so we never mis-attribute a
    personal or ambiguous address."""
    by_domain = {}
    for addr, info in contact_lookup.items():
        if info.get("kind") != "analyst" or not info.get("firm") or "@" not in addr:
            continue
        dom = addr.rsplit("@", 1)[-1]
        if not dom or dom in _FREE_EMAIL_DOMAINS:
            continue
        if dom not in by_domain:
            by_domain[dom] = {"name": f"{info['firm']} (desk)", "firm": info["firm"], "kind": "analyst"}
        elif by_domain[dom]["firm"] != info["firm"]:
            by_domain[dom] = None                    # domain used by 2+ firms -> ambiguous, drop
    return {d: v for d, v in by_domain.items() if v}


def sync_inbox(contact_lookup, since_days=14, save_attachments_as="email_attachment", client_id=None, accept_unknown=None):
    host, port, user, password = get_imap_config()
    if not host:
        return {"ok": False, "reason": "not_configured",
                "message": "Email sync isn't set up yet - add MAIL_IMAP_HOST/PORT/USER/PASSWORD "
                           "to .env once you have real (or test) mailbox credentials."}

    # A dedicated ingest inbox can accept mail from any sender (attributed from the email),
    # rather than only known analyst contacts. Off by default; on via MAIL_INBOX_ACCEPT_ANY.
    if accept_unknown is None:
        accept_unknown = os.environ.get("MAIL_INBOX_ACCEPT_ANY", "").strip().lower() in ("1", "true", "yes", "on")

    import imaplib
    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select("INBOX")

        since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        status, data = conn.search(None, f'(SINCE "{since}")')
        if status != "OK":
            return {"ok": False, "reason": "search_failed", "message": "IMAP search returned a non-OK status."}

        domain_lookup = _build_domain_lookup(contact_lookup)
        from core import db as _db
        _seen = _db.load_json("mail_seen_msgids.json", [], client_id=client_id) or []
        _seen_set = set(_seen)
        results = []
        for num in data[0].split():
            status, msg_data = conn.fetch(num, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            _mid = (msg.get("Message-ID") or "").strip()
            if _mid and _mid in _seen_set:
                continue  # handled on an earlier sync — skip (no re-classify, no re-file)
            if _mid:
                _seen.append(_mid); _seen_set.add(_mid)
            from_addr = email.utils.parseaddr(msg.get("From", ""))[1].lower()
            # exact address first (names the individual); else the firm domain (catches an
            # associate sending on the analyst's behalf).
            match = contact_lookup.get(from_addr)
            if not match and "@" in from_addr:
                match = domain_lookup.get(from_addr.rsplit("@", 1)[-1])
            if not match:
                if not accept_unknown:
                    continue
                # Accept-any inbox: no CRM match, so attribute straight from the email —
                # display name as the contact, sending domain as the firm (never a free
                # /consumer domain, which is a person, not a firm).
                _disp = _decode(email.utils.parseaddr(msg.get("From", ""))[0]).strip()
                _dom = from_addr.rsplit("@", 1)[-1] if "@" in from_addr else ""
                match = {"name": _disp or from_addr,
                         "firm": (None if (not _dom or _dom in _FREE_EMAIL_DOMAINS) else _dom),
                         "kind": "institution"}

            subject = _decode(msg.get("Subject", ""))
            body, attachments = _extract_body_and_attachments(msg)
            category, extracted, saved_filenames = _route_message(
                match, subject, body, attachments, client_id, save_attachments_as,
            )

            results.append({
                "from": from_addr, "contact_name": match.get("name"), "firm": match.get("firm"),
                "subject": subject, "date": msg.get("Date", ""),
                "body": body.strip()[:5000], "attachments_saved": saved_filenames,
                "category": category, "extracted": extracted,
            })

        conn.close()
        conn.logout()
        if len(_seen) > 2000:
            _seen = _seen[-2000:]
        _db.save_json("mail_seen_msgids.json", _seen, client_id=client_id)
        return {"ok": True, "reason": "success", "messages": results}
    except Exception as e:
        return {"ok": False, "reason": "fetch_error", "message": str(e)}
