# IRconnect — Demo Script & Shot List

**Product:** IRconnect (by Praxis Point) — the IR intelligence platform
**Demo tenant:** Northlake Payments, Inc. (NASDAQ: NLKP) — *fully illustrative; no real client data*
**Login for capture:** staff (PPADMIN) → switch tenant to *Northlake Payments, Inc.*, or boot with `DEV_TENANT=demo`
**Runtime target:** ~3–4 min full walkthrough; the Prep Cards segment stands alone at ~45–60s
**Surface for capture:** real Chrome at `http://localhost:8502` (the in-app browser pane freezes on capture — do not use it)

> One-line pitch: *An inbound analyst invite becomes a fully-routed New York roadshow, and management walks into every meeting with a prep card built live off real ownership data — not a rented contact database.*

---

## The arc (why this order)

The demo is deliberately built around a single, believable day of IR work rather than a feature tour. It starts with a real trigger (an analyst's conference invite lands in the inbox), turns that into a planned non-deal roadshow, and pays off on the thing IR actually loses sleep over: *walking into eight back-to-back meetings knowing exactly who's across the table.* The Prep Cards scene is the close because it's the differentiator competitors can't fake — it reads off the client's own 13F-derived ownership book, so a holder looks like a holder and a prospect looks like a prospect, with the numbers to back it.

---

## Scenes

| # | On screen (action) | Narration (VO) | What it proves |
|---|--------------------|----------------|----------------|
| 1 | **Today** page — the morning brief. Let the price band, risk signals, and "talking points for management" sit for a beat. | "This is the IR team's morning. One screen: where the stock is, what the Street is doing, and the three things that actually need a decision today." | IRconnect is a daily operating surface, not a quarterly report. |
| 2 | **IR Inbox** → the inbound request from **Ellis Grant, Ashfield Research** (invite to the NY payments conference). | "An analyst just invited the company to their New York conference. In most shops that's a forwarded email and a scramble. Here it's the start of a workflow." | Real inbound demand is the trigger — not a cold list. |
| 3 | From the request, **Plan the NDR** → the *New York — Ashfield Payments Conference* trip. | "One click turns the invite into a roadshow. We're now building the day around being in the city." | Inbound → planned trip in one move. |
| 4 | **NDR/CRM → the trip → the metro targets table** ("Fill open slots — 13 available targets in New York"). | "IRconnect already knows who to see in New York — ranked by conviction off real 13F filings, not a database you rent. Existing holders to defend, and the high-fit funds that *should* own you." | Targeting is built from the client's real ownership graph. |
| 5 | **Active NDRs** — the scoped itinerary: 8 meetings, the **Point72 car leg to Stamford** (6:39 AM pickup, ~71 min), the **catered working lunch**, the **same-venue 10-min turnovers**. | "Eight meetings, routed. It opens with a car up to Point72 in Connecticut, holds the middle of the day at the conference hotel, and paces the turnovers so nothing starts late." | The tool plans a *physically real* day — geography, travel, meals, timing. |
| 6 | **PREP CARDS** tab. Expand **Halewood Capital Management** (holder), then **Point72** (prospect). Read the two side by side. | "This is the payoff. One card per meeting, pulled live from tracked ownership data. Halewood is an existing holder — so the card leads with their position: 1.4 million shares, adding, and the peers they *also* own. Point72 isn't in yet — so the same tool frames it as a priority conversion. A holder reads like a holder; a prospect reads like a prospect." | The differentiator: prep is generated off the real book, correctly typed per fund. |
| 7 | Back out to the trip header (0/8 completed · 6 non-holders). Optional: Post-NDR Debrief tab. | "Six of the eight are funds that don't own the stock yet. That's the whole point of a roadshow — and IRconnect walks the team in ready for every one." | Closes the loop: reach + intelligence, measured. |
| 8 | **Mobile** (phone viewport). The CFO opens IRconnect on her phone → "Your meetings" now lists the NY NDR stops with an **NDR** badge → she taps **Point72** (her 8:00) → the **same prep card** opens on the phone. | "The morning of the roadshow, the CFO doesn't open a laptop. She opens her phone in the car — every NDR meeting is right there, and tapping one gives her the exact same prep card the team built: who they are, the position, what to bring. She walks in ready." | The intelligence travels: desktop-built prep, pulled up on a phone before the meeting. |

---

## Scene 6 — Prep Cards (the money shot), verbatim reference

Capture these two expanded cards. The on-screen text below is what the live demo renders — read the bolded lines aloud.

**Halewood Capital Management — *Existing holder*** (caption: *Peter Vance, Portfolio Manager · New York, NY · Hedge Fund · Existing holder · Engagement 91*)
- The read: *"Existing holder — a defend-and-deepen meeting: protect the position and grow it. They're warm: adding to the position, on your IR site 3× in 30d. Last conversation read positive."*
- **Why they matter now: "Holds 1,420,000 shares (~$46.6M · 1.2% of their book) — adding (+42,000 sh last quarter)."**
- *"Also owns PYRA, CLRT, VNTG (SEC 13F) — deep in the space; reinforce why you're the best expression of it."*
- Bring: *"The side-by-side vs PYRA, CLRT, VNTG — they own the peers too; make the case you're the best expression of the group."*

**Point72 Asset Management — *Prospect · Fit 92*** (caption: *Adam Feldman, Sector PM · Stamford, CT · Multi-strategy · Prospect · Fit 92 · Engagement 14*)
- The read: **"High-fit prospect (Fit 92/100) — a priority conversion, not a cold intro."**
- Why they matter now: *"Marquee multi-strat; sector PM engaged — the Connecticut anchor that opens the NY swing."*

> The contrast is the point: **same tool, opposite framing**, because it reads off whether the fund actually holds the stock — no manual tagging, no contradictions.

---

## Voiceover script (final — as narrated in IRconnect-demo-narrated.mp4)

Neural TTS via edge-tts, voice `en-US-AndrewNeural`, rate −4%. Each scene is held to its line's length + ~1.1s. Swap the voice by changing `VOICE` in `scratchpad/build_narrated_video.py`.

- **Title:** "This is IRconnect. Investor targeting, roadshows, and meeting prep, in one place."
- **1 · Today:** "It starts with the morning brief. One screen: where the stock is, what the Street is doing, and the few things that actually need a decision today."
- **2 · IR Inbox:** "Every investor email is parsed, classified, and filed automatically. Models, research, meeting requests, all ready for one click."
- **3 · NY trip:** "When an analyst sends a conference invite, it becomes a fully planned New York roadshow, built straight from that inbound request."
- **4 · Targets:** "IRconnect already knows who to see in the city. Ranked by conviction, off real thirteen-F filings, not a database you rent."
- **5 · Plan New NDR:** "And you can spin up a brand new roadshow from any inbound request in a single click."
- **6 · Prep Cards:** "Here's the payoff. A prep card for every meeting, off the real ownership book. For a holder, it shows whether they're adding or trimming, and that they sit underweight versus a peer they already own. So the ask writes itself."
- **7 · Mobile list:** "On the road, those same meetings show up on the CFO's phone, in order."
- **8 · Mobile prep card:** "She taps one, and the prep card is right there, so she walks into every meeting ready."

---

## Scene 8 — Mobile: the CFO pulls up the prep card on her phone

The payoff for "the NDR is built — now the CFO needs it on the road." After the desktop plans the trip,
the NDR meetings surface on the phone automatically, and each opens the **same** `render_prep_card_body`
briefing the desktop shows (one shared renderer — no separate mobile-lite version).

Capture flow (phone viewport, 390×844):
1. Bottom tab bar → **Home** (the on-the-road view). Header reads "On the road."
2. **Your meetings** now lists the NY NDR stops, each with a small **NDR** badge and its metro.
3. Tap **Point72 Asset Management** (8:00 AM) → the prep card opens full-screen:
   *"High-fit prospect (Fit 92/100) — a priority conversion, not a cold intro."* + why-they-matter + a **Capture a note** box for right after.
4. (Optional contrast) Back → tap **Halewood** (10:00) → *"Existing holder — defend-and-deepen… Holds 1,420,000 shares (~$46.6M · 1.2% of their book) — adding."*

Talk track: *"Same briefing, in her hand, before she's out of the car."*

Build note: mobile "Your meetings" merges `scheduled_meetings` + NDR trip meetings; the tap routes NDR
stops to `mobile_page._open_ndr_prep`, which calls the shared `investors_page.render_prep_card_body`.

---

## The itinerary (reference — Scene 5)

*New York — Ashfield Payments Conference · 2026-09-03 · The Pierre, 2 E 61st St · 8 of 8 slots filled*

| Time | Fund | Who | Type | Note |
|------|------|-----|------|------|
| 8:00 | Point72 Asset Management | Adam Feldman, Sector PM | Prospect · 92 | CT field visit; 6:39 AM car, ~71 min |
| 10:00 | Halewood Capital Management | Peter Vance, PM | Holder · 74 | Current owner — adding; deepen |
| 11:00 | Ruane, Cunniff & Goldfarb | Elena Marsh, Analyst | Prospect · 86 | Marquee concentrated value |
| 12:00 | GAMCO Investors (Gabelli) | Frank DeLaria, PM | Prospect · 80 | Catered working lunch (~50 min) |
| 1:00 | Brentmoor Capital Management | Julia Reyes, Sr Analyst | Holder · 69 | Current owner — maintain |
| 2:00 | Neuberger Berman | Amira Osei, PM | Prospect · 83 | Small-cap sleeve |
| 3:00 | First Eagle Investment Mgmt | Daniel Okafor, Analyst | Prospect · 82 | Value / patient capital |
| 4:00 | Royce Investment Partners | Steven Kohl, PM | Prospect · 91 | Small-cap specialist — strong fit |

---

## Capture notes (for the recorder / GIF pass)

- **Tenant:** confirm header reads *Northlake Payments, Inc.* and *Dana Whitfield — IR Director* before recording.
- **Window:** ~1568×773 (current Chrome) is fine; keep it stable across the session so frames align.
- **Navigation quirk:** NiceGUI nav items and Quasar tabs respond reliably to a real Chrome click; the left rail *NDR/CRM* item expands, then pick the trip. The **Prep Cards** tab is a Quasar tab at the top of the Roadshow surface.
- **Pacing:** hold ~1.5–2s on each expanded prep card so the numbers are legible in the GIF; scroll slowly.
- **Segments to export:** (a) full walkthrough Scenes 1–7; (b) a standalone **Prep Cards** clip (Scene 6) for embedding in decks/emails.
- **Existing assets** (Downloads, 2026-08-21): `northlake_ndr_create_demo.gif`, `northlake_ndr_scoped_itinerary.gif`, `northlake_ny_ndr_demo.gif`, `northlake_ny_ndr_targets.gif`. The new Prep Cards clip is the missing piece; the others already cover Scenes 3–5.
