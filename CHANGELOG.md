# Changelog — Praxis Point IR Platform (NiceGUI app)

Running log of feature work on `app_nicegui.py` + `page_modules_nicegui/`.
Dates are absolute. Newest first.

---

## 2026-07-18 — Console: editable client_id + in-Console edit/deactivate (Phase 3, start)

- **Add-client form:** `Client ID` is now an explicit editable field (blank still derives from
  the ticker) — so the permanent tenant key isn't forced to match the ticker.
- **Edit / deactivate a client** from the Console: an edit pencil on each portfolio card opens a
  dialog to change name/ticker/exchange/email domain, or uncheck Active to hide the tenant
  everywhere. Saves as a partial DB overlay (deep-merged onto the seed, so rich config survives —
  verified: editing USIO's domain keeps Paul Manley's IR contact + guidance_policy). Guards block
  deactivating the default client or the last active one. client_id stays immutable.
- **Domain hygiene:** a leading `www.` is now stripped from the email domain in both add and edit
  (a `www.ceva.com` entry was producing `irconnect@www.ceva.com`).

---

## 2026-07-18 — Praxis Point Console, Phase 2 (onboard a client without a deploy)

The SaaS threshold: tenant definitions moved from code to DATA, and the Console can now onboard a
client from a form.

- **DB-backed client store.** New `clients` table (unscoped — it IS the client list, like `users`)
  holding a JSON `record` per tenant; `core/client_store.py` is the CRUD. The in-code registry
  literal became `_CODE_SEED`; `CLIENT_REGISTRY` is a live dict that `reload_registry()` rebuilds
  IN PLACE by deep-merging the DB `clients` rows onto the seed (DB wins per field, DB-only clients
  added, inactive hidden). Every existing caller (`get_client`/`CT`/iteration/membership) is
  unchanged — the whole point of the containment. A startup hook overlays the DB before anything
  reads the registry.
- **Add-client form** on the Console (staff-only dialog): company name, ticker, exchange, email
  domain → writes the record, reloads the registry, and seeds the tenant's two standard IR logins
  — all live, no code change, no redeploy. New tenant appears on the portfolio grid immediately
  (honest "—"/attention until its data is pulled).
- **Mail-gateway identity (the "IRconnect@company.com" fix).** `email_domain` is now a
  first-class client field; the IRconnect address derives as `irconnect@<email_domain>`. Backfilled
  usio (`usio.com`) and saro (`standardaero.com`, whose `ir_contact` had been empty), and the
  add-client form captures it for every new tenant.

Deferred to Phase 3: in-Console client EDIT/deactivate, and per-client data-ops refresh controls.

---

## 2026-07-18 — Praxis Point Console, Phase 1 (the operator surface above the tenants)

Formalized the two surfaces the product actually has. Until now "Praxis Point management" was
two orphaned bolt-ons in the client header (the tenant switcher + the user-admin icon); there
was no vantage point ABOVE the tenants. Phase 1 adds a staff-only **Console** — additive only,
no schema change, no registry migration.

- **Two surfaces, one app.** `/console` (staff-only) is the operator home; `/` + the existing nav
  is the tenant WORKSPACE. Routing now enforces the model: staff land on `/console` at login and
  when they haven't picked a client yet (`/` always means "inside a tenant"); client users skip
  the Console entirely and land in their one workspace. Drilling into a client card sets the
  active tenant and drops into the workspace; a `grid_view` header button goes back up.
- **Portfolio home.** One card per client from `core/portfolio.py` — cheap, CACHED-ONLY reads
  (no network fan-out): live-cached price/%Δ, next earnings + days-out, curated consensus, 13F
  holder count + freshness, and amber attention chips (earnings ≤14d, 13F missing/stale, no
  consensus). It honestly surfaces gaps — e.g. SARO shows "no consensus" because its registry
  has no `q2_consensus_rev`.
- **`core/portfolio.py`** is UI-free and client_id-parameterized (summarizes any tenant without
  switching the session), so it's unit-tested headlessly. Deliberately reads the registry
  consensus directly rather than `market_data.consensus_rev()` — that resolves the ticker from
  the active-client ContextVar (not its arg) and its blank path hits the network.

Deferred to Phase 2+: registry → DB + an add-client form (the real "onboard without a deploy"
threshold), and per-client data-ops refresh controls. No "Add client" placeholder shipped yet,
by choice.

---

## 2026-07-18 — Auth + the account-type axis (praxis_staff vs client_user)

The platform gained a real access boundary. Until now it was open on its port with a code-defined
tenant switcher — right operator model, but no authentication and no notion of a *client* user.
Added on branch `auth-account-axis` (off `q2-earnings-script`; not merged, not pushed).

### Two axes, deliberately separate
- **`account_type` — the tenant boundary.** `praxis_staff` sees every tenant and can switch between
  them; `client_user` is pinned to ONE home tenant, read-only, switcher hidden. This is what makes
  the app a real multi-tenant SaaS rather than an internal console.
- **`role_key` — the persona** (IR/CEO/CFO/CRO/Legal). Pre-existing `ROLE_PERMISSIONS`; unchanged.

### Two security guarantees, enforced server-side
1. **Tenant isolation.** The tenants a session may touch come from `auth.allowed_clients(user)` —
   derived from the authenticated user, NEVER trusted from the `active_client_id` cookie.
   `_bind_active_client()` re-asserts this clamp every render; a client_user forging the cookie to
   another tenant is clamped back to its home tenant.
2. **Read-only at the data layer.** A client_user session is marked read-only in `core.db`, and
   `save_json` raises `PermissionError` regardless of UI gating. `core/ui_context` mirrors it so
   mutating controls never render for a client_user (belt and suspenders).

### The pieces
- **`core/auth.py`** — stdlib PBKDF2-HMAC-SHA256 (240k iters; no new dependency), `users` table,
  `authenticate` (dummy-verify on unknown users, no enumeration side channel), the account-axis
  helpers, and seeding: `seed_admin_from_env()` (first-boot only) + `seed_client_users()` (roster
  participants — IR contact + executives, analysts excluded — plus a per-tenant
  `praxispointclient@<ticker>` default; all forced to change password on first sign-in).
- **`app_nicegui`** — `/login` + `/change-password` pages, the auth gate on `/`, the tenant clamp,
  a staff-only header switcher, a VIEW-ONLY badge + identity + logout, and a startup seeding hook.
- **`.env.example`** — `IRCONNECT_STORAGE_SECRET`, `ADMIN_EMAIL`/`ADMIN_PASSWORD` (one-time
  bootstrap, rotation forced), `DEFAULT_USER_PASSWORD`.

Verified by a 27-check headless security test (tenant isolation, forged-cookie clamp
client_user saro→usio, data-layer write refusal, authenticate + forced-change flow) — all pass —
and a clean live boot (`/login`, `/change-password`, `/` all 200). USIO seeds 6 client logins,
SARO seeds 1 (`praxispointclient@saro`); no staff seeds until the operator sets the env creds.

**Follow-on same day:**
- **Standardized client logins.** Replaced the roster-derived seeding (per-executive accounts +
  a `praxispointclient@<ticker>` default — which left roster-less tenants like SARO with no
  meaningful login) with a uniform pair every tenant gets: **`directorofir@<ticker>`
  ("Director of IR")** and **`irassistant@<ticker>` ("IRassistant")**, both read-only, role IR,
  forced to rotate on first sign-in. Default password is now **`IRconnect1`**. The 7 old unused
  client accounts were dropped and the pair re-seeded for USIO + SARO.
- **Staff user-admin screen** (`/admin/users`, staff-only, linked from the header via a
  `manage_accounts` icon): list every login, add a user (seeded with the shared default password
  + forced first-login rotation), reset a password (re-arms must-change), and enable/disable a
  login (soft, not delete; you can't disable your own account). Backed by `auth.list_users`,
  `auth.admin_reset_password`, `auth.set_user_active`. Data-layer functions verified headlessly;
  live render pending a manual click-through (NiceGUI/Quasar resists browser automation here).
- **`.env` now loads before `ui.run`.** `IRCONNECT_STORAGE_SECRET` is read eagerly at module load,
  earlier than the first lazy `load_environment()` — so it was silently falling back to the dev
  default even when set. Load the env explicitly at the top of the entrypoint. Prod `.env` now
  carries a real 256-bit secret.

---

## 2026-07-18 — Multi-tenancy made real: client #2 (SARO), two-layer valuation, live consensus, full UI sweep

The platform went from "USIO app that says it's multi-tenant" to **genuinely multi-tenant**,
with a second real client onboarded end-to-end and the USIO-specific content that had been
baked in everywhere either generalized or explicitly gated. 26 commits on branch
`q2-earnings-script` (off `main`; not merged, not pushed).

### Tenant switching actually works now
The data layer was already `client_id`-scoped and 94 files routed through `CT()`/`CE()`/`CP()`,
but active-client resolution still read Streamlit's `st.session_state` — dead under NiceGUI, so
every session silently fell back to USIO. Ported to a **`contextvars.ContextVar`** (fast on the
hot path, async-safe so two browser sessions can't bleed), fed per render from `app.storage.user`,
with a **header switcher** that appears once there are 2+ tenants. `storage_secret` added to
`ui.run` (set `IRCONNECT_STORAGE_SECRET` in prod).

### Client #2: WRAP → SARO
Onboarded **WRAP** (Wrap Technologies) as a public-info-only demo, which served as the stress
test that exposed the whole USIO-leak surface — then **retired it** (weak lead: $114M micro-cap,
no analyst coverage) and onboarded **SARO (StandardAero, NYSE)** — a real, well-covered aerospace
engine-MRO mid-cap ($11.3B EV, 14 analysts, live consensus). WRAP's registry entry, peer set, and
transcript were purged.

### Peer discovery is now a method, not recall (`core/peer_discovery.py`)
Peer selection from memory left holes (missed BYRN for WRAP; the client fed us AerSale/TAT/FTAI
for SARO; a plain SIC screen instantly surfaced Howmet/Loar/Ducommun). The engine **triangulates
primary sources**: the 10-K competition section, an EDGAR SIC screen (own SIC + adjacent), the
DEF 14A compensation peer group, and the 10-K performance-graph index — then enriches each with
EV / filing gross margin / coverage. It captures; the analyst tiers.

### Two-layer valuation framework — the CFA-correct separation
A blended peer median made SARO look "+86% cheap." That's a **composition artifact** (a low-margin
services-MRO measured against high-margin parts makers). Fixed by separating:
- **Layer 1 — tight median** (`core/value_chain.py`): EV/Gross-Profit computed ONLY across
  model-matched peers (SARO + AAR + TAT), → **+36%**, the review-defensible read. `chain` is a
  free-form slug per peer, not hardcoded to aerospace.
- **Layer 2 — value chain**: the full chain (OEM → parts → aftermarket-services → distribution →
  leasing) shown for demand context, not the multiple.
- **Layer 3 — demand anchor** (`core/demand_anchor.py`): regresses each layer's revenue growth on
  a demand driver — and **honestly reports a negative**: Boeing revenue (the only filings-pullable
  driver) explains ~nothing ex-COVID (median R² 0.02), so the module refuses to rank layers off
  noise and flags the traffic/RPK feed as the real upgrade.

### Live, period-verified consensus (`market_data.consensus_rev`)
`q2_consensus_rev` is now a live per-tenant feed from Yahoo (`yfinance revenue_estimate`), with
**registry-value-wins precedence** (a curated number is a deliberate override; live fills the gap)
and **period verification** — reconciles Yahoo's year-ago figure against the client's own filed
actuals before trusting it; an unverified estimate returns None rather than risk a wrong-quarter
number. USIO $25.1M (registry), SARO $1,593.7M (live, verified, n=12).

### Transcript-driven script content (`transcripts.script_inputs`)
The earlier persona/guidance/carry-over **gates** (USIO-constants-or-blank) are replaced by
extraction from each client's OWN summarized transcript — guidance_language → prior guidance
quotes, qa_risk_topics → carry-over topics, key_quotes → persona refs by speaker role. USIO's
curated constants still win; other clients are transcript-driven. Proven on SARO (shows its own
risk topics: material weaknesses, customer concentration, tariffs).

### VSE: reclassify discontinued gross profit, don't fake-refresh it
VSE Corp came back `stale` (2017-vintage 48%). It can't be refreshed — VSE restructured and no
longer reports a cost-of-revenue line. `forensics.filing_margin` now distinguishes genuinely-stale
(1–2 yr) from **discontinued (≥3 yr)** → `no_gross_profit_line`, so an 8-year-old figure stops
posing as current.

### The big cleanup: two parallel USIO-leak surfaces swept
Driving SARO through every surface exposed that **USIO-specific content was baked in two places** —
the PDF generators (`report_pdf.py`) and, separately, the on-screen UI (`reports_page.py`, which
had never been swept). Both now generalized or gated to USIO:
- **PDFs**: SARO renders **10/10 reports clean, 0 crashes**; USIO unchanged. Fixed crashes
  (None-division where USIO always has a value — net cash vs net debt, settlement float), gated the
  interchange/SBC/gross-as-principal narrative, generalized every "USIO" label to the active
  ticker, and stubbed the USIO-Q2-specific artifacts (q2_script trio, mgmt_model EPS bridge).
- **UI reports page**: fixed the crashes that stopped it loading for SARO (Board IR Report,
  deep-dive, forensics, onboarding tabs) and gated the same USIO narrative in the valuation/
  forensics tabs. Verified statically (all `pol[...]`/USIO strings inside gates, compile + boot
  clean); browser click-through still recommended.

### Also
- `gitignore vendor/` — the Loughran-McDonald dictionary is commercial-licence-pending; committing
  it would be redistribution. **Correction (verified 2026-07-18): LM is NOT launch-blocking and is
  not a dependency.** The shipped hedge/non-answer analytics are our own, licence-free
  (`core/non_answers.py` + `core/hedge_lexicon.py`, built from the client's own outcome-labelled
  calls — see hedge_lexicon.py's docstring for why that beats LM for the IR question). LM
  (`core/lexicon.py`) is a dormant optional add-on gated behind an `lm_license` setting; it
  degrades to None and the app is fully functional without it. Licensing it later is purely
  additive.
- Systematic mistrust of favourable-looking numbers throughout: the +86%, the +142% consensus PT
  optics, the demand-beta noise — each surfaced with its caveat rather than presented as a finding.

### Known open items (not done)
- The remaining USIO-only report generators (q2_script trio) are stubbed for other tenants, not
  generalized — a real per-tenant Q2 script/decision-tree is a future build.
- Demand anchor needs a traffic/RPK feed to produce signal (external data).
- `persona_refs` needs a real call transcript with speaker turns to populate (SARO's public-filings
  source has none).
- Branch `q2-earnings-script` is unmerged/unpushed; `main` untouched. `data/app.db` (runtime
  binary), docs, `website_draft/`, `irconnect_live/` remain uncommitted by design.

---

## 2026-07-16 — The growth gap is **19pp, not 4pp**; Q2's base is divergent

Two corrections from the user, both of which changed the analysis rather than the wording.

### 1. We threw revenue out of the multiple — then quoted revenue growth beside it

The comp table's growth column is **latest-quarter REVENUE growth**. Every company is measured
that way, so it is internally consistent. But we rank on **EV/GROSS PROFIT**, precisely because
revenue is not comparable across gross and net reporters. Having correctly removed revenue from
the multiple, the table then reported revenue growth next to it. The growth attached to the
denominator we actually use is **gross profit growth**.

| basis | USIO | peer median | gap |
|---|---|---|---|
| quarterly revenue *(what the table showed)* | +15.7% | +19.5% | **−3.8pp** |
| annual revenue | +3.0% | +18.2% | −15.2pp |
| **annual gross profit** *(what EV/GP pays for)* | **+0.4%** | **+19.2%** | **−18.8pp** |

**Five times wider, in the flattering direction.** The difference between "grows a little slower"
and "does not grow while peers compound near 19%".

`forensics.annual_growth()` computes both bases from each filer's own annual report — reported
gross profit where tagged, derived from its own cost line where not, same period both sides.
USIO's row ties **exactly** to the FY2025 segment note parsed independently (+2.97% / +0.40%).

**What it does to the headline.** A company growing gross profit at +0.4% against peers at +19.2%
*should* trade at a discount. The live question is not whether 17% is too large — it is whether
it is too **small**. The +20% is not a finding that USIO is cheap; **it is a bet that the growth
gap closes.** The bet has real evidence (Q1 FY26 gross profit +7% vs FY2025's +0.4%) — but it is
one quarter, margin compressed while it happened, and the re-rating case now rests entirely on it.

### The user's framing, which is better than ours was

> "growth is always part of the story but if your margins are higher its forgiven but they have
> neither and costs are easier to control and thats why investors favor the margin expansion"

Investors forgive slow growth when **margins expand** — cost is the lever management controls, so
margin expansion is self-help and credible. They forgive thin margins when **growth is fast** —
scale is coming. USIO claims **neither**: gross profit +0.4%, gross margin −0.6pp. Adding revenue
that does not convert to gross profit earns credit from neither camp. **That explains the 17%
discount far better than "mispricing", and any re-rating case has to beat it.** Now in
`growth_basis()`'s read, so it travels with the number.

### 2. `core/comp_quality.py` — the Q2 base is divergent, and the script must not lead with revenue

User: *"q2 of last year ... so when they are building the script"*. Correct, and the filings make
it sharper than a single one-timer would:

| Q2 FY25 (2025-06-30) | | |
|---|---|---|
| revenue | **$19,960,990** | the WEAKEST quarter of FY2025 (−5.2% vs its FY average) |
| gross profit | **$5,140,069** | the **STRONGEST** in the two-year series — **#1 of 9** |
| margin | **25.8%** | the highest in the series |

**Easy on revenue and the hardest comp in two years on gross profit — off the same quarter.**
Both, because the revenue that went missing was LOW-margin. The 10-Q names it: *"the loss of a
meaningful customer in our Payfac business"*, *"attrition in our legacy portfolios"*, prepaid
program customer losses, lower interest revenue.

> Repeat Q1 FY26 and **revenue prints +27.6% while gross profit prints −0.1%** — a **28pp gap**.
> The same dollars are +21.0% vs that year's average quarter and **+12.6%/yr on a two-year stack**.

USIO grew revenue $19.96M → $25.47M while gross profit went **$5,140,069 → $5,136,883 — down
$3,186.**

`earnings_prep.headline()` now **leads** with this when the base is divergent — it outranks the
guidance gap, because the number the script wants to lead with is the one the base manufactured,
and the sell-side unpicks it within the hour.

### 🔴 The board package was shipping the headline naked

Found while building the PDF the user asked for: `board_package_pdf` rendered **"+20% implied
upside" in green with nothing attached** — no blend caveat, no sum-of-the-parts, no PRTH overhang.
The qualifications existed in the payload and never reached the page. **The one document that
leaves the building had the favourable number stripped of everything qualifying it.** Fixed via
`_valuation_caveats()`, shared by the board package and the benchmarking deep-dive.

### The $2M event: not found, not fabricated

Searched the Q1 FY25 10-Q, Q2 FY25 10-Q, Q1 FY26 10-Q and the Q1 FY26 earnings release. **No
discrete $2M line exists.** The largest single swing in Q2 FY25 is the **−$1.15M prepaid decline**
(incl. interest). The *mechanism* the user described is real and is now modelled from the filings;
the specific figure is not sourced, so no adjustment was applied. Flagged for the user rather than
back-solved.

### My own near-misses

- **`~/Desktop` is not the Desktop.** It is redirected to OneDrive; my write created
  `C:\Users\Owner\Desktop` — a folder the user never sees. The first PDF was delivered nowhere.
  Now asks Windows for the real path.
- **"every peer price is $0"** — I read `price`; the key is `last_price`. Nearly "fixed" working
  market data.
- **`_tc.build(bench)`** — the variable is `bm`. `py_compile` passed (NameError inside a function),
  and my own `try/except` would have swallowed it and silently dropped the section.

### Result

**Headline mechanically unchanged: median 3.61x · USIO 2.98x · +20% — now surrounded by what
qualifies it.** 10 reports build · 0 defects · 9 page modules import · server boots with 0 errors
· 0 missing-glyph boxes.

---

## 2026-07-16 — Segment revenue wired in; **PRTH is not GDOT**; the sensitivity blind spot closed

Three tasks. The second one required contradicting the instruction that started it.

### 1. The sensitivity gap: `sensitivity()` was blind to the peers that matter most

`sensitivity()` only inspects peers that HAVE an `ev_gp`. A peer excluded outright has
`ev_gp = None`, so it never enters `have` — the function whose entire job is finding open
questions was **structurally blind to the largest one**. That blindness had a price: IIIV and
PRTH were both once excluded as `stale`, `sensitivity()` returned `None` (reporting the answer
as ROBUST), while including them moved the median **3.13x → 3.74x** and the read **−3% → +16%**.

`excluded_impact()` closes it, and distinguishes two exclusions that are not the same:

| kind | example | sizable? |
|---|---|---|
| **STALE** — a real gross profit exists, just old | IIIV (last filed FY2023) | **yes**, as a labelled hypothetical |
| **NO GROSS PROFIT LINE** — none at any vintage | CASS, GDOT (banks) | **no** — and admitting a vendor number "to complete the median" is the exact error this module exists to prevent |

Proven rather than assumed: today's set is at 100% coverage so it correctly returns `None`. So
I forced IIIV back in — `sensitivity()` still returned `None`, `excluded_impact()` caught it and
flagged a **14pp swing as material**. Then restored the set.

### 2. 🔴 PRTH is **not** GDOT — the instruction rested on a premise the filings contradict

Asked to "treat PRTH just like GDOT" because it is "as good as gone". It is not, and acting on
it would have moved the CFO-facing headline by **14 points**.

| | GDOT | PRTH |
|---|---|---|
| Merger agreement | **signed** 2025-11-23 | **none** |
| DEFM14A / SC 13E3 / 425 | **yes** | **none** |
| Stockholder approval | **yes** — 8-K Item 5.07, 2026-06-23 | n/a |
| What exists | a deal | a *preliminary, non-binding* proposal, 2025-11-09 |
| Last development | closing | **2025-12-08 — 220 days of silence** |

The Special Committee's own 8-K: it *"has not set a definitive timetable"* and there *"can be no
assurance that any definitive offer will be made."* Since then PRTH filed a 10-K, filed a 10-Q,
changed auditors, and held a routine annual meeting electing directors *"until the next annual
meeting in 2027"* — a going concern's behaviour.

**The tape settles it.** PRTH trades **$6.79 against a $6.00–6.15 bid — 9.4% ABOVE the high
offer.** A stock pinned to a live deal trades just UNDER the offer on deal spread. Trading OVER
it means the market is pricing a control holder's lowball that the minority has not taken. So
PRTH's 4.06x is a **live market multiple** and belongs in the median.

Also: **GDOT was never in the median anyway.** It is excluded as `no_gross_profit_line` — it is
a bank. "Treat PRTH like GDOT" had no mechanical meaning; the two are excluded, or not, for
unrelated reasons.

Removing PRTH would take the median **3.61x → 3.16x** and the headline **+20% → +6%**. Note this
cuts AGAINST USIO — so it was not motivated reasoning. But wrong in the conservative direction
is still wrong. Surfaced it; PRTH stays, flagged and footnoted.

### `core/transaction_comps.py` — what an acquirer offered, kept OUT of the trading median

| Target | Consideration | Status | Implied EV/GP |
|---|---|---|---|
| **PRTH** | $6.00–6.15 cash | preliminary, **non-binding**; 220 days stale | **3.89x–3.92x** (vs **4.06x** market) |
| **GDOT** | $8.11 cash + 0.2215 New CommerceOne sh | **definitive**, approved 2026-06-23 | **not computable** |

GDOT's returns `None` deliberately — **two** independent disqualifiers: no gross profit line (no
denominator), and the stock leg does not trade (numerator not observable). Citi's $15.45–$17.51
is a **DCF output, not a price**, and is never quoted as one.

Corroboration worth noting: **Citi valued GDOT on P/2026E Adj. EPS and P/Tangible Book** — a
*bank* framework. The financial advisor on the actual deal agrees GDOT is not an EV/GP comp.

The usable read: the one **control bid** in the peer group — an insider with 58%, full diligence
and Barclays advising — landed near **3.9x** on a near-perfect structural analog, while USIO
trades near **3.0x**. Corroboration from a second, independent kind of buyer. **Not a price
target**, and the module says so.

### 3. `core/segments.py` — segment revenue, from the filing's own XBRL instance

`companyfacts` returns consolidated facts only; it strips dimensions, so segment detail is not
in that API at any depth. This goes to the **instance document** directly.

**Our own kit had the structure wrong.** It listed "Segment revenue table (ACH / Card / Prepaid /
Output)" as unsourceable, as though those were four segments. USIO reports **two**:

| FY2025 | Revenue | Cost | Gross profit | Margin | Rev growth | Margin Δ |
|---|---|---|---|---|---|---|
| Output Solutions | $20.8M | $16.8M | $4.0M | 19.3% | +0.2% | −1.7pp |
| Merchant Services | $64.6M | $48.9M | $15.7M | 24.3% | +3.9% | −0.3pp |
| **Total** | **$85.4M** | **$65.7M** | **$19.7M** | **23.1%** | | |

ACH, Card/PayFac and Prepaid all sit INSIDE Merchant Services. The kit was declining to produce
a table that could not have been produced anyway.

**Output Solutions' cost of services is 85% POSTAGE** — a pass-through. It is a print-and-mail
business, flat (+0.2%) with a declining margin (−1.7pp).

### 🔴 …which is a real objection to our own headline

USIO's 2.98x is **blended** across payments and print-and-mail. The 3.61x peer median is
**pure-play payments**. We were comparing a blend to a pure-play and calling the gap a discount.

`sotp_breakeven()` sizes it **without inventing a print comp** — we have no print/mail comp set,
and making one up is the fabrication this platform was rebuilt to eliminate. Instead: hold
Merchant Services at *exactly* the peer median, attribute all residual EV to Output Solutions,
and solve.

> Merchant Services at 3.61x = **$56.6M**. USIO's EV is **$58.7M**. Residual for Output
> Solutions = **$2.1M** → breakeven **0.52x**.

**0.52x is implausibly cheap** for a business with real revenue and positive gross profit — the
cheapest name in the peer set trades near 2.7x. **The discount survives the blend objection**,
and this is a *stronger* claim than the blended headline because it required no assumption about
what Output Solutions is worth. Had the breakeven come back at 3x, the callout says the headline
is not safe.

### Guards, not vibes

Segments are **reconciled** before they are shown: they must sum to consolidated on revenue,
cost AND gross profit, *and* consolidated GP must tie to `forensics.filing_margin()` — the figure
every other number on the platform is built from. All four tie **EXACTLY**. On any break the
module returns `reconcile_failed` and shows nothing, because a silently wrong segment split would
look authoritative.

That guard earned its keep immediately: the first parse returned `no_segments` and **failed loudly
instead of shipping a wrong split**. Cause — `explicitMember`'s `dimension` attribute is a QName
with a *colon* prefix (`us-gaap:StatementBusinessSegmentsAxis`), but `_local()` only stripped
Clark notation (`{ns}name`), so the axis never matched. Fixed with `_qn_local()`.

### Two of my own near-misses

- **`_tc.build(bench)` — no such variable** (it is `bm`). `py_compile` passed, as it always does
  for a NameError inside a function. Worse, my own `try/except` would have **swallowed it
  silently** and dropped the whole section from the PDF. Caught by asserting the payload is
  populated rather than trusting that it built.
- **"every peer price is $0"** — my probe read `price`; the key is `last_price`. My bug, not the
  platform's. Nearly "fixed" live market data that was working.

### Result

**Headline unchanged: median 3.61x · USIO 2.98x · +20% · $73.9M equity · n=6.** 10 reports build
· 0 defects · 9 page modules import · server boots with 0 errors · PDF renders with 0
missing-glyph boxes.

---

## 2026-07-16 — Board package cold render **12.3s → 7.3s**, warm **0.40s → 0.07s**

Profiled rather than guessed. The 12.3s was three separate problems, and the fix for the
biggest one would have gotten us blocked by SEC if done naively.

### What the profile actually said

| | |
|---|---|
| `_fetch_companyfacts` × 9 | **4.7s** — nine SEQUENTIAL multi-MB HTTP fetches |
| `psycopg2 execute` × 76 | **2.9s** — Neon is a cloud DB; every call is a round-trip |
| `get_snapshot` | **97.8ms each**, called **27×** = 2.6s |
| `build_benchmark` | called **3×** per render |

`build_benchmark` ran three times because `board_package.valuation()` calls it directly,
`valuation_comp.build()` calls it again, and `revenue_bridge()` calls `build()` which calls
it a third time. Same inputs, same answer, three times the latency. `filing_margin` ran **63×**
for 9 companies.

### Three fixes

1. **`get_snapshot` memo** (30s TTL, in-process). It reads `market_data_cache` in Neon — 98ms
   of network to re-read a row that already said the same thing, 27 times per render. Only
   short-circuits the FRESH path, so staleness is unchanged.
2. **`build_benchmark` memo** (45s TTL). 3× → **1×**. Short enough that a price refresh or a
   peer-set edit is felt on the next interaction; `clear_cache()` for explicit invalidation.
3. **Parallel `forensics.prefetch()`** — the 9 companyfacts fetches are independent.
   **4.7s → 1.98s.**

### 🔴 …and #3 would have gotten us rate-limited

`sec_filings._get()` slept `_REQUEST_DELAY_SEC` (0.15s) **after** each call. That is a
per-CALL delay, not a rate limit — it works only because every caller was sequential. Four
threads each sleeping on their own clock is **~26 req/s against SEC's ~10 req/s fair-access
limit**, and SEC blocks abusers.

So before parallelising anything, `_get()` now paces **globally**: one shared "next allowed
slot" that every thread advances under a lock, capped at **8 req/s**. Verified — 16 slots
across 4 threads measured **8.5 req/s**, within the limit. Sleeping *before* the request also
stops the delay being wasted on the last call of a batch.

This makes every SEC caller in the platform safer, not just the prefetch.

### Also

`board_package.compose()` and `at_a_glance()` both called `_reported_period()`, which fans
out to `financial_summary()`. Resolved once and passed through.

### Result

| | before | after |
|---|---|---|
| `board_package.compose` cold | 12.3s | **7.3s** |
| `board_package.compose` warm | 0.40s | **0.07s** |
| whole Board IR Reports tab, cold | 12.9s | **8.5s** |
| `build_benchmark` calls | 3× | **1×** |
| `live_ev` calls | 27× | **9×** |
| SQL statements | 76 | **38** |

The remaining 7.3s is legitimate cold work: ~2.0s of parallel multi-MB SEC downloads and
~1.8s of Neon first-reads that then memoise. Warm renders — every render after the first —
are effectively instant.

**Numbers verified unchanged by the perf work: median 3.61x · USIO 2.98x · +20%.** 9 reports
build · 0 defects · 6 page modules import · server boots with 0 errors.

---

## 2026-07-16 — Share count: **the EV behind every multiple was 7.8% stale, and a dual-class bug nearly halved a peer**

Went to settle the share-count discrepancy (config 26.80M vs market-implied 28.83M). The
answer was easy; what it exposed was not.

### The share count itself — EDGAR settles it

`dei:EntityCommonStockSharesOutstanding` off the 10-Q cover page. All four of our numbers
were wrong in different ways:

| source | shares | |
|---|---|---|
| `CF()['shares_out_m']` | 26.80M | tracks the **May 2025** filing — **a year stale** |
| TwoTier CompSheet | 27.70M | used the **10-K** (Mar 2026) — one quarter old |
| Yahoo (mcap ÷ price) | 28.83M | 4.5% high — **because the mcap was stale, see below** |
| **EDGAR dei (10-Q filed 2026-05-13)** | **27,595,994** | **authoritative, as of 2026-05-11** |

Yahoo's own `sharesOutstanding` returns **27,595,994** — agreeing with EDGAR to the share.
Our 28.83M was never a source; it was my division of a stale market cap by a live price.

### 🔴 THE REAL BUG — EV was computed at a stale price

`get_fundamentals()` caches **24h**. `get_snapshot()` caches **60 minutes**. So the price on
screen refreshed hourly while the **market cap and enterprise value behind every multiple
refreshed daily**. Measured with the cache 11.7h old and USIO down 7.5% on the day:

| | cached | live | |
|---|---|---|---|
| market cap | $64,298,664 | **$61,539,068** | −4.3% |
| **enterprise value** | $63,650,704 | **$58,683,424** | **−7.8%** |

**EV is the numerator of EV/Gross Profit, EV/Revenue and EV/EBITDA.** That error propagated
into every multiple, the peer median, the discount and the implied value — silently, and
worst on exactly the volatile days when anyone would look.

It is not a cache-tuning problem. **EV has two halves on different clocks:** market cap moves
every tick; net debt moves when the company FILES. Caching them together at the slower
cadence is the mistake. New `market_data.live_ev()` caches the slow half (shares, net debt)
and rebuilds the fast half from the live snapshot — exact at any cache age, and returns
`None` rather than a stale guess if either half is missing.

### 🔴 …and the fix nearly shipped a worse bug

Rebuilding market cap from Yahoo's `sharesOutstanding` **halved PAY**. `sharesOutstanding` is
the REPORTED count — **Class A only** for dual-class and up-C structures — while `marketCap`
covers every class:

| | mcap ÷ price | sharesOutstanding | |
|---|---|---|---|
| **PAY** | **125,789,331** | 62,936,502 | **2.00×** |
| MQ | 105,202,041 | 97,000,000 | 1.08× |
| RPAY | 88,086,833 | 82,800,952 | 1.06× |
| USIO / PMTS / PRTH / PAYS | — | — | identical (single class) |

PAY's EV/Gross Profit would have fallen **11.19x → 5.17x**, dragging the peer median down and
**inflating USIO's apparent discount**. Same species as every other error today: plausible,
undetectable by eye, and flattering to the client. Caught only because a **−50% "drift"** is
not a price move.

Fixed: `shares_for_mcap` (mcap-consistent, all classes) for market-cap maths;
`shares_outstanding` (reported) kept for per-share statements about the client;
`multi_class` flagged. `live_ev()` now **prints a warning** when drift exceeds 25% — that is
the tripwire that caught this, so it is permanent.

*(The TwoTier CompSheet had PAY at 125.8M. It got this right and I did not.)*

### Net effect on the headline

| | before | after |
|---|---|---|
| USIO EV | $63.65M (stale) | **$58.68M (live)** |
| USIO EV/GP | 3.23x | **2.98x** |
| peer median | 3.59x | **3.61x** |
| implied | +11% | **+20%** |
| **implied price/share** | $3.29 or $3.05 (ambiguous) | **$2.68 on 27,595,994 shares** |

The per-share figure is now unambiguous — EDGAR and Yahoo agree to the share, and USIO is
single-class so there is no ambiguity to inherit.

### Verified

9 reports build · 0 defects · 6 page modules import · server boots with 0 errors · every peer
now carries real shares and net debt with ~0% drift.

---

## 2026-07-16 — Cleanup while waiting on the CFO: **3 more seed bypasses. The Pre-Call panel was inverted.**

Client is waiting on CFO confirmation and asked what to clean up so everything is "framed in
and ready to plug in the information." The right lens: **when the CFO's data arrives, what
would fail to flow, or silently keep serving demo data?** We had already found two of those
(`period_estimates` falling back to the seed; `risk_scorecard` bypassing the override). So I
audited every seed fallback path.

### 🔴 Three more bypasses found — all latent, all fire exactly when the data lands

| file | what it read | why it matters |
|---|---|---|
| `earnings_page.py` | `get_seed_consensus()["period_guidance"]["Q2 2026E"]` | **the guidance number.** Invisible today because the override happens to equal the seed — the moment the CFO revises, this panel keeps the old number while every other surface updates |
| `today_page.py` | `get_seed_consensus()["period_estimates"]` for the consensus PT | **the landing screen.** Its own docstring promises *"a PT change… is reflected here automatically"* — while reading the seed, where `update_estimate()` never lands. The docstring asserted the opposite of the code. |
| `investors_page.py` | `get_seed_consensus()["period_guidance"]` for an EV/Rev outreach multiple | puts a stale multiple in front of an **investor** — the exact failure its docstring says it exists to prevent |

All three now read `consensus.get_consensus()`. Verified: the only surviving
`get_seed_consensus` references are `core/consensus.py` (which IS the override-applier) and
two comments.

### 🔴 The Pre-Call Assessment panel was inverted, and it is the one used on call morning

`earnings_page.py`'s Pre-Call Assessment — the panel that "captures the embedded expectation
for post-call scoring" — had **four** hardcoded fields:

| field | showed | reality |
|---|---|---|
| Street consensus | **$25.1M** — `CT('q2_consensus_rev')`, a config constant | **$23.67M** live, n=4, verified mapping |
| Guidance midpoint | seed — **bypassed the override** | |
| vs street | **`"-$0.6M below street"`** — a literal string | guidance is **+$0.83M ABOVE**, above EVERY published estimate |
| Bar risk | **`"HIGH"`** hardcoded | LOW — delivering the guide beats the whole street |
| period | `"Q2 2026E"` hardcoded | breaks silently on the roll to Q3 |

**It would have told the IR team they were BELOW the street on the morning of the call, when
they are above it** — the same inverted claim retracted from the Earnings Prep Brief, still
live in the panel management actually opens. Now all derived: street from the feed, guidance
from the override, gap/risk/note computed, period from `CE()`.

### Caught my own NameError — and only one check would have found it

Adding `consensus`/`market_data` to that panel, my patch's import never landed. **`py_compile`
passed and `import earnings_page` passed** — because the names are referenced inside a
function, not at module scope. It would have thrown `NameError` the moment anyone opened the
tab. Caught by checking `hasattr(module, name)` for every name the new code uses. That check
is now the habit: for UI code, compiling proves nothing.

### The test that actually matters

Simulated a CFO guidance revision ($24.50M → $26.90M) and confirmed it propagates:

```
consensus.get_consensus()   -> $26.90M  OK
earnings_prep.the_bar()     -> $26.90M  OK
guidance_reconciliation     -> sum moves 98.47 -> 100.87  OK
risk_scorecard              -> reads the override  OK
restored to $24.50M         OK
```

**The plumbing is now proven, not assumed.** When the CFO sends models or revises guidance, it
flows.

### Seeds WITHOUT an override — not bugs, but know what they are

`buyside_institutions` (62 funds, powers NDR-by-city + scoring), `conferences`,
`institution_contacts`, `nobo_holders` (awaiting the real Broadridge pull), and
`peer_fundamentals` (documented last-resort for EV/Rev + growth only; it no longer touches
margin). These are seed-only by design — there is no override to bypass. Worth knowing they
are seed data if any of them ever needs to be real.

---

## 2026-07-16 — NEW: NDR Coverage by City — **the CFO asked for a report we didn't have**

CFO asked for examples of the reports and specifically for **NDR by City**, which didn't
exist. Every input already did — the buy-side list with metros, the live engagement scoring,
and the booked NDR calendar. It was a join the platform could always have done and never had.
`core/ndr_by_city.py` + `ndr_by_city_pdf()`, live in Reports → 90-Day IR Plan.

### 🔴 I nearly shipped a false finding. The metric was wrong.

The obvious move is to average engagement score across every fund in a metro. Do that and:

> New York = **51**, second-weakest of eight → the NDR schedule looks **INVERTED**, as if we
> are spending our best days in our worst market.

**That read is an artefact.** New York has 15 funds and Chicago has 6, so New York's average
is diluted by a long tail we would never actually meet. **An NDR is not an average** — you fly
somewhere and take 4–6 meetings. The question is not "what is the mean fund here" but "how
good are the meetings I could actually FILL A DAY with."

Ranked on the **top-5 non-holders**, the picture reverses: New York is the **strongest** market
(74) and the schedule is **positively correlated (+0.44)**. The plan is directionally right.

I caught this only because I computed the correlation instead of eyeballing the table. Rank on
the wrong metric and you talk yourself out of a correct schedule.

### 🔴 And a real data bug: the city labels don't join

The NDR calendar files trips under a **city** label ("Boston"); the buy-side list uses a
**metro** label ("Boston / New England"). An exact-match join drops the trip on the floor —
**and my first cut did exactly that, reporting "Boston — no trip" about a metro with a trip
already on the calendar.** A city-level report whose labels don't join is worse than no report:
it invents an absence.

`_normalise_city()` joins on the leading segment and logs anything that still doesn't match.
**This mismatch means any prior city-level analysis was silently dropping Boston.**

### The findings, once the metric and the join are right

| # | metro | top-5 | non-holders | booked |
|---|---|---|---|---|
| 1 | New York Metro | **74** | 12 | 7 ✓ |
| 2 | Boston / New England | 69 | 7 | **0 — but a trip IS booked** |
| 3 | Chicago / Midwest | 69 | 5 | **0** |
| 4 | Texas | 69 | 6 | 4 ✓ |
| 5 | San Francisco | 68 | 6 | **0** |
| 6 | Los Angeles | **60** | 8 | **4** |

- 🔴 **Boston has a trip on the calendar with ZERO meetings in it** — #2 market, 7 non-holders,
  Rutabaga (75) / Adage (75) / Wellington (74) unbooked. A day already committed and wasted.
- ⚠ **Chicago (69) and San Francisco (68)** are as strong as Texas (69, 4 meetings) and get none.
- ⚠ **LA (60) ranks 6th of 8** and gets 4 meetings.

### Delivered

Three example PDFs to `Downloads/USIO_Platform_Examples/`: NDR Coverage by City (3pp), Peer
Benchmarking (5pp), Earnings Prep Brief (4pp). All 0 rendering defects. Render cost checked
before trusting it: **1.78s cold / 0.00s warm.**

Recommended sending NDR by City (answers the ask, and carries the Boston finding) + Peer
Benchmarking (the EV/Revenue bridge answers the question every CFO is asked). Flagged the
Earnings Prep Brief as a judgement call — it opens with "your quarters don't foot to your FY
range", which is true, his number, and 27 days out, but lands differently as a cold demo.

**9 live reports · 0 rendering defects.**

---

## 2026-07-16 — IRConnect Onboarding Checklist: **the one document with no bad data — and it contains the root cause**

`IRConnect_Client_Onboarding_Checklist.docx` is the only artifact in the set with nothing
fabricated in it. It is a **process** document, not an analytical one — Praxis Point's own
ask-list for a new client. So it wasn't audited; it was turned into
`core/onboarding_checklist.py` + `onboarding_checklist_pdf()`, live.

### A tick is not a check

The .docx asked the client to tick "□ Pending" boxes. **A tick says someone typed an answer,
not that the thing works** — and those differ: USIO's checklist would have shown "analyst
roster ✓" while every model behind it was demo data. Every item is now answered by querying
the platform. Items sourced from SEC filings aren't asked of the client at all.

**USIO: 8 of 15 ready.** The 7 gaps are real and two of them chain:

| gap | |
|---|---|
| **Sell-side MODELS (0 of 5)** | **not on the original checklist at all** — and it is the most consequential omission. It asked for the *roster* (which was right) and never for the *models* (which were demo). |
| **Transfer agent of record** | not tracked anywhere — and it **gates** the NOBO request |
| **NOBO ever requested?** | still no. Oldest open item on the engagement: on the 90-Day Plan (target Jul 3, overdue), the Board Package ("scoped but not yet submitted"), and here. **Blocked on the transfer agent above. Two gaps, one chain** — which is why it has survived three documents. |
| Annual meeting date · outside counsel · proxy solicitor · quarter-end→results lag | not tracked |

### 🔴 The root cause of half of today, sitting in the onboarding policy

> **"Peer/comp group — defined by your team and sell-side coverage, NOT ASSIGNED BY US."**

That deference sounds respectful. **It is how USIO came to be benchmarked against a bank.**
The inherited comp group was, in its own words, *"set by management and sell-side coverage
(Ladenburg, H.C. Wainwright): GDOT, IMXI, FINW, PAYS"* — GDOT (merger approved 2026-06-23),
IMXI (pending Western Union), FINW (**a bank**), PAYS. Three of four disqualified.

The TwoTier memo had already named the mechanism: *"That list reflects USIO **management's**
competitive landscape view, not necessarily the most useful **investor** comp set."*
**Management's competitor list answers "who do we lose deals to." An investor comp set
answers "what should this trade at." Different questions, and only the second has rules.**

`peer_group_policy()` rewrites the item. Not an override — the client's view is real
information about the business — but "not assigned by us" is an abdication, not deference:

> "We want your team's view AND your analysts'… We will then **TEST** every name against the
> criteria below and tell you which fail and why."

**(a)** independent, no pending/approved M&A · **(b)** segment overlap (a name that divested
the overlapping business no longer qualifies — that is IIIV) · **(c)** comparable revenue
basis, payments processor not bank accounting.

`check()` runs (a) and (c) against the live set on every render. All 6 current peers PASS (c);
PRTH carries its take-private flag. **Criterion (a) can't be checked from XBRL** — it needs a
human on each name's filings quarterly. It is the one that caught GDOT, and it caught it from
an **8-K**, not a feed. The kit says so rather than implying automation it doesn't have.

### Verified

3 pages, 0 black-box glyphs. **Final regression: all 9 live reports build, 0 glyphs across
every one, server boots clean.**

---

## 2026-07-16 — Analyst Onboarding Kit REBUILT live — **the framework kept, every answer regenerated**

Client: *"this was all a demo, its the framework we need to use."* So the escalation below
stands as a record of what the demo contained, but nothing went to an analyst and there is
nothing to unwind. **The framework was the deliverable, and it is now live**:
`core/onboarding_kit.py` + `onboarding_kit_pdf()`, in Reports → Board IR Reports.

### The .docx's shape was right and is kept

Business model → thesis → forensic positioning → **Q&A cheat sheet** → model-building
metrics is a genuinely good artifact, and it correctly identified which question analysts
ask first. The shape survives; every answer is regenerated from a primary source and prints
the source beside it — because this is **the only artifact built to be handed to a sell-side
analyst, and its reader has the 10-K open.**

### The answer that had to invert

| | |
|---|---|
| **.docx Q1** | *"Some peers report gross revenue (**inflating their margin denominator**). On a normalized net basis, Usio's margins are competitive."* |
| **live Q1** | *"Because **WE** report revenue gross, as a principal — not because peers inflate theirs. Our 10-K says it plainly: 'The Company complies with ASC 606-10 and reports revenues at gross as a principal versus net as an agent.' … So gross margin is not comparable across payment processors at all. Compare gross PROFIT, or EV/Gross Profit — revenue cancels out of that ratio entirely."* |

**And the true answer is the stronger pitch.** It explains the margin, quotes a checkable
line, redirects to a metric where USIO looks reasonable (3.2x vs a 3.6x median) rather than
one where it looks broken, and it *holds when checked*. Nothing was conceded by telling the
truth — that is the whole thesis of the module.

It also keeps the .docx's one genuinely good half: interest income on prepaid float, a
~100%-margin line, fell ~$400K YoY costing ~150bps. **Independently corroborated** by the
TwoTier CompSheet's SOTP ($1.5M FY25A → $1.1M FY26E). Two sources, same number.

### 5 questions, not 8 — on purpose

Three of the .docx's answers depended on the fabricated forensic table. An unanswerable
question is better left off an external document than answered from a workbook nobody can
check. Every surviving answer carries `sources`, and **Q2 branches on the live number** —
if USIO is at a premium it says *"We are not making a cheapness argument right now."*

Q4 is the one that shows the shift in posture. The .docx called 2-of-5 coverage *"the
asymmetric setup… the opportunity."* Live: *"'five analysts' overstates it and we would
rather you knew that from us"* — because an analyst can count the notes themselves.

### A section that says what it will NOT claim

`cannot_source()` prints the three things the prior kit asserted and this one won't, with the
reason: segment revenue (companyfacts is **consolidated only** — verified; segment detail
lives in the filing's segment note, which we don't parse), payment volume (earnings release,
not XBRL), and the peer forensic adjustments (quarantined workbook). *A kit that quietly
drops what it can't support looks thinner; one that says why is more credible than the
version that made it up.*

### Verified

4 pages, 0 black-box glyphs. **Absent:** `Net reporter`, `82% discount`, `MOST MISPRICED`,
`LONG USIO`, `21.8%`, `23.8%`, `inflating their margin denominator`, `cheapest and most
capital-efficient`. **Present:** `gross as a principal`, `we report revenue gross`, `not
because peers inflate theirs`, `EV/Gross Profit`. Full regression — all **8** live reports
build; server boots clean.

### Queue complete

Earnings Prep Brief · Board Deck (verified, nothing portable) · TwoTier CompSheet (adopted) ·
Board Package + Board IR Report (merged) · 90-Day IR Plan (verified) · Onboarding Kit (rebuilt).

### Still open

- `IRConnect_Client_Onboarding_Checklist.docx` (12.5KB) — a separate document, never audited.
- Segment revenue + payment volume would need the earnings release wired in; both are named
  in the kit as absent.

---

## 2026-07-16 — 🔴 [SUPERSEDED — demo artifact, nothing distributed] Analyst Onboarding Kit audit

Two distinct documents, not duplicates: `USIO_New_Analyst_Onboarding_Kit_1.docx` (37KB) and
`IRConnect_Client_Onboarding_Checklist.docx` (12.5KB). This entry covers the first.

**This is the most dangerous artifact in the engagement, and the reason is its audience.**
Every other document we audited was internal — a board deck, a workbook, a board package.
This one is **built to be handed to sell-side analysts.** It carries the fabricated workbook's
conclusions in an external-facing wrapper, and its errors would be discovered by the reader.

### 🔴 The scripted answer to the #1 question is backwards

Section 4's **Q1** — which the document itself marks **"📌 CRITICAL — this is the first
question ever asked"**:

> **Q1: Why is gross margin only 20-23% when competitors are 30-40%?**
> "…(2) **Some peers report gross revenue (inflating their margin denominator).** On a
> normalized net basis, Usio's margins are competitive with direct peers."

**USIO is the gross reporter.** From its own 10-K, filed 2026-03-18, verbatim:

> "The Company complies with ASC 606-10 and **reports revenues at gross as a principal**
> versus net as an agent."
> "Revenues derived from electronic processing of credit, debit, and prepaid card
> transactions … are **reported gross of amounts paid to sponsor banks as well as interchange
> and assessments** paid to credit card associations."

**The failure mode is specific and severe.** An analyst asks the question this document
predicts they will ask first. IR gives the scripted answer. The analyst opens the 10-K's
revenue recognition note — the first thing anyone checks on a payments company — and finds
the opposite. On a micro-cap whose stated goal is going from 2 covering analysts to 5, that
is not a correction; it is the end of the relationship.

### The rest of the forensic content is the retracted material, verbatim

| kit says | reality |
|---|---|
| "**Net reporter — 23.8% GM is real**" | USIO is a GROSS reporter; FY2025 GM is **23.1%** |
| "FOUR's adjusted gross margin is ~21.8% — **BELOW Usio's 23.8%. The company you think has better margins actually has worse ones**" | FOUR's real GM is **32.4%** (its own MD&A). Retracted this morning. |
| "EV/Revenue 0.4x · peer median 2.3x — **82% discount**" | 0.75x actual; EV/Rev is **not comparable** — the discount is a margin difference |
| "$67.2M capitalized software" / "$89.4M SBC" | from the quarantined seed; actual FOUR SBC **$82.0M** |
| "⚡ FORENSIC PAIR TRADE: **LONG USIO**" | on the adopted peer set the cheapest name is **MQ**, not USIO |
| "USIO 72/100 ★★★ **MOST MISPRICED**" | efficiency 31.2, **rank 3 of 6** |
| "THE THESIS: Usio is the **cheapest and most capital-efficient** payment processor in its peer universe" | it is neither |

### What is REAL and worth keeping

The kit is not worthless — **Sections 1, 4 and 5 are good IR work**, and one claim is
independently corroborated:

- **Q1 point (1) is TRUE and checkable:** *"interest income on prepaid card loads — a 100%
  margin revenue line — declined ~$400K YoY as rates normalized, compressing reported margin
  by ~150bps."* The TwoTier CompSheet's SOTP independently shows Interest Income **$1.5M FY25A
  → $1.1M FY26E = −$0.4M**. Two sources, same number. This is a real and useful piece of the
  margin story.
- **Section 5's model-building metrics** (volume $2.50B vs $1.96B +28%; ACH $6.3M +25%; Card
  $9.7M +23%; Output $6.8M +19%) sum to ~$25.2M against a reported $25.47M — consistent with
  segment disclosure, and the "build your model volume → take rate → revenue → gross profit"
  framing is exactly right.
