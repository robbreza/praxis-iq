"""
config/client_config.py — Client / tenant registry for the Praxis Point IR platform.

Praxis Point Advisory serves multiple IR clients over time. Every client's
identifying data (ticker, contacts, executives, analysts, peers, earnings
calendar, financial snapshot, management guidance) lives here as ONE RECORD
per tenant in CLIENT_REGISTRY, instead of being hardcoded as literal strings
scattered across app.py and the page modules.

USIO is the first client and is fully wired up below.

--- Onboarding client #2 (or #3, #4...) ---
Add a new entry to CLIENT_REGISTRY with the same shape as "usio". That's it —
every function below (C, CI, CA, CP, CE, CF, CT, CG, get_client,
team_email_lookup) automatically works for any client_id in the registry.
No changes needed anywhere else, PROVIDED a page/component calls these
functions instead of hardcoding a client's name directly. That proviso does
NOT yet hold everywhere — see "Known gaps before a real client #2" below.

--- Known gaps before a real client #2 (noted 2026-07-09) ---
page_modules_nicegui/earnings_page.py's Script Generation tab (Guidance & Outlook
Decision Engine + the per-persona Review/What's-New/Generate canvas) had a
growing amount of business logic living as Python module constants in that
file instead of CLIENT_REGISTRY lookups — it would have silently produced
USIO-flavored output for any other tenant. Two different categories, needing
two different fixes:

1. CLIENT CHARACTERISTICS/POLICY (→ belongs in CLIENT_REGISTRY as new
   per-client fields, same pattern as fy_guidance/q2_consensus_rev above).
   FIXED 2026-07-12 — moved into "tone_band_m", "fls_items", "guidance_policy"
   (with prior_fy_quarterly_revenue/seasonal_weights/fy_growth_low+high/
   range_deltas_m/known_h2_catalysts/closing_line/operator_handoff sub-keys),
   and per-executive "title" + top-level "qa_only_participants" below.
   earnings_page.py now reads all of these via CT()/C() instead of hardcoding
   USIO's numbers/language/exec titles as module constants. A client that
   omits "guidance_policy" gets an empty dict back (CT default) rather than
   USIO's numbers leaking through — the Guidance & Outlook Decision Engine's
   math will honestly read as zeros/blanks for that client instead of
   fabricating a plausible-looking but wrong number, same "disclosed
   approximation over fabricated precision" philosophy as core/risk_scorecard.py.

2. VERBATIM HISTORICAL CALL CONTENT (→ arguably shouldn't be hand-typed
   constants at all, for ANY client, including USIO next quarter — NOT
   fixed by this pass, still open):
   _PERSONA_LAST_QUARTER's quotes/tone tags and _GUIDANCE_PRIOR_QUOTES (both
   still in earnings_page.py) are literal transcript excerpts from Q1 2026.
   These are exactly the kind of data core/transcripts.py already ingests
   and stores per quarter — the real fix isn't "move to client_config," it's
   teaching that module to extract verbatim quotes/tone read from an
   ingested transcript automatically, so this section self-updates each
   quarter for any client instead of needing a human to hand-edit
   earnings_page.py every cycle. Left as-is; this is a separate, larger
   feature build (transcript-driven quote extraction), not a config move.

--- How "the active client" works ---
get_active_client_id() reads from Streamlit's st.session_state. Nothing sets
st.session_state["active_client_id"] yet (there's no tenant-switcher UI in
the app yet — see HANDOFF.md's "Multi-tenancy requirement" and the
"pages/" step later in the build order), so today every session silently
falls back to DEFAULT_CLIENT_ID ("usio"). Once a real switcher dropdown is
added, it just needs to call set_active_client_id(new_id) and every page
that uses C()/CI()/etc. updates automatically — no other code changes.
"""

import contextvars
import os
import pandas as pd

