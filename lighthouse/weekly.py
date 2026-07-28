"""Lighthouse — Weekly Digest.

Daily answers "what happened today"; the weekly digest answers the more telling question: "what is
happening to this stock lately?" It rolls the daily attribution up to the week, and its headline
metric is the CUMULATIVE UNEXPLAINED DRIFT — a week can be highly abnormal on the sum of small daily
residuals even when no single day was dramatic (five quiet -1.5% unexplained days = a -7% weekly
drift). That drift is the Spec 12 lag/diffusion made visible, and it matches the cadence a CEO
actually wants: a weekly read, with daily alerts reserved for the rare/extreme.
"""
from __future__ import annotations
from datetime import timedelta

import numpy as np
import psycopg2
from core.security import get_database_url


def _conn(): return psycopg2.connect(get_database_url())


def _isoweek(d): return d.isocalendar()[:2]


def ordinal(n: int) -> str:
    n = int(n)
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


def weekly_digest(model, ticker, week_ending=None, conn=None) -> dict:
    """model: the attribution DataFrame (index=date; cols actual_ret/expected_ret/residual/
    residual_pctile). Rolls up one ISO week (the latest if week_ending is None)."""
    own = conn is None; conn = conn or _conn()
    idx = list(model.index)
    target = _isoweek(week_ending or idx[-1])
    wk = model[[_isoweek(d) == target for d in idx]]
    if wk.empty:
        if own: conn.close()
        return {"empty": True}

    a = wk["actual_ret"].values; e = wk["expected_ret"].values; r = wk["residual"].values
    car_actual = float(np.prod(1 + a) - 1)
    car_expected = float(np.prod(1 + e) - 1)
    resid_sum = float(np.sum(r))                 # cumulative unexplained drift

    # weekly rarity: |this week's residual sum| vs the historical distribution of weekly residual sums
    by_week = {}
    for d, row in model.iterrows():
        by_week.setdefault(_isoweek(d), []).append(row["residual"])
    hist = np.array([sum(v) for v in by_week.values()])
    weekly_rarity = float((np.abs(hist) <= abs(resid_sum)).mean())

    abnormal_days = int((wk["residual_pctile"] >= 0.75).sum())
    days = [d for d in wk.index]
    big_day = wk["residual"].abs().idxmax()
    big_resid = float(wk.loc[big_day, "residual"])

    # material events in the week
    cur = conn.cursor()
    wstart, wend = days[0], days[-1]
    cur.execute("""SELECT published_at::date, headline FROM lh_event
                   WHERE ticker=%s AND published_at::date BETWEEN %s AND %s
                     AND (headline LIKE '10-Q%%' OR headline LIKE '10-K%%' OR headline LIKE '8-K%%')
                   ORDER BY published_at""", (ticker, wstart - timedelta(days=2), wend))
    wk_events = cur.fetchall()
    if own: conn.close()

    # dominant driver of the week
    if wk_events:
        driver = f"{wk_events[0][1][:60]} [{wk_events[0][0]}]"; driver_kind = "event"
    elif weekly_rarity >= 0.80 and abnormal_days <= 1:
        driver = "quiet unexplained drift (built from small daily moves — no single dramatic day)"; driver_kind = "drift"
    elif abs(car_expected) >= 0.6 * abs(car_actual) and car_actual != 0:
        driver = "moved with the market & payments peers"; driver_kind = "market"
    else:
        driver = "unexplained by current lenses"; driver_kind = "unexplained"

    # When the week's move is unexplained by market/peers/events, bring the holder lens (the Praxis
    # moat): is a large holder reducing? Only surfaced for drift/unexplained weeks — that's when
    # "who's selling?" is the question.
    hctx = None
    if driver_kind in ("drift", "unexplained") and resid_sum < 0:
        try:
            from lighthouse import holders as _h
            hctx = _h.holder_context(ticker)
        except Exception:
            hctx = None

    return dict(ticker=ticker, week=f"{wstart} .. {wend}", trading_days=len(days),
                car_actual=car_actual, car_expected=car_expected, resid_sum=resid_sum,
                weekly_rarity=weekly_rarity, abnormal_days=abnormal_days,
                biggest_day=str(big_day), biggest_residual=big_resid,
                events=[f"{h[:60]} [{d}]" for d, h in wk_events],
                driver=driver, driver_kind=driver_kind, holders=hctx)


def render_weekly(w: dict) -> str:
    if w.get("empty"):
        return "No trading data for the week."
    tell = ("The week's cumulative UNEXPLAINED drift is the story" if w["driver_kind"] == "drift"
            else "Driven by a filing" if w["driver_kind"] == "event"
            else "Largely explained by market/peers" if w["driver_kind"] == "market"
            else "Idiosyncratic and unexplained")
    return "\n".join([
        f"# {w['ticker']} — week of {w['week']}",
        f"**{w['ticker']} {w['car_actual']*100:+.1f}% on the week** vs an expected "
        f"{w['car_expected']*100:+.1f}%. Cumulative **unexplained drift {w['resid_sum']*100:+.1f}%**, "
        f"{ordinal(w['weekly_rarity']*100)}-percentile for a week.",
        f"\n_Read:_ {tell}. {w['driver']}.",
        f"\n- Abnormal days this week: {w['abnormal_days']} of {w['trading_days']}",
        f"- Biggest single day: {w['biggest_day']} ({w['biggest_residual']*100:+.1f}% unexplained)",
        ("- Filings in-week: " + "; ".join(w["events"])) if w["events"] else "- No 10-Q/10-K/8-K filed in-week",
    ] + ([
        f"- Holder lens ({w['holders']['quarter']}): " + "; ".join(w["holders"]["lines"][:3]),
        f"  → {w['holders']['note']}. {w['holders']['caveat']}",
    ] if w.get("holders") and w["holders"].get("lines") else []))
