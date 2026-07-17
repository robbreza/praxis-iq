"""
core/documents.py — file storage for analyst models, note attachments, and
(eventually) email attachments, linked to a contact/firm so the CFO/IR team
can pull up "the model this analyst sent" or "the most recent note" from one
place instead of hunting through email or a shared drive.

Why this exists: before this module, three separate parts of the app each
tracked analyst-relationship data with no link between them — Calendar
events (conference/meeting dates, no attachments), Meeting Hub's
scheduled_meetings.json (callback scheduling, a free-text Topic field only),
and Today page's per-analyst "Model Received" upload (parses a simple CSV
into consensus numbers, discards the original file). None of them stored an
actual uploaded file for later retrieval. This module is that missing
piece: the file itself (Excel model, PDF, etc.) goes in Neon Postgres as
real bytes, tagged with who it's from and what it is, so a calendar
reminder or Meeting Hub card can show "here's the last model, here's the
last note" without anyone re-finding the original email.

Storage choice: real file bytes in the `documents` table (see core/db.py's
schema), not a local uploads/ folder. This app already runs its source of
truth on Neon (a real, persistent server) rather than the machine's local
disk, and that's deliberate — local disk doesn't survive a move to a
different host/machine, Neon does. For the file volumes this feature
realistically sees (one model per analyst per quarter, not thousands of
large files), storing bytes in Postgres avoids standing up separate object
storage (S3 or similar) for a first pass. If volume ever grows enough that
this matters, only the internals of save_document/get_document need to
change — every caller already goes through this module, not raw SQL.

Every function below takes an explicit client_id (or resolves the active
one) — same multi-tenant scoping as every other core/ module.
"""

from datetime import datetime

from core import db

# Free-text but conventionally one of: "model" (analyst's Excel/financial
# model), "note_attachment" (a file that came with a post-meeting note),
# "email_attachment" (pulled from the IR inbox via core/mail_gateway.py).
# Not enforced as a DB constraint — new types can be added without a
# migration, same philosophy as activity_log.py's event_type strings.
DOC_TYPES = ("model", "note_attachment", "email_attachment", "other")


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def save_document(contact, firm, doc_type, filename, file_bytes,
                   content_type=None, source="manual_upload", uploaded_by=None,
                   linked_meeting_id=None, client_id=None):
    """Stores one file. Returns the new document's id. `contact`/`firm` are
    the join keys used everywhere else in the app (post_meeting_notes.json,
    scheduled_meetings.json) — pass whatever string is on hand even if it
    doesn't match a known contact exactly; retrieval below degrades to
    firm-only or contact-only lookups rather than requiring an exact
    match on both."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        if pg:
            cur.execute(
                "INSERT INTO documents (client_id, contact, firm, doc_type, filename, content_type, "
                "file_bytes, source, uploaded_by, linked_meeting_id, uploaded_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now()) RETURNING id",
                (cid, contact, firm, doc_type, filename, content_type,
                 psycopg2_binary(file_bytes), source, uploaded_by, linked_meeting_id),
            )
            new_id = cur.fetchone()[0]
        else:
            cur.execute(
                "INSERT INTO documents (client_id, contact, firm, doc_type, filename, content_type, "
                "file_bytes, source, uploaded_by, linked_meeting_id, uploaded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (cid, contact, firm, doc_type, filename, content_type,
                 file_bytes, source, uploaded_by, linked_meeting_id, datetime.now().isoformat()),
            )
            new_id = cur.lastrowid
        conn.commit()
        return new_id
    finally:
        conn.close()


def psycopg2_binary(file_bytes):
    """Wraps raw bytes for a BYTEA insert. Isolated in its own function so
    the psycopg2 import only happens on the Postgres path (this module is
    also imported/exercised in the SQLite-only sandbox test environment,
    which has no psycopg2 installed)."""
    from psycopg2 import Binary
    return Binary(file_bytes)


_METADATA_COLUMNS = ("id", "contact", "firm", "doc_type", "filename", "content_type",
                     "source", "uploaded_by", "linked_meeting_id", "uploaded_at")


def list_documents(contact=None, firm=None, doc_type=None, client_id=None):
    """Metadata only (no file_bytes — keep listing cheap). Filters are
    AND'ed together; any left as None is not filtered on. Newest first."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    ph = "%s" if pg else "?"
    try:
        cur = conn.cursor()
        clauses, params = [f"client_id = {ph}"], [cid]
        if contact:
            clauses.append(f"contact = {ph}")
            params.append(contact)
        if firm:
            clauses.append(f"firm = {ph}")
            params.append(firm)
        if doc_type:
            clauses.append(f"doc_type = {ph}")
            params.append(doc_type)
        cur.execute(
            f"SELECT {', '.join(_METADATA_COLUMNS)} FROM documents WHERE {' AND '.join(clauses)} "
            f"ORDER BY uploaded_at DESC",
            params,
        )
        rows = cur.fetchall()
        return [dict(zip(_METADATA_COLUMNS, r)) for r in rows]
    finally:
        conn.close()


def get_latest_document(contact=None, firm=None, doc_type=None, client_id=None):
    """The single most recent document matching the given filters (metadata
    only), or None. This is the call a calendar reminder / Meeting Hub card
    uses for "show me the latest model for this analyst.\""""
    matches = list_documents(contact=contact, firm=firm, doc_type=doc_type, client_id=client_id)
    return matches[0] if matches else None


def get_document_bytes(doc_id, client_id=None):
    """Returns (filename, content_type, file_bytes) for download, or None
    if doc_id doesn't exist (or belongs to a different client)."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    ph = "%s" if pg else "?"
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT filename, content_type, file_bytes FROM documents WHERE id = {ph} AND client_id = {ph}",
            (doc_id, cid),
        )
        row = cur.fetchone()
        if row is None:
            return None
        filename, content_type, file_bytes = row
        return filename, content_type, bytes(file_bytes)
    finally:
        conn.close()


def delete_document(doc_id, client_id=None):
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    ph = "%s" if pg else "?"
    try:
        cur = conn.cursor()
        cur.execute(f"DELETE FROM documents WHERE id = {ph} AND client_id = {ph}", (doc_id, cid))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
