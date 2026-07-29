"""Lighthouse — multiple-testing gate (Spec 13.3).

A single day's residual is "abnormal" at a z-score, but Lighthouse scans EVERY trading day. Under the
null (no stock-specific information) the standardized residual is ~N(0,1), so ~2.3% of days breach 2σ
one-sided by pure chance — roughly 11 spurious "abnormal" days a year. If those buzz a phone, the
channel trains the reader to ignore it. This gate applies **Benjamini-Hochberg** over a trailing
window of daily p-values to control the **False Discovery Rate** — the expected proportion of false
alarms among flagged days — at a level q (default 10%).

Discipline: point-in-time. Day t's gate uses only the p-values of the trailing `window` days ENDING at
t (never the future), so a verdict is never revised by look-ahead.

Semantics (Spec 13.3): the gate does NOT change the descriptive abnormality label (how statistically
unusual the move is) — it decides whether the day is a genuine DISCOVERY worth an alert vs. an expected
tail event given how many days we've scanned. The loud channels (phone push) require `fdr_significant`.

p-value: p = 1 − rarity, where rarity = normal-tail mass within ±|z| (from factor_model), i.e. the
two-sided p = 2·(1 − Φ(|z|)). Uses the regime-aware z, so the multiple-testing correction sits on top
of the conditional-vol standardization, not a static distribution.
"""
from __future__ import annotations
import math


def bh_cutoff(pvals: list[float], q: float = 0.10, dependent: bool = False) -> float:
    """Benjamini-Hochberg p-value cutoff for FDR ≤ q. Returns the largest p(k) with p(k) ≤ (k/N)·q
    (0 if none qualify). `dependent=True` applies the Benjamini-Yekutieli harmonic penalty, which holds
    FDR under ARBITRARY dependence (more conservative); default BH assumes independence / positive
    dependence, appropriate for factor-model residuals with common factors removed."""
    n = len(pvals)
    if n == 0:
        return 0.0
    c = sum(1.0 / i for i in range(1, n + 1)) if dependent else 1.0
    cutoff = 0.0
    for k, p in enumerate(sorted(pvals), start=1):
        if p <= (k / (n * c)) * q:
            cutoff = p           # keep the largest qualifying p (BH steps up to it)
    return cutoff


def apply_gate(model_df, q: float = 0.10, window: int = 252, dependent: bool = False):
    """Add `p_value`, `fdr_cutoff`, `fdr_significant` to a factor-model frame. Each day is tested
    against the BH cutoff computed on the trailing `window` p-values ending that day (point-in-time)."""
    if model_df is None or model_df.empty or "residual_pctile" not in model_df.columns:
        return model_df
    df = model_df.copy()
    pv = [min(1.0, max(1e-12, 1.0 - float(r))) for r in df["residual_pctile"].tolist()]
    cutoffs, sig = [], []
    for i in range(len(pv)):
        w = pv[max(0, i - window + 1): i + 1]        # trailing window ending at i (inclusive)
        cut = bh_cutoff(w, q=q, dependent=dependent)
        cutoffs.append(cut)
        sig.append(pv[i] <= cut)
    df["p_value"] = pv
    df["fdr_cutoff"] = cutoffs
    df["fdr_significant"] = sig
    df["fdr_q"] = q
    return df


def two_sided_p_from_z(z: float) -> float:
    """Standalone two-sided p under the standard normal (kept for callers that hold a z, not a rarity)."""
    return 2.0 * (1.0 - 0.5 * (1.0 + math.erf(abs(z) / math.sqrt(2.0))))
