# Praxis IQ — Project Handoff Package

Prepared for: Robert Breza  
Purpose: Transfer the Praxis IQ product concept, architecture direction, and implementation requirements to another AI/developer.

## Executive Summary

Praxis IQ is a Capital Markets Intelligence Platform for Investor Relations. It is not intended to be a generic ownership database. The core product vision is to help CEOs, CFOs, Heads of IR, and capital markets advisors allocate management time where it creates the greatest long-term shareholder value.

The initial use case is USIO, Inc., but the platform must be multi-client from the beginning. USIO is only the first client and proof of concept.

The platform should combine public ownership data, peer ownership analysis, investor demand signals, relationship intelligence, narrative intelligence, forensic accounting, technical market context, and roadshow optimization into a decision engine.

Core guiding principle:

> Praxis IQ does not collect data. It converts capital markets information into better management decisions.

## Product Philosophy

1. Recommendations over reports.
2. Precision over volume.
3. Management time is the scarce resource.
4. Every recommendation must be explainable.
5. Public data first.
6. Signals matter more than static snapshots.
7. Guidance is only guidance.
8. Mobile-first workflows.
9. Modular architecture with feature entitlements.
10. Client success is measured by better capital markets decisions, not more data.

## Key User Insight

Existing ownership databases create too much noise. Example: searching a small-cap ticker may return 30 contacts at AllianceBernstein, while the useful answer is the actual PM or strategy owner. Praxis IQ must identify the real investment decision path:

Institution → Strategy/Product → PM → Analyst → likely meeting owner.

Precision and accuracy matter more than a long list of names.

## Initial Client / Use Case

Client: USIO, Inc.  
Ticker: USIO  
Sector: Payments / FinTech / Embedded Finance  
Goal: Build an investor targeting engine using peer ownership.

## Initial Peer Universe

### Tier 1 — Direct Comparable Companies, Weight 10
- USIO — Usio
- GDOT — Green Dot
- PRTH — Priority Technology
- EEFT — Euronet Worldwide
- PSFE — Paysafe
- FOUR — Shift4 Payments
- PAY — Paymentus
- RPAY — Repay Holdings
- MQ — Marqeta
- ACIW — ACI Worldwide

### Tier 2 — Payment Infrastructure, Weight 8
- CPAY — Corpay
- FI — Fiserv
- GPN — Global Payments
- JKHY — Jack Henry
- FIS — Fidelity National Information Services
- FLYW — Flywire

### Tier 3 — Vertical Software + Payments, Weight 6
- TOST — Toast
- EVCM — EverCommerce
- BILL — Bill Holdings
- NCNO — nCino
- CWAN — Clearwater Analytics
- ALKT — Alkami
- QTWO — Q2 Holdings

### Tier 4 — Similar Market Cap / Adjacent FinTech, Weight 5
- BLND — Blend Labs
- OLO — Olo
- PAYO — Payoneer
- RSKD — Riskified
- IIIV — i3 Verticals
- AVDX — AvidXchange
- RMNI — Rimini Street
- PDFS — PDF Solutions
- INTA — Intapp

Excluded:
- FTCH
- CANO

## Data Source Philosophy

Primary source of truth should be SEC EDGAR.

Initial public/free sources:
- SEC EDGAR 13F-HR filings
- SEC 13D / 13G filings
- SEC Forms 3/4/5 later
- Company IR websites for analyst coverage and events
- Yahoo Finance / Stooq / Alpha Vantage / OpenFIGI for supplementary market data
- Manual contact validation where required

The platform should avoid paid databases until proof of concept is validated.

## Core Scoring Framework

Institutional Target Score / Capital Opportunity Score should be 0–100.

Initial proposed weights:
- Weighted peer ownership score: 35
- Number of peer companies owned / peer density: 20
- Ownership changes over last two quarters: 12
- Typical market-cap preference: 10
- FinTech/payments specialization: 8
- Position concentration / conviction: 5
- Geographic fit for roadshows: 3
- Existing relationship / prior meetings: 5
- Existing USIO holder: 2

Ownership change logic should distinguish:
- New position
- Increased position
- Reduced position
- Sold out
- Unchanged

Recent buyer and asset turnover should both exist, but total ownership-change/turnover signal should be around 10–15% of the model.

## Geographic / Roadshow Intelligence

Do not simply rank New York and Boston because they have the most investors. The platform must balance:
- Investor density
- Investor quality
- New investor opportunity
- Existing shareholder saturation
- Where management has not been
- Travel practicality
- Investor demand signals
- Roadshow history

Important insight:
A full day of eight meetings in New York or Boston may be less valuable than four high-quality new-investor meetings in Minneapolis, Chicago/Milwaukee, or Toronto.

Canada / Toronto should not be ignored. Toronto is a rich investor base and a short flight from New York. Europe is harder for micro/small caps but should not be excluded categorically.

Potential metrics:
- Geographic Opportunity Score
- Geographic Saturation Index
- Relationship Decay
- Management ROI / MROI
- Expected Shareholder Value / ESV

## Demand-Side Intelligence

Praxis IQ should eventually capture institutional demand before ownership appears in 13F filings.

Demand signals include:
- Website visits
- IR page views
- Investor deck downloads
- Earnings call registration
- Earnings call attendance
- Webcast engagement
- Email engagement
- Contact form submissions
- Meeting requests
- Conference interactions

