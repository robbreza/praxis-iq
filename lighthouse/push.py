"""Lighthouse — Web Push (VAPID) phone alerts.

The digest reaches a phone by email; this reaches it as a native-style notification — the "buzz the
phone on a Critical move" half of the mobile plan. Flow: the browser subscribes through the service
worker (using our VAPID public key), we store the subscription, and on a high-tier verdict we send an
encrypted payload to the browser's push service (FCM/Mozilla/Apple), which the SW turns into a
notification. Requires the installed PWA on iOS (16.4+).

Consent is the subscription itself — a user taps "Enable alerts", so push does NOT depend on the email
digest being enabled. Everything here is best-effort and fail-closed: a push failure never affects a
verdict log or the app. Dead subscriptions (410/404) are pruned automatically.

VAPID keys: env-first (VAPID_PUBLIC_KEY / VAPID_PRIVATE_KEY / VAPID_SUBJECT); if unset they are
generated once and persisted to the DB, so there is zero manual setup and the keys stay stable across
restarts (changing them would invalidate every existing subscription).
"""
from __future__ import annotations
import os
import json
import base64

import psycopg2
from core.security import get_database_url

_STATE_KEY = "lighthouse_vapid.json"
_STATE_CLIENT = "_lighthouse"


def _conn():
    return psycopg2.connect(get_database_url())


def _ensure(cur):
    cur.execute("""CREATE TABLE IF NOT EXISTS lh_push_subscription (
        id BIGSERIAL PRIMARY KEY, client_id TEXT, endpoint TEXT UNIQUE, p256dh TEXT, auth TEXT,
        user_agent TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now())""")


# ── VAPID keys (env → db-persisted auto-gen) ───────────────────────────────────────────────────────
def _generate_keys() -> dict:
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import serialization
    priv = ec.generate_private_key(ec.SECP256R1())
    priv_pem = priv.private_bytes(serialization.Encoding.PEM,
                                  serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()).decode()
    raw_pub = priv.public_key().public_bytes(serialization.Encoding.X962,
                                             serialization.PublicFormat.UncompressedPoint)
    app_server_key = base64.urlsafe_b64encode(raw_pub).rstrip(b"=").decode()   # client applicationServerKey
    return {"public": app_server_key, "private_pem": priv_pem}


def get_vapid() -> dict:
    """Return {public, private_pem, subject}. Stable: env, else db, else generate-and-persist."""
    subject = os.environ.get("VAPID_SUBJECT") or "mailto:robbreza@yahoo.com"
    pub, priv = os.environ.get("VAPID_PUBLIC_KEY"), os.environ.get("VAPID_PRIVATE_KEY")
    if pub and priv:
        return {"public": pub, "private_pem": priv, "subject": subject}
    try:
        from core import db
        saved = db.load_json(_STATE_KEY, None, client_id=_STATE_CLIENT)
        if saved and saved.get("public") and saved.get("private_pem"):
            saved["subject"] = subject
            return saved
        keys = _generate_keys()
        db.save_json(_STATE_KEY, keys, client_id=_STATE_CLIENT)
        keys["subject"] = subject
        return keys
    except Exception:
        keys = _generate_keys()          # last resort (non-persistent) — still functional this run
        keys["subject"] = subject
        return keys


def public_key() -> str:
    return get_vapid()["public"]


# ── subscriptions ───────────────────────────────────────────────────────────────────────────────────
def save_subscription(client_id, sub: dict, user_agent=None) -> bool:
    endpoint = (sub or {}).get("endpoint")
    keys = (sub or {}).get("keys") or {}
    p256dh, auth = keys.get("p256dh"), keys.get("auth")
    if not (endpoint and p256dh and auth):
        return False
    conn = _conn()
    try:
        cur = conn.cursor()
        _ensure(cur)
        cur.execute("""INSERT INTO lh_push_subscription (client_id,endpoint,p256dh,auth,user_agent)
                       VALUES (%s,%s,%s,%s,%s)
                       ON CONFLICT (endpoint) DO UPDATE SET client_id=EXCLUDED.client_id,
                         p256dh=EXCLUDED.p256dh, auth=EXCLUDED.auth, user_agent=EXCLUDED.user_agent""",
                    (client_id, endpoint, p256dh, auth, (user_agent or "")[:300]))
        conn.commit()
        return True
    except Exception:
        try: conn.rollback()
        except Exception: pass
        return False
    finally:
        conn.close()


