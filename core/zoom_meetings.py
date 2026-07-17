"""
core/zoom_meetings.py — create Zoom meetings from the NDR planner via Zoom's
Server-to-Server OAuth API, so marking a meeting "Zoom" mints the join link
automatically (no more paste).

WHY SERVER-TO-SERVER OAUTH
Zoom deprecated JWT apps in 2023. For a backend that acts as the account (no
end-user login redirect), the current path is a Server-to-Server OAuth app: it
authenticates with an Account ID + Client ID + Client Secret and returns a
short-lived bearer token. Free with any Zoom account — no per-meeting charge.

CREDENTIALS live in Settings (`settings.json` → zoom_account_id / zoom_client_id
/ zoom_client_secret) or the matching ZOOM_* env vars. `is_configured()` gates
everything; unset → the planner just keeps the paste-a-link field.

SCOPE the Zoom app needs: meeting:write (create/delete meetings) —
`meeting:write:admin` in classic scopes, or the granular
`meeting:write:meeting:admin`.
"""

import base64
import os
import time

import requests

from core import db

_TOKEN_URL = "https://zoom.us/oauth/token"
_API = "https://api.zoom.us/v2"
_TIMEOUT = 15
# In-process token cache (tokens last ~1h; refetched with a 60s safety margin).
_TOK = {"token": None, "exp": 0.0}


def _creds():
    s = db.load_json("settings.json", {}) or {}
    return (
        (s.get("zoom_account_id") or os.environ.get("ZOOM_ACCOUNT_ID", "")).strip(),
        (s.get("zoom_client_id") or os.environ.get("ZOOM_CLIENT_ID", "")).strip(),
        (s.get("zoom_client_secret") or os.environ.get("ZOOM_CLIENT_SECRET", "")).strip(),
    )


def is_configured():
    return all(_creds())


def _zoom_error(resp):
    """Pull Zoom's human error message out of a failed response."""
    try:
        j = resp.json()
        return j.get("message") or j.get("error") or resp.text[:200]
    except Exception:
        return resp.text[:200]


def _token(force=False):
    aid, cid, csec = _creds()
    if not (aid and cid and csec):
        raise RuntimeError("Zoom credentials are not set.")
    now = time.time()
    if not force and _TOK["token"] and _TOK["exp"] > now + 60:
        return _TOK["token"]
    auth = base64.b64encode(f"{cid}:{csec}".encode()).decode()
    r = requests.post(_TOKEN_URL,
                      params={"grant_type": "account_credentials", "account_id": aid},
                      headers={"Authorization": f"Basic {auth}"}, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise RuntimeError(f"Zoom auth failed ({r.status_code}): {_zoom_error(r)}")
    d = r.json()
    _TOK["token"] = d["access_token"]
    _TOK["exp"] = now + int(d.get("expires_in", 3600))
    return _TOK["token"]


def create_meeting(topic, start_utc=None, duration_min=45, timezone_name="America/New_York"):
    """Create a Zoom meeting and return {'join_url','id','start_url'}.

    start_utc: a timezone-aware/naive UTC datetime for a scheduled meeting; None
    makes an instant meeting (still returns a usable join link)."""
    tok = _token()
    body = {
        "topic": (topic or "NDR meeting")[:200],
        "type": 2 if start_utc else 1,          # 2 = scheduled, 1 = instant
        "duration": int(duration_min),
        "timezone": timezone_name,
        "settings": {"join_before_host": True, "waiting_room": True,
                     "meeting_authentication": False},
    }
    if start_utc:
        body["start_time"] = start_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    r = requests.post(f"{_API}/users/me/meetings",
                      headers={"Authorization": f"Bearer {tok}",
                               "Content-Type": "application/json"},
                      json=body, timeout=_TIMEOUT)
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Zoom create failed ({r.status_code}): {_zoom_error(r)}")
    d = r.json()
    return {"join_url": d.get("join_url"), "id": d.get("id"),
            "start_url": d.get("start_url")}


def delete_meeting(meeting_id):
    try:
        requests.delete(f"{_API}/meetings/{meeting_id}",
                        headers={"Authorization": f"Bearer {_token()}"}, timeout=_TIMEOUT)
    except Exception:
        pass


def test():
    """Settings Test button: create then delete a throwaway meeting — this
    validates the credentials AND the meeting:write scope in one shot. Returns
    (ok, message)."""
    if not is_configured():
        return False, "Zoom credentials not set."
    try:
        m = create_meeting("Praxis Point IR — connection test", duration_min=1)
    except Exception as e:
        return False, str(e)
    if m.get("id"):
        delete_meeting(m["id"])
    return True, "Working — created and removed a test meeting successfully."
