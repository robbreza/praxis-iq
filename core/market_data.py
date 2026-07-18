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

import threading
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


# Tickers with no Yahoo quote that just burn slow 404 retries on every refresh —
# skip them so one dead symbol can't stall the whole snapshot pass (and, at
# startup, starve the websocket connection into a reconnect loop).
#
# FI (Fiserv) doesn't resolve on yfinance under its post-rebrand ticker. It was
# dropped from the peer set on 2026-07-16, so this entry is inert today — kept
# because the fact is verified and re-adding FI would otherwise reintroduce the
# 404 stall. NOTE: this guard only covers _fetch_one(); get_fundamentals() has its
# own path and was still 404ing on FI until it left the peer set.
_YF_SKIP = {"FI"}


# ─────────────────────────────────────────────────────────────────────────
# Per-process snapshot memo.
#
# get_snapshot() reads market_data_cache in Neon — a CLOUD database, so every call
# is a ~98ms network round-trip. live_ev() calls it once per company and the board
# package fans out to 27 calls in a single render: **2.6 seconds of latency to
# re-read a row that already said the same thing.**
#
# This does NOT change staleness. The row it reads is refreshed on its own 60-minute
# cadence by the refresh pass; this only stops us asking Neon the same question
# dozens of times inside one render. TTL is deliberately short (30s) so a manual
# refresh is still felt immediately.
_SNAP_MEMO_TTL = timedelta(seconds=30)
_snap_memo = {}
_snap_memo_lock = threading.Lock()


def _snapshot_memo_get(key):
    with _snap_memo_lock:
        hit = _snap_memo.get(key)
        if hit and datetime.now() - hit[0] < _SNAP_MEMO_TTL:
            return hit[1]
    return None


def _snapshot_memo_put(key, val):
    with _snap_memo_lock:
        _snap_memo[key] = (datetime.now(), val)


def clear_snapshot_memo():
    """Drop the per-process snapshot memo — call after a manual refresh."""
    with _snap_memo_lock:
        _snap_memo.clear()


def _fetch_one(ticker):
    """Hits yfinance for one ticker's latest snapshot. Returns a dict or
    None on any failure (network, rate limit, bad ticker) — callers must
    handle None, never assume this succeeds."""
    if (ticker or "").upper() in _YF_SKIP:
        return None
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        info = tk.fast_info

        # yfinance FastInfo resolves BOTH snake_case and camelCase via subscript
        # (info["last_volume"] and info["lastVolume"] both work), but .get() does
        # NOT alias — in current yfinance versions info.get("last_volume") returns
        # None even though info["last_volume"] returns the value. The old code read
        # price via subscript (worked) but guarded volume with .get() (always None),
        # which is why the Today page's "volume vs 10-day avg" showed no value. Read
        # every field via guarded subscript so it's robust to key casing/version.
        def _fi(*keys):
            for k in keys:
                try:
                    v = info[k]
                except Exception:
                    v = None
                if v is not None:
                    return v
            return None

        last_price = _fi("last_price")
        prev_close = _fi("previous_close")
        _vol = _fi("last_volume")
        _avg = _fi("ten_day_average_volume", "three_month_average_volume")

        # Fallback for tickers whose fast_info comes back empty (CSGS is flaky on
        # the fast endpoint; a rebranded symbol may only resolve on the heavier
        # .info quote). Fall back to the regular-market last price, then to the
        # previous close / open when there's no intraday print — so the peer-watch
        # mover list still gets a price rather than dropping the name.
        if last_price is None or prev_close is None:
            try:
                di = tk.info or {}
            except Exception:
                di = {}
            if last_price is None:
                last_price = (di.get("regularMarketPrice") or di.get("currentPrice")
                              or di.get("regularMarketPreviousClose") or di.get("previousClose")
                              or di.get("regularMarketOpen") or di.get("open"))
            if prev_close is None:
                prev_close = di.get("regularMarketPreviousClose") or di.get("previousClose")
            if _vol is None:
                _vol = di.get("regularMarketVolume") or di.get("volume")
            if _avg is None:
                _avg = di.get("averageDailyVolume10Day") or di.get("averageVolume")

        if last_price is None:
            return None
        last_price = float(last_price)
        prev_close = float(prev_close) if prev_close is not None else last_price
        pct_change = ((last_price - prev_close) / prev_close * 100) if prev_close else None
        volume = int(_vol) if _vol is not None else None
        avg_vol = int(_avg) if _avg is not None else None
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
    pg = db.connection_is_postgres(conn)
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
    pg = db.connection_is_postgres(conn)
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
    # Per-process memo first — see _SNAP_MEMO_TTL. Only short-circuits the FRESH path,
    # so a stale row still takes the refresh branch below and nothing gets served older
    # than it would have been.
    _mk = (ticker.upper(), client_id)
    _m = _snapshot_memo_get(_mk)
    if _m is not None:
        return _m
    cached = get_cached(ticker, client_id)
    if cached and not _is_stale(cached["fetched_at"], max_age_minutes):
        _snapshot_memo_put(_mk, cached)
        return cached
    if refresh_if_stale:
        fresh = _fetch_one(ticker)
        if fresh:
            _save_snapshot(ticker, fresh, client_id)
            out = get_cached(ticker, client_id)
            _snapshot_memo_put(_mk, out)
            return out
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