def delete_subscription(endpoint) -> None:
    conn = _conn()
    try:
        cur = conn.cursor()
        _ensure(cur)
        cur.execute("DELETE FROM lh_push_subscription WHERE endpoint=%s", (endpoint,))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def list_subscriptions(client_id) -> list:
    conn = _conn()
    try:
        cur = conn.cursor()
        _ensure(cur)
        cur.execute("SELECT endpoint,p256dh,auth FROM lh_push_subscription WHERE client_id=%s", (client_id,))
        return [{"endpoint": e, "keys": {"p256dh": p, "auth": a}} for e, p, a in cur.fetchall()]
    except Exception:
        return []
    finally:
        conn.close()


# ── sending ───────────────────────────────────────────────────────────────────────────────────────
def _vapid_key(vapid: dict):
    """pywebpush's vapid_private_key wants a Vapid object or a base64url DER — NOT a PEM string (it
    would try to b64url-decode the PEM and fail with an ASN.1 error). Build the object from our PEM."""
    from py_vapid import Vapid01
    return Vapid01.from_pem(vapid["private_pem"].encode())


def _send_one(sub: dict, payload: dict, vapid: dict) -> str:
    """Return 'ok' | 'gone' | 'error'. 'gone' means the subscription is dead and should be pruned."""
    from pywebpush import webpush, WebPushException
    try:
        pk = vapid.get("_obj") or _vapid_key(vapid)
        webpush(subscription_info=sub, data=json.dumps(payload),
                vapid_private_key=pk, vapid_claims={"sub": vapid["subject"]}, ttl=3600)
        return "ok"
    except WebPushException as e:
        code = getattr(getattr(e, "response", None), "status_code", None)
        return "gone" if code in (404, 410) else "error"
    except Exception:
        return "error"


def send_to_client(client_id, title, body, url="/", tag="lighthouse") -> dict:
    """Push to every subscription for a client. Prunes dead ones. Best-effort — never raises."""
    try:
        subs = list_subscriptions(client_id)
        if not subs:
            return {"sent": 0, "total": 0, "pruned": 0}
        vapid = get_vapid()
        try:
            vapid["_obj"] = _vapid_key(vapid)          # build the key object once for the whole fan-out
        except Exception:
            pass
        payload = {"title": title, "body": body, "url": url, "tag": tag}
        sent = pruned = 0
        for s in subs:
            res = _send_one(s, payload, vapid)
            if res == "ok":
                sent += 1
            elif res == "gone":
                delete_subscription(s["endpoint"]); pruned += 1
        return {"sent": sent, "total": len(subs), "pruned": pruned}
    except Exception:
        return {"sent": 0, "total": 0, "pruned": 0, "error": True}


def maybe_push_verdict(v: dict, client_id="usio") -> dict:
    """Tier-gated push for a freshly-logged verdict. Only fires at/above the push floor. Records the
    send to telemetry (channel 'push') for the used-vs-ignored denominator."""
    from lighthouse.digest import priority, _TIER_RANK, config
    pr = priority(v)
    floor = _TIER_RANK.get((os.environ.get("LIGHTHOUSE_DIGEST_PUSH_TIER", "important") or "").lower(), 2)
    if pr["rank"] < floor:
        return {"sent": 0, "reason": "below_floor", "tier": pr["tier"]}
    # Multiple-testing gate (Spec 13.3): the phone is the loudest channel — never buzz it for a day
    # that doesn't survive FDR control (an expected tail event from scanning every session). Only
    # suppress on an explicit False so verdicts predating the gate still push.
    if v.get("fdr_significant") is False:
        return {"sent": 0, "reason": "fdr_gated", "tier": pr["tier"]}
    # Liquidity gate (Spec 13.5): a big move on a thin tape is likely microstructure, not information —
    # don't buzz a phone for it (it's still shown in-app with the liquidity caveat).
    if v.get("thin_tape") is True:
        return {"sent": 0, "reason": "thin_tape", "tier": pr["tier"]}
    c = config()
    title = f"{v['ticker']} {v['actual']*100:+.1f}% — {pr['tier'].upper()}"
    rep = send_to_client(client_id, title, pr["action"], url=(c["app_url"] or "/"))
    if rep.get("sent"):
        try:
            from lighthouse import telemetry
            telemetry.record_send(client_id, v["ticker"], "daily", v["day"], "push", f"{rep['sent']} device(s)")
        except Exception:
            pass
    return {**rep, "tier": pr["tier"]}
