"""core/rating_actions.py — analyst rating CHANGES (upgrade / downgrade / initiate) per ticker.

Source: Finnhub `/stock/upgrade-downgrade` — structured firm / from-grade / to-grade / date events,
returned HISTORICALLY. This catches the quant & aggregator rating moves (Verus, Zacks, etc.) that a
plain headline scraper misses — and, as the May 2026 Verus SELL->HOLD on USIO showed (right off the
$1.03 low), those can be strong market-timing signals. Distinct from the client's own covering
sell-side desks (HCW, Ladenburg, ...), which live in the analyst registry.

Because Finnhub returns the full history, refresh() doubles as the BACKFILL — one call pulls the
whole rating-change trail for the ticker, not just this week's.

The API key is read from env `FINNHUB_API_KEY` and NEVER logged. The user pastes it into .env;
Claude never handles the value. With no key, every function degrades to the cached store (or empty)
and the UI shows a "connect your key" prompt. Nothing here is ever fabricated — an empty result
means the source returned nothing (or no key yet).
"""
import os
from datetime import datetime, timezone

from config.client_config import CT, get_active_client_id
from core import db

_STORE_KEY = "rating_actions.json"   # per-client store
_BASE = "https://finnhub.io/api/v1/stock/upgrade-downgrade"

# Finnhub `action` codes -> (verb, glyph) for display.
_ACTION = {
    "up":   ("upgraded", "▲"),
    "down": ("downgraded", "▼"),
    "init": ("initiated", "●"),
    "main": ("maintained", "→"),
    "reit": ("reiterated", "→"),
}


def api_key():
    return (os.environ.get("FINNHUB_API_KEY") or "").strip()


def has_key():
    return bool(api_key())


def _norm(raw, ticker):
    gt = raw.get("gradeTime")
    try:
        date = datetime.fromtimestamp(int(gt), timezone.utc).date().isoformat() if gt else None
    except Exception:
        date = None
    firm = (raw.get("company") or "").strip()
    return {
        "ticker": ticker,
        "firm": firm,
        "from_grade": (raw.get("fromGrade") or "").strip(),
        "to_grade": (raw.get("toGrade") or "").strip(),
        "action": (raw.get("action") or "").strip().lower(),   # up / down / init / main / reit
        "date": date,
        # stable id so re-fetches de-dupe rather than pile up
        "id": f"{ticker}|{firm}|{gt}|{(raw.get('toGrade') or '').strip()}",
    }


def refresh(cid=None, ticker=None):
    """Fetch Finnhub's full upgrade/downgrade history for the ticker and merge it into the
    per-client store (this IS the backfill — Finnhub returns history, not just recent). Returns
    the stored list. No key or network error -> returns the existing store unchanged.

    Returns a small status dict via the `.last_status` attribute for callers that want to
    distinguish "no key" / "premium/forbidden" / "ok" without raising on a render path."""
    cid = cid or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    existing = db.load_json(_STORE_KEY, [], client_id=cid) or []
    if not tk:
        refresh.last_status = "no_ticker"
        return existing
    if not has_key():
        refresh.last_status = "no_key"
        return existing

    import requests
    by_id = {i["id"]: i for i in existing if i.get("id")}
    try:
        r = requests.get(_BASE, params={"symbol": tk, "token": api_key()}, timeout=20)
        if r.status_code in (401, 403):
            # free tier may not include this endpoint on some accounts — surface, don't crash
            refresh.last_status = "forbidden"
            return existing
        r.raise_for_status()
        rows = r.json() or []
        for raw in rows:
            item = _norm(raw, tk)
            if item["firm"] and item["date"]:
                by_id[item["id"]] = item
        refresh.last_status = "ok"
    except Exception as e:
        refresh.last_status = f"error:{type(e).__name__}"
        return existing

    out = sorted(by_id.values(), key=lambda i: i.get("date") or "", reverse=True)
    db.save_json(_STORE_KEY, out, client_id=cid)
    return out


refresh.last_status = None


def recent(cid=None, limit=None, ticker=None):
    """Read the stored rating changes for the ticker (never fetches — safe on a render path)."""
    cid = cid or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    items = [i for i in (db.load_json(_STORE_KEY, [], client_id=cid) or [])
             if (i.get("ticker") or "").upper() == tk]
    items.sort(key=lambda i: i.get("date") or "", reverse=True)
    return items[:limit] if limit else items


def describe(item):
    """One-line human form: 'Verus upgraded Sell -> Hold (2026-05-18)'."""
    verb, _ = _ACTION.get(item.get("action"), ("changed", "•"))
    frm, to = item.get("from_grade"), item.get("to_grade")
    move = f"{frm} → {to}" if frm and to else (to or frm or "")
    return f"{item.get('firm')} {verb} {move}".strip() + (f" ({item['date']})" if item.get("date") else "")


def glyph(item):
    return _ACTION.get(item.get("action"), ("", "•"))[1]
