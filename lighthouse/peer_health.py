"""Lighthouse — peer-set health check (Spec 13.4).

The comp set decays: names get acquired, delisted, taken private, or drift out of the size band (the
stale FI/Fiserv row; FPAY delisted; DFS/CTLP gone). The onboarding checklist already tests criterion
(c) — comparable revenue basis (no gross-profit line = bank accounting). This adds the dimensions that
let a dead row survive: is the peer LIVE, SIZE-appropriate, and LIQUID enough to calibrate a multiple.

The verdict TIERS rather than pass/fails — an important distinction from an analyst's real comp sheet.
A sell-side comp sheet carries names the analyst tracks as a category but doesn't actively model
(covering MSFT/ORCL but keeping SAP on the sheet): those are legitimate REFERENCE peers, not errors. So
a name that's merely too big isn't "bad" — it's reference (excluded from the median, kept for context).
Only a name with no live data is a true remove.

  STALE     — no live market data (delisted/acquired) → REMOVE from the median
  NO-GP     — no gross-profit line (financial/bank accounting) → fails comparable basis (c)
  OVERSIZED — EV ≫ the issuer's → keep as REFERENCE, not a median driver
  THIN      — too illiquid to calibrate a multiple cleanly
  HEALTHY   — live · size-appropriate · comparable basis

Reuses core.peer_discovery.enrich (EV / gross margin / gp-status / current-filer) and core.market_data
(liquidity). Pure `verdict` core is separated and unit-tested; result cached, run by peer_install and
surfaced in the onboarding checklist.
"""
from __future__ import annotations
import logging
from collections import Counter

_OVERSIZE_X = 25.0          # EV more than this multiple of the issuer's → reference, not median
_MIN_DOLLAR_ADV = 500_000   # below ~$0.5M/day, a peer's print is too thin to trust for a multiple


def verdict(current: bool, ev_m, gp_status, issuer_ev_m, dollar_adv, tier=None) -> tuple[str, str]:
    """Pure health verdict for one peer. `tier` is its current tier (a 'reference' name is exempt from
    the OVERSIZED downgrade — it's already reference by design)."""
    if not current or not ev_m:
        return "STALE", "no live market data — delisted/acquired; remove from the median"
    if gp_status == "no_gross_profit_line":
        return "NO-GP", "no gross-profit line (financial/bank accounting) — fails comparable basis (c)"
    if issuer_ev_m and ev_m and (ev_m / issuer_ev_m) > _OVERSIZE_X and tier != "reference":
        return "OVERSIZED", f"~{ev_m / issuer_ev_m:.0f}× the issuer's EV — keep as reference, exclude from the median"
    if dollar_adv is not None and dollar_adv < _MIN_DOLLAR_ADV:
        return "THIN", f"~${dollar_adv / 1e6:.2f}M/day traded — too illiquid to calibrate a multiple cleanly"
    return "HEALTHY", "live · size-appropriate · comparable basis"


def _dollar_adv(snap: dict):
    vol = (snap or {}).get("avg_volume_10d") or (snap or {}).get("volume")
    px = (snap or {}).get("last_price")
    return (vol * px) if (vol and px) else None


def assess(client_id="usio", issuer=None) -> dict:
    """Run the health check across the client's comp set (CP()). Best-effort."""
    try:
        from config.client_config import CP, CT
        from core import peer_discovery, market_data
        issuer = issuer or CT("ticker")
        peers = CP() or []
        iev = (market_data.live_ev(issuer) or {}).get("enterprise_value")
        issuer_ev_m = (iev / 1e6) if iev else None
        enr = {r["ticker"]: r for r in peer_discovery.enrich([p["ticker"] for p in peers])}
        rows = []
        for p in peers:
            r = enr.get(p["ticker"], {})
            adv = _dollar_adv(market_data.get_snapshot(p["ticker"]))
            v, note = verdict(bool(r.get("current")), r.get("ev_m"), r.get("gp_status"),
                              issuer_ev_m, adv, tier=p.get("tier"))
            rows.append(dict(ticker=p["ticker"], name=r.get("name") or p.get("name"), tier=p.get("tier"),
                             live=bool(r.get("current")), ev_m=r.get("ev_m"), gross_margin=r.get("gross_margin"),
                             gp_status=r.get("gp_status"), analysts=r.get("analysts"),
                             dollar_adv=adv, verdict=v, note=note))
        return dict(issuer=issuer, issuer_ev_m=issuer_ev_m, peers=rows,
                    summary=dict(Counter(x["verdict"] for x in rows)),
                    remove=[x["ticker"] for x in rows if x["verdict"] == "STALE"],
                    retier=[x["ticker"] for x in rows if x["verdict"] == "OVERSIZED"],
                    review=[x["ticker"] for x in rows if x["verdict"] in ("NO-GP", "THIN")])
    except Exception as e:
        return {"error": repr(e)}


_CACHE_KEY = "lighthouse_peer_health.json"


def refresh_cache(client_id="usio", issuer=None) -> dict:
    c = assess(client_id, issuer)
    try:
        from core import db
        if not c.get("error"):
            db.save_json(_CACHE_KEY, c, client_id=client_id)
    except Exception:
        logging.getLogger(__name__).warning("lighthouse peer_health cache write failed", exc_info=True)
    return c


def load_cache(client_id="usio"):
    try:
        from core import db
        return db.load_json(_CACHE_KEY, None, client_id=client_id)
    except Exception:
        return None


def render(c: dict) -> str:
    if not c or c.get("error"):
        return f"Peer health unavailable: {(c or {}).get('error')}"
    L = [f"Comp-set health — {c['issuer']} (issuer EV ~${(c.get('issuer_ev_m') or 0):.0f}M)", "=" * 48,
         "  " + " · ".join(f"{k}:{v}" for k, v in c["summary"].items())]
    for r in c["peers"]:
        L.append(f"  {r['ticker']:<6} {r['verdict']:<9} {r['note']}")
    if c["remove"]:
        L.append(f"\nREMOVE (no live data): {', '.join(c['remove'])}")
    if c["retier"]:
        L.append(f"→ REFERENCE (oversized): {', '.join(c['retier'])}")
    return "\n".join(L)
