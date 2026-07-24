"""core/sandbox.py — reset a client tenant's user-generated ("sandbox") data.

For letting a client operator (e.g. Paul at USIO) explore with a read-write login,
then wiping what they created back to a clean slate. Clears only PER-TENANT,
user-generated stores for one client_id — never the shared house data (fund-lineup
crosswalk, relationship-quality notes, account identities), which are global and
curated across every client.
"""
from core import db

# (db key, empty value, human label) — every per-tenant store a client can write to.
_STORES = [
    ("ndr_trips.json", [], "NDR trips"),
    ("prospects.json", [], "Promoted prospects"),
    ("ndr_requests.json", [], "Inbound NDR requests"),
    ("scheduled_meetings.json", [], "Scheduled meetings"),
    ("meeting_log.csv", [], "Meeting log entries"),
    ("crm_interactions", [], "Logged interactions"),
    ("confirmed_speakers.json", {}, "Confirmed speaker lineups"),
    ("call_opening.json", {}, "Call-opening edits"),
]


def _count(v):
    return len(v) if hasattr(v, "__len__") else (1 if v else 0)


def preview(cid):
    """{label: count} of what a reset WOULD clear for this tenant (non-empty stores only)."""
    out = {}
    for key, empty, label in _STORES:
        n = _count(db.load_json(key, empty, client_id=cid))
        if n:
            out[label] = n
    return out


def reset_tenant(cid):
    """Clear every per-tenant user-generated store for `cid`. Returns {label: count} of
    what was cleared. Global / house data is untouched. Caller must be staff (writes go
    through the normal db path, so a read-only session would be refused anyway)."""
    cleared = {}
    for key, empty, label in _STORES:
        n = _count(db.load_json(key, empty, client_id=cid))
        db.save_json(key, [] if isinstance(empty, list) else {}, client_id=cid)
        if n:
            cleared[label] = n
    return cleared
