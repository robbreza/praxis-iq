"""
core/market_data.py — free, delayed market data (yfinance), cached in the
market_data_cache table (see core/db.py).

The user confirmed there's no existing market data vendor and a paid feed
isn't needed: up to a 60-minute delay is acceptable. yfinance (wraps
Yahoo Finance's public quote endpoint) fits that exactly — free, no API
key/signup required, and Yahoo's own quotes already carry a real-time-ish
but not guaranteed-instant delay, which is well inside what's been asked
for here.

Same shape as core/sec_filings.py's SEC EDGAR integration, deliberately:
a _fetch_one() that hits the network and can fail, a cache read/write pair
backed by the database instead of a file, a staleness check, and a
refresh_all() that both a startup hook and a manual "Refresh" button can
call. Any network failure (no route, Yahoo rate-limiting, an unknown
ticker) is caught and logged, never raised up into a page render — the UI
falls back to whatever's cached, or a plain "not yet fetched" state.

Network note: this module's yfinance calls have not been exercised against
the real network in development — the sandbox this was built in has no
route to Yahoo Finance's servers (only pypi.org, for pip installs is
reachable; confirmed via direct curl test). The caching/staleness/
fallback logic is unit-tested against a stubbed fetch function instead.
Live behavior needs to be verified on a machine with normal internet
access — same situation as core/sec_filings.py.
"""

from datetime import datetime, timedelta

from core import db

DEFAULT_STALE_MINUTES = 60


def _resolve_client_id(client_id):
    if client_id is not None:
        return client_id
    from config.client_config import get_active_client_id
    return get_active_client_id()


def tracked_tickers():
    """Active client's own ticker plus its full peer set — same universe
    core/sec_filings.py tracks, kept as a separate call (not imported from
    there) so this module has no hard dependency on sec_filings.py."""
    from config.client_config import C, CP
    client = C()
    peers = [p["ticker"] for p in CP() if p.get("ticker")]
    return [client["ticker"]] + [t for t in peers if t != client["ticker"]]


def _fetch_one(ticker):
    """Hits yfinance for one ticker's latest snapshot. Returns a dict or
    None on any failure (network, rate limit, bad ticker) — callers must
    handle None, never assume this succeeds."""
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).fast_info
        last_price = float(info["last_price"])
        prev_close = float(info["previous_close"])
        pct_change = ((last_price - prev_close) / prev_close * 100) if prev_close else None
        volume = int(info["last_volume"]) if info.get("last_volume") is not None else None
        avg_vol = info.get("ten_day_average_volume") or info.get("three_month_average_volume")
        avg_vol = int(avg_vol) if avg_vol is not None else None
        return {
            "last_price": last_price, "prev_close": prev_close, "pct_change": pct_change,
            "volume": volume, "avg_volume_10d": avg_vol, "as_of": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"[market_data] fetch failed for {ticker}: {e}")
        return None


def _save_snapshot(ticker, snap, client_id=None):
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.is_postgres()
    try:
        cur = conn.cursor()
        if pg:
            cur.execute(
                "INSERT INTO market_data_cache (client_id, ticker, last_price, prev_close, pct_change, "
                "volume, avg_volume_10d, as_of, fetched_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s, now()) "
                "ON CONFLICT (client_id, ticker) DO UPDATE SET last_price=EXCLUDED.last_price, "
                "prev_close=EXCLUDED.prev_close, pct_change=EXCLUDED.pct_change, volume=EXCLUDED.volume, "
                "avg_volume_10d=EXCLUDED.avg_volume_10d, as_of=EXCLUDED.as_of, fetched_at=EXCLUDED.fetched_at",
                (cid, ticker, snap["last_price"], snap["prev_close"], snap["pct_change"],
                 snap["volume"], snap["avg_volume_10d"], snap["as_of"]),
            )
        else:
            cur.execute(
                "INSERT INTO market_data_cache (client_id, ticker, last_price, prev_close, pct_change, "
                "volume, avg_volume_10d, as_of, fetched_at) VALUES (?,?,?,?,?,?,?,?,?) "
                "ON CONFLICT(client_id, ticker) DO UPDATE SET last_price=excluded.last_price, "
                "prev_close=excluded.prev_close, pct_change=excluded.pct_change, volume=excluded.volume, "
                "avg_volume_10d=excluded.avg_volume_10d, as_of=excluded.as_of, fetched_at=excluded.fetched_at",
                (cid, ticker, snap["last_price"], snap["prev_close"], snap["pct_change"],
                 snap["volume"], snap["avg_volume_10d"], snap["as_of"], datetime.now().isoformat()),
            )
        conn.commit()
    finally:
        conn.close()


