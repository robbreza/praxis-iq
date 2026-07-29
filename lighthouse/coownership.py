"""Lighthouse — co-ownership revealed peers (Spec 14b).

"Who owns USIO also owns ___." Aggregates USIO's 13F holders' OTHER holdings to surface the market's
peer grouping through capital allocation — the flow that actually moves a name that trades on its own.

The methodology matters (see Spec 14b): USIO's holders are mostly quant/passive/wealth vehicles whose
books hold everything (mega-caps lead every list), so RAW co-holding is meaningless. We restrict to
FOCUSED, FUNDAMENTAL holders — non-mechanical and concentrated (≤ max_positions) — the managers making
a real small-cap bet, and score each co-held name by the SUM OF ITS PORTFOLIO WEIGHTS across those
holders (a 40-name fund contributes far more per name than a 1,699-name book, which self-normalizes
against index breadth and suppresses mega-caps).

13F is quarterly and ~45d lagged, so this is a cached batch refreshed on demand — not a live render.
The pure aggregation core (`aggregate`) is separated from the EDGAR fetch and unit-tested.
"""
from __future__ import annotations
import re

# Quant / passive / market-maker / broad-index filers whose books are the whole market, not a bet.
_MECH = ("citadel", "susquehanna", "sig ", "gsa capital", "xtx", "jump trading", "hudson river",
         "two sigma", "de shaw", "millennium", "geode", "vanguard", "blackrock", "state street",
         "renaissance", "tower research", "jane street", "virtu", "ubs", "morgan stanley",
         "goldman sachs", "bank of america", "wells fargo", "jpmorgan", "jp morgan")
# Broad ETFs / cash-parking vehicles that aren't peers even in a focused book.
_ETF_STOP = ("SPDR", "ISHARES", "VANGUARD", "INVESCO QQQ", "SPY", "S&P 500", "ETF", "INDEX",
             "TREASURY", "SELECT SECTOR")


def _norm(name: str) -> str:
    return re.sub(r"[^A-Z0-9 ]", "", (name or "").upper()).strip()


def is_mechanical(filer: str) -> bool:
    return any(k in (filer or "").lower() for k in _MECH)


def _is_etf(issuer: str) -> bool:
    n = (issuer or "").upper()
    return any(k in n for k in _ETF_STOP)


def aggregate(holders: list[dict], issuer_ticker="USIO", max_positions=400, top=12) -> dict:
    """Pure core. `holders` = [{filer, mechanical, positions:[{issuer,cusip,value}]}]. Returns the
    revealed-peer ranking scored over FOCUSED (non-mechanical, ≤max_positions) holders only."""
    focused = [h for h in holders if not h.get("mechanical") and 0 < len(h.get("positions") or []) <= max_positions]
    by_cusip = {}                                        # cusip -> {issuer, score(sum weights), holders}
    tkey = _norm(issuer_ticker)
    for h in focused:
        pos = h["positions"]
        total = sum((p.get("value") or 0) for p in pos) or 1
        for p in pos:
            iss = p.get("issuer") or ""
            cusip = (p.get("cusip") or iss)[:9] if p.get("cusip") else _norm(iss)
            if _norm(iss) == tkey or tkey in _norm(iss) or _is_etf(iss):
                continue                                 # drop the issuer itself and broad ETFs
            w = (p.get("value") or 0) / total
            rec = by_cusip.setdefault(cusip, {"issuer": iss, "score": 0.0, "holders": 0})
            rec["score"] += w
            rec["holders"] += 1
    ranked = sorted(by_cusip.values(), key=lambda r: -r["score"])
    peers = [dict(issuer=r["issuer"], holders=r["holders"],
                  avg_weight=(r["score"] / r["holders"] if r["holders"] else 0.0), score=r["score"])
             for r in ranked[:top]]
    return dict(n_holders=len(holders), n_focused=len(focused),
                n_mechanical=sum(1 for h in holders if h.get("mechanical")), peers=peers)


# ── EDGAR batch (heavy; cached) ──────────────────────────────────────────────────────────────────
def _fetch_portfolio(cik) -> list[dict]:
    """A filer's latest 13F-HR holdings via core.sec_filings plumbing. [] on any failure."""
    from core import sec_filings as sf
    try:
        fil = sf.filer_13f_filings(cik, limit=1)
        if not fil:
            return []
        acc = fil[0]["accession"]
        fn = sf._info_table_filename(cik, acc)
        if not fn:
            return []
        acc2 = str(acc).replace("-", "")
        cik_i = int(str(cik).strip())
        r = sf._get(f"https://www.sec.gov/Archives/edgar/data/{cik_i}/{acc2}/{fn}", timeout=25)
        return list(sf._infotable_entries(r.content))
    except Exception:
        return []


def compute(ticker="USIO", max_holders=25, max_positions=400, top=12) -> dict:
    """Fetch the top `max_holders` USIO holders' portfolios and aggregate revealed peers. Heavy
    (throttled EDGAR) — run as a batch and cache. Best-effort; returns {'error':...} on failure."""
    try:
        from core import sec_filings as sf
        snap = sf.get_cached_13f_holders(ticker) or {}
        hs = sorted((snap.get("holders") or []), key=lambda h: -(h.get("shares") or 0))[:max_holders]
        holders = []
        for h in hs:
            pos = _fetch_portfolio(h.get("cik"))
            holders.append(dict(filer=h.get("filer"), mechanical=is_mechanical(h.get("filer")),
                                positions=pos))
        agg = aggregate(holders, issuer_ticker=ticker, max_positions=max_positions, top=top)
        agg["quarter"] = snap.get("quarter")
        agg["ticker"] = ticker
        # focused holder names (the managers whose bets define the revealed peers) for transparency
        agg["focused_holders"] = [h["filer"] for h in holders
                                  if not h["mechanical"] and 0 < len(h["positions"]) <= max_positions]
        return agg
    except Exception as e:
        return {"error": repr(e)}


_CACHE_KEY = "lighthouse_coownership.json"


def refresh_cache(client_id="usio", ticker="USIO") -> dict:
    c = compute(ticker)
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
        return f"Co-ownership unavailable: {(c or {}).get('error')}"
    L = [f"Market-revealed peers via co-ownership — {c.get('ticker')} ({c.get('quarter')})", "=" * 52,
         f"{c['n_holders']} holders fetched · {c['n_focused']} focused/fundamental · {c['n_mechanical']} quant/passive"]
    if not c["peers"]:
        L.append("\nNo concentrated active holders with clear co-holdings — USIO is owned via broad/quant/"
                 "wealth vehicles, consistent with trading on small-cap FLOW, not a fundamental peer complex.")
        return "\n".join(L)
    L.append("\nCo-held by USIO's concentrated active managers (revealed peers):")
    for p in c["peers"]:
        L.append(f"  {p['issuer']:<34} held by {p['holders']} · avg wt {p['avg_weight']*100:.1f}%")
    if c.get("focused_holders"):
        L.append("\nDefining managers: " + ", ".join(c["focused_holders"][:6]))
    return "\n".join(L)