- **The Q&A cheat-sheet structure** (8 questions, two-sentence answers, "asked in 5 of last 5
  calls") is genuinely strong IR practice.

### The honest answer to Q1 is BETTER than the false one

This is the point worth making. The kit's inverted answer isn't even a good pitch. The true
one is stronger, because it survives the analyst reading the 10-K:

> *Our gross margin is ~23% because **we** report revenue gross of interchange, as a principal
> (10-K, revenue recognition note). Interchange we never keep sits in both our revenue and our
> cost of services. A peer reporting net shows 60–75% on identical economics. So gross margin
> is not comparable across payment processors at all — compare **gross profit**, or
> **EV/Gross Profit**, where revenue cancels out of the ratio entirely. On that basis we trade
> at **3.2x vs a 3.5x peer median**. Separately, interest income on prepaid float — a
> 100%-margin line — fell ~$400K YoY as rates normalised, which cost ~150bps of reported
> margin; ex-interest, processing margin is improving.*

Every clause is sourced, it answers the question asked, and an analyst who checks it finds it
holds. That is the version this platform can now generate — `forensics.USIO_POLICY` carries
the quote, `valuation_comp.revenue_bridge()` carries the arithmetic.

### 🔴 RECOMMENDATION — client decision, not ours

**This document must not be distributed in its current form.** If it has already gone to any
analyst, the gross-vs-net claim needs correcting directly rather than quietly — it is a factual
statement about the company's own accounting that its 10-K contradicts.

Nothing was ported. Flagged and stopped.

### Still open

- `IRConnect_Client_Onboarding_Checklist.docx` (12.5KB) — a different document, not yet audited.

---

## 2026-07-16 — 90-Day IR Plan: **live plan already correct. The .docx has the wrong earnings date.**

Both copies of `USIO_90_Day_IR_Plan.docx` are byte-identical (`44e340c3576a`). One document.

`core/ir_plan.py` already composes this live and **needed no rebuild** — it reads the real
earnings date, the real quiet period, live NDR trips with meeting counts, live prospects from
the pipeline, catalysts pulled from the transcripts, and ownership signals from the NOBO flow.
Verify-not-rebuild was the right call.

### 🔴 The .docx has the wrong earnings date — and every downstream phase hangs off it

| | |
|---|---|
| Plan says (Phase 2) | Q2 2026 earnings = **Aug 5** |
| Platform + **Yahoo calendar** | **2026-08-12 16:00 ET** |

**Yahoo is authoritative here and I checked it rather than assume:** its `earnings_dates`
history matches **all six** of our transcript dates exactly (2026-05-13, 2026-03-18,
2025-11-12, 2025-08-06, 2025-05-14, 2025-03-26). Last year's Q2 reported Aug 6 — the author
likely assumed by analogy.

**The 7-day error makes the plan internally impossible:** Phase 2 has the blackout *reopening*
**Aug 7**, five days BEFORE the release it exists to protect, and Phase 3 begins "post-earnings"
on **Aug 8** — four days before earnings. Consistent with Aug 5; incoherent against reality.

### The whole of Phase 1 is overdue

Phase 1 ran **Jun 19 – Jul 14**. Today is **Jul 16**. All five of its "Open" items are past
target: NOBO request (Jul 3), 5th-analyst follow-up (Jun 26), Russell Microcap verification
(Jun 26), peer roster refresh (Jul 7). The document describes itself as "living — review
weekly" and hasn't been.

Two of those trace to threads already open here: the **NOBO request** is the standing roadmap
item, and the **5th analyst** is the same phantom Sell/$1.50 the Board Package flagged as
unresolved. Its "verify CTLP" item is also stale — Cantaloupe was already acquired and
delisted, which the CompSheet confirms.

### 🔴 FIFTH hardcoded-favourable claim found and fixed

`ir_plan.py`'s positioning was a **static list**, including:

> "Benchmark us on gross profit, not gross revenue — **the valuation discount is real, not a
> margin weakness**."

A claim about a **live** number frozen into a string. That number has been **+37% → −3% (a
PREMIUM) → +9%** in a single day of peer-set work. On the day it was a premium, this line
would have sent the IR team into meetings to assert a discount that didn't exist. And "not a
margin weakness" is contradicted by our own EV/Revenue bridge — the EV/Rev gap **is** a margin
difference, findable by any analyst who multiplies EV/GP by gross margin.

Now `_valuation_message(ctx)`, derived. The thesis half is legitimately static (benchmark on
gross profit — always true, because revenue cancels out of EV/GP). The claim half branches:

- **discount:** *"we trade at 3.2x vs a 3.5x peer median, a 9% discount. That is the number to
  use, and it is defensible line by line."*
- **premium:** *"**AND DO NOT CLAIM A DISCOUNT RIGHT NOW** — a 3% PREMIUM. The case has to be
  made on the margin bridge and growth, not on being cheap."*

Verified by forcing the premium branch.

**Running tally of this bug, all found today:** `key_finding`'s growth conclusion · the
`LONG USIO` pair trade · `"a -3% discount"` · the board report's "cheap on a growing base" ·
this. Every one asserted a favourable conclusion the live data was free to contradict.

### What the .docx has that we don't (worth stealing later)

Phase structure with a **workstream table — Owner / Target date / Status** — and explicit
blocking items. Our live plan has a timeline but no owners or status, so it says what happens
and not who owes it. That is a real gap; the .docx's *shape* is better even though its content
is stale.

### Verified

`ir_plan_pdf` 2 pages, 0 black-box glyphs, stale claim absent, Aug 12 correct. Full regression:
ir_plan, board_package, earnings_prep, peer_benchmarking all build.

---

## 2026-07-16 — Board Package + Board IR Report **merged into one live document**

Client decision: merge. Two board documents that duplicated each other's valuation and
ownership sections — and could therefore disagree in front of the same board — are now one.
`core/board_package.py` + `board_package_pdf()`, live in Reports → Board IR Reports.
`board_ir_report_pdf()` kept as a back-compat alias so existing callers don't break.

**Structure from the .docx** (it was better than what we printed), **every figure from a
filing, the market feed, or our own log.**

### The .docx's central failure was a LABEL. The fix is structural.

It said "Q2 2026" on a package built from Q1 data because a human typed the title.
`_reported_period()` now **derives** the period from `quarter_end` on the 10-Q, and names
the unreported quarter separately so the two can never blend. The header reads:

> "Reporting the **Q1 2026** quarter ended **2026-03-31** (last quarter actually filed).
> **Q2 2026** reports 2026-08-12 — **27 days out and NOT reflected here.**"

### 🔴 A 13D count without a date window is meaningless — and I got it wrong first

USIO has **19 Schedule 13D filings** on EDGAR. They span **2001–2023**. Activists file, then
exit, and the filing stays on EDGAR forever.

- The .docx said **"0 Schedule 13D filers — holder base remains passive."** Directionally
  right, stated as a fact that is false: there are 19.
- **My first draft counted all 19 and reported "19 activists"** on a $64M micro-cap. Caught it
  because the number was implausible on its face and contradicted the .docx.

The honest read is the **window**: **0 filings in 2 years** (newest 2023-11-29), 3 Schedule
13G (passive) in the same period. The package now states the window, the all-time count, and
*why the all-time count says nothing* — so neither error can recur.

### Two bugs fixed while absorbing the old report

1. **Executive summary asserted "cheap on a growing base" unconditionally** and quoted
   EV/Revenue as supporting evidence. Both are claims: the discount can be a premium, and
   EV/Revenue isn't comparable at all. Now branches on the sign and says so — currently
   *"a 9% discount to the 3.5x peer median. EV/Revenue is NOT a usable comparison here and is
   excluded from that read."*
2. **EV/Revenue shown GREEN with "% below median"** — the third instance of this exact bug
   today (board deck panel, benchmarking engine, here). Now *"context only — NOT comparable"*,
   uncoloured.

### What it refuses to print

- **Short interest** — the .docx printed "0.14% of float / 0.3 days to cover". No
  short-interest feed is wired in. Reported as absent, naming the figure it won't reproduce.
- **Per-analyst models** — no feed publishes them; none on file. Sell-side section says so and
  points at Open Items.

### Sell-side section earns its keep immediately

| firm | rating | PT | last action | |
|---|---|---|---|---|
| Ladenburg Thalmann | Buy | $6.25 | 2026-05-15 | active |
| HC Wainwright | Buy | $4.00 | 2026-03-20 | active |
| Litchfield Hills | Buy | $6.00 | 2024-06-05 | **DORMANT** |
| Barrington Research | Market Perform | — | 2023-05-25 | **DORMANT** |
| Maxim Group | Buy | $5.00 | 2022-08-15 | **DORMANT** |

> "2 of 5 covering analysts have acted within the last year… calling this 5-analyst coverage
> is generous."

### Appendix A carries a rationale per name

Because a comp sheet without one is how the prior package listed an acquired company, a
pending acquisition and a bank as "Active" for a quarter without anyone noticing.

### Verified

4-page PDF, 0 black-box glyphs, back-compat alias works, server boots clean, all sections
confirmed rendering in-browser. Render timed before trusting it: **9.7s cold / 0.4s warm** —
slow on a cold cache but not the 23s class of regression.

---

## 2026-07-16 — Quarterly Board Package audited: **reports a quarter that hadn't happened**

All 9 copies in Downloads (`_1`–`_7`, `(1)`, base) are **byte-identical** — `35a088660f2c`,
14,311 bytes. One document, nine download duplicates.

### 🔴 It reports Q2 2026 results. It is dated June 19, 2026.

| | |
|---|---|
| Document date | **2026-06-19** |
| Q2 2026 covers | Apr 1 – **Jun 30**, 2026 |
| Q2 2026 earnings date | **2026-08-12** |

On 2026-06-19 the quarter **had not ended** (11 days to go) and would not be reported for
another **54 days**. Yet the package states *"Q2 beat and raised: revenue growth guidance
moved from 10–12% to 12–13%"*, *"+8.75% Beat vs. consensus"*, *"+24.2% Stock reaction"* and
*"Stock ran ~24% into the print."*

**It is Q1 2026 data wearing a Q2 label.** The +16% growth is Q1's (live: +15.7%), and app.py
independently attributes the +8.75% beat and +24.2% reaction to Q1'26.

### Its USIO valuation is wrong in both directions at once — both flattering

| | doc | actual | error |
|---|---|---|---|
| Market cap | ~$40M | **$64.3M** | 38% LOW |
| TTM revenue | ~$102M | **$85.4M** | 19% HIGH |
| **P/S (TTM)** | **~0.4x** | **0.75x** | 47% low |

A low numerator over a high denominator. Internally consistent ($40/$102 = 0.39x) and wrong on
both inputs, in the direction that makes USIO look cheap. Then: *"USIO trades at roughly a 4x
discount to the group average."* Same P/S-across-different-revenue-bases error as every other
artifact today — USIO reports GROSS.

### Its comp group is 3-of-4 disqualified

> "Comp group set by management and sell-side coverage (Ladenburg, H.C. Wainwright):
> **GDOT, IMXI, FINW, PAYS**"

- **GDOT** — merger approved 2026-06-23 (4 days after this doc; pending at the time)
- **IMXI** — pending Western Union acquisition (the doc flags this itself)
- **FINW** — FinWise Bancorp, **a bank**
- **PAYS** — legitimate, in our set

This is the comp group the **TwoTier CompSheet was written to replace** — the CompSheet
evaluates GDOT, IMXI, CTLP and FINW by name and excludes all four. Three June 2026 documents,
three different comp sets: this package (GDOT/IMXI/FINW/PAYS) → the CompSheet
(PAY/MQ/RPAY/PMTS + IIIV/PRTH/PAYS) → the board deck (GDOT/PRTH/EEFT/FOUR/RPAY). Only the
CompSheet's holds up.

### 4 of 5 analyst entries contradict the tape

| doc | Yahoo (verified) |
|---|---|
| Hickman / Ladenburg · Buy $6.25 | Buy $6.25 (2026-05-15) ✓ |
| Buck / HCW · Buy **$4.50** | Buy **$4.00** (2026-03-20) |
| Diana / Maxim · Buy **$4.00** | Buy **$5.00** (2022-08-15) |
| Sine / Litchfield · **Hold $3.00** | **Buy $6.00** (2024-06-05) |
| "5th analyst" · **Sell $1.50** · *pending confirmation* | Barrington: **Market Perform**, no PT (2023-05-25) |

### ⚠ UNRESOLVED — the bear

The doc asserts a 5th analyst at **Sell / $1.50** against a $2.23 stock, marked "pending
confirmation." Independently, Yahoo's rating buckets show `strongSell: 1` that **no named firm
in upgrades_downgrades accounts for**. Two sources hint at a bear; neither substantiates
$1.50, and Barrington's actual last action is Market Perform. Yahoo's buckets are unreliable
for micro caps. **Not surfaced anywhere. Genuinely open** — and worth asking the CFO about
alongside the models.

### What survives: the STRUCTURE

The skeleton is a legitimate IR board package and better than what we print today:
**1.** Quarter at a glance · **2.** Sell-side coverage (per-analyst, vs guide) · **3.** Buy-side
& retail (13D/G, callback coverage, NOBO) · **4.** Market context & valuation vs peers ·
**5.** Open items for board awareness · **Appendix A** comp sheet with rationale.

Every one of those inputs is now live and verified: Yahoo `upgrades_downgrades` for §2, our
ownership/13D-G tracking and NDR pipeline for §3, the benchmarking engine + EV/GP + the
revenue bridge for §4, `risk_scorecard` for §5, and the adopted peer set + memo rationale for
Appendix A.

Note *"NOBO list request scoped but not yet submitted — recommend authorizing ahead of the
annual meeting"* matches the standing roadmap item (real Broadridge NOBO upload).

### ⚠ OVERLAP — needs a decision before building

`board_ir_report_pdf` already exists and covers: executive summary · quarter financials ·
balance sheet & cash flow · **valuation & peer position** · **ownership & the Street** · board
takeaway · talking points. That is §4 and part of §2/§3 of this package, already built and live.

Building the Quarterly Board Package standalone would duplicate the valuation and ownership
sections across two board documents. Since the Board IR Report is the very next item in the
queue (#5), the two should be resolved together rather than sequentially.

---

## 2026-07-16 — IIIV/PRTH 10-K read: **PRTH recovered (+11%), IIIV sold its payments business. 100% coverage.**

Read both MD&As, as the FOUR pattern suggested. They came back opposite.

### PRTH — derivable, and it reconciles to the CompSheet exactly

Its 10-K uses "gross profit" 4 times and **none of them are its own**: all four are acquisition
earn-out mechanics (*"earn-outs will be paid as a percentage of gross profit when certain
thresholds are met"*) referencing acquired businesses inside contracts. So no MD&A figure to
hand-carry — but XBRL has it:

```
RevenueFromContractWithCustomerExcludingAssessedTax   FY2025   $953.0M
CostOfGoodsAndServiceExcludingDepreciationDepletion…  FY2025   $578.3M
                                                      GP    =  $374.7M -> 39.3%
```

**CompSheet says $375M / 39.3%.** Same derivation, independently. Our `_COST` list simply
lacked `CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization` — **the same tag
FOUR uses**. Added.

Flagged honestly: that tag **excludes D&A**, so a margin derived from it is a gross profit
*before* depreciation and is flattering by however much D&A belongs in cost of revenue. The
detail string says so, and quantifies it with the one case where we can check both ways —
FOUR reads 34.2% ex-D&A vs the **32.4%** its own MD&A reports. FOUR still uses its MD&A figure
(`ok_mda` is checked before the cost derivation), verified.

### 🔴 IIIV — not a payments company. Removed.

Its 10-K uses "gross profit" **zero times**, and the reason is bigger than a tagging choice.
Verbatim, 10-K filed 2025-11-21:

> "As a result of the **sale of the Merchant Services Business in 2024** and the Healthcare RCM
> Business in 2025, the results of operations… have been reflected as **discontinued
> operations**… After giving effect to these developments, we have **one operating segment**…
> enterprise software and services solutions to our **public sector customers**."

**i3 Verticals sold its payments business in 2024.** The CompSheet included it as *"Best
size-matched analog for USIO's PayFac-in-a-Box strategy"* — for a business it had already
sold. It fails the memo's own criterion (b), *"meaningful overlap with at least one USIO
segment."* Its 10-K predates the CompSheet by 7 months, so this was knowable.

That also explains its stale XBRL: the FY2023 `GrossProfit` of $333.3M is the **pre-divestiture**
company, on revenue that is now $213M — a 90% "margin" that is an artifact of comparing the old
business's profit to the new business's revenue. Exactly the period-mismatch class of error that
produced FOUR's nonsense 6.7% earlier today. Removed from the peer set; backed up first.

**The CompSheet is good work but not infallible** — it was right about GDOT and CASS on
principle, wrong about IIIV on fact. Verifying it was worth doing.

### Result: coverage 100%, and the answer moves −3% → +11%

| | EV/GP | GM | basis |
|---|---|---|---|
| MQ | 2.60x | 70.0% | ok |
| RPAY | 2.98x | 75.0% | ok |
| PMTS | 3.13x | 31.3% | ok |
| **USIO** | **3.23x** | **23.1%** | ok |
| **PRTH** | **4.04x** | **39.3%** | **derived (new)** |
| PAYS | 9.44x | 59.4% | ok |
| PAY | 11.19x | 24.8% | ok |

**Peer median 3.59x · USIO 3.23x → +11% implied ($2.66/sh).** Forensics coverage
**100% of 6 primary, nothing excluded** — the first time every peer in the median has a
filing-sourced gross profit.

The EV/Revenue bridge moves with it: USIO's warranted EV/Rev is now **0.83x** against 0.75x
traded — **10% below warranted**. The finding survives the peer-set change intact: the peer
median EV/Rev of 1.98x still isn't a target, because it still reflects margins USIO doesn't have.

### Open

- PRTH carries a take-private overhang (CEO proposal $6.00–6.15). If it closes, it leaves the
  set for the same reason GDOT did — and it is now the median-setter, so that would move the
  headline. Worth a watch.
- PRTH's margin is ex-D&A and therefore slightly flattering; a full-cost figure would lower its
  39.3% and, since it sets the median, lower the +11%.

---

## 2026-07-16 — The EV/Revenue bridge: **the "revenue discount" was a margin difference in a costume**

`valuation_comp.revenue_bridge()`, surfaced in Reports → Peer & Market and printing on the
benchmarking PDF.

### The problem it solves

Everyone quotes EV/Revenue. Across this peer set it is **not comparable** — USIO reports
revenue GROSS as a principal, peers vary — which is how the retired board deck got from
"0.4x vs a 2.3x peer median, an 82% discount" to a **$9–12 price target on a ~$3 stock**.

But refusing to speak EV/Revenue isn't an option either: it's the number in every screen and
every first meeting. So bridge to it instead of arguing with it.

### The bridge

The identity is exact and verified on every row:

> **EV/Revenue = (EV/Gross Profit) × (Gross Profit/Revenue) = EV/GP × gross margin**

EV/Revenue can't be compared ACROSS companies — but each company's **warranted** EV/Revenue
is derivable: take the peer median EV/Gross Profit (the multiple that IS comparable) and
apply it to that company's **OWN** margin. The margin never leaves its own filer, so nothing
is compared that shouldn't be.

| | EV/GP | gross margin | EV/Rev today | **EV/Rev warranted** | vs warranted |
|---|---|---|---|---|---|
| RPAY | 2.98x | 75.0% | 2.24x | **2.35x** | −5% |
| MQ | 2.60x | 70.0% | 1.82x | **2.19x** | −17% |
| PAYS | 9.44x | 59.4% | 5.61x | **1.86x** | +201% |
| PMTS | 3.13x | 31.3% | 0.98x | **0.98x** | +0% |
| PAY | 11.19x | 24.8% | 2.77x | **0.78x** | +257% |
| **USIO** | **3.23x** | **23.1%** | **0.75x** | **0.72x** | **+3%** |

### The finding

**USIO's warranted EV/Revenue is 0.72x. It trades at 0.75x — 3% ABOVE warranted.**

The peer median EV/Revenue of **2.08x was never a target**. Peers trade there because they
earn 60–75% gross margins on net-reported revenue; USIO earns 23.1% on gross-reported
revenue. **Closing that "gap" would require the margin, not a re-rating.** The EV/Revenue
discount was a margin difference wearing a valuation costume — and this table is the
one-page proof, in the language the market already speaks.

It also explains the whole arc of today's retractions in one line: every version of the
"USIO is deeply undervalued on EV/Revenue" story — the workbook's 82%, the deck's $9–12,
app.py's "82% discount not justified by fundamentals" — was reading a margin as a discount.

### Verified

- Identity checked on all 6 rows: `EV/GP × GM == EV/Rev` to 4 decimals, exactly.
- Benchmarking PDF now 5 pages, 0 black-box glyphs. UI matches.

---

## 2026-07-16 — TwoTier CompSheet: **real work. Adopted its peer set. The discount disappears.**

First of the three legacy artifacts that survives review. Unlike the fabricated workbook
(0/11 claims) and the board deck (0/11), this one is rigorous, and **it is better than
ours**.

### It matches our filings to the penny

| | CompSheet | our EDGAR data |
|---|---|---|
| LTM revenue | $85.40M | **$85.39M** |
| LTM gross profit | $19.70M | **$19.69M** |
| Gross margin | 23.07% | **23.06%** |

Whoever built this read the same filings we did.

### Its SOTP independently corroborates our valuation

Segment sum-of-parts **BASE $3.56/share** vs our EV/Gross-Profit **$3.29**. Two unrelated
methods, within 8%. Both demolish the retired deck's **$9–12**.

### 🔴 GDOT — verified in an approved merger, and it was in our live peer set

The memo flagged it; the primary source confirms it. **8-K Item 5.07, filed 2026-06-24:**

> "On June 23, 2026, Green Dot Corporation held a virtual special meeting of stockholders
> to consider... the Agreement and Plan of Merger, dated as of November 23, 2025, by and
> among Green Dot, CommerceOne Financial Corporation... **Each of the four proposals was
> approved by the requisite vote of Green Dot's stockholders.**"

Its price is pinned to deal consideration. We had already found its EV was **negative
(−$318M)** without understanding why.

### Its criteria state, on principle, what our forensics found the hard way

> "(a) US-listed, actively traded, independent public company — **no pending M&A**;
> (b) meaningful overlap with at least one USIO segment; (c) revenue reported on
> comparable basis (**payments processor, not bank accounting**)"

- **(a)** disqualifies GDOT — we found the negative EV.
- **(c)** disqualifies CASS — we found its 10-K uses "gross profit" **zero times**. The memo
  excluded FinWise for exactly this: *"Reports under bank accounting (NII, provisions,
  capital ratios)."*

Two names, two routes, same conclusion. And on provenance:

> "The prior comp set was built primarily from the USIO 10-K's named competitors section...
> That list reflects USIO **management's** competitive landscape view, not necessarily the
> most useful **investor** comp set."

### ADOPTED (client decision)

| | |
|---|---|
| removed | CASS, CSGS, FOUR, GDOT, PSFE |
| added | IIIV, MQ, PAYS, PMTS, PRTH |
| kept | PAY, RPAY (+ GPN/TOST reference) |

**T1 segment analogs** (PAY, MQ, RPAY, PMTS) and **T2 size-matched** (IIIV, PRTH, PAYS) both
map to `primary`; the tier survives in the record and the segment label. Backed up first.

### 🔴 THE DISCOUNT DISAPPEARS

| peer set | median EV/GP | USIO | implied |
|---|---|---|---|
| old (CASS/CSGS/FOUR/GDOT/PSFE…) | 4.44x | 3.23x | **+37%** |
| **adopted two-tier** | **3.13x** | 3.23x | **−3% ($2.33/sh)** |

**USIO trades at a 3% PREMIUM to a properly size-matched, payments-focused peer set with no
acquired companies and no banks in it.**

This is exactly what the memo predicted: *"Using only large-cap analogs systematically
overstates the appropriate multiple."* Our old set carried FOUR ($9.3B EV, 6.9x), CSGS
($2.7B, 4.4x) and PSFE ($2.7B, 2.8x) against a $57M-EV company. The +37% was an artifact of
comparing a micro-cap to mid-caps.

Coverage held at 5 of 7 — but the two gaps are now *closable*: IIIV and PRTH stopped tagging
`GrossProfit` (FY2023 / FY2020), the same MD&A situation as FOUR. **This is material**: on the
CompSheet's own figures they'd come in at 3.90x and 3.74x, moving the median 3.13x → 3.74x and
the implied read **−3% → +16%**. Not applied — unverified against the filings.

### Two more hardcoded-favourable bugs, same species as the earlier one

1. **`"a {discount_gp:.0f}% discount"`** printed **"a -3% discount"**. A negative discount is
   a premium; burying the sign in a word meaning its opposite is how an unfavourable read
   gets skimmed as a favourable one. Now prints **"a 3% PREMIUM"**.
2. **The pair-trade hardcoded LONG the client** — `f"LONG {u['ticker']} / SHORT {short}"`
   regardless of rank. Only invisible while USIO was near-cheapest. On the new set USIO is
   #4 of 6, so it asserted a trade the table on the same page contradicts. Now: *"the
   cheapest name is MQ (2.6x), not USIO (3.2x) — a long/short built off this table would be
   LONG MQ / SHORT PAY and would not involve USIO at all. That is the read a hedge fund gets
   from these comps."*

Also note the growth branch fixed earlier now fires on its unfavourable side for the first
time: *"It grows slower than the group (16% vs 19% median) — so part of the discount is a
growth discount."* The old code would have said "so the discount isn't a growth discount."

### Verified

All four PDFs build on the new set (peer_benchmarking, board_ir_report, ir_plan,
earnings_prep). Distribution is bimodal — MQ 2.60x / RPAY 2.98x / PMTS 3.13x, then PAYS 9.44x
/ PAY 11.19x — so the median is doing real work and the mean would mislead.

### Open

- **Read IIIV's and PRTH's 10-K MD&A for current gross profit** (the FOUR pattern). Worth
  −3% → +16% on the headline. Highest-value item on the board.
- PRTH carries a take-private overhang (CEO proposal $6.00–6.15) — flagged in its segment
  label; if that closes it leaves the set for the same reason GDOT did.
- `sensitivity()` doesn't cover peers excluded for *staleness* that would move the median —
  it only detects non-filing-backed peers already *inside* it. The IIIV/PRTH gap is invisible
  to it.
- The CompSheet's own trading comps rank on **EV/Revenue** and **EV/EBITDA** — neither is
  comparable here (USIO reports gross). Its SOTP is sound; its comp-table multiples are not
  the ones to quote.

---

## 2026-07-16 — Real analyst data entered · **2 more bugs found: risk_scorecard bypassed the override, and "models" never meant models**

### What could actually be entered — and what could not

Yahoo attributes data to a named firm on **exactly one surface**: `upgrades_downgrades`
has a `Firm` column. Every estimate surface (`revenue_estimate`, `earnings_estimate`,
`eps_trend`, `eps_revisions`) is **aggregate only** — avg/low/high/n, no attribution.

| | source | entered? |
|---|---|---|
| Rating per firm | Yahoo `upgrades_downgrades` | ✅ real |
| Price target per firm | Yahoo `upgrades_downgrades` | ✅ real |
| Revenue / EPS / EBITDA per firm | **nowhere** | ❌ not obtainable |

So "enter the real analyst models" resolves to: **the models aren't publicly obtainable.**
They come from the analysts by email — which is what app.py's Mail Gateway "ingested_models"
archive was for. The honest action was therefore to **clear the fakes**, not replace them.

### The demo models, tested against reality before removal

6 of the 8 checkable estimates fell **outside** Yahoo's published range. The two that
landed inside did so by coincidence:

| period | firm | demo | real range | inside? |
|---|---|---|---|---|
| Q2 2026E | H.C. Wainwright | 25.50 | $23.02–24.45M | **NO** |
| Q2 2026E | Ladenburg | 24.80 | $23.02–24.45M | **NO** |
| Q3 2026E | H.C. Wainwright | 26.00 | $23.01–23.52M | **NO** |
| Q3 2026E | Ladenburg | 25.50 | $23.01–23.52M | **NO** |
| FY 2026E | H.C. Wainwright | 96.00 | $94.85–96.27M | yes |
| FY 2026E | Ladenburg | 94.50 | $94.85–96.27M | **NO** |
| FY 2027E | H.C. Wainwright | 108.00 | $103.64–107.04M | **NO** |
| FY 2027E | Ladenburg | 106.00 | $103.64–107.04M | yes |

**18 demo model rows cleared** across 9 periods. Ratings + PTs kept — they were already
correct and Yahoo confirms them (HCW Buy/$4.00 ✓, Ladenburg Buy/$6.25 ✓). The three
inactive analysts stay empty: Yahoo has last-known ratings for Maxim (2022), Barrington
(2023) and Litchfield (2024), but writing a 2-to-4-year-old rating into "Q2 2026E
estimates" would assert it as current. Their history lives in the coverage table, dated.

Wrote `period_estimates.json` directly rather than via `consensus.update_estimate()` — that
function stamps `analyst_dates_override[firm] = today`, which would record that we heard
from the analyst today. We didn't; we read a feed. Reversible: delete the override key and
it falls back to the seed. Prior value backed up.

### 🔴 BUG 1 — risk_scorecard bypassed the override entirely

`core/risk_scorecard.py` imported `get_seed_consensus` **directly from the seed module in
six places**, never going through `consensus.get_consensus()` — the accessor that layers the
DB override on top.

**Consequence: every risk signal on the Today page was computed from demo seed data that no
amount of real data entry could ever change.** The IR team could enter a real model via
`update_estimate()`, `get_consensus()` would see it, and the risk signals would keep
reporting the demo number forever. Found because the signals still said "Street $25.1M"
after I'd cleared it and `street_avg()` correctly returned `None`.

All six routed through `get_consensus()`. Immediately: "Consensus Revenue" flipped from a
fabricated `YELLOW · Street $25.1M vs guidance $24.5M` to an honest
`GRAY · No ingested analyst estimates for this period yet`, and the bogus AMBER
"Street at $25.1M" signal disappeared.

### 🔴 BUG 2 — "analyst models" never counted models

Two signals counted analyst **status**, not whether a model exists:

```python
active   = sum(1 for a in CA() if a.get("status") == "active")   # -> "2 of 5 models"
inactive = [a for a in CA() if a.get("status") != "active"]       # -> "3 of 5 models missing"
```

An analyst being active means they **publish research** — not that we hold their
spreadsheet. Those are different facts, and conflating them understated the gap:

| | before | after |
|---|---|---|
| EBITDA / EPS Risk | `YELLOW · consensus built on 2 of 5 models` | `RED · NO analyst models on file — 2 of 5 actively cover USIO, but not one of their models has been ingested` |
| Actionable signal | `3 of 5 analyst models missing` | `5 of 5 analyst models missing — no consensus can be built from models we hold` |

The signal's **email recipient list was also wrong** — it mailed `inactive` analysts asking
for models, so the two ACTIVE analysts who publish (and whose models are collectable today)
were never asked. Now mails everyone with no model on file, and the copy distinguishes the
2 active from the 3 dormant.

### Verified

- `street_avg()` over the file → `None` (not a stale number).
- The brief's street still comes from the feed: **$23.67M, n=4, market feed** — unaffected.
- The demo-data warning in the brief is now gone, because the demo data is gone.
- Regression pass: `earnings_prep`, `script_scorecard`, `weekly_brief` and all three PDFs
  build clean. Server boots with 0 errors.

### Open

- **Collect HCW's and Ladenburg's actual models.** They're active, they publish, and the
  platform now says plainly that we don't have them. That is the one gap real work closes.
- `_model_request_email()` still takes its copy from the old inactive/re-init framing —
  worth re-reading now that it goes to active analysts too.

---

## 2026-07-16 — 🔴 **RETRACTION: the Earnings Prep Brief's street was DEMO data.** Yahoo wired in.

Client asked whether we could pull analyst estimates from Yahoo to run the brief against
live data. We can — and doing so **falsified the brief I shipped an hour earlier**.

### The consensus file was never written

```
period_estimates.json  -> NOT written  ->  falls back to data/seed/consensus_estimates.py  [DEMO]
period_guidance.json   -> WRITTEN      ->  real entered data
```

`consensus.get_consensus()` silently falls back to the seed. So the brief's "street
$25.15M (H.C. Wainwright $25.50M, Ladenburg $24.80M)" was **demo seed values**, presented
as the number the call is judged against.

| | our file (demo seed) | Yahoo (real, 4 analysts) |
|---|---|---|
| Q2 2026 street | **$25.15M** | **$23.67M** |
| range | $24.80 – 25.50M | **$23.02 – 24.45M** |
| FY 2026 street | — | $95.68M |

**Both seeded figures sit ABOVE the entire real range.** And the error was not
directionally neutral — it inverted the brief's headline:

- ~~"USIO can hit its $24.5M guide and still MISS the street ($25.15M) by 2.7%"~~ — **FALSE.**
- **TRUE: USIO's $24.5M guide sits ABOVE every published analyst estimate** (street high
  $24.45M). Delivering the guide beats the whole street by 3.4%. The risk isn't the bar —
  it's that USIO has guided to a number nobody on the street models, so **the guide itself
  is the claim that needs backing on the call.**

### Finding #1 SURVIVES — and gets sharper

The guidance-reconciliation finding used only real inputs, and I verified the one that
mattered: **Q1 2026 actual $25.47M reconciles EXACTLY to EDGAR XBRL** (quarter_end
2026-03-31). Quarters still sum to $98.47M vs a real $95.3–97.0M FY range.

It's now sharper: the street models FY2026 at **$95.68M** while USIO's own quarterly
guides imply **$98.47M** — the street is 2.9% below USIO's own build.

### NEW: `market_data.get_estimates()` / `street_for_quarter()`

Yahoo exposes `revenue_estimate`, `earnings_estimate`, `analyst_price_targets` and
`upgrades_downgrades`. Wired in with the same cache/fallback contract as
`get_fundamentals()` (12h TTL).

**Period mapping is VERIFIED, not assumed.** Yahoo labels periods relatively ("0q", "0y"),
which is useless unless you know which quarter it thinks is current. `street_for_quarter()`
reconciles Yahoo's year-ago figures against actuals from the filings:

```
0q yearAgoRevenue $19,960,990  vs USIO Q2 2025 actual ~$19.90M   ✓
0y yearAgoRevenue $85,393,630  vs USIO FY2025 XBRL     $85.4M    ✓
```

If the check fails it returns `verified: False` and the caller must not use it.

**`the_bar()` refuses to fall back to the seed.** If the feed can't be sourced with a
verified mapping, it returns `unavailable` and offers no beat/miss read — a brief that
silently swaps a demo number in for the street is worse than one that says it can't source it.
The platform's file is retained ONLY as a cross-check, and the brief now prints a warning
naming the demo figures and the fact that they fall outside the real range.

### Bonus: `upgrades_downgrades` confirms the roster and adds real PTs

Yahoo's coverage list **matches our platform's five firms exactly** — the roster was right,
only the estimates were demo:

| firm | rating | PT | last action |
|---|---|---|---|
| Ladenburg Thalmann | Buy | $6.25 | 2026-05-15 (raised from $5.75) |
| HC Wainwright | Buy | $4.00 | 2026-03-20 |
| Litchfield Hills | Buy | $6.00 | 2024-06-05 (init) |
| Barrington Research | Market Perform | — | 2023-05-25 |
| Maxim Group | Buy | $5.00 | 2022-08-15 |

Now printed in the brief. Note the vintage: **Maxim's last action is 4 years old and
Barrington's is 3** — "5 covering analysts" is generous.

### Also fixed

- `scenarios()` rebuilt for a distribution (low/avg/high) instead of per-analyst
  attribution, which the feed doesn't provide. Its caption claimed thresholds were "each
  analyst's OWN published number" — untrue once the source changed; corrected in both
  renderers.
- Left a `⚠` in `_bar_read` after making the no-emoji-in-the-data-layer rule an hour
  earlier. Reportlab rendered it as a black box. Removed; verified 0 black-box glyphs.
- Render timing checked before trusting it: 3.8s cold. No regression.

### Open

- **Enter the real analyst models** into `period_estimates` so the cross-check does its
  job. Until then the platform's own estimate file is demo data with a live warning on it.
- Yahoo's `recommendations` shows a **strongSell** in the bucket counts that no firm in
  `upgrades_downgrades` accounts for. Yahoo's rec buckets are notoriously stale for micro
  caps — not surfaced anywhere, flagged as unverified.

---

## 2026-07-16 — Board Deck verified against live data: **0 of 11 claims survive. Nothing ported.**

Extracted all 5 slides of `USIO_Peer_Benchmarking_Board_Deck.pptx` (stdlib zipfile +
ElementTree; python-pptx not installed) and tested every quantitative claim against
live filings and market data before porting anything.

| claim | deck says | live says | verdict |
|---|---|---|---|
| Peer universe | GDOT·PRTH·EEFT·FOUR·RPAY | CASS·CSGS·FOUR·GDOT·PAY·PSFE·RPAY | **WRONG** |
| USIO revenue growth | 10.0% | **+15.7%** | stale |
| Peer median growth | 8.3% | **+10.4%** | stale |
| USIO gross margin | 23.8% | **23.1%** (FY2025 filing) | stale |
| "At peer median gross margin…" | implies a valid GM comparison | **no valid peer GM median exists** | **INVALID** |
| USIO EV/Revenue | 0.4x | **0.72x** | **WRONG (44% off)** |
| Peer median EV/Revenue | 2.3x | 2.18x | stale |
| "82% discount" | 82% on EV/Rev | **27%** on the one comparable multiple | **INVALID** |
| **"Implied USIO price ~$9–12"** | **$9–12** | **~$3** | **WRONG (2.7–3.7×)** |
| Consensus PT | $5.12 · 138% to $2.15 | $5.12 · 130% to $2.23 | stale |
| "$2.07/$100 vs RPAY $1.06 — premium processor" | premium positioning | **INVERTED** | **INVALID** |

**0 of 11 survive. 6 WRONG/INVALID, 5 STALE.**

### The dangerous one

**"Implied USIO price ~$9–12 at peer median"** — a price target, in a board deck. It
comes from applying a peer **EV/REVENUE** median to USIO's **GROSS** revenue: the exact
error the footnote forensics exists to prevent. Revenue does not cancel out of EV/Rev,
and USIO's revenue is inflated by interchange it never keeps, so the multiple lands on
a denominator that isn't comparable to anything.

On EV/Gross Profit (where revenue does cancel): implied equity **$88.1M** → **~$3/share**.
The deck overstates by **2.7–3.7×**.

### Nothing was ported. The live panel already replaced it — but carried one of its errors

`_render_board_deck_live()` had `EV / Revenue … "{discount}% below median"` styled **green**,
presenting the invalid metric as a favourable valuation fact — the same mistake the deck
made, in our own live panel. Now shown as **"context only — NOT comparable"**, uncoloured,
and the slot it freed is given to the defensible number: **implied upside +37%** at the
4.4x peer median.

### Why no per-share figure, deliberately

The board will want one, and the deck gave them $9–12. We give a percentage instead,
because **the two share-count sources on file disagree by 7.6%**: `CF()['shares_out_m']`
= 26.80M vs market-implied (Yahoo mcap ÷ price) = 28.83M. Implied price is $3.29 on the
first and $3.05 on the second. A per-share number would silently inherit that gap. The
panel states the disagreement rather than picking a side.

*(Both land at ~$3 either way — the deck's $9–12 is wrong on any share count, so the
falsification doesn't depend on resolving it.)*

### Verified

- The .pptx is **not rendered anywhere in the live app** — `PBD_PAGES` is never imported;
  only a review-tracking row references the filename.
- Live panel confirmed in-browser: 3.2x EV/GP, +37% implied upside, EV/Rev marked
  context-only, key_finding carrying the gross-reporter explanation.

### Open

- Share-count discrepancy (26.8M vs 28.8M) — worth resolving; it feeds any per-share work.

---

## 2026-07-16 — Earnings Prep Brief built live → **USIO's own guidance doesn't foot**

### Why it was never ported: it never worked

app.py's "Generate Q2 Earnings Prep Briefing" button shelled out to
`node generate_briefing.js`. **That file does not exist anywhere on the filesystem**
(searched; node itself is installed, v24.18.0). The button could only ever have
failed. There was nothing to port — the only surviving spec is the caption:

> "consensus vs guidance, beat/miss scenarios, approved talking points, risk flags,
> and Q&A prep"

Good spec, honoured live in `core/earnings_prep.py` + `earnings_prep_pdf()`, surfaced
in **Reports → Board IR Reports**. Prints as PDF, not .docx — the audit's premise is
that every report must print, and report_pdf is the established path.

### 🔴 FINDING 1 — the quarters do not foot to the full year

| | |
|---|---|
| Q1 2026 **actual** | $25.47M |
| Q2 guide | $24.50M |
| Q3 guide | $25.00M |
| Q4 guide | $23.50M |
| **Sum** | **$98.47M** |
| **Stated FY 2026 guidance (CFO decision)** | **$95.3 – 97.0M** |

The sum is **$1.47M ABOVE the top of USIO's own FY range.** Any analyst who builds the
quarters gets a different full year than the one USIO published. It reads either as
sandbagged FY guidance or as quarterly guides that won't hold — and that is a
credibility question, not a modelling one.

**Nothing in the platform was checking this.** `guidance_engine.guidance_consistency()`
returns `needs_redraft: False, conflicts: []` — because it verifies the SCRIPT'S PROSE
states the same FY range the CFO decided. It is a text-vs-decision check and was never
built to add the quarters up. New `earnings_prep.guidance_reconciliation()` closes it.

### 🔴 FINDING 2 — USIO can hit its guidance and still miss the Street

Street $25.15M vs guidance $24.50M → **+2.7%**. Management can deliver exactly what it
promised and the tape reads a miss. That is the most likely way a good quarter gets
reported as a bad one, and it is now the brief's second headline.

**And the bar is set by two analysts.** H.C. Wainwright $25.50M, Ladenburg $24.80M;
Maxim, Litchfield Hills and Barrington carry **no model at all**. A 2-analyst mean is
not a consensus — if either revises by $0.5M the "consensus" moves $0.25M and the
beat/miss headline flips with nothing changing at the company. **Both** published
numbers sit above guidance: there is no analyst on file who has USIO merely hitting its
own guide.

Scenarios are built off each analyst's OWN number, not the mean, because an analyst
writes "beat" or "miss" against their own model:

| revenue | vs guide | vs Street | reads as |
|---|---|---|---|
| $25.50M | +4.1% | +1.4% | Clean beat — clears every published model |
| $25.15M | +2.7% | 0.0% | Beats the mean, **misses H.C. Wainwright** |
| $24.80M | +1.2% | −1.4% | **Hits guidance, misses the Street** |
| $24.50M | 0.0% | −2.6% | Hits guidance, misses the Street |

### FINDING 3 — four unpaid questions carried from Q1 2026

Via `morning_after.frame_qa` (the number_frame model): 3 MISMATCH + 1 DEFERRED.
Analysts asked for numbers and got prose. They carry debts forward — it's in their notes.

| verdict | demand | anchor |
|---|---|---|
| MISMATCH | BACKING on a CLAIM | sales funnel / pipeline ("billions of dollars", no metrics) |
| MISMATCH | REPEATABILITY on a GOOD number | PayFac activation tempo |
| DEFERRED | REPEATABILITY on a GOOD number | % of customers on single vs all four products |
| MISMATCH | REPEATABILITY on a GOOD number | card revenue growth |

### Design rules

- **`headline()` picks the sharpest TRUE fact, in priority order.** A brief that opens
  with anything softer than its worst true fact is decoration — management can feel
  reassured without our help.
- **Coverage honesty:** "consensus" always prints with its n.
- **No emoji in the data layer** — reportlab's Helvetica has no glyph and rendered a
  black box. The renderer picks the marker; the module states the fact. Verified: 0
  black-box glyphs in the PDF.

### Caught in passing

- My patch script's idempotence guard matched the **call site** rather than the `def`,
  so it skipped and would have shipped a `NameError` at render. Fixed the guard.
- Timed the render before trusting it (lesson from the 23s regression): 3.5s cold,
  0.8s warm. No regression.
- Peer & Market's data-provenance note still said gross margin comes "from the filing
  where reported, otherwise from market data (Yahoo)" — untrue since the engine
  rebuild. Corrected.

---

## 2026-07-16 — app.py cleaned: **7 false claims, several were investor-facing scripts**

### app.py is NOT dead code — checked before touching it

It is imported by `pages/outreach.py`, `page_modules/calendar_page.py` and
`page_modules/outreach.py`, and `extract_report_images.py` deliberately preserved
`streamlit run app.py`. So this was a surgical fix, not a deletion. Backed up first
(1,608,795 bytes); 53 lines changed; **all 9 removed lines verified to be the false
claims and nothing else**; compiles, AST-parses, and its three importers compile.

### Why this mattered more than "stale demo text"

These were **talking points for what the IR team would say to investors** — not
display copy. And they were INVERTED, not imprecise:

| claim in app.py | reality |
|---|---|
| `"PRTH holder entry: both net reporters — direct margin comparison valid"` | **USIO reports revenue GROSS as a principal** (10-K 2026-03-18). It instructed the team to make a comparison that is invalid. |
| `"GDOT holder entry: USIO adj. GM > GDOT adj. GM after gross vs net normalization"` | **GDOT reports no gross profit or cost-of-revenue line at all.** Nothing to normalize, no comparison to offer. |
| `"Putnam … Lead with forensic finding: USIO adj. GM > GDOT adj. GM"` | same — offered to a real GDOT holder. |
| `"Lead with forensic finding: adj. GM advantage over peers"` | no such advantage exists on filing data. |
| `"USIO efficiency ratio 61.2 — #1 in peer group, more than double next-best (GDOT 30.0)"` | live: **31.2, rank 3 of 6**. PSFE (35.7) and RPAY (33.3) ahead. GDOT has no efficiency figure at all. |
| `"0.4x EV/Revenue vs peer median 2.3x — 82% discount not justified"` | EV/Revenue is **not comparable** here; it overstates the discount *because* USIO reports gross. |
| `"Eaton Vance … 0.4x EV/Revenue discount story resonates"` | same. |

All replaced with the filing-sourced position, and where a comparison is impossible
the text now says so rather than substituting a friendlier one.

### The factor-screen point was kept, with its reason

`"Low valuation factor: 0.4x EV/Revenue — cheapest in fintech peer group"` was NOT
simply deleted. A mechanical quant screen genuinely does use EV/Revenue, so USIO
really does screen cheap — *because* gross reporting inflates the denominator. That
cuts both ways and is worth knowing, so the text now says: the screen will rank it
cheap, a fundamental analyst will not, and the defensible figure is 3.2x EV/GP vs a
4.4x median.

### Three false positives, checked not assumed

- `# Q1: 23.8% | Q2: 34.7% | Q3: 17.9% | Q4: 23.7%` — **quarterly revenue seasonality
  weights**, not margins. The 23.8% collides with the workbook's USIO GM by coincidence.
  Legitimately derived from transcripts. Left alone.
- `"Revenue Est ($M): 28.4"` — an analyst estimate, colliding with the workbook's GDOT
  SBC figure. Left alone.
- One hit was my own corrective text matching the search pattern.

### Header added

app.py now opens by stating it is a legacy Streamlit prototype, that the live app is
`app_nicegui.py`, that **its analysis strings are hard-coded rather than computed**,
and lists the inverted claims with their corrections. Closing rule for the next
person: *"If you add analysis text here, hard-code nothing. Import from core/ so it
moves when the filings move. A number typed into a string is true only on the day it
is typed, and this file is the proof."*

---

## 2026-07-16 — **benchmarking_engine rebuilt: filing-only, less favourable, honest**

Client: *"we need to rebuild it, I think its not favorable but it has to be honest."*
Page 1 and page 3 of the same PDF contradicted each other, and page 1 was the flattering
one. Fixed at the source, so every downstream consumer (ir_plan, board_ir_report_pdf,
script_scorecard, Reports page) inherits it.

### The line that did the damage

```python
if fi.get("gross_margin") is not None:  gm, src = fi["gross_margin"], "filing"
elif yf.get("gross_margin"):            gm, src = yf["gross_margin"], "market"   # <-- here
else:                                    gm, src = curated.get("gross_margin"), "est"
```

A silent vendor substitution whenever EDGAR came up short — and every consumer treated the
result as filing-grade. **Gross margin/gross profit is now FILING ONLY** via `core.forensics`.
No market fallback, no curated estimate. A filer with no gross profit line gets `None` and
drops out of every margin-based comparison.

`_ev_gp` changed from `(EV/Rev) ÷ gross margin` to **`EV ÷ the filer's own gross profit`**.
Algebraically identical, but the old form inherited the margin's provenance and let the
vendor number in through the back door.

### What it cost (the honest direction — down)

| | before | after |
|---|---|---|
| USIO EV/GP | 3.5x | **3.2x** |
| peer median | 5.1x | **4.4x** |
| discount | 31% | **27%** |
| rank | #3 of 7 | **#3 of 6** |
| FOUR EV/GP | 5.9x (Yahoo 35.1%) | **6.9x** (filed 32.4%) |
| CASS EV/GP | 5.8x (Yahoo 47.6%) | **none — no gross profit line exists** |

### `median_gm` is now deliberately `None`

Every margin is filing-sourced, but they sit on **different bases** — USIO and FOUR report
gross, others net or mixed per-contract. A median of 23.1% (gross) and 75.0% (net) describes
no company and invites the exact comparison the report exists to prevent. Each firm's own
margin is still shown; the central tendency is not. The UI chart now says why instead of
rendering a bare chart with a missing median line.

### Latent bug found in `key_finding`

It asserted **"so the discount isn't a growth discount"** on BOTH branches — drawing the
favourable conclusion even while reporting that USIO grew *slower*. Only invisible because
USIO currently grows faster. The conclusion now follows the number.

Also corrected: "on raw EV/Revenue the gap looks even wider … flattered by gross-revenue
accounting" now says plainly that EV/Revenue **overstates how cheap USIO is and is not a
usable comparison**.

### `_efficiency` unified

Was `gross_margin ÷ EV/Revenue` — the same thing as `100/ev_gp` ONLY if both share a
revenue. They stopped doing so the moment margin came from the filing and EV/Rev from
Yahoo; the two drifted (FOUR by a full point). Now derived from `ev_gp` directly.

### 🔴 PERFORMANCE REGRESSION I INTRODUCED — AND FIXED

Wiring `forensics.filing_margin()` into `_resolve_company` meant **33 multi-MB companyfacts
HTTP fetches and 23 seconds per render** of the Peer & Market tab — it read as a hung page
and risked SEC's fair-access limits. `filing_margin()` calls `_fetch_companyfacts` directly,
bypassing `financial_summary()`'s cache, and is now called from `survey()`, `sbc_profile()`,
`sbc()` AND `_resolve_company()` — four fetches of the same JSON per ticker.

Added `forensics._facts()`: a locked, per-process, 6-hour TTL memo (in-process, not Postgres
— these payloads are megabytes). Negative results cached too. **33 fetches → 11; 23s → 0.1s
on repeat.** Numbers verified identical after caching.

### Nearly chased a ghost

`read_page` showed *"Connection lost / Message too long"* on the page and I started
diagnosing a websocket limit. It was NiceGUI's **permanently-present hidden popup markup**
from `index.html` — `read_page` with `filter:"all"` renders hidden elements. Checked
`aria-hidden` and `socket.connected` before acting: both fine, no error. The real cause of
the unresponsive UI was the 23s render above.

### Verified

- Reports → Peer & Market renders live; valuation comp, SBC panel and gross-margin note all
  present and matching the PDF.
- `peer_benchmarking_pdf`, `board_ir_report_pdf`, `ir_plan_pdf` all build.
- Page 1's peer table now shows no gross margin for CASS/GDOT, with a footnote explaining
  they don't report one — page 1 and page 3 finally agree.

### Open

- `app.py` (legacy Streamlit, not the live app) hardcodes demo-workbook claims:
  *"USIO efficiency ratio 61.2 — #1 in peer group, more than double next-best (GDOT 30.0)"*.
  Live: USIO **32.2, rank 3 of 6**; PSFE leads; GDOT has no efficiency at all. Dead code
  describing demo files — flagged, not chased.
- One stray `_fetch_companyfacts("FI")` still fires per render from somewhere despite FI
  leaving the peer set. Harmless (cached), but it means a stale peer list persists somewhere.
- Peer watch still lists an `FI · 8-K` filing from cache.

---

## 2026-07-16 — CASS/FOUR cost of revenue read → **range collapses to +37%**. SBC rebuilt → **third inversion**.

Went to the filings for CASS's and FOUR's cost of revenue (the open item that gated the
+4%/+45% range). Two opposite answers, both decisive.

### FOUR — discloses GAAP gross profit, just not in XBRL

FOUR stopped tagging `GrossProfit` after FY2021 because it stopped presenting the subtotal
on the face of the income statement. It still discloses it, in an MD&A reconciliation table.
**Its own footnote says so:**

> "Although gross profit is not presented on the Consolidated Statements of Operations, it
> represents the **most comparable metric calculated under U.S. GAAP** to non-GAAP gross
> revenues less network fees."

FY2025, verbatim from the table: `4,180 gross revenue − 2,199 network fees − 553 other costs
of sales − 74 depreciation of equipment under lease = **$1,354M gross profit → 32.4%**`.
Cross-checks XBRL exactly (`2,199 + 553 = 2,752` = the `CostOfGoodsAndServiceExcludingDDA`
tag). **Yahoo said 35.1% — 2.7pp too high.**

Carried in `_MDA_GROSS_PROFIT` **with a staleness guard**: `check.revenue` must reconcile
against live XBRL every run. If FOUR files a new 10-K, revenue moves, the check fails, and
the fact is reported `stale_mda` rather than silently applied to the wrong year. Hand-carried
data is what burned this module twice; the difference is that this one has an expiry, and
the guard is tested (faking FY2024 correctly produces "REFUSING to apply a stale
hand-carried figure").

**FOUR also discloses its network fees ($2,199M) — so its net-basis margin is computable:
68.3%.** That is precisely the disclosure USIO does not make. Concrete proof that the
interchange-disclosure recommendation is achievable: a direct peer already does it.

### CASS — the metric does not exist

CASS's 10-K uses the phrase **"gross profit" zero times.** "Cost of revenue", "cost of sales",
"cost of services" — zero, zero, zero. Its income statement is a bank's (processing fees
$66.1M + financial fees $40.4M + net interest income $81.2M, less operating expenses). There
is no cost-of-revenue line to derive a margin from.

**So Yahoo's 47.6% gross margin for CASS is a pure vendor construction with no filing basis.**
CASS leaves the EV/GP median because the metric doesn't exist for it — a fact about the
business, not a gap in our data. Same for GDOT.

### Result: the range collapses to a single defensible number

`valuation_comp` now computes **EV ÷ the filer's own gross profit** — one market input, one
filing input, no vendor margin in between. The engine's `ev_gp` (EV/Rev ÷ vendor margin) is
no longer used anywhere.

| | EV/GP | GM | basis |
|---|---|---|---|
| PSFE | 2.82x | 56.4% | derived (20-F) |
| RPAY | 2.98x | 75.0% | reported |
| **USIO** | **3.23x** | **23.1%** | reported |
| CSGS | 4.44x | 49.0% | derived |
| FOUR | 6.86x | 32.4% | 10-K MD&A |
| PAY | 11.19x | 24.8% | reported |

**Peer median 4.44x (n=5, all filing-backed) → implied equity $88.1M vs $64.3M → +37%.**
~~+4% to +45%~~ retired. `sensitivity()` now returns `None` and is kept wired as a live
tripwire: if any peer's gross profit ever falls back to a vendor number, the range reappears
in the headline automatically. Coverage 43% → **71%**.

### 🔴 SBC REBUILT FROM XBRL — THIRD INVERSION, SAME ROOT CAUSE

Client asked whether we'd used SBC as an indicator. We had — **inside the quarantine**, and
the conclusion was wrong. The workbook's numbers are plausible magnitudes but not accurate:

| | workbook | actual (XBRL) | |
|---|---|---|---|
| USIO | $1.8M | $1.7M | ≈ |
| FOUR | $89.4M | $82.0M | off $7.4M |
| GDOT | $28.4M | $18.7M | **overstated 52%** |

**The denominator is the whole argument.** The workbook measured SBC as % of REVENUE and
concluded USIO was "clean — small in absolute terms, so the add-back represents little real
dilution." Both halves fail:

- Absolute dollars are not a test. $1.7M is small because USIO is small.
- **"% of revenue" is the wrong basis for USIO specifically** — its revenue is GROSS, so the
  denominator is inflated by interchange it never keeps. That basis flatters USIO more than
  any other name in the set. The error is not neutral; it points one way.

On gross profit (presentation-invariant, the same logic that makes EV/GP work):

| | % of revenue | % of gross profit |
|---|---|---|
| PSFE | 1.9% | **3.4%** (leanest) |
| FOUR | 2.0% | 6.1% |
| PAY | 1.6% | 6.3% |
| CSGS | 3.7% | 7.5% |
| RPAY | 5.9% | 7.9% |
| **USIO** | **2.0%** | **8.9% — HIGHEST of 6** |

USIO moves from **rank 4 of 6 to rank 6 of 6.** The "lean SBC" story does not survive the
right denominator. SBC is not a point in USIO's favour — it is the largest in the peer set
relative to the gross profit the business actually generates.

### Verified

- All gates pass: every peer in the median is filing-backed; `sensitivity is None`;
  USIO SBC rank 6/6.
- Retracted strings confirmed absent from the generated PDF: `BEATS FOUR`, `clean on 3`,
  `Net reporter`, `net of interchange`, `+45%`, `5.10x`, `+4% to`.
- Staleness guard fires correctly under a faked stale year.

### Open

- USIO's own gross margin still has three defensible bases (FY XBRL **23.1%**, engine
  quarterly **20.2%**, Yahoo **22.5%**). The comp now uses FY consistently; the rest of the
  report does not. Pick one basis platform-wide.
- `benchmarking_engine.median_gm` still averages non-comparable margins — label or drop.
- Page 1's peer table still shows vendor gross margins for CASS/GDOT (47.6%/36.0%) that the
  forensics page says don't exist. Should show "—".

---

## 2026-07-16 — Valuation Comp section + CIK bug fixed + **two of my own claims corrected**

Client confirmed the workbook/board deck are **demo artifacts**, so nothing to unwind
externally. The quarantine stands; our live primary-source computation is the truth.
Fixed the two real bugs in OUR code that the investigation surfaced, then built the
Valuation Comp.

### 🔴 CORRECTIONS TO MY OWN CHANGELOG ENTRY BELOW

Two claims I logged yesterday were wrong. Correcting them rather than quietly editing:

1. ~~"`benchmarking_engine` uses the latest *quarter*, per-company, so the comp table
   compares mismatched periods across peers."~~ **FALSE.** Every peer's latest quarter
   resolves to `2026-03-31` — the periods ARE aligned. Measured before claiming this
   time; I had asserted it from reading the code, not from running it.
2. ~~"PSFE does not report a gross profit line."~~ **FALSE — my bug.** Paysafe is a
   **foreign private issuer**: it files **20-F and 6-K, never a 10-K**. My `_fy_facts`
   filtered on `form == "10-K"` and so never saw its filings. PSFE reports
   `CostOfGoodsAndServicesSold` $741M on `Revenues` $1,701M (FY2025) → 56.4% margin.
   `_ANNUAL_FORMS` now includes 20-F/40-F. GDOT and CASS genuinely have no cost-of-revenue
   tag, so those claims stand.

### Fixed: `resolve_cik` silently lost peers

`company_tickers.json` is **not exhaustive** (~10,426 tickers) and was missing **CSGS**
outright. It also still lists Fiserv under its **pre-2023 ticker FISV** — as does
`data.sec.gov/submissions/CIK0000798354.json` — so **FI** could never resolve either.

Both failures were **silent**: `resolve_cik` returned `None`, `edgar_financials` shrugged,
and the comp table showed a Yahoo margin for a company we appeared to have filing data for.

- Added a **browse-EDGAR fallback** with positive+negative caching (30d). It verifies the
  CIK actually belongs to the ticker via the submissions API before accepting it — a name
  match is not an identity match, and a wrong CIK would attribute another issuer's
  financials to a peer. Rejects and logs rather than guessing.
- `MANUAL_CIK_OVERRIDES["FI"] = 798354` — the only route, since SEC's own data is stale.
- Failures now **print loudly** instead of degrading quietly.
- Verified: all 11 platform tickers resolve; `FAKEXYZ` still correctly returns `None`.
- **CSGS now resolves to a filing-sourced 49.0%** — which independently matches the Yahoo
  figure exactly. Comparable peers went 2 → 4 of 7.

### NEW: `core/valuation_comp.py` + section in Reports → Peer & Market + PDF page 2

Built on **EV/Gross Profit**, the only multiple this peer set's accounting doesn't
distort. The algebra is the justification, and it's exact:

> `EV/GP = (EV/Revenue) ÷ (GrossProfit/Revenue) = EV/GrossProfit` — **revenue cancels.**

Whatever presentation basis a filer chose inflates revenue and cost of revenue equally,
leaves gross profit untouched, and drops out of the ratio. EV/Revenue and gross margin
are carried as **context only** and marked non-comparable on the face of the table.

Headline: **USIO 3.5x vs primary-peer median 5.1x → implied equity $93.4M vs $64.3M today,
+45%.** Full bridge printed (gross profit → × median → implied EV → + net cash → equity).
EV/EBITDA is deliberately never averaged — USIO's EBITDA is negative and the ~-292x
multiple would read as a data error in a board packet.

### 🔴 …but the +45% is NOT robust, and the report says so in the headline

`EV/GP = (EV/Rev) ÷ gross margin`, so **every peer's multiple inherits its margin's
provenance** — and the two peers sitting immediately above USIO are exactly the two whose
margins are NOT filing-backed:

| peer | EV/GP | GM basis |
|---|---|---|
| CASS | 5.8x | **market — reports no gross profit line at all**; the vendor constructs it from a mapping we cannot inspect |
| FOUR | 5.9x | **market — last filed gross profit is FY2021 vintage** |

The 6-peer median of **5.10x** literally straddles CSGS (4.4x, filing-backed) and CASS
(5.8x, constructed). Restrict the median to the **4 filing-backed peers** (PSFE, RPAY,
CSGS, PAY) and it falls to **3.65x** — barely above USIO's own 3.5x — and the implied
upside goes **+45% → +4%**.

So the stat box reads **"+4% to +45%"**, not a point estimate. The direction is solid;
the magnitude is an open question. Quoting the midpoint as fact would be the same species
of error as the workbook's. **Resolving it requires reading CASS's and FOUR's cost of
revenue out of their filings** — that is now the highest-value open item, and unlike the
GDOT one I recommended yesterday, this task is actually possible.

### Open

- **Read CASS's and FOUR's cost of revenue from the filings** → collapses the +4%/+45% range.
- FOUR: `GrossProfit` untagged since FY2021 — is there a differently-tagged cost line?
- The three engines still disagree on USIO's own gross margin: FY2025 XBRL **23.1%**,
  `benchmarking_engine` quarterly **20.2%**, Yahoo **22.5%**. All three are defensible on
  their own basis; the report should state ONE basis. Recommend FY or TTM consistently.
- `benchmarking_engine.median_gm` is still computed and displayed — it is a median of
  margins we now know are non-comparable. Should be labelled or dropped.

---

## 2026-07-16 — 🔴🔴 **THE SOURCE WORKBOOK IS FABRICATED. USIO IS A GROSS REPORTER.**

Went to source GDOT's reported gross margin from its 10-K (flagged earlier as "the
single highest-value hour of work"). GDOT **does not report a gross profit line at
all** — no `GrossProfit`, no `CostOfRevenue`, no `CostOfServices` in XBRL. It is a
bank holding company: Revenues ($2,080.5M FY2025) less total OperatingExpenses
($2,066.8M) straight to a 0.7% operating margin. **That task was impossible, and my
recommendation to do it was wrong** — the workbook's "GDOT reported_gm 40.5%, 10-K
p.71" cannot have come from a 10-K, because the line does not exist.

Pulling that thread collapsed the entire analysis.

### 🔴 THE WORKBOOK'S 10-K CITATIONS ARE FABRICATED

`USIO_Peer_Benchmarking_Report_v2_2.xlsx` ("Footnote Forensics" sheet) presents
verbatim, page-cited 10-K quotes. **Not one of them exists in the source filing.**
Verified by fetching each 10-K from EDGAR and string-matching:

| Workbook's "verbatim quote" | Primary source |
|---|---|
| USIO 10-K p.58: *"Revenue is recognized net of interchange and network fees."* / *"USIO is a true net reporter"* | **NOT PRESENT.** 10-K filed 2026-03-18 says: *"complies with ASC 606-10 and reports revenues at **gross as a principal** versus net as an agent"* and *"reported **gross of** amounts paid to sponsor banks as well as **interchange** and assessments."* The string "net of interchange" appears **nowhere** in USIO's 10-K. |
| RPAY 10-K p.38: *"Revenue recognized net of interchange."* | **NOT PRESENT.** RPAY runs a per-contract principal/agent evaluation under ASC 606-10-55-36 to -40 — judgment-based and MIXED, not a blanket "net reporter". |
| FOUR 10-K p.94: gross incl. ~$1.8B interchange pass-through | **NOT PRESENT.** FOUR's actual text is mixed: *"TFS revenue is recognized net, as the Company is considered an agent."* |

The workbook has the *form* of forensic work — page numbers, quotation marks, ASC
references — with invented content behind it. `USIO_Peer_Benchmarking_Board_Deck.pptx`
sits in the same folder, built from it.

### 🔴 RETRACTION — "USIO IS CLEAN ON 3/3 DISTORTIONS" IS INVERTED

**USIO is the gross reporter.** Its ~23% gross margin is depressed by its OWN
presentation — the exact mechanism the workbook attributed only to peers. Everything
built on the opposite premise is withdrawn:

- ~~"USIO is clean on 3/3 — our reported figures already ARE the adjusted ones"~~ — false.
- ~~"USIO looks worse than it is because peers report gross"~~ — **backwards.**
- ~~"The RPAY gap is real economics — forensics cannot argue it away"~~ — false; USIO (gross)
  and RPAY (mixed/net) are not on a common basis, so the 55.9pp gap is not economics.
- ~~"USIO BEATS FOUR after adjustment"~~ — already retracted above for a different reason.

**Our own codebase had it right the whole time.** `core/edgar_financials.py:279` has
said since it was written: *"Because we present revenue gross of interchange, the
comparable figure to net-revenue peers is our gross profit."* My seed file contradicted
the codebase and I did not check. `benchmarking_engine`'s EV/Gross Profit ranking was
correct all along — gross profit is invariant to gross-vs-net presentation, because
interchange inflates revenue and cost of revenue equally.

### A SECOND INVERTED CONCLUSION, SAME ROOT CAUSE

The workbook's Disclosure Gap sheet claims USIO earns **"~$2.07 per $100 of volume vs
RPAY $1.06 — shows premium positioning."** USIO's $2.07 is a **gross** take rate
(interchange included); RPAY's $1.06 is **net**. Strip ~1.5% interchange and USIO is
~$0.5–0.6 — **below** RPAY. The workbook's own disclosure-gap analysis also **omits the
single most consequential gap USIO has: interchange disclosure.**

### THE REAL FINDING (verified, and more useful than the false one)

**USIO discloses no interchange dollar amount anywhere in its 10-K.** Its net-basis
margin therefore **cannot be computed from public filings — by us or by any analyst.**
Only the CFO can, from internal data. That is a genuine, actionable IR recommendation
and it is the *opposite* of the workbook's conclusion.

### Actions taken

- **`data/seed/peer_forensics.py` QUARANTINED** → `data/seed/quarantine/peer_forensics_QUARANTINED.py`,
  unmodified beneath an evidence banner. Nothing imports it. Because the one claim that
  could be independently checked was fabricated — and then the next two also were — **no
  entry in it may be treated as fact.**
- **`core/forensics.py` rebuilt from primary sources only.** No seed, no fallback estimate.
  Every fact resolves to a filing the code fetched itself, or reports UNKNOWN. `None` is
  a valid answer and renders as one.
- UI panel + PDF section rewritten to lead with **what cannot be claimed**. Verified: the
  strings `BEATS FOUR`, `clean on 3`, `Net reporter`, `net of interchange`, `23.8%`,
  `21.8%`, `57.5%`, `40.5%` are all **gone** from the generated PDF.
- Page 1's pointer corrected — it promised a restatement that is impossible.

### Collateral findings — the comp set is far thinner than represented

Only **2 of 7** primary peers have a current, filing-sourced, period-aligned gross margin:

| | status |
|---|---|
| USIO 23.1%, RPAY 75.0%, PAY 24.8% (FY2025) | usable |
| **FOUR** | last tagged `GrossProfit` in **FY2021** — the engine's 35.1% is yfinance, not a filing |
| **GDOT, CASS, PSFE** | **never report a gross profit line** |
| **CSGS** | **`resolve_cik("CSGS")` returns `None`** — no EDGAR data at all (this is the `$CSGS: possibly delisted` log noise flagged earlier; it is a real bug, not noise) |

### Caught before it printed (my own bug)

A first pass paired FOUR's **FY2021** gross profit ($278.4M) with its **FY2025** revenue
($4,180M) and produced a nonsense **6.7%** margin. `filing_margin()` now requires gross
profit and revenue from the **same period** or returns nothing.

### 🔴 OPEN — NEEDS A HUMAN DECISION

1. **The board deck built on this workbook is wrong.** Its central claim inverts USIO's
   own revenue recognition. If it has been shown to the board or anyone external, that
   needs unwinding. **Not my call — flagged and stopped.**
2. **Where did the workbook come from?** If it was machine-generated, the generator
   fabricates citations and anything else it produced is suspect.
3. **`resolve_cik("CSGS")` returns None** — real bug, affects page 1's EV table.
4. **The three engines disagree on USIO's own gross margin**: FY2025 XBRL **23.1%**,
   `benchmarking_engine` **20.2%** (it uses the latest *quarter*, per-company, so the
   comp table compares mismatched periods across peers), workbook **23.8%**. Needs a
   single defined basis — recommend FY or TTM, consistently.
5. **Recommended IR action:** disclose interchange. It is the only way any analyst can
   put USIO on a comparable basis, and it is absent from the workbook's disclosure-gap list.

---

## 2026-07-16 — Footnote Forensics rebuilt LIVE + **RETRACTION: "USIO beats FOUR"**

Rebuilt the Peer Benchmarking report's Footnote Forensics against OUR curated peer
set (`core/forensics.py`, `data/seed/peer_forensics.py`), surfaced in
**Reports → Peer & Market Analysis** and printing as page 2+ of
`peer_benchmarking_pdf()`. Verified live in the UI and in the generated PDF.

### 🔴 RETRACTION — a false claim reached a board packet before it was caught

The first cut of `core/forensics.py` took **reported margins from the seed workbook**
(`USIO_Peer_Benchmarking_Report_v2_2.xlsx`, June 2026) and concluded:

> "**USIO BEATS FOUR** — FOUR reported 32.1% → adjusted 21.8%, below USIO's 23.8%."

**That finding is false.** It was an artefact of stale data. It was verified,
written into the module, rendered into the UI, and generated into a PDF before a
consistency check against page 1 of the same document caught it.

The workbook disagreed with the live filings on **every covered ticker**:

| | live (filings) | seed (workbook) | delta |
|---|---|---|---|
| USIO | 20.2% | 23.8% | −3.6pp |
| RPAY | 76.1% | 57.5% | **+18.6pp** |
| FOUR | 35.1% | 32.1% | +3.0pp |
| GDOT | 36.0% (est) | 40.5% | −4.5pp |

On live figures USIO is **20.2% vs FOUR's adjusted 24.8% — 4.6pp BEHIND, not 2.0pp
ahead.** USIO beats **nobody** after adjustment. `beats_after_adjustment()` now
returns `[]`, and that empty list is a result, not a failure.

**Root cause:** mixing a live report with a frozen seed. **Fix:** the two sources are
now split by what each is actually good for —

- **Reported margin** — LIVE from `benchmarking_engine`, the same call that renders
  the peer table. The forensics page can no longer contradict the table two pages earlier.
- **Distortion** — from the seed: accounting *policy* read out of each 10-K with the
  citation. Stable across quarters, and not derivable from a margin figure.
- `adjusted = live_reported + policy_distortion_pp` — disclosed as an approximation
  (the FY2025 policy effect carried onto the current margin), not a restatement.

### What replaced the false finding

- **`closes_on()`** — the honest version of the same point, and it still reprices the
  stock: the gap to **GDOT closes 14.4pp** (15.8 → 1.4) and to **FOUR closes 10.3pp**
  (14.9 → 4.6). USIO doesn't overtake either; the residual is real and stated.
- **`like_for_like_peers()`** — added deliberately: **a forensics page that only ever
  narrows gaps is advocacy, not analysis.** RPAY is already a net reporter on USIO's
  basis, so no adjustment applies — **76.1% vs 20.2% is a 55.9pp gap in the economics,
  not the accounting.** RPAY is also USIO's closest operating analog (per the report's
  own key finding). Forensics cannot argue this away, and the CFO will be asked it.
