"""Lighthouse — Holder / forced-seller lens (the Praxis moat).

Cross-references the issuer's OWN 13F holder base (already assembled in the platform) against an
unexplained move: when the stock is bleeding with no public catalyst, is a large holder reducing or
exiting? A standalone surveillance tool can't answer this; Praxis can, because it already tracks each
holder's position history. Turns "unexplained drift" into "and here is the holder behind it."

Honest caveats (stated, per the spec ethos): 13F is QUARTERLY and ~45 days lagged, long-only-ish, and
misses non-13F/foreign/sub-$100M/short sellers. So this is CONTRIBUTING/COINCIDENT context — a strong
candidate, never a same-day proof.
"""
from __future__ import annotations
import re
from core import sec_filings as sf


def _ncik(c):
    d = re.sub(r"\D", "", str(c or ""))
    return d.lstrip("0") or d


_REDUCE = {"decreased", "exited", "trimmed", "sold", "reduced"}


def forced_sellers(ticker, top=6) -> list[dict]:
    """Top holders reducing/exiting per the latest known 13F position histories, name-joined from the
    current snapshot, sorted by size of the quarter-over-quarter reduction."""
    hist = sf.get_holder_histories(ticker) or {}
    snap = sf.get_cached_13f_holders(ticker) or {}
    names, cur_shares = {}, {}
    for h in (snap.get("holders") or []):
        c = _ncik(h.get("cik"))
        if c:
            names[c] = h.get("filer"); cur_shares[c] = h.get("shares") or 0
    # quant/market-maker/passive filers whose 13F changes are mostly mechanical, not a fundamental sell
    _MECH = ("citadel", "susquehanna", "sig ", "gsa capital", "xtx", "jump trading", "hudson river",
             "two sigma", "de shaw", "millennium", "geode", "vanguard", "blackrock", "state street",
             "renaissance", "tower research", "jane street", "virtu")
    rows = []
    for cik, d in hist.items():
        qoq = d.get("qoq_change_shares") or 0
        direction = (d.get("direction") or "").lower()
        exited = direction == "exited"
        if not (qoq < 0 or exited):        # require a REAL recent cut (or a full exit)
            continue
        c = _ncik(cik)
        nm = names.get(c) or d.get("name") or f"CIK {c}"
        cur = cur_shares.get(c, 0)
        prior = (cur - qoq) if qoq else None
        pct = (-qoq / prior) if (prior and prior > 0 and qoq < 0) else None
        mechanical = any(k in nm.lower() for k in _MECH)
        rows.append(dict(name=nm, cik=c, action=("exited" if exited else "cut"),
                         qoq_shares=qoq, current_shares=cur, pct_reduced=pct,
                         quarters_held=d.get("quarters_held"), mechanical=mechanical))
    rows.sort(key=lambda r: r["qoq_shares"])   # most-negative (biggest cut) first
    return rows[:top]


def holder_context(ticker, top=4) -> dict:
    """A compact context block for the weekly digest: notable reducers, split fundamental vs
    mechanical (quant/passive/MM), + the 13F caveat."""
    sellers = forced_sellers(ticker, top=top)
    snap = sf.get_cached_13f_holders(ticker) or {}
    fundamental = [s for s in sellers if not s["mechanical"]]
    def _line(s):
        pct = f" (-{s['pct_reduced']*100:.0f}%)" if s.get("pct_reduced") else ""
        tag = " [quant/passive]" if s["mechanical"] else ""
        return (f"{s['name']} exited" if s["action"] == "exited"
                else f"{s['name']} cut {abs(s['qoq_shares']):,}sh{pct}") + tag
    return dict(quarter=snap.get("quarter"), sellers=sellers, lines=[_line(s) for s in sellers],
                fundamental_sellers=[s["name"] for s in fundamental],
                note=("mostly mechanical (quant/passive/market-maker) — likely index/flow, not a "
                      "fundamental holder dumping" if not fundamental else
                      "includes fundamental holder(s) reducing"),
                caveat="13F is quarterly & ~45d lagged (long-only, no shorts) — a candidate, not a same-day cause.")
