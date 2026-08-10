"""Lighthouse Phase 1 — market data wiring. Fetches historical adjusted OHLCV (yfinance) for the
issuer, benchmarks and peers into lh_ohlcv, builds the peer set, and produces a point-in-time daily
returns frame. Every bar is stamped with a knowledge_ts of the session-close evening (a daily bar is
knowable after the close, never intraday), so downstream models cannot leak the future.
"""
from __future__ import annotations
from datetime import datetime, timezone, time

import psycopg2
import pandas as pd

from core.security import get_database_url
from core import db as _db

KNOWLEDGE_HOUR_UTC = 21   # ~1h after the 4pm ET close; the daily bar is knowable this evening


def _conn():
    return _db.get_connection()


def fetch_ohlcv(ticker: str, period="3y") -> list[dict]:
    import yfinance as yf
    df = yf.Ticker(ticker).history(period=period, auto_adjust=False)
    rows = []
    for idx, r in df.iterrows():
        d = idx.date()
        kts = datetime.combine(d, time(KNOWLEDGE_HOUR_UTC, 0), tzinfo=timezone.utc)
        rows.append(dict(ticker=ticker, d=d, open=float(r["Open"]), high=float(r["High"]),
                         low=float(r["Low"]), close=float(r["Close"]),
                         adj_close=float(r["Adj Close"]), volume=int(r["Volume"] or 0),
                         knowledge_ts=kts, source="yfinance"))
    return rows


def load_ohlcv(tickers, period="3y", conn=None) -> dict:
    from psycopg2.extras import execute_values
    own = conn is None
    conn = conn or _conn()
    cur = conn.cursor()
    got = {}
    for t in tickers:
        try:
            rows = fetch_ohlcv(t, period)
        except Exception as e:
            got[t] = f"ERR {e!r}"; continue
        vals = [(r["ticker"], r["d"], r["open"], r["high"], r["low"], r["close"],
                 r["adj_close"], r["volume"], r["knowledge_ts"], r["source"]) for r in rows]
        execute_values(cur,
            """INSERT INTO lh_ohlcv (ticker,d,open,high,low,close,adj_close,volume,knowledge_ts,source)
               VALUES %s ON CONFLICT (ticker,d) DO UPDATE SET adj_close=EXCLUDED.adj_close,
                 close=EXCLUDED.close, volume=EXCLUDED.volume, knowledge_ts=EXCLUDED.knowledge_ts""",
            vals, page_size=500)
        conn.commit()
        got[t] = len(rows)
    if own: conn.close()
    return got


def build_peers(cfg, conn=None):
    own = conn is None
    conn = conn or _conn()
    cur = conn.cursor()
    first = min((r["d"] for r in fetch_ohlcv(cfg["ticker"], "5d")), default=None)
    kts = datetime.now(timezone.utc)
    for pk, tk in (("sector", cfg["benchmarks"].get("sector")),):
        pass
    n = 0
    for pt in cfg["business_peers"]:
        cur.execute("""INSERT INTO lh_peer (client_id,ticker,peer_ticker,peer_kind,weight,effective_from,knowledge_ts)
                       VALUES (%s,%s,%s,'business',%s,%s,%s)
                       ON CONFLICT (client_id,ticker,peer_ticker,peer_kind,effective_from) DO NOTHING""",
                    (cfg["client_id"], cfg["ticker"], pt, 1.0/len(cfg["business_peers"]),
                     "2000-01-01", kts))
        n += 1
    conn.commit()
    if own: conn.close()
    return n


_RF_CACHE = {}                          # (tickers, as_of) -> (built_at, DataFrame)
_RF_TTL_SECONDS = 120                   # short: the Lighthouse page calls this several times per
                                        # render and revisits recompute it — cache within the visit
                                        # window while staying fresh enough for a daily model.


def returns_frame(tickers, as_of=None, conn=None) -> pd.DataFrame:
    """Daily simple returns (date x ticker) from lh_ohlcv, adjusted-close based. If `as_of` (an
    AsOf) is given, only bars knowable at that horizon are used — the point-in-time guard.

    Memoized for a short TTL: lh_ohlcv is a daily series, but this is called several times per page
    render (and on every revisit) with identical args — recomputing N per-ticker queries + the pandas
    build each time was a top contributor to the Lighthouse page's render time."""
    _ck = (tuple(sorted(tickers)), str(as_of))
    _hit = _RF_CACHE.get(_ck)
    if _hit and (datetime.now(timezone.utc) - _hit[0]).total_seconds() < _RF_TTL_SECONDS:
        return _hit[1].copy()
    own = conn is None
    conn = conn or _conn()
    cur = conn.cursor()
    gate, params = ("", [])
    if as_of is not None:
        gate, val = as_of.where_sql("knowledge_ts"); gate = " AND " + gate; params = [val]
    frames = {}
    for t in tickers:
        cur.execute(f"SELECT d, adj_close FROM lh_ohlcv WHERE ticker=%s{gate} ORDER BY d", [t]+params)
        rows = cur.fetchall()
        if len(rows) > 2:
            s = pd.Series({d: ac for d, ac in rows}).sort_index()
            frames[t] = s.pct_change()
    if own: conn.close()
    _df = pd.DataFrame(frames).dropna(how="all")
    _RF_CACHE[_ck] = (datetime.now(timezone.utc), _df)
    return _df.copy()
