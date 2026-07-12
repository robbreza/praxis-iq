# Training Manual Notes — Behaviors That Need End-User Documentation

This file tracks intentional, non-obvious product behaviors discovered during
development — things that are correct by design but would look like bugs to
a user who hasn't been told about them. Every time we find one of these, it
gets logged here so it isn't lost, and so the eventual training manual /
onboarding guide has a ready-made list instead of us trying to reconstruct
"wait, why does it do that?" months later. Add to this list any time we ship
something where two related views, stages, or features deliberately behave
differently.

---

## 1. Today's Investor Pipeline vs. Investor Targeting's Full Institution List
**Where:** Today tab ("Investor Pipeline — Strongest Signal") vs. Investor
Targeting tab ("Full Institution List").

**Behavior:** Today's Pipeline shows the top 5 funds by Engagement Score,
*excluding* any fund with a logged meeting/email/call in the last 7 days.
Investor Targeting's Full Institution List shows every tracked fund, with no
such exclusion — instead it shows a "📞 Contacted Nd ago — off Today's
Investor Pipeline until day 8" note on affected funds.

**Why this is intentional, not a bug:** Today's widget is a daily action
list — a fund you just reached out to shouldn't be nagging you to reach out
again. Investor Targeting is the full research/reference view, where hiding
a fund because you talked to them recently would actually be unhelpful.

**Training manual should cover:** Explain both views use the identical
Engagement Score ranking (same formula, same source), and that Today
deliberately shows a *subset* (recent-contact-excluded, top 5) rather than a
different ranking. Otherwise a new user comparing the two lists side by side
will assume something's broken, exactly like this session's bug report.

---

## 2. Muting a Risk Signal does not resolve it — and isn't offered everywhere
**Where it exists:** Today tab's 3 Risk Signal cards (Missing analyst
models, Beat bar above guidance, Days to consensus lock) and Markets tab's
IR Risk Dashboard signals — each has a 🔇 Mute button (1/3/7/30 day
options). Shared logic lives in `core/signals.py`.

**Behavior:** Muting hides the card for the chosen window. It does NOT
mark the underlying issue resolved or noted — when the window expires,
the card reappears exactly as it was, still red/unresolved, unless it was
actually resolved (sent) or noted in the meantime.

**Why this is intentional, not a bug:** Mute is for "I know, I'm on it,
stop showing me this every morning" — not a way to make a risk go away.
It's tracked in the same activity ledger (`signal_muted` events) as every
other action on these pages, so a training manual or an audit review can
always see when something was snoozed vs. actually handled.

**Deliberately NOT offered on:** Reports' Reg FD Flags (each flag is a
dated, individually-reviewed legal/compliance record — a HIGH-risk MNPI
flag or an open 8-K needing legal review isn't a recurring daily nag, it's
a specific item that shouldn't be snoozable) or Earnings' 5-stage Script
Generation gates (those are mandatory sequential sign-offs, not optional
signals). If a training manual walks through "why can't I mute this Reg
FD flag," that's the answer — not a missing feature.

**Training manual should cover:** A muted item is still counted as
outstanding anywhere that reads the raw resolve/note state directly
(nothing today does this yet, but a future rollup should be built to
treat "muted" as its own state, not lump it in with "resolved"). Also
worth an aside while fixing this: building out Markets' mute surfaced
that its resolve/note actions weren't logging to `activity_log` at all
(a pre-existing gap, unrelated to mute) — that's now fixed too, so
Markets actions count toward the Today page's "N tasks automated" /
"hrs saved" numbers same as Today's own actions always have.

---

## 3. Outbound email from Today/Risk Signals does not go through the mail gateway
**Where:** Every "✉️ Resolve" / "Draft clarification" / "Propose check-in"
dialog on the Today tab (and the equivalent buttons elsewhere).

**Behavior:** Clicking an analyst's name opens a `mailto:` link, which
hands off to the user's own email client (Outlook, Gmail, etc.) with a
pre-filled subject/body. The app has no visibility into whether that
email actually gets sent, edited, or discarded — "✅ Mark as sent" is a
self-reported click, not a confirmed delivery. `core/mail_gateway.py` is
a *separate, inbound-only* module (IMAP sync of the IR inbox, used to
classify replies/attachments into the Pending Inbox Items queue) — it has
no outbound send capability today.

