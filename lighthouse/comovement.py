"""Lighthouse — broad-universe co-movement peers (Spec 14a).

Our attribution uses the 6 peers WE picked. This lets the DATA say who USIO actually tracks, over a
broad candidate universe (networks, processors, fintech, small/micro payments, data/credit, and the
small-cap complex). Two views:

  * RANK-CORRELATION — the univariate co-movers (simple, robust, interpretable);
  * SPARSE SELECTION — a greedy forward-stepwise regression that lets the data pick the handful of names
    that JOINTLY explain USIO. Stepwise (not univariate) matters because payments names are collinear:
    after V is in, MA adds little — so the selected set is the marginal explainers, not a redundant pile.

Reported against the R² of our hand-picked peer basket, so divergence is quantified. This is a
STRUCTURAL discovery over history (which names are USIO's statistical peers), not a live trailing
signal — the winners can then feed the point-in-time factor model as a challenger. No sklearn/scipy:
pure-numpy OLS + forward selection, separated from the data fetch and unit-tested.
"""
from __future__ import annotations
import numpy as np
import pandas as pd

# Curated candidate universe (ticker -> short category label). yfinance-fetchable liquid names;
# any without enough overlapping history with the issuer are skipped, not faked.
CANDIDATE_UNIVERSE = {
    "V": "network", "MA": "network", "AXP": "network", "DFS": "network", "COF": "card issuer",
    "PYPL": "fintech", "XYZ": "fintech", "AFRM": "fintech", "UPST": "fintech", "SOFI": "fintech",
    "BILL": "fintech", "TOST": "fintech", "FOUR": "fintech", "FLYW": "fintech", "MQ": "fintech",
    "FI": "processor", "FIS": "processor", "GPN": "processor", "JKHY": "processor", "ACIW": "processor",
    "WEX": "processor", "EEFT": "processor", "NVEI": "processor", "STNE": "processor", "PAGS": "processor",
    "RPAY": "small payments", "PRTH": "small payments", "PAYS": "small payments", "CTLP": "small payments",
    "EVTC": "small payments", "GDOT": "small payments", "CASS": "small payments", "PAY": "small payments",
    "EFX": "data/credit", "FICO": "data/credit", "TRU": "data/credit", "INUV": "small ad-tech",
    "IPAY": "payments ETF", "FINX": "fintech ETF", "ARKF": "fintech ETF",
    "IWM": "small-cap idx", "IWO": "small growth", "IWN": "small value", "IJR": "small-cap idx",
    "SPY": "broad market", "KRE": "regional banks",
}


def _ols_r2(y: np.ndarray, X: np.ndarray):
    """Return (beta, r2) for y ~ [1, X]. X is 2-D (n × k)."""
    A = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    resid = y - A @ beta
    ssr = float(resid @ resid)
    sst = float(((y - y.mean()) ** 2).sum()) + 1e-18
    return beta, 1.0 - ssr / sst


def forward_select(y: np.ndarray, Xdf: pd.DataFrame, max_select=6, min_gain=0.005):
    """Greedy forward-stepwise: repeatedly add the candidate that most raises R², until `max_select`
    names or the marginal R² gain drops below `min_gain`. Returns (path, final_r2)."""
    selected, remaining, prev_r2, path = [], list(Xdf.columns), 0.0, []
    while remaining and len(selected) < max_select:
        best, best_r2 = None, prev_r2
        for c in remaining:
            _, r2 = _ols_r2(y, Xdf[selected + [c]].values)
            if r2 > best_r2:
                best, best_r2 = c, r2
        if best is None or (best_r2 - prev_r2) < min_gain:
            break
        selected.append(best); remaining.remove(best)
        beta, r2 = _ols_r2(y, Xdf[selected].values)
        path.append(dict(name=best, cum_r2=float(r2), beta=float(beta[len(selected)]),
                         marginal=float(best_r2 - prev_r2)))
        prev_r2 = best_r2
    return path, prev_r2


