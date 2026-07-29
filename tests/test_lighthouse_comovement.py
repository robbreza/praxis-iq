"""Pin the co-movement discovery core (Spec 14a): OLS R², greedy forward-stepwise driver selection
(picks the true joint drivers, skips noise, handles collinearity), and discover's shape. Pure numpy."""
import numpy as np
import pandas as pd
from lighthouse import comovement as cm


def test_ols_r2_recovers():
    np.random.seed(0)
    n = 300
    x = np.random.normal(0, 1, n)
    y = 2 * x + np.random.normal(0, 0.1, n)
    beta, r2 = cm._ols_r2(y, x.reshape(-1, 1))
    assert abs(beta[1] - 2) < 0.1 and r2 > 0.9


def test_forward_select_picks_true_drivers_not_noise():
    np.random.seed(1)
    n = 400
    x1 = np.random.normal(0, 1, n)
    x2 = np.random.normal(0, 1, n)
    cols = {"DRV1": x1, "DRV2": x2}
    for i in range(5):
        cols[f"N{i}"] = np.random.normal(0, 1, n)
    y = 1.5 * x1 + 0.8 * x2 + np.random.normal(0, 0.3, n)
    path, r2 = cm.forward_select(y, pd.DataFrame(cols), max_select=6, min_gain=0.005)
    names = [p["name"] for p in path]
    assert "DRV1" in names and "DRV2" in names and r2 > 0.8
    assert sum(1 for n in names if n.startswith("N")) <= 1        # noise mostly rejected
    # collinearity: a near-duplicate of DRV1 shouldn't both get picked for much marginal gain
    cols2 = dict(cols); cols2["DUP1"] = x1 + np.random.normal(0, 0.01, n)
    path2, _ = cm.forward_select(y, pd.DataFrame(cols2), max_select=6, min_gain=0.005)
    n2 = [p["name"] for p in path2]
    assert not ("DRV1" in n2 and "DUP1" in n2)                    # one of the pair suffices


def test_discover_shape_and_top_correlate():
    np.random.seed(2)
    n = 200
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    cands = ["IWM", "V", "MA", "RPAY", "SPY", "UPST"]
    d = {c: np.random.normal(0, 0.01, n) for c in cands}
    d["USIO"] = 0.6 * d["IWM"] + np.random.normal(0, 0.008, n)    # USIO tracks IWM by construction
    out = cm.discover("USIO", pd.DataFrame(d, index=idx), ["RPAY"], top_corr=5, max_select=4)
    assert out["top_correlates"][0]["ticker"] == "IWM"
    assert isinstance(out["sparse_r2"], float) and "revealed_new" in out
    assert out["top_correlates"][0]["defined_peer"] is False