# ─────────────────────────────────────────────────────────────────────────
# CLIENT_REGISTRY — one record per tenant
# ─────────────────────────────────────────────────────────────────────────
CLIENT_REGISTRY = {
    "usio": {
        "ticker": "USIO", "name": "Usio, Inc.", "exchange": "NASDAQ",
        "last_price": 2.15, "price_date": "Jun 26, 2026",
        "market_cap_m": 61, "ev_m": 72, "sector": "Fintech / Payments",
        "fy_guidance": "10-12% revenue growth",
        "q2_consensus_rev": 25.1, "peer_median_ev_rev": 2.3,
        # Pre-Call Assessment (Earnings > Consensus Tracker): mirrors
        # app.py's hardcoded Q2 2026 pre-call snapshot ("Bar risk HIGH",
        # "-$0.6M below street"). These are point-in-time IR judgment calls,
        # not derived math, so they're stored as plain client-record values
        # the same way app.py hardcoded them, rather than computed from a
        # formula that doesn't actually exist upstream.
        "guidance_vs_street_note": "-$0.6M below street",
        "bar_risk_level": "HIGH", "bar_risk_note": "Stock +35% YTD vs flat sector",
        "ir_contact": {"name": "Paul Manley", "title": "SVP, Investor Relations",
            "email": "paul.manley@usio.com", "irconnect": "irconnect@usio.com"},
        # "title" per exec is read by earnings_page.py's Call Opening card
        # (_call_opening_text) to introduce each speaker by role — moved out
        # of that file's _CALL_OPENING_EXEC_TITLES module constant 2026-07-12
        # so a client with a different exec roster/titles isn't stuck with
        # USIO's. A role/client with no "title" set falls back to a generic
        # "our {role}" there rather than crashing.
        "executives": {
            "CEO": {"name": "Louis Hoch", "email": "lhoch@usio.com", "title": "our Chairman and CEO"},
            "CFO": {"name": "Michael White", "email": "mwhite@usio.com",
                    "title": "Senior Vice President and Chief Accounting Officer"},
            # CRO — used by the Script Generation tab's per-persona canvases
            # (page_modules_nicegui/earnings_page.py). Not every client will
            # have this role; that page falls back to a generic placeholder
            # for any client whose executives dict omits it, rather than
            # assuming a name.
            "CRO": {"name": "Greg Carter", "email": "gcarter@usio.com",
                    "title": "Executive Vice President of Payment Acceptance and our Chief Revenue Officer"},
            "Legal": {"name": "Legal Counsel", "email": "legal@usio.com"}},
        # Non-presenting execs introduced as available for Q&A only, read by
        # the same Call Opening card. Moved out of
        # _CALL_OPENING_QA_ONLY_PARTICIPANTS 2026-07-12 — a client with no
        # such participants just gets an empty/omitted clause.
        "qa_only_participants": "Houston Frost, our Chief Product Officer, and Jerry Uffner, Head of Card Issuing,",
        # $ band around Street consensus treated as "in line" rather than a
        # beat/miss, read by earnings_page.py's _tone_context (drives the
        # beat/in-line/miss word-choice register across the IR/CFO/CEO
        # drafts). Right order of magnitude for USIO's ~$60M market cap;
        # moved out of a hardcoded 0.5 in that function 2026-07-12 so a
        # client 10-100x the size isn't stuck with the same tiny band.
        "tone_band_m": 0.5,
        # Forward-Looking-Statements checklist for the Script Generation
        # tab's Legal Sign-Off stage — moved out of earnings_page.py's
        # FLS_ITEMS module constant 2026-07-12 (that constant was already
        # flagged, when built, as needing this exact treatment for a future
        # client with different guidance language). A client with none
        # configured sees an empty checklist rather than USIO's items.
        "fls_items": [
            ("FLS-01", "10-12% full-year revenue growth guidance"),
            ("FLS-02", "Continued positive Adjusted EBITDA"),
            ("FLS-03", "Gross margins expected to improve in H2 2026"),
            ("FLS-04", "PayFac expected to remain growth engine of card business"),
            ("FLS-05", "Prepaid headwind expected to diminish in H2"),
            ("FLS-06", "Interest income headwind expected to stabilize in H2 and lap in Q1 2027"),
            ("FLS-07", "SG&A not expected to materially increase this year"),
            ("FLS-08", "New PayFac clients not yet fully ramped will contribute to H2 revenues"),
            ("FLS-09", "FY2027 operating leverage expected to be visible in EPS line"),
            ("FLS-10", "Analyst coverage expected to expand post-Q2 earnings"),
        ],
        # Guidance & Outlook Decision Engine inputs (earnings_page.py's
        # _guidance_math/_guidance_range_for_action/_generate_guidance_draft)
        # — moved out of that file's _FY2025_Q1..Q4/_SEASONAL_WEIGHTS/
        # _FY_GUIDANCE_GROWTH_LOW+HIGH/_GUIDANCE_KNOWN_H2_CATALYSTS module
        # constants 2026-07-12. All of this is USIO's real business shape
        # (Q2 heaviest quarter, Q3 lightest, its own stated 10-12% growth
        # policy, its own named H2 initiatives) — a different client could
        # have a completely different seasonal curve, growth policy, or no
        # formal guidance practice at all, so a client that omits
        # "guidance_policy" entirely gets an empty dict (CT() default) and
        # the Decision Engine's math will honestly read as zeros/blanks
        # rather than silently reusing USIO's numbers.
        "guidance_policy": {
            "prior_fy_label": "FY2025",
            "prior_fy_quarterly_revenue": {"Q1": 22.01, "Q2": 19.90, "Q3": 21.10, "Q4": 22.24},
            "seasonal_weights": {"Q1": 0.238, "Q2": 0.347, "Q3": 0.179, "Q4": 0.237},  # 2-yr avg, FY2024+FY2025
            "fy_growth_low": 0.10, "fy_growth_high": 0.12,
            # Flat-dollar range nudges per guidance action, sized for USIO's
            # scale — see config docstring gap-inventory item 1 for why this
            # is a per-client constant rather than a %-of-revenue formula
            # (either would work; this is the simpler of the two options
            # noted there).
            "range_deltas_m": {"raise_low": 1.0, "raise_mid": 1.5, "narrow": 0.5},
            "known_h2_catalysts": [
                "School voucher program — expected to exceed $1 billion in re-disbursements",
                "PostCredit — market-ready in the coming months, auto-account for new clients",
                "Real-Time Payments — grew from ~2,000 to 200,000+ transactions/month, higher margin than PINless",
                "Filtered Spend — 2,000+ merchants live, 8,000+ remaining to be boarded through mid-2026",
                "New bank sponsor for card issuing — signed agreement, programs scaling in H2",
                "New printer installation — 4x speed",
                "April — best-ever ACH month",
            ],
            "closing_line": "We remain committed to building a stronger, more innovative, and more valuable Usio.",
            "operator_handoff": "Operator, you can now open the call to questions.",
        },
        "analysts": [
            {"name": "Scott Buck", "firm": "H.C. Wainwright", "pt": 4.00, "status": "active", "email": "sbuck@hcwco.com"},
            {"name": "Jon Hickman", "firm": "Ladenburg Thalmann", "pt": 6.25, "status": "active", "email": "jhickman@ladenburg.com"},
            {"name": "Michael Diana", "firm": "Maxim Group", "pt": None, "status": "inactive", "email": "mdiana@maxim.com"},
            {"name": "Barry Sine", "firm": "Litchfield Hills Research", "pt": None, "status": "inactive", "email": "bsine@litchfieldhills.com"},
            {"name": "Gary Prestopino", "firm": "Barrington Research", "pt": None, "status": "inactive", "email": "gprestopino@barrington.com"},
        ],
        # Tiered peer architecture (2026-07): USIO is a hybrid — Merchant
        # Services (PayFac / card / ACH / prepaid) + Output Solutions (billing /
        # print). "primary" peers drive the valuation median; "reference"
        # large-caps set the industry growth/margin bar but are excluded from the
        # median (you don't apply a $100B processor's multiple to a micro-cap).
        # closest_analog flags the single tightest operating comp.
        "peers": [
            {"ticker": "RPAY", "name": "Repay Holdings", "ev_rev": 2.8, "tier": "primary",
             "segment": "Integrated card + ACH + billing/output", "closest_analog": True},
            {"ticker": "FOUR", "name": "Shift4 Payments", "ev_rev": 4.2, "tier": "primary",
             "segment": "Card acceptance / PayFac"},
            {"ticker": "PSFE", "name": "Paysafe", "ev_rev": 1.5, "tier": "primary",
             "segment": "Integrated payments"},
            {"ticker": "CSGS", "name": "CSG Systems", "ev_rev": 2.2, "tier": "primary",
             "segment": "Billing / customer comms (output)"},
            {"ticker": "PAY", "name": "Paymentus Holdings", "ev_rev": 2.5, "tier": "primary",
             "segment": "Bill presentment / EBPP (output)"},
            {"ticker": "CASS", "name": "Cass Information Systems", "ev_rev": 2.2, "tier": "primary",
             "segment": "Payment information / billing"},
            {"ticker": "GDOT", "name": "Green Dot", "ev_rev": 1.2, "tier": "primary",
             "segment": "Prepaid / card issuing"},
            # Fiserv (FI) removed 2026-07-16 — too big to inform a micro-cap comp, and it
            # carried no live data on either side: Yahoo has no quote for the post-rebrand
            # ticker, and SEC still indexes it under the pre-2023 FISV. Its whole row was
            # curated estimate (ev_rev 5.0 / gm 60.0 -> an 8.3x EV/GP that is one guess
            # divided by another) sitting next to live peers.
            {"ticker": "GPN", "name": "Global Payments", "ev_rev": 4.5, "tier": "reference",
             "segment": "Large-cap processor (reference)"},
            {"ticker": "TOST", "name": "Toast", "ev_rev": 3.5, "tier": "reference",
             "segment": "Large-cap fintech (reference)"},
        ],
        "earnings": {"current_quarter": "Q2 2026", "earnings_date": "2026-08-12",
            "call_time": "4:30 PM ET", "dial_in": "+1-844-883-3890",
            "quiet_start": "2026-07-20", "quiet_end": "2026-08-13"},
        "financials": {"last_quarter": "Q1 2026", "last_rev": 25.47, "last_rev_yoy": 16.0,
            "last_eps": 0.00, "last_gm": 20.2, "last_ebitda": 0.8, "cash_m": 7.7,
            # Shares out + debt feed the live EV/Revenue in the peer-benchmarking
            # analysis (core/benchmarking_engine.py); USIO is roughly net-cash.
            "shares_out_m": 26.8, "debt_m": 0.0},
        # Note: not referenced anywhere in the original demo (verified — dead
        # data in the old single-file version). Kept here, not deleted, in
        # case a future guidance-tracking feature wants it.
        "guidance": {
            "EPS Est":          0.20,
            "Revenue Est ($M)": 95.0,
            "EBITDA Est ($M)":  7.0,
            "note":             "FY2026 mgmt guidance: 10-12% revenue growth, positive adj. EBITDA",
        },
    },
    # ── Client #2: WRAP (Wrap Technologies) — DEMO tenant, PUBLIC INFO ONLY ──
    # Onboarded from public sources only (EDGAR + market feed). Every private
    # field a real engagement would carry — guidance, consensus, IR contacts,
    # executive detail, analyst coverage, tone/FLS policy — is intentionally left
    # EMPTY (matching usio's field types), because none of it is public. The
    # accessors return those blanks rather than fabricating a number or leaking
    # usio's, so the guidance/script surfaces honestly read as "not disclosed"
    # for WRAP. What IS populated is the public identity + the independently
    # chosen peer set (in the peer_universe data layer, keyed client_id="wrap").
    "wrap": {
        "ticker": "WRAP",
        "name": "Wrap Technologies, Inc.",
        "exchange": "Nasdaq",
        "last_price": 2.05,               # public market feed, 2026-07-17
        "price_date": "Jul 17, 2026",
        "market_cap_m": 114,
        "ev_m": 115,
        "sector": "Public Safety / Less-Lethal Technology",
        # ── everything below: not public, left blank (no fabrication, no leak) ──
        "fy_guidance": "",
        "q2_consensus_rev": None,
        "peer_median_ev_rev": None,
        "guidance_vs_street_note": "",
        "bar_risk_level": "",
        "bar_risk_note": "",
        "ir_contact": {},
        "executives": {},
        "qa_only_participants": "",
        "tone_band_m": None,
        "fls_items": [],
        "guidance_policy": {},
        "analysts": [],
        "peers": [],                      # peers live in peer_universe (client_id="wrap")
        "earnings": {},
        "financials": {},
        "guidance": {},
    },
}

