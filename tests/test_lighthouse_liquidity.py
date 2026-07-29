"""Pin the liquidity layer (Spec 13.5): the conviction weight, the RVOL/thin-tape metrics (point-in-time
baseline), and that a liquidity-discounted rarity de-escalates a thin-tape spike. Pure logic, no DB."""
import numpy as np
from lighthouse import liquidity as lq


def test_conviction_weight():
    assert lq.conviction(1.0) == 1.0                      # normal volume → full conviction
    assert lq.conviction(4.0) == 1.0                      # heavy volume capped at 1
    assert abs(lq.conviction(0.25) - 0.5) < 1e-9          # quarter volume → sqrt = 0.5
    assert lq.conviction(0.01) == 0.35                    # floored, never zero on volume alone
    assert lq.conviction(None) == 1.0 and lq.conviction(0) == 1.0   # unknown → don't penalize


def test_metrics_rvol_and_thin_flag():
    n = 40
    thin = [1000.0] * (n - 1) + [250.0]                    # steady baseline, last day 0.25×
    mt = lq.compute_metrics([10.0] * n, thin, lookback=20)
    assert abs(mt["rvol"].iloc[-1] - 0.25) < 0.01 and bool(mt["thin_tape"].iloc[-1]) is True
    heavy = [1000.0] * (n - 1) + [3000.0]                  # last day 3× (heavy)
    mh = lq.compute_metrics([10.0] * n, heavy, lookback=20)
    assert mh["rvol"].iloc[-1] > 1.5 and bool(mh["thin_tape"].iloc[-1]) is False


def test_baseline_is_point_in_time():
    # the RVOL baseline excludes today, so a single huge-volume day doesn't deflate its OWN rvol
    n = 40
    m = lq.compute_metrics([10.0] * n, [1000.0] * (n - 1) + [10000.0], lookback=20)
    assert m["rvol"].iloc[-1] > 5                          # 10000 vs a ~1000 trailing baseline


def test_liquidity_discount_de_escalates_thin_spike():
    # a 95th-pctile abnormality on quarter volume → discounted below the 90th HIGH threshold
    rarity, conv = 0.95, lq.conviction(0.25)
    assert rarity * conv < 0.90
    # the same abnormality on normal volume is untouched
    assert rarity * lq.conviction(1.0) == 0.95
