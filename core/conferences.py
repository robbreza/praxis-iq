"""core/conferences.py — the IR conference & events calendar store, one door.

The calendar the Calendar page shows and the events an email invite adds both live
in the SAME db store ("ir_conference_calendar.csv" — JSON despite the legacy key
name). The event-row dict used to be hand-written in three places (calendar_page's
Add-Event form, the inbox "Add to Calendar" confirm closure, and the seed), which is
how the two writers could drift and how the email path silently dropped the parsed
organizer. This centralizes:

  - add_event(): append a normalized row (idempotent on Event+Date), used by BOTH the
    manual Add-Event form and the email-invite "Add to Calendar" path.
  - parse_ics() / extract_from_attachments(): pull {event_name,date,location,organizer}
    out of a real .ics attachment, so an invite that carries an ICS is read from the
    ICS (exact) instead of guessed from prose.

Every writer produces exactly the canonical field set, so the Calendar page, the
CSV export, and Today's upcoming-events read never see a half-populated row.
"""
import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta

from config.client_config import get_active_client_id
from core import db

try:
    from zoneinfo import ZoneInfo
    _HAVE_TZ = True
except Exception:  # pragma: no cover — zoneinfo is stdlib on 3.9+
    _HAVE_TZ = False

CALENDAR_KEY = "ir_conference_calendar.csv"


def load_events(client_id=None):
    return db.load_json(CALENDAR_KEY, None, client_id=client_id or get_active_client_id()) or []


def busy_attendees_on(date_str, client_id=None):
    """People already committed to a calendar event on `date_str` — {lower(name): event}.
    Lets the inbox flag which executives are already booked when an invite comes in."""
    import re
    out = {}
    ds = (str(date_str or "")).strip()
    if not ds:
        return out
    for e in load_events(client_id):
        if str(e.get("Date", "")).strip() != ds:
            continue
        for nm in re.split(r"[,+/;]", str(e.get("Attending") or "")):
            nm = nm.strip()
            if nm and nm.upper() not in ("TBD", "MANAGEMENT + IR", "—"):
                out.setdefault(nm.lower(), e.get("Event"))
    return out


def save_events(events, client_id=None):
    db.save_json(CALENDAR_KEY, events, client_id=client_id or get_active_client_id())


def _clean(v):
    return (str(v).strip() if v is not None else "")


def add_event(*, event, date=None, location=None, organizer=None, event_type="Conference",
              status="Invited — pending confirmation", deadline="—", notes="",
              source="Email invite", attending="TBD", priority="Medium", client_id=None):
    """Append a normalized event row to the calendar store.

    Idempotent on (Event, Date): a same-name, same-date event already present is not
    duplicated (so re-confirming a re-sent invite, or an auto-path plus a manual add,
    can't double-book). Returns (row, added: bool) — added is False when it was already
    on the calendar.
    """
    events = load_events(client_id)
    row = {
        "Event": _clean(event), "Type": event_type or "Conference",
        "Date": _clean(date) or "TBD", "Location": _clean(location) or "—",
        "Organizer": _clean(organizer) or "—", "Status": status,
        "Deadline": _clean(deadline) or "—", "Notes": _clean(notes), "Source": source,
        "Attending": _clean(attending) or "TBD", "Priority": priority or "Medium",
    }
    key = (row["Event"].lower(), row["Date"])
    for e in events:
        if (_clean(e.get("Event")).lower(), _clean(e.get("Date")) or "TBD") == key and row["Event"]:
            return e, False  # already on the calendar
    events.append(row)
    save_events(events, client_id)
    return row, True


# ── .ics parsing (RFC 5545, minimal — no external dependency) ─────────────────────
def _unfold(text):
    """RFC 5545 line folding: a line break followed by a space or tab continues the
    previous logical line."""
    return (text.replace("\r\n", "\n").replace("\r", "\n")
                .replace("\n ", "").replace("\n\t", ""))


def _ics_date(value):
    """DTSTART value → 'YYYY-MM-DD'. Handles '20260603', '20260603T140000Z', etc.
    (the property PARAMS before the ':' are stripped by the caller)."""
    digits = value.strip()[:8]
    if len(digits) == 8 and digits.isdigit():
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}"
    return None


def parse_ics(file_bytes):
    """Best-effort {event_name, date, location, organizer} from a VEVENT. Returns {}
    if the bytes aren't a parseable calendar. Never raises."""
    try:
        text = file_bytes.decode("utf-8", "ignore") if isinstance(file_bytes, (bytes, bytearray)) else str(file_bytes)
    except Exception:
        return {}
    if "BEGIN:VEVENT" not in text.upper():
        return {}
    out = {}
    for line in _unfold(text).split("\n"):
        if ":" not in line:
            continue
        name, _, value = line.partition(":")
        prop = name.split(";", 1)[0].strip().upper()
        value = value.strip()
        if prop == "SUMMARY" and value:
            out["event_name"] = value.replace("\\,", ",").replace("\\;", ";")
        elif prop == "DTSTART":
            d = _ics_date(value)
            if d:
                out["date"] = d
        elif prop == "LOCATION" and value:
            out["location"] = value.replace("\\,", ",").replace("\\n", " ").replace("\\;", ";")
        elif prop == "ORGANIZER":
            cn = None
            for param in name.split(";")[1:]:
                if param.strip().upper().startswith("CN="):
                    cn = param.split("=", 1)[1].strip().strip('"')
            out["organizer"] = cn or value.replace("mailto:", "").strip()
    return out


