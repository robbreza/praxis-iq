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
        "peers": [
            {"ticker": "GDOT", "name": "Green Dot", "ev_rev": 1.2},
            {"ticker": "PRTH", "name": "Priority Technology", "ev_rev": 1.8},
            {"ticker": "FOUR", "name": "Shift4 Payments", "ev_rev": 4.2},
            {"ticker": "RPAY", "name": "Repay Holdings", "ev_rev": 2.8},
        ],
        "earnings": {"current_quarter": "Q2 2026", "earnings_date": "2026-08-12",
            "call_time": "4:30 PM ET", "dial_in": "+1-844-883-3890",
            "quiet_start": "2026-07-20", "quiet_end": "2026-08-12"},
        "financials": {"last_quarter": "Q1 2026", "last_rev": 25.47, "last_rev_yoy": 16.0,
            "last_eps": 0.00, "last_gm": 20.2, "last_ebitda": 0.8, "cash_m": 7.7},
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
    # Add client #2 here, same shape as "usio" above.
}

DEFAULT_CLIENT_ID = "usio"


# ─────────────────────────────────────────────────────────────────────────
# Active-client helpers
# ─────────────────────────────────────────────────────────────────────────
def get_active_client_id():
    """The client_id currently in view for this browser session. Falls back
    to DEFAULT_CLIENT_ID if nothing has been selected yet (no switcher UI
    exists yet), or if Streamlit isn't running (e.g. a script importing this
    module directly, outside the app — including every NiceGUI page, which
    is the primary app now).

    This function is called on essentially every CT()/CE()/CA()/C() lookup,
    i.e. constantly, on every page render. Under the NiceGUI app there is
    never a real Streamlit ScriptRunContext, so a plain `st.session_state`
    access used to print Streamlit's "missing ScriptRunContext! This warning
    can be ignored when running in bare mode" line on *every single call* —
    harmless individually, but at that call volume (hundreds per page
    render on a busy page like Investors) the synchronous stdout writes were
    slow enough to stall NiceGUI's single-threaded event loop and drop the
    browser's websocket heartbeat, which is what showed up as "Lost
    connection" in the UI. get_script_run_ctx(suppress_warning=True) checks
    for a real context first, silently, so the common (no-context) path
    never touches session_state or prints anything."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx
        if get_script_run_ctx(suppress_warning=True) is None:
            return DEFAULT_CLIENT_ID
        import streamlit as st
        return st.session_state.get("active_client_id", DEFAULT_CLIENT_ID)
    except Exception:
        return DEFAULT_CLIENT_ID


def set_active_client_id(client_id):
    """Switch the active client for this session. Will be wired up to a
    tenant-switcher dropdown in a later step."""
    if client_id not in CLIENT_REGISTRY:
        raise ValueError(f"Unknown client_id '{client_id}'. Known clients: {list(CLIENT_REGISTRY)}")
    import streamlit as st
    st.session_state["active_client_id"] = client_id


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
        return [{"ticker": p["ticker"], "name": p["name"],
                  "ev_rev": float(p["ev_rev"]) if p.get("ev_rev") not in (None, "") else None}
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
