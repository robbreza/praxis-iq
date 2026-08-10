"""Lighthouse Phase 1 — continuous historical validation (Spec: Validation Framework).

Not a hand-picked 30-50 days: this scores the engine across EVERY eligible trading day, on the
measures the spec calls for — expected-return accuracy, residual reduction, alert burden/calibration,
big-move explanation coverage, and an earnings-signal check (does the event lens actually light up
around filings). No-look-ahead is enforced structurally (attribution fits on trailing data; the CI
test in tests/test_lighthouse_replay.py gates the AsOf invariant).
"""
from __future__ import annotations
import numpy as np
import psycopg2
from core.security import get_database_url
from core import db as _db
from lighthouse import data
from lighthouse.attribution import market_peer_model


def validate(issuer="USIO", market="IWM", peers=None, window=126) -> dict:
    peers = peers or ["RPAY", "PSFE", "PAY", "CASS", "GDOT", "EVTC"]
    rets = data.returns_frame([issuer, market] + peers)
    model = market_peer_model(rets, issuer=issuer, market=market, peers=peers, window=window)
    a = model["actual_ret"].values; e = model["expected_ret"].values; r = model["residual"].values

    # model accuracy
    corr = float(np.corrcoef(a, e)[0, 1])
    rmse_bps = float(np.sqrt(np.mean(r**2)) * 1e4)
    resid_reduction = 1 - (np.median(np.abs(r)) / (np.median(np.abs(a)) + 1e-12))
    dir_hit = float(np.mean(np.sign(a) == np.sign(e)))

    # alert burden / calibration (rarity is an empirical trailing percentile)
    rar = model["residual_pctile"].dropna().values
    alert_90 = float(np.mean(rar >= 0.90)); alert_75 = float(np.mean(rar >= 0.75))
    per_year = alert_90 * 252

    # big-move explanation coverage: of the top-decile |residual| days, how many had a candidate
    # SEC cause in the +/-10d window (public before that day's close)
    from lighthouse import events
    thr = np.quantile(np.abs(r), 0.90)
    big_days = [d for d, row in model.iterrows() if abs(row["residual"]) >= thr]
    conn = _db.get_connection()
    explained = 0
    for d in big_days:
        win = events.window_for_day(issuer, d, lookback_days=10, conn=conn)
        if any("candidate" in w["timing"] for w in win):
            explained += 1
    # earnings signal: mean |residual| on the session AFTER an 8-K/10-Q vs baseline
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT published_at::date FROM lh_event
                   WHERE ticker=%s AND (headline LIKE '10-Q%%' OR headline LIKE '10-K%%' OR headline LIKE '8-K%%')""", (issuer,))
    filing_days = {row[0] for row in cur.fetchall()}
    conn.close()
    resid_by_day = {d: row["residual"] for d, row in model.iterrows()}
    day_list = list(model.index)
    post_filing = []
    for i, d in enumerate(day_list[:-1]):
        if d in filing_days:
            post_filing.append(abs(resid_by_day[day_list[i+1]]))
    base = float(np.mean(np.abs(r)))
    earn_ratio = (float(np.mean(post_filing)) / base) if post_filing else None

    m = dict(days=len(model), start=str(model.index[0]), end=str(model.index[-1]),
             model_corr=corr, rmse_bps=rmse_bps, residual_reduction=resid_reduction, direction_hit=dir_hit,
             alert_rate_90=alert_90, alert_rate_75=alert_75, alerts_per_year=per_year,
             big_move_days=len(big_days), big_move_explained_by_sec=explained,
             big_move_explained_frac=(explained/len(big_days) if big_days else None),
             earnings_signal_ratio=earn_ratio, no_lookahead="enforced (AsOf + CI test)")
    return m


def report(m: dict) -> str:
    L = ["Lighthouse — Historical Validation", "=" * 40,
         f"Coverage: {m['days']} trading days ({m['start']} .. {m['end']})", "",
         "Model accuracy (market+peer expected-return):",
         f"  corr(expected, actual)   {m['model_corr']:+.2f}",
         f"  residual RMSE            {m['rmse_bps']:.0f} bps/day",
         f"  |residual| reduction     {m['residual_reduction']*100:.0f}%  (vs raw daily move)",
         f"  direction hit-rate       {m['direction_hit']*100:.0f}%", "",
         "Alert burden / calibration:",
         f"  HIGH-abnormality (>=90th) {m['alert_rate_90']*100:.1f}% of days  (~{m['alerts_per_year']:.0f}/yr)",
         f"  Watch+ (>=75th)           {m['alert_rate_75']*100:.1f}% of days", "",
         "Explanation coverage:",
         f"  Big moves (top-decile |resid|): {m['big_move_days']}",
         f"  ...with a candidate SEC cause in-window: {m['big_move_explained_by_sec']} "
         f"({(m['big_move_explained_frac'] or 0)*100:.0f}%)",
         f"  -> the rest are genuinely SEC-unexplained (flow/news/private lenses, Phase 3)", "",
         f"Earnings signal: mean |residual| the day after an 8-K/10-Q is "
         f"{(m['earnings_signal_ratio'] or 0):.1f}x the baseline "
         f"({'event lens fires' if (m['earnings_signal_ratio'] or 0) > 1.3 else 'weak'})",
         f"No-look-ahead: {m['no_lookahead']}"]
    return "\n".join(L)
