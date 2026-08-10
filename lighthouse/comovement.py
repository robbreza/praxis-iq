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
from core import db as _db
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

# The factor/size/sector ETFs & indices — always in the universe as the market context, whatever the
# client. Everything else is discovered per-client (below).
_ANCHOR_CATS = ("payments ETF", "fintech ETF", "small-cap idx", "small growth", "small value",
                "broad market", "regional banks")
_MARKET_ANCHORS = {t: c for t, c in CANDIDATE_UNIVERSE.items() if c in _ANCHOR_CATS}
_UNIVERSE_CACHE_KEY = "lighthouse_comovement_universe.json"


def candidate_universe(issuer, client_id=None, defined_peers=None, max_sic=60) -> dict:
    """Assemble the co-movement candidate universe for ANY client by TRIANGULATING sources — so the
    lens isn't hardcoded per issuer (the bridge to onboarding). Union of: the SIC screen
    (core.peer_discovery), the client's defined + valuation comps, the coverage-lens tickers, and the
    fixed market anchors. Falls back to the built-in universe when discovery is too thin (e.g. USIO's
    SIC 6099 yields ~3 names). Cached."""
    uni = dict(_MARKET_ANCHORS)
    try:                                              # (1) SIC screen — auto, per client
        from core import peer_discovery
        d = peer_discovery.discover(issuer)
        label = (d.get("sic_desc") or "SIC peer")[:22]
        for tk in (d.get("sic_tickers") or [])[:max_sic]:
            if tk and tk != issuer:
                uni.setdefault(tk, label)
    except Exception:
        pass
    for tk in (defined_peers or []):                  # (2) the client's own defined peers
        if tk and tk != issuer:
            uni.setdefault(tk, "defined peer")
    try:                                              # (2b) valuation comps (peer_universe store)
        from core import db
        for p in (db.load_json("peer_universe.csv", default=None, client_id=client_id) or []):
            tk = p.get("ticker")
            if tk and tk != issuer:
                uni.setdefault(tk, "valuation comp")
    except Exception:
        pass
    try:                                              # (3) tickers the coverage lens surfaced
        from lighthouse import coverage as _cov
        for p in ((_cov.load_cache(client_id) or {}).get("coverage_peers") or []):
            tk = p.get("ticker")
            if tk and tk != issuer:
                uni.setdefault(tk, "coverage peer")
    except Exception:
        pass
    if sum(1 for t in uni if uni[t] not in _ANCHOR_CATS) < 4:   # too few real companies -> built-in
        return dict(CANDIDATE_UNIVERSE)
    try:
        from core import db
        db.save_json(_UNIVERSE_CACHE_KEY, uni, client_id=client_id)
    except Exception:
        pass
    return uni


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


def discover(issuer: str, rets: pd.DataFrame, defined_peers: list[str], universe: dict | None = None,
             top_corr=15, max_select=6) -> dict:
    """Rank-correlation + sparse selection of the candidate `universe` against the issuer, plus the
    defined-peer basket R² for comparison. `rets` = date×ticker return frame; `universe` = ticker→
    category (defaults to the built-in set)."""
    universe = universe or CANDIDATE_UNIVERSE
    cand = [c for c in universe if c in rets.columns and c != issuer]
    if issuer not in rets.columns or len(cand) < 3:
        return {"error": "insufficient candidate coverage"}
    df = rets[[issuer] + cand].dropna()
    if len(df) < 60:
        return {"error": "insufficient overlapping history"}
    y = df[issuer].values

    corrs = sorted(((c, float(np.corrcoef(df[issuer], df[c])[0, 1])) for c in cand),
                   key=lambda t: -abs(t[1]))
    top = [dict(ticker=c, corr=r, category=universe.get(c, "?"),
                defined_peer=(c in defined_peers)) for c, r in corrs[:top_corr]]

    path, sparse_r2 = forward_select(y, df[cand], max_select=max_select)
    for p in path:
        p["category"] = universe.get(p["name"], "?")
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
def ensure_universe_loaded(universe=None, period="3y"):
    """Load the candidate universe into lh_ohlcv (yfinance). `universe` = a ticker→category dict or a
    ticker list; defaults to the built-in set."""
    from lighthouse import data
    tickers = list(universe) if universe else list(CANDIDATE_UNIVERSE)
    return data.load_ohlcv(tickers, period=period)


def compute(issuer="USIO", client_id="usio", universe=None) -> dict:
    try:
        import psycopg2
        from core.security import get_database_url
        from lighthouse import data
        from lighthouse.config.usio import USIO
        defined = USIO["business_peers"]                          # per-client defined peers (USIO MVP)
        uni = universe or candidate_universe(issuer, client_id=client_id, defined_peers=defined)
        conn = _db.get_connection()
        rets = data.returns_frame([issuer] + list(uni) + defined, conn=conn)
        conn.close()
        return discover(issuer, rets, defined, universe=uni)
    except Exception as e:
        return {"error": repr(e)}


_CACHE_KEY = "lighthouse_comovement.json"


def refresh_cache(client_id="usio", issuer="USIO") -> dict:
    from lighthouse.config.usio import USIO
    uni = candidate_universe(issuer, client_id=client_id, defined_peers=USIO["business_peers"])
    ensure_universe_loaded(uni)                       # load any newly-discovered names' bars
    c = compute(issuer, client_id=client_id, universe=uni)
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
