"""core/speakers.py — the CONFIRMED earnings-call speaker lineup, per client, per quarter.

WHY
The script's persona roster used to come straight from static registry config (ir_contact +
executives). A departure (USIO's IR head leaving) silently propagated a stale name into a
client-facing script, and "fixing" it by editing the registry corrupted the PRIOR quarter's record
(whose script was correctly that person's). Earnings-call lineups also legitimately change quarter
to quarter — a new CFO, someone travelling, a guest.

WHAT
A per-quarter confirmed lineup. Script generation is BLOCKED until the reporting quarter's speakers
are confirmed (see earnings_page's gate), the confirmation is stored per period so history stays
accurate, and a quarter rollover forces a fresh confirm — a lineup can never quietly carry forward.

Store: db key "confirmed_speakers.json", client-scoped:
    {period: {"confirmed_at": iso, "speakers": [{"role","name","title","speaking"}]}}
`speaking` False = on the lineup / available for Q&A, but not a prepared-remarks speaker.
"""
from datetime import datetime

from core import db

_KEY = "confirmed_speakers.json"


def _resolve(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def current_period(client_id=None):
    """The reporting quarter whose lineup must be confirmed — the client's current_quarter.
    None when the client has no earnings period configured (then the gate simply doesn't apply)."""
    from config.client_config import get_client
    return ((get_client(client_id).get("earnings") or {}).get("current_quarter") or "").strip() or None


def _store(cid):
    return db.load_json(_KEY, {}, client_id=cid) or {}


def get_confirmed(period, client_id=None):
    """The confirmed record for a period ({confirmed_at, speakers}) or None."""
    if not period:
        return None
    return _store(_resolve(client_id)).get(period)


def is_confirmed(period, client_id=None):
    return bool(get_confirmed(period, client_id))


def default_lineup(client_id=None):
    """Prefill for the confirmation form: the MOST RECENTLY confirmed lineup (carrying prior edits
    and departures forward as the starting point), else the registry roster on first use."""
    cid = _resolve(client_id)
    store = _store(cid)
    if store:
        latest = max(store.values(), key=lambda v: v.get("confirmed_at", ""))
        return [dict(s) for s in latest.get("speakers", []) if s.get("name")]
    from config.client_config import role_roster
    return [{"role": e["role_key"], "name": e.get("name", ""), "title": e.get("title") or "",
             "speaking": True} for e in role_roster(cid)]


def confirm(period, speakers, client_id=None):
    """Persist the confirmed lineup for `period`. Drops rows with no name."""
    cid = _resolve(client_id)
    store = _store(cid)
    clean = [{"role": s.get("role"), "name": (s.get("name") or "").strip(),
              "title": (s.get("title") or "").strip(), "speaking": bool(s.get("speaking", True))}
             for s in speakers if (s.get("name") or "").strip()]
    store[period] = {"confirmed_at": datetime.now().isoformat(timespec="seconds"), "speakers": clean}
    db.save_json(_KEY, store, client_id=cid)
    return store[period]


def speaking_roster(period, client_id=None):
    """The confirmed lineup filtered to prepared-remarks speakers — what the script targets."""
    rec = get_confirmed(period, client_id)
    return [s for s in (rec or {}).get("speakers", []) if s.get("speaking") and s.get("name")]