DEFAULT_CLIENT_ID = "usio"


# ─────────────────────────────────────────────────────────────────────────
# Role-based access (RBAC) — roles & responsibilities
# ─────────────────────────────────────────────────────────────────────────
# WHO fills each role comes from the active client's profile (ir_contact +
# executives above) — never hardcoded person names in app logic. WHAT each
# role may do (which pages it sees/edits, whether it can change Settings or
# send outbound email) is a PLATFORM concern, identical across clients, so it
# lives here once instead of being copied into every client record.
#
# Role keys line up with the profile roster: "IR" is filled by ir_contact;
# every other key ("CEO", "CFO", "CRO", "Legal", ...) is filled by the
# matching key in the client's "executives" dict. A client whose executives
# dict omits a role simply doesn't offer that role in the selector — nothing
# else changes. Access level per page is one of: "full", "read", "none".
PAGES = ["Today", "Calendar", "Markets", "Investors",
         "Outreach", "Earnings", "Reports", "Settings"]

ROLE_PERMISSIONS = {
    "IR": {
        "label": "IR Director",
        # Power user / platform admin — full run of the app.
        "pages": {p: "full" for p in PAGES},
        "can_change_settings": True,
        "can_send_email": True,
    },
    "CFO": {
        "label": "CFO",
        # Full access — the CFO is backing up / taking over from the IR role
        # (IR departure, noted 2026-07-13), so the CFO now has the same run of
        # the app the IR Director does, including Settings and outbound send.
        "pages": {p: "full" for p in PAGES},
        "can_change_settings": True,
        "can_send_email": True,
    },
    "CEO": {
        "label": "CEO",
        "pages": {"Today": "full", "Earnings": "full", "Calendar": "full",
                  "Markets": "read", "Reports": "read", "Investors": "none",
                  "Outreach": "none", "Settings": "none"},
        "can_change_settings": False,
        "can_send_email": False,
    },
    "CRO": {
        "label": "CRO",
        # Owns investor demand/outreach + carries a script persona. Can DRAFT
        # outreach but NOT send — send is IR-only per client policy.
        "pages": {"Investors": "full", "Outreach": "full", "Calendar": "full",
                  "Markets": "full", "Earnings": "full", "Reports": "read",
                  "Today": "read", "Settings": "none"},
        "can_change_settings": False,
        "can_send_email": False,
    },
    "Legal": {
        "label": "Legal",
        # Disclosure/sign-off focus: FLS checklist in Earnings + the Reg FD log.
        "pages": {"Earnings": "full", "Reports": "full", "Today": "read",
                  "Calendar": "read", "Investors": "none", "Outreach": "none",
                  "Markets": "none", "Settings": "none"},
        "can_change_settings": False,
        "can_send_email": False,
    },
}

