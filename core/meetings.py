"""core/meetings.py — one canonical read model over the two meeting stores.

The IR team's meetings live in two physically different stores with incompatible shapes:
  • scheduled_meetings.json    — standalone 1x1s (absolute Date; Contact/Firm/Side/Time/Type/…)
  • ndr_trips.json[].meetings  — NDR 1x1s (a day-offset + slot; the absolute date comes from the trip)

Every surface (Calendar overlay, Meeting Hub, NDR) re-derived those fields and the date itself. This
module normalizes BOTH into one record so they read the same everywhere. Pure read, client-scoped;
writes still go through the page forms (store-unification is a later phase). This is the single source
of truth for meeting date resolution — the Calendar's Phase-0 parsers were lifted here.
"""
import re
from datetime import datetime, timedelta

from core import db

_SIDE = {"buy-side": "buy", "sell-side": "sell", "buy": "buy", "sell": "sell"}


def parse_ymd(s):
    """Tolerant YYYY-MM-DD parse → date or None (never raises)."""
    try:
        return datetime.strptime((s or "").strip()[:10], "%Y-%m-%d").date()
    except Exception:
        return None


def parse_trip_start(dates_str):
    """Best-effort absolute start date from a trip's free-text `dates` (often 'TBD'). None → the
    trip's meetings are undated and can't be placed on an absolute calendar."""
    s = (dates_str or "").strip()
    if not s or s.upper() == "TBD":
        return None
    d = parse_ymd(s)
    if d:
        return d
    m = re.match(r"([A-Za-z]{3,9})\s+(\d{1,2})(?:\s*[–-]\s*\d{1,2})?,?\s*(\d{4})", s)
    if m:
        for fmt in ("%b %d %Y", "%B %d %Y"):
            try:
                return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", fmt).date()
            except Exception:
                pass
    return None


def _record(**kw):
    base = {"id": None, "source": None, "contact": "", "firm": "", "side": None,
            "date": None, "time": "", "type": "", "status": "", "priority": "",
            "location": "", "topic": "", "meeting_link": "", "non_holder": None,
            "group": None, "date_tbd": False, "editable": True}
    base.update(kw)
    return base


def normalize_scheduled(m):
    """A scheduled_meetings.json row → canonical meeting record."""
    return _record(
        id=m.get("id"), source="scheduled",
        contact=m.get("Contact", ""), firm=m.get("Firm", ""),
        side=_SIDE.get((m.get("Side") or "").strip().lower()),
        date=parse_ymd(m.get("Date")), time=m.get("Time", ""),
        type=m.get("Type", ""), status=m.get("Status", ""), priority=m.get("Priority", ""),
        topic=m.get("Topic", ""),
    )


def normalize_ndr(trip, m, _start=None):
    """A ndr_trips.json meeting (+ its trip) → canonical record. Absolute date = trip start + the
    meeting's day offset; date_tbd=True when the trip has no resolvable start date."""
    start = _start if _start is not None else parse_trip_start(trip.get("dates"))
    date, tbd = None, True
    if start is not None:
        try:
            date = start + timedelta(days=max(0, int(m.get("day", 1) or 1) - 1))
            tbd = False
        except Exception:
            date, tbd = None, True
    return _record(
        id=(m.get("id") or f"{trip.get('name', '')}:{m.get('institution', '')}:{m.get('day', '')}"),
        source="ndr",
        contact=m.get("contact", ""), firm=m.get("institution", ""),
        side="buy",                                   # an NDR is a roadshow of investor meetings
        date=date, time=(m.get("time", "") if m.get("time") != "—" else ""),
        type=m.get("type", ""), status=m.get("status", ""),
        location=trip.get("city", ""), topic=m.get("notes", ""),
        meeting_link=m.get("meeting_link", ""), non_holder=m.get("non_holder"),
        group=trip.get("name"), date_tbd=tbd,
    )


def all_meetings(cid, include_undated=True):
    """A client's meetings — standalone 1x1s + NDR trip meetings — as canonical records.
    include_undated=False drops NDR meetings on TBD-dated trips (no absolute date to place)."""
    out = []
    for m in (db.load_json("scheduled_meetings.json", [], client_id=cid) or []):
        out.append(normalize_scheduled(m))
    for t in (db.load_json("ndr_trips.json", [], client_id=cid) or []):
        start = parse_trip_start(t.get("dates"))
        for m in (t.get("meetings") or []):
            if m.get("type") == "break":              # slot-grid filler, not a real meeting
                continue
            rec = normalize_ndr(t, m, _start=start)
            if rec["date_tbd"] and not include_undated:
                continue
            out.append(rec)
    return out


def undated_ndr_count(cid):
    """Count of NDR meetings that can't be placed (their trip's dates are TBD) — for a 'set the trip
    dates' nudge on the calendar."""
    return sum(1 for r in all_meetings(cid) if r["source"] == "ndr" and r["date_tbd"])