# ─────────────────────────────────────────────────────────────────────────
# Fundamentals — gross margin, EV, and EV/Revenue from Yahoo (yfinance's
# heavier .info call), for the peer-benchmarking analysis. Free, no key.
# Cached in the JSON store (fundamentals move slowly — 24h TTL). `ev_positive`
# flags names whose enterprise value is non-positive (a bank's cash holds
# customer deposits; net-cash names) — those aren't EV-comparable and the
# benchmark drops them from the EV ranking. Same "None on any failure" contract
# as _fetch_one: callers must handle a miss.
# ─────────────────────────────────────────────────────────────────────────
_YAHOO_SYMBOL = {"PAX": "0327.HK"}   # peer ticker -> Yahoo symbol for non-US listings


def _yahoo_symbol(ticker):
    return _YAHOO_SYMBOL.get(ticker.upper(), ticker)


def _fetch_fundamentals(ticker):
    try:
        import yfinance as yf
        info = yf.Ticker(_yahoo_symbol(ticker)).info
    except Exception as e:
        print(f"[market_data] fundamentals fetch failed for {ticker}: {e}")
        return None

    def num(v, mult=1.0):
        return round(v * mult, 4) if isinstance(v, (int, float)) else None

    ev = info.get("enterpriseValue")
    ev_rev = info.get("enterpriseToRevenue")
    mcap = info.get("marketCap")
    px = info.get("currentPrice") or info.get("regularMarketPrice")

    # ── SHARES: two different numbers, and using the wrong one halves a peer ──
    # Yahoo's sharesOutstanding is the REPORTED count, which for a dual-class or up-C
    # company is CLASS A ONLY. Its marketCap covers every class. So for those names
    # `sharesOutstanding` and `marketCap / price` disagree — measured 2026-07-16:
    #
    #     PAY   mcap/price 125,789,331  vs sharesOutstanding 62,936,502  -> 2.00x
    #     MQ    mcap/price 105,202,041  vs sharesOutstanding 97,000,000  -> 1.08x
    #     RPAY  mcap/price  88,086,833  vs sharesOutstanding 82,800,952  -> 1.06x
    #     USIO / PMTS / PRTH / PAYS — identical (single class)
    #
    # Rebuilding market cap from sharesOutstanding therefore HALVED PAY, dropping its
    # EV/Gross Profit from 11.19x to 5.17x, pulling the peer median down and inflating
    # USIO's apparent discount. Use the mcap-consistent count for any market-cap maths;
    # keep the reported count for per-share statements about the client itself.
    shares_reported = info.get("sharesOutstanding") or info.get("impliedSharesOutstanding")
    shares_for_mcap = (mcap / px) if (mcap and px) else shares_reported
    multi_class = bool(
        shares_reported and shares_for_mcap
        and abs(shares_for_mcap / shares_reported - 1) > 0.02)

    # NET DEBT is the slow-moving half of EV and the only part worth caching.
    # EV = market cap + net debt. Shares and net debt move when a company FILES;
    # market cap moves every tick. Storing net debt lets live_ev() rebuild EV from
    # the current price instead of serving one computed at a stale price.
    net_debt = (ev - mcap) if (isinstance(ev, (int, float)) and isinstance(mcap, (int, float))) else None
    return {
        "ticker": ticker.upper(),
        "gross_margin": num(info.get("grossMargins"), 100),
        "ev_rev": num(ev_rev),
        "ev_ebitda": num(info.get("enterpriseToEbitda")),
        "rev_growth": num(info.get("revenueGrowth"), 100),
        "market_cap": mcap,
        "enterprise_value": ev,
        "shares_for_mcap": shares_for_mcap,
        "shares_outstanding": shares_reported,
        "multi_class": multi_class,
        "net_debt": net_debt,
        "price_at_fetch": px,
        "ev_positive": bool(ev and ev > 0 and ev_rev and ev_rev > 0),
        "as_of": datetime.now().isoformat(),
    }


