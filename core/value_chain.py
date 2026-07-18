"""Value-chain positioning — the two-layer comp framework.

THE PROBLEM THIS SOLVES. An EV/Gross-Profit median is only meaningful across companies with
the SAME business model. Blend business models and the median lies: SARO (an aftermarket
SERVICES / MRO business, ~15% gross margin because it is labour + parts pass-through) looked
"+86% cheap" against a median dragged up by 40-60%-margin parts MANUFACTURERS (HEICO,
TransDigm) that happen to share the word "aerospace". Same sector, different economics, wrong
comp.

THE FIX IS TWO LAYERS, HELD SEPARATE:
  * LAYER 1 — RELATIVE VALUE (narrow): the multiple is computed ONLY across model-matched
    peers — companies in the same value-chain position as the client. For SARO that is the
    aftermarket-services pure-plays (AAR, TAT). Three names including SARO. This is the median
    that goes in a valuation.
  * LAYER 2 — DEMAND CONTEXT (broad): the whole chain — airframe OEMs -> engine OEMs -> parts
    -> aftermarket services -> distribution -> leasing — is shown for context, because every
    layer draws on the same aggregate demand (ultimately aircraft build rates and fleet flight
    hours). You value against Layer 1 and explain against Layer 2.

WHY POSITION MATTERS BEYOND MARGIN. Aftermarket services is driven by the INSTALLED fleet's
flight hours and shop-visit cycles — recurring, higher-visibility, less cyclical than the OEM
order book. So an aftermarket-services name can legitimately trade at a different multiple
than an engine OEM even at the same growth. The demand-beta layer (separate module, planned)
quantifies that; this module does the positioning that layer needs.

DESIGN. `chain` is a free-form slug on each peer record and on the client, so the taxonomy is
not hardcoded to aerospace — a payments client would use its own chain slugs (network /
processor / ISV / merchant). The ONLY generic rule is: model-matched == same chain slug as the
client. Unknown slugs still group and render; they just sort last. A client with no chain set
gets no tight median (graceful no-op) and the existing blended median stands.
"""

# Display order for the chains we've onboarded. Unknown slugs sort after these, alphabetically.
# Ordered upstream -> downstream so a rendered chain reads like the real value chain.
CHAIN_ORDER = [
    "airframe_oem", "engine_oem", "parts", "aftermarket_services",
    "distribution", "leasing",
    # payments chain (USIO and future fintech tenants)
    "network", "processor", "isv", "merchant",
]

CHAIN_LABELS = {
    "airframe_oem": "Airframe OEM",
    "engine_oem": "Engine OEM",
    "parts": "Parts / components (mfg)",
    "aftermarket_services": "Aftermarket services / MRO",
    "distribution": "Distribution / used material",
    "leasing": "Leasing / asset owner",
    "network": "Card network",
    "processor": "Payment processor",
    "isv": "ISV / software",
    "merchant": "Merchant / end user",
}


def label(slug):
    if not slug:
        return "Unclassified"
    return CHAIN_LABELS.get(slug, slug.replace("_", " ").title())


def _order_key(slug):
    try:
        return (0, CHAIN_ORDER.index(slug))
    except ValueError:
        return (1, slug or "~")


def group_by_chain(rows):
    """[(chain_slug, label, [rows])] in upstream->downstream order. `rows` are peer dicts that
    carry a 'chain' key (missing/None -> Unclassified)."""
    buckets = {}
    for r in rows:
        buckets.setdefault(r.get("chain") or "", []).append(r)
    ordered = sorted(buckets.items(), key=lambda kv: _order_key(kv[0]))
    return [(slug or None, label(slug), rs) for slug, rs in ordered]


def model_matches(client_chain, peers):
    """Peers in the SAME value-chain position as the client — the tight relative-value set.
    Empty when the client has no chain set (then callers fall back to the blended median)."""
    if not client_chain:
        return []
    return [p for p in peers if (p.get("chain") or "") == client_chain]
