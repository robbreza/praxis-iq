"""Lighthouse — live calibration monitor (Spec 13.6).

Rigor is only credible if it's *calibrated*: when Lighthouse says a day is abnormal, does that actually
correspond to information? This turns the one-shot validation into a standing control on the LIVE engine
(multi-factor model + FDR gate), answering three questions a desk would ask:

  1. RELIABILITY — bin days by abnormality; does the frequency of a real catalyst (a material SEC
     filing in-window) rise monotonically with the abnormality bin? A well-calibrated engine's higher
     bins are more often explained AND are followed by larger forward moves.
  2. ALERT PRECISION — of the days that clear the FDR gate (the ones that would buzz a phone), what
     fraction had an identifiable catalyst? (The rest are the honest "flow/news/private" coverage gap.)
  3. INFORMATION vs NOISE — do abnormal days DIFFUSE (the move persists — Spec 12) or REVERT (a
     liquidity/microstructure blip)? Persistence on abnormal days is the signature of real information.

Note on look-ahead: the LIVE verdict is strictly point-in-time (trailing fits). Calibration is an ex-post
EVALUATION done now over history, so it may legitimately use forward returns to LABEL past days — that
is how you score a forecaster, not a leak into the live signal. The pure scoring core (`reliability`) is
separated from the DB fetch so it is unit-tested on synthetic arrays.
"""
from __future__ import annotations
from core import db as _db
import numpy as np

# Abnormality buckets aligned to the confidence thresholds (rarity = normal-tail mass within ±|z|).
_BINS = [("ROUTINE", 0.0, 0.75), ("MODERATE", 0.75, 0.90), ("HIGH", 0.90, 0.97), ("EXTREME", 0.97, 1.01)]


def reliability(rarity, residual, explained, fwd_resid) -> dict:
    """Pure scoring core. All args are aligned per-day arrays (fwd_resid may be nan for the last k days).
    Returns the reliability table + monotonicity + information-vs-noise persistence."""
    rar = np.asarray(rarity, float)
    res = np.asarray(residual, float)
    exp = np.asarray(explained, float)                      # 1.0 if a material catalyst was in-window
    fwd = np.asarray(fwd_resid, float)
    table = []
    for label, lo, hi in _BINS:
        mask = (rar >= lo) & (rar < hi)
        n = int(mask.sum())
        if n == 0:
            table.append(dict(bin=label, n=0, event_rate=None, fwd_abs_bps=None, persist_rate=None))
            continue
        ev = float(np.nanmean(exp[mask])) if n else None
        fm = fwd[mask]
        valid = ~np.isnan(fm)
        fwd_abs = float(np.mean(np.abs(fm[valid])) * 1e4) if valid.any() else None
        # persistence: forward move continues in the SAME direction as the day's residual (diffusion)
        persist = (float(np.mean(np.sign(fm[valid]) == np.sign(res[mask][valid]))) if valid.any() else None)
        table.append(dict(bin=label, n=n, event_rate=ev, fwd_abs_bps=fwd_abs, persist_rate=persist))
    # is the event rate monotonically non-decreasing across non-empty bins? (calibration sanity)
    rates = [t["event_rate"] for t in table if t["event_rate"] is not None]
    monotonic = all(a <= b + 1e-9 for a, b in zip(rates, rates[1:])) if len(rates) >= 2 else None
    return dict(table=table, event_rate_monotonic=monotonic)