- **`sensitivity()`** — GDOT is held out of the group figure because our only *live*
  source for its margin is our own estimate (`gm_source == "est"`); applying a −14.4pp
  forensic adjustment to a number we guessed manufactures precision. But an exclusion
  rule that quietly suppresses the *more favourable* answer is as suspect as one that
  suppresses the less favourable, so the sensitivity is disclosed: **admitting GDOT
  takes n to 3 (a real median) and moves the swing +5.1pp → +11.2pp.**
- **`_gm_read()` / `closes_on()` qualifiers** — "most" is a claim about a ratio, not a
  figure of speech. Now computed from the share closed (>50% "Most", >25% "A material
  part", else "Some"). The group read had said "most of the shortfall is presentation"
  when the adjustment closed only **15%** of it.

### Honest state of the analysis

- Group figure is **n=2** (RPAY, FOUR) and labelled **"average of 2"**, not "median" —
  with n<3 a median is a dressed-up average. The prose points the reader at the
  pairwise rows instead: averaging a 76%-margin net reporter against a 35% gross
  reporter produces a number that describes no company.
- Coverage **43%** of the primary comp set. `CASS/CSGS/PAY/PSFE` have no 10-K work —
  **excluded** from adjusted figures rather than assumed clean. `PRTH/EEFT` have the
  work but the peer tiering dropped them — context only, never entering a median.
- USIO **clean on 3/3** distortions (net reporter · expenses software as incurred ·
  $1.8M SBC) — this survives, and is the one part of the original thesis that holds.

### Open items

- **Highest-value missing work:** source GDOT's reported gross margin from the 10-K
  (seed cites p.71 at 40.5%). One number takes the analysis to a real median.
- 10-K forensic work for CASS, CSGS, PSFE, PAY (the four coverage gaps).
- `$CSGS: possibly delisted; no price data found (period=5d)` recurring in the server
  log — yfinance fetch for CSGS is flaky; its 49.0% margin is `market`-sourced. Not
  yet load-bearing (CSGS is a coverage gap, out of the forensics medians), but it
  feeds the EV table on page 1. **Unverified — needs a look.**

---

## 2026-07-16 — Coverage-network prospecting: quality gates (the Optiver problem)

- **Problem:** the Automated Prospecting Pipeline had NO filtering at all — its
  only exclusion was `known_fund_names`. It dumped every cached 13F holder of the
  analyst's coverage stocks at the IR lead, surfacing **Optiver** (a market
  maker), **Wells Fargo**, and RIA aggregators (Focus Financial, NewEdge) as
  "prospects". This predated the conviction/denylist work done for Peer Prospects
  and never received it.
