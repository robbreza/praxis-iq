"""Lighthouse — GARCH(1,1) conditional volatility (Spec 13.2, formal).

The factor model standardizes each residual by its conditional volatility so abnormality is regime-aware
(a −3% residual is a 3σ event in a calm tape, noise in a high-vol tape). The first cut used an EWMA with
λ fixed at 0.94 — which is exactly IGARCH(1,1) with ω=0, α=1−λ, β=λ and persistence pinned to 1. This
replaces it with a proper GARCH(1,1):

    σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

whose parameters are ESTIMATED by maximum likelihood, so the persistence (α+β) and the mean-reversion
of volatility come from the data instead of an assumption. No scipy, so we fit with variance targeting
(ω = v̄·(1−α−β), pinning the unconditional variance to the sample) + a coarse-to-fine grid search over
(α, β) maximizing the Gaussian log-likelihood — dependency-free and stable.

Point-in-time: σ²_t depends only on ε_{t-1} and σ²_{t-1}, so the one-step-ahead vol used to standardize
day t is knowable before ε_t. The parameters are a structural, slow-moving estimate on the residual
history (the EWMA λ it replaces was likewise a fixed structural constant). Falls back to EWMA when the
series is too short or the fit doesn't converge.
"""
from __future__ import annotations
import math
import numpy as np

_LOG2PI = math.log(2.0 * math.pi)


def _cond_var_path(eps: np.ndarray, omega: float, alpha: float, beta: float, seed: float) -> np.ndarray:
    n = len(eps)
    v = np.empty(n)
    v[0] = seed                                          # σ²_1 seed (sample var); mild, first obs only
    for t in range(1, n):
        vt = omega + alpha * eps[t - 1] * eps[t - 1] + beta * v[t - 1]   # uses ε_{t-1}, σ²_{t-1} — PIT
        v[t] = vt if vt > 1e-18 else 1e-18
    return v


def _loglik(eps: np.ndarray, v: np.ndarray) -> float:
    return float(-0.5 * np.sum(_LOG2PI + np.log(v) + (eps * eps) / v))


def fit_garch11(eps, min_obs: int = 100) -> dict:
    """MLE fit via variance targeting + coarse-to-fine grid. Returns params + loglik, or converged=False."""
    eps = np.asarray(eps, float)
    eps = eps[np.isfinite(eps)]
    n = len(eps)
    if n < min_obs:
        return {"converged": False, "reason": "too_short", "n": n}
    vbar = float(eps.var())
    if vbar <= 0:
        return {"converged": False, "reason": "degenerate", "n": n}

    def _eval(a, b):
        if a < 0 or b < 0 or (a + b) >= 0.999:
            return None
        omega = vbar * (1.0 - a - b)
        if omega <= 0:
            return None
        return _loglik(eps, _cond_var_path(eps, omega, a, b, vbar)), omega

    best = None                                          # (loglik, alpha, beta, omega)
    for a in np.linspace(0.01, 0.30, 15):
        for b in np.linspace(0.50, 0.98, 25):
            r = _eval(a, b)
            if r and (best is None or r[0] > best[0]):
                best = (r[0], a, b, r[1])
    if best is None:
        return {"converged": False, "reason": "no_valid_region", "n": n}
    _, a0, b0, _ = best
    for a in np.linspace(max(0.001, a0 - 0.03), a0 + 0.03, 7):          # local refine
        for b in np.linspace(max(0.30, b0 - 0.03), min(0.985, b0 + 0.03), 7):
            r = _eval(a, b)
            if r and r[0] > best[0]:
                best = (r[0], a, b, r[1])
    ll, a, b, omega = best
    # EWMA (IGARCH λ=0.94) loglik for an honest "did the fit actually beat the assumption" comparison
    ewma_ll = _loglik(eps, _cond_var_path(eps, 0.0, 0.06, 0.94, vbar))
    return {"converged": True, "omega": float(omega), "alpha": float(a), "beta": float(b),
            "persistence": float(a + b), "uncond_var": vbar, "loglik": ll, "ewma_loglik": ewma_ll,
            "beats_ewma": ll >= ewma_ll, "n": n}


def cond_vol(eps, params: dict, seed: float | None = None) -> np.ndarray:
    """Point-in-time conditional stdev path for `eps` under `params`."""
    eps = np.asarray(eps, float)
    seed = seed if seed is not None else float(np.nanvar(eps)) or 1e-12
    return np.sqrt(_cond_var_path(eps, params["omega"], params["alpha"], params["beta"], seed))


def standardize(eps, params: dict) -> np.ndarray:
    """Standardized residuals ε_t / σ_t (regime-aware z)."""
    eps = np.asarray(eps, float)
    sig = cond_vol(eps, params)
    return np.divide(eps, sig, out=np.zeros_like(eps), where=sig > 0)
