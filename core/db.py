"""
core/db.py — data layer, scoped by client_id. Neon Postgres when configured,
local SQLite otherwise.

Every page in this app persists its working state (meeting logs, NDR trips,
report review checkmarks, settings, risk-signal resolutions, etc.) through
load_json()/save_json() — a drop-in replacement for the per-page
_load_json(name, default)/_save_json(name, data) helper every page used to
define locally. That contract hasn't changed. What changed is the backend:

    - If DATABASE_URL is set (core.security.get_database_url() — Neon
      dashboard -> project -> Connection Details), every read/write goes to
      that Postgres database. This is the path for real usage: Neon is a
      real server, so data survives across machines/restarts and multiple
      people can eventually work off the same data instead of each having
      their own local data/app.db.
    - If DATABASE_URL is not set, everything falls back to the exact same
      local SQLite file (data/app.db) this module used before. This isn't
      a "degraded mode" — it's a fully working backend, kept specifically
      so the app (and this module's own test suite) still runs with zero
      external dependencies when Neon isn't configured yet, e.g. in a
      sandboxed environment with no network route to Neon's servers.

Three tables now, not one:

    client_data (client_id, key, value, updated_at)
        Same generic JSON-blob key/value store as before — every existing
        page's load_json/save_json calls land here unchanged. On Postgres,
        `value` is a native JSONB column (psycopg2 hands back a Python
        dict/list automatically, no json.loads needed); on SQLite it's
        still JSON-encoded TEXT.

    activity_log (id, client_id, event_type, entity, detail, created_at)
        NEW — an append-only event ledger. Every time a page's closed-loop
        resolve/note/reset action actually does something (an analyst
        request is marked sent, a risk signal is resolved, a script stage
        completes...) it calls activity_log.log_event(...), which inserts
        a row here. This is what makes the Today page's "11 tasks
        automated today" style ROI numbers real, computed facts instead of
        hardcoded demo literals — see core/activity_log.py.

    market_data_cache (client_id, ticker, ...)
        NEW — cached price/volume snapshots from core/market_data.py
        (yfinance), refreshed on a timer (the user has confirmed up to a
        60-minute delay is acceptable, so this doesn't need to be a
        streaming/real-time feed — a periodic refresh is enough).

    call_transcripts (client_id, quarter, ...)
        NEW — ingested earnings call transcripts (see core/transcripts.py).
        ChorusCall (the vendor USIO's calls are hosted on) has no public
        API, so these arrive as a PDF export or pasted text a user uploads
        by hand, not an automated fetch — the table just needs to hold the
        extracted full text plus an AI-generated summary/key-quotes/
        Q&A-risk-topics payload once summarize_transcript() has run.

Migration: the very first time a (client_id, key) is requested from
client_data and the row doesn't exist yet, load_json() transparently
imports it from the legacy pre-SQLite file (via client_data_path()) exactly
as before. Moving from SQLite to Postgres is a SEPARATE, explicit step —
see scripts/migrate_to_neon.py — because that migration needs to run once,
by hand, on a machine that can actually reach Neon (this sandbox can't;
confirmed no route to *.neon.tech), not silently on every read.
"""

import json
import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join("data", "app.db")