def get_fundamentals(ticker, client_id=None, max_age_hours=24, force=False):
    """Cached fundamentals for one ticker (gross margin, EV/Revenue, growth).
    Returns the cached dict when fresh, refetches when stale, and falls back to
    any stale cache on a failed fetch. None only if never fetched and the fetch
    fails."""
    key = f"market_fundamentals_{ticker.upper()}.json"
    if not force:
        cached = db.load_json(key, None, client_id=client_id)
        if cached and cached.get("as_of"):
            try:
                age = (datetime.now() - datetime.fromisoformat(cached["as_of"])).total_seconds() / 3600
                if age < max_age_hours:
                    return cached
            except (ValueError, TypeError):
                pass
    fresh = _fetch_fundamentals(ticker)
    if fresh:
        db.save_json(key, fresh, client_id=client_id)
        return fresh
    return db.load_json(key, None, client_id=client_id)


# ─────────────────────────────────────────────────────────────────────────
# Street estimates — the real analyst consensus, from the market data feed.
#
# WHY THIS EXISTS: the platform's period_estimates were never entered. They fall
# back to data/seed/consensus_estimates.py — DEMO figures — and the whole
# beat/miss read was being computed off them. Verified 2026-07-16:
#
#     seed (demo)  H.C. Wainwright $25.50M · Ladenburg $24.80M -> "street" $25.15M
#     Yahoo (real) 4 analysts, Q2 2026 range $23.03-24.45M     -> street $23.67M
#
# BOTH seeded numbers sit ABOVE the entire real range. The demo data inverted the
# most important fact going into the call: on seed, USIO's $24.5M guide looked
# BELOW the street; on real estimates it is ABOVE every published analyst.
#
# Period mapping is confirmed against known actuals rather than assumed: Yahoo's
# "0q" year-ago revenue reconciles to USIO's Q2 2025 actual, and "0y" year-ago to
# USIO's FY2025 revenue per XBRL ($85,393,630 vs $85.4M). If that check fails the
# mapping has drifted and we return nothing rather than guess.
# ─────────────────────────────────────────────────────────────────────────

