# Project Lighthouse — Phased Build Plan

**Governing principle:** ship the chapel before funding the cathedral. Each phase has a **gate** —
you do not fund the next phase until the prior one clears its gate. The most expensive, most
differentiated work (language-drift NLP, options/borrow flow, private intel) is deliberately last,
sequenced by *customer pull*, not spec completeness.

**The one non-negotiable, from day one:** point-in-time / no-look-ahead discipline. Build the replay
harness as a first-class constraint in Phase 0 — every feature is computed *as of* a historical
timestamp with zero future data. This is where competitors quietly cheat and where credibility is
won or lost.

---

## Phase 0 — Foundations & the no-look-ahead spine  (~2–4 weeks, mostly reuse)
**Build:** repo/project structure, DB schema, USIO client config, and the **historical replay
harness** (recreate exactly what was knowable at a chosen date/time).
**Reuse from Praxis (shortcuts):**
- Multi-tenant `client_id` isolation, auth/MFA, role-based views — already built.
- The NiceGUI app shell + page framework — CEO/IR/Research views reuse it, don't rebuild UI.
- `market_data` (OHLCV, benchmarks), SEC-filings parsing, peer construction (`peer_prospects`),
  and the 13F holder + CRM datasets — all already in the platform.
**Gate 0:** replay harness provably reproduces a past date with no future leakage (unit-tested).

## Phase 1 — V0.1 Historical Intelligence Engine  (the chapel, ~1 quarter, 1 dev)
**Build (the smallest complete answer to "what happened today?"):**
- Expected/actual/residual with champion/challenger models (naive, static OLS, rolling OLS
  63/126/252) + expected range.
- Residual/anomaly engine — abnormality confidence, residual percentile, volume abnormality.
- Event overlay from the **existing** SEC/company/peer feeds, with the basic Spec-12 timing logic:
  multi-day event windows (CAR t-1…t-10) + the "event published *after* the move began can't explain
  it" flag. (This already handles the common **lag** case.)
- Technician's Model (subset: 21/63/126/252 trend, relative volume, support break, ATR).
- Evidence Fusion v0 (Primary / Contributing / Amplifier / Unexplained) with evidence lineage.
- CEO one-pager + one-click-to-evidence.
- Continuous historical validation across every eligible day (not a cherry-picked 30–50).
**Deliverable:** a demoable USIO "what happened" note over history.
**Gate 1:** on the event stress-test subset, expected-return accuracy + residual stability are
credible, confidence is calibrated, and the CEO note reads like something a smart analyst wrote.
This is also your **demo asset** — use it to test willingness-to-pay before spending more.

## Phase 2 — Shadow Mode + paying pilot  (validate WTP, ~1 quarter)
**Build:** live Shadow Mode (no automated CEO alerts) on USIO + 1–2 more clients; **IR Review Mode**
(the IRO curates before the CEO sees anything); plus the two **cheap-because-you-already-have-the-data,
highest-leverage moat pieces:**
- **Holder-flow / forced-seller detection** — cross-reference the move against the issuer's own 13F
  holder base *in your CRM* ("a top-10 holder is reducing"). No standalone tool can do this. **This is
  the differentiator; build it here, not later.**
- **Sector context** (ties to the Sector-Appetite screen).
**Gate 2 (the commercial gate):** a real small-cap CEO/IRO says *"I would pay for / renew on this."*
**Do not fund Phase 3 until Gate 2 clears.** If it doesn't clear, V0.1 still stands as a platform
differentiator — you've lost a quarter, not a cathedral.

## Phase 3 — Differentiation tail  (sequenced by pull, the expensive/moaty parts)
Fund these **individually**, each only when a paying pilot asks for it:
- **Sell-side language-drift engine** — start rules-based (rating/PT/estimate deltas + first-paragraph
  / conviction-language comparison vs the analyst's own prior notes); add ML only once calibrated.
  Needs the client's *inbound* research (internal-only, no crawling).
- **Private-company competitive intel (Spec 12.5)** — build from news/filings/funding-round data; the
  strongest differentiator because *no IR surveillance tool does it.*
- **Flow & positioning (options gamma, short interest / borrow)** — the most competed, most
  data-expensive lane. Add only if pilots demand it; consider it table-stakes to *match*, not to *win*.
- **Anticipatory / information-leakage detector** (Spec 12 lead effect) + **provisional, revisable
  verdicts** with back-annotation.
**Gate 3:** each tail feature earns its data/eng cost against a specific paying-customer need.

## Phase 4 — Mature production
Automated CEO-alert mode (only after Shadow proves reliability), full confidence calibration,
alert dedup/escalation, client onboarding/offboarding, feed-health/stale-data monitoring, SLAs,
model/data/config versioning at scale.

---

## Critical-path risks (in priority order)
1. **Scope discipline** — the spec is a cathedral; the biggest risk is spending a year before a single
   customer validates. The gates exist to prevent exactly this.
2. **No-look-ahead correctness** — subtle, and fatal to credibility if wrong. Phase 0.
3. **Language-drift reliability** — do not put a shaky NLP verdict in front of a CEO; rules-first.
4. **Flow-data cost** — don't build the wall where the incumbents are already dug in.

## What makes it defensible (build the plan around these)
- Small/micro/nano-cap focus + the **honesty discipline** (abnormality vs explanation confidence,
  "checked but not found," provisional verdicts) — a feature *because* the data is thin.
- **Holder-flow attribution off your own 13F/CRM base** (Phase 2) — structurally impossible for a
  standalone tool.
- **Private-company competitive intel** (Phase 3) — unserved by IR surveillance today.
Treat generic settlement-data surveillance as table-stakes, not the battleground.
