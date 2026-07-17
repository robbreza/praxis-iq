"""
core/activity_log.py — the event ledger behind every computed ROI/readiness
number in the app.

Every page that already implements the closed-loop resolve/note/reset
pattern (today_page.py's Risk Signals, markets_page.py's IR Risk Dashboard,
reports_page.py's Reg FD Flags, earnings_page.py's script_workflow stage
completions) calls log_event() at the moment something real happens: an
email actually gets marked sent, a signal actually gets resolved, a script
stage actually completes. That's the whole idea behind "everything needs to
compute and have the ability to resolve it" — a metric like "11 tasks
automated today" stops being a literal someone typed into the page and
becomes a COUNT(*) against real rows logged by real actions.

EVENT_MINUTES_SAVED is a judgment-call lookup table (how many minutes a
given automated action is estimated to save vs. doing it by hand) — the
same kind of point-in-time IR judgment call as CLIENT_REGISTRY's
bar_risk_level/guidance_vs_street_note fields, not a measured fact. It's a
plain module-level dict specifically so it's easy to find and adjust
later, not buried in a formula.
"""

from datetime import datetime, timedelta

from core import db

EVENT_MINUTES_SAVED = {
    "signal_resolved": 15,
    "signal_noted": 5,
    "signal_muted": 2,
    "email_sent": 10,
    "script_stage_complete": 20,
    "sec_filing_reviewed": 5,
    "model_request_sent": 10,
    "model_received": 15,
    "regfd_reviewed": 5,
    "regfd_8k_resolved": 10,
    "transcript_ingested": 10,
    "transcript_summarized": 15,
    "board_slide_generated": 20,
}
_DEFAULT_MINUTES_SAVED = 5


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def log_event(event_type, entity=None, client_id=None, **detail):
    """Append one row to the ledger. `entity` is a free-text identifier for
    whatever the event happened to (an analyst name, a signal index, a
    stage id) — used by overdue_sent_without_response() to match a later
    "resolved" event back to the "sent" event it resolves. `**detail` is
    any extra JSON-serializable context worth keeping (reason text, dollar
    amounts, etc.) — stored but not required by any query helper below."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        if pg:
            from psycopg2.extras import Json
            cur.execute(
                "INSERT INTO activity_log (client_id, event_type, entity, detail, created_at) "
                "VALUES (%s, %s, %s, %s, now())",
                (cid, event_type, entity, Json(detail)),
            )
        else:
            import json as _json
            cur.execute(
                "INSERT INTO activity_log (client_id, event_type, entity, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (cid, event_type, entity, _json.dumps(detail, default=str), datetime.now().isoformat()),
            )
        conn.commit()
    finally:
        conn.close()


def _rows_since(since_dt, event_type=None, client_id=None):
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        sql = f"SELECT event_type, entity, created_at FROM activity_log WHERE client_id = {ph} AND created_at >= {ph}"
        params = [cid, since_dt if pg else since_dt.isoformat()]
        if event_type:
            sql += f" AND event_type = {ph}"
            params.append(event_type)
        cur.execute(sql, params)
        return cur.fetchall()
    finally:
        conn.close()


def count_today(event_type=None, client_id=None):
    """How many events (optionally of one type) were logged since local
    midnight today. Backs the Today page's "N tasks automated today"."""
    midnight = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return len(_rows_since(midnight, event_type, client_id))


def count_this_week(event_type=None, client_id=None):
    """Events since the most recent Monday 00:00 — backs weekly rollups."""
    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return len(_rows_since(monday, event_type, client_id))


def minutes_saved_this_week(client_id=None):
    """Sum of EVENT_MINUTES_SAVED across every event logged since Monday —
    backs the Today page's "N.N hrs saved this week"."""
    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = _rows_since(monday, None, client_id)
    total = sum(EVENT_MINUTES_SAVED.get(r[0], _DEFAULT_MINUTES_SAVED) for r in rows)
    return total


def breakdown_this_week(client_id=None):
    """Every event type logged since Monday, with count and total minutes
    saved per type. minutes_saved_this_week() and count_this_week() give
    the Today page's single rolled-up numbers; this is the per-category
    view Reports' Automation Tracker tab needs to show WHAT actually got
    automated, not just how much. Sorted by minutes saved, largest first."""
    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    rows = _rows_since(monday, None, client_id)
    totals = {}
    for event_type, _entity, _created_at in rows:
        d = totals.setdefault(event_type, {"count": 0, "minutes": 0})
        d["count"] += 1
        d["minutes"] += EVENT_MINUTES_SAVED.get(event_type, _DEFAULT_MINUTES_SAVED)
    return sorted(
        ({"event_type": k, **v} for k, v in totals.items()),
        key=lambda d: d["minutes"], reverse=True,
    )


def recent_events(limit=20, client_id=None):
    """Most recent events, newest first — used for an activity feed / audit
    trail, and for spot-checking that logging is actually happening."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"SELECT event_type, entity, detail, created_at FROM activity_log "
            f"WHERE client_id = {ph} ORDER BY created_at DESC LIMIT {ph}",
            (cid, limit),
        )
        rows = cur.fetchall()
        out = []
        for event_type, entity, detail, created_at in rows:
            if not pg:
                import json as _json
                try:
                    detail = _json.loads(detail) if detail else {}
                except Exception:
                    detail = {}
            out.append({"event_type": event_type, "entity": entity, "detail": detail, "created_at": str(created_at)})
        return out
    finally:
        conn.close()


def overdue_sent_without_response(sent_event_type, complete_event_types, hours=24, client_id=None):
    """Entities with a `sent_event_type` event logged more than `hours` ago
    that have NO later event in `complete_event_types` for that same
    entity. Backs the Today page's "0 analyst requests overdue" — real
    instead of hardcoded, but still self-reported (this app has no email
    inbox integration; "complete" only happens when a user marks it,
    exactly as documented in today_page.py's Activity & Responses
    section)."""
    cid = _resolve_client_id(client_id)
    cutoff = datetime.now() - timedelta(hours=hours)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"SELECT entity, created_at FROM activity_log "
            f"WHERE client_id = {ph} AND event_type = {ph} AND entity IS NOT NULL AND created_at <= {ph}",
            (cid, sent_event_type, cutoff if pg else cutoff.isoformat()),
        )
        sent_rows = cur.fetchall()
        overdue = []
        for entity, sent_at in sent_rows:
            found = False
            for complete_type in complete_event_types:
                cur.execute(
                    f"SELECT 1 FROM activity_log WHERE client_id = {ph} AND event_type = {ph} "
                    f"AND entity = {ph} AND created_at > {ph} LIMIT 1",
                    (cid, complete_type, entity, sent_at),
                )
                if cur.fetchone():
                    found = True
                    break
            if not found:
                overdue.append({"entity": entity, "sent_at": str(sent_at)})
        return overdue
    finally:
        conn.close()