def _fetch_estimates(ticker):
    """Street revenue/EPS estimates + price targets for one ticker. None on failure."""
    if (ticker or "").upper() in _YF_SKIP:
        return None
    try:
        import yfinance as yf
        tk = yf.Ticker(ticker)
        out = {"ticker": ticker.upper(), "as_of": datetime.now().isoformat(),
               "revenue": {}, "eps": {}, "price_target": None, "coverage": []}

        rev = tk.revenue_estimate
        if rev is not None and not rev.empty:
            for period in rev.index:
                r = rev.loc[period]
                out["revenue"][str(period)] = {
                    "avg": _num(r.get("avg")), "low": _num(r.get("low")),
                    "high": _num(r.get("high")),
                    "n": _num(r.get("numberOfAnalysts")),
                    "year_ago": _num(r.get("yearAgoRevenue")),
                    "growth": _num(r.get("growth")),
                }
        eps = tk.earnings_estimate
        if eps is not None and not eps.empty:
            for period in eps.index:
                e = eps.loc[period]
                out["eps"][str(period)] = {
                    "avg": _num(e.get("avg")), "low": _num(e.get("low")),
                    "high": _num(e.get("high")), "n": _num(e.get("numberOfAnalysts")),
                    "year_ago": _num(e.get("yearAgoEps")),
                }
        try:
            pt = tk.analyst_price_targets
            if pt:
                out["price_target"] = {k: _num(v) for k, v in pt.items()}
        except Exception:
            pass
        try:
            ud = tk.upgrades_downgrades
            if ud is not None and not ud.empty:
                seen = {}
                for ts, row in ud.iterrows():
                    firm = str(row.get("Firm") or "").strip()
                    if firm and firm not in seen:
                        seen[firm] = {"firm": firm, "grade": str(row.get("ToGrade") or ""),
                                      "price_target": _num(row.get("currentPriceTarget")),
                                      "date": str(ts)[:10]}
                out["coverage"] = sorted(seen.values(), key=lambda x: x["date"], reverse=True)
        except Exception:
            pass
        return out if (out["revenue"] or out["eps"]) else None
    except Exception as exc:
        print(f"[market] estimates fetch failed for {ticker}: {exc}")
        return None


def _num(v):
    try:
        if v is None:
            return None
        f = float(v)
        return None if f != f else f  # NaN check
    except (TypeError, ValueError):
        return None


def get_estimates(ticker, client_id=None, max_age_hours=12, force=False):
    """Cached street estimates. Same fetch/fallback contract as get_fundamentals()."""
    key = f"market_estimates_{ticker.upper()}.json"
    if not force:
        cached = db.load_json(key, None, client_id=client_id)
        if cached and cached.get("as_of"):
            try:
                age = (datetime.now() - datetime.fromisoformat(cached["as_of"])).total_seconds() / 3600
                if age < max_age_hours:
                    return cached
            except (ValueError, TypeError):
                pass
    fresh = _fetch_estimates(ticker)
    if fresh:
        db.save_json(key, fresh, client_id=client_id)
        return fresh
    return db.load_json(key, None, client_id=client_id)


def street_for_quarter(ticker, fy_revenue_actual=None, q_year_ago_actual=None, client_id=None):
    """The current quarter's street revenue, with its period mapping VERIFIED.

    Yahoo labels periods relatively ("0q" = current quarter, "0y" = current FY), which
    is only useful if you know which quarter it thinks is current. Rather than assume,
    this reconciles Yahoo's reported year-ago figures against actuals the caller passes
    in from the filings. A mismatch returns `verified: False` and the caller must not
    treat the number as the street.
    """
    est = get_estimates(ticker, client_id=client_id)
    if not est or not est.get("revenue"):
        return None
    q, y = est["revenue"].get("0q"), est["revenue"].get("0y")
    if not q:
        return None
    checks = {}
    if q_year_ago_actual and q.get("year_ago"):
        checks["quarter"] = abs(q["year_ago"] / 1e6 - q_year_ago_actual) / q_year_ago_actual < 0.02
    if fy_revenue_actual and y and y.get("year_ago"):
        checks["fy"] = abs(y["year_ago"] / 1e6 - fy_revenue_actual) / fy_revenue_actual < 0.02
    verified = bool(checks) and all(checks.values())
    return {
        "avg_m": q["avg"] / 1e6 if q.get("avg") else None,
        "low_m": q["low"] / 1e6 if q.get("low") else None,
        "high_m": q["high"] / 1e6 if q.get("high") else None,
        "n": int(q["n"]) if q.get("n") else None,
        "year_ago_m": q["year_ago"] / 1e6 if q.get("year_ago") else None,
        "fy_avg_m": y["avg"] / 1e6 if (y and y.get("avg")) else None,
        "fy_low_m": y["low"] / 1e6 if (y and y.get("low")) else None,
        "fy_high_m": y["high"] / 1e6 if (y and y.get("high")) else None,
        "fy_n": int(y["n"]) if (y and y.get("n")) else None,
        "verified": verified, "checks": checks,
        "as_of": est.get("as_of"), "price_target": est.get("price_target"),
        "coverage": est.get("coverage") or [],
    }


