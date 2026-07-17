"""
core/jitsi_meetings.py — instant, free video-meeting links via Jitsi Meet.

Unlike Zoom/Teams/Meet, a Jitsi meeting needs no account, no API, and no
credentials: the meeting simply IS a URL. We mint a hard-to-guess room name and
return `https://meet.jit.si/<room>`. Opening the link starts the meeting; anyone
you send it to joins the same room.

PRIVACY: public meet.jit.si rooms are reachable by anyone who has the link (like
an unlisted Zoom link with no password). We defend that by making the room name
unguessable — a slugged label plus a random token — which is appropriate for
one-off investor calls. For stronger control (lobby/password enforced up front,
JWT auth) point `jitsi_domain` at a self-hosted instance or 8x8's JaaS; the link
format is identical, so nothing else changes.
"""

import re
import secrets

from core import db

_DEFAULT_DOMAIN = "meet.jit.si"


def _domain():
    d = (db.load_json("settings.json", {}) or {}).get("jitsi_domain", "") or _DEFAULT_DOMAIN
    return d.strip().rstrip("/").replace("https://", "").replace("http://", "") or _DEFAULT_DOMAIN


def _slug(s, maxlen=28):
    """Alnum room-safe slug from a label (Jitsi rooms dislike spaces/punctuation)."""
    return re.sub(r"[^A-Za-z0-9]+", "", (s or "").title())[:maxlen]


def create_link(label="NDR", token_bytes=5):
    """A ready-to-use Jitsi meeting URL with an unguessable room name. `label`
    is a human hint baked into the room (e.g. 'USIO NDR Ancora Advisors'); the
    random token is what actually keeps it private."""
    room = f"{_slug(label) or 'NDR'}-{secrets.token_hex(token_bytes)}"
    return f"https://{_domain()}/{room}"
