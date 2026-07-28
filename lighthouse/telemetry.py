"""Lighthouse — engagement telemetry (used vs. ignored).

The honest way to answer "is Lighthouse the most-used or most-ignored feature" is to MEASURE it, not
hope. This records three signals:
  * email OPENS  — a 1x1 tracking pixel in the digest (endpoint /lh/o/<token>);
  * CLICK-THROUGHS — the digest CTA routes through /lh/c/<token> before redirecting to the app;
  * in-app VIEWS — the Lighthouse page and the Today-mirror click-through.

Two tables, self-bootstrapping (CREATE IF NOT EXISTS on first use — no migration step): `lh_delivery`
logs each send (the denominator), `lh_engagement` logs opens/clicks/views. Tokens are HMAC-signed so a
pixel URL can't be forged or enumerated. Everything is best-effort and fail-closed: telemetry must
never break a send, a page render, or the app.
"""
from __future__ import annotations
import os
import hmac
import base64
import hashlib

import psycopg2
from core.security import get_database_url


def _conn():
    return psycopg2.connect(get_database_url())


def _writes_disabled() -> bool:
    """Suppress engagement WRITES under test/smoke so they don't pollute the real used-vs-ignored
    numbers. Reads (summary) are always allowed."""
    return ("PYTEST_CURRENT_TEST" in os.environ
            or os.environ.get("LIGHTHOUSE_TELEMETRY_OFF", "").lower() in ("1", "true", "yes"))


def _ensure(cur):
    cur.execute("""CREATE TABLE IF NOT EXISTS lh_delivery (
        id BIGSERIAL PRIMARY KEY, client_id TEXT, ticker TEXT, kind TEXT, ref TEXT,
        channel TEXT, recipient TEXT, sent_at TIMESTAMPTZ NOT NULL DEFAULT now())""")
    cur.execute("""CREATE TABLE IF NOT EXISTS lh_engagement (
        id BIGSERIAL PRIMARY KEY, delivery_id BIGINT, client_id TEXT, ticker TEXT, kind TEXT,
        channel TEXT, event TEXT, user_agent TEXT, ts TIMESTAMPTZ NOT NULL DEFAULT now())""")
    cur.execute("CREATE INDEX IF NOT EXISTS lh_engagement_client_ts ON lh_engagement(client_id, ts)")


# ── signed tokens (opaque; can't be forged/enumerated) ─────────────────────────────────────────────
def _secret() -> bytes:
    return (os.environ.get("IRCONNECT_STORAGE_SECRET") or "lighthouse-dev-secret").encode()


def make_token(delivery_id: int) -> str:
    body = base64.urlsafe_b64encode(str(int(delivery_id)).encode()).decode().rstrip("=")
    sig = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{body}.{sig}"


def parse_token(token: str):
    try:
        body, sig = token.split(".", 1)
        good = hmac.new(_secret(), body.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, good):
            return None
        return int(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode())
    except Exception:
        return None


# ── writes (best-effort; never raise) ──────────────────────────────────────────────────────────────
def record_send(client_id, ticker, kind, ref, channel, recipient, conn=None):
    if _writes_disabled():
        return None
    own = conn is None
    conn = conn or _conn()
    try:
        cur = conn.cursor()
        _ensure(cur)
        cur.execute("""INSERT INTO lh_delivery (client_id,ticker,kind,ref,channel,recipient)
                       VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (client_id, ticker, kind, str(ref), channel, recipient))
        did = cur.fetchone()[0]
        conn.commit()
        return did
    except Exception:
        try: conn.rollback()
        except Exception: pass
        return None
    finally:
        if own: conn.close()


def _event_from_delivery(delivery_id, event, user_agent):
    if _writes_disabled():
        return
    conn = _conn()
    try:
        cur = conn.cursor()
        _ensure(cur)
        cur.execute("SELECT client_id,ticker,kind,channel FROM lh_delivery WHERE id=%s", (delivery_id,))
        row = cur.fetchone()
        if not row:
            return
        cid, tk, kind, ch = row
        cur.execute("""INSERT INTO lh_engagement (delivery_id,client_id,ticker,kind,channel,event,user_agent)
                       VALUES (%s,%s,%s,%s,%s,%s,%s)""", (delivery_id, cid, tk, kind, ch, event, (user_agent or "")[:300]))
        conn.commit()
    except Exception:
        try: conn.rollback()
        except Exception: pass
    finally:
        conn.close()


def record_open(delivery_id, user_agent=None):
    _event_from_delivery(delivery_id, "open", user_agent)


def record_click(delivery_id, user_agent=None):
    _event_from_delivery(delivery_id, "click", user_agent)


def record_view(client_id, ticker, source, user_agent=None, conn=None):
    """An in-app view. `source` is a label like 'lighthouse_page' or 'today_mirror' (stored in kind)."""
    if _writes_disabled():
        return
    own = conn is None
    conn = conn or _conn()
    try:
        cur = conn.cursor()
        _ensure(cur)
        cur.execute("""INSERT INTO lh_engagement (client_id,ticker,kind,channel,event,user_agent)
                       VALUES (%s,%s,%s,'app','view',%s)""", (client_id, ticker, source, (user_agent or "")[:300]))
        conn.commit()
    except Exception:
        try: conn.rollback()
        except Exception: pass
    finally:
        if own: conn.close()


# ── read (the used-vs-ignored numbers) ──────────────────────────────────────────────────────────────
def summary(client_id, ticker, days=30, conn=None) -> dict:
    own = conn is None
    conn = conn or _conn()
    empty = dict(days=days, emails_sent=0, emails_opened=0, open_rate=None, clicks=0,
                 app_views=0, last_engaged=None)
    try:
        cur = conn.cursor()
        _ensure(cur)
        cur.execute("""SELECT count(*) FROM lh_delivery
                       WHERE client_id=%s AND ticker=%s AND channel='email'
                         AND sent_at >= now() - (%s || ' days')::interval""", (client_id, ticker, days))
        sent = cur.fetchone()[0] or 0
        cur.execute("""SELECT
              count(DISTINCT delivery_id) FILTER (WHERE event='open'),
              count(*) FILTER (WHERE event='click'),
              count(*) FILTER (WHERE event='view'),
              max(ts) FILTER (WHERE event IN ('open','click','view'))
            FROM lh_engagement
            WHERE client_id=%s AND ticker=%s AND ts >= now() - (%s || ' days')::interval""",
                    (client_id, ticker, days))
        opened, clicks, views, last = cur.fetchone()
        opened, clicks, views = opened or 0, clicks or 0, views or 0
        return dict(days=days, emails_sent=sent, emails_opened=opened,
                    open_rate=(opened / sent if sent else None), clicks=clicks,
                    app_views=views, last_engaged=str(last)[:16] if last else None)
    except Exception:
        return empty
    finally:
        if own: conn.close()


# ── url helpers ─────────────────────────────────────────────────────────────────────────────────────
def pixel_url(app_url, delivery_id):
    return f"{app_url.rstrip('/')}/lh/o/{make_token(delivery_id)}" if app_url and delivery_id else None


def click_url(app_url, delivery_id):
    return f"{app_url.rstrip('/')}/lh/c/{make_token(delivery_id)}" if app_url and delivery_id else None
