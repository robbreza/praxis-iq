"""Lighthouse Phase 1 — Market/Peer Attribution (the first expected-return lens, Spec 1).

Champion model here is a rolling OLS of the issuer's daily return on two factors: a small-cap market
factor and an equal-weight business-peer basket. Coefficients for day t are fit ONLY on the trailing
`window` days ending at t-1 (strictly prior) — the point-in-time rule — so:

    expected_t = alpha + b_mkt * market_t + b_peer * peerbasket_t
    residual_t = actual_t - expected_t   (the unexplained move)

Residual rarity is the residual's percentile within the trailing-window residual distribution. This
is the champion; challengers (naive, static OLS, other windows, later Ridge/ElasticNet) plug in via
the same interface and are compared on the validation subset — never chosen by assumption.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def _ols(y: np.ndarray, X: np.ndarray):
    """Return coefficients for y ~ [1, X] via least squares."""
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    return beta  # [alpha, *factor_betas]


def market_peer_model(rets: pd.DataFrame, issuer: str, market: str, peers: list[str],
                      window: int = 126) -> pd.DataFrame:
    """rets: date x ticker daily-return frame. Returns per-day expected/actual/residual/rarity for
    the issuer, each day fit on the trailing `window` days ending the PRIOR day (no look-ahead)."""
    peers = [p for p in peers if p in rets.columns]
    cols = [issuer, market] + peers
    df = rets[cols].dropna()
    if len(df) <= window + 5:
        return pd.DataFrame()
    y = df[issuer].values
    mkt = df[market].values
    peer = df[peers].mean(axis=1).values          # equal-weight peer basket
    X = np.column_stack([mkt, peer])
    idx = df.index
    out = []
    resid_hist: list[float] = []
    for t in range(window, len(df)):
        Xtr, ytr = X[t-window:t], y[t-window:t]   # trailing window ENDING at t-1
        beta = _ols(ytr, Xtr)
        exp = beta[0] + beta[1]*X[t, 0] + beta[2]*X[t, 1]
        act = y[t]
        res = act - exp
        # rarity: percentile of |res| within trailing residual distribution
        if resid_hist:
            rar = float((np.abs(resid_hist) <= abs(res)).mean())
        else:
            rar = float("nan")
        # trailing-window sigma for an expected range
        sd = float(np.std(y[t-window:t]))
        out.append(dict(d=idx[t].date() if hasattr(idx[t], "date") else idx[t],
                        actual_ret=float(act), expected_ret=float(exp),
                        expected_lo=float(exp-2*sd), expected_hi=float(exp+2*sd),
                        residual=float(res), residual_pctile=rar,
                        beta_mkt=float(beta[1]), beta_peer=float(beta[2]),
                        pct_explained=float(1 - (res**2)/((act-np.mean(ytr))**2 + 1e-12))))
        resid_hist.append(res)
    return pd.DataFrame(out).set_index("d")
