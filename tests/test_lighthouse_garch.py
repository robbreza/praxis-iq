"""Pin GARCH(1,1) (Spec 13.2): the fit converges to a stationary model on clustered vol and beats a
constant-vol EWMA, the conditional-vol path is strictly point-in-time (σ_t doesn't use ε_t), and
standardization delivers ~unit variance. Synthetic simulation — no DB."""
import numpy as np
from lighthouse import garch


def _simulate_garch(n=1500, omega=1e-6, alpha=0.08, beta=0.90, seed=0):
    rng = np.random.RandomState(seed)
    v = omega / (1 - alpha - beta)
    eps = np.empty(n)
    for t in range(n):
        s = np.sqrt(v)
        e = s * rng.standard_normal()
        eps[t] = e
        v = omega + alpha * e * e + beta * v
    return eps


def test_fit_converges_stationary_and_beats_ewma():
    eps = _simulate_garch()
    g = garch.fit_garch11(eps)
    assert g["converged"] is True
    assert 0.0 < g["persistence"] < 1.0                 # stationary GARCH, not IGARCH
    assert g["omega"] > 0 and g["alpha"] >= 0 and g["beta"] >= 0
    assert g["loglik"] >= g["ewma_loglik"]              # MLE fit is at least as good as fixed-λ EWMA


def test_conditional_vol_is_point_in_time():
    eps = _simulate_garch(n=400, seed=3)
    g = garch.fit_garch11(eps)
    sd = g["uncond_var"]                                # fixed seed → isolate the recursion, not the seed
    v1 = garch.cond_vol(eps, g, seed=sd)
    bumped = eps.copy(); bumped[200] = 0.1              # a definite large shock at t=200
    v2 = garch.cond_vol(bumped, g, seed=sd)
    assert np.allclose(v1[:201], v2[:201])              # σ_t (t<=200) unchanged by ε_200 → no look-ahead
    assert not np.allclose(v1[201], v2[201])            # σ_201 DOES react to ε_200 (the recursion works)


def test_standardization_gives_unit_variance():
    eps = _simulate_garch(n=2000, seed=7)
    g = garch.fit_garch11(eps)
    z = garch.standardize(eps, g)
    assert 0.8 < float(np.std(z)) < 1.25                # standardized residuals ~ N(0,1)


def test_too_short_series_does_not_converge():
    assert garch.fit_garch11(np.random.RandomState(0).standard_normal(40))["converged"] is False
