"""Lighthouse Production Stage 3 — Shadow Mode.

Runs the engine LIVE each trading day but WITHOUT automated executive alerts: it computes and LOGS a
verdict for the latest completed session to lh_verdict for IR review, accumulating a track record so
the explanation/calibration can be trusted before anyone wires automated CEO alerts (Spec: "USIO
should first run in Shadow Mode before automated executive alerts"). Idempotent per (client,ticker,
day). Schedule `python -m lighthouse.shadow` as a post-close daily cron; here we also backfill the
recent window so the IR-review track record is useful on day one.
"""
from __future__ import annotations
import psycopg2
from core.security import get_database_url
from lighthouse import data, events, ceo
from lighthouse.factor_model import attribution
from lighthouse.factors import FACTOR_ETFS
from lighthouse.config.usio import USIO
from lighthouse.weekly import BENCHMARK_TICKERS

# Issuer + the factor ETFs (which drive the multi-factor attribution, Spec 13.1) + the broad-market
# indices (weekly context strip) + peers (weekly peer basket, holder lens). Deduped.
_MARKET_ETFS = sorted(set(BENCHMARK_TICKERS) | set(FACTOR_ETFS))
SHADOW_TICKERS = ["USIO"] + _MARKET_ETFS + USIO["business_peers"]


def _conn(): return psycopg2.connect(get_database_url())


def _exists(cur, client_id, ticker, d):
    cur.execute("SELECT 1 FROM lh_verdict WHERE client_id=%s AND ticker=%s AND d=%s LIMIT 1",
                (client_id, ticker, d))
    return cur.fetchone() is not None


def run_shadow(client_id="usio", cfg=USIO, days_back=1, refresh=True, conn=None) -> list:
    """Compute + persist verdicts for the last `days_back` completed sessions (skip already-logged)."""
    own = conn is None; conn = conn or _conn(); cur = conn.cursor()
    if refresh:
        try:
            data.load_ohlcv(SHADOW_TICKERS, period="1mo", conn=conn)   # incremental recent bars
            events.load_events(cfg["ticker"], client_id, conn=conn)     # latest filings
        except Exception as e:
            print(f"[shadow] refresh warning: {e!r}")
    rets = data.returns_frame(SHADOW_TICKERS, conn=conn)
    model = attribution(rets, issuer=cfg["ticker"], window=126)
    days = list(model.index)[-days_back:]
    logged = []
    for d in days:
        if _exists(cur, client_id, cfg["ticker"], d):
            continue
        v = ceo.build_verdict(client_id, cfg["ticker"], d, model.loc[d], conn=conn)
        ceo.persist_verdict(v, conn=conn)
        logged.append(v)
    if own: conn.close()
    return logged


def shadow_status(client_id="usio", ticker="USIO", conn=None) -> dict:
    own = conn is None; conn = conn or _conn(); cur = conn.cursor()
    cur.execute("""SELECT count(*), min(d), max(d),
                          avg(CASE WHEN abnormality_conf>=0.85 THEN 1.0 ELSE 0 END),
                          avg(CASE WHEN explanation_conf>=0.6 THEN 1.0 ELSE 0 END)
                   FROM lh_verdict WHERE client_id=%s AND ticker=%s""", (client_id, ticker))
    n, lo, hi, abn, expl = cur.fetchone()
    if own: conn.close()
    return dict(mode="Shadow", logged=n or 0, since=str(lo) if lo else None, latest=str(hi) if hi else None,
                pct_high_abnormality=float(abn or 0), pct_explained=float(expl or 0))


if __name__ == "__main__":
    # daily post-close cron entry point (logs the latest session, no alerts)
    got = run_shadow(days_back=1)
    st = shadow_status()
    print(f"[shadow] logged {len(got)} new verdict(s); track record: {st['logged']} sessions "
          f"{st['since']}..{st['latest']} | {st['pct_high_abnormality']*100:.0f}% high-abnormality, "
          f"{st['pct_explained']*100:.0f}% explained")