def discover(issuer: str, rets: pd.DataFrame, defined_peers: list[str],
             top_corr=15, max_select=6) -> dict:
    """Rank-correlation + sparse selection of the candidate universe against the issuer, plus the
    defined-peer basket R² for comparison. `rets` = date×ticker return frame."""
    cand = [c for c in CANDIDATE_UNIVERSE if c in rets.columns and c != issuer]
    if issuer not in rets.columns or len(cand) < 3:
        return {"error": "insufficient candidate coverage"}
    df = rets[[issuer] + cand].dropna()
    if len(df) < 60:
        return {"error": "insufficient overlapping history"}
    y = df[issuer].values

    corrs = sorted(((c, float(np.corrcoef(df[issuer], df[c])[0, 1])) for c in cand),
                   key=lambda t: -abs(t[1]))
    top = [dict(ticker=c, corr=r, category=CANDIDATE_UNIVERSE.get(c, "?"),
                defined_peer=(c in defined_peers)) for c, r in corrs[:top_corr]]

    path, sparse_r2 = forward_select(y, df[cand], max_select=max_select)
    for p in path:
        p["category"] = CANDIDATE_UNIVERSE.get(p["name"], "?")
        p["defined_peer"] = p["name"] in defined_peers

    peers_in = [p for p in defined_peers if p in df.columns]
    basket_r2 = None
    if peers_in:
        _, basket_r2 = _ols_r2(y, df[peers_in].mean(axis=1).values.reshape(-1, 1))

    revealed_new = [p["name"] for p in path if not p["defined_peer"]]
    return dict(issuer=issuer, days=len(df), n_candidates=len(cand),
                top_correlates=top, sparse=path, sparse_r2=float(sparse_r2),
                defined_basket_r2=(float(basket_r2) if basket_r2 is not None else None),
                revealed_new=revealed_new)


# ── data + cache ────────────────────────────────────────────────────────────────────────────────
def ensure_universe_loaded(period="3y"):
    """One-time/refresh load of the candidate universe into lh_ohlcv (yfinance)."""
    from lighthouse import data
    return data.load_ohlcv(list(CANDIDATE_UNIVERSE), period=period)


def compute(issuer="USIO") -> dict:
    try:
        import psycopg2
        from core.security import get_database_url
        from lighthouse import data
        from lighthouse.config.usio import USIO
        conn = psycopg2.connect(get_database_url())
        rets = data.returns_frame([issuer] + list(CANDIDATE_UNIVERSE) + USIO["business_peers"], conn=conn)
        conn.close()
        return discover(issuer, rets, USIO["business_peers"])
    except Exception as e:
        return {"error": repr(e)}


_CACHE_KEY = "lighthouse_comovement.json"


def refresh_cache(client_id="usio", issuer="USIO") -> dict:
    c = compute(issuer)
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
    if not c or c.get("error"):
        return f"Co-movement unavailable: {(c or {}).get('error')}"
    L = [f"Market-revealed peers via co-movement — {c['issuer']} ({c['days']} days, {c['n_candidates']} candidates)",
         "=" * 60, "Top co-movers (daily-return correlation):"]
    for t in c["top_correlates"][:10]:
        tag = " [our peer]" if t["defined_peer"] else ""
        L.append(f"  {t['ticker']:<6} {t['corr']:+.2f}  [{t['category']}]{tag}")
    L += ["", "Sparse set — names that JOINTLY explain USIO (forward-stepwise):"]
    for p in c["sparse"]:
        tag = " [our peer]" if p["defined_peer"] else " [NEW]"
        L.append(f"  +{p['name']:<6} cum R²={p['cum_r2']:.3f} (β {p['beta']:+.2f}) [{p['category']}]{tag}")
    L += ["",
          f"Revealed set R²: {c['sparse_r2']:.3f}   vs our peer-basket R²: "
          f"{(c['defined_basket_r2'] or 0):.3f}",
          f"New names the market ties to USIO that we DIDN'T define: {', '.join(c['revealed_new']) or '—'}"]
    return "\n".join(L)
