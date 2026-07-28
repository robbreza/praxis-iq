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


# Benchmark ladder for the weekly context strip. Order = relevance to a nano-cap payments name.
# `relevant` flags the two the attribution model actually uses (the peer basket + the small-cap market
# factor); the broad indices are familiar TV anchors, kept as reference so the reader can locate the
# number — never as the primary comp. A naked drift figure is uninterpretable; this is its yardstick.
_BENCH_LADDER = [
    ("Payments peers", "__peers__", True,  "direct comp"),
    ("Russell 2000",   "IWM",       True,  "size cohort · model factor"),
    ("S&P 500",        "SPY",       False, "broad market"),
    ("Nasdaq 100",     "QQQ",       False, "large-cap tech ref"),
    ("Dow 30",         "DIA",       False, "mega-cap ref"),
]
# Loaded alongside the issuer so the context strip always has data (see shadow.SHADOW_TICKERS).
BENCHMARK_TICKERS = ["IWM", "SPY", "QQQ", "DIA"]


def benchmark_context(week_start, week_end, issuer_car, peers, conn) -> list[dict]:
    """Weekly total return of each benchmark over the same ISO week, plus the issuer's RELATIVE
    performance (issuer − benchmark, in points). Same close-to-close compounding used for the issuer,
    so the comparison is apples-to-apples. Missing/unloaded tickers are skipped, not faked."""
    from lighthouse.data import returns_frame
    rf = returns_frame(BENCHMARK_TICKERS + list(peers), conn=conn)
    if rf.empty:
        return []
    wk = rf[[week_start <= d <= week_end for d in rf.index]]
    out = []
    for label, tk, relevant, note in _BENCH_LADDER:
        if tk == "__peers__":
            cols = [p for p in peers if p in wk.columns]
            daily = wk[cols].mean(axis=1) if cols else None      # equal-weight basket, as the model builds it
        else:
            daily = wk[tk] if tk in wk.columns else None
        if daily is None:
            continue
        vals = daily.dropna().values
        if len(vals) == 0:
            continue
        car = float(np.prod(1 + vals) - 1)
        out.append(dict(label=label, ret=car, rel=issuer_car - car, relevant=relevant, note=note))
    return out


def _context_read(issuer_car, ctx) -> str:
    """One plain-English sentence anchoring the move to its two most-relevant comps."""
    by = {c["label"]: c for c in ctx}
    peers, rus = by.get("Payments peers"), by.get("Russell 2000")
    if not peers and not rus:
        return ""
    anchor = peers or rus
    verb = "underperformed" if anchor["rel"] < 0 else "outperformed"
    bits = []
    if peers:
        bits.append(f"payments peers {peers['ret']*100:+.1f}%")
    if rus:
        bits.append(f"the Russell 2000 {rus['ret']*100:+.1f}%")
    return (f"{issuer_car*100:+.1f}% on the week vs " + " and ".join(bits) +
            f" — {verb} its peer group by {abs(anchor['rel'])*100:.1f} pts.")


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

    # dominant driver of the week. "Explained by market/peers" requires the residual to actually be
    # SMALL — both absolutely and as a fraction of the move — AND the move to share the market's
    # direction. Otherwise a big divergence (stock flat while peers rally) would be mislabelled as
    # "moved with peers" when it is the opposite: an unexplained divergence.
    same_dir = car_actual != 0 and (car_expected * car_actual) > 0
    explained = abs(resid_sum) < 0.015 or (same_dir and abs(resid_sum) < 0.4 * abs(car_actual))
    if wk_events:
        driver = f"{wk_events[0][1][:60]} [{wk_events[0][0]}]"; driver_kind = "event"
    elif explained:
        driver = "moved with the market & payments peers"; driver_kind = "market"
    elif weekly_rarity >= 0.80 and abnormal_days <= 1:
        driver = "quiet unexplained drift (built from small daily moves — no single dramatic day)"; driver_kind = "drift"
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

    # Market context — the yardstick. A drift number alone is uninterpretable; anchor it to the
    # peer basket, the small-cap index, and the broad-market indices the CEO already watches.
    peers = []
    if ticker.upper() == "USIO":
        from lighthouse.config.usio import USIO as _U
        peers = _U["business_peers"]
    try:
        ctx = benchmark_context(wstart, wend, car_actual, peers, conn)
    except Exception:
        ctx = []
    context_read = _context_read(car_actual, ctx) if ctx else ""

    if own: conn.close()
    return dict(ticker=ticker, week=f"{wstart} .. {wend}", trading_days=len(days),
                car_actual=car_actual, car_expected=car_expected, resid_sum=resid_sum,
                weekly_rarity=weekly_rarity, abnormal_days=abnormal_days,
                biggest_day=str(big_day), biggest_residual=big_resid,
                events=[f"{h[:60]} [{d}]" for d, h in wk_events],
                driver=driver, driver_kind=driver_kind, holders=hctx,
                context=ctx, context_read=context_read)