def get_cached(ticker, client_id=None):
    """Whatever's in the cache for this ticker, or None if it's never been
    fetched. Does not trigger a fetch — pure read."""
    cid = _resolve_client_id(client_id)
    conn = db.get_connection()
    pg = db.is_postgres()
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(
            f"SELECT last_price, prev_close, pct_change, volume, avg_volume_10d, as_of, fetched_at "
            f"FROM market_data_cache WHERE client_id = {ph} AND ticker = {ph}",
            (cid, ticker),
        )
        row = cur.fetchone()
        if not row:
            return None
        # Postgres' NUMERIC columns come back via psycopg2 as decimal.Decimal,
        # not float — SQLite's REAL columns always come back as plain float,
        # which is why this only ever surfaced once Neon was actually reachable.
        # Every page does plain float arithmetic on these (pt_avg / last_price,
        # EV / revenue, etc.), so normalize to float/int here once, at the
        # single read path, instead of patching every call site.
        def _f(v):
            return float(v) if v is not None else None

        def _i(v):
            return int(v) if v is not None else None

        return {
            "last_price": _f(row[0]), "prev_close": _f(row[1]), "pct_change": _f(row[2]),
            "volume": _i(row[3]), "avg_volume_10d": _i(row[4]), "as_of": str(row[5]), "fetched_at": str(row[6]),
        }
    finally:
        conn.close()


def _is_stale(fetched_at_str, max_age_minutes=DEFAULT_STALE_MINUTES):
    try:
        fetched_at = datetime.fromisoformat(fetched_at_str.replace("Z", "+00:00")) if "T" in fetched_at_str else datetime.fromisoformat(fetched_at_str)
        # Strip tz-awareness for a simple same-clock comparison — this cache
        # is only ever read/written by this one app process.
        fetched_at = fetched_at.replace(tzinfo=None)
        return (datetime.now() - fetched_at) > timedelta(minutes=max_age_minutes)
    except Exception:
        return True


def get_snapshot(ticker, refresh_if_stale=True, max_age_minutes=DEFAULT_STALE_MINUTES, client_id=None):
    """Cache-first accessor — the one most pages should call. Returns
    cached data immediately if fresh; refreshes first if stale (or never
    fetched) and refresh_if_stale is True. Always returns whatever's
    available (fresh, stale, or None) rather than blocking indefinitely —
    a failed refresh just falls back to the stale cache."""
    cached = get_cached(ticker, client_id)
    if cached and not _is_stale(cached["fetched_at"], max_age_minutes):
        return cached
    if refresh_if_stale:
        fresh = _fetch_one(ticker)
        if fresh:
            _save_snapshot(ticker, fresh, client_id)
            return get_cached(ticker, client_id)
    return cached  # possibly stale, possibly None — caller decides how to show that


def refresh_all(client_id=None):
    """Refresh every tracked ticker (active client + peers). Meant to be
    called from a non-blocking startup hook (see app_nicegui.py) and from
    a manual "Refresh" button, same pattern as sec_filings.refresh_all."""
    results = []
    for ticker in tracked_tickers():
        snap = _fetch_one(ticker)
        if snap:
            _save_snapshot(ticker, snap, client_id)
            results.append({"ticker": ticker, "ok": True})
        else:
            results.append({"ticker": ticker, "ok": False})
    log = {"run_at": datetime.now().isoformat(), "results": results}
    db.save_json("market_data_refresh_log.json", log, client_id=client_id)
    return log


def get_last_refresh_log(client_id=None):
    return db.load_json("market_data_refresh_log.json", None, client_id=client_id)
