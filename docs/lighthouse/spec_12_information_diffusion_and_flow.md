# Specification 12 — Information Diffusion & Flow

**Status:** proposed addendum to the locked Lighthouse architecture (Specs 01–11).
**Motivation:** Specs 01–11 attribute a move as a **same-day, point-in-time** residual. But
information does not price in on a single day — it diffuses, sometimes *before* the public event
(lead) and usually *after* it (lag). A single-day residual therefore conflates *"the market hasn't
reacted yet"* with *"there is no cause,"* and will systematically dump both the lagged and the
anticipatory cases into **Unexplained** — on exactly the days a CEO most wants an answer.

**Core concept — information state.** Stop treating events as instantaneous. Every catalyst carries
a state: **latent** (exists, not yet priced) → **diffusing** → **priced** → **stale**. The features
below make that state observable and attributable.

---

## 12.1 Multi-day event-window attribution — the LAG
Attribute today's residual not only to today's events but to a **decaying contribution from prior
N-day catalysts.** This is documented post-event drift (PEAD is the canonical case; slow diffusion is
*stronger* in thinly-covered small/micro-caps — Lighthouse's core segment).
- Compute cumulative abnormal return (CAR) over t-1…t-10 windows.
- Each open catalyst carries a decay curve; today's residual can be partly assigned to it.
- Output example: *"~60% of today's −5% is the market still absorbing Tuesday's guidance cut."*
Turns "unexplained today" into "explained, with a lag."

## 12.2 Anticipatory / information-leakage detector — the LEAD
When a move has **no confirmed public catalyst but a scheduled event is near** (earnings, conference,
lockup expiry, index rebalance, known contract/FDA date), raise the prior that the move is
**anticipatory**, not unexplained. Signature lives in microstructure: pre-event volume, options
skew/OI build, short-interest and borrow-cost changes ahead of the date. Label *"possible anticipatory
move — elevated pre-event positioning"*; in replay, **retro-confirm** whether the later event
validated it. This is the "unknown information" case made explicit.

## 12.3 Flow & positioning engine — the mechanical causes a price/peer/event model can't see
For a small-cap this is frequently **the actual answer**, and Specs 01–11 are blind to it:
- **Options / dealer gamma** — squeezes and hedging unwinds move thin names with no news.
- **Short interest, borrow availability & fee spikes** — squeezes, forced covers.
- **Passive / mechanical flow** — Russell rebalance, index add/delete, ETF create/redeem.
- **Forced sellers / holder distress** — a top-10 holder liquidating or redeeming.
**Praxis moat:** the last item cross-references the issuer's **own 13F holder base in the CRM** —
"the move coincides with a large holder reducing." No standalone tool can produce that. Build this
piece early; treat generic settlement-data surveillance as table-stakes, not the battleground.

## 12.4 Provisional, revisable verdicts — makes lead/lag honest
A same-day verdict is a first draft. Issue verdicts as **provisional**, with an explicit
re-evaluation trigger, and **back-annotate** the historical record when the lagged catalyst surfaces:
*"T+0: unexplained / high abnormality / flagged; T+2: reclassified → delayed reaction to the Tuesday
8-K."* Specs already provide evidence lineage, versioning and no-silent-overwrites — this adds an
explicit **verdict lifecycle** (draft → revised → settled) and an "explanation half-life."

## 12.5 Private-company competitive intelligence (small/nano-cap correction)
The capital markets Lighthouse models are *public*, but a public micro-cap competes for **revenue**
against private companies — some larger than the issuer — whose news flow (funding rounds, product
launches, customer wins, exec hires, expansions, layoffs) is a real fundamental driver yet is invisible
because "they're not public." Ignoring that half of the competitive landscape is fundamentally wrong.
- Maintain, per issuer, a **private competitor set** (from the issuer's own 10-K competition section,
  industry taxonomy, and the issuer's stated markets) alongside the public peer set.
- Ingest private-company news: funding rounds (a well-funded private entrant is a demand/pricing
  threat), product/customer announcements, M&A, leadership, capacity moves.
- Feed it into Event Intelligence as **competitive context** — usually a *Contributing/Coincident*
  factor and a narrative input, not a same-day price trigger, but essential to "what is actually
  happening to this business." Differentiator: **no IR surveillance tool does this.**

---

## Where it plugs into Specs 01–11
- **Event Intelligence** gains event *windows* + information-state (latent/diffusing/priced/stale) and
  the private-competitor feed.
- **Evidence Fusion** gains two driver classes: **Diffusing Driver** and **Anticipatory / Leaked**.
- **Flow** becomes a sixth analytical lens alongside the five existing.
- **Validation** already supports back-annotation via no-look-ahead historical replay.

## Methodological caution (the reason for all of the above)
A single-day residual cannot distinguish *"not reacted yet"* from *"no cause."* 12.1 and 12.2 are what
separate them — the difference between a tool that answers "what happened today" and one that says
"we don't know" precisely when it matters most.