def consensus_rev(client_id=None):
    """Live street revenue consensus ($M) for the quarter about to report — a drop-in for
    the registry's static CT('q2_consensus_rev').

    Prefers Yahoo's live estimate (yfinance revenue_estimate '0q', the current reporting
    quarter) for any client with analyst coverage; falls back to the static registry value
    when there is no coverage (a micro-cap like WRAP), and to None when neither exists. This
    is what turns a hand-maintained per-client field into a live per-tenant feed: SARO's 12
    analysts populate automatically, USIO's 4 do too, and an uncovered name honestly reads as
    'no consensus' rather than a stale hardcode.

    Returns (value_m, source) where source is 'live' | 'registry' | None so callers can label
    the number; consensus_rev_value() is the bare-value convenience wrapper.
    """
    from config.client_config import CT
    try:
        est = get_estimates(CT("ticker"), client_id=client_id)
        q = (est or {}).get("revenue", {}).get("0q") or {}
        if q.get("avg") and q.get("n"):
            return round(q["avg"] / 1e6, 2), "live"
    except Exception as exc:
        print(f"[market_data] live consensus unavailable: {exc}")
    static = CT("q2_consensus_rev", None)
    if isinstance(static, (int, float)) and static:
        return float(static), "registry"
    return None, None


def consensus_rev_value(client_id=None):
    """The upcoming-quarter street revenue consensus ($M), live-preferring, or None."""
    return consensus_rev(client_id)[0]


def live_ev(ticker, client_id=None):
    """Market cap and enterprise value rebuilt at the LIVE price.

    THE BUG THIS FIXES. get_fundamentals() caches for 24h; get_snapshot() caches for 60
    minutes. So the price on screen refreshed hourly while the market cap and EV behind
    every multiple refreshed daily — and EV is the numerator of EV/Gross Profit, EV/Revenue
    and EV/EBITDA. Measured 2026-07-16 with the cache 11.7h old and USIO down 7.5% on the
    day: cached EV $63.65M vs live $58.68M. The EV driving every multiple was 7.8% stale,
    computed at a $2.33 share price while the page displayed $2.23.

    It is not a cache-tuning problem. EV has two halves that move on different clocks:

        market cap  -> every tick
        net debt    -> when the company FILES

    Caching them together at the slower one's cadence is the mistake. This recomputes the
    fast half from the live snapshot and keeps the slow half cached, so the answer is exact
    at any cache age.

    Returns None rather than a stale guess if either half is missing: a silently stale EV
    is precisely what this exists to prevent.
    """
    f = get_fundamentals(ticker, client_id=client_id)
    if not f:
        return None
    # shares_for_mcap, NOT shares_outstanding — see _fetch_fundamentals. For a dual-class
    # name the reported count is Class A only and market cap covers every class.
    shares = f.get("shares_for_mcap") or f.get("shares_outstanding")
    net_debt = f.get("net_debt")
    snap = get_snapshot(ticker, client_id=client_id)
    price = snap.get("last_price") if snap else None
    if not (shares and price is not None and net_debt is not None):
        return None
    mcap = price * shares
    ev = mcap + net_debt
    stale_mcap = f.get("market_cap")
    drift = ((mcap / stale_mcap - 1) * 100) if stale_mcap else None
    # A drift this large is not a price move, it is a broken share count. Say so rather
    # than quietly publishing it — this is how the PAY dual-class error surfaced.
    if drift is not None and abs(drift) > 25:
        print(f"[market] {ticker}: live market cap differs {drift:+.0f}% from the cached one. "
              f"That is too large to be a price move — check the share count "
              f"(shares_for_mcap={shares:,.0f}, multi_class={f.get('multi_class')}).")
    return {
        "ticker": ticker.upper(), "price": price,
        "shares_for_mcap": shares, "shares_outstanding": f.get("shares_outstanding"),
        "multi_class": f.get("multi_class"),
        "market_cap": mcap, "net_debt": net_debt, "enterprise_value": ev,
        "ev_positive": ev > 0,
        "price_at_fetch": f.get("price_at_fetch"),
        "drift_pct": drift,
        "fundamentals_as_of": f.get("as_of"), "price_as_of": snap.get("as_of"),
    }
