"""Pin the multi-factor model (Spec 13.1): factor construction (spreads + graceful skips), that the
rolling OLS recovers known loadings, and that the reported stats are well-formed and point-in-time.
Synthetic data only — no DB, no network."""
import numpy as np
import pandas as pd

from lighthouse.factors import build_factors
from lighthouse.factor_model import factor_model


def _dates(n):
    return pd.date_range("2024-01-01", periods=n, freq="B")


def test_build_factors_spreads_and_graceful_skip():
    n = 50
    d = _dates(n)
    r = pd.DataFrame({t: np.random.normal(0, 0.01, n) for t in
                      ["SPY", "IWM", "IWB", "IWD", "IWF", "MTUM", "IPAY", "IEF"]}, index=d)
    f = build_factors(r)
    assert list(f.columns) == ["MKT", "SMB", "HML", "MOM", "SEC", "RATE"]
    # SMB is the small-minus-large spread, not a raw leg
    assert np.allclose(f["SMB"].values, (r["IWM"] - r["IWB"]).values)
    assert np.allclose(f["MKT"].values, r["SPY"].values)          # MKT is a raw return
    # a missing short leg drops that spread factor rather than mislabeling a raw leg
    f2 = build_factors(r.drop(columns=["IWB"]))
    assert "SMB" not in f2.columns and "MKT" in f2.columns


def test_factor_model_recovers_known_loadings():
    np.random.seed(7)
    n = 400
    d = _dates(n)
    F = pd.DataFrame({"MKT": np.random.normal(0, 0.01, n),
                      "SMB": np.random.normal(0, 0.01, n)}, index=d)
    issuer = 0.8 * F["MKT"] + 1.5 * F["SMB"] + np.random.normal(0, 0.003, n)   # strong signal
    rets = pd.DataFrame({"USIO": issuer.values}, index=d)
    out = factor_model(rets, "USIO", F, window=126)
    assert not out.empty
    last = out.iloc[-1]["loadings"]
    assert abs(last["MKT"] - 0.8) < 0.25 and abs(last["SMB"] - 1.5) < 0.25   # OLS recovers betas
    assert out["r2"].mean() > 0.6                                            # high signal → high R²


def test_reported_stats_well_formed():
    np.random.seed(1)
    n = 300
    d = _dates(n)
    F = pd.DataFrame({"MKT": np.random.normal(0, 0.01, n),
                      "SMB": np.random.normal(0, 0.01, n),
                      "RATE": np.random.normal(0, 0.005, n)}, index=d)
    rets = pd.DataFrame({"USIO": np.random.normal(0, 0.02, n)}, index=d)
    out = factor_model(rets, "USIO", F, window=126)
    assert (out["residual_pctile"].between(0, 1)).all()          # rarity is a normal-tail mass
    assert np.isfinite(out["z"]).all() and np.isfinite(out["t_stat"]).all()
    assert (out["resid_se"] > 0).all()
    assert (out["n_factors"] == 3).all()
    # expected range brackets the expectation
    assert (out["expected_lo"] <= out["expected_ret"]).all() and (out["expected_ret"] <= out["expected_hi"]).all()


def test_empty_when_factors_missing_or_too_short():
    d = _dates(30)
    rets = pd.DataFrame({"USIO": np.random.normal(0, 0.02, 30)}, index=d)
    assert factor_model(rets, "USIO", pd.DataFrame(), window=126).empty     # no factors
    F = pd.DataFrame({"MKT": np.random.normal(0, 0.01, 30)}, index=d)
    assert factor_model(rets, "USIO", F, window=126).empty                  # too few rows for the window
