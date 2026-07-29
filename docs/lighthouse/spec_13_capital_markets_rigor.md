# Spec 13 — Capital-Markets Rigor (hardening the abnormality/attribution core)

**Status:** in progress. Item 1 (multi-factor model) building now; 2–6 sequenced behind it; 7–11 gated
behind a paying pilot (paid data).
**Why:** Lighthouse's entire value rests on ONE number — the *unexplained residual* and its
*abnormality*. A CFA charterholder or a professional desk will interrogate that number on two axes:
is it **rigorous** (defensible methodology) and is it **complete** (were enough causes checked before
calling a move "unexplained"). Today's champion (Spec 1, `attribution.market_peer_model`) is an honest
but thin **2-factor OLS** — issuer ~ small-cap market + equal-weight peer basket. That is not enough to
call a residual "stock-specific." This spec hardens it to a measure the best market professionals would
trust, without inventing data.

Standing rule (unchanged): point-in-time / no-look-ahead; abnormality confidence separate from
explanation confidence; "found vs checked-but-not-found"; never assert causation the evidence doesn't
support.

---

## A. RIGOR — make the residual defensible (data we already have)

### 1. Multi-factor risk model (the linchpin) — BUILDING NOW
Replace the 2-factor regression with a decomposition against a proper, low-collinearity factor set
built from liquid ETF proxies (fetched the same way as SPY/IWM today), expressed as **factor spreads**
so the style factors aren't swamped by the market factor:

| Factor | Construction (daily returns) | Captures |
|---|---|---|
| **MKT** | SPY | broad market beta |
| **SMB** (size) | IWM − IWB | small-cap premium (core for a nano-cap) |
| **HML** (value) | IWD − IWF | value vs growth |
| **MOM** | MTUM − SPY | momentum tilt |
| **SEC** (sector) | IPAY − SPY | payments/fintech factor (less noisy than 6 hand-picked peers) |
| **RATE** | IEF | rate sensitivity (payments = consumer + rate) |

Model, fit on the trailing `window` days ending **t-1** (strictly prior):

```
expected_t = α + Σ βᵢ · factorᵢ,t
residual_t = actual_t − expected_t        # the genuinely stock-specific move
```

*Why #1:* a "−4% idiosyncratic residual" from the 2-factor model may just be the value or small-cap
factor selling off market-wide. Only after stripping **all priced common factors** is the remainder
defensibly stock-specific. Parsimony matters on a 126-day window with a thin name — 6 spread factors
(~21:1 obs:param) is the default; challengers (Ridge/ElasticNet, other windows) plug in via the same
interface and are chosen on the validation set, never by assumption.

**Deliverables:** `lighthouse/factors.py` (factor construction), `lighthouse/factor_model.py` (rolling
multi-factor OLS with loadings, in-window R², residual, residual standard error → t-stat). Validated
against the 2-factor champion on USIO: how much *more* of each move is attributed to common factors
(higher R²), and which residuals shrink to noise vs. survive as real.

### 2. Conditional-volatility standardization
Abnormality is currently a static historical residual percentile. Volatility clusters, so standardize
the residual by its **conditional vol** (EWMA / GARCH(1,1)) → a regime-aware **z-score**: a −3%
residual is a 3σ event in a calm tape and noise in an earnings-season high-vol tape. Abnormality then
reads off the standardized magnitude, not a static distribution. *(First cut — EWMA — ships with #1.)*

### 3. Significance + estimation error
Betas are estimated with error (brutal on an illiquid nano-cap). Report the residual with a **t-stat /
confidence band**, widen the band when factor loadings are uncertain, and control **multiple testing**
(scanning many days inflates tail false-positives — apply an FDR/Benjamini-Hochberg gate to daily
alerts).

### 4. Peer-set integrity
The hand-picked basket (RPAY, PSFE, PAY, CASS, GDOT, EVTC) has stale/suspect names (observed PAY/PSFE
data oddities — reverse splits, near-delisting). Validate peers are **live and liquid**, weight by
correlation/market-cap (not equal-weight), and re-derive periodically. The factor model's `SEC` factor
(IPAY) reduces reliance on the fragile basket; the basket stays in the event/holder lenses with a
health check.

### 5. Liquidity / microstructure normalization
A −6% move on 0.3× ADV is microstructure noise; on 5× ADV with a tight spread it is information. Fold
**$-volume, Amihud illiquidity, turnover, VWAP deviation** into the residual's weight (not just RVOL as
a side signal), so thin-tape prints don't masquerade as abnormal information.

### 6. Live calibration monitoring
Validation ran once (624 days). Make it a **standing control**: does "90th-percentile abnormal" map to
a real catalyst ~90% of the time? Track the **settle rate** (how often "unexplained" is later explained
by a lagged catalyst — Spec 12 revisable verdicts) and publish a reliability diagram. A miscalibrated
engine is a known, monitored state — not a silent one.

---

## B. COVERAGE — shrink "unexplained" honestly (mostly paid feeds; pilot-gated)

7. **Short interest / borrow / days-to-cover** — squeezes and borrow-driven moves dominate this cap
   range. Highest-value coverage add. *(Spec: currently "Phase 3, not wired.")*
8. **Options / dealer positioning** — gamma exposure, unusual options volume, IV/skew, pinning.
9. **Analyst revisions + non-SEC news** — PT/rating changes, estimate revisions, wire catalysts, and
   competitor/customer news the peer model should ingest.
10. **Macro sensitivity** — on a CPI/Fed day, decompose macro beta (rates/credit/consumer-discretionary)
    vs. stock-specific.
11. **Intraday timing signature** — daily bars hide *where* the move happened: gap/open (overnight
    news) vs. close (index/MOC flow). Diagnostic, cheap if intraday bars are available.

---

## Sequencing
- **Phase 1 (now, no new data, max credibility):** items 1–6 — pure methodology on data we own. Turns
  the residual from "a 2-factor leftover" into a **risk-adjusted, regime-aware, significance-tested
  abnormal return.** This is the lock-down.
- **Phase 2 (pilot-funded):** items 7–11 need paid feeds ($1–15k/mo); gate behind a paying client and
  keep the "checked-but-not-found" honesty explicit until then.