Email demand requires companies to route inbound IR emails into one or more controlled inboxes:
- ir@company.com
- investors@company.com
- management@company.com
- events@company.com
- dedicated investor day / earnings inboxes

Signals should be normalized and mapped to institution/contact where possible.

## Narrative Intelligence

Guidance is only guidance. The platform must detect emerging catalysts and narrative changes even when formal guidance is unchanged.

Example insight:
USIO’s Q1 transcript laid out multiple upside catalysts while revenue guidance was maintained. The stock did not move immediately after Q1 but later strengthened as Q2 closed. The platform should pick up:
- New catalysts
- Tone changes
- Word usage changes
- Confidence changes
- Relative narrative vs peer group
- Narrative vs stock and ETF performance

Compare:
- Company transcript vs prior quarter
- Company transcript vs peer group
- Company stock vs peer basket
- Company stock vs relevant ETF
- Management tone vs reported numbers

Potential module:
Narrative Momentum Score.

## Technical Market Context

Technical analysis is not the user’s core expertise but PMs do look at it. Include practical IR-facing technical context:
- Relative strength vs peer group
- Relative strength vs ETF/index
- 1M / 3M / 6M / 12M performance
- 50-day / 200-day trend
- Volume vs average
- Accumulation/distribution
- Breakouts or breakdowns

Do not try to replace a trading platform. Use technical analysis as context for capital markets decisions.

## Forensic Accounting / Normalized Valuation

Build a forensic accounting summary before true peer comparison. This should adjust for:
- Stock-based compensation
- Capitalized software
- One-time items
- Acquisition accounting
- Deferred revenue differences
- Margin definitions
- Cash conversion
- Share count trends
- Revenue quality

Output should explain how the company is different from peers and how that may affect valuation.

## Platform Modules

Long-term engines/modules:
1. Ownership Intelligence Engine
2. Demand Intelligence Engine
3. Relationship Intelligence Engine
4. Narrative Intelligence Engine
5. Financial / Forensic Accounting Intelligence Engine
6. Technical Market Context Engine
7. Geographic Roadshow Optimization Engine
8. Decision Engine / Recommendation Engine
9. Executive Copilot / Ask Praxis IQ

## Mobile and Subscription Design

The platform must be mobile-first and tiered.

Mobile should not show giant tables. It should show:
- 3 recommended actions
- Priority signals
- Investor pipeline highlights
- Earnings readiness
- One-click drilldowns
- Alerts

Database must support feature entitlements:
- features
- subscription_plans
- plan_features
- client_feature_entitlements
- user_feature_entitlements

Example service tiers:
- Core: ownership + targeting + export
- Professional: roadshow optimizer + analyst coverage + demand signals
- Enterprise: narrative intelligence + forensic accounting + CRM + AI decision engine

## Data Model Direction

Use PostgreSQL.

Core objects:
- clients
- companies
- securities
- institutions
- people
- users
- peer_groups
- peer_group_companies
- filings
- holdings
- ownership_changes
- signals
- scoring_models
- investor_scores
- recommendations
- recommendation_explanations
- features
- subscription_plans
- entitlements
- meetings
- contacts
- analyst_coverage
- audit_logs
- import_logs

Important design choice:
Use a flexible `signals` table/event stream rather than creating a separate table for every possible event.

A signal should include:
- signal_id
- client_id
- company_id
- institution_id
- person_id
- signal_category
- signal_type
- signal_date
- signal_weight
- confidence_score
- source_system
- source_url
- metadata JSONB
- created_at

## Recommended Repository Structure

Create a clean GitHub repository named:

praxis-iq

Top-level structure:

praxis-iq/
- README.md
- docs/
- database/
- backend/
- frontend/
- python/
- assets/
- tests/

Do not create nested folders by typing a top-level folder path while already inside that folder.

Rule:
Before creating any new top-level folder, make sure the GitHub breadcrumb is exactly:
robbreza / praxis-iq

## Correct GitHub Workflow

For new folder creation through the GitHub web UI:
1. Start at repository root.
2. Click Add file → Create new file.
3. Use filename like `docs/README.md` or `database/README.md`.
4. Commit.
5. Click breadcrumb `praxis-iq` to return to root before creating the next top-level folder.

Avoid creating many files manually in GitHub if possible. For a real software workflow, build the file tree locally and push it to GitHub.

## Current GitHub Status at Time of Handoff

A clean repo was recreated, but only partial top-level folders existed. The user became frustrated because manual GitHub instructions caused nested folder mistakes and slow progress.

The next assistant/developer should avoid asking for repetitive screenshots and should provide exact instructions that specify:
- where the user currently is,
- where they need to be,
- the exact breadcrumb,
- the exact filename to enter,
- whether to return to root before proceeding.

## Recommended Next Step

Do not continue with manual GitHub folder creation unless necessary.

Better approach:
1. Generate a complete project scaffold locally.
2. Package it as a zip.
3. Have the user upload or push it into GitHub.
4. Then proceed to Neon/PostgreSQL schema execution.

## User Working Style / Instruction Requirements

The user needs very precise step-by-step instructions and does not want assumptions. When using GitHub or other UI tools:
- Say exactly where the user should be before starting.
- Give minimal steps.
- Do not change direction midstream.
- Do not ask for screenshots unless truly needed.
- Correct structural issues immediately.
- Avoid workarounds that compound mistakes.
- Keep responses short when the user is in execution mode.
