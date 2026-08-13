"""core/quarter_roll.py — persistent reporting-quarter roll-forward.

The reporting quarter (client `earnings.current_quarter` / `earnings_date`) is a
per-client, time-varying fact. It lives in the DB `clients` overlay, NOT the code
seed — the seed is only the first-run baseline. So advancing the quarter MUST go
through `client_store.upsert_client(..., merge=True)` + `reload_registry()`, or the
stale DB overlay silently masks any in-memory/seed change and a restart reverts it
(exactly how the app got stuck pre-report on Q2 while the seed said Q3).

`roll_forward_quarter()` is the single correct way to advance a quarter. Pure
label math is split out (`next_quarter_label`) so it stays unit-testable with no I/O.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta

_Q_RE = re.compile(r"^\s*Q([1-4])\s+(\d{4})\s*$")


def next_quarter_label(q: str) -> str:
    """'Q3 2026' -> 'Q4 2026'; 'Q4 2026' -> 'Q1 2027'. Returns the input unchanged
    if it isn't a recognizable 'Q# YYYY' label (never guesses)."""
    m = _Q_RE.match(q or "")
    if not m:
        return q
    qn, yr = int(m.group(1)), int(m.group(2))
    return f"Q{qn + 1} {yr}" if qn < 4 else f"Q1 {yr + 1}"


def _estimate_next_earnings_date(prev_date: str) -> str | None:
    """Estimate the next call date as ~one quarter (91 days) after the previous one.
    An estimate the user can refine, not a hard fact — returns None if the previous
    date isn't parseable so we never fabricate a date out of nothing."""
    try:
        d = datetime.strptime((prev_date or "")[:10], "%Y-%m-%d").date()
    except Exception:
        return None
    return (d + timedelta(days=91)).isoformat()


def roll_forward_quarter(client_id=None, new_quarter: str | None = None,
                         new_earnings_date: str | None = None) -> dict:
    """Advance the client's reporting quarter and PERSIST it (DB overlay + registry
    reload), so it survives a restart. The quarter just closing becomes last_quarter
    and its date becomes last_earnings_date.

    new_quarter / new_earnings_date override the computed values (use them when the
    company has given a real next-call date); otherwise the quarter label advances by
    one and the date is estimated ~91 days out. Returns the persisted earnings dict.
    Raises if there's no current quarter to advance from."""
    from config.client_config import CE, get_active_client_id, reload_registry
    from core import client_store

    cid = client_id or get_active_client_id()
    ce = dict(CE() or {})
    cur_q = (ce.get("current_quarter") or "").strip()
    if not cur_q:
        raise ValueError("No current_quarter set for this client — nothing to roll forward from.")

    nxt_q = (new_quarter or "").strip() or next_quarter_label(cur_q)
    if nxt_q == cur_q:
        raise ValueError(f"Next quarter '{nxt_q}' equals the current quarter — refusing a no-op roll.")

    nxt_date = new_earnings_date or _estimate_next_earnings_date(ce.get("earnings_date"))

    updated = {
        "current_quarter": nxt_q,
        "earnings_date": nxt_date,
        "last_quarter": cur_q,
        "last_earnings_date": ce.get("earnings_date"),
    }
    # merge=True: overlay only these fields onto the client's existing DB record.
    client_store.upsert_client(cid, {"earnings": updated}, merge=True)
    reload_registry()   # rebuild CLIENT_REGISTRY in place so the live app sees it now
    return updated
