"""core/client_store.py — CRUD for the `clients` table (tenant definitions).

This is the DB half of Phase 2: tenant definitions become DATA, so the Praxis Point Console can
onboard/edit a client without a code change + deploy. config.client_config.reload_registry()
overlays these rows onto the in-code seed to build the live CLIENT_REGISTRY.

A stored `record` is the per-tenant config dict. For an EXISTING (code-seed) client it need only
carry the fields being overridden — reload_registry deep-merges it onto the seed. For a NEW client
it is the whole (minimal) record. Unlike most tables this one is NOT scoped by client_id: it IS
the client list, same as `users`.
"""
import json
from datetime import datetime

from core import db


def _record_out(raw):
    """Normalize a stored record to a dict — JSONB comes back as a dict (Postgres), TEXT as a
    JSON string (SQLite)."""
    if raw is None:
        return {}
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        return {}


def all_clients():
    """Every row as (client_id, record_dict, active_bool), in client_id order."""
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT client_id, record, active FROM clients ORDER BY client_id")
        return [(r[0], _record_out(r[1]), bool(r[2])) for r in cur.fetchall()]
    finally:
        conn.close()


def get_client_record(client_id):
    """The stored record dict for one client, or None if it has no DB row."""
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"SELECT record FROM clients WHERE client_id = {ph}", (client_id,))
        row = cur.fetchone()
        return _record_out(row[0]) if row else None
    finally:
        conn.close()


def client_exists(client_id):
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"SELECT 1 FROM clients WHERE client_id = {ph}", (client_id,))
        return cur.fetchone() is not None
    finally:
        conn.close()


def upsert_client(client_id, record, active=True):
    """Insert or update a client's record (upsert on client_id). Stamps updated_at; preserves
    created_at on update."""
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        now = datetime.now()
        now_v = now if pg else now.isoformat()
        if pg:
            from psycopg2.extras import Json
            payload = Json(record, dumps=lambda d: json.dumps(d, default=str))
            cur.execute(
                "INSERT INTO clients (client_id, record, active, created_at, updated_at) "
                "VALUES (%s,%s,%s,%s,%s) "
                "ON CONFLICT (client_id) DO UPDATE SET record = EXCLUDED.record, "
                "active = EXCLUDED.active, updated_at = EXCLUDED.updated_at",
                (client_id, payload, bool(active), now_v, now_v))
        else:
            cur.execute(
                "INSERT INTO clients (client_id, record, active, created_at, updated_at) "
                "VALUES (?,?,?,?,?) "
                "ON CONFLICT(client_id) DO UPDATE SET record = excluded.record, "
                "active = excluded.active, updated_at = excluded.updated_at",
                (client_id, json.dumps(record, default=str), bool(active), now_v, now_v))
        conn.commit()
    finally:
        conn.close()


def set_client_active(client_id, active):
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        now = datetime.now()
        cur.execute(
            f"UPDATE clients SET active = {ph}, updated_at = {ph} WHERE client_id = {ph}",
            (bool(active), now if pg else now.isoformat(), client_id))
        conn.commit()
    finally:
        conn.close()


def delete_client(client_id):
    """Hard-delete a client's DB row. Note this only removes the DB OVERLAY — a client that also
    exists in the code seed reverts to its seed definition on the next reload, it does not vanish.
    Prefer set_client_active(cid, False) to actually hide a tenant."""
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"DELETE FROM clients WHERE client_id = {ph}", (client_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()
