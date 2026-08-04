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
from config.client_config import get_active_client_id
from core import db

CALENDAR_KEY = "ir_conference_calendar.csv"


def load_events(client_id=None):
    return db.load_json(CALENDAR_KEY, None, client_id=client_id or get_active_client_id()) or []


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