_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS client_data (
    client_id  TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (client_id, key)
);
CREATE TABLE IF NOT EXISTS activity_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id  TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity     TEXT,
    detail     TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_activity_log_client_created ON activity_log (client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_log_client_type ON activity_log (client_id, event_type);
CREATE TABLE IF NOT EXISTS market_data_cache (
    client_id      TEXT NOT NULL,
    ticker         TEXT NOT NULL,
    last_price     REAL,
    prev_close     REAL,
    pct_change     REAL,
    volume         INTEGER,
    avg_volume_10d INTEGER,
    as_of          TEXT,
    fetched_at     TEXT NOT NULL,
    PRIMARY KEY (client_id, ticker)
);
CREATE TABLE IF NOT EXISTS call_transcripts (
    client_id      TEXT NOT NULL,
    quarter        TEXT NOT NULL,
    call_date      TEXT,
    source         TEXT,
    source_filename TEXT,
    full_text      TEXT,
    ai_summary     TEXT,
    key_quotes     TEXT,
    qa_risk_topics TEXT,
    guidance_language TEXT,
    summarized_at  TEXT,
    uploaded_at    TEXT NOT NULL,
    PRIMARY KEY (client_id, quarter)
);
CREATE TABLE IF NOT EXISTS documents (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id         TEXT NOT NULL,
    contact           TEXT,
    firm              TEXT,
    doc_type          TEXT NOT NULL,
    filename          TEXT NOT NULL,
    content_type      TEXT,
    file_bytes        BLOB NOT NULL,
    source            TEXT,
    uploaded_by       TEXT,
    linked_meeting_id TEXT,
    uploaded_at       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_documents_client_contact ON documents (client_id, contact, firm);
"""

_POSTGRES_SCHEMA = """
CREATE TABLE IF NOT EXISTS client_data (
    client_id  TEXT NOT NULL,
    key        TEXT NOT NULL,
    value      JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (client_id, key)
);
CREATE TABLE IF NOT EXISTS activity_log (
    id         BIGSERIAL PRIMARY KEY,
    client_id  TEXT NOT NULL,
    event_type TEXT NOT NULL,
    entity     TEXT,
    detail     JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_activity_log_client_created ON activity_log (client_id, created_at);
CREATE INDEX IF NOT EXISTS idx_activity_log_client_type ON activity_log (client_id, event_type);
CREATE TABLE IF NOT EXISTS market_data_cache (
    client_id      TEXT NOT NULL,
    ticker         TEXT NOT NULL,
    last_price     NUMERIC,
    prev_close     NUMERIC,
    pct_change     NUMERIC,
    volume         BIGINT,
    avg_volume_10d BIGINT,
    as_of          TIMESTAMPTZ,
    fetched_at     TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (client_id, ticker)
);
CREATE TABLE IF NOT EXISTS call_transcripts (
    client_id      TEXT NOT NULL,
    quarter        TEXT NOT NULL,
    call_date      TEXT,
    source         TEXT,
    source_filename TEXT,
    full_text      TEXT,
    ai_summary     TEXT,
    key_quotes     JSONB,
    qa_risk_topics JSONB,
    guidance_language JSONB,
    summarized_at  TIMESTAMPTZ,
    uploaded_at    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (client_id, quarter)
);
CREATE TABLE IF NOT EXISTS documents (
    id                BIGSERIAL PRIMARY KEY,
    client_id         TEXT NOT NULL,
    contact           TEXT,
    firm              TEXT,
    doc_type          TEXT NOT NULL,
    filename          TEXT NOT NULL,
    content_type      TEXT,
    file_bytes        BYTEA NOT NULL,
    source            TEXT,
    uploaded_by       TEXT,
    linked_meeting_id TEXT,
    uploaded_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_documents_client_contact ON documents (client_id, contact, firm);
"""


# Cached, once-per-process reachability check (see _pg_reachable below) —
# a misconfigured or momentarily-unreachable Neon endpoint must never crash
# every page in the app (every page calls load_json/save_json somewhere).
# This mirrors the graceful-degradation policy already used in
# core/sec_filings.py and core/market_data.py: catch the failure, fall back
# to the local SQLite file, print one clear message, keep the app usable.
_pg_status = {"checked": False, "available": False}


def _pg_reachable():
    """True only if DATABASE_URL is set, psycopg2 is importable, AND a real
    connection attempt to Neon actually succeeds — not just that the URL is
    present. Cached for the life of the process so a down/misconfigured
    Neon endpoint doesn't retry (and re-print a warning) on every single
    database call; restart the app after fixing .env to re-check."""
    if _pg_status["checked"]:
        return _pg_status["available"]
    _pg_status["checked"] = True

    from core.security import get_database_url
    url = get_database_url()
    if not url:
        _pg_status["available"] = False
        return False

    try:
        import psycopg2
        conn = psycopg2.connect(url, connect_timeout=5)
        conn.close()
        _pg_status["available"] = True
        print("[db] Connected to Neon Postgres.")
    except ImportError:
        print("[db] DATABASE_URL is set but psycopg2 isn't installed — "
              "run `pip install -r requirements.txt`. Falling back to local SQLite (data/app.db).")
        _pg_status["available"] = False
    except Exception as e:
        print(f"[db] Could not connect to Neon ({e}). Falling back to local SQLite (data/app.db) "
              f"for this session — check DATABASE_URL in .env, then restart the app to retry.")
        _pg_status["available"] = False

    return _pg_status["available"]


def is_postgres():
    """True if DATABASE_URL is configured, psycopg2 is importable, and a
    real connection to Neon has been confirmed reachable this process —
    i.e. Neon is the active backend. Other modules (activity_log.py,
    market_data.py) use this to pick %s vs ? placeholders when they build
    their own SQL against get_connection()."""
    return _pg_reachable()


class _PooledConnection:
    """Thin wrapper around the single cached psycopg2 connection below.
    Every existing call site across the codebase (db.py's own helpers,
    activity_log.py, market_data.py, transcripts.py...) follows the same
    `conn = db.get_connection(); try: ...; finally: conn.close()` pattern,
    written back when every call opened its own short-lived connection.
    Rather than touch every one of those call sites, `.close()` here is a
    no-op — from the caller's point of view they're "done with it", but the
    real TCP/TLS session to Neon stays open and cached for the next caller
    to reuse. Every other attribute (cursor, commit, rollback, ...) passes
    straight through to the real connection."""

    def __init__(self, real_conn):
        self._real = real_conn

    def close(self):
        pass

    def __getattr__(self, name):
        return getattr(self._real, name)


# The one long-lived Postgres connection, reused across every load_json/
# save_json/etc. call for the life of the process (see get_connection()).
_pg_conn_holder = {"conn": None}


def _get_pooled_pg_connection():
    """Returns the cached, live Neon connection — opening one (and running
    the schema-ensure DDL) only the first time, or again if the cached one
    turned out to be dead. This is the fix for a real performance bug: the
    original version of get_connection() opened a brand-new TCP+TLS
    connection to Neon on EVERY single call, and a single page render can
    call it dozens of times (meeting log, NDR requests, NDR trips, peer
    universe, prospects, SEC filings per ticker...) — all synchronous,
    all blocking NiceGUI's single-threaded event loop in sequence. On a
    real network (and especially against Neon's serverless compute, which
    can take a couple of seconds to wake from idle), that was slow enough
    to stall the event loop past the browser's websocket timeout, which is
    what showed up as "Connection lost" on ordinary page navigation —
    not a crash, just the server too busy reconnecting to Neon over and
    over to answer the heartbeat in time."""
    real = _pg_conn_holder["conn"]
    if real is not None:
        try:
            with real.cursor() as cur:
                cur.execute("SELECT 1")
            return real
        except Exception:
            try:
                real.close()
            except Exception:
                pass
            _pg_conn_holder["conn"] = None

    import psycopg2
    from core.security import get_database_url
    real = psycopg2.connect(get_database_url())
    with real.cursor() as cur:
        cur.execute(_POSTGRES_SCHEMA)
    real.commit()
    _pg_conn_holder["conn"] = real
    return real


def get_connection():
    """A live, schema-ensured connection — Postgres (Neon) if configured
    and reachable, SQLite otherwise. Caller is responsible for closing it
    (use a try/finally, same convention as every function below) — for
    Postgres that's now a cheap no-op release back to the cached connection
    (see _PooledConnection), not an actual disconnect. Even after
    is_postgres() has confirmed Neon is reachable, this still falls back to
    SQLite for THIS call (without crashing the page) if the actual
    connection attempt fails — belt-and-suspenders against a mid-session
    network blip."""
    if is_postgres():
        try:
            real = _get_pooled_pg_connection()
            return _PooledConnection(real)
        except Exception as e:
            print(f"[db] Neon connection failed mid-session ({e}) — using local SQLite for this call.")
            # Don't keep retrying a Neon endpoint that just failed live —
            # same reasoning as the cached check above.
            _pg_status["available"] = False

    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.executescript(_SQLITE_SCHEMA)
    return conn


# Backward-compatible alias — a handful of earlier call sites/tests refer
# to the SQLite-only connection helper by its old name.
def _connect():
    return get_connection()


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def _migrate_legacy_file_if_needed(client_id, key):
    """First-read import of a pre-database JSON/CSV file. Returns the
    imported value, or None if no legacy file exists for this key. Uses
    client_data_path()'s existing data/<client_id>/ -> models/ fallback."""
    from config.client_config import client_data_path
    path = client_data_path(key, client_id)
    if not os.path.exists(path):
        return None
    try:
        if path.endswith(".csv"):
            import pandas as pd
            return pd.read_csv(path).to_dict("records")
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None


def load_json(key, default=None, client_id=None):
    """Read the value stored under `key` for the given (or active) client.
    Same shape regardless of backend: returns `default` if nothing is on
    file yet, never raises for a missing key."""
    cid = _resolve_client_id(client_id)
    conn = get_connection()
    pg = is_postgres()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT value FROM client_data WHERE client_id = {'%s' if pg else '?'} AND key = {'%s' if pg else '?'}",
            (cid, key),
        )
        row = cur.fetchone()
        if row is not None:
            if pg:
                return row[0]  # JSONB comes back as a native dict/list already
            try:
                return json.loads(row[0])
            except Exception:
                return default

        migrated = _migrate_legacy_file_if_needed(cid, key)
        if migrated is not None:
            save_json(key, migrated, client_id=cid)
            return migrated
        return default
    finally:
        conn.close()


def save_json(key, data, client_id=None):
    """Write `data` (anything json-serializable) under `key` for the given
    (or active) client. Upserts, so repeated saves to the same key just
    overwrite."""
    cid = _resolve_client_id(client_id)
    conn = get_connection()
    pg = is_postgres()
    try:
        cur = conn.cursor()
        if pg:
            from psycopg2.extras import Json
            cur.execute(
                "INSERT INTO client_data (client_id, key, value, updated_at) VALUES (%s, %s, %s, now()) "
                "ON CONFLICT (client_id, key) DO UPDATE SET value = EXCLUDED.value, updated_at = EXCLUDED.updated_at",
                (cid, key, Json(data, dumps=lambda d: json.dumps(d, default=str))),
            )
        else:
            cur.execute(
                "INSERT INTO client_data (client_id, key, value, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(client_id, key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
                (cid, key, json.dumps(data, default=str), datetime.now().isoformat()),
            )
        conn.commit()
    finally:
        conn.close()


def delete_key(key, client_id=None):
    """Remove a key entirely (rarely needed — mostly for tests/debugging)."""
    cid = _resolve_client_id(client_id)
    conn = get_connection()
    pg = is_postgres()
    try:
        cur = conn.cursor()
        cur.execute(
            f"DELETE FROM client_data WHERE client_id = {'%s' if pg else '?'} AND key = {'%s' if pg else '?'}",
            (cid, key),
        )
        conn.commit()
    finally:
        conn.close()


def list_keys(client_id=None):
    """All keys currently stored for a client — useful for debugging/admin,
    and for a future "export all my data" or "reset this client" feature."""
    cid = _resolve_client_id(client_id)
    conn = get_connection()
    pg = is_postgres()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT key, updated_at FROM client_data WHERE client_id = {'%s' if pg else '?'} ORDER BY key",
            (cid,),
        )
        rows = cur.fetchall()
        return [{"key": r[0], "updated_at": str(r[1])} for r in rows]
    finally:
        conn.close()