# The default role a session lands in before any explicit selection — the IR
# Director, who has full access (matches the original demo's implicit "you are
# Paul Manley" assumption, now expressed as a role rather than a person name).
DEFAULT_ROLE_KEY = "IR"


def _role_entry(role_key, name, title):
    """Combine the platform permission set for role_key with WHO fills it
    (name/title) from the active client's profile."""
    perms = ROLE_PERMISSIONS[role_key]
    return {
        "role_key": role_key,
        "label": perms["label"],
        "name": name,
        "title": title or perms["label"],
        # Human-facing selector string, e.g. "Paul Manley — IR Director".
        # Person name is data pulled from the profile, not a literal.
        "display": f"{name} — {perms['label']}",
        "permissions": perms,
    }


def role_roster(client_id=None):
    """Ordered list of roles the active client actually staffs, each merging
    platform permissions with the profile's person for that role. IR first
    (from ir_contact), then executives in registry order. Roles with no
    permission definition, or with no person assigned, are skipped."""
    client = get_client(client_id)
    roster = []
    ir = client.get("ir_contact", {})
    if ir.get("name") and "IR" in ROLE_PERMISSIONS:
        roster.append(_role_entry("IR", ir.get("name"), ir.get("title")))
    for role_key, info in client.get("executives", {}).items():
        if role_key in ROLE_PERMISSIONS and info.get("name"):
            roster.append(_role_entry(role_key, info.get("name"), info.get("title")))
    return roster


