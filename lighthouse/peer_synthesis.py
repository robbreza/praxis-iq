"""Lighthouse — peer-tier synthesis (Spec 14 capstone).

A naive peer analysis picks one list and calls it "peers." The three revealed-peer lenses show that's
wrong: who USIO TRADES with, who research BRACKETS it with, and who we DEFINED are three different
concepts that barely intersect. This synthesizes them into one view so the distinction is legible:

  * TRADING peers      (co-movement + co-ownership) — what actually moves the stock;
  * NARRATIVE peers    (sell-side coverage)         — the story/valuation comps it's told alongside;
  * FUNDAMENTAL peers  (our/company-defined)        — competitors for a valuation comp.

Pure `synthesize` (reads the cached lens outputs) is separated from the cache load and unit-tested.
"""
from __future__ import annotations

# Co-movement categories that are indices/ETFs, not individual-company peers.
_NON_STOCK = ("small-cap idx", "small growth", "small value", "broad market",
              "payments ETF", "fintech ETF", "regional banks")


def synthesize(comovement: dict, coownership: dict, coverage: dict, defined_peers: list[str]) -> dict:
    defined = list(defined_peers or [])
    cm, co, cv = comovement or {}, coownership or {}, coverage or {}

    trading = [t["ticker"] for t in cm.get("top_correlates", [])
               if t.get("category") not in _NON_STOCK][:6]                # individual-stock co-movers
    top_cat = (cm.get("top_correlates") or [{}])[0].get("category")
    cm_r2, base_r2 = cm.get("sparse_r2"), cm.get("defined_basket_r2")
    narrative = [p["ticker"] for p in cv.get("payments_coverage_peers", [])]
    fundamental = list(defined)

    st, sn, sfd = set(trading), set(narrative), set(fundamental)
    overlaps = dict(all=sorted(st & sn & sfd), trading_narrative=sorted(st & sn),
                    narrative_fundamental=sorted(sn & sfd), trading_fundamental=sorted(st & sfd))

    insights = []
    if cv.get("new_payments_peers"):
        insights.append(f"Narrative peers the sell-side brackets that aren't in your defined set: "
                        f"{', '.join(cv['new_payments_peers'])} — candidates to add to the comp set.")
    if cv.get("defined_not_covered"):
        insights.append(f"Defined peers USIO's own analysts don't even cover: "
                        f"{', '.join(cv['defined_not_covered'])}.")
    if co.get("n_focused") is not None and co.get("n_holders"):
        insights.append(f"Ownership: only {co['n_focused']} of {co['n_holders']} holders are "
                        f"concentrated/active — USIO is owned via flow, not a fundamental peer complex.")
    if not overlaps["all"]:
        insights.append("No company is a peer by all three definitions — trading, narrative, and "
                        "fundamental peer groups are genuinely distinct here.")

    tiers = [
        dict(key="trading", label="TRADING peers", subtitle="how USIO actually moves",
             members=trading,
             note=(f"Dominant co-mover: {top_cat or 'small-cap complex'}. Even the data-selected set explains "
                   f"only ~{(cm_r2 or 0)*100:.0f}% (vs your basket ~{(base_r2 or 0)*100:.0f}%) — USIO trades "
                   f"largely on its own, on small-cap flow.")),
        dict(key="narrative", label="NARRATIVE peers", subtitle="who the sell-side brackets it with",
             members=narrative,
             note="The payments story it's told alongside; whose upgrade lands in the same inboxes."),
        dict(key="fundamental", label="FUNDAMENTAL peers", subtitle="who you / the company defined",
             members=fundamental, note="Competitors for a valuation comp."),
    ]
    return dict(tiers=tiers, overlaps=overlaps, insights=insights,
                headline=("Three peer groups, "
                          + (f"overlapping only on {', '.join(overlaps['narrative_fundamental'])} "
                             f"(narrative ∩ fundamental)" if overlaps["narrative_fundamental"]
                             else "with no shared name")
                          + " — trading ≠ narrative ≠ fundamental."))


def load_and_synthesize(client_id="usio") -> dict:
    try:
        from lighthouse import comovement, coownership, coverage
        from lighthouse.config.usio import USIO
        return synthesize(comovement.load_cache(client_id), coownership.load_cache(client_id),
                          coverage.load_cache(client_id), USIO["business_peers"])
    except Exception as e:
        return {"error": repr(e)}


def render(s: dict) -> str:
    if not s or s.get("error"):
        return f"Peer synthesis unavailable: {(s or {}).get('error')}"
    L = ["Peer intelligence — three definitions of 'peer'", "=" * 48, s.get("headline", ""), ""]
    for t in s["tiers"]:
        L.append(f"{t['label']} ({t['subtitle']}): {', '.join(t['members']) or '—'}")
        L.append(f"   {t['note']}")
    L += ["", "Insights:"] + [f"  · {i}" for i in s["insights"]]
    return "\n".join(L)
