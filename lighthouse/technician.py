"""Lighthouse Phase 1 — Technician's Model (Spec 3).

A separate technical/trading-structure lens computed from daily OHLCV: trend structure (21/63/126/
252d), support/resistance breaks, relative volume, ATR / realized-vol expansion, relative strength,
gaps, and price-volume confirmation. Per the spec, technicals explain HOW a move was confirmed or
amplified — never proof of the original CAUSE — so every signal is tagged role = amplifier /
contributor (never `trigger`). Point-in-time via the AsOf knowledge_ts gate.

Daily-bar limitation (stated, not hidden): VWAP, intraday acceleration and true intraday structure
need intraday data and are out of scope for the daily engine.
"""
from __future__ import annotations
from datetime import datetime, timezone, time

import numpy as np
import pandas as pd
import psycopg2
from core.security import get_database_url
from core import db as _db


def _conn(): return _db.get_connection()


def _ohlcv(ticker, day, as_of, cur) -> pd.DataFrame:
    gate, params = "", [ticker, day]
    if as_of is not None:
        frag, val = as_of.where_sql("knowledge_ts"); gate = " AND " + frag; params.append(val)
    cur.execute(f"""SELECT d, open, high, low, close, adj_close, volume FROM lh_ohlcv
                    WHERE ticker=%s AND d<=%s{gate} ORDER BY d""", params)
    rows = cur.fetchall()
    df = pd.DataFrame(rows, columns=["d", "open", "high", "low", "close", "adj_close", "volume"])
    return df.astype({c: float for c in ["open", "high", "low", "close", "adj_close", "volume"]})


def compute_technicals(ticker, day, benchmark="IWM", as_of=None, conn=None) -> dict:
    own = conn is None; conn = conn or _conn(); cur = conn.cursor()
    df = _ohlcv(ticker, day, as_of, cur)
    if len(df) < 60:
        if own: conn.close()
        return {"signals": [], "summary": "insufficient history"}
    c = df["adj_close"]; hi = df["high"]; lo = df["low"]; vol = df["volume"]
    prev_close = c.iloc[-2]; today = c.iloc[-1]
    ret = today / prev_close - 1
    gap = df["open"].iloc[-1] / prev_close - 1

    # trend structure across horizons
    trend = {}
    for w in (21, 63, 126, 252):
        if len(c) > w:
            sma = c.iloc[-w:].mean()
            trend[w] = "above" if today > sma else "below"

    # relative volume, ATR, vol expansion
    rvol = float(vol.iloc[-1] / (vol.iloc[-22:-1].mean() + 1e-9))
    tr = np.maximum(hi - lo, np.maximum((hi - c.shift()).abs(), (lo - c.shift()).abs()))
    atr14 = float(tr.iloc[-15:-1].mean())
    move_atr = abs(today - prev_close) / (atr14 + 1e-9)
    rvol21 = float(np.std(c.pct_change().iloc[-21:]) * np.sqrt(252))

    # support/resistance (prior 20d, excluding today) and 52w breakout
    sup20 = float(lo.iloc[-21:-1].min()); res20 = float(hi.iloc[-21:-1].max())
    break_down = today < sup20; break_up = today > res20
    lo252 = float(lo.iloc[-253:-1].min()) if len(lo) > 60 else None
    hi252 = float(hi.iloc[-253:-1].max()) if len(hi) > 60 else None
    new_low = lo252 is not None and today <= lo252
    new_high = hi252 is not None and today >= hi252

    # relative strength vs benchmark (21d)
    bdf = _ohlcv(benchmark, day, as_of, cur)
    rs21 = None
    if len(bdf) > 22:
        bret = bdf["adj_close"].iloc[-1] / bdf["adj_close"].iloc[-22] - 1
        iret = c.iloc[-1] / c.iloc[-22] - 1
        rs21 = float(iret - bret)
    if own: conn.close()

    up = ret >= 0
    signals = []
    if break_down and rvol > 1.5:
        signals.append(dict(label=f"broke 20-day support (${sup20:.2f}) on {rvol:.1f}x volume", role="amplifier"))
    if break_up and rvol > 1.5:
        signals.append(dict(label=f"broke 20-day resistance (${res20:.2f}) on {rvol:.1f}x volume", role="amplifier"))
    if new_low:
        signals.append(dict(label="new 52-week low", role="amplifier"))
    if new_high:
        signals.append(dict(label="new 52-week high", role="amplifier"))
    if move_atr >= 2:
        signals.append(dict(label=f"range {move_atr:.1f}x ATR — volatility expansion", role="amplifier"))
    if abs(gap) >= 0.03:
        signals.append(dict(label=f"gapped {gap*100:+.1f}% at the open", role="contributor"))
    if rvol >= 2 and not (break_down or break_up):
        signals.append(dict(label=f"{rvol:.1f}x volume {'accumulation' if up else 'distribution'}", role="contributor"))
    if rs21 is not None and abs(rs21) >= 0.05:
        signals.append(dict(label=f"{'out' if rs21>0 else 'under'}performing small-caps by {abs(rs21)*100:.0f}% (21d)", role="contributor"))

    below = sum(1 for v in trend.values() if v == "below")
    struct = ("below all major moving averages" if below == len(trend)
              else "above all major moving averages" if below == 0
              else "mixed trend structure")
    summary = (f"{struct}; " + ("; ".join(s["label"] for s in signals) if signals
               else "no notable technical break")) + ". (Technicals describe how the move was expressed, not its cause.)"
    return dict(ret=ret, gap=gap, rvol=rvol, atr14=atr14, move_atr=move_atr, realized_vol_21=rvol21,
                trend=trend, support20=sup20, resistance20=res20, break_down=break_down, break_up=break_up,
                new_52w_low=new_low, new_52w_high=new_high, rel_strength_21=rs21,
                signals=signals, summary=summary)
