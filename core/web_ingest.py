"""core/web_ingest.py — turn raw website-traffic events into web_flow visitor rows.

The site's capture snippet posts per-session events (pageview / download / demo_request,
carrying a firm + email when a visitor self-identifies) through a serverless function into
the `web_events` table. This module groups those events by session into the visitor shape
core/web_flow.py expects and writes them to the tenant's `web_flow_visitors.json` store, so
the existing analyzer (intent scoring, downloader/reader split, hot prospects) renders live
traffic with no change.

Praxis's own marketing site uses tenant 'praxis'; identified visitors there are prospective
CLIENTS (leads), since the site is marketing, not an IR page — so is_holder is always False
and every identified firm is a lead. The same pipe can later serve a client's IR site by
writing events under that client's id (and matching is_holder against its 13F holders).
"""
import re
from datetime import datetime, timezone

from core import db

PRAXIS_TENANT = "praxis"

_EVENT_COLS = ["session_id", "event_type", "path", "asset", "org", "email",
               "utm_source", "referrer", "created_at"]


def _ph(conn):
    return "%s" if db.connection_is_postgres(conn) else "?"


def record_event(tenant, session_id, event_type, path=None, asset=None, org=None,
                 email=None, utm_source=None, referrer=None, created_at=None):
    """Insert one raw event. Used by tests and any in-app capture; in production the same
    row shape is written by the serverless function. created_at defaults to now (UTC)."""
    conn = db.get_connection()
    try:
        ph = _ph(conn)
        conn.cursor().execute(
            f"INSERT INTO web_events (tenant, session_id, event_type, path, asset, org, email, "
            f"utm_source, referrer, created_at) VALUES ({', '.join([ph] * 10)})",
            (tenant, session_id, event_type, path, asset, org, email, utm_source, referrer,
             created_at or datetime.now(timezone.utc).isoformat()))
        conn.commit()
    finally:
        conn.close()


def _events_for(tenant):
    conn = db.get_connection()
    try:
        ph = _ph(conn)
        cur = conn.cursor()
        cur.execute(
            f"SELECT {', '.join(_EVENT_COLS)} FROM web_events WHERE tenant = {ph} ORDER BY created_at",
            (tenant,))
        return [dict(zip(_EVENT_COLS, r)) for r in cur.fetchall()]
    finally:
        conn.close()


def _minutes(timestamps):
    """Session length in whole minutes from first→last event; a single-event session is ~1."""
    parsed = []
    for t in timestamps:
        try:
            parsed.append(datetime.fromisoformat(str(t).replace("Z", "+00:00")))
        except Exception:
            pass
    if len(parsed) < 2:
        return 1
    return max(1, round((max(parsed) - min(parsed)).total_seconds() / 60))


_public_idx = {"map": None}


def _public_index():
    """Public-company lookup built once (per process) from sec_filings.ticker_name_map():
      by_name   — {distinctive-name-key: {'ticker','name'}}  (e.g. "Roper Technologies" -> ROP)
      by_ticker — {TICKER: {'ticker','name'}}                 (e.g. a hand-typed "Msft" -> MSFT)."""
    if _public_idx["map"] is None:
        from core import sec_filings, web_flow
        by_name, by_ticker = {}, {}
        for tk, name in (sec_filings.ticker_name_map() or {}).items():
            entry = {"ticker": tk, "name": name}
            by_ticker[tk.upper()] = entry
            key = web_flow._org_key(name)
            if key and key not in by_name:
                by_name[key] = entry
        _public_idx["map"] = {"by_name": by_name, "by_ticker": by_ticker}
    return _public_idx["map"]


def public_match(org):
    """If an identified visitor firm is a public company, return {'ticker','name'}, else None.
    Matches conservatively: first a distinctive-name-token match against SEC company_tickers
    (e.g. "Roper Technologies" -> ROP), then, for a short ticker-like string, a direct ticker
    match (e.g. a hand-typed "Msft" / "MSFT" -> Microsoft). No fuzzy guessing."""
    if not org or org == "New — unidentified":
        return None
    from core import web_flow
    idx = _public_index()
    hit = idx["by_name"].get(web_flow._org_key(org))
    if hit:
        return hit
    tk = re.sub(r"[^A-Za-z]", "", org).upper()
    if 1 <= len(tk) <= 5:                       # only a short, ticker-shaped string
        return idx["by_ticker"].get(tk)
    return None


def _session_to_visitor(events):
    """One session's events → a web_flow visitor row (see core/web_flow._normalize)."""
    pageviews = [e for e in events if e["event_type"] == "pageview"]
    downloads = [e["asset"] for e in events if e["event_type"] == "download" and e.get("asset")]
    if any(e["event_type"] == "demo_request" for e in events):
        downloads.append("Demo request")
    ident = next((e for e in events if (e.get("org") or "").strip()), None)
    org = (ident or {}).get("org")
    pub = public_match(org)
    return {
        "org": org or "New — unidentified",
        "category": "Identified lead" if org else "New — unidentified",
        "is_holder": False,   # praxispointir.com is marketing — visitors are leads, not holders
        "ticker": pub["ticker"] if pub else None,     # public-company flag
        "pages": len(pageviews) or len(events),
        "minutes": _minutes([e.get("created_at") for e in events]),
        "visits": 1,
        "downloads": downloads,
        "email": (ident or {}).get("email"),
        "last_visit": str(max((e.get("created_at") or "" for e in events), default=""))[:10],
    }


def aggregate(tenant=PRAXIS_TENANT, save=True):
    """Group web_events for `tenant` by session into web_flow visitor rows, one per session,
    and (by default) persist them to that tenant's web_flow_visitors.json so the analyzer
    renders them. Returns {sessions, identified, rows}."""
    by_session = {}
    for e in _events_for(tenant):
        by_session.setdefault(e["session_id"], []).append(e)
    rows = [_session_to_visitor(evs) for evs in by_session.values()]
    if save:
        db.save_json("web_flow_visitors.json", rows, client_id=tenant)
    return {"sessions": len(rows),
            "identified": sum(1 for r in rows if r["category"] == "Identified lead"),
            "rows": rows}