def role_permissions(role_key):
    """Permission set for a role key, falling back to the default role rather
    than crashing on an unknown key."""
    return ROLE_PERMISSIONS.get(role_key, ROLE_PERMISSIONS[DEFAULT_ROLE_KEY])


def role_access_level(role_key, page):
    """'full' | 'read' | 'none' for a given role/page pair."""
    return role_permissions(role_key).get("pages", {}).get(page, "none")


def role_can_view(role_key, page):
    """True if the role may open the page at all (full or read)."""
    return role_access_level(role_key, page) in ("full", "read")


def role_can_edit(role_key, page):
    """True only for full (read/write) access to the page."""
    return role_access_level(role_key, page) == "full"


def role_has_full_access(role_key):
    """True if the role has IR-equivalent full run of the app — every page at
    'full' plus both sensitive-action flags. Used to decide whether a role
    gets the complete app or a restricted curated landing: a role elevated to
    back up / cover the IR Director (e.g. the CFO after an IR departure) has
    full access and should see the full app, not an exec briefing view."""
    perms = role_permissions(role_key)
    pages_full = all(perms.get("pages", {}).get(p) == "full" for p in PAGES)
    return pages_full and perms.get("can_change_settings", False) and perms.get("can_send_email", False)


def role_can_send_email(role_key):
    return role_permissions(role_key).get("can_send_email", False)


