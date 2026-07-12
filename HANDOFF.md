# Praxis Point IR Platform — Handoff to Claude Code

## Context
Parent company: **Praxis Point Advisory** (an IR advisory firm).
First client: **USIO Inc. (NASDAQ: USIO)**. More clients will be onboarded later —
the app must NOT assume "USIO" is permanent anywhere in the codebase.

`app.py` in this folder is a working demo (~12,750 lines, single file, Streamlit).
It is functional but was never split into modules, and it hardcoded the client
name/contacts throughout. This handoff exists to turn it into a real,
multi-tenant, production app.

## Security — already fixed in this copy, verify on your machine
The original demo had a live Anthropic API key hardcoded in 3 places in
`app.py`. That key has been **removed from this copy** and replaced with
reads from `os.environ.get("ANTHROPIC_API_KEY")`. Before running this:

1. The user (not you) already generated a fresh key and revoked all previous
   ones via console.anthropic.com/settings/keys.
2. Copy `.env.example` to `.env` in this same folder and fill in the real key.
3. `.env` is already covered by `.gitignore` — confirm it never gets committed.
4. Do NOT reintroduce any hardcoded key anywhere in this codebase, including
   in comments, test files, or commit history.

## Design direction
User supplied a reference screenshot of the target look: warm off-white/cream
canvas, graphite body text, a single confident purple/indigo accent, soft
rounded cards with thin borders, clean uppercase micro-labels, generous
whitespace. This replaces the current dark navy (#0F172A background, #3B82F6
blue accent) theme entirely. The old theme's CSS block lives inline in
`app.py` around lines 822–1100+ (search for `st.markdown("""` followed by
`<style>`) — pull every color value out into a token file rather than editing
in place.

## Multi-tenancy requirement (confirmed by user)
- Real multi-tenant switching is required, not just a config swap for one
  client at a time.
- A tenant/client switcher UI element is needed (e.g., dropdown near the logo).
- `st.session_state` is NOT sufficient for persistent multi-client data
  (scripts, Reg FD logs, surprise-tracker history) — it's per-browser-session
  memory only. A real lightweight database is needed (SQLite is fine to
  start; every table needs a `client_id` column, or use one DB file per
  tenant — pick based on expected client count, see open questions below).
- Currently ~296 hardcoded "USIO" references and ~59 hardcoded "Paul Manley"
  references throughout `app.py` — these all need to route through a client
  registry object instead of literals.

## Hosting
Low-cost to start (USIO is standing this up), but must not block adding
client 2+ later. Streamlit Community Cloud is the cheapest fast path but
isn't built for real tenant isolation; a small VPS or Render/Railway host
(~$5–20/mo) with a proper DB is the likely next step once client 2 is real.
Don't over-build for scale that doesn't exist yet — but don't paint into a
single-tenant corner either.

## Proposed target architecture
```
praxis_point_ir/
├── app.py                      # thin entrypoint: page routing only
├── config/
│   ├── client_config.py        # client registry — one record per tenant
│   └── theme.py                # design tokens (colors, fonts, spacing)
├── core/
│   ├── session.py              # session_state init/helpers
│   └── security.py             # secrets loading — no literals, ever
├── pages/
│   ├── today.py, investors.py, earnings.py, markets.py,
│   │   outreach.py, calendar.py, reports.py, settings.py
├── components/
│   ├── cards.py, nav.py, status_pills.py, script_workflow.py
├── services/
│   ├── mail_gateway.py, sec_edgar.py, anthropic_client.py, pdf_export.py
└── data/
    └── seed/  (Q1 2026 surprise-tracker seed data, etc.)
```

## Current feature inventory (all real, none are placeholders)
- **Today** — landing dashboard, executive "Today's Story" summary
- **Investors** — Buy-Side Intelligence (pre/post-earnings modes), NDR
  Planner, Meeting Hub
- **Earnings** — 5-step script workflow (Review → What's New → Draft →
  Review/Edit → Insert) per speaker (Paul/Michael/Greg/Louis), Q&A Prep,
  CFO Portal view, Version History, Surprise Tracker (History / Log
  Quarter / Pre-Call Setup, seeded with real Q1 2026 data)
- **Markets** — market/peer data views
- **Outreach**, **Calendar** — scheduling and investor comms
- **Reports** — Reg FD compliance log + CSV export, downloadable reports
- **Settings** — IRConnect email/SMTP config, data source status,
  quiet period dates
- Mail Gateway (IMAP/SMTP via IRConnect), PDF export via `reportlab`,
  5 embedded base64 report images

## Known bug already fixed in the demo (do not reintroduce)
Version History used to duplicate entries because Stage 1–5 submit buttons
in both the CFO Portal view and the IR Earnings page view wrote to the same
shared `script_state` object without a completion gate. Fixed via an
`_add_version()` dedup guard. If refactoring this into `services/` or
`components/`, preserve the guard — don't let two call sites append twice.

## Step-by-step build order (recommended)
1. Extract `config/client_config.py` — move every hardcoded "USIO" and
   "Paul Manley" literal into a client registry record.
2. Extract `config/theme.py` — pull the inline CSS block into design tokens;
   implement the neutral/cream palette here, reviewable in isolation before
   touching page logic.
3. Split `pages/` — one file per nav section, each `if page == ...` branch
   becomes an imported function.
4. Extract the repeated 5-step script workflow into one shared
   `components/script_workflow.py` used by all 4 speakers + Q&A Prep.
5. Move all secrets to `.env` / environment variables — confirmed already
   started in this handoff.
6. Add the SQLite (or equivalent) data layer with `client_id` scoping for
   anything that needs to persist beyond one browser session.
7. Re-seed and regression-test each page against current demo behavior.

## Open questions for the user (ask before big structural decisions)
1. SQLite acceptable to start, or is a hosted Postgres already expected?
2. Do tenants need fully separate logins (client 2 must never see USIO's
   nav), or is this internal Praxis Point staff switching between clients
   under one login?
3. Rough client count expected in year one (2 vs 10 changes how much to
   build into the registry now).
4. Confirm hosting target once decided, so `.env`/secrets handling matches
   that platform's conventions.