- **Fix — shared denylist, one source of truth:**
  - `peer_prospects._is_passive` → public **`is_passive()`** (alias kept for
    existing call sites), so BOTH prospect surfaces filter off one list.
  - Extended `_PASSIVE` from 33 → ~60 entries, now grouped: index/passive,
    **market makers/HFT** (optiver, flow traders, virtu, jane street, imc, drw,
    jump, hudson river, xtx, gamma investing…), banks, and **RIA aggregators /
    wealth platforms** (focus financial, newedge, captrust, creative planning,
    cetera, lpl, osaic…) — they hold via client accounts, so there's no PM to
    pitch.
  - `prospecting.generate_coverage_prospects` now applies `is_passive()` plus a
    generic **breadth gate** (`_MAX_BREADTH = 800` positions → index/quant
    sleeve), and returns `filtered_passive` / `filtered_breadth` counts.
  - UI shows what was removed ("N filtered out as passive / market-maker /
    aggregator noise") so a short/empty list reads as the filter working, not the
    pipeline being broken.
- **Verified:** all 5 prior suggestions filtered (5/5 were noise → 0 survive) and
  **zero false positives** — Perkins, Royce, Ancora, Hodges, Eagle, ArrowMark,
  Wellington, Kayne Anderson all pass through unfiltered.
- **Data starvation FIXED — coverage-network 13F pull:**
  - `sec_filings.coverage_tickers(cid)` — analyst coverage-network tickers as
    (ticker, name), minus anything already a peer. `holder_pull_tickers()` =
    peers + coverage. Deliberately separate from `tracked_tickers()` so these
    NEVER enter the valuation peer set / medians (verified: CP() unchanged at
    RPAY…TOST; zero leak).
  - Settings "Full investor universe" pull now uses `holder_pull_tickers()` —
    one ~100MB scan fans out to all 20 issuers, so the 9 coverage tickers are
    nearly free.
  - **Pull run (49s):** coverage network 5 unusable records → **569 holders with
    real share counts**. AEYE 5→90, VERI 0→96, PRTH 0→117, DPRO 0→68, KSCP 0→67,
    GCTS 0→61, WYY 0→37, INUV 0→30, FPAY 0→3 (genuinely tiny holder base).
  - **Pipeline result: 0 → 22 real prospects** (32 filtered passive/MM, 83
    filtered extreme-breadth). Surfaced **Kennedy Capital Management (823k sh
    AEYE)**, Skylands, Formula Growth, 683 Capital, Thompson Siegel & Walmsley,
    Banta — real small-cap PMs, exactly the intended output.
  - Denylist extended again from live results: `headlands technologies` (HFT) and
    ETF issuers (`themes management`, global x, first trust, wisdomtree,
    direxion, proshares, exchange traded concepts). Re-verified zero false
    positives against 8 known-good names.
- **RIA/wealth split into its own bucket (not dropped):** an RIA that owns an
  adjacent name isn't noise — it's just not an NDR target (no PM to pitch). So
  the taxonomy is now three-way instead of two:
  - `is_passive()` — index / market-maker / bank / ETF-issuer → **dropped**.
  - `is_ria()` — `_RIA_NAMES` (aggregators, moved OUT of `_PASSIVE`) plus
    `_RIA_PATTERNS` generic substrings ("wealth management|wealth advisors|
    financial strategies|financial planning|advisory services"…). Kept narrow on
    purpose: "capital management"/"asset management" are NOT patterns, since
    that's what real institutional PMs are called.
  - `is_excluded()` = passive OR ria, for surfaces with no RIA bucket;
    `_is_passive` alias now points here so peer_prospects keeps its old
    all-in-one behaviour.
  - `generate_coverage_prospects` routes RIAs to a new `ria_holders` list —
    **only when a real position backs the name** (`size_known` and shares > 0),
    ranked by size. UI renders them in a collapsed "RIA / wealth managers holding
    these names (N)" expansion with its own ADD (tags style "RIA / wealth
    manager"). Removed the empty-prospects early-return so the bucket still shows
    when there are 0 institutional targets — "no PMs, but 6 RIAs own it" is a
    real answer.
- **Video-call tier for RIAs (low-touch routing):** an RIA doesn't warrant
  management travel — an assistant can set up a video call. So the tier is now
  enforced, not just labelled:
  - `_open_add_to_trip_dialog` checks `peer_prospects.is_ria(fund)` and defaults
    the meeting Format to **Zoom** instead of In-person, with an amber
    "video-call tier — an assistant can set this up" hint. Because the format is
    virtual, these also never enter the itinerary's driving-distance calc or
    consume a routed leg.
  - RIA-bucket ADD tags the prospect `touch: "video-call"` /
    `outreach: "Video call — assistant can schedule"` so the tier travels with
    the record.
  - This also settles the PNC/Stifel boundary question: whichever side of the
    RIA line they fall on, they get the same low-touch video treatment, so the
    classification no longer needs to be perfect.
  - Verified: 8 RIA names (LPL, Summit, Focus, Creative Planning, Stifel, PNC,
    Ritholtz, Golden State) → Zoom/assistant; 6 institutional names (Kennedy,
    Skylands, Banta, Royce, Ancora, Wellington) → In-person.
- **Kennedy Capital added to the prospect queue** (2 → 3) with its real
  SEC-sourced office — 10829 Olive Blvd, St Louis, MO 63141 (CIK 0000884589) —
  written into the address book and metro resolved, so it routes on any NDR.
- **False positive caught & fixed (MFS):** the generic `"financial services"`
  RIA pattern swept up **`MASSACHUSETTS FINANCIAL SERVICES CO /MA/` = MFS
  Investment Management**, a top-tier institutional manager already in the seed
  universe (the SEC legal name never matched the seed's "MFS Investment
  Management", so the known-name exclusion didn't save it either).
  - Dropped `"financial services"` as a pattern; firms that genuinely belong
    (PNC) are now named explicitly in `_RIA_NAMES` instead.
  - Added `_INSTITUTIONAL_ALLOW` (massachusetts financial services, fiduciary
    management, eagle asset management, brandywine global), checked FIRST in
    `is_ria()` so a real manager can never be demoted by a name pattern.
  - Re-verified: MFS/Eagle/FMI → institutional; PNC/Commonwealth/Corient/Motley
    Fool/Bragg/Warther/LPL/Transamerica → RIA; 10 known-good institutional names
    → zero false positives.
- **Peer Prospects gets the RIA bucket too (the 225 question, resolved):**
  - `build_candidates(..., kind="institutional"|"ria")`. Passive still dropped
    outright; RIAs now routed to their own bucket instead of discarded. **No
    breadth gate on the RIA path** — a wealth platform holding thousands of
    positions is normal, so breadth says nothing about them; only a real
    position (`peer_value > 0`) qualifies. Ranked by position size, conviction
    left `None` (they aren't scored as targets).
  - `counts()` gained `rias`; the tab shows a 4th "RIA / wealth" card and a
    collapsed "RIA / wealth managers holding your comps (64)" expansion with
    Promote/Dismiss, same video-call copy as the coverage-network bucket.
  - **Bug caught in verification:** `promote()` did `int(candidate["conviction"])`
    — which crashes on an RIA (conviction is None by design). Now falls back to
    0 and tags `touch: "video-call"` / `outreach` / `style: "RIA / wealth manager
    — holds …"` / `source: "Peer overlap (13F) — RIA"`. Exercised the real
    promote path end-to-end (Bragg Financial) to confirm.
  - **Count reconciliation:** the bucket list was capped at 60 while the card
    said 64 — the header silently hid 4. Limit removed; header now matches the
    card exactly.
  - **64, not 225:** the earlier raw survey counted every peer including the
    three **reference-tier** mega-caps (FI/GPN/TOST), which are deliberately
    excluded from prospecting, and didn't dedupe by CIK or suppress existing
    holders. 64 is the real, deduped, prospecting-tier number.
- **RIA coverage audit (answers "did we get them all?"):** no repull needed —
  all 20 issuers are cached from the 49s pull. But RIAs are only *surfaced* from
  the coverage network; `peer_prospects.build_candidates` still **discards**
  them via `is_excluded`. Survey of the cached data: coverage network = 209
  institutional / 33 RIA / 28 passive; **peer network = 1,544 institutional /
  225 RIA / 40 passive — those 225 RIAs are currently thrown away** (Ameriprise
  7.8m GPN, LPL 781k FI, Corient 398k FI, Creative Planning 364k FI…). Open:
  give Peer Prospects the same RIA bucket so they surface.
- **Final split verified live:** 17 institutional prospects (Kennedy Capital
  823k AEYE, Banta 2.46m VERI, Skylands, Formula Growth, Thompson Siegel, 683
  Capital) · 24 RIA/wealth holders (LPL 188k, Summit Financial, Focus Financial,
  Creative Planning, Ameriprise, Ritholtz, Stifel, PNC… down to 3 shares) · 26
  passive/MM/ETF + 70 extreme-breadth dropped. Over-filter guard re-run: all 16
  known-good institutional names still pass.

- **Original deeper issue (now resolved, kept for context):**
  Of Scott Buck's 8 coverage stocks, only AEYE has any cached 13F holders (5, all
  `size_known=False` from the limited EDGAR full-text path); **FPAY — his highest
  relevance stock at 95 — has zero**. The bulk-13F pull set is the *valuation peer
  universe* (USIO/RPAY/CASS/…), which deliberately contains none of the
  coverage-network tickers. Proposed: pull bulk 13F for coverage-network tickers
  as a set SEPARATE from the valuation peers (so the curated comp set stays
  clean), giving the filters a real pool to work on — the same fix that took RPAY
  from 17 → 145 holders.

---

## 2026-07-16 — Target Database: collapsible search + the 5-vs-2 reconciliation

- **Collapsible search (`_render_target_db_tab`):** the 91-row result list
  dominated the tab, so search + results now live in a `ui.expansion`
  ("Search by fund name"), collapsed by default — the four cards are the
  summary. It auto-opens on a card-filter click or a global-search prefill, so a
  filtered list is never stranded behind a closed panel. The initial
  `do_search()` deliberately does NOT open it (that would defeat the default).
- **"5 prospect(s) found" vs the "2 Prospects" card — NOT a bug, a naming
  collision.** They're disjoint by construction: the Automated Prospecting
  Pipeline passes `known_fund_names` (all 89 tracked + 2 added = 91) as an
  exclusion set, so its suggestions are *by definition* names not in the
  database. Verified: prospects.json = 2 (Potomac, Harbor Capital); all-targets
  card = 89 + 2 = 91; pipeline excludes all 91.
  - Relabelled to "**N new suggestion(s) — not in your database yet**" with a
    subline explaining already-tracked/added funds are filtered out and that ADD
    moves one into the Prospects count.
  - Prospects card subtitle "Manually added" → "**Added to database**" (it also
    holds pipeline-ADDed names, so "manually" was inaccurate too).

---

## 2026-07-15 — NDR: Jitsi one-click meeting links (zero-setup)

- **`core/jitsi_meetings.py` (new):** `create_link(label)` mints a free Jitsi
  URL (`https://meet.jit.si/<slug>-<random token>`) — no account, no API, no
  credentials. The random token keeps the room unguessable (privacy comparable
  to an unlisted link). Optional `jitsi_domain` in settings.json points at a
  self-hosted / JaaS instance for enforced auth; link format is unchanged.
- **`investors_page` edit dialog:** "Generate Jitsi link" button (visible when
  format = Jitsi) mints the link, writes it to the meeting, and persists — sync,
  instant, no network. "Jitsi" added to all three format selects. Flows into the
  itinerary (`Join (Jitsi): …`) and .ics (LOCATION:Jitsi + URL) like any virtual
  stop.
- **Verified end-to-end in-app:** set a meeting to Jitsi, clicked Generate → a
  real `meet.jit.si` link populated the field and persisted to ndr_trips.json.
  (Also surfaced the known external-write cache-staleness: presetting data from a
  separate process needs a server restart for the running app to see it.)

- **`core/zoom_meetings.py` (new):** creates Zoom meetings via Server-to-Server
  OAuth (JWT is deprecated). `is_configured()` gates on the three creds
  (settings.json `zoom_account_id/zoom_client_id/zoom_client_secret` or ZOOM_*
  env). `_token()` fetches + caches the ~1h bearer; `create_meeting(topic,
  start_utc, duration, tz)` → {join_url, id, start_url}; `test()` creates+deletes
  a throwaway meeting to validate creds AND the meeting:write scope. Surfaces
  Zoom's own error message on failure. Free with any Zoom account.
- **`core/ndr_calendar.py`:** extracted `meeting_datetime()` + `tz_name_for()` so
  the .ics export and Zoom creation place a meeting at the same instant.
- **`settings_page`:** "Zoom meetings — auto-create join links" section (Account
  ID / Client ID / Client Secret, secret masked) with Save + Test. Verified
  rendering.
- **`investors_page` edit dialog:** "Create Zoom meeting" button (visible only
  when format = Zoom) computes the meeting's UTC start, calls Zoom in a worker
  thread, writes the returned join link + `zoom_meeting_id` back to the meeting,
  and persists immediately so a created meeting is never orphaned. Verified the
  button renders in the dialog. Teams/Meet stay on the paste-a-link path.

- **`core/ndr_calendar.py` (new):** `build_ics(trip, ticker, contacts, address_for)`
  emits an RFC 5545 iCalendar with one VEVENT per meeting.
  - **Timezone-correct, not floating:** a meeting's wall-clock time is
    interpreted in the trip city's zone (`_METRO_TZ` → IANA, via `zoneinfo`) and
    emitted as a UTC instant, so it displays at the right local time in any
    attendee's calendar. Verified: NY 9:00 AM → 1300Z (EDT), LA 9:00 AM → 1600Z
    (PDT).
  - Virtual stops → `LOCATION: <format>` + `URL:` join link + link in
    DESCRIPTION; in-person → street address (own or from the fund address book).
  - Unscheduled meetings (time "—") become an all-day placeholder on their day.
  - RFC-compliant escaping + 75-octet line folding (byte-safe for emoji); every
    physical line verified ≤75 octets.
- **`investors_page`:** "Add to calendar (.ics)" button beside the itinerary
  export; downloads `<trip>.ics`. Verified rendering in-app.

---

## 2026-07-15 — NDR: virtual meetings + join links on the schedule

- **Meeting model gains `meeting_link`** and a "Virtual" format option. Both
  add-meeting forms now show a link field (bound-visible only when format ≠
  In-person) and persist it.
- **Edit existing meetings:** new ✎ dialog per row in Active NDRs — time (with
  clock picker), format, address, and the join link. This is how a stop is made
  virtual and its link pushed to the schedule after the fact.
- **Itinerary rendering:** virtual stops show `Join (<format>): <link>` in the
  .txt and a clickable `<a>` in the print HTML; "link TBD — add on the Active
  NDRs tab" when empty. In-app rows show the clickable link or an amber "link
  TBD" nudge. Routing already skips non-In-person stops, so virtual meetings add
  no travel legs.
- **Applied to the NY trips:** Ancora (Cleveland) and Vanguard (Malvern) set to
  Virtual on the Post-Q2 NY NDR (Ancora also on the Wainwright Conf). The 686-mi
  long-haul flags are gone; BlackRock (50 Hudson Yards) and Royce (One Madison)
  remain the genuine in-person NYC stops. Verified end-to-end in-app: opened the
  edit dialog, pasted a link, saved → persisted to `ndr_trips.json` and appeared
  on the itinerary as a Join line.

---

## 2026-07-15 — Fund address book (SEC-by-CIK) for NDR routing

- Routing only produces real driving miles when a stop has a street address;
  typing one per meeting doesn't scale. Added a canonical, per-fund address book.
- **`core/fund_addresses.py` (new):** db-backed store (`fund_addresses.json`).
  - `address_for()` / `record_for()` with exact + normalized-name matching;
    `set_address()` for manual entry; `coverage()` for a have/total readout.
  - `refresh_from_sec(name_cik_pairs)` — the systematic backbone: pulls each
    filer's **SEC business address BY CIK** (exact, no name guessing; every
    13F/13D-G filer already carries a CIK). Preserves manual/seed entries.
  - Hand-verified `_SEED` for the near-term NDR-calendar funds so those trips
    route before any pull. **Name→CIK lookup deliberately excluded** — it
    false-matches ("BlackRock" → an Isle-of-Man subsidiary; "Vanguard Group" →
    no hit), the same matching hazard as the RPAY 13F gap.
- **Resolution order (`investors_page._meeting_street`/`_meeting_loc`):** meeting
  address override → fund address book → metro/city. Routing gate now keys off
  the resolved street, so a fund's stored address routes meetings with no typed
  address.
- **`settings_page`:** new "Fund office addresses (SEC EDGAR, by CIK)" data pull
  walks cached 13F filers → `refresh_from_sec`. Verified live: Whittier→South
  Pasadena, Citadel→Brickell, Renaissance→Third Ave — all exact. (Fixed a
  tuple-unpacking bug — `tracked_tickers()` yields (ticker, name).)
  `refresh_from_sec` now checkpoints every 25 records so a long full-universe
  pull survives interruption.
- **Ran the USIO pull:** 28 addresses in ~12s. Coverage — **USIO holders 30/34
  (88%)** on file (the 4 gaps are foreign filers with no US street in EDGAR);
  full live universe 33/89 (the 56 missing are non-filer prospects with no CIK,
  which fill when they file or via manual entry).
- **Data-quality catch (the point of real addresses):** seeding the four NY-trip
  funds exposed the "Post-Q2 New York NDR" as **686 driving miles** — Ancora is
  Cleveland OH (456 mi leg) and Vanguard is Malvern PA (116 mi), not NYC. The
  itinerary now flags each as long-haul + TIGHT. BlackRock (50 Hudson Yards) and
  Royce (One Madison Ave — SEC-current, they moved from 745 Fifth) are genuine
  NYC.

---

## 2026-07-15 — NDR: real routed driving distance/time (OpenRouteService)

- Upgrades the offline great-circle travel estimate to **real driving miles and
  time** when an API key is present; falls back to offline automatically.
- **`core/routing.py` (new):** OpenRouteService integration.
  - Key from Settings (`settings.json` → `routing_api_key`) or `ORS_API_KEY`
    env. `is_configured()` gates everything; no key → callers use `geo.leg()`.
  - `geocode()` (`/geocode/search`) address→[lon,lat], cached in
    `routing_geocode.json`; `leg()` (`/v2/directions/driving-car`) returns real
    driving distance/duration, cached in `routing_legs.json`. Metro labels map
    to a geocodable "City, ST" so metro-only stops still route.
  - Best-effort: any error/timeout/unresolved address → None (caller falls
    back). Misses aren't cached, so fixing the key works without a restart.
  - `test()` powers the Settings Test button (geocode + route a sample).
- **`investors_page._travel_leg_between`:** tries `routing.leg()` first, falls
  back to `geo.leg()`. New `_travel_total_line()` labels the trip total honestly
  by basis — "real driving miles/time, routed via OpenRouteService" vs the
  straight-line caveat (and, mixed, says how many legs were routed).
- **`settings_page._render_routing_key`:** Settings → Data Sources now has an
  OpenRouteService key field (password-masked) with **Save key** + **Test**
  (green ✓ / red ✗ with the sample leg). Verified rendering in-app.
- **Geocoding accuracy fix (found live):** with a real key, "745 5th Ave, New
  York" geocoded to *Brooklyn's* 5th Ave — a ~10 mi error between two Midtown
  stops. Pelias needs a location bias, and a generic city center isn't enough
  (NYC resolves to City Hall, ~equidistant to Brooklyn's 5th Ave). Added
  `_METRO_FOCUS` — a **business-district** (lat,lon) per tracked metro (Midtown,
  the Loop, FiDi, Center City, …) — and `focus_for()`; `geocode()`/`leg()` now
  take a `focus.point` bias (with `boundary.country=US` for US trips) and cache
  by query+focus. `_travel_leg_between` passes the trip's district focus. Result
  on the same NY day: legs now ~1.0 mi / 3 min (correct), ~2 mi total.
- **Address-gating fix (found in spot-check):** meetings without a street
  address made both endpoints collapse to the trip city → a misleading "0 mi ·
  0 min routed." Now routing runs only when BOTH stops have a real address (plus
  a <0.1 mi guard); otherwise it uses the honest offline "same city — allow ~20
  min" allowance. `_travel_total_line` gained `routing_on`: when a key is set
  but legs weren't routed, it nudges "add a street address to each meeting"
  rather than "add a key." Verified against the 5 real trips: LA (Wilshire /
  Downtown / Century City = 36 mi, accurate), Dallas Uptown/downtown (~1 mi
  legs), Austin correctly on Day 2, NY days show the local-transit allowance.

---

## 2026-07-15 — NDR: schedule-on-add clock + itinerary travel calc

- **Request:** adding an investor to a trip should ask *what time* (a clock,
  flexible for travel), and — nice-to-have — the itinerary should show miles
  between stops, the way a bank's roadshow-logistics desk works.
- **Time picker on quick-add (`investors_page`):** the "Fill this trip" quick
  "Add to trip" button no longer silently drops the investor in at `time="—"`.
  It now opens `_open_add_to_trip_dialog` — Day, a **clock time picker**
  (`_time_picker_input`, the same `ui.time`-in-a-menu the manual form uses),
  Format, and an optional Address that powers the travel calc. The meeting also
  stores its `metro` so travel can resolve a city even with no street address.
- **Itinerary travel legs (`core/geo.py`, new):** honest, offline, zero-dep.
  - Resolves each stop to a **city** (from address → metro → trip city) against
    a built-in coordinate table (every tracked metro + USIO's 13F filer cities +
    financial hubs) and computes **great-circle miles**; same-city stops get a
    nominal local-transit allowance; >75 mi legs are flagged inter-city
    (flight/rail). Everything is labelled "straight-line, city-level — not
    driving miles" so it's never mistaken for odometer/routed miles.
  - `_build_ndr_itinerary` (txt) + `_build_ndr_itinerary_html` (print) now sort
    each day's meetings **chronologically**, insert a travel line between
    consecutive in-person stops, **flag TIGHT connections** (gap < drive + 30 min
    turnaround), and print an est. trip travel total.
  - Real routing (Google/Mapbox Distance Matrix) can slot behind `geo.leg()`
    later without touching callers — noted in the module docstring.
- **Housekeeping:** removed one stray unscheduled "Bandera Partners" meeting
  from the NY NDR trip (residue of an earlier click-through; `time="—"`, no
  address/metro).

---

## 2026-07-15 — Fix: lazy tab could hang on a permanent spinner

- **Symptom:** clicking NDR Planner spun forever. **Cause:** a *stale client* —
  the server was restarted while the page stayed open, so the browser's socket
  pointed at the dead process. In `_load_tab_on_demand`, the tab was flagged
  `loaded` *before* building, and `nav.tab_changed()` → `render_nav()` raised
  "client has been deleted" *before* `build_fn()` ran → spinner never replaced,
  and re-clicking was a no-op (already "loaded").
- **Fix (`investors_page._load_tab_on_demand`):**
  - `nav.tab_changed()` wrapped in try/except (a stale-client nav error no
    longer aborts the build).
  - `loaded_tabs.add(name)` moved to *after* a successful build.
  - `build_fn()` wrapped: on failure the spinner is replaced with an error +
    "Reload page" button, and the tab is left unmarked so re-selecting retries.
  - Immediate user recovery for a stale client is still a browser refresh
    (Ctrl-R); the guard just prevents the eternal-spinner trap.

---

## 2026-07-16 — 🔴 THE CFO'S GROSS MARGIN IS WRONG — four sources, and it breaks the EBITDA bridge

The IR lead supplied the real deliverables (7 files). The Peer Benchmarking
Report v2 settles the margin question I had flagged as unresolvable.

**Submitted Q2 gross margin: 34.6% ($8.9M gross profit). It is wrong.**
1. **Q1 2026 call, verbatim:** Louis — *"I feel that we've hit the bottom on the
   gross margins this quarter, and we should be able to get back to **23%-25% in
   the short term**."*
2. **Peer Benchmarking Report v2 (Jun 2026), Summary tab:** USIO LTM gross margin
   **23.8%**.
3. **Same report, Gross Margin Trend tab — 8 consecutive quarters:** 22.1 / 22.4 /
   22.8 / 23.1 / 22.5 / 22.9 / **23.4%**, improving 40-70bps YoY. **34.6% is
   eleven points outside an eight-quarter band.**
4. **Same report, Footnote Forensics tab:** USIO is a **NET reporter** —
   reported GM = adjusted GM, distortion **0**. There is no definitional route
   (gross-vs-net, adjusted-vs-reported) that arrives at 34.6%.

**It also breaks the P&L, which is why it matters beyond the sentence.** At
~23.8% gross profit is ~$6.1M, not $8.9M. $6.1M − $7.7M SG&A is **negative before
interest income** — so the $2.1M adjusted EBITDA on this page does not stand
either, and the "operating leverage inflection" paragraph is resting on it. Both
sections now carry a blocking 🔴 flag with the four sources and the knock-on
named. Nothing is silently substituted: the CFO owns the correction.

**Footnote Forensics is the most valuable analysis in these files** and the app
has none of it: USIO's margins look poor against peers ONLY because the peers
report GROSS while USIO reports NET. Adjusted: GDOT 40.5%→26.1% (−14.4pp), FOUR
32.1%→**21.8%** (−10.3pp), EEFT 54.5%→48.2% (−6.3pp), while USIO and RPAY are
undistorted. **Post-adjustment USIO's 23.8% beats Shift4's 21.8%.** That is the
"MOST MISPRICED" thesis, and it is invisible on reported numbers.

---

## 2026-07-16 — CEO + CFO sections written; a margin figure I won't let the CEO say

Scorecard **83 → 92**. Timing 0/20 → 10/20 (CEO 5.5 min vs 6.5 target, CFO 5.5 vs
8.0 — both now inside the band; IR Open and Business Operations still skeletons).

- **🔴 GROSS MARGIN — BLOCKING, CFO MUST RESOLVE BEFORE DELIVERY.** The submitted
  Q2 figure is **34.6%** on $8.9M gross profit. But on the Q1 2026 call Louis told
  this audience, verbatim from the transcript: *"I feel that we've hit the bottom
  on the gross margins this quarter, and we should be able to **get back to
  23%-25% in the short term.**"* 34.6% is ~10 points ABOVE that and ~1,440bp above
  Q1's 20.2% — implying gross profit went $5.1M → $8.9M on flat revenue.
  - It is NOT an arithmetic error: 8.9 − 7.7 SG&A + ~0.9 interest ≈ 2.1 EBITDA
    reconciles. So it is either **the headline of the call or a wrong number**,
    and the CEO cannot say it until the CFO confirms which. Both sections carry an
    explicit [CFO TO CONFIRM] block instead of the claim. Writing "gross margin of
    34.6%" one quarter after guiding 23-25% would either bury the biggest story on
    the call or destroy the guide's credibility.
- **CEO narrative (756w / 5.5 min)** — reprises the "operating leverage
  inflection" framing Q1's post-mortem said worked, on real Q2 numbers: $25.6M
  revenue, $2.1M adj. EBITDA, $0.01 EPS, $947k OCF / $333k FCF after $614k capex,
  $9.6M cash, no term debt, $3.05B volume +30% on 44M transactions, card +25% with
  PayFac 80%, ACH txns +37% / dollars +31.5%, RTP 223k, 17 ISV implementations.
  **States NO guidance range** — the CFO section owns that number; this script has
  already had three conflicting ranges in it.
- **CFO section (757w / 5.5 min)** — owns the guide: raising to $95.3M–$97.0M,
  [FLS]-tagged, with the seasonal arithmetic (YTD $51.1M = 53% of the new midpoint;
  ~$44.2M needed in H2; Q3 ~18% / Q2 ~35% so do not model an even split).
- **The interest-income bridge is now written into prepared remarks**, with the
  four things to say (dollar amount + prior year; 100% gross margin so a decline
  compresses reported GM with no operating deterioration; GM excluding it both
  periods; structural vs cyclical). Q1's post-mortem flagged this CRITICAL — "not
  pre-empted, drew 3 analyst questions" — and the transcript summariser
  independently surfaced "Interest Income Revenue Impact". Two methods, same
  finding, so it gets said before it's asked.
- **The signed-vs-assumed backing is placed in BOTH sections** as [CFO/CRO TO
  SUPPLY]: $X contracted / $Y in implementation with named go-live dates / $Z
  not yet won. The CEO commits to it out loud, the CFO delivers it. That is the
  demand analysts have pressed on in some form on four of the last five calls and
  never received. It cannot be written without the number — the CFO has it.

---

## 2026-07-16 — Reports audit CLOSED: Morning After PDF shipped, Investor Materials deleted

Pulled back to the audit that started this. Fair challenge from the IR lead: the
critique engine had been built with **no printable output** — the exact sin the
audit was convened to find ("Q&A Prep has no print path"), reproduced by me.

- **`report_pdf.morning_after_pdf()`** — the script-writing report. Renders from
  `morning_after.critique()` + the cached Q&A frames, so page and paper can't
  disagree. **Ordering is the argument**: unmet demands lead, because an unmet
  demand is the only thing in here that tells you what next quarter's script must
  say. Sections: the tape (with the after-hours exclusion explained), what the
  Q&A demanded (MISMATCH → DEFERRED → WITHHELD, with the DEFERRED note that the
  market is not on the callback), non-answers vs the published ~11% norm with the
  citation, delivery timing by role, then the written read with any unverified
  figures flagged. Verified: **valid 3-page PDF, 11,268 bytes.** Download button
  live in Earnings → Morning After.
- **Investor Materials tab deleted** — tab, panel, `_render_investor_materials_tab()`,
  nav sub-item, docstring entry. It listed 3 PDFs that have never existed
  (`reports/` isn't there), so every row rendered "not found". Same call as All
  Downloads: a dead tab is worse than no tab. Verified live — Reports is now
  Board IR / 90-Day IR Plan / Peer & Market / Reg FD / Automation Tracker, no
  orphaned tab objects.

**Audit status: 4 of 6 closed.**
| item | state |
|---|---|
| Weekly IR Brief | ✅ rebuilt live + PDF |
| Script Effectiveness Scorecard | ✅ rebuilt live (83/100) + PDF |
| All Downloads | ✅ deleted |
| Investor Materials | ✅ deleted |
| Morning After critique | ✅ new — live + PDF |
| Earnings Prep Brief | ⏸ deferred — never ported from app.py; real build (pre-call, different data) |
| Peer Benchmarking Board Deck | ⏸ deferred — static image; needs pptx generation |

Every report that remains in the UI now renders live and prints. Nothing left in
Reports promises a file that doesn't exist.

---

## 2026-07-16 — Competitive fishing + the callback: two corrections that reframe the metric

IR lead, from the sell-side chair:

> "Analysts are thinking about the company but also in the context of their
>  coverage universe of competing stocks, so they are sometimes fishing for
>  competitive information — and that is often the reason they won't answer. In
>  addition, most of the questions on the call are for general knowledge
>  transfer; the real question gets answered when management calls you back after
>  the public call."

**Both were already implied by evidence in hand and I missed them.**

- **(A) Competitive fishing — this is the PUBLISHED finding I had extracted and
  failed to connect.** Gow/Larcker/Zakolyukina (2021), verbatim from the abstract
  I pulled: *"product-related questions are associated with non-answers, and this
  association is stronger when competition is more intense, suggesting
  product-related information has higher proprietary cost."* A refusal on
  competitively sensitive ground is CORRECT, and the tool was scoring it as a
  defect. New `WITHHELD` verdict + `competitive` / `competitive_why` fields.
  Guarded against the obvious abuse: the rubric requires naming the rival
  advantage the disclosure would confer, because a company's OWN contracted
  backlog, signed-vs-assumed split, margin path or implementation schedule is not
  competitively sensitive — firms disclose that routinely. "It's competitive" is
  otherwise an excuse.
- **(B) The public call is not where the real answer lands** — and this reframes
  what the whole critique measures. The analyst gets their answer on the
  CALLBACK. So judging "did the analyst get their answer" is measuring the wrong
  venue: they usually do, privately, invisibly to us. **The MARKET is not on the
  callback**, and the tape prices what the market heard.
- **It exposed a contradiction I had just written in.** "Analyst is the arbiter"
  (accepted ⇒ DISCHARGED) collides with (B): an analyst may accept publicly
  *precisely because* they'll take it up privately. Resolved with a new category:
  | verdict | meaning | action |
  |---|---|---|
  | MISMATCH | element absent, analyst PRESSED | fix first — live and unmet in public |
  | **DEFERRED** | element absent, analyst moved on | **they'll get it on the callback; the market never will. CHEAPEST to fix — nobody in the room flagged it** |
  | WITHHELD | element absent, genuinely competitive | correct refusal; cost is market uncertainty — a trade, not a mistake |
  | DISCHARGED | element present | say so |
- **Q1 2026 re-run: 5 numeric → 3 MISMATCH, 1 DEFERRED, 0 WITHHELD, 1 DISCHARGED.**
  **Zero withheld is the finding: none of USIO's omissions are competitively
  protected.** Every one is the company's own data. The DEFERRED item — "percent
  of customers taking a single product vs all four" — is the pattern exactly:
  analyst asked for cross-sell penetration, didn't get the %, moved on, and will
  pick it up on the callback. Every other holder is left without it.
- UI: four counters (Pressed & unmet / Deferred / Withheld / Discharged), colour
  by verdict, WITHHELD shows the rival advantage it protects.

---

## 2026-07-16 — number_frame wired into Morning After (+2 fixes it forced)

Live in Earnings → Morning After, replacing the marker-based press detector.
Cached per quarter (`qa_frames_<Q>.json`) because it costs an LLM call per
exchange — an explicit "Analyse the Q&A" action with a stored result, never a
render-time cost. Fed into `narrative()` facts with instructions to LEAD with
unmet demands. Every verdict ships with an expandable Q/A/reaction so the
reasoning can be checked against the transcript instead of trusted.

**Two fixes the first live run forced — both caught by the numbers looking wrong:**

1. **The rubric measured against an ideal, not against the analyst.** First run:
   **9 unmet of 9 numeric questions on Q1 2026** — the best-received call on
   record (+21%). A 100% failure rate is the same tell as the marker regex's 42%:
   the instrument is measuring the author's expectations, not the call. The
   corpus contains **18 explicit closures** — analysts saying "that's a great
   answer" and moving on. **The analyst is the arbiter, not the rubric.** The
   judge now treats the reaction as DECISIVE: accepted-and-moved-on ⇒ DISCHARGED
   even if imperfect (with the gap still recorded in `missing` as an
   opportunity); re-asked/sharpened ⇒ MISMATCH. 9/9 → 7/12.
2. **Un-evaluable exchanges were being blamed on management.** Three of those 7
   read "no management answer provided in transcript" and "never answered due to
   audio/connection issues" — i.e. OUR extraction handed the judge a fragment
   ("That's correct.") or a transcript with an audio gap, and it dutifully
   reported an omission. `frame_qa` now abstains below 120 chars of answer.

**Result on Q1 2026 (+21% call): 28 exchanges → 21 abstained as un-evaluable
(short back-and-forth), 5 substantive numeric questions, 2 unmet** —
  * "sales funnel / pipeline" (CLAIM ⇒ BACKING): omitted quantified pipeline
    metrics — dollar value, deal count, stage distribution, conversion rates.
  * "card revenue growth" (GOOD ⇒ REPEATABILITY): omitted which programs drive
    it and whether growth is accelerating.
Both land on the same two-year concern. That is a credible profile for a call the
market took +21% on — unlike 9/9.

**Open limitation:** abstaining on 21 of 28 is a lot; the 120-char threshold is a
judgment call, and USIO's Q&A genuinely contains much short back-and-forth. It
errs toward abstaining rather than blaming, which is the right way to be wrong,
but it means the denominator is small and the rate shouldn't be trended yet.

---

## 2026-07-16 — `core/number_frame.py`: the frame that explains the corpus

The IR lead supplied the model that four previous instruments were groping at:

> "Almost every question references a number in the financial statements or
>  prepared remarks, and then needs to be judged — is the number the analyst is
>  questioning a good number? If it's good, a certain type of response is
>  expected; if the number is negative, a certain type of response is expected.
>  And it's this they seek or want to know."

An analyst question is therefore structured, not free-form:
**ANCHOR** (a number) → **VALENCE** (they have ALREADY judged it) → **DEMAND**
(what that valence obliges) → **TEST** (did management deliver it).
  * GOOD → prove it REPEATS (run-rate or one-timer?)
  * BAD → prove you CONTROL it and say WHEN it reverses
  * CLAIM/GUIDE → prove it's BACKED (what's signed vs assumed?)

**A press is the MISMATCH** — management answered but omitted what the valence
obliged. Usually not evasion: a good answer to a question nobody asked.

- **Why it beats all four earlier attempts:** marker regex swung 6%→42% across
  three tweaks (measures nothing); IDF-cosine scored the real presses 0.02–0.08
  because a press REPHRASES by design (wrong instrument, not a tuning problem);
  bare semantic "same topic?" says only THAT they pressed, never WHAT was owed.
  This frame is **auditable** — it names the anchor, the valence, the demand and
  the omission, so the reasoning can be checked against the text in seconds. An
  argument, not a score.
- **It discriminates.** Q4 2025 "add $4 million back… normalized growth" came
  back **DISCHARGED** — management gave the $3–5M pro forma and the analyst took
  it. So it is not flagging everything.
- **THE FINDING — the same omission, three calls running:**
  | Qtr | anchor | verdict | omitted |
  |---|---|---|---|
  | Q3 2025 | "pipeline of future opportunities" | MISMATCH | what's signed vs assumed; conversion schedule |
  | Q4 2025 | "10%-12% guidance" | MISMATCH | signed/booked vs assumed |
  | Q1 2026 | "sales funnel" | MISMATCH | portion already signed vs assumed |
  Q1 2026 verbatim: management called the pipeline "robust and fairly consistent"
  with "billions of dollars" of volume and **declined to quantify the funnel**.
- **So the two-year unresolved concern reduces to ONE answerable disclosure:**
  *"Of our FY guidance, $X million is already signed/contracted, $Y million is
  assumed from new sales, and here is the conversion schedule."* That single
  sentence discharges the demand analysts have pressed on five times since Q3
  2025 — and it is the concern management conceded was "largely outside their
  control" in Q2 2025, the −16.58% call.
- **Status: no accuracy figure claimed.** The previous validation was circular
  (scored against the regex it replaced). A real error rate needs exchanges
  labelled by someone who is not the author of the module.

---

## 2026-07-16 — Topic continuity: lexical fails, semantic works, validation was circular

Built `core/topic_continuity.py` to fix the ambiguity that killed the peer
comparison ("follow-up" = etiquette vs real press). Restated the construct so it
can be measured: **a PRESS is a reaction that asks something AND is about the
same underlying concern.** Politeness and vocabulary are irrelevant.

- **Fixed a real extraction bug first.** The USIO turn header is
  "Name\nName\nTitle\nHH:MM:SS" and `_TURN` anchors on the TITLE, so every turn's
  body swallowed the NEXT speaker's name lines ("…Such as? Louis Hoch"). Top
  "shared terms" between a question and its follow-up were literally `louis`,
  `hoch`, `greg`, `carter`. `_clean_body()` strips them; applied to word counts,
  non-answer bodies and exchange text.
- **IDF-cosine lexical similarity FAILED, for a principled reason.** All five
  hand-read presses scored **0.024–0.081** — effectively zero. The analyst who
  moves from "pipeline of future opportunities" to "levers to push the pace of
  adoption, or is that outside your control" shares NO content words. **A press
  is a rephrasing by nature** — a good analyst attacks the same concept from a
  new angle with new words. Lexical overlap is structurally the wrong instrument;
  no threshold fixes it. Kept in-module with the failure documented.
- **`classify_semantic()`** — LLM judge given the question, the answer and the
  reaction, explicitly told that "just a quick follow-up" is turn-taking
  etiquette, that analysts are polite by reflex, and that a press REPHRASES so
  shared vocabulary must not be required.
- **⚠️ MY VALIDATION WAS CIRCULAR — recorded so nobody trusts the number.** I
  scored the LLM against labels produced by the regex detector I had already
  declared unreliable, then reported "27/39". That is not accuracy, it is
  agreement with a bad oracle. The run also revealed the regex now flags **35 of
  84 exchanges (42%) as presses, up from 5** — my own closure/press "fixes" made
  it worse. An instrument that swings 6% → 42% across three tweaks measures
  nothing.
- **Where they disagree, the LLM is right** (read individually): "And then maybe
  for Greg, you talked about the UCO One…", "Lastly, a financial question. In
  terms of the gross margin…", "Great. Last thing, in terms of cash leverage…"
  are all plainly NEW TOPICS that the regex called presses. Those were scored as
  LLM "misses". The LLM was being penalised for being correct.
- **NO accuracy figure is claimed for the semantic judge.** Establishing one
  needs labels a human actually read — the IR lead, not the author of the
  detector, and not the detector itself. Until then it is a better instrument on
  inspection, with an unknown error rate.

---

## 2026-07-16 — Peer comparison ABANDONED: the instrument isn't sound enough

Pulled 8 RPAY calls (2021–2026, both Motley Fool formats) to answer "do analysts
press USIO harder than peers?". **Answer: cannot be determined, and the honest
move is to say so rather than ship a number.** Three artifacts, each of which
alone would have produced a confident, wrong headline:

1. **Operator turns unmatched in the old format.** Old Motley Fool renders
   speakers as "Name\n--\nFirm -- Analyst", but Operator has no role block, so it
   never matched. Operator hand-offs vanished and analyst A's turn ran straight
   into analyst B's NEW question — read as a press. Fixed (presses 41 → 33), but
   it only narrowed the gap; it didn't explain it.
2. **"Follow-up" is ambiguous, and this is the killer.** Analysts say "just a
   quick follow-up" to mean *my next question* — turn-taking etiquette, not
   dissatisfaction. Read in sequence: "Got it. That makes a ton of sense. And
   then just a quick follow-up for me…" is a RESOLVED concern plus a new topic,
   and the detector calls it a press. Distinguishing that from USIO's "It's
   helpful. It's a bit of a follow-up. Do you have levers… or is that outside
   your control?" (a real same-topic push) needs **topic-continuity detection,
   which doesn't exist here**. Same word, opposite meanings.
3. **The result tracks ERA/FORMAT, not company.** Old-format RPAY (2021–22) 30%
   vs new-format RPAY (2025–26) 5%; USIO (2025–26) 6%. USIO matches RPAY's
   contemporaneous rate almost exactly. A 6x swing inside one company across a
   format change is a parser tell, not analyst behaviour.

**Reported RPAY 25.8% vs USIO 6.0% is an ARTIFACT and must not be quoted.**

Also decisive: the closure/press precedence has now been flipped TWICE and the
answer moved each time. An instrument whose output depends on which way its own
tie-break points is not measuring the construct. Continuing to tune regexes until
the number looks right is p-hacking with extra steps.

**What survives, and it's the part that matters:** USIO's 5 presses were read
individually and are substantively real — same-topic pushes where the analyst
would not let go. That finding rests on human reading of 5 exchanges, not on the
rate. The RATE is unreliable; the EXCHANGES are not.

**To do this properly** needs topic-continuity between question and reaction
(does the follow-up concern the same subject?), which is a real build — embeddings
or a classifier, not a regex. Deferred rather than faked.

---

## 2026-07-16 — Peer comparison (RPAY): method fixed, question unanswered

Ran the press analysis against a peer. Two real methodology bugs surfaced; the
comparison itself is not yet answerable.

- **Bug 1 — transcription house style broke the classifier.** Motley Fool
  EXPANDS contractions ("that is helpful", "you do not provide", "let us say");
  the vendor behind our USIO transcripts PRESERVES them ("that's", "don't").
  Patterns tuned on one corpus silently miss the other: both of RPAY's apparent
  "presses" were actually closures ("Thanks for that", "That is helpful") that
  didn't match. Unfixed, this would have produced a confident headline — "RPAY
  analysts press 20% vs USIO's 5%" — that was **purely an artifact of house
  style**. Added `normalize()` (contraction folding + smart-quote folding), run
  before matching.
- **Bug 2 — politeness beat signal.** Precedence let closure win, so "Okay. It's
  helpful. It's a bit of a follow-up. Do you have levers… **or is that really
  outside of your control?**" scored RESOLVED — the single most important press
  in the corpus. Analysts are courteous by reflex; "helpful" is free. Press now
  wins. The discriminator holds: a genuine new topic ("Thanks for that. And then
  could you remind us on Consumer?") does not trip `_PRESS`, while an explicit
  same-topic continuation ("follow-up", "just specifically", "to be clear",
  "back to") does. **USIO press count 4 → 5.**
- **The 5th press reinforces the pattern rather than diluting it.** Q4 2025: "add
  about $4 million back to what you reported and then calculate that growth, and
  that would be the normalized growth if that one event had not…" — the analyst
  doing management's revenue-quality bridge FOR them, out loud, on the call.
  That's the same concern again: **is the reported number repeatable?**
- **The comparison is NOT answerable yet.** USIO 5/84 presses (6%); RPAY 0/10 on
  a single call (Q1 2026). At USIO's 6% rate the expected count in 10 exchanges
  is 0.6 — so RPAY's zero is exactly what chance produces. **No difference is
  detectable and none should be claimed.** Matching USIO's sample needs ~6 RPAY
  calls. CASS isn't carried by Motley Fool (thin coverage) — a different source
  is required.
- **Peer transcripts analysed IN MEMORY, never persisted.** They're third-party
  copyrighted material; storing them in the client-facing DB is a terms question
  that shouldn't be answered silently, and fetch-analyse-discard avoids it.

---

## 2026-07-16 — Own hedge list: the method worked, the lexicon didn't, and it found the thing

Built `core/hedge_lexicon.py` to derive a hedge list from our own six calls,
per the IR lead's framing:

> "We often ask questions to understand what it's NOT — which is a concern that
>  could make a violent reaction to the stock."

An analyst question is a hypothesis test for a NEGATIVE. A direct answer
eliminates the possibility; a *variation* leaves it live, and the analyst must
price it. So the instrument isn't sentiment or even hedging — it's **did the
answer eliminate the concern**, and our transcripts carry the ground truth:
**the analyst's own reaction.** Closure ("that's a great answer") = eliminated;
a press ("just specifically…", "so to be clear…") = not eliminated. That label
comes from the person whose opinion moves the stock, not a dictionary.

- **The lexicon FAILED, and the failure is the good news.** 84 Q&A exchanges
  across six calls: 18 explicit closures, 50 moved-on, 12 no-reaction, and only
  **4 presses**. Zero terms cleared a min-count of 3. You cannot derive a lexicon
  from 4 positive examples — that's an anecdote. The reason the sample is empty
  is that **USIO management resolves concerns ~95% of the time**, consistent with
  the independently-measured 0–7% non-answer rate vs the 11% norm. Reported as a
  negative result rather than forcing a word list out of noise.
- **But the 4 presses are the finding.** Across four calls and two years,
  analysts pressed on ONE thing, four different ways:
  - Q3 2025 — "Do you have **levers** to push the pace of adoption, **or is that
    really outside of your control**?"
  - Q3 2025 — "if you **don't get those one-time events**, then the rest of the
    revenue…"
  - Q4 2025 — "back to the 10%–12% guidance. **What's already booked?** Signed,
    maybe not onboarded?"
  - Q1 2026 — "the **tempo** of getting folks who are on board to **start
    activating**"
  All four are: **"can you convert your pipeline on a predictable schedule, or is
  revenue timing outside your control?"**
- **It is the same concern that caused the worst tape on record.** Q2 2025's
  HIGH-severity material gap was "implementation timing unpredictability —
  management conceded delays are largely outside their control": **−16.58%**.
  The one concern analysts have never been able to eliminate is the one that
  detonated the stock. Nothing in the literature would have found this; it came
  out of the IR lead's framing applied to our own transcripts.
- **Honest limits, in the code:** the log-ratio is descriptive, not a
  significance test (no p-value implied); the list is OURS (good for tracking us
  over time, useless for peer comparison — that's what an LM licence would buy);
  and "moved on" can't be distinguished from "gave up" in text, so it isn't.

---

## 2026-07-16 — Guidance conflict cleared: 67 → 83, zero conflicts

Fixed the last stale range, in `full_script_override` (the consolidated,
hand-edited script the tooling deliberately won't auto-rewrite).

- **It wasn't a number problem, it was a VERB problem.** Both stale passages were
  written for **raise_low** — "raising the low end … while maintaining the high
  end at $95.5 million" — while the decision on file is **raise_mid** ($95.3M–
  $97.0M, both ends up). Swapping digits alone would have left the script
  asserting the opposite of the decision in prose while quoting the right
  numbers: worse than the original, because it would read as deliberate.
- Two passages rewritten (CEO narrative + guidance section): verb corrected to
  "raising our full-year guidance", range to $95.3M–$97.0M, and the "we're
  maintaining the high end to preserve discipline around H2 execution risk"
  sentence **deleted** — under raise_mid it contradicts the decision outright.
  Rationale replaced with the decision's own ("first-half performance now banked
  and improving second-half visibility").
- **"up from our prior range of $93.8 million to $95.5 million" preserved** —
  that's correct history, exactly the case `_HISTORICAL_RE` exists to protect.
  The edit aborts rather than writes if the source text doesn't match verbatim.
- **`guidance_consistency` → 0 conflicts, ok=True.** Scorecard **67 → 83**
  (Guidance consistency 0/20 → 20/20). All three guidance surfaces now state one
  range, and `set_decision()` keeps it that way structurally from here.
- Remaining 0/20 is timing — the persona sections are real prose but still short
  of target. That's writing to be done, not a defect to fix.

---

## 2026-07-16 — Licence gate made a UI decision; hedge panel built behind it

IR lead has emailed Loughran & McDonald for commercial terms. Built so that
activation is a switch, not a code change.

- **`settings_page._render_lexicon_licence()`** — Settings → Data Sources now
  carries the licence gate: an amber "licence required before this ships to a
  client" panel stating the terms, and a three-way selector (Unlicensed —
  default / Commercial licence agreed / Academic use only). Deliberately a UI
  decision rather than a code edit so switching it on is explicit and auditable,
  made by someone who knows the licence position — not something that happens
  quietly in a deploy. Verified rendering.
- **Hedge panel in the Script Effectiveness Scorecard** (`hedge` from
  `lexicon.measure()`), the right home because hedging is a PRE-delivery check:
  hedge ratio (qualifiers ÷ commitments), the two counts, the qualifiers found,
  and the caveat + licence state inline.
- **Deliberately NOT scored.** LM was validated on 10-K filings, not spoken
  calls, and there is no published "normal" hedge rate for a script — unlike the
  11% non-answer base rate. It's evidence for a human, not a number folded into
  the composite. Verified: score stays 67 whether the gate is open or shut.
- **Gate verified both ways:** closed ⇒ `hedge` is None and the scorecard is
  untouched; open ⇒ panel appears reporting the full script at **6.25x more
  hedging than commitment (25 qualifiers vs 4 commitments)**, score unchanged.

---

## 2026-07-16 — Non-answer panel surfaced; Loughran-McDonald acquired (LICENCE FLAG)

- **Non-answer panel live** in Earnings → Morning After: rate vs the ~11% norm,
  colour-coded (green <7th pct, red >75th pct), Refuse/Unable/Offline split, each
  flagged phrase with its excerpt, and the amber "labels unreliable ⇒ rate is
  indicative only" banner for Q2 2025. Fed into `narrative()` facts with the
  benchmark stated, and the rule that a rate at/below ~11% must NOT be written up
  as a failing.
- **Two crashes caught before shipping:** `_fallback_narrative()` and the no-seam
  error path still referenced `blind_spots`/`ineffective`, which the arena
  refactor had removed — both would have thrown KeyError the moment the model was
  unavailable or a transcript lacked a seam (i.e. exactly when you most need the
  fallback). Fixed and exercised.

**Loughran-McDonald Master Dictionary — downloaded for EVALUATION, not shipped.**
- March 2026 edition, 86,553 words, 9.1 MB → `vendor/loughran_mcdonald/`.
  Verified counts: Negative 2,355 · Positive 354 · Uncertainty 297 · Litigious
  905 · Strong_Modal 19 · Weak_Modal 27 · Constraining 184 · Complexity 53.
- **⚠️ COMMERCIAL LICENCE REQUIRED — BLOCKING.** The lists are free for academic
  research only; commercial use needs a licence (loughranmcdonald@gmail.com).
  Praxis Point IR is a commercial product sold to IR clients — that is not
  academic use. `vendor/loughran_mcdonald/NOTICE.md` records the terms, the
  action required, and the fallback (build our own hedge list from our own
  transcripts if the terms don't work).
- **`core/lexicon.py` is gated by default**: returns None unless settings.json
  declares `lm_license`. Verified closed — `available()` False, `measure()` None
  out of the box. A speed bump so nobody wires an unlicensed dictionary into a
  client deliverable by accident.
- **Why this dictionary:** general sentiment lists misread financial prose —
  "liability", "cost", "tax", "capital", "vice" (as in vice-president) score
  NEGATIVE on psychology-derived lists though they're neutral accounting
  vocabulary. That mis-measurement is the reason LM exists. For our purpose the
  instruments are Weak_Modal + Uncertainty vs Strong_Modal — hedging vs
  commitment — not sentiment.
- **Evaluation on the current Q2 2026 draft** (gate opened temporarily, then
  reverted): CEO narrative **hedge ratio 4.0x** (4 qualifiers — could,
  dependence, risk — vs 1 commitment: "will"). Guidance section: **1 qualifier
  and ZERO strong-modal commitments** — it qualifies without ever committing.
- **Honest limit, in the code:** LM was validated on 10-K filings, not spoken
  calls. Directional only. Unlike the 11% non-answer base rate there is NO
  published "normal hedge rate" for scripts — one must not be invented.

---

## 2026-07-16 — Non-answer detection, from the published literature

Searched the literature rather than inventing. `core/non_answers.py` implements
the classifier from **Gow, Larcker & Zakolyukina (2021), "Non-Answers During
Conference Calls", Journal of Accounting Research 59(4), 1349–1384**
(SSRN 3310360). Regexes/dictionaries transcribed from the paper's Tables A.1/A.2.

- **Why borrow:** they hand-tagged Q&A pairs, trained regexes on a split, and
  report honest out-of-sample performance — **78.87% TPR, 89.20% accuracy**
  (in-sample 81.82%/90.90%, so barely overfit). Our `_CONCESSION` regex was an
  unvalidated guess at the same construct.
- **Their taxonomy** replaces our binary: **REFUSE** (won't — base 8.2%),
  **UNABLE** (can't — 3.6%), **AFTERCALL** (take it offline — 0.2%, rare because
  Reg FD makes "call me later" a selective-disclosure problem).
- **The benchmark is the real prize: ~11% of responses are non-answers**, stable
  over time and across industries (p25 7%, p75 14%; materials/energy 9%, telecom/
  health care 13%; 34.67 responses per call). **11% is NORMAL** — this finally
  gives the critique a yardstick instead of an opinion.
- Validated against the paper's own worked examples: "not at liberty to give you
  much more details" → REFUSE; "I don't have it in the room" / "I do not know" →
  UNABLE; "take that offline" → AFTERCALL; a normal factual answer → clean.
- `_DISC_NOUN` is truncated in the published PDF; the missing tail is documented
  in-code. Effect is a slightly conservative REFUSE detector — it under-flags,
  which is the right way to be wrong here.

**USIO's actual record — management answers questions:**
| Qtr | resp | non-ans | rate | vs 11% norm | next close |
|---|---|---|---|---|---|
| Q4 2024 | 6 | 0 | 0% | −11.0pp | −1.89% |
| Q1 2025 | 27 | 2 | 7% | −3.6pp | −8.33% |
| Q2 2025 | 41 | 1 | 2% | *labels unreliable* | −16.58% |
| Q3 2025 | 22 | 0 | 0% | −11.0pp | −0.70% |
| Q4 2025 | 20 | 1 | 5% | −6.0pp | −9.92% |
| Q1 2026 | 30 | 0 | 0% | −11.0pp | +21.37% |

Three non-answers across six calls, all well under the norm. Q1 2025: CRO "I
don't have that", CFO "I don't know". Q4 2025: CEO "…n't get into a lot of
detail" (REFUSE).

- **Bug caught by the validated classifier — and it's a big one.** Filtering to
  management turns returned a confident **0% for Q2 2025**, yet the transcript
  contains a textbook UNABLE on the quarter's central question: *"We don't have
  the dollars associated with those programs."* It's attributed to **"Operator"**
  — the same mislabelling already flagged for timing. A false clean bill of
  health is the worst failure this metric can have. `non_answer_profile()` now
  inherits the reliability gate: when labels are junk it scans EVERY Q&A turn and
  reports the rate as indicative only, keeping the flagged phrases (which are
  real) while disowning the denominator (which isn't).
- **This also corrects my own over-flagging.** The validated classifier finds
  ZERO non-answers in Q1 2026, where my `_CONCESSION` heuristic had called
  "Gross Margin Recovery Timeline" a material gap because the summary said
  management sounded "vague". Vague ≠ non-answer. My heuristic was measuring
  something softer and calling it the same thing.

---

## 2026-07-16 — The Q&A is an arena, not a scorecard (IR lead correction)

The critique was too harsh, and the IR lead named the design flaw: it assumed
**every analyst question is a failure to pre-empt**. That is wrong about how a
call works.
- Sell-side analysts are OBLIGED to ask something — they must be on record
  engaging with the call or their opinion carries no weight.
- Most questions fish for INCREMENTAL colour (the trend, the cadence, the forward
  read). Asking about interest income may mean they want the TREND — you cannot
  pre-empt a request for more than you said.
- Some are positioning: a big-picture question to sound smart, which management
  may rightly wave off.
- "The answer is not in the model, it's in how you interpret the data going
  forward" — the analyst's real problem is that their model didn't tell them, and
  the most valuable thing management can supply is that interpretation, unasked.

**Rebuilt the taxonomy around EVIDENCE rather than the fact of being asked:**
- `material_gap` — management couldn't answer / conceded something the script
  framed as upside (`_CONCESSION`), OR the topic recurs quarter to quarter, OR
  never addressed and HIGH severity. These are the ones that cost money.
- `unaddressed` — not covered, but they'd have asked anyway.
- `probing` — covered; they wanted MORE. An OPPORTUNITY to own the narrative next
  quarter, not a failure.
- `ritual` — big-picture/macro. The arena working as designed. No action.
- Severity gate: a concession on a LOW-severity aside is not material. Flagging
  it dilutes the two or three findings that matter, which is the fastest way to
  get a critique ignored.
- `_NARRATIVE_RULES` rewritten to respect these classifications and to state
  plainly: do not scold management for being asked; if there are no material
  gaps, say the call held and do not manufacture criticism.

**Effect — the metric now discriminates where it didn't before:**
| Qtr | material | unaddr | probing | open | next close |
|---|---|---|---|---|---|
| Q4 2024 | 0 | 3 | 2 | +8.81% | −1.89% |
| Q1 2025 | 0 | 3 | 3 | −7.05% | −8.33% |
| Q2 2025 | **3** | 2 | 1 | −2.67% | **−16.58%** |
| Q3 2025 | 0 | 0 | 5 | −2.10% | −0.70% |
| Q4 2025 | **3** | 0 | 3 | −4.96% | −9.92% |
| Q1 2026 | **1** | 1 | 3 | +12.21% | **+21.37%** |

Q1 2026's Interest Income reclassifies from "language failure" to **probing** —
which is right: that call was the best received on record.

**Honest statistics.** correlation(material_gaps, next-close) = **−0.41, n=6**.
Directionally consistent and 5 of 6 quarters fit, but n=6 is far too small to
claim a relationship — that is well inside noise and must NOT be presented as a
finding. Q1 2025 breaks it outright (0 material gaps, −8.33%). The deeper reason
is structural: **the tape prices the RESULTS, not the script.** A clean script
cannot rescue a bad quarter, so this critique explains the gap between what was
said and what the buy-side needed — never the whole move. Do not build a
predictive claim on this.

---

## 2026-07-16 — Q2 2025 deep-dive (the −16.6% quarter) + 3 more fixes

**What actually happened on 2025-08-06:** close $1.87 → next open $1.82 (a
−2.67% overnight gap) → next close $1.56 (**−16.58% cumulative**) on 362k shares.
The move was −13.9pp AFTER the open: the market kept selling THROUGH the session
as it read the transcript. A digestion pattern, not a gap — the verdict wasn't in
at the bell, it built as people read.

**Why (4 blind spots, 2 language failures — the worst pre-emption on record):**
- **Implementation timing (HIGH, language failure).** The script framed 20 new
  ISVs "in implementation" and one "expected to process $100 million annually" as
  additive growth. Under questioning management conceded delays are "largely
  outside their control", citing 3+ month slips on major deals. The constraint
  was buried inside a volume metric — the buy-side re-read it as forecast risk.
- **Customer concentration (language failure).** Disclosed a "surprise loss of a
  large card-issuing account (≈$2 million in quarterly revenue)" with spillover
  into Q3 — then the analyst asked about two MORE large accounts with prolonged
  delays. He was modelling tail risk on the top accounts by then.
- **"We don't have the dollars."** Asked to quantify the 20 new card programs,
  management said they couldn't. That tells the buy-side the company isn't
  modelling its own forward revenue — which reframes guidance as a point estimate
  without visibility.
- Blind spots: macro/retail exposure, mix shift (electronic docs higher-margin
  but lower-revenue, no margin quantification), M&A intent with the stock down.

**Three more fixes the dive forced:**
1. **Operator time was being counted as prepared remarks.** The operator turn
   that hands over to Q&A STRADDLES the seam — it starts in the prepared section
   but runs to the first analyst. That added 9.0 min of queue instructions to
   Q2 2025 and made **the shortest call on record (10.9 min) look like the
   longest (19.9)** — inverting the "longest call, worst reception" read I'd
   drawn from the six-quarter table. `section_timing()` now counts management
   only and reports `operator_minutes` separately.
2. **Timing reliability flag.** Q2 2025's transcript has anonymous speakers
   ("Speaker 5/6/2") AND the operator holding 48% of the clock — turns are
   mislabelled, so its minutes can't be trusted at all. `section_timing()` now
   returns `reliable` + `warnings`; the tape and Q&A topics remain valid (they
   come from the text and the market, not the labels), only timing is withheld.
3. **Misattribution caught in the wild — the exact failure `_verify_numbers()`
   cannot catch.** With 0 unverified numbers, the model still wrote "closed
   −2.67% on call day, gapped down −16.58% at next open". Both figures are real;
   both are attached to the wrong measurement, and it inverts the story (gap vs
   digestion). Fixed at the source: the TAPE fact is now spelled out as three
   explicitly labelled measurements (a) call-day close, (b) next open + overnight
   gap, (c) next close + cumulative — plus a computed interpretation line stating
   whether the move happened at the bell or through the session. Re-run: the
   critique now reads it correctly ("The stock kept selling through the entire
   session after the open. That is sustained directional rejection").

---

## 2026-07-16 — Critique run across all six quarters (+3 bugs it exposed)

Summarized the remaining 4 transcripts (all 6 now have qa_risk_topics, 5–6 each)
and ran `morning_after.critique()` across the full history.

| Qtr | close→open | next close | prep | Q&A | topics | blind | ineff |
|---|---|---|---|---|---|---|---|
| Q4 2024 | +8.81% | −1.89% | 17.9 | 2.9 | 5 | 3 | 2 |
| Q1 2025 | −7.05% | −8.33% | 17.6 | 15.4 | 6 | 3 | 3 |
| Q2 2025 | −2.67% | **−16.58%** | 19.9 | 13.4 | 6 | **4** | 2 |
| Q3 2025 | −2.10% | −0.70% | 18.6 | 10.5 | 5 | **0** | 5 |
| Q4 2025 | −4.96% | −9.92% | 17.2 | 13.0 | 6 | 2 | 4 |
| Q1 2026 | **+12.21%** | **+21.37%** | 17.5 | 15.3 | 5 | 1 | 4 |

**Three bugs the run exposed — all silent, all plausible-looking:**

1. **Q&A seam regex too narrow.** Q4 2024 says "conduct **our** question-and-answer
   session" / "begin **that** question-and-answer session" / "first question
   **today** comes from"; the pattern demanded "begin **the**…". No seam ⇒ the
   whole transcript counted as prepared remarks. Broadened — carefully, because
   the operator's opening boilerplate ("there will be an opportunity to ask
   questions", ~2k chars in) must NOT match or the call splits at the top.
   Added a **fail-safe**: no seam ⇒ `preempt_analysis` refuses (returns an error)
   instead of searching the Q&A for evidence, which would have scored every topic
   "addressed" and hidden real blind spots behind a confident number.
2. **Turn regex dropped any speaker label containing a comma** — so "Founder,
   Chairman, and CEO at Usio" never matched and **the CEO's turns vanished**.
   Worse, a turn's duration runs to the next *matched* turn, so the dropped time
   was silently absorbed by the preceding speaker rather than lost. Q1 2026
   turns 61→86; Q4 2024 7→32.
   - **RETRACTION:** the earlier claim that measured timing "corroborated the
     post-mortem's *Business Review ran 2 min over at 12 min*" was an artifact of
     this bug. The CRO's "11.8 min" was the CEO's 8.4 min bleeding into it. True
     split: **CEO 8.4, CRO 3.4, CFO/CAO 3.2, IR 2.2**. The 17.5 min total was
     always right — only the attribution was wrong, which is exactly why it
     looked credible.
3. **Speaker labels aren't stable across quarters** — the same person appears as
   "Founder, Chairman, and CEO", "Chairman and CEO", "Founder, Chairman, CEO and
   President", fragmenting into rows that can't be trended. Added
   `normalize_role()` → CEO / CRO / CFO/CAO / IR / Analyst / Operator, keeping the
   raw labels for traceability. Q2 2025's speakers are genuinely anonymous
   ("Speaker 5") and report as **Unknown speaker** rather than being guessed.

**Prepared-remarks minutes by role (normalized):**
| role | Q4 24 | Q1 25 | Q2 25 | Q3 25 | Q4 25 | Q1 26 |
|---|---|---|---|---|---|---|
| CEO | 10.6 | 8.9 | — | 9.8 | 8.5 | 8.4 |
| CRO | 3.2 | 4.0 | — | 3.6 | 3.8 | 3.4 |
| IR | 3.7 | 4.4 | — | 4.7 | 4.9 | 2.2 |
| **total** | 17.9 | 17.6 | 19.9 | 18.6 | 17.2 | 17.5 |

---

## 2026-07-16 — Morning-after critique engine (`core/morning_after.py`)

Built to the standard set by `USIO INVESTMENT CASE.docx`: name the hesitation and
say whether the call resolved it; separate the headline from what the buy-side
models; give the mechanical why; cite everything.

- **Key design call — the prepared remarks ARE the script as delivered.** So
  pre-emption is measured straight from the transcript: no separate script file,
  no dependence on anyone archiving the right draft. `split_prepared_qa()` finds
  the seam ("Operator, you can now open the call to questions").
- **Timing is MEASURED, not estimated.** These transcripts carry per-speaker
  timestamps, so `section_timing()` reports real delivery. Q1 2026: prepared
  17.5 min, Q&A 15.3 min, total 32.8 min — **CRO 11.8 min**, which independently
  corroborates the hand-written post-mortem's "Business Review ran 2 min over at
  12 min". Two methods, same answer.
- **The metric was flattering itself — fixed.** The naive read ("was the topic
  mentioned in prepared remarks?") scored Q1 2026 as "4/5 pre-empted, 80%". That
  is backwards: every topic here came FROM the Q&A, so all 5 were asked. A topic
  that WAS in the script and still drew three questions is worse than a clean
  miss — the language was there and failed. Now split into **blind_spot** (never
  addressed — 1: Legacy Singular Portfolio Attrition) vs **ineffective**
  (addressed and asked anyway — 4, incl. Interest Income, which the hand-written
  post-mortem also flagged). The actionable finding is "your words didn't land",
  not "you forgot".
- **`narrative()`** hands ONLY the computed facts to the model and returns
  `(text, was_ai, unverified)`.
- **CORRECTION (2026-07-16, later): the "23-25% fabrication" was MY error, not
  the model's.** $23-25% is management's real gross margin guidance — it sits in
  the summarizer's `qa_risk_topics.why` ("management's 23-25% guidance appearing
  somewhat vague"), which `narrative()` passes into the facts. The model sourced
  it correctly. I grepped the raw transcript, found 23% (card growth) and 25%
  (ACH growth) nearby, and concluded "welded fabrication" without checking the
  facts blob I had actually supplied — a false positive produced by verifying
  against the wrong corpus. The citation rule and `_verify_numbers()` are still
  worth having (the planted 41.9% test passes, and unambiguous inputs fixed the
  real gap/close misread), but the record should show the model was right and the
  reviewer was wrong. Left as a caution: an over-eager verifier that cries
  fabrication is its own failure mode.
- **Fabrication controls.** The first run also produced a "50% interrogation
  claim" reading (PINless Debit grows ">50%"), which is a misattribution rather
  than an invention.
  - `_verify_numbers()` cross-checks every figure against the facts + transcript.
    **Honest limit, documented in the code:** it is a digit-presence check, so it
    catches pure invention (verified: flags a planted "41.9%") but CANNOT catch
    misattribution — right digits, wrong meaning — because those digits are real.
  - The actual control is the citation rule (`_NARRATIVE_RULES` 1a): every number
    must carry the verbatim sentence it came from, and combining two unrelated
    figures into a range is called out explicitly. After that change the same
    prompt produced **0 unverified numbers** and inline quotes throughout, with
    the fabricated range and the recycled 50% both gone.
- Falls back to `_fallback_narrative()` (facts, no prose) when the model is
  unavailable — never invents.
- **Not yet wired into the UI** — core + verified output only.

---

## 2026-07-16 — Transcripts ingested; the "+24.22% AH reaction" debunked

Transcripts were on `E:\` (not OneDrive/Claude Projects) — 6 quarters plus a
17,680-word "USIO INVESTMENT CASE" research doc.

- **`transcripts.extract_text_from_docx()` + `extract_text()` (new).** .docx was
  unsupported (only pypdf). A .docx is a zip of word/document.xml, so this uses
  stdlib zipfile + ElementTree — no new dependency. Paragraph boundaries are
  preserved because speaker turns ARE paragraphs; losing them makes the Q&A
  unparseable.
- **All 6 ingested with call dates parsed from the text:** Q4 2024 (2025-03-26),
  Q1 2025 (2025-05-14), Q2 2025 (2025-08-06), Q3 2025 (2025-11-12), Q4 2025
  (2026-03-18), Q1 2026 (2026-05-13). No Q2 2026 — that call is Aug 12, upcoming.
- **The prior call's date now exists, so `close_to_open_reaction()` is wired into
  the scorecard.** Six quarters of REAL executable reaction:
  | Quarter | close→next open | next close | vol |
  |---|---|---|---|
  | Q4 2024 | +8.81% | −1.89% | 182,600 |
  | Q1 2025 | −7.05% | −8.33% | 203,000 |
  | Q2 2025 | −2.67% | **−16.58%** | 362,000 |
  | Q3 2025 | −2.10% | −0.70% | 94,200 |
  | Q4 2025 | −4.96% | −9.92% | 216,400 |
  | **Q1 2026** | **+12.21%** | **+21.37%** | **682,100** |
- **The static scorecard's "+24.22% AH reaction" is confirmed an artifact.** The
  real executable move on Q1 2026 was **+12.21% at the open** (+21.37% by the
  close). The IR lead's call — that after-hours prints on a micro-cap are
  market-maker quotes that register but aren't executable — is now demonstrated,
  not just asserted: the AH figure overstated the open by ~2x.
  - Also visible: 5 of 6 calls were SOLD at the open. Q1 2026 broke the pattern
    on 3x volume. Q2 2025 opened −2.7% and closed −16.6% — the call didn't hold.
- **Q&A pre-empt score UNLOCKED.** Summarized Q4 2025 + Q1 2026 →
  `compute_qa_preemption_delta()` returns **11 real items** (5 NEW, 6 KEEP) from
  the actual Q&A, replacing the hand-maintained 4-item `_Q1_TO_Q2_ACTIONS`.
  - **It independently corroborates the hand-written post-mortem:** the model
    pulled "Interest Income Revenue Impact" out of the Q1 2026 Q&A on its own —
    matching the hand-noted "Interest income — NOT pre-empted · 3 analyst
    questions." Two independent methods, same finding.
  - New topics the hand list missed: Legacy Singular Portfolio Attrition, Prepaid
    Growth Drivers Specificity, Cross-Sell Penetration Rates, Gross Margin
    Recovery Timeline.
  - Q4 2025's HIGH-severity "Revenue beat visibility / implementation timing" did
    NOT recur in Q1 2026 → correctly scored KEEP (the pre-emption worked).
- **Transient bug noted:** Q4 2025's first summarize returned an empty body →
  "Failed to parse AI summary JSON: Expecting value: line 1 column 1 (char 0)".
  The fence-stripping parser is fine; the response was empty. A plain retry
  succeeded. Worth a retry-on-empty in `summarize_transcript` — the parser
  can't fix an empty response.
- **Reviewed `USIO INVESTMENT CASE.docx`** as the target standard for script
  critique / morning-after commentary. Its pattern: CFA/buy-side lens; name the
  investor hesitation then show whether it was resolved; separate the headline
  from what smart money actually watches; give the MECHANICAL why (flat $4.4M/qtr
  overhead ⇒ incremental gross profit drops to net income); corroborate
  management claims against third-party data (RTP surge vs The Clearing House's
  31.7% CAGR); cite every claim to source.

---

## 2026-07-16 — STRUCTURAL FIX: guidance prose now generates from the input

The invariant is now real: **the decision is the input; the prose is derived.**
It can no longer contradict the decision, because changing the decision rewrites
the words in the same call.

- **Root cause of the split:** the decision lived in `core.guidance_engine`
  (`set_decision`) but the renderer lived in `page_modules_nicegui.earnings_page`
  (`_guidance_template_draft` / `_generate_guidance_draft`). Core cannot import a
  page module, so `set_decision()` *structurally could not* regenerate the prose
  — all it could do was set `needs_redraft` and hope. That's the whole bug.
- **`render_guidance_prose()` moved into core**, next to `set_decision()`. Every
  number comes from its arguments, never from stored text. `earnings_page.
  _guidance_template_draft()` is now a thin delegate, so the decision path and
  the page render identical words from identical inputs (the old duplicate is
  kept as `_guidance_template_draft_legacy` for reference only).
  - Also fixed the `reiterate` variant: it previously stated only "continues to
    expect {growth}% growth" with **no range**, which let a stale range from an
    earlier draft survive underneath it. It now always restates the range from
    the input — exactly one number in play.
- **`set_decision()` now regenerates** `gd["text"]` whenever the action changed,
  the numbers moved, or the existing prose is already stale. Previous words are
  preserved at `gd["text_prev"]` (nothing discarded) and `ai_redraft_suggested`
  invites the richer AI draft — which regenerates from the same inputs.
  `needs_redraft` is popped: it cannot be stale, it was just rewritten.
- **Hole caught during testing:** re-deciding the *same* action left already-
  stale prose untouched (nothing "changed"), which is precisely how the
  $93.8M–$95.5M paragraph outlived the raise_mid decision. Added
  `stated_range_conflicts()` — shared by `set_decision` and
  `guidance_consistency` so both agree what "stale" means — and the repair now
  triggers on staleness itself. Verified: planted stale prose under an unchanged
  action → `set_decision('raise_mid')` → `text_regenerated=True`, prose repaired
  to $95.3M–$97.0M.
- **Reporting bug caught:** `text_regenerated` omitted `already_stale`, so a
  self-repair reported `False` while actually rewriting. Fixed — the return now
  tells the truth.
- **Verified:** flipping reiterate → raise_low → raise_mid, the prose follows
  every time. `guidance_decision.text` is now permanently consistent.
- **Remaining (correctly flagged, not auto-rewritten):** `full_script_override`
  still states $94.8M–$95.5M. That's the consolidated, human-edited script — the
  scorecard flags it (Guidance consistency 0/20) rather than silently rewriting
  someone's edited script. Re-consolidating from the sections clears it.

---

## 2026-07-16 — Guidance version conflict: verified, and now enforced

IR lead's hypothesis — "multiple attempts at guidance over the last couple of
days, we're in a version conflict; guidance should just pull from the Input" —
**confirmed exactly.**

- **What's actually single-source:** `set_decision(action)` → `apply_action()` →
  persists `guidance_decision.{action,new_low,new_hi}` and commits the FY. The
  CEO opener in `earnings_page:903` correctly GENERATES its sentence from those
  fields. That path is sound.
- **What breaks it:** `guidance_engine.set_decision()` carries the comment
  *"Deliberately does NOT touch gd['text'] — the words are authored in Script
  Generation."* So the numbers are single-source but the PROSE is a hand-authored
  copy with the range baked in. Re-decide the action and the paragraphs still
  quote the old range. `needs_redraft` flags it; **nothing enforces it**, and a
  persona can hand-type a range on top. Hence several "attempts" coexisting, each
  looking authoritative.
- **`guidance_engine.guidance_consistency()` (new):** reads the input, scans all
  6 prose sources (guidance text, 4 persona sections, full override) for any
  stated FY range, and reports what disagrees. **Verified result: input =
  raise_mid → $95.3M–$97.0M; 2 real conflicts —** `guidance_decision.text`
  ("reiterating … $93.8M to $95.5M" — wrong verb AND wrong range) and
  `full_script_override` ("we now expect … $94.8M and $95.5M"). `needs_redraft`
  was already True.
- **False positive caught and fixed:** the first pass flagged 3 conflicts, but
  one was legitimate — *"up from our prior range of $93.8M to $95.5M"* correctly
  cites history. Added `_HISTORICAL_RE` (prior/previous/up from/versus our/…) so
  a historical reference isn't flagged; a checker that cries wolf trains people
  to ignore it.
- **Now scored, hard:** new "Guidance consistency" component (20 pts, all-or-
  nothing) in the scorecard; total normalised to 100. Score **80 → 67** — the
  conflict is a disclosure problem, not a style nit. Surfaced in the UI (red
  panel showing the input, the needs_redraft flag, and each conflicting excerpt)
  and in the PDF. Verified live.
- **Open (management decision):** reconcile to one range. The structural fix is
  to generate the guidance prose FROM the input (as the CEO opener already does)
  rather than authoring numbers by hand — otherwise this recurs every cycle.

---

## 2026-07-16 — Operating-leverage framing closed; reaction metric corrected

- **Carry-over closed: 3/4 → 4/4. Score 70 → 80.** Rewrote `ceo_narrative`
  reprising Q1's "operating leverage inflection" framing (the post-mortem's KEEP
  item — "same length, update numbers only"), rebuilt on the CFO's submitted Q2
  numbers: $25.6M revenue, 34.6% GM, $2.1M adj. EBITDA on $8.9M GP, $947K OCF /
  $333K FCF after $614K capex, $9.6M cash, card +25% YoY with PayFac 80% growing
  25%, ACH txns +37%, ACH $ +31.5%, RTP 223k, 17 ISV implementations.
- **MATERIAL ERRORS FOUND in the existing CEO section (flagged, not silently
  papered over):**
  - It stated **revenue of $23.7M**; the CFO submitted **$25.6M**. The guidance
    section's own YTD figure proves $25.6M (25.47 + 25.6 = $51.07M ≈ the $51.1M
    it cites). The CEO would have misstated revenue on the call.
  - **Three conflicting full-year guidance ranges in one script:** CEO narrative
    "raise low to $94.8M / high $95.5M"; `guidance_decision.action` raise_mid →
    **$95.3M–$97.0M**; `guidance_decision.text` "reiterating **$93.8M–$95.5M**".
    `needs_redraft: True` was already set. The rewrite deliberately states **no**
    guidance range — the CFO/guidance section owns that number, and a fourth
    variant would have made it worse. Reconciling the range is a management
    decision, left open.
- **Reaction metric corrected to close→next-open (`close_to_open_reaction()`).**
  Per the IR lead: on a micro-cap the after-hours tape isn't a real price —
  market makers park wide, non-executable quotes at the bell that still print and
  still register, so the old scorecard's "+24.22% AH reaction" is an artifact of
  that, not a verdict. The last executable print of the day is the CLOSE and the
  next is the following OPEN, so that's the measure. Returns close, next open,
  %, next-day close %, and volume; None (never a fabricated number) when history
  is unavailable. Verified against real USIO history (e.g. 2026-07-08: close
  $2.10 → next open $2.12 = +0.95%). Still needs the prior call's date stored to
  wire into the scorecard headline.
- Timing stays honest at **0/20** — the CEO section is 353 words (2.5 min) vs a
  6.5-min target; real prose, still short of a full section.

---

## 2026-07-16 — CRITICAL: stale-cache data corruption (found via the scorecard)

Building the live scorecard surfaced a real data-integrity bug: the app rendered
`script_workflow_state.json` as `ir_review` / 0-char script while Neon held
`exec_review` / 6,072 chars. Two bugs compounding.

- **Bug 1 — race in `_pg_reachable()` (pre-existing, latent).** It set
  `_pg_status["checked"] = True` *before* the ~1s `psycopg2.connect()`. Any other
  thread calling in during that window saw `checked=True, available=False` and
  silently used the SQLite fallback. Proven from the log ordering: the Today
  page's first read (`render_today_page → _earnings_readiness_pct`) logged
  `pg=False` and read stale local data **before** `[db] Connected to Neon
  Postgres.` appeared.
  - Fix: probe now runs under a lock, with double-checked locking, and publishes
    `available` **before** `checked` in a `finally`. Concurrent callers block for
    the probe instead of racing it into a premature False.
- **Bug 2 — the in-memory cache made it permanent (mine, from this session).**
  `load_json()` cached whatever it read, including fallback reads. So a 1-second
  startup race pinned stale SQLite data in `_MEM_CACHE` for the life of the
  process — silently shadowing Neon. Only the first-read key was affected, which
  is why everything else (13F, prospects, addresses) looked right and only the
  script state was wrong: the classic hard-to-spot mixed state.
  - Fix: new `postgres_configured()` distinguishes "SQLite is the intended
    backend" from "SQLite is a degraded fallback". `load_json` now caches a value
    **only when it came from the authoritative store** (`if pg or not
    postgres_configured()`); a fallback read is returned so the page renders, but
    not cached, so the next read retries Neon. Same guard applied to caching
    `_ABSENT` — a "missing" answer from the fallback isn't authoritative either.
- **Verified:** app and CLI now agree (score 70, 943 words / 6.7 min, 3/4 topics
  closed, exec_review 2/5). db regression re-run: save→load, overwrite, no
  mutation leak, delete-invalidates all pass.
- **Worth noting:** the SQLite fallback is a silent correctness hazard by design
  — it serves *different data*, not degraded performance. Now that it can no
  longer poison the cache, the remaining question is whether it should fail loudly
  instead when DATABASE_URL is configured. Left as an open decision.

---

## 2026-07-16 — Script Effectiveness Scorecard rebuilt live

- **`core/script_scorecard.py` (new).** Replaces the static Q1 image with a
  scorecard computed from the script on file. Honest about its limits: the
  original's two headline numbers are NOT reproduced, because neither is
  derivable from anything held — "+24.22% AH reaction" needs the prior call's
  date (not stored) and "pre-empt score 8/12" needs Q&A topics from transcripts
  (**zero ingested**, so `compute_qa_preemption_delta()` returns None). Both are
  reported as named gaps with the exact unlock step, not faked.
  - Measures what IS real: section word-count → speaking time @140 wpm (the
    direct answer to Q1's "Business Review ran 2 min over at 12 min"),
    carry-over closure vs last quarter's post-mortem **with the matching script
    excerpt shown as evidence**, FLS tag discipline, workflow completeness.
  - Composite states its own weights and what it excludes.
- **Bug caught in verification:** timing credit used `mins <= target`, so a
  1.1-min skeleton against a 6.5-min target scored **full marks** — the script
  graded **90/100 while being a 4-minute skeleton of a ~26-minute call**. Fixed
  to a 50–100%-of-target band: under it the prose doesn't exist, over it the
  section overruns. Score corrected to a truthful **70/100** with 0/20 on timing.
- **`report_pdf.script_scorecard_pdf()`** — valid 2-page PDF (5,329 bytes),
  renders from the same dict as the screen.
- Live finding: **"Operating leverage framing" is STILL OPEN** — Q1 said that CEO
  framing worked and should be reprised, and it is not in the current script.

---

## 2026-07-16 — Weekly IR Brief made real; All Downloads deleted

Prompted by a reports audit: "Generate Weekly Brief" produced no findable output,
and two tabs promised files that never existed.

- **Audit findings.** 5 reports worked end-to-end (Board IR Report, 90-Day IR
  Plan, Peer Benchmarking — all live PDFs, verified building at 5,086 / 5,667 /
  3,833 bytes; Reg FD CSV; NDR itinerary). 6 did not: Weekly Brief (one line, no
  document), Script Effectiveness Scorecard (static Q1 image, buried in a
  collapsed expansion under Peer & Market, no download), Peer Benchmarking Board
  Deck (static image, no download), Q&A Prep (no print path), and **All Downloads
  + Investor Materials — which listed 7 and 3 files respectively while
  `reports/` did not exist at all**, so every row rendered "not found".
- **`core/weekly_brief.py` (new):** `compose()` builds a real sectioned brief
  from live data only — Market (price, %, volume vs 10d avg with a read,
  consensus PT/upside), Earnings & script workflow (days to earnings, quiet-period
  state, workflow stage), IR activity this week, Investor pipeline (prospects,
  peer candidates, RIA video-call tier, promoted), NDR schedule, Peer watch,
  Peer news. Every source read defensively; a section with no live data is
  omitted rather than filled with placeholders. Returns one dict consumed by
  BOTH the screen and the PDF so they can't drift.
- **`report_pdf.weekly_brief_pdf()`** — renders that dict in the house style
  (verified: valid 2-page PDF, 4,242 bytes). Added `_esc()` since dynamic text
  (fund names, headlines) would break reportlab's mini-HTML parser on a bare `&`.
- **`reports_page._render_live_weekly_brief()`** — this week's brief in full:
  headline, stat row, every section, Download PDF. `_compose_weekly_brief()` now
  just borrows `compose()["headline"]` so the card matches the document.
- **All Downloads tab deleted** — tab, panel, `_render_downloads_tab()`, nav
  sub-item, and the docstring entry. It only ever promised 7 files that have
  never existed; a dead tab is worse than no tab in a demo.
- Verified live: Reports tabs now Board IR / 90-Day / Investor Materials / Peer &
  Market / Reg FD / Automation Tracker (no All Downloads), and the brief renders
  "Week of Jul 16, 2026 · live · Composed now" with real figures.
- **Still open:** Script Effectiveness Scorecard (rebuild live, like Peer
  Benchmarking was), Earnings Prep Brief (never ported from app.py), Investor
  Materials (3 missing files — delete or repoint).

---

## 2026-07-15 — "Where they are": metro breakdown for Investor Targeting

- **Request:** on Investor Targeting → Buy-Side Intelligence, "This week's
  priority" reads "27 institutions" with no sense of *where* they are. Added a
  geographic answer.
- **`investors_page._render_big_picture()`** — new **"Where they are — tracked
  institutions by metro"** table (Metro, Institutions, Holders, Non-holders,
  Tier-1 ready, NDRs, Top name), sorted by count then Tier-1 readiness, built
  from the `metro_summary` already computed for Metro Priority scoring.
- **Root cause the table exposed:** all 27 SEC 13F holders were bucketed as
  **"Unknown (SEC)"** — the records carried the filer's HQ city/state (from the
  bulk 13F address) but `_sec_holder_record` hardcoded `Metro="Unknown (SEC)"`.
  - New **`_metro_from_city(city, state)`** + `_SEC_CITY_METRO` map fold real
    filers into the *same* metro labels the seed universe uses (New York Metro,
    Boston / New England, Texas (Dallas / Austin), Florida (Miami / Tampa),
    Denver / Mountain West, etc.); unmapped US cities fall back to "City, ST",
    non-US filers group as "International" (SEC non-US state codes X0/V8/M0/K3).
  - `_sec_universe_records` now threads `h["city"]/h["state"]` through.
  - Result: **zero "Unknown" institutions** — 89 tracked across 12 real metros,
    34 holders. NY Metro 15→20, Chicago 6→11, Boston 8→10; International = 5
    (London ×2, Zurich, Tokyo, Hong Kong); one-offs honest ("Scottsdale, AZ",
    "Atlanta, GA"). Filter the full Buy-Side list / Target Database by metro to
    see the individual fund names.

---

## 2026-07-15 — Live peer benchmarking

- **Root cause found:** the Peer Benchmarking Report v2 only ever showed one
  page. `data/seed/report_images.py` had `PBR_PAGES = [PBR_P1]` (the gross-margin
  page); `PBR_P2`–`PBR_P5` never existed — true in the original `app.py` too, so
  the "5 tabs" was aspirational and the rest of the analysis was simply missing.
- **Fix — rebuilt it live** instead of re-embedding static images:
  - **`core/benchmarking_engine.py`** — computes the full analysis from data the
    platform already tracks: EV/Revenue (live price × shares − cash ÷ forward
    guidance revenue), the peer universe (CP() EV/Revenue), USIO gross margin /
    growth (CF()), and per-peer gross margin / growth
    (**`data/seed/peer_fundamentals.py`**). Produces the valuation discount,
    gross-margin and growth comparisons, an efficiency-ratio (GM ÷ EV/Rev)
    ranking, and a pair-trade read.
  - **`reports_page._render_benchmark_analysis()`** — renders it: dynamic key
    finding, stat row, four peer bar charts, a ranked comparison table, and the
    pair-trade callout. Replaces the single static image; Board Deck + Scorecard
    stay as (complete) static documents.
  - Added `shares_out_m` / `debt_m` to the financials config for the live EV/Rev.
- Current read: USIO **0.6x EV/Revenue vs 2.2x peer median (~72% discount)**,
  16% growth vs 6% median, **#1 on efficiency** (GDOT next at 30.0), LONG USIO /
  SHORT FOUR — matching the original report's thesis, now computed and live.

### Then rebuilt to real EDGAR financials + CFA-grade metrics
- **`core/edgar_financials.py`** — pulls real financials from SEC EDGAR's
  `companyfacts` XBRL API (the 10-Q/10-K), extracts a clean income statement /
  balance sheet / cash flow with ratios, and generates **management talking
  points** per statement. Handles two payments-specific nuances: settlement
  float (customer prepaid/settlement funds — ~$100M cash+restricted held in
  custody vs ~$8M corporate cash — surfaced as pass-through, not leverage) and
  gross-vs-net revenue presentation.
- **Reports → Peer & Market → "Company Financial Analysis & Peer Benchmarking"**
  now renders the full analysis from EDGAR (income statement, balance sheet incl.
  the settlement-fund read, cash flow), each with meeting-ready talking points —
  not just gross margin.
- **Benchmarking upgraded to EV/Gross Profit** (payments-appropriate; neutralizes
  gross-vs-net presentation). USIO reads **3.0x EV/Gross Profit, cheapest of 8,
  ~25% below the 4.0x peer median** — the honest number; the 72% EV/Revenue gap
  is flagged as flattered by gross-revenue accounting. USIO gross margin/growth
  now sourced from its actual filing (20.2% GM, 15.7% YoY).
- Standing bar: financial/valuation work held to CFA-charterholder rigor.

### Peer actuals — real financials, at no cost + Adjusted EBITDA
- **Fully real peer benchmarking, free.** Revenue growth from each company's
  EDGAR filing; **gross margin & EV/Revenue from Yahoo via yfinance** (already
  our price source — no key, no cost) on a consistent trailing basis, filling
  the metrics XBRL doesn't tag. `market_data.get_fundamentals()` +
  `benchmarking_engine._resolve_company()` layer filing → market → curated with
  per-metric source flags. This corrected materially-wrong curated inputs
  (EEFT gross margin 52% → **24% actual**, CASS 62% → **48%**).
- **GDOT and PAX excluded from the EV comparison** — a bank's cash holds
  customer deposits and a net-cash name's EV goes negative, so their EVs aren't
  meaningful (any provider hits this); their growth & margins still show. A
  licensed feed (Capital IQ/Bloomberg) remains an optional later upgrade for
  cleaner normalization.
- **Honest result:** with real gross margins, USIO is **cheapest on EV/Revenue
  (~64% discount) but #3 of 6 on EV/Gross Profit** (RPAY 2.9x, EEFT 3.4x screen
  cheaper) — a defensible read, not a manufactured "#1."

### Reports overhaul — retired stale static images, rebuilt live
- **Fixed a contradiction:** the static Peer Benchmarking Board Deck still showed
  0.4x EV/Rev / 82% discount, contradicting the live analysis. Replaced with a
  **live board summary** off the same `benchmarking_engine` — one set of numbers
  everywhere.
- **Board IR Report is now live** — composed from the real 10-Q (financials,
  balance sheet, cash flow), the valuation/peer position, and ownership
  (consensus PT, real 13F holder count, NOBO), with an executive summary and a
  board takeaway. Replaces static images whose page counts were overstated
  (Q1 "4 pages" = 1 image; Q2 "6 pages" = 3).
- **Script Effectiveness Scorecard** relabeled as the Q1 2026 historical example
  (static) rather than implying it's current; live Q2 comes from the Script
  workflow post-call.
- **Investor Materials / Downloads** reframed honestly — they no longer imply
  pre-baked files exist; live reports render in their tabs.

### PDF export of the live reports
- **`core/report_pdf.py`** (reportlab) — generates board-packet-ready PDFs on the
  spot from the same live data: `board_ir_report_pdf()` (executive summary,
  financials, balance sheet, valuation, ownership, board takeaway, talking
  points) and `peer_benchmarking_pdf()` (key finding, at-a-glance stats, and the
  EV/Gross-Profit-ranked peer table with source flags). Institutional layout,
  footer disclaimer, page numbers.
- **"Download PDF" buttons** on the Board IR Report and the Peer Benchmarking
  analysis — every export recomputes from the latest filing/market data, so the
  file always matches what's on screen.
- **Adjusted EBITDA** reconstructed from XBRL add-backs (stock comp,
  restructuring, impairment, acquisition costs) with the bridge shown: USIO
  GAAP EBITDA $0.72M + $0.33M stock comp = **$1.05M adjusted (4.1% margin)**.
  Talking points and the analysis note the company's own non-GAAP figure may
  include further items. Per-metric source flags (filing vs estimated) render
  in the peer table.

### Two-level sidebar navigation — every destination visible, one click deep
- **Problem:** the sidebar was a flat list of ~8 page buttons, but five of those
  pages each hid 4–7 tabs you only discovered after clicking in (~26 real
  destinations advertised as 8). The nav didn't tell you where to go.
- **Fix — expandable, deep-linking nav.** Each content-heavy page (Market
  Intelligence, Investor Targeting, Earnings Cycle, Reports, Settings) now shows
  a chevron and expands (accordion — one open at a time, active section
  auto-expands) to list its own tabs as sub-items. Clicking a sub-item jumps
  straight to that tab instead of landing on the page and hunting. The
  single-view pages (Today, Calendar, Outreach) stay as plain buttons.
  - `NAV_SUBITEMS` registry maps each page → its primary tab labels;
    `render_nav()` rebuilds the sidebar on every navigation / role change /
    tab-switch so the accordion, active-page, and active-tab highlights always
    reflect current state.
  - Deep-link plumbing in `page_modules_nicegui/nav.py`: `go_to(section, tab=…)`
    stashes the target tab, the page reads it once via `consume_target_tab()`
    when building its tab strip, and `tab_changed()` syncs the sidebar highlight
    back when the user clicks a tab inside the page (two-way).
  - Lazy-loaded pages (Investors, Earnings) eager-build whichever tab you
    deep-link to, so a jumped-to tab renders immediately instead of stranding on
    a spinner.

### Data pulls consolidated to Settings → Data Sources
- All manual, network-hitting refreshes are now triggered from **one deliberate
  place** (Settings → Data Sources), so opening a tab can never kick off an
  expensive pull. Controls: **Full investor universe** (~100MB SEC 13F bulk by
  CUSIP + 13D/13G, feeds Peer Prospects), **Market prices & fundamentals**
  (Yahoo), **Peer watch** (filings + the 7-day news window), and **13D/13G only**.
  Each runs in a worker thread with an immediate toast; results land in the
  db cache so reopening the relevant tab shows fresh data.
- The three refresh buttons on the SEC Intelligence tab were removed and replaced
  with a pointer ("Data pulls live in Settings" + an Open Settings button); that
  tab now only *displays* cached holder data.

### Perf — in-memory JSON-store cache (heavy renders, the scaling fix)
- Root cause of multi-second tab renders: **every `db.load_json` was a Neon
  round-trip** — `get_connection`'s `SELECT 1` health-check plus the query, ~100–
  200 ms each — and one heavy render (Buy-Side, Target Database, Peer Prospects)
  reads the same keys (13F holders per ticker, NOBO, prospects, peer universe,
  seed) dozens of times over, all synchronous on NiceGUI's event loop. Profiled:
  `build_candidates` spent 1,194 ms of 1,387 ms just on 12 DB reads.
- **`core/db.py` now caches the JSON store in memory**, keyed by (client_id, key).
  The store is written only through `save_json` / `delete_key`, so the cache stays
  coherent (writes update it in place); reads return deep copies so callers can
  mutate freely. Repeat reads drop from ~100 ms to ~0. Measured:
  `build_candidates` 2,407 ms → **27 ms**, `_sec_universe_records` 191 ms → **1 ms**.
- **Cache warmed at startup** (`_warm_cache`, background thread) so the FIRST
  navigation is fast too, not just repeats.
- **Net:** Peer Prospects tab **~7 s → 0.6 s**, Investor Targeting **3.4 s → 1.6 s**.
  Critically this *scales*: reading the same data N times now costs one round-trip,
  not N, so render time stops growing with data volume — the remaining cost is UI
  element building, which is bounded by the existing per-list caps.

### Fix — navigation "did nothing" (startup-pull contention / reconnect loop)
- "Open Full Investor Pipeline" (and other nav) appeared to do nothing: the click
  DID navigate, but the app was overloaded at launch — the startup data refresh
  (market data + peer filings + news for the whole universe, with FI's slow dead
  404s) was competing with the heavy investor-page render, starving the NiceGUI
  websocket handshake so the client reloaded back to Today. Not a data pull from
  the button — navigation is cache-only.
- **Deferred the startup refreshes** (`_kick_off_market_data_refresh` +20s,
  `_kick_off_peer_watch` +40s) so cached data shows instantly and the pulls run
  once the UI has settled — no more reconnect loop.
- **Skipped FI in the snapshot refresh** (`market_data._YF_SKIP`) — Fiserv's
  post-rebrand ticker has no Yahoo quote and just burned slow 404 retries every
  pass; it's a reference-only peer, so a missing snapshot is harmless.
- **"Open Full Investor Pipeline" now deep-links to Target Database** (the
  searchable database) with the sidebar highlight in sync, instead of the default
  Buy-Side tab. Confirmed the only data-pull triggers are the SEC Intelligence
  refresh buttons and the Today price-refresh icon — never plain navigation.

### Conviction-scored peer prospects + review gate (noise & false-positive fix)
- Ranking peer-overlap prospects by raw 13F position size surfaced index/passive
  giants (Vanguard, BlackRock, CalSTRS…) that never take a micro-cap NDR, and
  flagged funds that already own USIO (sub-13F-threshold or NOBO-only) as
  prospects. Rebuilt the whole surface.
- **`core/peer_prospects.py`** — turns the ~1,600-name raw pool into a short,
  explainable candidate list. **Conviction score** (kills noise): concentration
  (peer position ÷ the fund's whole 13F book), focus on the tight comps, breadth
  (fewer holdings ⇒ active, not index), and micro-cap size fit. **False-positive
  control**: suppress anyone already ours (13F / NOBO / tracked universe / 13D-G),
  de-dupe by CIK, drop passive/market-maker books and extreme-breadth quasi-index
  filers. Whole-book value + position count come from the same bulk 13F file
  (`refresh_13f_bulk_all` now captures them — no per-filer fetch).
- **"Peer Prospects" tab** (Investor Targeting) — a reviewed queue: each candidate
  shows its evidence (comps held, concentration, position size, breadth, filing
  date) and a **Promote / Dismiss** gate. Nothing enters the pipeline unvetted;
  promoting adds to prospects.json. Peer-overlap names are no longer auto-injected
  into the main universe (`_sec_universe_records`). A **"Rank by" toggle** flips
  the list between Conviction (default), Position size (what a plain 13F screen
  shows), and Concentration.
- Result: 1,600 → **223 qualified candidates**; the top of the list is exactly
  right — concentrated active small-caps (Veradace 16.7% in RPAY, **Forager
  Capital 12% in RPAY — the fund that bid to buy Repay**, Emmett/Speece Thorson
  in Cass), index giants gone.
- **Root-cause fix:** the Fit-Score "Peer Universe" (tiers core/close/large) and
  the valuation peer set (`CP()`, primary/reference) shared the DB key
  `peer_universe.csv`, so the Fit-Score merge kept re-adding the retired
  PRTH/EEFT/PAX and polluting the valuation median. Aligned `DEFAULT_PEER_UNIVERSE`
  to the new set and made `CP()` normalize the tier (large → reference), so the
  two systems stay consistent and navigation no longer re-pollutes the list.

### Peer-13F prospecting refreshed for the new peer set
- Ran the SEC 13F bulk pull for the new peer universe. The data holds **~1,600
  institutional managers that own a peer but not USIO** — but 77% of that (1,245)
  hold *only* a large-cap reference name (Fiserv / Toast / Global Payments), i.e.
  index/pension noise, not micro-cap-payments prospects.
- **Excluded reference-tier peers from prospecting** (`_sec_universe_records`
  skips `tier=="reference"`) and re-tiered the comps (`_PEER_TIER`: RPAY / CASS /
  CSGS / PSFE / PAY = Tier 1 tight payment comps; FOUR / GDOT = Tier 2) — the old
  map still listed dropped peers (PRTH/EEFT/PAX). Net: the pipeline surfaces the
  top-15 highest-conviction holders per *primary* comp — **68 new peer-overlap
  prospects (54 Tier 1, 14 Tier 2)** — instead of drowning in index funds.
- **CUSIP two-pass matching** (`sec_filings.refresh_13f_bulk_all`): pass 1
  name-matches only to discover each security's CUSIP (which every filer reports
  identically); pass 2 collects the complete holder list by CUSIP, catching every
  name variant. Closed the abbreviation gap — **RPAY 17 → 145 holders**, FOUR
  57 → 357, CSGS 58 → 295, CASS 28 → 158. The high-signal tight-comp pool
  (RPAY/CASS/CSGS/PSFE/PAY owners, not USIO, new) grew 280 → **478**.
- With complete data, the pipeline's top-15-by-position-size cut surfaces ~48
  net-new named prospects (the largest holders overlap more across comps and with
  the tracked seed). Sorting by raw position size now skews toward large
  diversified holders — a candidate future tweak is to rank the surfaced slice by
  conviction (concentration) rather than share count.

### Tiered peer architecture + RPAY closest-analog flag
- Client raised peer selection (via a PeerGPT note). USIO is a hybrid — Merchant
  Services + Output Solutions — so a single generic payments median understated
  the Output business. Restructured the peer set into **primary valuation peers**
  (RPAY, FOUR, PSFE, CSGS, Paymentus/PAY, CASS, GDOT — spanning integrated
  payments, billing/output, and prepaid) and a **large-cap reference tier**
  (FI, GPN, TOST) that sets the industry growth/margin bar but is **excluded from
  every median and rank**. Dropped EEFT / PAX / PRTH; **RPAY flagged as the
  closest single operating analog** (integrated card + ACH + document/billing).
  - `config` peers gained `tier` / `segment` / `closest_analog`; `CP()` threads
    them; `benchmarking_engine` computes the median from primary peers only,
    surfaces the reference tier separately, and leads the key finding with the
    RPAY analog. Reports show a segmented peer table + a reference table; the
    board PDFs pick up the new numbers automatically.
  - New read: USIO **3.6x EV/Gross Profit vs a 5.1x primary-peer median — a 29%
    discount, #3 of 7**, closest analog RPAY. (Did NOT build the full 2-segment
    sum-of-the-parts valuation — client opted out of "the valuation business.")

### Peer news feed — rolling 7-day window (free, no key)
- **`core/news_feed.py`** — a news feed for the peer group sourced from Yahoo
  Finance via yfinance (the same free library as prices — no API key, no cost).
  Each refresh fetches headlines for USIO + every peer, merges into one store,
  ages out anything past **7 days**, de-dupes by article id, and overwrites — a
  rolling past-7-days window that never grows unbounded (~11 KB). Preserves each
  article's original publish date so a re-surfaced item still ages out correctly.
- Refreshed by the same startup + ~12h background hook as the peer watch; the
  Today card reads the cache only. **Recent peer news** section added to the Peer
  Watch card — ticker · source · date, each a clickable link. Footnote notes a
  licensed feed (Benzinga / FMP / Polygon, ~$30–100/mo) would add breaking speed
  and deeper M&A/press-wire coverage; it can drop in behind the same
  refresh()/recent() interface via an .env key. Nothing is fabricated — an empty
  window means the sources had nothing.

### Daily peer watch on the Today page
- **`core/peer_watch.py`** — daily monitor of the peer group on the two signals
  we can source for free: **price moves** (cached market snapshots, notable = a
  ≥3% day) and **recent SEC filings** (each peer's own 8-K / 10-Q / 10-K / merger
  forms via EDGAR's submissions API, cached ~daily). News / M&A headlines are
  deliberately not faked — that needs a licensed feed (flagged, not invented).
- **Peer Watch card on Today** — today's peer movers (tagged by segment, with the
  closest analog marked) and clickable recent peer filings. Refreshed by a
  startup + ~12h background hook (`_kick_off_peer_watch`); the render path reads
  caches only so it never blocks the page. On day one it already surfaced RPAY's
  real 2026-07-14 8-K (the Forager-rejection / board-appointment filing).
- **Snapshot price fallback** — `market_data._fetch_one` now falls back to the
  `.info` regular-market price / previous close / open when yfinance's fast_info
  comes back empty (CSGS was flaky on the fast endpoint), so those names still get
  a price on the mover list. (FI still won't resolve on Yahoo under its post-
  rebrand ticker — reference-only, so no daily move; benchmark uses curated.)
- Thesis one-pager + demo hub refreshed to the tiered peer numbers (3.6x EV/GP =
  29% discount to the 5.1x primary-peer median, #3 of 7, RPAY closest analog).

### Global database search in the header
- Demo feedback: search was stuck in "one spot" (Target Database, fund-name only,
  three clicks deep) plus a separate transcript search. No way to "search the
  database" from anywhere.
- **`core/search_engine.py`** — one query across every database the platform
  holds: tracked buy-side funds + manually-added prospects (by fund name,
  contact, metro, style, holder status), NOBO beneficial owners, SEC 13F
  institutional holders, and sell-side analysts / firms. Ranked (exact → prefix →
  word-start → contains), per-source-capped and de-duplicated.
- **Global search box in the app header** (app_nicegui.render_header_search) —
  reachable from every page. Grouped, deep-linking results: a fund/prospect jumps
  to Target Database **pre-searched** on that fund (`search_prefill`), a NOBO
  holder to NOBO Ownership, a 13F holder to SEC Intelligence, an analyst to
  Consensus / Guidance — each landing with the sidebar highlight in sync. E.g.
  "perkins" surfaces the fund, its NOBO position, and its 13F filing at once;
  "chicago"/"value" search by metro/style; "buck" finds the analyst.

### Fix — Today-page deep-link arrows landed on the wrong sidebar tab
- The analyst-coverage "→" arrows and "Open Script Generation →" on Today used
  the old highlight-based deep-links (`highlight_analyst`, `earnings_tab=…`).
  Those opened the right *content* tab but passed no nav tab target, so the new
  two-level sidebar highlighted the page's *first* sub-item instead — the content
  and the sidebar disagreed, so the arrows read as "not working."
- Switched them to pass the tab explicitly via the new nav target
  (`nav.go_to("Markets", "Consensus / Guidance", highlight_analyst=…)` /
  `nav.go_to("Earnings", "Script Generation")`), so the tab opens **and** the
  sidebar sub-item highlight matches. Also hardened the arrow's click handler
  (`lambda e=None, firm=firm`) so the event NiceGUI passes can't clobber the
  captured analyst. Same fix applied to the two sibling deep-links (Markets →
  Guidance Engine, Prior-Qtr → Call Transcripts).

### Email restored to the IR Risk Dashboard signal dialogs
- The actionable-signal dialogs said things like "Send model request emails" but
  had no way to actually send one — they pointed off to Today / Mail Gateway.
  Restored a **"Draft the email"** action (a `mailto:` draft, the same proven
  pattern the NOBO and NDR surfaces use) on every signal that has a real
  recipient/action, built from live data by `core/risk_scorecard`:
  - **Missing analyst models** → the analysts with no model on file
    (`_model_request_email`) — model/estimates request.
  - **Street vs guidance gap** (beat risk) → the CFO (`_guidance_gap_email`) —
    align on walking analysts toward guidance or revisiting the range.
  - **PT upside** (>50%) → an outreach draft (`_outreach_upside_email`) with the
    upside hook; no fixed recipient, so it opens a compose window for the IR lead
    to address to a target investor.
  - "In line" / "Monitor" / not-tracked blind-spot signals carry no email (no
    action to take). Each dialog shows the recipient under the button and opens a
    review-before-send draft in the user's mail client.
- The Guidance & Outlook Decision Engine (shown inline on Market Intelligence →
  Consensus / Guidance, and ahead of the CEO canvas in Script Generation) used a
  different, un-numbered shape than the rest of the script-generation cycle,
  whose persona Script Canvases run **Step 1 — Review / Step 2 — What's New /
  Step 3 — Generate Draft** (`_render_persona_steps`).
- Reframed `_render_guidance_decision` onto the same three-step spine:
  **Guidance Step 1 — Review** (Street-expectations protocol, situation metrics,
  recommended action, morning-after read) · **Guidance Step 2 — Decide** (the
  action selector + H2-context input) · **Guidance Step 3 — Generate Draft**
  (draft with AI → edit → submit to script). Same controls and behaviour, now
  consistent with the cycle. Prefixed "Guidance" so on the CEO Script Canvas —
  where the engine renders just above the CEO persona's own Step 1/2/3 — the two
  step sequences read as distinct. Shared engine, so both surfaces update together.

### Fix — Today page "volume vs 10-day avg" showed no value
- **Root cause:** yfinance `FastInfo` resolves both snake_case and camelCase keys
  via subscript (`info["last_volume"]` works), but its `.get()` does **not** alias
  — `info.get("last_volume")` returns `None` in current yfinance versions even
  when the value exists. `_fetch_one` read price via subscript (worked) but
  guarded volume with `.get()` (always `None`), so `volume`/`avg_volume_10d` were
  dropped from every snapshot and the Today card rendered "—".
- **Fix:** `market_data._fetch_one` now reads every FastInfo field via guarded
  subscript (`_fi()` helper), robust to key casing across yfinance versions.
  Today now shows the real ratio (e.g. 0.3x), and peer snapshots repopulate
  volume on their next refresh.
- Note: NOBO figures are computed live by `nobo_engine`, but from the
  representative demo pull (`data/seed/nobo_holders.py`) — they become a real
  feed when a Broadridge NOBO file is uploaded on the NOBO tab.

### Pre-demo lock-down
- Full click-through of all nav destinations and sub-tabs (Market Intelligence,
  Investor Targeting, Earnings Cycle, Reports, Settings) — every page and tab
  renders with real data, no errors or stuck spinners, and the server log shows
  zero tracebacks across the sweep.
- **Outreach hidden from the sidebar** for the demo: its Mail Gateway (IMAP/SMTP)
  workflow isn't ported to this interface yet, so it only surfaced a "use app.py"
  placeholder. Nav entry removed (one line, commented); its `PORTED` render
  mapping stays, so restoring it is a one-line change.

### Nav reorg — two tabs moved to where they belong
- **NOBO Ownership: Market Intelligence → Investor Targeting.** It reads the
  investor base, not the market, so it now sits with Buy-Side Intelligence, the
  NDR planner, and the target database. The renderer (CEO's-read BLUF,
  composition/concentration, two-pull flow, 13D/13G watch, Broadridge upload)
  stays in `markets_page._render_nobo` as the single home for the nobo_engine
  surface; `investors_page` calls it cross-module (same pattern Earnings uses for
  narrative momentum). Its outreach-log tag updated to "Investor Targeting ·
  NOBO Ownership".
- **Narrative Momentum: Market Intelligence → its own Earnings Cycle tab.**
  Removed from Market Intelligence (where it was a compact glance) and promoted
  to a dedicated tab under Earnings Cycle, right after Script Generation, showing
  the full read (`markets_page._render_narrative_momentum` over
  `narrative_engine`). Lazy-loaded like the other Earnings tabs. Tomorrow's Setup
  (inside Script Generation) was trimmed to match: it keeps the guidance
  morning-after read and now links to the new tab ("Open Narrative Momentum →")
  instead of re-rendering the full signal, so the read lives in exactly one
  place.
- `NAV_SUBITEMS` updated so the sidebar reflects both moves.

### 90-Day IR Plan — the forward complement to the Board IR Report
- **`core/ir_plan.py`** (`compose_ir_plan`) — composes a live, forward-looking
  90-day action plan from data the platform already holds: the earnings-cycle
  dates (quiet start/end, earnings call) and NDR schedule laid onto a
  today→+90-day **timeline**, quarter **objectives**, **targeting** (booked
  roadshows + top-5 non-holder prospects by engagement score), **catalysts**
  (named H2 items), the three **positioning** messages from the thesis, and
  **ownership actions** derived from NOBO flow + the 13D/13G threshold
  (reinforce the top accumulator, broaden retail, re-engage a trimmer, watch the
  5% builder). Context snapshot pulls growth / operating margin / EV-GP /
  consensus PT so the plan opens with why it matters.
- **Reports → new "90-Day IR Plan" tab** (`_render_ir_plan`) renders it, and
  **`report_pdf.ir_plan_pdf()`** exports the same plan as a board-ready PDF with
  a "Download PDF" button — recomposed live each time, like the other reports.
- Answers "where's the 90-day plan?" — the Board IR Report is current-state;
  this is the forward action plan.

---

## 2026-07-14 — Ownership data, NOBO, guidance UX, demo prep

Big session ahead of the Wednesday CFO demo (Michael White, USIO). Highlights:
real SEC ownership data by CUSIP, a full NOBO analysis surface, data-provenance
tagging across the investor universe, and the guidance Decision Engine surfaced
inline on Market Intelligence.

### New engines & data (single-source-of-truth pattern)
- **`core/narrative_engine.py`** — `narrative_read(seed)`: pure compute for the
  Narrative Momentum signal (analyst-PT direction, named H2 catalysts, guidance
  stance, narrative-vs-price). Shared by Script Generation and Markets.
- **`core/nobo_engine.py`** — NOBO analytics (composition, concentration/HHI,
  coverage-of-float, two-pull flow, 13D/13G threshold alerts, cross-reference,
  CEO's-read BLUF) + a Broadridge CSV parser (`parse_nobo_csv`) and an
  uploaded-pull store (`get_active_pulls`, demo ↔ uploaded resolution).
- **`data/seed/nobo_holders.py`** — representative NOBO list as two dated pulls
  (retail + institutional), so the flow analysis is live for the demo.
- **`core/guidance_engine.set_decision()`** — one write path for the guidance
  decision (verb → range → workflow state → write-through to `period_guidance`).
- **`core/sec_filings.refresh_13f_bulk_all()`** — pulls the **complete, exact**
  institutional 13F holders from SEC's quarterly bulk dataset filtered by CUSIP
  (replaces the sparse EDGAR full-text-search path for this use). One ~100MB
  download covers the client + all peers.

### Market Intelligence
- Tab renamed **"Consensus Matrix" → "Consensus / Guidance"**; added a standout
  **GUIDANCE & OUTLOOK** section header on the tab.
- **Guidance & Outlook Decision Engine now renders inline** on the guidance card
  (expand/collapse), rather than navigating to Script Generation. The CFO sets
  the decision here and it writes through to the CEO's script and the FY guidance
  (shared `earnings_page._render_guidance_decision`, `context="markets"`).
- **New "NOBO Ownership" tab** — CEO's-read BLUF, composition/concentration,
  coverage bar, two-pull flow (accumulators/distributors/new/exited), 13D/13G
  threshold watch, cross-reference into the pipeline (Call / Email / Log
  outreach), top-holders table, and a Broadridge NOBO-file upload.
- **Narrative Momentum** moved to a light glance here; the full read now lives in
  Script Generation → Tomorrow's Setup.
- CFA-grade guidance impact analysis + "morning-after read" BLUF surfaced here
  and in the Decision Engine.

### Investor Targeting
- **Tracked universe expanded 8 → 62 funds** across 8 metros (New York, Boston,
  SF/Bay, LA/SoCal, Chicago, Denver, Texas, Florida), each with a contact
  (name/title/email/phone). Real fund names, representative demo holdings.
- **Peer universe pruned to true payment comps** (removed non-comps CGTX/AEYE/
  WYY/LX). **Peer-overlap prospecting tiered**: Tier 1 tight comps (GDOT, PRTH,
  RPAY, CASS) surfaced first; Tier 2 broader industry (EEFT, FOUR, PAX), capped.
- **Data provenance** — every name tagged with its `Source` (Seed / Seed +
  SEC-confirmed / SEC 13F / Peer 13F T1 / T2 / NOBO). Colored badges on Buy-Side
  cards; a "Universe by data source" rollup on the SEC Intelligence tab.
- **Real SEC 13F holders merged into the universe** via the bulk-by-CUSIP pull —
  e.g. Whittier Trust, Renaissance, Citadel, Morgan Stanley, BlackRock, Goldman
  with exact share counts; 3 seed names auto-confirmed by live filings.
- New **"Refresh full universe from SEC EDGAR (complete, by CUSIP)"** button.
- **NDR Planner**: "Add a meeting by hand" now captures who-you're-meeting,
  address, time (picker), type, format, holder status; **per-meeting Call /
  Email / remove**; **Print** and **Email** the itinerary; a **"Fill open slots"**
  finder (metro targeting, peers-first). Seeded LA and Dallas/Austin trips.

### Script Generation
- New **"Tomorrow's Setup"** panel (forward bookend to Prior-Quarter Review):
  guidance morning-after read + full Narrative Momentum.
- **IR Guidance Protocol** moved to the **top** of the Decision Engine (open by
  default) so the CFO reads the Street-expectations briefing before deciding.
- Guidance decision write-through so a decision made anywhere reflects everywhere.

### Demo collateral (published Artifacts)
- Four one-page CFO briefs (Ownership & Provenance, Script Process & Controls,
  NDR Workflow, NOBO) + an all-in-one tabbed hub.

### Fixes
- "Open the full Guidance Decision Engine" no longer dead-ends on the Earnings
  default tab (now inline; earlier interim: deep-link + scroll via `earnings_tab
  ="guidance"`).
- Workflow-note yellow-on-yellow contrast fixed (#FDE68A → #92400E / #B45309).
- Guidance FY roll-up corrected by folding reported actuals (Q1) into implied FY.

### Notes for the demo
- The by-CUSIP refresh downloads ~100MB (1–3 min); the cache is already
  populated, so **don't click it live** unless demonstrating the pull.
- NOBO runs on representative data today; it ingests a real Broadridge file
  when available.