def role_can_change_settings(role_key):
    return role_permissions(role_key).get("can_change_settings", False)


def role_key_from_display(display, client_id=None):
    """Map a selector string (e.g. 'Paul Manley — IR Director') back to its
    role_key. Falls back to DEFAULT_ROLE_KEY if nothing matches."""
    for entry in role_roster(client_id):
        if entry["display"] == display:
            return entry["role_key"]
    return DEFAULT_ROLE_KEY


# ─────────────────────────────────────────────────────────────────────────
# Active-client helpers
# ─────────────────────────────────────────────────────────────────────────
# The active tenant for the current execution context. A ContextVar — not a
# module global, not Streamlit session_state — because get_active_client_id() is
# called on essentially every CT()/CE()/CA()/C() lookup (hundreds of times per
# render) and from deep inside core modules that have no UI context. Requirements
# that ContextVar satisfies and the alternatives did not:
#   * FAST on the hot path: .get() is a C-level read, no I/O, no framework-context
#     probe. The old Streamlit path touched session_state on every call and, under
#     NiceGUI (no ScriptRunContext), printed a warning per call — hundreds of
#     synchronous stdout writes per render stalled the event loop and dropped the
#     websocket heartbeat ("Lost connection").
#   * ASYNC-SAFE: each request/task gets its own value, so two browser sessions
#     viewing different tenants never bleed into each other.
#   * SAFE OUTSIDE A UI CONTEXT: a script, a batch job, or a worker thread handed
#     no explicit client_id reads the default cleanly instead of raising.
# The NiceGUI app assigns it per render from persistent per-browser storage
# (app.storage.user) via app_nicegui._bind_active_client(). Nothing here imports
# NiceGUI, so importing this module elsewhere just yields DEFAULT_CLIENT_ID until
# someone calls set_active_client_id().
_active_client_ctx = contextvars.ContextVar("active_client_id", default=None)


