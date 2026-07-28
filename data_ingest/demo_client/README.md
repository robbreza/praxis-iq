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

## Old contact lists — LPVIC / TAAL / Northland (Jul 2026, house book)
`ingest_oldlists.py` — three OLD (2021-22) lists: **LPVIC** (Lytham VIC ACT list, Sep 2022 —
Company/Contact/Email/Phone/Title), **TAAL** (Lytham 1x1 campaign opens, Jan 2021), **Northland**
(Northland Capital Markets call list — Company/Name/Email/City/Quality). Scan first: 1,679 distinct
emails across the three, low cross-file dup (LPVIC∩TAAL 24, TAAL∩Northland 15), 770 already in CRM,
~909 net-new. Kept fund/email/phone (+title/city); sell-side flagged; `validation_status=stale`,
`email_status` left UNKNOWN (2021-22 — can't vouch for current deliverability). Tagged micro,small.

RESULT: LPVIC +61, TAAL +1,052 ingested. **Northland +202 ingested 2026-07-27** once the drive was
reconnected (initial run missed it — the E:\ drive had been pulled). House CRM after all three: ~5,041
contacts / 91% email / 1,472 phone.

OUTBOUND-EMAIL CAUTION (recorded per the user's question): these are old lists — re-validate before
any send; respect CASL (Canada) / GDPR (UK) / CAN-SPAM (US); route through a proper IR platform with
unsubscribe, not a cold blast. Phone-first outreach avoids the consent issue and the phones age better.

## Wiza LinkedIn equity-research export (2022, house book)
`ingest_wiza.py` — Wiza LinkedIn export of "Global Equity Research" professionals (analysts /
research boutiques — a segment distinct from the investor book). Two files; WIZA_B (490) is a
superset of WIZA_A (431), so only B loaded. Rich schema: Wiza-VERIFIED email + type + title +
company + location + LinkedIn + company_country. **490 ingested (only 10 overlapped the CRM — ~480
net-new)**, title-classified, LinkedIn URL kept in source_ref/provenance, 58 personal emails flagged.
`validation_status=probable` (Wiza-verified, but 2022 — re-validate before outbound). House CRM
after: 4,897 contacts / 90% email / 1,472 phone.
NOTE: firm_type sell-side heuristic flagged 0 — most independent-research boutiques don't match the
broker/securities keywords; the research titles are captured but firm_type may need a manual pass.

## Doubly-engaged tagging (2026-07-27)
`tag_doubly_engaged.py` — recovers the cross-campaign signal lost to the provenance-overwrite:
tags the **434 emails / 440 contacts** that opened BOTH Lytham 1x1 invites (ProStar ∩ IBI) as
`DOUBLY-ENGAGED` (queryable via `provenance LIKE '%DOUBLY-ENGAGED%'`), `validation_status=engaged`,
`confidence>=90`. These are the highest-intent small-cap meeting-takers. NOTE: the full send lists
(~2,600 non-openers/campaign) are unavailable — only the opener/click exports exist.

## Wiza firm_type pass (2026-07-27)
`wiza_firmtype_pass.py` — the Wiza ingest classified firm_type from the NAME only, so research
boutiques defaulted to `asset_manager`. Re-derived firm_type from Wiza's `company_industry` /
`subindustry` / `description` (by email, scoped to the Wiza cohort): **247 asset_manager · 93
broker_dealer · 60 bank · 29 independent_research (new label) · 29 ria · 21 other · 5 PE · rest**.
~182 sell-side/research/vendor contacts are no longer mislabeled buy-side, so the asset_manager
(buy-side target) set is clean.

## Mislabeled-RIA fix (2026-07-27)
`reclassify_mislabeled_ria.py` — `firm_type_for()` returns `ria` for any name containing
"Advisors/Advisory", so 7 institutional funds/hedge funds were mislabeled (Rosalind, Apis Capital,
Long Cast, Kopp, Columbia Pacific, Yorkville, Conestoga Capital Advisors — the last had 12 records
from the Philly sweep). Reclassified **23 contacts -> asset_manager**. Doubly-engaged buy-side cut:
395 -> 402; RIA cut 32 -> 25 (genuine wealth firms). Lesson: the "advisors" name-rule over-fires;
a real institutional vs wealth split needs more than the name (industry/AUM/strategy).
