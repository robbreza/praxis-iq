"""
core/ndr_calendar.py — export an NDR trip as an iCalendar (.ics) file so every
meeting (with its join link for virtual stops) imports into Outlook / Google
Calendar / Apple Calendar in one click.

Design notes:
* One VEVENT per meeting. Scheduled meetings get a real timed event; meetings
  with no time ("—") become an all-day event on their day so they still land on
  the calendar as a to-be-slotted placeholder.
* TIMEZONE — done correctly, not floating. A meeting's wall-clock time ("9:00
  AM") is interpreted in the TRIP CITY's timezone (an NDR is anchored to one
  city/zone) and emitted as a UTC instant (…Z) via zoneinfo, so it displays at
  the right local time in any attendee's calendar regardless of their own zone.
  This matters for a multi-city roadshow: a 9 AM LA meeting shows as 12 PM for
  an attendee on the East Coast, not 9 AM.
* LOCATION is the street address for in-person stops; for virtual stops it's the
  format ("Virtual" / "Zoom" …) and the join link goes in URL + DESCRIPTION.
* Self-contained: stdlib only (datetime + zoneinfo, both in Py3.9+).
"""

import re
from datetime import datetime, timedelta

try:
    from zoneinfo import ZoneInfo
    _HAVE_TZ = True
except Exception:  # pragma: no cover - zoneinfo is stdlib on 3.9+
    _HAVE_TZ = False

_DEFAULT_MEETING_MIN = 45  # default meeting length when we only have a start time

# Trip metro/city label -> IANA timezone. Falls back to America/New_York.
_METRO_TZ = {
    "New York Metro": "America/New_York", "Boston / New England": "America/New_York",
    "Philadelphia / Baltimore": "America/New_York", "Florida (Miami / Tampa)": "America/New_York",
    "Chicago / Midwest": "America/Chicago", "Texas (Dallas / Austin)": "America/Chicago",
    "Denver / Mountain West": "America/Denver",
    "Los Angeles / SoCal": "America/Los_Angeles", "San Francisco / Bay Area": "America/Los_Angeles",
}


def canonical_metro(city_label):
    """Resolve a free-text trip city onto the canonical metro vocabulary.

    THE TRIP CITY IS FREE TEXT AND THREE SEPARATE LOOKUPS KEY OFF IT EXACTLY:
    _METRO_TZ here, routing._METRO_FOCUS, and the buy-side list's Metro field. Nothing
    validated it, so a trip saved as "Boston" instead of "Boston / New England" missed all
    three — silently, because each one falls back rather than raising.

    Boston's timezone survived that BY LUCK: the fallback is America/New_York, which is
    Boston's timezone anyway. A trip saved as "Denver" would put every meeting in the .ics
    TWO HOURS WRONG, and "Los Angeles" three — an investor gets a calendar invite at the
    wrong time and nothing anywhere reports an error.

    Matching on the leading segment ("Boston" -> "Boston / New England") because that is
    how the labels actually diverge in the data.
    """
    t = (city_label or "").strip()
    if not t:
        return t
    if t in _METRO_TZ:
        return t
    low = t.lower()
    for canon in _METRO_TZ:
        cl = canon.lower()
        if cl.split("/")[0].strip() == low or low.split("/")[0].strip() == cl.split("/")[0].strip():
            return canon
    return t


def known_metros():
    """The canonical vocabulary. Anything not in here will silently fall back."""
    return sorted(_METRO_TZ)


def tz_name_for(city_label):
    """IANA timezone name for a trip's city/metro (America/New_York fallback).

    Normalises first — see canonical_metro(). Without that a mislabelled trip gets
    America/New_York and ships a .ics with the wrong meeting time.
    """
    canon = canonical_metro(city_label)
    if canon not in _METRO_TZ and (city_label or "").strip():
        print(f"[ndr] city {city_label!r} does not resolve to a known metro — timezone falling "
              f"back to America/New_York, which may be WRONG. Known: {known_metros()}")
    return _METRO_TZ.get(canon, "America/New_York")


def _tz_for(city_label):
    if _HAVE_TZ:
        try:
            return ZoneInfo(tz_name_for(city_label))
        except Exception:
            return None
    return None


def meeting_datetime(trip, m):
    """Timezone-aware local start datetime for a meeting, or None when it's
    unscheduled or the trip has no parseable date. Shared by the .ics export and
    the Zoom meeting creator so both place a meeting at the same instant."""
    start_date = _trip_start_date(trip)
    tmin = _parse_time_min(m.get("time"))
    tz = _tz_for(trip.get("city"))
    if not (start_date and tmin is not None and tz is not None):
        return None
    day = int(m.get("day", 1) or 1)
    return datetime(start_date.year, start_date.month, start_date.day,
                    tmin // 60, tmin % 60, tzinfo=tz) + timedelta(days=day - 1)


def _trip_start_date(trip):
    """First calendar date of the trip, from its 'dates' string. Accepts
    '2026-09-11 to 09-12', '2026-08-19', 'Sep 11-12' (best-effort). None if
    unparseable."""
    s = (trip.get("dates") or "").strip()
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3))).date()
        except ValueError:
            return None
    return None


