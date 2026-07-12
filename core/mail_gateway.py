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
        inbox_queue.enqueue_item(
            category=category, contact=match.get("name"), firm=match.get("firm"), subject=subject,
            extracted=extracted, doc_id=primary_doc_id, filename=primary[0] if primary else None,
            source="email_sync", client_id=client_id,
        )
    return category, extracted, saved_filenames


def sync_inbox(contact_lookup, since_days=14, save_attachments_as="email_attachment", client_id=None):
    host, port, user, password = get_imap_config()
    if not host:
        return {"ok": False, "reason": "not_configured",
                "message": "Email sync isn't set up yet - add MAIL_IMAP_HOST/PORT/USER/PASSWORD "
                           "to .env once you have real (or test) mailbox credentials."}

    import imaplib
    try:
        conn = imaplib.IMAP4_SSL(host, port)
        conn.login(user, password)
        conn.select("INBOX")

        since = (datetime.now() - timedelta(days=since_days)).strftime("%d-%b-%Y")
        status, data = conn.search(None, f'(SINCE "{since}")')
        if status != "OK":
            return {"ok": False, "reason": "search_failed", "message": "IMAP search returned a non-OK status."}

        results = []
        for num in data[0].split():
            status, msg_data = conn.fetch(num, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            msg = email.message_from_bytes(msg_data[0][1])
            from_addr = email.utils.parseaddr(msg.get("From", ""))[1].lower()
            match = contact_lookup.get(from_addr)
            if not match:
                continue

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
        return {"ok": True, "reason": "success", "messages": results}
    except Exception as e:
        return {"ok": False, "reason": "fetch_error", "message": str(e)}
