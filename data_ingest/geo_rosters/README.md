# Geographic roster build-out — provenance

Auditable record of the July 2026 geographic build-out of the PraxisPoint **house CRM**
(`contacts` table, Neon Postgres). These scripts and verification files document *which*
buy-side firms and people were added, *where they came from*, and — critically — *which
candidate firms were rejected and why*.

Everything here is data-loading provenance. The runtime code it depends on
(`core/roster.py`, `core/contacts.py`, `core/contact_classifier.py`, `core/firm_book.py`,
`core/email_finder.py`, `core/contact_currency.py`) is committed separately in `core/`.
The contacts themselves live in the database, not in the repo — these files exist so the
book's growth is reproducible and auditable, not to re-run blindly (the ingest scripts hold
absolute scratchpad paths from the original session).

## Standard applied

Held to CFA-charterholder rigor with a hard no-fabrication rule. A candidate firm was
**ingested only if** an independent web-research verification agent confirmed it is a
**real, currently-operating, actively-managed public-equity manager** (a stock-picker, ideally
with small/mid-cap exposure) with **confirmed current people**. Rejected on sight:

- Venture capital / private equity / venture-secondaries
- Defunct, merged-away, or renamed firms
- Pure index/ETF-index shops
- Wealth-management-only RIAs with no institutional active-equity strategy
- Off-mandate specialists (REITs-only, top-down macro) where noted
- Anything unverifiable or fabricated (firm-name-matches-founder was a recurring red flag)

Every rejection is recorded with its reason in `verifications/`.

## Pipeline

1. **Discover / verify** — verification agent returns strict JSON `{firm: {status, reason, city, domain, people}}`.
2. **Ingest** — verified firms only, via `core.roster.add_people` (dedup-safe; enriches an
   existing contact in place rather than duplicating; classifies roles/seniority; tags city + country).
3. **Email-find** — `run_emailfind.py` (Anymailfinder; only `valid` charges a credit; misses free;
   repeats within 30 days free).
4. **CIK resolution + currency** — `run_currency.py` / `run_signatory.py` bind firms to their 13F
   CIK and confirm active-filer liveness.
5. **Dedup** — `dedup_contacts.py` (within-firm) and `email_dedup.py` (same email + surname across firms).

## Regions covered (verified firms)

| Region | File | Verified / Rejected |
|---|---|---|
| Canada (TO/Montreal/Vancouver) | `verifications/canada_to_montreal.json` | 6 / 5 |
| US — SF / Denver / NY | `verifications/us_sf_denver_ny.json` | 4 / 9 |
| Philadelphia metro (PA/DE) — A | `verifications/philly_group_a.json` | 7 / 1 |
| Philadelphia metro (PA/DE) — B | `verifications/philly_group_b.json` | 6 / 2 |
| Baltimore / Maryland | `verifications/baltimore_md.json` | 7 / 2 |

Earlier geo passes (Canada bulk, TX, FL, NC, TN, GA, CO, SD, CA + supplements) were loaded via
`ingest_geo.py` / `ingest_ca.py` and the fund-complex / hedge-fund rosters via
`ingest_roster.py` / `ingest_hf.py`.

## Notable rejections (the audit trail earns its keep here)

- **Brandywine Global** — equity teams spun into Franklin Templeton's new *Franklin Equity Group*
  (Jan 1, 2026); the surviving Brandywine entity is now fixed-income.
- **Fiera Capital** small-cap — strategy wound down April 2025, lead PM departed to Montrusco Bolton.
- **Passport Capital** (wound down 2017), **Legg Mason** (into Franklin Templeton 2020),
  **Investment Counselors of Maryland** (into William Blair 2021), **Stone / Mavrix** (absorbed).
- **Crosslink, Saints** — venture capital, not public equity.
- **Sway, Glidepath, Moritz, Flatirons, Centennial** — unverifiable / fabricated.
- Source-list name errors caught and dropped: "Russell Thaler" → Richard Thaler;
  "Sylvain Boulianne" → Sylvain Boule; "Mathieu Gauvin" (not on Formula Growth's roster).