def get_active_client_id():
    """The tenant in view for the current context, or DEFAULT_CLIENT_ID.

    Never raises and never blocks — it is on the hottest path in the app."""
    return _active_client_ctx.get() or DEFAULT_CLIENT_ID


def set_active_client_id(client_id):
    """Make client_id the active tenant for the current context.

    Validated against the registry so a typo fails loudly here rather than
    silently serving the wrong tenant's data. Returns the id set."""
    if client_id not in CLIENT_REGISTRY:
        raise ValueError(f"Unknown client_id '{client_id}'. Known clients: {list(CLIENT_REGISTRY)}")
    _active_client_ctx.set(client_id)
    return client_id


def get_client(client_id=None):
    """Full config record for the given client, or the active one."""
    cid = client_id or get_active_client_id()
    if cid not in CLIENT_REGISTRY:
        raise ValueError(f"Unknown client_id '{cid}'. Known clients: {list(CLIENT_REGISTRY)}")
    return CLIENT_REGISTRY[cid]


# ─────────────────────────────────────────────────────────────────────────
# Backward-compatible accessors
# These match the exact function names/signatures app.py already calls
# throughout its ~12,750 lines (C(), CI(), CA(), etc.), so pages/components
# do not need to change in this step — only WHERE these functions are
# defined changes. They now read from the active client instead of one
# hardcoded dict.
# ─────────────────────────────────────────────────────────────────────────
def C():
    return get_client()


def CI():
    return get_client().get("ir_contact", {})


def CA():
    return get_client().get("analysts", [])


def CE():
    return get_client().get("earnings", {})


def CF():
    return get_client().get("financials", {})


def CG():
    """Management guidance snapshot (new accessor — the old USIO_GUIDANCE
    global is folded into the client record as its 'guidance' key)."""
    return get_client().get("guidance", {})


def CGP():
    """Guidance & Outlook Decision Engine policy inputs (earnings_page.py's
    Script Generation tab) — seasonality weights, prior-FY quarterly
    revenue, growth-range assumption, per-action range deltas, known H2
    catalysts, closing line, operator handoff. Empty dict if the active
    client hasn't configured one (see CLIENT_REGISTRY's "usio" record and
    this module's docstring gap-inventory item 1)."""
    return get_client().get("guidance_policy", {})


def CT(key, default=""):
    return get_client().get(key, default)


def _read_csv_with_fallback_encoding(path):
    """Small local CSV reader with the same encoding-fallback order as
    app.py's robust_read_csv (utf-8 -> utf-8-sig -> cp1252 -> latin1).
    Deliberately NOT importing robust_read_csv from app.py here — app.py
    will import THIS module, so importing back from app.py would create a
    circular import. If this needs the full delimiter-sniffing behavior
    robust_read_csv has, that function should move to a shared
    core/io_utils.py module in a later pass (it currently has 40+ call
    sites throughout app.py's page code, which is out of scope for this
    config-extraction step)."""
    last_err = None
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin1"):
        try:
            return pd.read_csv(path, encoding=enc)
        except UnicodeDecodeError as e:
            last_err = e
            continue
    raise last_err


