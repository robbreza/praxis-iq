# Roadmap — Weekly EPS / Management Nowcast (next major item)

**Status:** roadmap / not built. The flagged next major item after V0.1 + Shadow Mode.
**Origin:** the user's own IR/industry practice — in a prior corporate/industry role he gave the CEO a
**weekly EPS forecast built from internal operating metrics**. The insight that produced it: daily
price action tells you *what happened*; a weekly, metrics-driven forecast tells you *where the
business is actually tracking vs expectations* — which is more telling and more actionable.

## What it is
A weekly **management nowcast**: where the current quarter's **revenue / EPS** is tracking (from the
issuer's internal operating metrics + external signals) **versus where the street consensus is
drifting** — surfaced on the same weekly cadence as the Lighthouse drift digest.

Two halves:
1. **Internal nowcast** — a forward revenue/EPS estimate for the live quarter, built from the client's
   own operating KPIs (volumes, bookings, pipeline, churn, pricing, run-rate) fed in weekly.
2. **Consensus-drift tracker** — where the street is moving: estimate revision direction, dispersion,
   tone, analyst support state, and the "earnings bar" (already sketched in Specs 6-8 of the master
   Lighthouse architecture). The deliverable is the **gap**: "internal read ~$X; street drifting
   toward $Y; here's the delta and why."

## Why it fits Lighthouse / Praxis
- Praxis **already computes consensus/estimates** (`core/market_data.consensus_rev`, `guidance_engine`)
  and the sell-side language-drift / earnings-bar concepts live in the master spec (6-8).
- Lighthouse **already has the weekly cadence and the "drift" framing** (`lighthouse/weekly.py`) — this
  extends "what's happening to the **stock**" into "what's happening to the **business vs
  expectations**."
- It is the piece that turns an **IR tool into a CFO tool** — a different, arguably larger buyer.

## What it needs (why it's later, not now)
- **New input: the client's internal operating metrics.** This is the gating dependency — it requires a
  client relationship deep enough to feed KPIs weekly (a pilot customer, not a prospect). No public
  data substitutes for it.
- A nowcast model per issuer (metric → revenue/EPS mapping), calibrated on the client's own history.
- The consensus-drift tracker productized from the estimates/sell-side work.

## Sequencing
Gate this behind a **V0.1 paying pilot** (a CEO/CFO already using the daily/weekly Lighthouse read and
willing to share internal metrics). It is a distinct product from the price-attribution engine — build
it when a customer pulls for it, not to complete the spec. Pair it with the daily/weekly price read and
you cover both questions a management team lives on: *what is the market doing to us* and *where is the
quarter actually landing vs the bar.*
