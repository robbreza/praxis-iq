"""Pin the calibration scoring core (Spec 13.6): reliability binning, monotonicity detection, and
persistence — the ex-post evaluation logic, tested on synthetic aligned arrays (no DB)."""
import numpy as np
from lighthouse import calibration as cal


def test_reliability_bins_and_event_rate():
    # rarity spread across ROUTINE/HIGH/EXTREME; catalysts only on the extreme days
    rarity = [0.3, 0.4, 0.5, 0.92, 0.98, 0.99]
    residual = [0.001, -0.002, 0.001, -0.03, 0.05, -0.06]
    explained = [0, 0, 0, 0, 1, 1]                       # catalysts concentrated in the rarest days
    fwd = [0.001, -0.001, 0.0, -0.02, 0.04, -0.05]       # forward moves continue same direction
    r = cal.reliability(rarity, residual, explained, fwd)
    bins = {t["bin"]: t for t in r["table"]}
    assert bins["ROUTINE"]["n"] == 3 and bins["EXTREME"]["n"] == 2
    assert bins["EXTREME"]["event_rate"] == 1.0          # both extreme days had a catalyst
    assert bins["ROUTINE"]["event_rate"] == 0.0
    # forward moves share the residual's sign here → high persistence
    assert bins["EXTREME"]["persist_rate"] == 1.0


def test_monotonic_flag():
    # event rate strictly increases across bins → monotonic True
    rarity = [0.3, 0.8, 0.93, 0.99]
    res = [0.01, 0.01, 0.01, 0.01]
    explained = [0.0, 0.3, 0.6, 1.0]                     # each bin has one day; rate = its value
    fwd = [0.0, 0.0, 0.0, 0.0]
    assert cal.reliability(rarity, res, explained, fwd)["event_rate_monotonic"] is True
    # a dip breaks monotonicity
    explained2 = [0.5, 0.1, 0.6, 1.0]
    assert cal.reliability(rarity, res, explained2, fwd)["event_rate_monotonic"] is False


def test_forward_nan_excluded_from_persistence():
    rarity = [0.99, 0.99]
    res = [0.05, 0.05]
    explained = [1, 1]
    fwd = [np.nan, np.nan]                               # no future available
    t = cal.reliability(rarity, res, explained, fwd)["table"]
    ext = [b for b in t if b["bin"] == "EXTREME"][0]
    assert ext["n"] == 2 and ext["persist_rate"] is None and ext["fwd_abs_bps"] is None