def calibrate(issuer="USIO", window=126, fwd_k=5, lookback_days=10, conn=None) -> dict:
    """Score the live engine over all available history. Best-effort; returns {'error':...} on failure
    so a display never breaks."""
    own = conn is None
    try:
        import psycopg2
        from core.security import get_database_url
        from lighthouse import data
        from lighthouse.factor_model import attribution
        from lighthouse.shadow import SHADOW_TICKERS
        conn = conn or _db.get_connection()
        rets = data.returns_frame(SHADOW_TICKERS, conn=conn)
        m = attribution(rets, issuer, window=window)
        if m.empty:
            return {"error": "no model"}
        idx = list(m.index)
        rar = m["residual_pctile"].values
        res = m["residual"].values
        fdr = m["fdr_significant"].values if "fdr_significant" in m.columns else np.zeros(len(m), bool)

        # material catalysts (batch): a day is "explained" if a 10-Q/10-K/8-K filed within the lookback
        cur = conn.cursor()
        cur.execute("""SELECT DISTINCT published_at::date FROM lh_event WHERE ticker=%s
                       AND (headline LIKE '10-Q%%' OR headline LIKE '10-K%%' OR headline LIKE '8-K%%')""",
                    (issuer,))
        material = {r[0] for r in cur.fetchall()}
        explained = np.array([
            1.0 if any((d - __import__("datetime").timedelta(days=o)) in material for o in range(lookback_days + 1))
            else 0.0 for d in idx])

        # forward k-day cumulative residual (ex-post label; nan where the future is unavailable)
        fwd = np.array([float(np.sum(res[i+1:i+1+fwd_k])) if i + fwd_k < len(res) else np.nan
                        for i in range(len(res))])

        rel = reliability(rar, res, explained, fwd)

        # FDR alert precision + recall of the biggest moves
        fdr_mask = np.asarray(fdr, bool)
        n_fdr = int(fdr_mask.sum())
        fdr_precision = float(np.mean(explained[fdr_mask])) if n_fdr else None
        big_thr = np.quantile(np.abs(res), 0.90)
        big_mask = np.abs(res) >= big_thr
        recall_big = float(np.mean(fdr_mask[big_mask])) if big_mask.any() else None

        if own:
            conn.close()
        return dict(days=len(m), start=str(idx[0]), end=str(idx[-1]),
                    reliability=rel["table"], event_rate_monotonic=rel["event_rate_monotonic"],
                    fdr_days=n_fdr, fdr_per_year=(n_fdr / len(m) * 252), fdr_precision=fdr_precision,
                    big_move_recall=recall_big, fwd_k=fwd_k)
    except Exception as e:
        try:
            if own and conn:
                conn.close()
        except Exception:
            pass
        return {"error": repr(e)}


_CACHE_KEY = "lighthouse_calibration.json"


def refresh_cache(client_id="usio", ticker="USIO") -> dict:
    """Compute calibration and persist it (calibration re-runs the full model, so the page reads this
    cache instead of recomputing on every render). Called from the daily scheduler."""
    c = calibrate(ticker)
    try:
        from core import db
        if not c.get("error"):
            db.save_json(_CACHE_KEY, c, client_id=client_id)
    except Exception:
        pass
    return c


def load_cache(client_id="usio"):
    try:
        from core import db
        return db.load_json(_CACHE_KEY, None, client_id=client_id)
    except Exception:
        return None


def render(c: dict) -> str:
    if c.get("error"):
        return f"Calibration unavailable: {c['error']}"
    L = [f"Lighthouse — Live Calibration ({c['days']} days, {c['start']}..{c['end']})", "=" * 44,
         "Reliability (abnormality bin -> catalyst rate / forward move / persistence):"]
    for t in c["reliability"]:
        if not t["n"]:
            continue
        er = f"{t['event_rate']*100:.0f}% w/ catalyst" if t["event_rate"] is not None else "—"
        fa = f"{t['fwd_abs_bps']:.0f}bps fwd" if t["fwd_abs_bps"] is not None else "—"
        ps = f"{t['persist_rate']*100:.0f}% persist" if t["persist_rate"] is not None else "—"
        L.append(f"  {t['bin']:<9} n={t['n']:<4} {er:<18} {fa:<12} {ps}")
    L += ["",
          f"Event-rate rises with abnormality: {c['event_rate_monotonic']}",
          f"FDR alerts: {c['fdr_days']} (~{c['fdr_per_year']:.0f}/yr) · "
          f"{(c['fdr_precision'] or 0)*100:.0f}% had an identifiable catalyst",
          f"Recall: {(c['big_move_recall'] or 0)*100:.0f}% of top-decile moves cleared the FDR gate"]
    return "\n".join(L)