def render_weekly(w: dict) -> str:
    if w.get("empty"):
        return "No trading data for the week."
    tell = ("The week's cumulative UNEXPLAINED drift is the story" if w["driver_kind"] == "drift"
            else "Driven by a filing" if w["driver_kind"] == "event"
            else "Largely explained by market/peers" if w["driver_kind"] == "market"
            else "Idiosyncratic and unexplained")
    ctx_lines = []
    if w.get("context"):
        ctx_lines.append("\n**This week in context** (total return; USIO relative in pts)")
        for c in w["context"]:
            tag = "  ◂ comp" if c["relevant"] else ""
            ctx_lines.append(f"- {c['label']}: {c['ret']*100:+.1f}%   (USIO {c['rel']*100:+.1f} pts){tag}")
    return "\n".join([
        f"# {w['ticker']} — week of {w['week']}",
        f"**{w['ticker']} {w['car_actual']*100:+.1f}% on the week** vs an expected "
        f"{w['car_expected']*100:+.1f}%. Cumulative **unexplained drift {w['resid_sum']*100:+.1f}%**, "
        f"{ordinal(w['weekly_rarity']*100)}-percentile for a week.",
        (f"\n{w['context_read']}" if w.get("context_read") else ""),
    ] + ctx_lines + [
        f"\n_Read:_ {tell}. {w['driver']}.",
        f"\n- Abnormal days this week: {w['abnormal_days']} of {w['trading_days']}",
        f"- Biggest single day: {w['biggest_day']} ({w['biggest_residual']*100:+.1f}% unexplained)",
        ("- Filings in-week: " + "; ".join(w["events"])) if w["events"] else "- No 10-Q/10-K/8-K filed in-week",
    ] + ([
        f"- Holder lens ({w['holders']['quarter']}): " + "; ".join(w["holders"]["lines"][:3]),
        f"  → {w['holders']['note']}. {w['holders']['caveat']}",
    ] if w.get("holders") and w["holders"].get("lines") else []))


# ── Context cache — lets the Today landing page mirror the weekly context WITHOUT the heavy live
# compute on every render. Refreshed post-close by the scheduler and on any Lighthouse-page visit.
_CTX_CACHE_KEY = "lighthouse_weekly_context.json"
_CTX_FIELDS = ("week", "car_actual", "car_expected", "resid_sum", "weekly_rarity", "abnormal_days",
               "trading_days", "driver", "driver_kind", "context", "context_read")


def save_context_cache(client_id, ticker, wk) -> None:
    if not wk or wk.get("empty"):
        return
    try:
        from core import db
        db.save_json(_CTX_CACHE_KEY, {k: wk.get(k) for k in _CTX_FIELDS}, client_id=client_id)
    except Exception:
        pass


def load_context_cache(client_id, ticker):
    try:
        from core import db
        return db.load_json(_CTX_CACHE_KEY, None, client_id=client_id)
    except Exception:
        return None