def extract_from_attachments(attachments):
    """Scan (filename, content_type, bytes) tuples for a .ics / text-calendar
    attachment and return its parsed fields, or {}. First parseable calendar wins."""
    for item in attachments or []:
        try:
            fn, ctype, data = item[0], item[1], item[2]
        except (TypeError, IndexError):
            continue
        if (fn or "").lower().endswith(".ics") or "calendar" in (ctype or "").lower():
            fields = parse_ics(data)
            if fields:
                return fields
    return {}


# ── .ics EXPORT — put IR events into the team's real Outlook / Google calendar ────
# Our events carry a Date (YYYY-MM-DD) but no clock time, so each becomes an ALL-DAY
# VEVENT. Reuses the RFC-5545 escaping/folding approach proven in core/ndr_calendar.py.

# Our free-text Status → the three RFC-5545 VEVENT states an external calendar renders.
_ICS_STATUS = {
    "confirmed": "CONFIRMED", "scheduled": "CONFIRMED", "completed": "CONFIRMED",
    "declined": "CANCELLED",
}


def _ics_esc(s):
    """RFC 5545 text escaping: backslash, comma, semicolon, newline."""
    return (str(s or "").replace("\\", "\\\\").replace("\n", "\\n")
            .replace(",", "\\,").replace(";", "\\;"))


def _ics_fold(line):
    """Fold a content line to <=75 octets (continuation lines start with a space)."""
    out, cur = [], line
    while len(cur.encode("utf-8")) > 75:
        cut = 74
        while len(cur[:cut].encode("utf-8")) > 74:
            cut -= 1
        out.append(cur[:cut])
        cur = " " + cur[cut:]
    out.append(cur)
    return "\r\n".join(out)


def _now_stamp():
    if _HAVE_TZ:
        return datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def _event_uid(event):
    """A STABLE UID (from event name + date) so a subscribed calendar updates the same
    entry on each refresh instead of duplicating it."""
    basis = f"{_clean(event.get('Event')).lower()}|{_clean(event.get('Date'))}"
    return f"ircal-{hashlib.md5(basis.encode('utf-8')).hexdigest()[:20]}@praxispoint"


def event_to_vevent(event):
    """VEVENT lines for one event (all-day). Returns [] if it has no parseable date —
    a 'TBD' event can't be placed on a calendar."""
    try:
        d = datetime.strptime(_clean(event.get("Date")), "%Y-%m-%d").date()
    except Exception:
        return []
    nxt = d + timedelta(days=1)
    ev = ["BEGIN:VEVENT", f"UID:{_event_uid(event)}", f"DTSTAMP:{_now_stamp()}",
          f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}",
          f"DTEND;VALUE=DATE:{nxt.strftime('%Y%m%d')}",
          _ics_fold(f"SUMMARY:{_ics_esc(event.get('Event') or 'IR event')}")]
    loc = _clean(event.get("Location"))
    if loc and loc != "—":
        ev.append(_ics_fold(f"LOCATION:{_ics_esc(loc)}"))
    desc = []
    for label, key in [("Type", "Type"), ("Organizer", "Organizer"), ("Status", "Status"),
                       ("Attending", "Attending"), ("Registration deadline", "Deadline")]:
        val = _clean(event.get(key))
        if val and val not in ("—", "TBD"):
            desc.append(f"{label}: {val}")
    if _clean(event.get("Notes")):
        desc.append(_clean(event.get("Notes")))
    if desc:
        ev.append(_ics_fold(f"DESCRIPTION:{_ics_esc(chr(10).join(desc))}"))
    st = _ICS_STATUS.get(_clean(event.get("Status")).lower())
    if st:
        ev.append(f"STATUS:{st}")
    ev.append("TRANSP:TRANSPARENT")  # an all-day IR event shouldn't mark the day busy
    ev.append("END:VEVENT")
    return ev


def events_to_ics(events, cal_name="IR Calendar", ttl_hours=12):
    """Full VCALENDAR for a list of events (undated ones skipped). The refresh hints
    tell a subscribed Outlook/Google to re-pull roughly twice a day."""
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//Praxis Point IR//IRconnect Calendar//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH", _ics_fold(f"X-WR-CALNAME:{_ics_esc(cal_name)}"),
             f"X-PUBLISHED-TTL:PT{int(ttl_hours)}H",
             f"REFRESH-INTERVAL;VALUE=DURATION:PT{int(ttl_hours)}H"]
    for e in events or []:
        lines.extend(event_to_vevent(e))
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def event_ics(event, cal_name="IR Calendar"):
    """Single-event VCALENDAR — for a one-click 'add to my calendar' download."""
    return events_to_ics([event], cal_name=cal_name)


# ── Subscribable feed token ───────────────────────────────────────────────────────
# An HMAC-signed tenant id, so a per-client feed URL (/calendar/<token>.ics) can't be
# guessed or enumerated — only the app, holding IRCONNECT_STORAGE_SECRET, mints them.
# Same construction as lighthouse.telemetry's signed pixel/click tokens.
def _feed_secret():
    return (os.environ.get("IRCONNECT_STORAGE_SECRET") or "lighthouse-dev-secret").encode()


def feed_token(client_id):
    body = base64.urlsafe_b64encode(str(client_id).encode()).decode().rstrip("=")
    sig = hmac.new(_feed_secret(), body.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{body}.{sig}"


def parse_feed_token(token):
    """Return the client_id encoded in a feed token, or None if the signature is bad."""
    try:
        body, sig = token.split(".", 1)
        good = hmac.new(_feed_secret(), body.encode(), hashlib.sha256).hexdigest()[:16]
        if not hmac.compare_digest(sig, good):
            return None
        return base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode()
    except Exception:
        return None
