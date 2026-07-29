"""Lighthouse — factor construction (Spec 13.1).

Builds a low-collinearity daily factor-return frame from liquid ETF proxies, expressed as SPREADS so
the style factors aren't swamped by the market factor (raw style ETFs are ~0.95 correlated with the
market; the spread isolates the tilt). Same data path as the rest of Lighthouse (lh_ohlcv via
data.returns_frame), point-in-time by construction (the returns frame is already knowledge_ts-gated
upstream when an AsOf is supplied).

Default set for a nano-cap payments name (parsimony matters on a 126-day window):
    MKT  = SPY                broad market beta
    SMB  = IWM - IWB          size (small minus large) — the core factor for this cap
    HML  = IWD - IWF          value minus growth
    MOM  = MTUM - SPY         momentum tilt
    SEC  = IPAY - SPY         payments/fintech sector factor (less noisy than 6 hand-picked peers)
    RATE = IEF                rate sensitivity (payments = consumer + rates)

A factor whose ETF is missing from the data frame is skipped (not faked), so the model degrades
gracefully to whatever coverage exists.
"""
from __future__ import annotations
import pandas as pd

# ETFs the factor set is built from — loaded alongside the issuer so the frame is always populated.
# IPAY (payments) + FINX/ARKF (fintech) are all kept fresh so the sector leg can be chosen empirically
# per issuer (Spec 14a found USIO co-moves with small-cap FINTECH, not the payments sector).
FACTOR_ETFS = ["SPY", "IWM", "IWB", "IWD", "IWF", "MTUM", "IPAY", "FINX", "ARKF", "IEF"]

# Default sector leg. USIO's is overridden to a fintech proxy (see config) on the co-movement evidence.
DEFAULT_SECTOR_ETF = "IPAY"


def _factor_defs(sector_etf: str):
    # (factor name, long leg, short leg or None). Spread = long - short; None short => the raw return.
    # FIN (fintech) is a SEPARATE leg from SEC (payments): Spec 14a showed USIO co-moves with small-cap
    # fintech distinctly from the payments sector, and the head-to-head confirmed adding FIN alongside
    # SEC raises R² (mean +0.5pt, latest +1.1pt) where swapping the sector leg was only a wash.
    return [
        ("MKT",  "SPY",       None),
        ("SMB",  "IWM",       "IWB"),
        ("HML",  "IWD",       "IWF"),
        ("MOM",  "MTUM",      "SPY"),
        ("SEC",  sector_etf,  "SPY"),
        ("FIN",  "FINX",      "SPY"),
        ("RATE", "IEF",       None),
    ]


def build_factors(rets: pd.DataFrame, sector_etf: str = DEFAULT_SECTOR_ETF, defs=None) -> pd.DataFrame:
    """rets: date x ticker daily-return frame (from data.returns_frame). Returns date x factor frame.
    `sector_etf` sets the SEC leg (SEC = sector_etf - SPY). Skips any factor whose leg(s) are absent so
    partial ETF coverage still yields a usable model."""
    defs = defs or _factor_defs(sector_etf)
    cols = {}
    for name, lo, sh in defs:
        if lo not in rets.columns:
            continue
        if sh is None:
            cols[name] = rets[lo]
        elif sh in rets.columns:
            cols[name] = rets[lo] - rets[sh]
        # else: short leg missing -> skip this factor rather than mislabel a raw leg as a spread
    if not cols:
        return pd.DataFrame()
    return pd.DataFrame(cols).dropna(how="all")
