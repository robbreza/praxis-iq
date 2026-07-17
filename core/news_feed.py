"""
core/news_feed.py — free news feed for the peer group, on a rolling 7-day window.

Source is Yahoo Finance news via yfinance (the same library already used for
prices — no API key, no cost). Each refresh fetches recent headlines for USIO and
every peer, merges them into a single store, drops anything older than 7 days,
de-dupes by article id, and overwrites the store — so it always holds a rolling
past-7-days window and never grows unbounded.

A paid feed (Benzinga / FMP / Polygon — see the cost note in the demo) would add
breaking speed and deeper M&A/press-wire coverage; it can drop in behind the same
refresh()/recent() interface by adding a provider that reads its key from .env.
Nothing here fabricates news — an empty window means the sources had nothing.
"""

from datetime import datetime, timedelta, timezone

from config.client_config import CP, CT, get_active_client_id

_STORE_KEY = "peer_news.json"
_WINDOW_DAYS = 7


def _tickers():
    return [CT("ticker")] + [p["ticker"] for p in CP()]


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _pub_dt(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    except Exception:
        return None


def _parse_item(ticker, raw):
    """Normalize one yfinance news record. Yahoo nests the real fields under
    `content`; older shapes are flat, so fall back to the top level."""
    c = raw.get("content", raw) or {}
    title = (c.get("title") or raw.get("title") or "").strip()
    if not title:
        return None
    url = ((c.get("clickThroughUrl") or {}).get("url")
           or (c.get("canonicalUrl") or {}).get("url")
           or raw.get("link"))
    provider = (c.get("provider") or {}).get("displayName") or raw.get("publisher") or ""
    pub = c.get("pubDate") or c.get("displayTime")
    if not pub and raw.get("providerPublishTime"):
        try:
            pub = datetime.fromtimestamp(raw["providerPublishTime"], timezone.utc).isoformat()
        except Exception:
            pub = None
    return {
        "id": raw.get("id") or url or title,
        "ticker": ticker,
        "title": title,
        "provider": provider,
        "url": url,
        "summary": (c.get("summary") or c.get("description") or "")[:280],
        "pub": pub or _now_iso(),   # undated → treat as just-seen so it ages out
    }


def refresh(cid=None):
    """Fetch Yahoo news for every tracked ticker, merge into the store, age out
    anything past the 7-day window, de-dupe, and overwrite. Returns the window."""
    import yfinance as yf
    from core import db
    cid = cid or get_active_client_id()
    by_id = {i["id"]: i for i in (db.load_json(_STORE_KEY, [], client_id=cid) or []) if i.get("id")}

    for t in _tickers():
        try:
            for raw in (yf.Ticker(t).news or []):
                item = _parse_item(t, raw)
                if not item:
                    continue
                # Preserve the original publish/first-seen time on re-fetch so a
                # re-surfaced article still ages out on its real date.
                if item["id"] in by_id and by_id[item["id"]].get("pub"):
                    item["pub"] = by_id[item["id"]]["pub"]
                by_id[item["id"]] = item
        except Exception:
            continue

    cutoff = datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)
    kept = [i for i in by_id.values()
            if (_pub_dt(i.get("pub")) is None or _pub_dt(i.get("pub")) >= cutoff)]
    kept.sort(key=lambda i: i.get("pub") or "", reverse=True)
    db.save_json(_STORE_KEY, kept, client_id=cid)
    return kept


def recent(cid=None, limit=None, ticker=None):
    """Read the rolling window from cache (never fetches — safe on a render path)."""
    from core import db
    cid = cid or get_active_client_id()
    items = db.load_json(_STORE_KEY, [], client_id=cid) or []
    if ticker:
        items = [i for i in items if i.get("ticker") == ticker]
    items.sort(key=lambda i: i.get("pub") or "", reverse=True)
    return items[:limit] if limit else items
