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

### 3. Significance + estimation error — BUILT
Betas are estimated with error (brutal on an illiquid nano-cap). The factor model reports the residual
with a **prediction-interval t-stat** (`resid / se_pred`) so significance accounts for beta estimation
error, and the expected range widens with the out-of-sample leverage. **Multiple testing** is
controlled by `lighthouse/fdr.py`: each day's two-sided p-value (`p = 1 − rarity`) is run through
**Benjamini-Hochberg** over a trailing window (default 252d, q=10%), point-in-time, to hold the False
Discovery Rate among flagged days. The gate does not change the descriptive abnormality label — it
decides whether a day is a genuine **discovery** worth a phone alert vs. an expected tail event, and
`push.maybe_push_verdict` will not buzz a phone on an FDR-gated day. Benjamini-Yekutieli available for
arbitrary dependence. *Measured on USIO: raw ≥1.6σ days ~22/yr → survive FDR ~4/yr (≈80% fewer phone
alerts, keeping only genuine discoveries).* Remaining sub-item: a formal GARCH conditional vol (2) can
replace the EWMA seed.

### 4. Peer-set integrity — BUILT
`lighthouse/peer_health.py` checks the live comp set on the dimensions the onboarding criteria (c) miss:
**LIVE** (delisted/acquired → remove), **SIZE** (EV ≫ issuer → reference, not a median driver),
**LIQUIDITY** ($-ADV too thin to calibrate a multiple), plus surfacing the (c) no-gross-profit-line
verdict. Crucially it **TIERS rather than pass/fails** — an analyst's real comp sheet carries category
names they track but don't model (covering MSFT/ORCL, keeping SAP on the sheet), so a merely-oversized
name is legitimate REFERENCE, not an error; only no-live-data is a true remove. Reuses
`peer_discovery.enrich` + `market_data`. Pure `verdict` unit-tested; cached, run by `peer_install`, and
surfaced as a table in the onboarding checklist. *First run on USIO (issuer EV ~$52M): flagged CSGS +
GDOT STALE (remove), CASS NO-GP, and PAY/PRTH/PSFE/FOUR OVERSIZED → reference — it even caught the PRTH
we'd just added as ~29× too big to drive the median.* (Correlation/market-cap WEIGHTING of the basket
is the remaining sub-item; the factor model already reduced reliance on the basket.)

### 5. Liquidity / microstructure normalization
A −6% move on 0.3× ADV is microstructure noise; on 5× ADV with a tight spread it is information. Fold
**$-volume, Amihud illiquidity, turnover, VWAP deviation** into the residual's weight (not just RVOL as
a side signal), so thin-tape prints don't masquerade as abnormal information.

### 6. Live calibration monitoring — BUILT
`lighthouse/calibration.py` scores the LIVE engine (multi-factor + FDR) over all history as a standing
control, cached and refreshed by the scheduler, surfaced on the Lighthouse page. Three readouts:
**reliability** (abnormality bin → catalyst rate / forward move / persistence, with a monotonicity
check), **alert precision** (of FDR-passing days, % with an identifiable catalyst), and **information
vs noise** (do abnormal days diffuse or revert). The pure scorer (`reliability`) is separated from the
DB fetch and unit-tested. *Honest first read on USIO (623d): catalyst-rate is NOT monotonic in
abnormality (SEC-only coverage is thin — most abnormal moves aren't filing-driven), FDR alerts ~4/yr
at 45% precision, top-decile recall ~17%, persistence ~50% — i.e. USIO is flow-driven, not
information-driven. A truthful, unflattering diagnostic — exactly the point — and the empirical case
for the paid-feed coverage items (7–9).* Note: calibration is an ex-post evaluation that legitimately
uses forward returns to label past days; the live verdict stays strictly point-in-time.

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