def _parse_time_min(s):
    s = (s or "").strip().upper().replace(".", "")
    if not s or s == "—":
        return None
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            t = datetime.strptime(s, fmt)
            return t.hour * 60 + t.minute
        except Exception:
            continue
    return None


def _esc(s):
    """iCalendar text escaping (RFC 5545): backslash, comma, semicolon, newline."""
    return (str(s or "").replace("\\", "\\\\").replace("\n", "\\n")
            .replace(",", "\\,").replace(";", "\\;"))


def _fold(line):
    """Fold a content line to <=75 octets per RFC 5545 (continuation lines start
    with a space)."""
    out, cur = [], line
    while len(cur.encode("utf-8")) > 75:
        # step back to a boundary that keeps the chunk <=75 bytes
        cut = 74
        while len(cur[:cut].encode("utf-8")) > 74:
            cut -= 1
        out.append(cur[:cut])
        cur = " " + cur[cut:]
    out.append(cur)
    return "\r\n".join(out)


def _utc_stamp(dt_utc):
    return dt_utc.strftime("%Y%m%dT%H%M%SZ")


def build_ics(trip, ticker, contacts=None, address_for=None):
    """Return the .ics document (str) for a trip.

    contacts: optional dict{name->{name,title,...}} to enrich the attendee line.
    address_for: optional callable(name)->street address, so a meeting with no
    typed address still gets its fund's office (matches the itinerary)."""
    contacts = contacts or {}
    start_date = _trip_start_date(trip)
    tz = _tz_for(trip.get("city"))
    now_stamp = (datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
                 if _HAVE_TZ else datetime.now().strftime("%Y%m%dT%H%M%SZ"))
    trip_name = trip.get("name", "NDR")

    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//Praxis Point IR//NDR Planner//EN", "CALSCALE:GREGORIAN",
             "METHOD:PUBLISH"]

    for i, m in enumerate(trip.get("meetings", [])):
        inst = m.get("institution", "Meeting")
        virtual = m.get("format", "In-person") != "In-person"
        uid = f"ndr-{re.sub(r'[^A-Za-z0-9]+','', trip_name)[:24]}-{i}@praxispoint"
        day = int(m.get("day", 1) or 1)

        ev = ["BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{now_stamp}"]

        tmin = _parse_time_min(m.get("time"))
        if start_date and tmin is not None and tz is not None:
            local = datetime(start_date.year, start_date.month, start_date.day,
                             tmin // 60, tmin % 60, tzinfo=tz) + timedelta(days=day - 1)
            end = local + timedelta(minutes=_DEFAULT_MEETING_MIN)
            ev.append(f"DTSTART:{_utc_stamp(local.astimezone(ZoneInfo('UTC')))}")
            ev.append(f"DTEND:{_utc_stamp(end.astimezone(ZoneInfo('UTC')))}")
        elif start_date:
            # Unscheduled (or no tz): all-day placeholder on the meeting's day.
            d = start_date + timedelta(days=day - 1)
            nxt = d + timedelta(days=1)
            ev.append(f"DTSTART;VALUE=DATE:{d.strftime('%Y%m%d')}")
            ev.append(f"DTEND;VALUE=DATE:{nxt.strftime('%Y%m%d')}")
        else:
            # No parseable trip date at all — skip (can't place it on a calendar).
            continue

        kind = m.get("format", "In-person")
        ev.append(_fold(f"SUMMARY:{_esc(ticker)} NDR — {_esc(inst)}"
                        + (f" ({_esc(kind)})" if virtual else "")))

        # Location: street address (own or fund book) for in-person; format for virtual.
        addr = (m.get("address") or "").strip()
        if not addr and address_for and not virtual:
            try:
                addr = (address_for(inst) or "").strip()
            except Exception:
                addr = ""
        loc = kind if virtual else (addr or trip.get("city", ""))
        if loc:
            ev.append(_fold(f"LOCATION:{_esc(loc)}"))

        link = (m.get("meeting_link") or "").strip()
        if virtual and link:
            ev.append(_fold(f"URL:{_esc(link)}"))

        # Description: who, holder status, score, join link, notes.
        cc = contacts.get(inst, {})
        who = m.get("contact") or ", ".join(p for p in (cc.get("name"), cc.get("title")) if p)
        parts = []
        if who:
            parts.append(f"With: {who}")
        parts.append("Holder" if not m.get("non_holder", True) else "Non-holder — priority target")
        if m.get("score") is not None:
            parts.append(f"Engagement score {m['score']}/100")
        if virtual:
            parts.append(f"Join ({kind}): {link or 'link TBD'}")
        if m.get("notes"):
            parts.append(f"Note: {m['notes']}")
        if trip.get("sponsor_bank"):
            parts.append(f"Sponsor: {trip['sponsor_bank']}")
        ev.append(_fold(f"DESCRIPTION:{_esc(chr(10).join(parts))}"))

        ev.append("END:VEVENT")
        lines.extend(ev)

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