def CP():
    """Peer comps used for valuation talking points (outreach drafts, etc).
    Reads the active client's peer universe from the SQLite data layer
    (core.db, key "peer_universe.csv" — same key investors_page.py's Peer
    Universe manager reads/writes, so a peer added via Peer Cross-Targeting
    is immediately available here too), falling back to the static default
    peer list in CLIENT_REGISTRY if nothing has been saved yet. core.db
    transparently imports a pre-existing peer_universe.csv file the first
    time this is called, so peers added before the SQLite migration aren't
    lost."""
    from core import db
    client = get_client()
    peers = db.load_json("peer_universe.csv", default=None)
    if peers:
        # The peer store is shared with the Fit-Score "Peer Universe" manager,
        # which tags peers with its own vocab (core / close / large). Normalize to
        # the valuation vocab: "large" (mega-cap) -> "reference" (out of the
        # median); everything else -> "primary". A peer with no tier defaults to
        # primary so it still counts. segment falls back to the Fit-Score sector.
        def _val_tier(t):
            return "reference" if t in ("large", "reference") else "primary"
        return [{"ticker": p["ticker"], "name": p["name"],
                  "ev_rev": float(p["ev_rev"]) if p.get("ev_rev") not in (None, "") else None,
                  "tier": _val_tier(p.get("tier")),
                  "segment": p.get("segment") or p.get("sector") or "",
                  "closest_analog": bool(p.get("closest_analog"))}
                 for p in peers]
    return client.get("peers", [])


def client_data_path(filename, client_id=None):
    """Path for per-client data files. The original demo hardcoded a single
    shared 'models/' folder (fine for one client). Now scoped under
    data/<client_id>/ so a future client #2 never reads or writes client
    #1's files. Falls back to the legacy shared 'models/' path if a
    client-scoped copy doesn't exist yet, so existing USIO data isn't
    silently orphaned by this change."""
    cid = client_id or get_active_client_id()
    new_dir = os.path.join("data", cid)
    os.makedirs(new_dir, exist_ok=True)
    new_path = os.path.join(new_dir, filename)
    legacy_path = os.path.join("models", filename)
    if not os.path.exists(new_path) and os.path.exists(legacy_path):
        return legacy_path
    return new_path


def team_labels():
    """'<Name> (<ROLE>)' labels for everyone on the active client's team,
    built from the profile (ir_contact + executives) instead of a hardcoded
    ['Louis Hoch (CEO)', 'Paul Manley (IR)', ...] list. Used by participant
    pickers — Reg FD meeting attendees, the earnings "Submitted by" selector,
    etc. — so those rosters are correct for whichever client is active. IR
    first, then executives in registry order. A role slot with no assigned
    name is skipped."""
    client = get_client()
    labels = []
    ir = client.get("ir_contact", {})
    if ir.get("name"):
        labels.append(f"{ir['name']} (IR)")
    for role_key, info in client.get("executives", {}).items():
        name = info.get("name")
        if name:
            labels.append(f"{name} ({role_key})")
    return labels


def team_email_lookup():
    """Client team members who show up in NDR trip rosters etc., mapped to
    their known email. Derived from the client's executives + ir_contact
    instead of being a separately hardcoded dict (the original demo had
    TEAM_EMAIL_LOOKUP as a second, independent copy of the same 3 names —
    a real duplication risk if the two ever drifted apart)."""
    client = get_client()
    lookup = {}
    ir = client.get("ir_contact", {})
    if ir.get("name") and ir.get("email"):
        lookup[ir["name"]] = ir["email"]
    for _role, info in client.get("executives", {}).items():
        if info.get("name") and info.get("email"):
            lookup[info["name"]] = info["email"]
    return lookup
