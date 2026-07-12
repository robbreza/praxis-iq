# Q2 2026 Earnings — Content Refresh Checklist

USIO's Q2 2026 call is currently scheduled ~Aug 12, 2026. A lot of the
Script Generation and Prior Qtr Review tabs currently show real Q1 2026
content used as "here's what changed last quarter" reference material.
None of it is broken today — but once the Q2 call happens, this list is
everything that needs to be swapped for Q2's real content before the
workflow is used to prep for Q3. Two workflow actions (not code) also need
to happen right after the call — those are called out separately below.

Ordered by how much damage it does if left stale: items that feed directly
into AI-generated script text first, then things that are just visibly
outdated reference material, then the two non-code workflow steps.

---

## Do these two things first — no code involved

1. **Log the Q2 actuals in Consensus Tracker.** Go to Earnings Cycle →
   Consensus Tracker → "➕ Log Quarter" and enter the real Q2 print (actual
   revenue, Street consensus, AH move, etc.). Without this, "Beat/Miss
   History" and its aggregate stats keep showing Q1 2026 as the only/most
   recent quarter forever.
2. **Ingest + summarize the Q2 call transcript.** Earnings Cycle → Call
   Transcripts → upload the Q2 transcript PDF, then run "Generate AI
   Summary." This is the one item on this whole list that fixes itself
   automatically: once both Q1's and Q2's transcripts are ingested and
   summarized, the Q1→Q2 Script Actions section and each persona's Step 2
   auto-seed switch over to computed Q2-based critique on their own — no
   code change needed for that one.

---

## Feeds directly into AI-generated script text — fix these first

These aren't just stale reference info — leaving them means the *next*
quarter's AI-drafted script will actually quote or reference Q1-era
language.

- [ ] **`_Q1_TO_Q2_ACTIONS`** (earnings_page.py) — the 4 "Q1 finding → fix"
      cards. Auto-seeds Step 2 of the CFO/CRO/CEO persona panels the first
      time each is opened. *(Fixes itself once both transcripts are
      ingested+summarized — see step 2 above — otherwise needs hand-editing.)*
- [ ] **`_GUIDANCE_PRIOR_QUOTES`** — the 3 verbatim CEO guidance quotes,
      tagged by quarter. Fed straight into the Guidance & Outlook AI prompt
      as "match this voice." Add Q2's actual guidance language, drop the
      oldest quarter.
- [ ] **`_GUIDANCE_KNOWN_H2_CATALYSTS`** — the 7 H2 catalyst bullets (school
      voucher, PostCredit, RTP, Filtered Spend, etc.). Fed into the Guidance
      AI prompt. Some are already Q1-specific claims (e.g. "April —
      best-ever ACH month") that need refreshing regardless of the call date.
- [ ] **`_Q1_2026_ACTUAL`** — this is more than a number swap. It currently
      drives `ytd_rev = _Q1_2026_ACTUAL + <this quarter's form input>` inside
      the Guidance Decision Engine's math. Once Q2 is done and the workflow
      moves to Q3 prep, this needs to become a fixed `Q1 + Q2` sum instead —
      flag this one for me, it's a small code change, not a data edit you
      can make yourself.

---

## Visible reference/display content — update for accuracy, doesn't corrupt drafts

- [ ] **`_PERSONA_LAST_QUARTER`** — the verbatim quotes + key-fact tables
      shown in every persona's "Step 1 — Review: What Was Said Last
      Quarter" card. The most visible one on the page, but doesn't feed the
      AI directly (a human reads it and decides what to type into Step 2).
- [ ] **Prior Qtr Review's hero stats** — the call-replay card ("May 13,
      2026 · 72 minutes") and the 5-metric strip (AH reaction, revenue,
      EPS, volume, call length). Most visually obvious stale content on
      that whole tab.
- [ ] **Analyst note alignment list** — the 5 "HCW/Ladenburg said X" cards
      on Prior Qtr Review.
- [ ] **`_Q1_QA_TOPICS`** — the 8 Q&A pre-emption topics. No auto-refresh
      path (unlike `_Q1_TO_Q2_ACTIONS`) — this one always needs hand-editing.
- [ ] **`_Q1_SECTION_TIMING` / `_Q1_SECTION_WORDCOUNT`** (and the derived
      `_HISTORICAL_WPM` / `_SECTION_HISTORICAL_MINUTES`) — the timing/word-
      count benchmarks. These also feed the live pacing estimate shown next
      to every draft box, so it's not purely cosmetic — the "on pace vs.
      historical norm" feedback will silently compare against Q1 numbers
      until this is updated.
- [ ] **`CLIENT_REGISTRY["usio"]["financials"]`** (config/client_config.py)
      — the `last_quarter`/`last_rev`/etc. snapshot. Not read by
      earnings_page.py itself, but exposed to other pages via `CF()`.
- [ ] **`guidance_vs_street_note` / `bar_risk_level` / `bar_risk_note`**
      (config/client_config.py) — these aren't stale data so much as a
      judgment call that needs re-entering for Q3's pre-call read once Q2
      has happened and resolved.

---

## Not on this list (already handled or doesn't need quarter-over-quarter changes)

- Call Opening's exec titles/Q&A-only participant roster — only needs
  updating if someone's title or the Q&A roster actually changes, not
  because the quarter rolled over.
- FY2025 quarterly figures, seasonal weights, full-year guidance range —
  valid through all of FY2026, not "last quarter" data.
