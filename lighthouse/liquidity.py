"""Lighthouse — liquidity / microstructure normalization (Spec 13.5).

A large residual is only information if the tape can carry it. A −6% move on 0.3× average volume is more
likely a thin print / stale quote than genuine selling; the same move on 5× volume is information. So
this adds a MICROSTRUCTURE CONVICTION layer on top of the statistical abnormality — a third, independent
gate for the loud channels: a phone alert now requires the move to be (1) statistically abnormal
(GARCH-standardized z), (2) a genuine discovery (FDR), AND (3) on real volume.

Per day, from lh_ohlcv (daily bars — no intraday, so VWAP-deviation is out of scope):
  * RVOL      — today's $-volume vs the trailing-20d average $-volume (point-in-time: baseline excludes
                today), the primary thin-tape signal;
  * $-ADV     — dollar liquidity level;
  * Amihud    — |return| / $-volume, the classic illiquidity (price impact per dollar traded).

`conviction(rvol)` maps volume to a weight in [0.35, 1]; `thin_tape` flags a notably light day. The raw
statistical abnormality (z, FDR p) is left UNTOUCHED — liquidity is a separate conviction, so each gate
stays interpretable, not a single muddied score.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

THIN_RVOL = 0.5             # below half the trailing-avg $-volume = notably thin
_FLOOR = 0.35              # never fully zero a move's conviction on volume alone


def conviction(rvol) -> float:
    """Volume → conviction weight in [_FLOOR, 1]. sqrt softens it; unknown/zero → 1 (don't penalize)."""
    if rvol is None or not np.isfinite(rvol) or rvol <= 0:
        return 1.0
    return float(min(1.0, max(_FLOOR, math.sqrt(rvol))))


def compute_metrics(prices, volumes, lookback: int = 20) -> pd.DataFrame:
    """Pure core: per-bar rvol / $-adv / amihud / conviction / thin_tape from price & volume arrays."""
    px = pd.Series(np.asarray(prices, float))
    vol = pd.Series(np.asarray(volumes, float))
    dvol = px * vol
    ret = px.pct_change()
    avg_dvol = dvol.shift(1).rolling(lookback).mean()          # trailing baseline EXCLUDING today (PIT)
    rvol = dvol / avg_dvol
    amihud = ret.abs() / (dvol + 1.0)
    out = pd.DataFrame({"dollar_adv": avg_dvol, "rvol": rvol, "amihud": amihud})
    out["conviction"] = out["rvol"].apply(conviction)
    out["thin_tape"] = out["rvol"] < THIN_RVOL
    return out


def liquidity_frame(ticker, conn=None, lookback: int = 20) -> pd.DataFrame:
    """Per-date liquidity metrics for `ticker` from lh_ohlcv (date-indexed)."""
    own = conn is None
    try:
        import psycopg2
        from core.security import get_database_url
        conn = conn or psycopg2.connect(get_database_url())
        cur = conn.cursor()
        cur.execute("SELECT d, adj_close, volume FROM lh_ohlcv WHERE ticker=%s ORDER BY d", (ticker,))
        rows = cur.fetchall()
    finally:
        if own and conn:
            conn.close()
    if len(rows) < lookback + 5:
        return pd.DataFrame()
    idx = [r[0] for r in rows]
    m = compute_metrics([float(r[1]) for r in rows], [float(r[2] or 0) for r in rows], lookback=lookback)
    m.index = idx
    return m[["dollar_adv", "rvol", "amihud", "conviction", "thin_tape"]].dropna(subset=["rvol"])
