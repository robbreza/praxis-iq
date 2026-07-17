"""
core/peer_watch.py — daily monitoring of USIO's peer group (pure compute).

Watches the two signals we can source for free and honestly:
  • Price / valuation moves — daily % change from the cached market snapshots
    (core.market_data, refreshed for every tracked ticker on the daily refresh).
  • SEC filings — each peer's own recent 8-K / 10-Q / 10-K / merger filings from
    EDGAR's submissions API (core.sec_filings.resolve_cik), cached ~daily.

News / M&A headlines and analyst actions are deliberately NOT invented here —
there is no free, reliable feed for them, and the platform's rule is to show
what's actually sourced, not fabricated. The RPAY-style takeover read-through in
the client's PeerGPT note came from an external tool; if they want that class of
signal in-app, it needs a licensed news feed (flagged, not faked).

Render path reads caches only (instant, never blocks the Today page); the daily
refresh (refresh()) does the network work in the startup/interval background hook.
"""

from datetime import datetime, timedelta, timezone

from config.client_config import CP, CT, get_active_client_id

# |daily %| at or above this is a "notable" mover worth surfacing on Today.
MOVE_THRESHOLD = 3.0
# Corporate filings worth flagging (a peer's own filings, not third-party 13D/G).
_FORMS = {"8-K", "8-K/A", "10-Q", "10-K", "10-K/A", "425", "DEFM14A", "SC 14D9",
          "S-1", "S-4", "6-K", "20-F", "DEFA14A"}
_FILINGS_KEY = "peer_watch_filings.json"
_FILINGS_TTL_HOURS = 20


def _peer_universe(cid):
    """Client + peers, each tagged with tier/segment so the Today card can label
    them (e.g. flag the closest analog, separate reference names)."""
    out = [{"ticker": CT("ticker"), "name": CT("name"), "is_client": True,
            "tier": "client", "segment": "", "closest_analog": False}]
    for p in CP():
        out.append({"ticker": p["ticker"], "name": p["name"], "is_client": False,
                    "tier": p.get("tier", "primary"), "segment": p.get("segment", ""),
                    "closest_analog": bool(p.get("closest_analog"))})
    return out


def movers(cid=None):
    """Every peer with a cached snapshot, sorted by absolute daily move. Reads
    cache only — safe to call on every Today render."""
    from core import market_data
    cid = cid or get_active_client_id()
    out = []
    for p in _peer_universe(cid):
        snap = market_data.get_cached(p["ticker"], cid)
        if not snap or snap.get("pct_change") is None:
            continue
        out.append({**p, "price": snap.get("last_price"), "pct": snap.get("pct_change"),
                    "as_of": snap.get("as_of")})
    out.sort(key=lambda r: -abs(r["pct"] or 0))
    return out


def notable_movers(cid=None, threshold=MOVE_THRESHOLD):
    return [m for m in movers(cid) if abs(m["pct"] or 0) >= threshold]


def _filing_url(cik, accession, doc):
    accn = (accession or "").replace("-", "")
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}"
    return f"{base}/{doc}" if doc else f"{base}/"


def _stale(iso, hours):
    if not iso:
        return True
    try:
        return datetime.now(timezone.utc) - datetime.fromisoformat(iso) > timedelta(hours=hours)
    except Exception:
        return True


def recent_filings(cid=None, days=10, refresh=False):
    """Recent peer SEC filings (cached). refresh=False returns the cache as-is
    (render path); refresh=True hits EDGAR's submissions API per peer and rewrites
    the cache (background daily refresh)."""
    from core import db
    cid = cid or get_active_client_id()
    cache = db.load_json(_FILINGS_KEY, None, client_id=cid)
    if not refresh:
        return (cache or {}).get("filings", [])
    if cache and not _stale(cache.get("fetched_at"), _FILINGS_TTL_HOURS):
        return cache["filings"]

    from core import sec_filings
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).date()
    filings = []
    for p in _peer_universe(cid):
        try:
            cik = sec_filings.resolve_cik(p["ticker"])
            if not cik:
                continue
            data = sec_filings._get(f"https://data.sec.gov/submissions/CIK{cik}.json").json()
            recent = data.get("filings", {}).get("recent", {})
            forms, dates = recent.get("form", []), recent.get("filingDate", [])
            accns, docs = recent.get("accessionNumber", []), recent.get("primaryDocument", [])
            for i, form in enumerate(forms):
                if form not in _FORMS:
                    continue
                try:
                    fdate = datetime.strptime(dates[i], "%Y-%m-%d").date()
                except (ValueError, IndexError):
                    continue
                if fdate < cutoff:
                    continue
                filings.append({
                    "ticker": p["ticker"], "name": p["name"], "is_client": p["is_client"],
                    "form": form, "date": dates[i],
                    "url": _filing_url(cik, accns[i] if i < len(accns) else "",
                                       docs[i] if i < len(docs) else ""),
                })
        except Exception:
            continue
    filings.sort(key=lambda f: f["date"], reverse=True)
    db.save_json(_FILINGS_KEY, {"fetched_at": datetime.now(timezone.utc).isoformat(),
                                "filings": filings}, client_id=cid)
    return filings


def summary(cid=None):
    """Everything the Today card needs, from caches only (never blocks)."""
    cid = cid or get_active_client_id()
    mv = movers(cid)
    return {
        "movers": [m for m in mv if abs(m["pct"] or 0) >= MOVE_THRESHOLD],
        "all_movers": mv,
        "filings": recent_filings(cid),
        "as_of": mv[0]["as_of"] if mv else None,
    }


def refresh(cid=None):
    """Daily background refresh: repopulate peer snapshots and re-pull filings.
    Called from the startup / interval hook, never from a render path."""
    cid = cid or get_active_client_id()
    log = {"run_at": datetime.now(timezone.utc).isoformat()}
    try:
        from core import market_data
        market_data.refresh_all(cid)
        log["snapshots"] = "ok"
    except Exception as e:
        log["snapshots"] = f"failed: {e}"
    try:
        n = len(recent_filings(cid, refresh=True))
        log["filings"] = f"{n} recent"
    except Exception as e:
        log["filings"] = f"failed: {e}"
    return log
