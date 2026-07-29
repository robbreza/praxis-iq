"""Lighthouse — multi-factor attribution model (Spec 13.1, with 13.2/13.3 folded in).

Generalizes the 2-factor champion (attribution.market_peer_model) to a proper multi-factor risk
decomposition, so the residual it leaves behind is defensibly STOCK-SPECIFIC — not just whatever the
small-cap + peer basket failed to explain. Same discipline: coefficients for day t are fit ONLY on the
trailing `window` days ending t-1 (point-in-time).

    expected_t = α + Σ βᵢ·factorᵢ,t        residual_t = actual_t − expected_t

On top of the fit it reports what a desk actually needs to trust the number:
  * R² — how much of the issuer's variance the factor model explains in-window (model quality);
  * a prediction-interval t-stat — the residual's significance GIVEN estimation error in the betas
    (Spec 13.3): resid / se_pred, se_pred² = s²·(1 + x₀ᵀ(XᵀX)⁻¹x₀);
  * a regime-aware z-score — residual standardized by its EWMA conditional vol (Spec 13.2), so a −3%
    residual reads as a 3σ event in a calm tape and as noise in a high-vol tape.

`residual_pctile` is the normal-tail mass within ±|z| (0–1, higher = rarer), keeping it drop-in
compatible with the abnormality thresholds ceo.build_verdict already uses.
"""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

from lighthouse.factors import build_factors


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def attribution(rets: pd.DataFrame, issuer: str = "USIO", window: int = 126,
                fdr_q: float = 0.10, fdr_window: int = 252) -> pd.DataFrame:
    """The live attribution entry point: build the default factor set from `rets`, run the rolling
    multi-factor model, then apply the multiple-testing (FDR) gate (Spec 13.3) so downstream callers
    get `p_value` / `fdr_significant` for free. Single call site for shadow, the page, and the digest."""
    m = factor_model(rets, issuer, build_factors(rets), window=window)
    if m.empty:
        return m
    from lighthouse.fdr import apply_gate
    return apply_gate(m, q=fdr_q, window=fdr_window)


def factor_model(rets: pd.DataFrame, issuer: str, factor_frame: pd.DataFrame | None = None,
                 window: int = 126, ewma_lambda: float = 0.94) -> pd.DataFrame:
    """rets: date x ticker daily-return frame. `factor_frame` (date x factor) is built from `rets` if
    not supplied. Returns per-day attribution with multi-factor stats, each day fit on the trailing
    `window` days ending the PRIOR day."""
    if factor_frame is None:
        factor_frame = build_factors(rets)
    if issuer not in rets.columns or factor_frame is None or factor_frame.empty:
        return pd.DataFrame()

    df = pd.concat([rets[issuer].rename("y"), factor_frame], axis=1).dropna()
    fac_names = list(factor_frame.columns)
    if len(df) <= window + 5:
        return pd.DataFrame()

    y = df["y"].values
    X = df[fac_names].values
    idx = df.index
    out = []
    ewma_var = None                                   # EWMA conditional residual variance (regime vol)

    for t in range(window, len(df)):
        Xtr, ytr = X[t-window:t], y[t-window:t]       # trailing window ENDING at t-1 (no look-ahead)
        A = np.column_stack([np.ones(window), Xtr])
        beta, *_ = np.linalg.lstsq(A, ytr, rcond=None)
        resid_in = ytr - A @ beta
        k = A.shape[1]
        dof = max(window - k, 1)
        ssr = float(resid_in @ resid_in)
        s2 = ssr / dof                                # in-window residual variance
        sst = float(((ytr - ytr.mean()) ** 2).sum()) + 1e-12
        r2 = 1.0 - ssr / sst

        x0 = np.concatenate([[1.0], X[t]])
        lev = float(x0 @ np.linalg.pinv(A.T @ A) @ x0)   # leverage of the out-of-sample point
        se_pred = math.sqrt(max(s2 * (1.0 + lev), 1e-18))

        exp = float(x0 @ beta)
        act = float(y[t])
        res = act - exp
        t_stat = res / se_pred if se_pred > 0 else 0.0

        if ewma_var is None:
            ewma_var = s2                             # seed regime vol with the in-window residual var
        cond_sd = math.sqrt(max(ewma_var, 1e-18))
        z = res / cond_sd if cond_sd > 0 else 0.0
        rarity = 2.0 * _phi(abs(z)) - 1.0             # normal-tail mass within ±|z|

        out.append(dict(
            d=idx[t].date() if hasattr(idx[t], "date") else idx[t],
            actual_ret=act, expected_ret=exp, residual=res,
            expected_lo=exp - 2 * se_pred, expected_hi=exp + 2 * se_pred,
            residual_pctile=float(max(0.0, min(1.0, rarity))),
            z=float(z), t_stat=float(t_stat), resid_se=float(se_pred),
            r2=float(r2), n_factors=len(fac_names),
            loadings={fac_names[i]: float(beta[i + 1]) for i in range(len(fac_names))},
            pct_explained=float(max(0.0, min(1.0, r2))),
            cond_vol_model="ewma", garch_persistence=None,
        ))
        ewma_var = ewma_lambda * ewma_var + (1.0 - ewma_lambda) * res * res   # update for next day

    # Formal GARCH(1,1) (Spec 13.2): replace the EWMA z with a maximum-likelihood conditional vol when
    # it converges and beats the fixed-λ EWMA on log-likelihood. Point-in-time (σ²_t uses ε_{t-1}); the
    # params are a structural estimate on the residual history, as the EWMA λ was a structural constant.
    try:
        from lighthouse import garch
        res_arr = np.array([o["residual"] for o in out], float)
        g = garch.fit_garch11(res_arr)
        if g.get("converged") and g.get("beats_ewma"):
            sig = garch.cond_vol(res_arr, g)
            for i, o in enumerate(out):
                zz = float(res_arr[i] / sig[i]) if sig[i] > 0 else 0.0
                o["z"] = zz
                o["residual_pctile"] = float(max(0.0, min(1.0, 2.0 * _phi(abs(zz)) - 1.0)))
                o["cond_vol_model"] = "garch"
                o["garch_persistence"] = g["persistence"]
    except Exception:
        pass
    return pd.DataFrame(out).set_index("d")
