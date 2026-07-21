"""core/rating_actions.py — analyst rating CHANGES (upgrade / downgrade / initiate / PT move) per ticker.

Source: Yahoo Finance via yfinance (`Ticker.upgrades_downgrades`) — the SAME free, no-key library we
already use for prices. It returns NAMED sell-side actions with date, firm, from/to grade, action code,
and the price-target move, going back years. For USIO that's the covering-desk trail — HC Wainwright,
Ladenburg, Maxim, Litchfield, Barrington — a real market-timing signal that also doubles as a genuine
PT-history source. Because Yahoo returns the full history, refresh() is a one-shot BACKFILL.

NOT included: quant / aggregator wire items (Verus, Zacks, Refinitiv via Investars). Those ride a paid
feed (Benzinga / Investars) that Yahoo doesn't carry — see the note in the UI. An empty result means
Yahoo returned nothing; nothing here is fabricated.

(An earlier version used Finnhub's /stock/upgrade-downgrade — verified premium-gated on the free tier,
403 "no access" — so we switched to the free yfinance source, which is richer for the covering desks
and needs no API key.)
"""
from config.client_config import CT, get_active_client_id
from core import db

_STORE_KEY = "rating_actions.json"   # per-client store

# yfinance/Yahoo `action` codes -> (verb, glyph) for display.
_ACTION = {
    "up":   ("upgraded", "▲"),
    "down": ("downgraded", "▼"),
    "init": ("initiated", "●"),
    "main": ("maintained", "→"),
    "reit": ("reiterated", "→"),
}


def _f(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except Exception:
        return None


def _norm(row, ticker):
    gd = row.get("GradeDate")
    try:
        date = gd.date().isoformat()
    except Exception:
        date = str(gd)[:10] if gd else None
    firm = str(row.get("Firm") or "").strip()
    to = str(row.get("ToGrade") or "").strip()
    frm = str(row.get("FromGrade") or "").strip()
    action = str(row.get("Action") or "").strip().lower()
    ptc, ptp = _f(row.get("currentPriceTarget")), _f(row.get("priorPriceTarget"))
    return {
        "ticker": ticker, "firm": firm, "from_grade": frm, "to_grade": to,
        "action": action, "date": date,
        "pt_current": ptc, "pt_prior": ptp,
        "pt_action": str(row.get("priceTargetAction") or "").strip(),
        # stable id so re-fetches de-dupe rather than pile up
        "id": f"{ticker}|{firm}|{date}|{to}|{ptc}",
    }


def refresh(cid=None, ticker=None):
    """Pull Yahoo's full analyst-action history for the ticker and merge it into the per-client
    store (this IS the backfill). Returns the stored list. Network error / empty -> returns the
    existing store unchanged, with a typed `.last_status` so callers can react without raising."""
    cid = cid or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    existing = db.load_json(_STORE_KEY, [], client_id=cid) or []
    if not tk:
        refresh.last_status = "no_ticker"
        return existing
    try:
        import yfinance as yf
        ud = yf.Ticker(tk).upgrades_downgrades
    except Exception as e:
        refresh.last_status = f"error:{type(e).__name__}"
        return existing
    if ud is None or len(ud) == 0:
        refresh.last_status = "empty"
        return existing

    by_id = {i["id"]: i for i in existing if i.get("id")}
    try:
        for _, row in ud.reset_index().iterrows():
            item = _norm(row, tk)
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
    """One-line human form: 'Ladenburg Thalmann maintained Buy · PT $5.75 → $6.25 (2026-05-15)'."""
    verb, _ = _ACTION.get(item.get("action"), ("changed", "•"))
    frm, to = item.get("from_grade"), item.get("to_grade")
    grade = f"{frm} → {to}" if (frm and to and frm != to) else (to or frm or "")
    s = f"{item.get('firm')} {verb}" + (f" {grade}" if grade else "")
    ptc, ptp = item.get("pt_current"), item.get("pt_prior")
    if ptc:
        s += f" · PT ${ptp:.2f} → ${ptc:.2f}" if (ptp and ptp != ptc) else f" · PT ${ptc:.2f}"
    if item.get("date"):
        s += f" ({item['date']})"
    return s


def glyph(item):
    return _ACTION.get(item.get("action"), ("", "•"))[1]