**Why this is intentional, not a bug:** The whole app's closed-loop
pattern (Today, Markets, Reports, Earnings) is built on self-reported
"I did this" clicks logged to `activity_log`, not on verified system
events — see `core/activity_log.py`'s docstring. `mailto:` was the
lowest-risk way to let a real person's real mail client send from their
own identity without the app holding SMTP credentials.

**Training manual should cover:** Every "sent" status on this app means
"a person clicked Mark as sent," not "the system confirmed delivery."
Every logged action since Jul 10, 2026 also carries a `launched_from`
tag (e.g. "Today · Risk Signals · Missing Models") in its activity_log
detail, so it's possible to trace which page/signal originated any given
outreach — that's the current ceiling on "closed loop" without adding
real outbound send infrastructure (see chat from Jul 10, 2026 for the
fuller build-vs-buy discussion).

---

## 4. CRO has a formal Stage 3 sign-off — the original demo never gave him one
**Where:** Earnings Cycle → Script Generation → Stage 3 (now "CFO+CEO+CRO
Review").

**Behavior:** Greg Carter (CRO / Business Operations) has his own Mark
Complete button and sent/received tracking in Stage 3, same as CFO and
CEO. Stage 4 (Consolidation) won't open until all three — not just
CFO and CEO — mark their review complete.

**Why this is intentional, not a bug (and not a demo-parity item):**
Checked directly against app.py, the original demo: it never gave CRO a
"reviewers" entry at all — only IR/CFO/CEO/Legal ever had sent/received/
status tracking there. CRO's script section was always visible and
editable at every stage (which is what made him feel "in the workflow"),
but nothing ever gated advancement on his sign-off. This changed
Jul 10, 2026 at the user's explicit request, specifically going beyond
what the demo did.

**Training manual should cover:** If a future reviewer compares this
against the original Streamlit demo and asks "why does CRO get a Mark
Complete button now, the demo didn't have that" — this is why, and it was
deliberate.

---

## 5. Peer Cross-Targeting only shows real ownership after you click Refresh 13F — and even then, matching is exact-name only
**Where:** Investor Targeting → Target Database → 🎯 Peer Cross-Targeting.

**Behavior:** Selecting a peer ticker and clicking "Run cross-targeting"
only returns institutions with a CONFIRMED SEC 13F filing showing they
hold that ticker, for any peer ticker that's actually been refreshed (SEC
Intelligence tab → "Refresh 13F Institutional Holders"). Until a ticker is
refreshed, cross-targeting falls back to the original hand-typed seed
list for that ticker only — visible via the ⚠️/✅ freshness line above the
peer selector, and the ✅ marker next to each ticker in "Peers held" /
"Owns:" wherever it's shown.

**Why this is intentional, not a bug:** Before Jul 10, 2026, EVERY peer
ticker's overlap data was 100% hand-typed seed data — never real SEC
data, even for the original 3 tracked tickers (GDOT/PRTH/EEFT). That
became visible once 4 more peer tickers (FOUR/CASS/RPAY/PAX) were added
to the selector but had zero seed overlap data behind them, so selecting
them always returned nothing. `core/sec_filings.py`'s
`live_peer_overlap_map()` now wires the app's real, working SEC 13F
fetcher into cross-targeting — once a ticker is refreshed, its real
filings always outrank the seed guess for that ticker, even when they
disagree.

**A real, disclosed limitation, not a bug:** matching a fund name (e.g.
"BlackRock Small Cap Growth") against SEC's 13F filer names (e.g.
"BLACKROCK INC") is done on EXACT normalized-name match, not fuzzy/
substring. This is deliberate — SEC 13F is filed at the parent-manager
level, not per specific fund/strategy, so a fuzzy match would misattribute
one manager's whole aggregate position to every differently-named product
under that umbrella (a real, misleading false positive). The tradeoff:
some legitimate strategy-level institutions in the curated list (anything
that isn't itself the SEC filer of record — "BlackRock Small Cap Growth"
is the clearest example in the current seed data) will show "no confirmed
match" once real data exists, even if the parent firm genuinely holds the
position. That's surfaced as "unknown," never silently guessed either way.

**Training manual should cover:** If a fund a user KNOWS holds a peer
ticker shows no confirmed match after a 13F refresh, check whether that
fund's name in the institution list is the actual SEC filer of record or
a specific strategy/product under a larger manager — the latter needs a
manual override, not a bug report.

---

*(Next entries go here as they come up.)*
