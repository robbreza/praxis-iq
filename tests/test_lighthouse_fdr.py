"""Pin the multiple-testing gate (Spec 13.3): Benjamini-Hochberg cutoff, the Benjamini-Yekutieli
conservative variant, and that the point-in-time gate suppresses an isolated borderline day while
still passing a genuinely extreme one. Pure logic — no DB."""
import pandas as pd
from lighthouse import fdr


def test_bh_cutoff_known_example():
    # sorted p, N=5, q=0.05: p(k) <= k/N*q holds up to p=0.02 (0.02 <= 3/5*0.05=0.03); 0.5,0.7 fail
    assert abs(fdr.bh_cutoff([0.001, 0.008, 0.02, 0.5, 0.7], q=0.05) - 0.02) < 1e-12
    assert fdr.bh_cutoff([], 0.10) == 0.0
    assert fdr.bh_cutoff([0.5, 0.6, 0.9], 0.05) == 0.0        # nothing qualifies → no discovery


def test_by_is_more_conservative_than_bh():
    p = [0.001, 0.01, 0.03, 0.2]
    assert fdr.bh_cutoff(p, 0.10, dependent=True) <= fdr.bh_cutoff(p, 0.10, dependent=False)


def test_gate_suppresses_isolated_but_passes_extreme():
    n = 200
    quiet = [0.30] * n                                        # p = 0.70 — unremarkable days
    # a lone MODERATELY rare day (p=0.05) among 200 quiet ones must NOT clear the gate
    iso = quiet.copy(); iso[-1] = 0.95
    g = fdr.apply_gate(pd.DataFrame({"residual_pctile": iso}), q=0.10, window=252)
    assert g["fdr_significant"].iloc[-1] is False or g["fdr_significant"].iloc[-1] == False
    assert {"p_value", "fdr_cutoff", "fdr_significant", "fdr_q"}.issubset(g.columns)
    # a truly EXTREME day (p≈1e-5) clears it even alone
    ext = quiet.copy(); ext[-1] = 0.99999
    g2 = fdr.apply_gate(pd.DataFrame({"residual_pctile": ext}), q=0.10, window=252)
    assert bool(g2["fdr_significant"].iloc[-1]) is True


def test_empty_passthrough():
    assert fdr.apply_gate(pd.DataFrame(), 0.10).empty
    assert fdr.apply_gate(None, 0.10) is None
