# Demo client build (Jul 2026)

An anonymized demo tenant seeded from **real** micro-cap investor-engagement data.

## Source
A Lytham Partners email-campaign engagement report — a "1x1 Meeting Invitation" blast for a real
micro-cap (ProStar Holdings / MAPS), Jan 25 2022. The workbook contains only the ENGAGEMENT subset,
not the full send list:
- Total recipients 3,487 · delivered 3,343 · **opened 743 (22.2%)** · **clicked 147 (4.4%)**
- Tabs present: summary, **Opens** (718 usable rows), **Clicks**. The ~2,600 delivered-but-unopened
  recipients are NOT in the file — they'd need a separate MAPS "Recipients/Delivered" export.

## What was built
1. **`ingest_demo_campaign.py`** — loads the 716 engaged contacts into the global house `contacts`
   table (real names/firms/emails). Tagged `market_cap_focus=micro`; **engagement-scored** via
   provenance (opens = warm, clicks = hot); email marked valid (an open proves deliverability);
   **sell-side/banker firms flagged `firm_type=sell_side`** (13 — Aegis, Ladenburg, Stifel, Gagnon,
   etc.) so they stay out of the buy-side target list. `source='demo_campaign'` tags the cohort.
   Run email-dedup afterward — merged 36 rows into existing CRM people (enriching them with the
   engagement signal).
2. **`create_demo.py`** — creates the DEMO tenant via `client_store.upsert_client("demo", ...)` and
   seeds its client-scoped curated NDR book from the HOT clickers (buy-side firms only, ~110).

## Anonymization
Per the user's choice, the **issuer is fictional** — "Meridian GeoData, Inc." (ticker MGEO), a
geospatial/precision-mapping SaaS micro-cap (~$85M), flagged `demo: true` with an explicit note that
name/ticker/figures are illustrative. The real ProStar/MAPS identity is kept entirely out of the
tenant. The **investor contacts are real** (real engaged accounts) — the demo's value is showing a
hot-prospect list derived from who actually clicked through to the fireside-chat materials.

## Notes
- Contacts are global (house CRM); the demo tenant's *view* of them is the client-scoped curated
  book plus normal CRM search. Per the user, the engaged base also accretes into the house book.
- A demo login user is NOT created here — add separately if the demo needs an interactive login.

## Second campaign — IBI Group (IBG), Jan 2022 (house book, not the demo tenant)
`ingest_ibi_campaign.py` — a second Lytham 1x1 campaign (IBI Group, a Toronto engineering/tech
small-cap, since acquired by Arcadis). Same micro/small-cap universe as ProStar → heavy overlap:
841 openers, **511 already in the CRM, 330 net-new**; 16 sell-side flagged, 172 hot clickers.
Tagged `micro,small`, `source=lytham_ibi_campaign`; goes to the **house book**, not the demo tenant
(IBI is a different issuer). House CRM after: 3,841 contacts / 88% email.

KNOWN LIMITATION: `update_classification` OVERWRITES `provenance`, so contacts that engaged BOTH
campaigns show only the latest (IBI) event — the "doubly-engaged" cross-campaign signal is not
preserved per-contact. Future campaign ingests should APPEND engagement events, not overwrite.
