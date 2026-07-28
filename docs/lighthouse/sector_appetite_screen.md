# Feature Spec — Sector-Appetite Screen (Praxis / IRconnect)

## Purpose
Surface institutions with **demonstrated appetite for the issuer's sector/theme that do not yet own
a comp** — the warm prospects the peer-holder crawl structurally misses. The 13F crawl answers "who
owns my peers"; the curated house book answers "who do I know"; this answers **"who wants my kind of
company but hasn't found it yet."** Data-driven, per-client, accretes across clients like the house
book.

## Core logic: Capacity × Fit × Absorbability
For each institution, score against the issuer:

- **Fit (appetite)** — the institution's **% of portfolio in the issuer's sector/theme** (from its
  aggregated 13F). This is the differentiator: it separates a genuine sector specialist from a
  generalist that holds the sector only because it holds everything. Also use the *trend* — is
  sector exposure rising (accumulating) or falling (rotating out)?
- **Capacity** — total equity AUM / sector $ held. Can they own the space at all.
- **Absorbability band (the micro/nano-cap correction)** — the AUM range where a *meaningful*
  position in a name of the issuer's float is (a) material to the manager and (b) absorbable by the
  issuer's liquidity without breaching ownership/liquidity limits. A $500B manager fails this for an
  $85M name; a $300M–$5B concentrated specialist is the sweet spot. Band is a function of the
  issuer's market cap, float, and ADV — computed, not fixed.

Composite = high fit × rising trend × in-band capacity. Rank descending.

## Inputs (mostly already in the platform)
- 13F holdings by institution (already ingested for the holder/peer work).
- A security → sector/theme map (GICS/SIC + a thematic overlay for narrower themes than GICS).
- Issuer market cap / float / ADV (from market_data) to compute the absorbability band.
- The house CRM to attach contacts/relationships to the ranked accounts.

## Method
1. Aggregate each institution's latest 13F into sector exposure (% port by sector) + total equity AUM.
2. Maintain sector-exposure history (2–4 quarters) for the accumulating/rotating trend.
3. For a client, compute the absorbability band from its cap/float/ADV.
4. Score every institution: Fit × Trend × in-band Capacity.
5. **Dedup / suppress** anything already surfaced as a current holder, a peer-owner (13F crawl), or a
   curated target — so the screen only shows *net-new appetite prospects* (same discipline as
   `all_candidates()` in curated_targets).
6. Attach known contacts from the house CRM; flag "no contact yet → email-find candidate."

## Output & integration
- A ranked "Sector-Appetite Prospects" tier in the existing Investors/prospects view, alongside
  peer-owners and curated targets — clearly labeled tier ("Sector appetite", not "holds a comp"), same
  honesty rule: this is *fit evidence*, not *ownership evidence*.
- Each row: institution, sector %, trend arrow, absorbability fit, current position (if any), best
  contact, one-click to the 360 profile.

## Why it's defensible
- Reuses the 13F + CRM data already assembled — near-zero marginal data cost.
- The **absorbability band** is the small/nano-cap-specific piece generic screens (and the user's
  2018 vendor pull) lack — it's what turns 2,000 institutions into an actionable few dozen.
- Accretes into the global house book: an institution scored as a fintech-appetite account for one
  client is a warm lead for the next fintech client onboarded.

## Guardrails
- Sector % is *fit*, never *intent* — an appetite prospect is a hypothesis, not a buyer.
- 13F is 45-day lagged and long-only-ish; flag staleness; it undercounts non-13F holders (foreign,
  <$100M, short). State the coverage limits, don't paper over them.
