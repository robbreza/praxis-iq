"""Lighthouse — coverage-overlap revealed peers (Spec 14c).

The third definition of "peer": who the SELL-SIDE brackets USIO with. Analysts covering USIO also cover
___ — the Street's revealed peer set, from the analyst-coverage network we already track
(core.analyst_coverage). Distinct in KIND from the other lenses: co-movement/co-ownership reveal the
TRADING peer group (how USIO actually moves / who holds it); coverage reveals the NARRATIVE / valuation
peer group (who research brackets it with, whose upgrade lands in the same inboxes).

Method: split covering analysts into sector SPECIALISTS (coverage concentrated in payments/fintech) vs
GENERALISTS, aggregate the other tickers they cover, flag which are payments/fintech, and diff against
our defined peer set — surfacing coverage peers we DIDN'T define and defined peers USIO's analysts don't
even cover. Internal data, so this is a cheap live compute (no EDGAR/paid feed). The pure `aggregate`
core is separated and unit-tested.
"""
from __future__ import annotations
import logging

_PAY_KEYS = ("payment", "fintech", "ach", "payfac", "lto", "processing", " card")


def _is_payments(sector: str) -> bool:
    return any(k in (sector or "").lower() for k in _PAY_KEYS)


def aggregate(coverage: dict, defined_peers: list[str], issuer="USIO") -> dict:
    """Pure core. `coverage` = {analyst_key: {analyst, firm, coverage:[{ticker,name,sector,relevance}]}}."""
    defined_peers = defined_peers or []
    analysts, ticker_agg = [], {}
    for a in (coverage or {}).values():
        cov = a.get("coverage") or []
        pay_n = sum(1 for s in cov if _is_payments(s.get("sector")))
        specialist = len(cov) > 0 and (pay_n / len(cov)) >= 0.5
        analysts.append(dict(analyst=a.get("analyst"), firm=a.get("firm"),
                             n_coverage=len(cov), payments_n=pay_n, specialist=specialist))
        for s in cov:
            tk = s.get("ticker")
            if not tk or tk == issuer:
                continue
            rec = ticker_agg.setdefault(tk, dict(ticker=tk, name=s.get("name"), sector=s.get("sector"),
                                                 analysts=[], relevance=[], payments=_is_payments(s.get("sector"))))
            rec["analysts"].append(a.get("analyst"))
            rec["relevance"].append(s.get("relevance") or 0)
    peers = [dict(ticker=r["ticker"], name=r["name"], sector=r["sector"], analysts=len(r["analysts"]),
                  analyst_names=r["analysts"], payments=r["payments"], defined_peer=(r["ticker"] in defined_peers),
                  avg_relevance=(sum(r["relevance"]) / len(r["relevance"]) if r["relevance"] else 0.0))
             for r in ticker_agg.values()]
    peers.sort(key=lambda p: (-int(p["payments"]), -p["analysts"], -p["avg_relevance"]))  # payments peers first
    pay_peers = [p for p in peers if p["payments"]]
    covered_defined = [p["ticker"] for p in peers if p["defined_peer"]]
    return dict(n_analysts=len(analysts), n_specialists=sum(1 for a in analysts if a["specialist"]),
                analysts=analysts, coverage_peers=peers, payments_coverage_peers=pay_peers,
                new_payments_peers=[p["ticker"] for p in pay_peers if not p["defined_peer"]],
                defined_covered=covered_defined,
                defined_not_covered=[t for t in defined_peers if t not in covered_defined])


def compute(client_id="usio", issuer="USIO") -> dict:
    try:
        from core.analyst_coverage import get_coverage
        from lighthouse.config.usio import USIO
        cov = get_coverage(client_id)
        out = aggregate(cov, USIO["business_peers"], issuer=issuer)
        out["issuer"] = issuer
        return out
    except Exception as e:
        return {"error": repr(e)}


_CACHE_KEY = "lighthouse_coverage.json"


def refresh_cache(client_id="usio", issuer="USIO") -> dict:
    c = compute(client_id, issuer)
    try:
        from core import db
        if not c.get("error"):
            db.save_json(_CACHE_KEY, c, client_id=client_id)
    except Exception:
        logging.getLogger(__name__).warning("lighthouse coverage cache write failed", exc_info=True)
    return c


def load_cache(client_id="usio"):
    try:
        from core import db
        return db.load_json(_CACHE_KEY, None, client_id=client_id)
    except Exception:
        return None


def render(c: dict) -> str:
    if not c or c.get("error"):
        return f"Coverage overlap unavailable: {(c or {}).get('error')}"
    L = [f"Market-revealed peers via sell-side coverage — {c.get('issuer')}", "=" * 52,
         f"{c['n_analysts']} covering analysts · {c['n_specialists']} payments/fintech specialist(s)"]
    for a in c["analysts"]:
        role = "specialist" if a["specialist"] else "generalist"
        L.append(f"  {a['analyst']} ({a['firm']}): {a['n_coverage']} names, {a['payments_n']} payments [{role}]")
    L.append("\nCo-covered — the Street's peer bracket for USIO (payments first):")
    for p in c["coverage_peers"][:10]:
        tags = []
        if p["payments"]:
            tags.append("payments")
        tags.append("our peer" if p["defined_peer"] else "NEW")
        L.append(f"  {p['ticker']:<6} {p['name']:<22} {p['sector']:<26} [{', '.join(tags)}]")
    L += ["",
          f"NEW payments peers the sell-side brackets that we didn't define: {', '.join(c['new_payments_peers']) or '—'}",
          f"Our defined peers USIO's analysts don't even cover: {', '.join(c['defined_not_covered']) or '—'}"]
    return "\n".join(L)
