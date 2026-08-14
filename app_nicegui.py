"""
app_nicegui.py — new NiceGUI entrypoint, replacing app.py's Streamlit UI
one page at a time.

Why this file exists alongside app.py: we're migrating away from Streamlit
because its internal CSS/component structure fought every attempt at a
specific branded look (see the override hacks in config/theme.py). NiceGUI
still lets us write plain Python function calls to build the UI (same
mental model as Streamlit — no separate frontend language, no React state
classes to learn), but gives direct styling control instead of CSS
overrides targeting someone else's internal markup.

Run this with:  python app_nicegui.py
(runs on port 8502 by default, so it can sit alongside the still-running
Streamlit app.py on its usual port 8501 during the transition.)

Pages get ported one at a time into page_modules_nicegui/. Anything not
yet ported shows a "not yet available here" placeholder and can still be
reached in the original app.py.
"""

import os
import base64
from fastapi import Request

# Load .env into os.environ BEFORE anything reads it eagerly. ui.run() reads
# IRCONNECT_STORAGE_SECRET straight from os.environ at module-load time (bottom of
# this file), which is earlier than the first lazy load_environment() call that
# DATABASE_URL relies on — so without this the storage secret would silently fall
# back to the dev default even when set in .env.
from core.security import load_environment
load_environment()

from nicegui import app, ui

from config.client_config import (
    CT, get_client, role_roster, role_access_level, role_can_view,
    DEFAULT_ROLE_KEY,
    CLIENT_REGISTRY, DEFAULT_CLIENT_ID, get_active_client_id, set_active_client_id,
)
from config.theme_tokens import ACTIVE as COLORS


def _current_user():
    """The authenticated user for this session (from the signed session cookie), or None."""
    from core import auth
    try:
        uid = app.storage.user.get("user_id")
    except Exception:
        return None
    # LOCAL DEV ONLY: when DEV_AUTOLOGIN is set (never in production), auto-establish a session as that
    # user so the app can be viewed on localhost without typing a password. Env-gated: inert unless the
    # operator sets the flag on their own machine.
    if not uid:
        import os
        _dev = os.environ.get("DEV_AUTOLOGIN")
        if _dev:
            try:
                app.storage.user["user_id"] = _dev
                app.storage.user.setdefault("active_client_id", os.environ.get("DEV_TENANT", "usio"))
                uid = _dev
            except Exception:
                pass
    return auth.get_user(uid) if uid else None


def _bind_active_client():
    """Assign this render's tenant AND enforce the access boundary, per render.

    THE SECURITY-CRITICAL CLAMP. The tenant a session may view is derived from the
    AUTHENTICATED user (auth.allowed_clients) — never trusted from the cookie. A client_user
    is pinned to its home tenant; a forged active_client_id pointing at another client is
    rejected here, server-side. Staff get their remembered choice within the full set.

    Also marks the session read-only in core.db for a client_user, so writes are refused at
    the DATA layer regardless of UI gating. Re-asserted every render because NiceGUI event
    handlers can run in fresh async contexts."""
    from core import auth, db
    user = _current_user()
    allowed = auth.allowed_clients(user)
    db.set_session_readonly(auth.is_readonly_user(user))   # CLIENT_RW is tenant-pinned but writable
    try:
        requested = app.storage.user.get("active_client_id")
    except Exception:
        requested = None
    if allowed:
        cid = requested if requested in allowed else allowed[0]
    else:
        cid = DEFAULT_CLIENT_ID  # unauthenticated; the page guard redirects to /login anyway
    set_active_client_id(cid)
    return cid


def _install_event_tenant_hook():
    """Re-assert the tenant binding for every USER-EVENT handler.

    _bind_active_client() runs per RENDER, but a later on_click/on_change
    callback runs in a fresh async context where those bindings are gone: the
    active-tenant ContextVar (config.client_config) falls back to
    DEFAULT_CLIENT_ID and the read-only flag (core.db) resets to writable. The
    effect: a write callback in a NON-default tenant acted on the wrong client
    (e.g. an emailed model for a non-usio tenant never matched its analysts),
    and a read-only client_user could in principle write via a callback.

    We wrap nicegui.element.Element._handle_event — the entry point for
    BROWSER-ORIGINATED events ONLY. Reactive/observable propagation does NOT go
    through it (it dispatches via events.handle_event directly), so this stays
    off the CT()/CE() hot path and fires just once per user gesture. The
    original sets storage.request_contextvar first so app.storage.user /
    _current_user() resolve; we set it too (idempotent) and re-run
    _bind_active_client() before delegating to the original dispatch, so the
    tenant + read-only clamp are correct for whatever the handler writes.

    NOTE: depends on NiceGUI internals (Element._handle_event, its listener/
    request_contextvar shape). Re-verify on a NiceGUI upgrade — see the
    callback-tenant-context memory note. Wrapped in try/except so a shape change
    degrades to the old (default-tenant) behavior rather than crashing."""
    from nicegui.element import Element
    from nicegui import storage as _storage
    orig = Element._handle_event
    if getattr(orig, "_tenant_rebound", False):
        return

    def _handle_event(self, msg):
        try:
            listener = self._event_listeners.get(msg.get("listener_id"))
            if listener is not None:
                _storage.request_contextvar.set(listener.request)
                _bind_active_client()
        except Exception:
            pass
        return orig(self, msg)

    _handle_event._tenant_rebound = True
    Element._handle_event = _handle_event


_install_event_tenant_hook()

# Nav icons are Material Symbols names (rendered via ui.icon), not emoji — a
# consistent monochrome line set reads more professional and inherits the
# nav's text color (graphite inactive, navy active) instead of fixed emoji.
# The rail is the map: top-level SECTIONS only (each answers "where am I"). A page's own sub-views
# live on the page as tabs (answering "which view"), never mirrored in the rail — so there is one
# menu, not two. "Investor Targeting" was one overloaded section with 9 tabs across three different
# jobs; it's now three focused sections (Ownership / Targeting / Roadshow), each a page with ~3 tabs.
NAV_GROUPS = [
    ("OVERVIEW", [
        ("Today",     "space_dashboard", "Today", "Morning brief · Alerts · Actions due"),
        ("Inbox",     "inbox", "IR Inbox", "The IRconnect inbox — parsed models, research notes and requests, filed automatically"),
        ("Calendar",  "calendar_month", "Calendar", "Earnings · conferences · NDR trips — every upcoming event, one page"),
    ]),
    ("INVESTOR TARGETING", [
        ("Targeting", "my_location", "Targeting\nwho should own you", "Target database · Peer prospects · Import"),
        ("Ownership", "donut_large", "Ownership\nwho owns you", "Buy-side · NOBO · Website"),
        ("Roadshow",  "route", "Outbound\nreach & track", "Meeting Hub · NDR · CRM"),
    ]),
    ("MARKET INTELLIGENCE", [
        ("Markets",   "trending_up", "Consensus & Estimates\nwhere the Street stands", "Consensus · PT tracker · Peer benchmarking"),
        ("Lighthouse", "lightbulb", "Lighthouse\nWhy is the stock moving?", "Expected vs actual · Residual · Events · Technicals · CEO read"),
    ]),
    ("EARNINGS", [
        # Outreach (Mail Gateway) hidden from the sidebar for the demo — the IMAP/SMTP mail workflow
        # isn't ported to this interface yet; its render mapping stays in PORTED below.
        ("Earnings",  "description", "Earnings Cycle\nScript Generation", "Script generation · Prior qtr review · Consensus tracker"),
    ]),
    ("REPORTS & SETTINGS", [
        ("Reports",   "assessment", "Reports", "Board report · Investor deck · Reg FD"),
        ("Settings",  "settings", "Settings", "Platform configuration · Data sources"),
    ]),
    # The phone / on-the-road view — demoted to the bottom and renamed "Mobile" (it is NOT the
    # desktop home; Today is the dashboard). The section KEY stays "Home", so routing, the mobile
    # landing (_is_mobile_ua → "Home"), and the bottom tab bar are all unaffected.
    ("ON THE ROAD", [
        ("Home",      "smartphone", "Mobile", "The phone / on-the-road view — pulse, schedule, meeting prep & notes"),
    ]),
]

# Flat list of section names, derived from NAV_GROUPS — used anywhere the
# grouping doesn't matter (e.g. looking up which module renders a section).
NAV_SECTIONS = [page for _group, items in NAV_GROUPS for page, *_ in items]

# Mobile bottom tab bar — the thumb-reachable on-the-road surfaces (section, icon, short label, deep-link
# sub-tab or None). Shown only on phones (CSS); the heavy authoring tools stay behind the header ☰ drawer.
# NDR deep-links into Investor Targeting's NDR Planner — the one on-the-road piece of that otherwise-heavy
# page worth a one-tap.
_MOBILE_TABS = [
    ("Home", "home", "Home", None),
    ("Lighthouse", "lightbulb", "Lighthouse", None),
    ("Calendar", "calendar_month", "Calendar", None),
    ("Roadshow", "route", "NDR", "NDR"),
    ("Markets", "trending_up", "Markets", None),
]

# Sub-items surfaced under each content-heavy page in the sidebar — the page's
# own primary (top-level) tabs, so every real destination is visible in the nav
# and one click deep instead of hidden until you open the page. Labels MUST match
# the ui.tab(...) labels in each page module exactly: the sidebar passes the
# label as the deep-link target and the page opens its tab strip on it (see
# nav.consume_target_tab). Pages not listed here (Today, Calendar, Outreach) are
# single-view and render as plain nav buttons with no expander.
NAV_SUBITEMS = {
    "Markets":   ["IR Risk Dashboard", "Consensus / Guidance", "PT Drift Tracker"],
    # Outbound (page key "Roadshow") surfaces its three destinations as sidebar pointers — the labels
    # match the page's ui.tab identities exactly so each one deep-links straight to its tab.
    "Roadshow":  ["Meeting Hub", "NDR", "CRM"],
    # Ownership / Targeting are DELIBERATELY absent here — they render as plain rail sections (no
    # sub-item expander), so their tabs live only on the page (one menu, not two). Deep-links
    # (go_to(section, tab)) still work — the target tab is consumed by the page.
    "Earnings":  ["Prior Qtr Review", "Script Generation", "Prep Brief", "Consensus Tracker",
                  "Call Transcripts", "Narrative Momentum", "Morning After"],
    "Reports":   ["Board IR Reports", "90-Day IR Plan",
                  "Peer & Market Analysis", "Reg FD & Compliance",
                  "Automation Tracker"],
    # SEC Intelligence lives here, not under Investors: it's a data-audit / source view
    # (13D/13G/13F filings + the tracked-universe refresh), a sibling of Data Sources — not a
    # targeting workflow. Moved 2026-08-08.
    "Settings":  ["Platform Config", "Data Sources", "SEC Intelligence", "About"],
}

# Optional intra-page grouping of the sidebar sub-items, so a dense page reads as a few clear
# intents instead of one long list (the ease-of-use audit's Investor-Targeting finding: 10 near-
# flat siblings → 3 buckets). Each group is (label, one-line intent, [sub-item names]). A page NOT
# listed here renders its NAV_SUBITEMS as a flat list, unchanged. The concatenation of a page's
# groups here MUST equal its NAV_SUBITEMS list, in order (asserted by tests/test_nav_subitems.py).
# (Investor Targeting's old three intent-groups are now their own top-level rail sections —
# Ownership / Targeting / Roadshow — so no intra-page sub-grouping is needed here.)
NAV_SUBGROUPS = {
    # Earnings Cycle's 7 tabs, clustered by where they sit in the earnings timeline so the
    # densest item in the menu reads as three clear phases. The concatenation (in order) MUST
    # equal NAV_SUBITEMS["Earnings"] and the page's tab order — see tests/test_nav_subitems.py.
    "Earnings": [
        ("Prep", "before the call", ["Prior Qtr Review", "Script Generation", "Prep Brief", "Consensus Tracker"]),
        ("The Call", "the transcript", ["Call Transcripts"]),
        ("After", "the post-mortem", ["Narrative Momentum", "Morning After"]),
    ],
}

# Plain-language gloss for the JARGON sub-items (the audit's P3 — the Lighthouse "Why is the stock
# moving?" pattern, applied where a label is an acronym or insider term). Self-explanatory items
# (Meeting Hub, Target Database, Board IR Reports…) are deliberately left un-glossed so the rail
# stays scannable.
NAV_SUBITEM_GLOSS = {
    "IR Risk Dashboard":   "what could move the stock",
    "PT Drift Tracker":    "how price targets have moved",
    "SEC Intelligence":    "13D / 13G / 13F filings",
    "NOBO Ownership":      "who your retail holders are",
    "NDR":                 "non-deal roadshow scheduling",
    "CRM":                 "the relationship book · Account 360",
    "Narrative Momentum":  "is the story landing?",
    "Prep Brief":          "one-page earnings prep",
    "Morning After":       "post-call critique",
    "Reg FD & Compliance": "fair-disclosure logging",
    "Automation Tracker":  "what the platform ran for you",
}

# Which sections have been ported to NiceGUI so far. Update this as each
# page_modules_nicegui/<name>.py lands (see task list — ported incrementally,
# smallest/lowest-risk pages first).
PORTED = {
    "Home": "page_modules_nicegui.mobile_page",
    "Today": "page_modules_nicegui.today_page",
    "Inbox": "page_modules_nicegui.inbox_page",
    # Investor Targeting, split into three focused sections — all rendered by the same module via
    # render_ownership_page / render_targeting_page / render_roadshow_page (each shows ~3 tabs).
    "Ownership": "page_modules_nicegui.investors_page",
    "Targeting": "page_modules_nicegui.investors_page",
    "Roadshow": "page_modules_nicegui.investors_page",
    "Earnings": "page_modules_nicegui.earnings_page",
    "Markets": "page_modules_nicegui.markets_page",
    "Outreach": "page_modules_nicegui.outreach",
    "Calendar": "page_modules_nicegui.calendar_page",
    "Reports": "page_modules_nicegui.reports_page",
    "Settings": "page_modules_nicegui.settings_page",
    "Lighthouse": "page_modules_nicegui.lighthouse_page",
}


def apply_theme():
    """Global look — direct equivalent of config/theme.py's CSS_TEMPLATE,
    but using NiceGUI's own styling hooks instead of CSS overrides aimed at
    Streamlit's internal element names."""
    ui.colors(
        primary=COLORS["accent"],
        secondary=COLORS["accent_strong"],
        accent=COLORS["accent_light"],
        positive=COLORS["success"],
        negative=COLORS["danger"],
        warning=COLORS["warning"],
        dark=COLORS["canvas_bg"],
    )
    ui.add_css(f"""
        body {{
            background: {COLORS["canvas_bg"]};
            color: {COLORS["text_body"]};
            font-family: 'Inter', 'SF Pro Display', -apple-system, sans-serif;
        }}
        /* Tighter cards (2026-07-21). The IR dashboards are detail-dense; with the
           normalised (smaller) type, NiceGUI's default 1rem card padding + 1rem
           internal gap left the text swimming in whitespace and read as "off" —
           and in this business a buried detail is a missed detail. Reclaim it by
           dialing the two card variables down globally. Cards with EXPLICIT padding
           (.ir-card at 20/24) keep it; only the default gap tightens there. Section
           rhythm is unaffected (that comes from .section-head margins). */
        :root {{
            --nicegui-default-padding: 0.625rem;  /* 16px -> 10px */
            --nicegui-default-gap: 0.25rem;       /* 16px ->  4px */
        }}
        /* Buttons in sentence case, not Quasar's default SHOUTING uppercase.
           ALL-CAPS button labels (RESOLVE / MUTE / DETAILS) read as dated and
           shouty — caps is reserved as a deliberate accent (small eyebrows),
           not applied wholesale to every control. */
        .q-btn {{ text-transform: none; }}
        .ir-card {{
            background: {COLORS["surface_bg"]};
            border: 1px solid {COLORS["border"]};
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }}
        .ir-card-accent {{
            background: {COLORS["surface_bg"]};
            border: 1px solid {COLORS["accent_strong"]};
            border-left: 3px solid {COLORS["accent"]};
            border-radius: 12px;
            padding: 20px 24px;
            margin-bottom: 16px;
        }}
        .section-eyebrow {{
            font-size:var(--fs-xs);
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: .10em;
            font-weight: 500;
            margin-bottom: 4px;
        }}
        .section-title {{
            font-size:var(--fs-2xl);
            font-weight: 700;
            color: {COLORS["text_heading"]};
            margin-bottom: 16px;
        }}
        /* Real section heading — sentence case, sized/weighted to carry
           hierarchy on its own, replacing 11px uppercase eyebrows that were
           doing heading duty (see the hierarchy pass, 2026-07-13). */
        .section-head {{
            font-size:var(--fs-lg);
            font-weight: 600;
            color: {COLORS["text_heading"]};
            letter-spacing: -0.01em;
            margin: 18px 0 8px;
        }}
        .nav-section {{
            font-size:var(--fs-md);
            color: {COLORS["text_secondary"]};
            text-transform: uppercase;
            letter-spacing: .07em;
            padding: 16px 16px 6px;
            font-weight: 700;
        }}
        .nav-btn {{
            width: 100%;
            justify-content: flex-start !important;
            color: {COLORS["text_body"]} !important;
            background: transparent !important;
            text-transform: none !important;
            line-height: 1.25 !important;
        }}
        .nav-btn .q-btn__content {{
            justify-content: flex-start !important;
            align-items: flex-start !important;
        }}
        .nav-btn-line1 {{
            font-size:var(--fs-lg);
            font-weight: 600;
            text-align: left !important;
            width: 100%;
            /* Force graphite over Quasar's default primary (purple) label
               color — inactive items read as high-contrast body text, and
               the accent is reserved for the active item below, so the
               selected page stands out instead of every item being purple. */
            color: {COLORS["text_body"]} !important;
        }}
        .nav-btn-line2 {{
            font-size:var(--fs-base);
            font-weight: 400;
            text-align: left !important;
            width: 100%;
            color: {COLORS["text_secondary"]};
        }}
        .nav-btn.active {{
            background: {COLORS["surface_bg"]} !important;
            border-left: 3px solid {COLORS["accent"]} !important;
        }}
        .nav-btn.active .nav-btn-line1 {{
            color: {COLORS["accent_strong"]} !important;
            font-weight: 700;
        }}
        .nav-btn.active .nav-btn-line2 {{
            color: {COLORS["text_secondary"]};
        }}
        .nav-icon {{
            font-size:var(--fs-2xl) !important;
            color: {COLORS["text_secondary"]} !important;
        }}
        .nav-btn.active .nav-icon {{
            color: {COLORS["accent_strong"]} !important;
        }}
        .nav-chevron {{
            font-size:var(--fs-xl) !important;
            color: {COLORS["text_muted"]} !important;
            margin-left: auto;
            align-self: center;
        }}
        .nav-btn.active .nav-chevron {{
            color: {COLORS["accent_strong"]} !important;
        }}
        /* Sub-item rail — the page's own tabs, surfaced under an expanded
           section so every destination is one click deep. */
        .nav-subwrap {{
            margin: 2px 0 8px 34px;
            border-left: 1px solid {COLORS["border"]};
            padding-left: 4px;
        }}
        .nav-sub {{
            width: 100%;
            justify-content: flex-start !important;
            text-transform: none !important;
            color: {COLORS["text_secondary"]} !important;
            background: transparent !important;
            font-size:var(--fs-md) !important;
            font-weight: 500 !important;
            min-height: 32px !important;
        }}
        .nav-sub .q-btn__content {{
            justify-content: flex-start !important;
        }}
        .nav-sub.active {{
            color: {COLORS["accent_strong"]} !important;
            font-weight: 700 !important;
        }}
        /* Sub-item label + optional plain-language gloss (jargon items only). */
        .nav-sub {{ min-height: 30px !important; padding-top: 3px !important; padding-bottom: 3px !important; }}
        .nav-sub-label {{
            font-size:var(--fs-md);
            font-weight: 500;
            line-height: 1.2;
            color: {COLORS["text_secondary"]};
        }}
        .nav-sub.active .nav-sub-label {{
            color: {COLORS["accent_strong"]};
            font-weight: 700;
        }}
        .nav-sub-gloss {{
            font-size:var(--fs-2xs);
            font-weight: 400;
            line-height: 1.15;
            color: {COLORS["text_muted"]};
            margin-top: 1px;
        }}
        /* Intent header above each sub-item cluster (Ownership / Targeting / Engagement). */
        .nav-subgroup {{
            font-size:var(--fs-2xs);
            letter-spacing: .08em;
            text-transform: uppercase;
            color: {COLORS["text_secondary"]};
            font-weight: 700;
            padding: 10px 8px 3px;
            display: flex;
            align-items: baseline;
            gap: 7px;
            line-height: 1.2;
        }}
        .nav-subgroup:first-child {{ padding-top: 4px; }}
        .nav-subgroup span {{
            text-transform: none;
            letter-spacing: 0;
            font-weight: 400;
            font-size:var(--fs-xs);
            color: {COLORS["text_muted"]};
        }}
        /* ─────────────────────────────────────────────────────────────
           SHARED UI STANDARD (2026-07-21 consistency pass)
           A semantic type scale, card variants, and status-colour utilities
           so pages stop hand-rolling inline font-size / color / radius (the
           audit found 16 font sizes, 10 card radii, ~307 hardcoded status
           hexes). Apply with .classes("t-meta"), .classes("ir-tile c-pos").
           Section vertical rhythm comes ONLY from .section-head — do not add
           ad-hoc margin-top overrides on it.
           ───────────────────────────────────────────────────────────── */
        .t-title   {{ font-size:var(--fs-2xl); font-weight:700; color:{COLORS["text_heading"]}; letter-spacing:-.01em; }}
        .t-head    {{ font-size:var(--fs-lg); font-weight:600; color:{COLORS["text_heading"]}; letter-spacing:-.01em; }}
        .t-subhead {{ font-size:var(--fs-base); font-weight:700; color:{COLORS["text_body"]}; }}
        .t-body    {{ font-size:var(--fs-base); font-weight:400; color:{COLORS["text_body"]}; line-height:1.45; }}
        .t-sec     {{ font-size:var(--fs-sm); font-weight:400; color:{COLORS["text_secondary"]}; line-height:1.45; }}
        .t-meta    {{ font-size:var(--fs-sm); font-weight:400; color:{COLORS["text_muted"]}; }}
        .t-fine    {{ font-size:var(--fs-2xs); font-weight:400; color:{COLORS["text_muted"]}; }}
        .t-eyebrow {{ font-size:var(--fs-xs); font-weight:600; color:{COLORS["text_muted"]};
                      text-transform:uppercase; letter-spacing:.08em; }}
        .t-kpi     {{ font-size:var(--fs-2xl); font-weight:700; line-height:1; }}
        /* Inner content tile (inside a section / .ir-card) — the compact card */
        .ir-tile    {{ background:{COLORS["surface_hover_bg"]}; border-radius:8px; padding:10px 12px; }}
        .ir-card-sm {{ background:{COLORS["surface_bg"]}; border:1px solid {COLORS["border"]};
                       border-radius:8px; padding:12px 14px; }}
        /* Collapsible (expansion) HEADERS — Quasar renders the header label in its own
           element, so a per-expansion inline `color:` never reaches it and the title fell
           back to a near-white default "part of the time". Force every expansion header to a
           solid heading grey, app-wide, so section breaks are always legible. */
        .q-expansion-item__container > .q-item {{ color:{COLORS["text_heading"]} !important; }}
        .q-expansion-item__container > .q-item .q-item__label {{
            color:{COLORS["text_heading"]} !important; font-weight:600; }}
        /* Tinted-panel expansion: a reusable NON-WHITE collapse box. Quasar's q-card/content inside an
           expansion defaults to a white surface that ignores the inline background on the root, so an
           expansion styled as a panel kept showing a white body. Force the header row AND the content
           to the tinted surface with !important so the whole box is one non-white panel, permanently. */
        .panel-tinted, .panel-tinted > .q-expansion-item__container,
        .panel-tinted .q-expansion-item__container > .q-item,
        .panel-tinted .q-expansion-item__content {{
            background:{COLORS["surface_hover_bg"]} !important; }}
        /* Every collapsible must read as a BOUNDED BOX, not a stray line of text on the
           page. Default Quasar expansions have no fill and no border, so their headers
           looked like floating text (recurring complaint). Give every expansion a grey
           fill + visible border + radius, app-wide, via tokens (adapts to theme). */
        .q-expansion-item {{
            background:{COLORS["surface_hover_bg"]};
            border:1px solid {COLORS["border"]};
            border-radius:8px;
            margin-bottom:6px; }}
        /* Status colour utilities — tied to tokens, replacing hardcoded hexes */
        .c-pos    {{ color:{COLORS["positive"]}; }}
        .c-neg    {{ color:{COLORS["negative"]}; }}
        .c-warn   {{ color:{COLORS["warning"]}; }}
        .c-accent {{ color:{COLORS["accent"]}; }}
        .c-muted  {{ color:{COLORS["text_muted"]}; }}
        .fw-600 {{ font-weight:600; }}
        .fw-700 {{ font-weight:700; }}
    """)


def _render_fallback_banner():
    """Page-top degraded-DB warning (shown on login too, since a Neon outage is the exact
    reason a sign-in would fail). Implementation lives in the import-safe signals module."""
    from page_modules_nicegui.signals import fallback_banner
    fallback_banner()


def _auth_card(title, subtitle):
    """Shared centered card shell for the login / change-password pages."""
    col = ui.column().classes("w-full items-center").style("margin-top:8vh;")
    with col:
        card = ui.card().style(
            f"width:360px;padding:24px;background:{COLORS['surface_bg']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;")
        with card:
            ui.label(title).classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};")
            ui.label(subtitle).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-bottom:8px;")
    return card


@ui.page("/login")
def login_page():
    apply_theme()
    if _current_user():
        ui.navigate.to("/")
        return
    _render_fallback_banner()   # explains a sign-in failure when the Neon user store is offline
    with _auth_card("IRconnect", "Sign in"):
        email = ui.input("Email").props("outlined dense autofocus").classes("w-full")
        pw = ui.input("Password", password=True, password_toggle_button=True).props("outlined dense").classes("w-full")
        msg = ui.label("").style("color:#B91C1C;font-size:var(--fs-sm);min-height:16px;")

        def do_login():
            from core import auth
            u = auth.authenticate((email.value or "").strip(), pw.value or "")
            if not u:
                msg.set_text("Invalid email or password.")
                return
            app.storage.user["user_id"] = u["user_id"]
            app.storage.user.pop("active_client_id", None)  # start from the user's default tenant
            auth.touch_login(u["user_id"])
            # Where to land: forced rotation first; then staff -> the Console (above the
            # tenants), client users -> straight into their one tenant's workspace.
            if u["must_change_password"]:
                dest = "/change-password"
            else:
                dest = "/console" if auth.is_staff(u) else "/"
            ui.navigate.to(dest)

        pw.on("keydown.enter", lambda _: do_login())
        ui.button("Sign in", on_click=do_login).props("color=primary").classes("w-full").style("margin-top:8px;")


@ui.page("/change-password")
def change_password_page():
    apply_theme()
    user = _current_user()
    if not user:
        ui.navigate.to("/login")
        return
    with _auth_card("Set a new password", f"{user['user_id']} — first sign-in"):
        p1 = ui.input("New password", password=True, password_toggle_button=True).props("outlined dense autofocus").classes("w-full")
        p2 = ui.input("Confirm password", password=True, password_toggle_button=True).props("outlined dense").classes("w-full")
        msg = ui.label("").style("color:#B91C1C;font-size:var(--fs-sm);min-height:16px;")

        def do_change():
            from core import auth
            a, b = (p1.value or ""), (p2.value or "")
            if len(a) < 10:
                msg.set_text("Use at least 10 characters.")
                return
            if a != b:
                msg.set_text("Passwords do not match.")
                return
            auth.set_password(user["user_id"], a)
            ui.navigate.to("/")

        p2.on("keydown.enter", lambda _: do_change())
        ui.button("Update password", on_click=do_change).props("color=primary").classes("w-full").style("margin-top:8px;")


@ui.page("/admin/users")
def user_admin_page():
    """Staff-only user administration: list every login, add a user (seeded with the shared
    default password + forced first-login rotation), reset a password, or enable/disable a login.
    Cross-tenant by nature, so it lives OUTSIDE the tenant-scoped main nav and is gated to
    praxis_staff — a client_user hitting this URL directly is bounced to /."""
    from core import auth
    from config.client_config import ROLE_PERMISSIONS
    apply_theme()
    user = _current_user()
    if not user:
        ui.navigate.to("/login"); return
    if user["must_change_password"]:
        ui.navigate.to("/change-password"); return
    if not auth.is_staff(user):
        ui.navigate.to("/"); return

    role_keys = list(ROLE_PERMISSIONS.keys()) or ["IR"]
    tenant_opts = {cid: rec.get("name", cid) for cid, rec in CLIENT_REGISTRY.items()}
    default_pw = auth.default_user_password()

    col = ui.column().classes("w-full items-center")
    with col:
        wrap = ui.column().style("width:min(1000px,94vw);margin-top:24px;gap:18px;")
        with wrap:
            # header
            with ui.row().classes("w-full items-center"):
                ui.label("User Administration").classes("text-2xl font-bold") \
                    .style(f"color:{COLORS['text_heading']};")
                ui.space()
                ui.button("Back to app", icon="arrow_back",
                          on_click=lambda: ui.navigate.to("/")).props("flat dense") \
                    .style(f"color:{COLORS['text_muted']};")

                def _logout():
                    app.storage.user.pop("user_id", None)
                    app.storage.user.pop("active_client_id", None)
                    ui.navigate.to("/login")
                ui.button("Sign out", icon="logout", on_click=_logout).props("flat dense") \
                    .style(f"color:{COLORS['text_muted']};")

            ui.label(f"New logins are seeded with the shared default password "
                     f"(“{default_pw}”) and must change it on first sign-in.") \
                .style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

            # ── add-user card ───────────────────────────────────────────────
            with ui.card().classes("w-full").style(
                    f"padding:18px;background:{COLORS['surface_bg']};"
                    f"border:1px solid {COLORS['border']};border-radius:10px;"):
                ui.label("Add a user").classes("text-base font-bold") \
                    .style(f"color:{COLORS['text_heading']};margin-bottom:4px;")
                with ui.row().classes("w-full items-end").style("gap:12px;flex-wrap:wrap;"):
                    a_email = ui.input("Email").props("outlined dense").style("min-width:230px;")
                    a_name = ui.input("Display name").props("outlined dense").style("min-width:180px;")
                    a_type = ui.select(
                        {auth.CLIENT_RW: "Client — read/write (1 tenant)",
                         auth.CLIENT: "Client — read-only (1 tenant)",
                         auth.STAFF: "Praxis Point staff (all tenants)"},
                        value=auth.CLIENT_RW, label="Account type").props("outlined dense") \
                        .style("min-width:240px;")
                    a_tenant = ui.select(tenant_opts, value=next(iter(tenant_opts)),
                                         label="Home tenant").props("outlined dense") \
                        .style("min-width:150px;")
                    a_role = ui.select(role_keys, value=role_keys[0], label="Role") \
                        .props("outlined dense").style("min-width:120px;")

                    # tenant + role apply to either client type (read-only or read/write); hide for staff
                    def _sync_type():
                        is_client = a_type.value in (auth.CLIENT, auth.CLIENT_RW)
                        a_tenant.set_visibility(is_client)
                        a_role.set_visibility(is_client)
                    a_type.on_value_change(lambda _: _sync_type())

                    def _add():
                        email = (a_email.value or "").strip().lower()
                        if "@" not in email:
                            ui.notify("Enter a valid email.", type="warning"); return
                        is_client = a_type.value in (auth.CLIENT, auth.CLIENT_RW)
                        home = a_tenant.value if is_client else None
                        role = a_role.value if is_client else "IR"
                        if is_client and not home:
                            ui.notify("Pick a home tenant for a client user.", type="warning"); return
                        ok = auth.create_user(email, default_pw, a_type.value, home, role,
                                              display_name=(a_name.value or "").strip() or email,
                                              must_change=True)
                        if not ok:
                            ui.notify(f"{email} already exists.", type="negative"); return
                        ui.notify(f"Created {email} — default password “{default_pw}” "
                                  f"(must change on first login).", type="positive", timeout=8000)
                        a_email.value = ""; a_name.value = ""
                        _render_users.refresh()

                    ui.button("Add user", icon="person_add", on_click=_add).props("color=primary")
                _sync_type()

            # ── reset sandbox data (per tenant) ─────────────────────────────
            # After a client operator has been exploring with a read/write login, wipe
            # what they created back to a clean slate. Per-tenant, user-generated stores
            # only (see core.sandbox) — shared house data is never touched.
            with ui.card().classes("w-full").style(
                    f"padding:18px;background:{COLORS['surface_bg']};"
                    f"border:1px solid {COLORS['border']};border-radius:10px;"):
                ui.label("Reset sandbox data").classes("text-base font-bold") \
                    .style(f"color:{COLORS['text_heading']};margin-bottom:4px;")
                ui.label("Clears a tenant's user-generated data — NDR trips, promoted prospects, "
                         "inbound requests, scheduled meetings, meeting log, logged interactions, "
                         "confirmed speaker lineups, and call-opening edits — back to a clean slate. "
                         "Shared house data (fund lineups, relationship-quality notes) is not touched.") \
                    .style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-bottom:8px;")
                with ui.row().classes("items-end").style("gap:12px;"):
                    r_tenant = ui.select(tenant_opts, value=next(iter(tenant_opts)), label="Tenant") \
                        .props("outlined dense").style("min-width:200px;")

                    def _open_reset_confirm():
                        from core import sandbox
                        cid = r_tenant.value
                        tname = tenant_opts.get(cid, cid)
                        prev = sandbox.preview(cid)
                        with ui.dialog() as d, ui.card().style(
                                f"background:{COLORS['surface_bg']};min-width:min(440px,92vw);"):
                            ui.label(f"Reset {tname} sandbox?").classes("text-lg font-bold") \
                                .style(f"color:{COLORS['text_heading']};")
                            if prev:
                                ui.label("This will permanently clear:").style(
                                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                                for lbl, n in prev.items():
                                    ui.label(f"•  {n} {lbl}").style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")
                            else:
                                ui.label("Nothing to clear — this tenant is already clean.").style(
                                    f"color:{COLORS['text_muted']};font-size:var(--fs-base);")
                            with ui.row().classes("w-full justify-end").style("gap:8px;margin-top:8px;"):
                                ui.button("Cancel", on_click=d.close).props("flat")

                                def _do_reset():
                                    cleared = sandbox.reset_tenant(cid)
                                    d.close()
                                    summary = ", ".join(f"{n} {l.lower()}" for l, n in cleared.items()) or "nothing"
                                    ui.notify(f"Reset {tname} — cleared {summary}.", type="positive", timeout=8000)
                                _rb = ui.button("Reset — clear it", icon="delete_sweep",
                                                on_click=_do_reset).props("color=negative")
                                if not prev:
                                    _rb.disable()
                        d.open()
                    ui.button("Reset sandbox data…", icon="cleaning_services",
                              on_click=_open_reset_confirm).props("outline color=negative")

            # ── user list ───────────────────────────────────────────────────
            @ui.refreshable
            def _render_users():
                users = auth.list_users()
                with ui.card().classes("w-full").style(
                        f"padding:0;background:{COLORS['surface_bg']};"
                        f"border:1px solid {COLORS['border']};border-radius:10px;overflow:hidden;"):
                    # header row
                    cols = "2.4fr 1.6fr 1fr 1fr .7fr 1.1fr 1.4fr"
                    with ui.element("div").style(
                            f"display:grid;grid-template-columns:{cols};gap:8px;padding:10px 14px;"
                            f"background:{COLORS['canvas_bg']};font-size:var(--fs-xs);font-weight:700;"
                            f"letter-spacing:.03em;color:{COLORS['text_muted']};"):
                        for h in ("EMAIL", "NAME", "TYPE", "TENANT", "ROLE", "STATUS", "ACTIONS"):
                            ui.label(h)
                    for u in users:
                        is_self = u["user_id"].lower() == user["user_id"].lower()
                        staff = u["account_type"] == auth.STAFF
                        tenant = "— all —" if staff else tenant_opts.get(u["home_client_id"], u["home_client_id"] or "—")
                        with ui.element("div").style(
                                f"display:grid;grid-template-columns:{cols};gap:8px;padding:10px 14px;"
                                f"align-items:center;border-top:1px solid {COLORS['border']};font-size:var(--fs-sm);"
                                f"color:{COLORS['text_body']};"):
                            ui.label(u["user_id"] + (" (you)" if is_self else "")).style("word-break:break-all;")
                            ui.label(u["display_name"] or "—")
                            _tl = ("Staff" if staff else
                                   "Client · R/W" if u["account_type"] == auth.CLIENT_RW else "Client · read-only")
                            _tc = ("#1D4ED8" if staff else
                                   "#15803D" if u["account_type"] == auth.CLIENT_RW else "#B45309")
                            ui.label(_tl).style(f"color:{_tc};")
                            ui.label(tenant)
                            ui.label("—" if staff else u["role_key"])
                            # status: active + whether they still owe a password change
                            with ui.row().style("gap:6px;align-items:center;"):
                                ui.label("Active" if u["active"] else "Disabled") \
                                    .style(("color:#15803D;" if u["active"] else "color:#B91C1C;") + "font-weight:600;")
                                if u["must_change_password"]:
                                    ui.label("• pw reset") \
                                        .style("color:#B45309;font-size:var(--fs-2xs);").tooltip(
                                        "Must change password on next login")
                            # actions
                            with ui.row().style("gap:2px;"):
                                def _reset(uid=u["user_id"]):
                                    pw = auth.admin_reset_password(uid)
                                    ui.notify(f"{uid} reset to “{pw}” (must change next login).",
                                              type="positive", timeout=8000)
                                    _render_users.refresh()
                                ui.button(icon="lock_reset", on_click=_reset) \
                                    .props("flat dense round").tooltip("Reset password to default")

                                def _toggle(uid=u["user_id"], now_active=u["active"]):
                                    auth.set_user_active(uid, not now_active)
                                    ui.notify(f"{uid} {'disabled' if now_active else 'enabled'}.",
                                              type="info")
                                    _render_users.refresh()
                                if is_self:
                                    ui.button(icon="block").props("flat dense round").props("disable") \
                                        .tooltip("You can't disable your own account")
                                else:
                                    ui.button(icon="toggle_off" if u["active"] else "toggle_on",
                                              on_click=_toggle).props("flat dense round") \
                                        .tooltip("Disable login" if u["active"] else "Enable login")

            _render_users()


@ui.page("/console")
def console_page_route():
    """Praxis Point operator home — the surface ABOVE the tenants (staff-only). Client users
    have no business here and are bounced to their workspace. Guards mirror /admin/users."""
    from core import auth
    apply_theme()
    user = _current_user()
    if not user:
        ui.navigate.to("/login"); return
    if user["must_change_password"]:
        ui.navigate.to("/change-password"); return
    if not auth.is_staff(user):
        ui.navigate.to("/"); return
    _render_fallback_banner()   # operators especially need to know the store is degraded
    from page_modules_nicegui import console_page
    console_page.render_console_home(user)


# Pretty labels for the canonical classifier tokens (core.contact_classifier).
_ROLE_LABELS = {
    "buy_side_pm": "Buy-side PM", "buy_side_sector_pm": "BS sector PM",
    "bs_sector_analyst": "BS sector analyst", "bs_generalist": "BS generalist",
    "bs_analyst": "BS analyst", "bs_unspecified": "Buy-side (role n/s)", "cio": "CIO",
    "director_of_research": "Dir. of Research", "associate_pm": "Associate PM",
    "ss_analyst": "Sell-side analyst", "ss_sector_analyst": "SS sector analyst",
    "ss_associate": "SS associate", "ss_sales": "SS sales", "ss_unspecified": "Sell-side (role n/s)",
    "trader": "Trader", "strategist_macro": "Strategist", "asset_allocator": "Asset allocator",
    "esg_governance": "ESG / Governance", "principal_csuite": "Principal / C-suite",
    "ria_advisor": "RIA advisor", "family_office": "Family office", "consultant": "Consultant",
    "banker": "Banker", "media": "Media", "ir_other": "IR / other"}
_SEN_LABELS = {"principal": "Principal", "decision_maker": "Decision-maker",
               "influencer": "Influencer", "junior": "Junior", "unknown": "—"}
_FIRM_LABELS = {"asset_manager": "Asset manager", "ria": "RIA", "broker_dealer": "Broker-dealer",
                "asset_owner": "Asset owner", "family_office": "Family office",
                "consultant": "Consultant", "ocio": "OCIO", "bank": "Bank", "insurance": "Insurance"}
_CURRENCY_LABELS = {"active_filer": "Active 13F filer", "inactive_filer": "Inactive filer",
                    "no_13f": "No 13F (small/RIA)", "unresolved": "Unresolved", "ambiguous": "Ambiguous"}


@ui.page("/contacts")
def house_contacts_page():
    """Staff-only browse of the GLOBAL house-contact universe (core.contacts) — filter by role,
    seniority, firm type, country, validation status; scan the classified + scrubbed seed."""
    from core import auth, contacts as C
    apply_theme()
    user = _current_user()
    if not user:
        ui.navigate.to("/login"); return
    if user["must_change_password"]:
        ui.navigate.to("/change-password"); return
    if not auth.is_staff(user):
        ui.navigate.to("/"); return

    val_color = {"verified": COLORS.get("positive", "#1B7F45"), "probable": COLORS.get("accent", "#1D3E70"),
                 "stale": COLORS.get("warning", "#9A6410"), "invalid": "#B0242C",
                 "unknown": COLORS.get("text_muted", "#6A7789")}
    facets = C.contact_facets()
    state = {"q": "", "primary_role": None, "seniority": None, "firm_type": None,
             "country": None, "validation_status": None, "market_cap": None}

    def opts(col, labels=None):
        o = {None: "All"}
        for v, n in facets.get(col, []):
            o[v] = f"{(labels.get(v, v) if labels else v)} ({n})"
        return o

    def _open_roster_pms_dialog():
        """Whole-book PM roster: for every firm the fund-lineup crosswalk resolves to a fund family,
        read its SEC prospectus and add its portfolio managers to the house CRM (classified, CIK-
        linked, deduped). Rule-based first; the AI reads formats the rules can't. Runs firm-by-firm
        off-thread with live progress so a multi-minute pass never blocks the page."""
        import asyncio
        from core import fund_managers as fmg
        firms = fmg.eligible_firms()
        dlg = ui.dialog()
        with dlg, ui.card().classes("w-full").style("max-width:640px;"):
            ui.label("Roster portfolio managers from prospectuses").classes("text-lg font-bold") \
                .style(f"color:{COLORS['text_heading']};")
            ui.label(
                f"{len(firms)} firms in the fund-lineup crosswalk resolve to a fund family. For each, "
                "IRconnect reads the SEC prospectus and adds its portfolio managers to the house CRM "
                "— classified, CIK-linked, deduped against anyone already here. Rule-based first; the "
                "AI reads the formats the rules can't.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            prog = ui.linear_progress(value=0, show_value=False).props("instant-feedback")
            prog.set_visibility(False)
            status = ui.label("").style(f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);")
            results = ui.column().classes("w-full").style("max-height:34vh;overflow:auto;gap:1px;")
            btns = ui.row().classes("w-full justify-end gap-2")

            async def _run(limit):
                targets = firms if limit is None else firms[:limit]
                if not targets:
                    status.set_text("No eligible firms — confirm fund-lineup matches first.")
                    return
                btns.set_visibility(False)
                prog.set_visibility(True)
                results.clear()
                tot = {"firms": 0, "found": 0, "added": 0}
                for i, f in enumerate(targets, 1):
                    status.set_text(f"{i}/{len(targets)} · {f['firm']} …")
                    prog.set_value(i / len(targets))
                    try:
                        res = await asyncio.to_thread(fmg.roster_pms_for_firm, f["firm"], f["cik"])
                    except Exception as ex:
                        res = {"found": 0, "added": 0, "error": str(ex)}
                    tot["firms"] += 1
                    tot["found"] += res.get("found", 0)
                    tot["added"] += res.get("added", 0)
                    if res.get("found"):
                        with results:
                            ui.label(f"✓ {f['firm']} — {res['found']} PMs "
                                     f"(+{res.get('added', 0)} new, {res.get('merged', 0)} enriched)").style(
                                f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                status.set_text(
                    f"Done — {tot['added']} PMs added across {tot['firms']} firms ({tot['found']} found).")
                with results:
                    ui.button("Reload to see them", icon="refresh",
                              on_click=lambda: ui.navigate.reload()).props("color=primary")
                    ui.button("Close", on_click=dlg.close).props("flat")

            with btns:
                ui.button(f"Run first 10", icon="playlist_add_check",
                          on_click=lambda: _run(10)).props("color=primary")
                ui.button(f"Run all ({len(firms)})", icon="account_tree",
                          on_click=lambda: _run(None)).props("flat").tooltip(
                    "Reads every firm's prospectus — can take a few minutes and uses AI for hard formats.")
                ui.button("Close", on_click=dlg.close).props("flat")
        dlg.open()

    with ui.column().classes("w-full items-center"):
        wrap = ui.column().style("width:min(1240px,97vw);margin-top:18px;gap:14px;")
        with wrap:
            with ui.row().classes("w-full items-center"):
                ui.label("House Contacts").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
                ui.label(f"Praxis Point CRM · {facets['_total']} contacts").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-base);margin-left:8px;")
                ui.space()
                ui.button("Roster PMs", icon="groups", on_click=_open_roster_pms_dialog) \
                    .props("dense").style(f"background:{COLORS['accent']};color:#fff;").tooltip(
                    "Fill in portfolio managers from fund prospectuses")
                ui.button("Console", icon="arrow_back", on_click=lambda: ui.navigate.to("/console")) \
                    .props("flat dense").style(f"color:{COLORS['text_muted']};")

                def _logout():
                    app.storage.user.pop("user_id", None)
                    app.storage.user.pop("active_client_id", None)
                    ui.navigate.to("/login")
                ui.button("Sign out", icon="logout", on_click=_logout).props("flat dense") \
                    .style(f"color:{COLORS['text_muted']};")

            with ui.row().classes("items-center").style("gap:8px;flex-wrap:wrap;"):
                for v, n in facets.get("validation_status", []):
                    with ui.row().classes("items-center").style(
                            f"gap:6px;background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                            "border-radius:999px;padding:3px 11px;"):
                        ui.element("span").style(
                            f"width:8px;height:8px;border-radius:50%;background:{val_color.get(v, COLORS['text_muted'])};")
                        ui.label(f"{v} · {n}").style(f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);")

            with ui.card().classes("w-full").style(
                    f"padding:12px;background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:10px;"):
                with ui.row().classes("w-full items-end").style("gap:10px;flex-wrap:wrap;"):
                    q_in = ui.input("Search name / firm / email").props("outlined dense clearable") \
                        .style("min-width:240px;flex:1;")
                    q_in.on("keydown.enter", lambda _: (state.update(q=q_in.value or ""), results.refresh()))
                    q_in.on("blur", lambda _: (state.update(q=q_in.value or ""), results.refresh()))

                    def mk(label, col, labels=None):
                        sel = ui.select(opts(col, labels), value=None, label=label) \
                            .props("outlined dense options-dense").style("min-width:150px;")
                        sel.on_value_change(lambda _, c=col, s=sel: (state.update({c: s.value}), results.refresh()))
                    mk("Role", "primary_role", _ROLE_LABELS)
                    mk("Seniority", "seniority", _SEN_LABELS)
                    mk("Firm type", "firm_type", _FIRM_LABELS)
                    mk("Country", "country")
                    mk("Validation", "validation_status")
                    mk("13F currency", "firm_currency", _CURRENCY_LABELS)
                    _ph = ui.select({None: "All", "yes": "Has phone", "no": "No phone"},
                                    value=None, label="Phone").props("outlined dense").style("min-width:130px;")
                    _ph.on_value_change(lambda _, s=_ph: (state.update({"has_phone": s.value}), results.refresh()))

            @ui.refreshable
            def results():
                filters = {k: state[k] for k in ("primary_role", "seniority", "firm_type", "country",
                                                 "validation_status", "firm_currency", "market_cap",
                                                 "has_phone") if state.get(k)}
                res = C.search_contacts(q=state.get("q") or None, filters=filters, limit=2000)
                ui.label(f"{res['total']} matching" + (" · showing first 2000" if res["total"] > 2000 else "")) \
                    .style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

                def role_disp(r):
                    prim = _ROLE_LABELS.get(r.get("primary_role"), r.get("primary_role") or "—")
                    n = len([x for x in (r.get("roles") or "").split(",") if x])
                    return prim + (f"  +{n-1}" if n > 1 else "")
                rows = [{
                    "id": r["contact_id"], "name": r["name"], "firm": r["firm"], "role": role_disp(r),
                    "seniority": _SEN_LABELS.get(r.get("seniority"), r.get("seniority") or "—"),
                    "firm_type": _FIRM_LABELS.get(r.get("firm_type"), r.get("firm_type") or "—"),
                    "country": r.get("country") or "—", "email": r.get("email") or "—",
                    "phone": r.get("phone") or "—",
                    "validation": r.get("validation_status") or "—",
                    "currency": _CURRENCY_LABELS.get(r.get("firm_currency"), r.get("firm_currency") or "—"),
                    "conf": r.get("confidence") if r.get("confidence") is not None else "",
                } for r in res["rows"]]
                columns = [
                    {"name": "name", "label": "Name", "field": "name", "sortable": True, "align": "left"},
                    {"name": "firm", "label": "Firm", "field": "firm", "sortable": True, "align": "left"},
                    {"name": "role", "label": "Role", "field": "role", "sortable": True, "align": "left"},
                    {"name": "seniority", "label": "Seniority", "field": "seniority", "sortable": True, "align": "left"},
                    {"name": "firm_type", "label": "Firm type", "field": "firm_type", "sortable": True, "align": "left"},
                    {"name": "country", "label": "Country", "field": "country", "sortable": True, "align": "left"},
                    {"name": "email", "label": "Email", "field": "email", "align": "left"},
                    {"name": "phone", "label": "Phone", "field": "phone", "align": "left"},
                    {"name": "validation", "label": "Validation", "field": "validation", "sortable": True, "align": "left"},
                    {"name": "currency", "label": "13F currency", "field": "currency", "sortable": True, "align": "left"},
                    {"name": "conf", "label": "Conf", "field": "conf", "sortable": True, "align": "right"},
                ]
                def _open_contact_detail(row):
                    with ui.dialog() as d, ui.card().style("min-width:min(94vw,560px);max-width:640px;"):
                        ui.label(row.get("name", "")).classes("text-lg font-bold").style(
                            f"color:{COLORS['text_heading']};")
                        sub = " · ".join(x for x in [row.get("firm"), row.get("role"),
                                                     (row.get("email") if row.get("email") not in (None, "—") else None)] if x)
                        if sub:
                            ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                        ui.separator().style("margin:6px 0;")
                        _n = ui.textarea("Add a note").props("autogrow dense outlined").classes("w-full")
                        _notes = ui.column().classes("w-full").style("gap:6px;margin-top:6px;")

                        def _render_notes():
                            _notes.clear()
                            with _notes:
                                items = C.all_contact_notes(row.get("id"))
                                ui.label(f"Notes timeline ({len(items)})").style(
                                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-weight:700;letter-spacing:.04em;")
                                if not items:
                                    ui.label("No notes yet — add the first one above.").style(
                                        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                                for it in items:
                                    tag = "House" if it.get("client") == "_house" else it.get("client", "")
                                    with ui.element("div").style(
                                            f"border-left:3px solid {COLORS['accent']};padding:2px 0 2px 9px;"):
                                        ui.label(" · ".join(x for x in [it.get("ts"), tag, it.get("source"), it.get("by")] if x)).style(
                                            f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")
                                        ui.label(it.get("note", "")).style(
                                            f"color:{COLORS['text_body']};font-size:var(--fs-sm);white-space:pre-wrap;")

                        def _save_note():
                            txt = (_n.value or "").strip()
                            if not txt:
                                ui.notify("Nothing to save yet.", type="warning"); return
                            C.add_contact_note(row.get("name"), row.get("firm"), txt, source="House Contacts",
                                               by=(user.get("display_name") or "Staff"), client_id="_house")
                            _n.value = ""
                            _render_notes()
                            ui.notify("Note added to the contact.", type="positive")
                        with ui.row().classes("w-full justify-end gap-2"):
                            ui.button("Close", on_click=d.close).props("flat")
                            ui.button("Add note", icon="add", on_click=_save_note).props("color=primary")
                        _render_notes()
                    d.open()

                ui.label("Click a contact to see or add notes.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                _tbl = ui.table(columns=columns, rows=rows, row_key="id", pagination=25).classes("w-full") \
                    .style(f"background:{COLORS['surface_bg']};cursor:pointer;")
                _tbl.on("rowClick", lambda e: _open_contact_detail(e.args[1]))
            results()


@ui.page("/console/calendar")
def console_calendar_route():
    """Cross-client operator calendar (staff-only) — the whole book's schedule at a glance."""
    from core import auth
    apply_theme()
    user = _current_user()
    if not user:
        ui.navigate.to("/login"); return
    if user["must_change_password"]:
        ui.navigate.to("/change-password"); return
    if not auth.is_staff(user):
        ui.navigate.to("/"); return
    from page_modules_nicegui import console_page
    console_page.render_console_calendar(user)


def _is_mobile_ua(request) -> bool:
    """Heuristic: is this a phone? Used only to choose the initial landing page (Home on a phone,
    Today on desktop) — the drawer's actual responsiveness is width-based. iPad is intentionally not
    matched (modern iPadOS reports a desktop UA, and Today is fine on a tablet)."""
    try:
        ua = (request.headers.get("user-agent", "") if request else "").lower()
    except Exception:
        return False
    return any(k in ua for k in ("mobi", "android", "iphone", "ipod"))


@ui.page("/")
def main_page(request: Request = None):
    apply_theme()
    from core import auth
    # AUTH GATE: no valid session -> login; unchanged bootstrap password -> forced change.
    user = _current_user()
    if not user:
        ui.navigate.to("/login")
        return
    if user["must_change_password"]:
        ui.navigate.to("/change-password")
        return
    # "/" always means "inside a tenant." A staff member who hasn't picked a client yet
    # belongs on the Console; send them there instead of silently defaulting a tenant.
    if auth.is_staff(user) and not app.storage.user.get("active_client_id"):
        ui.navigate.to("/console")
        return
    # Bind the tenant for this session BEFORE the first get_client()/CT() call, so
    # the whole page (header, nav, every data pull) reads the active client, not
    # the default. Re-asserted in render_page() for later navigations. This also
    # enforces the tenant clamp + read-only for client users.
    _bind_active_client()
    client = get_client()
    # "role" is the active RBAC role_key for this session (IR/CEO/CFO/CRO/
    # Legal…). Starts on the default role (IR — full access). The role
    # selector in the drawer changes it; go_to()/_apply_role_gating() below
    # enforce which pages each role may open, per config.client_config's
    # ROLE_PERMISSIONS matrix.
    # "expanded" is the single section whose sub-items are shown (accordion —
    # only one open at a time; the active section auto-expands). "active_tab" is
    # the sub-item to highlight, kept in sync both ways: set on sidebar
    # navigation and updated by nav.tab_changed when the user switches a tab
    # inside a page.
    # Phones land on the curated Home (the on-the-road assistant); desktop lands on Today. Flash-free:
    # decided from the User-Agent at first render, no client round-trip.
    # A digest / deep link can request a specific page (e.g. the weekly read):
    # /?page=Lighthouse. Honour it when it names a real page; otherwise land on the
    # device default (phones -> Home, desktop -> Today).
    _requested = (request.query_params.get("page") if request is not None else None)
    _landing = _requested if _requested in PORTED else ("Home" if _is_mobile_ua(request) else "Today")
    # "expanded" is the SET of sections whose sub-items are shown. Multiple can be open at once
    # (the audit's P3: an accordion that collapses the rest hides the whole map on a wide desktop).
    # The active page auto-expands; clicking an already-active section toggles it.
    # Persona persists per-account (app.storage.user["active_role"]), same as the active tenant.
    # Honour a saved persona only if the current client actually staffs it (role_keys vary per
    # tenant); otherwise fall back to the default so a stale/cross-tenant role can't stick.
    _role = DEFAULT_ROLE_KEY
    try:
        _saved_role = app.storage.user.get("active_role")
        if _saved_role and _saved_role in {r["role_key"] for r in role_roster()}:
            _role = _saved_role
    except Exception:
        _role = DEFAULT_ROLE_KEY
    state = {"page": _landing, "role": _role, "expanded": set(), "active_tab": None}
    # Auto-expand the landing page's own section so its sub-items show immediately (e.g. a deep
    # link to /?page=Investors opens with its rail already visible).
    if NAV_SUBITEMS.get(_landing):
        state["expanded"].add(_landing)
        state["active_tab"] = NAV_SUBITEMS[_landing][0]
    nav_buttons = {}
    # section → tooltip text, for re-labelling nav buttons as access changes.
    desc_by_section = {section: desc
                       for _grp, items in NAV_GROUPS
                       for section, _icon, _label, desc in items}

    # max-width caps how far content stretches on a wide desktop monitor —
    # without it, the column fills 100% of the space next to the drawer
    # (2000px+ on a wide screen), which pushes anything right-aligned (e.g.
    # a card's edit/delete icons) far from the text it belongs to and makes
    # every line of body text uncomfortably long to read. 1050px keeps
    # rows/cards at a scannable width; margin:0 auto centers the column in
    # the remaining space so it doesn't hug the drawer on the left.
    # Breadcrumb — REMOVED from the canvas per user direction: it put a faint
    # "Overview › Today" line at the very top and pushed the greeting/cards down.
    # The sidebar highlight + page heading already say "you are here." The row is
    # kept as a zero-footprint stub (created BEFORE `content`, survives
    # content.clear()) so the 3 update_breadcrumb() call sites stay valid, but it
    # renders nothing and takes no vertical space — content now sits at the top.
    breadcrumb = ui.row().classes("w-full").style(
        "display:none; height:0; min-height:0; padding:0; margin:0;")

    content = ui.column().classes("w-full app-content").style(
        # 1180 max-width, magnified to ~1274 effective by the desktop-only .app-content zoom below —
        # rebalances the canvas: the old 1050px cap + 11-13px body type read tiny next to the 17px
        # nav and left a lot of empty space on a wide monitor. Mobile is excluded from the zoom
        # (@media min-width:641px) so it can't overflow the viewport into a horizontal scroll.
        "padding: 12px 48px 24px 24px; max-width: 1180px; margin: 0 auto; gap: 12px;"
    )

    _PAGE_META = {p: (grp.title(), lbl.split("\n")[0])
                  for grp, items in NAV_GROUPS for p, _ic, lbl, _tt in items}

    def update_breadcrumb():
        # No-op: breadcrumb removed from the canvas (see stub above). Kept as a
        # function so the existing call sites don't need to change.
        breadcrumb.clear()

    def render_page():
        content.clear()
        # Re-assert the tenant from session storage every render: a nav click can
        # execute in a fresh async context where the ContextVar set at page load
        # is not visible, so without this the core calls below could fall back to
        # the default tenant mid-session.
        _bind_active_client()
        # Record who's viewing which page for this render, so page modules can
        # gate mutating controls (core.ui_context.can_edit / is_read_only).
        from core import ui_context
        ui_context.set_page_context(state["role"], state["page"])
        with content:
            module_path = PORTED.get(state["page"])
            if module_path:
                import importlib
                try:
                    module = importlib.import_module(module_path)
                    render_fn_name = f"render_{state['page'].lower()}_page"
                    _render_fn = getattr(module, render_fn_name)
                    # Today is magnified ~15% as a whole page (header, hero, top story and every
                    # dashboard section together) via one width-compensated .emph-15 wrapper —
                    # zoom:1.15 + width:calc(100%/1.15) so it stays one content-width wide (no
                    # horizontal scroll) and nests on the desktop .app-content 1.08 magnify.
                    if state["page"] == "Today":
                        with ui.element("div").classes("emph-15"):
                            _render_fn()
                    else:
                        _render_fn()
                except Exception:
                    # A page that throws while rendering used to just leave
                    # the user staring at a blank/half-cleared screen — the
                    # click "did nothing" (see earnings_page.py's generate()
                    # docstring for the same failure mode, one level down).
                    # This surfaces it instead: full traceback still goes to
                    # the server console for debugging, but the browser also
                    # gets a clear, dated notice instead of silence.
                    import traceback
                    traceback.print_exc()
                    ui.label(f"{state['page']} failed to load").classes("text-xl font-bold").style(f"color:{COLORS['danger']}")
                    ui.label(
                        "Something broke while rendering this page. The exact error is in the server "
                        "console/terminal log — nothing here was lost, try another tab or reload the app."
                    ).style(f"color:{COLORS['text_muted']}")
                    ui.notify(f"{state['page']} failed to load — see server console for the error.", type="negative")
            else:
                ui.label(f"{state['page']}").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']}")
                ui.label(
                    f"Not ported to the new interface yet — still available in the original app "
                    f"(run app.py) while this section is being rebuilt."
                ).style(f"color:{COLORS['text_muted']}")
        update_breadcrumb()   # reflects the page just rendered (+ its opening tab)

    def go_to(section, tab=None):
        # RBAC guard: a role may only open pages its matrix permits. Applies
        # to both nav-button clicks and programmatic nav.go_to() calls from
        # other pages.
        if not role_can_view(state["role"], section):
            ui.notify(f"The {state['role']} role has no access to {section}.", type="warning")
            return
        from page_modules_nicegui import nav
        subs = NAV_SUBITEMS.get(section)
        state["page"] = section
        # Multi-open: expand the section we're navigating to, WITHOUT collapsing the others the
        # user already opened. Single-view pages (no subs) leave the set untouched.
        if subs:
            state["expanded"].add(section)
        # Highlight the requested sub-item, or the page's first tab when arriving
        # via the parent (which opens on that first tab).
        state["active_tab"] = (tab or (subs[0] if subs else None))
        # Hand the target page the tab to open on (its tab strip reads this once).
        nav.set_target_tab(tab)
        render_nav()
        render_page()
        render_bottom_nav()

    def _nav_click(section):
        # Clicking the section you're already on toggles its sub-items open/closed (multi-open
        # sidebar); clicking any other section navigates there and expands it.
        subs = NAV_SUBITEMS.get(section)
        if subs and section == state["page"]:
            if section in state["expanded"]:
                state["expanded"].discard(section)
            else:
                state["expanded"].add(section)
            render_nav()
        else:
            go_to(section)

    def on_tab_change(tab_name):
        # Page → sidebar sync: user switched a tab inside the current page, so
        # move the sidebar's sub-item highlight to match, and update the breadcrumb.
        if tab_name and tab_name != state["active_tab"]:
            state["active_tab"] = tab_name
            render_nav()
            update_breadcrumb()

    def _on_role_change(e):
        state["role"] = e.value
        # Persist the chosen persona per-account (same store as the active tenant) so it
        # survives restarts and new tabs — validated against the client's roster on reload.
        try:
            app.storage.user["active_role"] = e.value
        except Exception:
            pass
        # If the current page isn't allowed for the newly-selected role, jump
        # to the first page that role can view.
        if not role_can_view(state["role"], state["page"]):
            allowed = [s for s in NAV_SECTIONS if role_can_view(state["role"], s)]
            state["page"] = allowed[0] if allowed else "Today"
        # Re-sync the accordion to whatever page is now active (role gating in
        # render_nav locks the rest).
        _subs = NAV_SUBITEMS.get(state["page"])
        # Drop any now-locked sections from the open set, then keep the active page expanded.
        state["expanded"] = {s for s in state["expanded"] if role_can_view(state["role"], s)}
        if _subs:
            state["expanded"].add(state["page"])
        state["active_tab"] = _subs[0] if _subs else None
        render_nav()
        render_page()
        render_bottom_nav()

    from page_modules_nicegui import nav
    nav.register(go_to, on_tab_change)

    # RESPONSIVE DRAWER: leave value at its default (None). NiceGUI then sets show-if-above and asks
    # the client to open/close the drawer by layout width — so on desktop (>=1024px) it docks beside
    # the content, and on a phone it becomes an off-canvas overlay toggled by the header ☰, leaving the
    # content full-width. (The old `value=True` + `breakpoint=0` FORCED it permanently docked at every
    # width, which is why the sidebar ate half a phone screen and squished the content to one word per
    # line. Verified at 1280px and 390px.)
    drawer = ui.left_drawer().style(
        f"background:{COLORS['sidebar_bg']}; border-right:1px solid {COLORS['border']};"
    ).props("width=280 bordered")

    with ui.header().style(f"background:{COLORS['sidebar_bg']}; border-bottom:1px solid {COLORS['border']};"):
        # Drawer toggle (☰). Hidden on desktop (≥1024px, where the drawer is docked and always
        # visible, so it's redundant) via the .drawer-toggle CSS rule. Kept below 1024px, where the
        # drawer is an off-canvas overlay and this is the only way to open the nav — so the mobile
        # app is unaffected (its dedicated nav is handled separately in the mobile pass).
        ui.button(icon="menu", on_click=drawer.toggle).props("flat color=white round").classes("drawer-toggle")
        # Tenant identity / switcher. Options are the tenants THIS user may see
        # (auth.allowed_clients) — so a client_user never gets a switcher (one tenant ->
        # static label), and staff switch only within their allowed set. The switch handler
        # re-checks membership as a second gate.
        from core import auth
        _allowed = auth.allowed_clients(user)
        if len(_allowed) > 1:
            _client_opts = {cid: CLIENT_REGISTRY[cid].get("name", cid) for cid in _allowed}

            def _switch_client(e):
                new_id = getattr(e, "value", None)
                if new_id in _allowed:
                    app.storage.user["active_client_id"] = new_id
                    ui.navigate.reload()

            ui.select(_client_opts, value=get_active_client_id(), on_change=_switch_client) \
                .props("dense outlined") \
                .classes("text-lg font-bold") \
                .style(f"min-width:210px;color:{COLORS['text_heading']};")
        else:
            ui.label(client.get("name", "")).classes("text-lg font-bold").style(
                f"color:{COLORS['text_heading']}")
        ui.space()
        # Today's date lives in the header (top bar), not on the page canvas.
        from datetime import datetime as _dt_hdr
        ui.label(_dt_hdr.now().strftime("%A, %B %d, %Y")).style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);text-transform:uppercase;"
            "letter-spacing:.08em;font-weight:600;white-space:nowrap;")
        ui.space()

        # Session identity + read-only badge + logout.
        if auth.is_readonly_user(user):
            ui.label("VIEW-ONLY").style(
                "background:#B45309;color:white;font-size:var(--fs-micro);font-weight:700;letter-spacing:.05em;"
                "padding:2px 8px;border-radius:10px;")
        ui.label(user.get("display_name") or user["user_id"]).style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

        # Staff-only: back up to the Console (portfolio home) + user administration.
        if auth.is_staff(user):
            ui.button(icon="grid_view",
                      on_click=lambda: ui.navigate.to("/console")) \
                .props("flat round dense").style(f"color:{COLORS['text_muted']};") \
                .tooltip("Praxis Point Console")
            ui.button(icon="manage_accounts",
                      on_click=lambda: ui.navigate.to("/admin/users")) \
                .props("flat round dense").style(f"color:{COLORS['text_muted']};") \
                .tooltip("User administration")

        def _logout():
            app.storage.user.pop("user_id", None)
            app.storage.user.pop("active_client_id", None)
            ui.navigate.to("/login")

        ui.button(icon="logout", on_click=_logout).props("flat round dense") \
            .style(f"color:{COLORS['text_muted']};").tooltip("Sign out")

        # Global database search — one box, reachable from every page, spanning
        # every database the platform holds: tracked funds + prospects, NOBO and
        # SEC 13F holders, analysts, and contacts. core.search_engine ranks the
        # matches; each result deep-links to the surface where that record lives
        # (Target Database results pre-search the fund via search_prefill).
        from core import search_engine
        # Theme-aware: the header (sidebar_bg) is light in the Institutional theme
        # and dark in the dark theme, so a fixed white-text box vanishes on a light
        # header. Use an outlined box on the theme surface with theme text; add
        # Quasar's `dark` only when the surface is actually dark.
        _dark_hdr = int(COLORS["surface_bg"][1:3], 16) < 128
        search = ui.input(placeholder="Search funds, holders, analysts, contacts…").props(
            "dense clearable outlined debounce=250" + (" dark" if _dark_hdr else "")).style(
            f"min-width:300px;max-width:420px;background:{COLORS['surface_bg']};border-radius:8px;")
        search.add_slot("prepend", f'<q-icon name="search" style="color:{COLORS["text_muted"]}" />')
        with search:
            smenu = ui.menu().props("no-parent-event").style(
                "min-width:380px;max-width:560px;max-height:72vh;")
            with smenu:
                sresults = ui.column().classes("w-full gap-0").style("padding:4px 0;")

        _SEARCH_GROUPS = {"Fund": "Funds", "Prospect": "Prospects", "NOBO holder": "NOBO holders",
                          "13F holder": "SEC 13F holders", "Analyst": "Analysts"}

        def _search_go(r):
            smenu.close()
            search.value = ""
            kw = {"search_prefill": r["prefill"]} if r.get("prefill") else {}
            nav.go_to(r["section"], r["tab"], **kw)

        def _run_search():
            sresults.clear()
            q = (search.value or "").strip()
            if len(q) < 2:
                smenu.close()
                return
            hits = search_engine.search(q)
            with sresults:
                if not hits:
                    ui.label(f"No matches for “{q}”").style(
                        "padding:10px 16px;color:#64748B;font-size:var(--fs-sm);")
                else:
                    grouped = {}
                    for r in hits:
                        grouped.setdefault(r["type"], []).append(r)
                    for typ, label in _SEARCH_GROUPS.items():
                        grp = grouped.get(typ)
                        if not grp:
                            continue
                        ui.label(f"{label} ({len(grp)})").style(
                            "padding:7px 16px 2px;font-size:var(--fs-2xs);letter-spacing:.06em;"
                            "color:#94A3B8;font-weight:700;text-transform:uppercase;")
                        for r in grp:
                            with ui.item(on_click=lambda r=r: _search_go(r)).props("clickable dense"):
                                with ui.item_section():
                                    ui.item_label(r["label"]).style("font-size:var(--fs-base);font-weight:600;color:#0F172A;")
                                    ui.item_label(r["sublabel"]).props("caption").style("font-size:var(--fs-xs);color:#64748B;")
            smenu.open()

        search.on_value_change(lambda: _run_search())

    _render_fallback_banner()   # page-top degraded-DB warning (no-op when healthy)

    with drawer:
        # Role selector — options come from the active client's profile
        # (ir_contact + executives), never hardcoded person names. Each option
        # reads "<Person> — <Role label>"; picking one re-gates the nav below.
        ui.html('<div class="nav-section">LOGGED IN AS</div>')
        _roster = role_roster()
        _role_options = {r["role_key"]: r["display"] for r in _roster}
        if _role_options:
            ui.select(options=_role_options, value=state["role"],
                      on_change=_on_role_change).props("dense outlined").classes("w-full q-mb-sm")
        # The nav list is rebuilt (not just restyled) on every navigation and
        # role change so the accordion expansion, active-page, and active-tab
        # highlights always reflect current state — see render_nav().
        nav_list = ui.column().classes("w-full gap-0")

    def render_nav():
        nav_list.clear()
        nav_buttons.clear()
        with nav_list:
            for group_label, items in NAV_GROUPS:
                # Heavy authoring groups (CRM/NDR build-out, earnings scripts, reports, settings) are
                # desktop work — hide them on phones so the mobile nav stays the on-the-road set.
                heavy = group_label in ("CORE WORKFLOWS", "REPORTS & SETTINGS")
                group_box = ui.column().classes(
                    "w-full gap-0 nav-group" + (" nav-group--desktop-only" if heavy else ""))
                with group_box:
                    ui.html(f'<div class="nav-section">{group_label}</div>')
                    for section, icon, label, desc in items:
                        subs = NAV_SUBITEMS.get(section)
                        access = role_access_level(state["role"], section)
                        is_active = section == state["page"]
                        is_open = section in state["expanded"]
                        lines = label.split("\n")
                        line1, line2 = lines[0], (lines[1] if len(lines) > 1 else "")
                        cls = "nav-btn w-full" + (" active" if is_active else "")
                        with ui.button(on_click=lambda s=section: _nav_click(s)).props("flat align=left no-caps").classes(cls) as btn:
                            with ui.row().classes("items-center no-wrap w-full").style("gap:12px;"):
                                ui.icon(icon).classes("nav-icon")
                                with ui.column().classes("gap-0").style("align-items:flex-start;flex:1;min-width:0;"):
                                    ui.label(line1).classes("nav-btn-line1")
                                    if line2:
                                        ui.label(line2).classes("nav-btn-line2")
                                if subs:
                                    ui.icon("expand_more" if is_open else "chevron_right").classes("nav-chevron")
                        nav_buttons[section] = btn
                        # Role gating: lock pages this role can't view.
                        if access == "none":
                            btn.disable()
                            btn.tooltip(f"Locked — the {state['role']} role has no access to {section}")
                        else:
                            btn.enable()
                            btn.tooltip(desc + (" · view-only for this role" if access == "read" else ""))
                        # Accordion: only the expanded, accessible section shows its
                        # sub-items — each deep-links straight to that tab.
                        if subs and is_open and access != "none":
                            def _sub_btn(section, sub):
                                sub_cls = "nav-sub w-full" + (
                                    " active" if (section == state["page"] and sub == state["active_tab"]) else "")
                                gloss = NAV_SUBITEM_GLOSS.get(sub)
                                with ui.button(on_click=lambda s=section, t=sub: go_to(s, t)).props(
                                        "flat align=left no-caps dense").classes(sub_cls) as _sb:
                                    with ui.column().classes("gap-0 items-start").style("min-width:0;"):
                                        ui.label(sub).classes("nav-sub-label")
                                        if gloss:
                                            ui.label(gloss).classes("nav-sub-gloss")
                                if gloss:
                                    _sb.tooltip(gloss)
                            with ui.column().classes("nav-subwrap w-full gap-0"):
                                _groups = NAV_SUBGROUPS.get(section)
                                if _groups:
                                    # Grouped: a small intent header above each cluster of sub-items.
                                    for gname, gcaption, gitems in _groups:
                                        ui.html(f'<div class="nav-subgroup">{gname}'
                                                f'<span>{gcaption}</span></div>')
                                        for sub in gitems:
                                            _sub_btn(section, sub)
                                else:
                                    for sub in subs:
                                        _sub_btn(section, sub)
                # A one-line hint (mobile only) that the heavy tools live on desktop.
                if heavy and group_label == "REPORTS & SETTINGS":
                    ui.html('<div class="resp-stack nav-desktop-hint">CRM build-out, earnings scripts &amp; '
                            'reports are on desktop.</div>')

    # Mobile bottom tab bar — thumb-reachable quick nav to the core on-the-road surfaces. Hidden on
    # desktop via CSS (.mobile-tabbar); the header ☰ still opens the full drawer for everything else.
    # Rebuilt (like render_nav) on each navigation so the active-tab highlight stays in sync.
    _bottom = ui.footer(fixed=True).classes("mobile-tabbar").style(
        f"background:{COLORS['surface_bg']};border-top:1px solid {COLORS['border']};padding:0;")

    def render_bottom_nav():
        _bottom.clear()
        with _bottom:
            with ui.row().classes("w-full items-stretch justify-around").style("gap:0;"):
                for section, icon, label, sub in _MOBILE_TABS:
                    if not role_can_view(state["role"], section):
                        continue
                    active = state["page"] == section
                    clr = "#1D4ED8" if active else COLORS["text_muted"]
                    with ui.column().classes("items-center").style(
                        "flex:1;gap:1px;padding:6px 0 8px;cursor:pointer;"
                        + (f"border-top:2px solid #1D4ED8;background:#1D4ED80D;"
                           if active else "border-top:2px solid transparent;")
                    ).on("click", lambda s=section, t=sub: go_to(s, t)):
                        ui.icon(icon).style(f"color:{clr};font-size:var(--fs-3xl);")
                        ui.label(label).style(f"color:{clr};font-size:var(--fs-2xs);font-weight:{'700' if active else '500'};")

    render_nav()
    render_page()
    render_bottom_nav()

    # On a phone, land on the curated Home (the on-the-road assistant) instead of Today. There is no
    # server-side viewport width, so this is detected client-side once the socket connects, and only
    # redirects when the user is still on the default page (never overrides a deep link or later nav).
    from nicegui import context as _context
    _client = _context.client

    async def _mobile_landing():
        try:
            w = await _client.run_javascript("window.innerWidth", timeout=3.0)
            if isinstance(w, (int, float)) and w < 640 and state["page"] == "Today":
                go_to("Home")
        except Exception:
            pass

    _client.on_connect(_mobile_landing)


async def _kick_off_sec_refresh():
    """Startup hook: refreshes 13D/13G ownership-stake filings (SEC EDGAR)
    for the active client and its full peer set (core.sec_filings) in the
    background as soon as the server comes up — this is the "series of
    commands on startup" the platform is meant to run automatically,
    rather than someone having to remember to go check SEC filings by
    hand. Deliberately non-blocking: refresh_all() runs in a worker thread
    via asyncio.to_thread so the very first page render isn't delayed
    waiting on SEC's servers, and any failure (no network, SEC unreachable,
    a ticker that doesn't resolve to a CIK) is caught and logged rather
    than crashing startup — the app falls back to whatever was cached
    from a previous run, or shows "not yet fetched" if this is the first
    run ever.

    Only 13D/13G refreshes here, not 13F institutional holders — 13F is a
    much heavier quarterly dataset (see core/sec_filings.py's module
    docstring) that's meant to run on its own cadence or an explicit
    "Refresh 13F Holders" button, not on every app launch."""
    import asyncio
    from core import sec_filings

    async def _run():
        try:
            log = await asyncio.to_thread(sec_filings.refresh_all, False)
            print(f"[startup] SEC 13D/13G refresh complete for {len(log['results'])} ticker(s).")
        except Exception as e:
            print(f"[startup] SEC refresh failed (non-fatal — cached/stale data will show instead): {e}")

    asyncio.create_task(_run())


async def _kick_off_market_data_refresh():
    """Startup hook: refreshes price/volume snapshots (core.market_data,
    yfinance) for the active client and its full peer set in the
    background as soon as the server comes up — same non-blocking pattern
    as _kick_off_sec_refresh above (asyncio.to_thread so a slow/unreachable
    Yahoo Finance endpoint never delays the first page render, failures
    caught and logged rather than crashing startup). The Today page's Key
    Market Metrics card and Today's Story narrative read whatever's cached
    by this — see core/market_data.py and page_modules_nicegui/today_page.py.
    The user has confirmed up to a 60-minute delay is acceptable, so this
    doesn't need to re-run on a tight interval — once at startup is enough
    for now; a manual refresh button also exists on the Today page."""
    import asyncio
    from core import market_data

    async def _run():
        # Deferred: a data pull firing the instant the server comes up competes
        # with the first (heavy) page renders and can starve the websocket
        # handshake into a reconnect loop. Cached data shows immediately; the
        # refresh runs once the UI has settled.
        await asyncio.sleep(20)
        try:
            log = await asyncio.to_thread(market_data.refresh_all)
            ok = sum(1 for r in log["results"] if r["ok"])
            print(f"[startup] Market data refresh complete for {ok}/{len(log['results'])} ticker(s).")
        except Exception as e:
            print(f"[startup] Market data refresh failed (non-fatal — cached/stale data will show instead): {e}")

    asyncio.create_task(_run())


async def _kick_off_peer_watch():
    """Daily peer monitoring (core.peer_watch) — pulls each peer's recent SEC
    filings at startup (peer price snapshots are already refreshed by
    _kick_off_market_data_refresh), then re-runs the full peer refresh on a ~12h
    loop so a long-running instance keeps the Today page's Peer Watch card
    current. Non-blocking and failure-tolerant, same pattern as the hooks above."""
    import asyncio
    from core import news_feed, peer_watch

    async def _run():
        # Deferred (and staggered after the market-data refresh) so the filings +
        # news pulls don't pile onto the first renders at launch.
        await asyncio.sleep(40)
        try:
            filings = await asyncio.to_thread(peer_watch.recent_filings, None, 10, True)
            print(f"[startup] Peer Watch: {len(filings)} recent peer filing(s).")
        except Exception as e:
            print(f"[startup] Peer Watch filings refresh failed (non-fatal): {e}")
        try:
            news = await asyncio.to_thread(news_feed.refresh)
            print(f"[startup] Peer news: {len(news)} article(s) in the rolling 7-day window.")
        except Exception as e:
            print(f"[startup] Peer news refresh failed (non-fatal): {e}")
        try:
            from core import rating_actions
            from config.client_config import CLIENT_REGISTRY
            total = 0
            for _cid, _rec in CLIENT_REGISTRY.items():
                tk = _rec.get("ticker")
                if tk:
                    total += len(await asyncio.to_thread(rating_actions.refresh, _cid, tk))
            print(f"[startup] Rating actions (Yahoo): {total} named change(s) backfilled across tenants.")
        except Exception as e:
            print(f"[startup] Rating actions refresh failed (non-fatal): {e}")
        try:
            from core import insider_feed
            from config.client_config import CLIENT_REGISTRY
            itot = 0
            for _cid, _rec in CLIENT_REGISTRY.items():
                tk = _rec.get("ticker")
                if tk:
                    itot += len(await asyncio.to_thread(insider_feed.refresh, _cid, tk))
            print(f"[startup] Insider Form 4 (EDGAR): {itot} transaction(s) across tenants.")
        except Exception as e:
            print(f"[startup] Insider Form 4 refresh failed (non-fatal): {e}")
        try:
            from core import nport_feed
            from config.client_config import CLIENT_REGISTRY
            ntot = 0
            for _cid, _rec in CLIENT_REGISTRY.items():
                tk = _rec.get("ticker")
                if tk:
                    ntot += len(await asyncio.to_thread(nport_feed.refresh, _cid, tk))
            print(f"[startup] N-PORT fund holders (EDGAR): {ntot} fund(s) across tenants.")
        except Exception as e:
            print(f"[startup] N-PORT refresh failed (non-fatal): {e}")
        try:
            from core import edgar_financials
            from config.client_config import CLIENT_REGISTRY, set_active_client_id
            qtot = 0
            for _cid in list(CLIENT_REGISTRY.keys()):
                set_active_client_id(_cid)
                qtot += len(await asyncio.to_thread(edgar_financials.refresh_trends, _cid))
            print(f"[startup] Quarterly trends (XBRL): cached for {qtot} ticker(s) across tenants.")
        except Exception as e:
            print(f"[startup] Quarterly trends refresh failed (non-fatal): {e}")
        while True:
            await asyncio.sleep(12 * 3600)
            try:
                log = await asyncio.to_thread(peer_watch.refresh)
                n = await asyncio.to_thread(news_feed.refresh)
                print(f"[peer-watch] daily refresh: {log} · news window {len(n)}")
            except Exception as e:
                print(f"[peer-watch] daily refresh failed (non-fatal): {e}")

    asyncio.create_task(_run())


def _warm_cache():
    """Pre-read the heavy JSON-store keys the investor views touch (13F holders
    per tracked ticker, NOBO, the conviction candidates) into core.db's in-memory
    cache, so the FIRST navigation to a heavy tab is served from memory (~30 ms)
    instead of paying dozens of cold Neon round-trips (~2 s)."""
    from core import sec_filings
    from config.client_config import get_active_client_id
    cid = get_active_client_id()
    for tk, _name in sec_filings.tracked_tickers():
        try:
            sec_filings.get_cached_13f_holders(tk)
        except Exception:
            pass
    try:
        from core import nobo_engine
        nobo_engine.get_active_pulls(cid)
    except Exception:
        pass
    try:
        from core import peer_prospects
        peer_prospects.build_candidates(cid, limit=40)
    except Exception:
        pass


async def _kick_off_ndr_reply_poll():
    """Poll the Zoho mailbox for analyst replies to NDR replies we sent, and thread them back onto
    the originating request (core.ndr_inbound). Runs on a ~30-min loop while the app is up; inert
    until Zoho is connected. Non-blocking, failure-tolerant, idempotent (dedupes on Message-ID)."""
    import asyncio

    from core import ndr_inbound, zoho_mail

    async def _run():
        await asyncio.sleep(90)
        while True:
            try:
                if zoho_mail.is_configured():
                    r = await asyncio.to_thread(ndr_inbound.poll_replies)
                    if r.get("matched"):
                        print(f"[startup] NDR replies: {r['matched']} threaded onto requests "
                              f"({r.get('checked')} checked).")
            except Exception as e:
                print(f"[startup] NDR reply poll failed (non-fatal): {e}")
            await asyncio.sleep(30 * 60)          # every 30 min — replies aren't time-critical

    asyncio.create_task(_run())


async def _kick_off_holder_moves_refresh():
    """Quarterly auto-refresh of the board holder-move briefings (core.prospect_hook). Checks on a
    ~24h loop but only runs the heavy two-quarter 13F pull when SEC posts a NEW quarter (the cached
    briefing goes stale) — so it does real work ~4x/year per client while staying current on a
    long-running instance. Non-blocking, failure-tolerant, sequential (one ~100MB download at a
    time), and skips the illustrative demo tenant. Same architecture as the hooks above; 13F is
    heavy, so this is its 'own cadence' the _kick_off_sec_refresh docstring points to."""
    import asyncio

    from config.client_config import CLIENT_REGISTRY
    from core import prospect_hook

    async def _run():
        await asyncio.sleep(120)          # well after the lighter startup refreshes settle
        while True:
            try:
                clients = [(cid, rec.get("ticker"), rec.get("name"))
                           for cid, rec in CLIENT_REGISTRY.items() if rec.get("ticker")]
                log = await asyncio.to_thread(prospect_hook.refresh_client_briefings, clients)
                did = sum(1 for r in log if r["status"] == "refreshed")
                print(f"[startup] Holder-move briefings: {did} refreshed for the new quarter, "
                      f"{len(log) - did} current/skipped.")
            except Exception as e:
                print(f"[startup] Holder-move briefing refresh failed (non-fatal): {e}")
            await asyncio.sleep(24 * 3600)  # re-check daily; only pulls when a new 13F quarter posts

    asyncio.create_task(_run())


async def _kick_off_cache_warm():
    """Warm the JSON-store cache shortly after launch (in a worker thread so it
    never blocks the event loop), so the first heavy render is already fast."""
    import asyncio

    async def _run():
        await asyncio.sleep(6)
        try:
            await asyncio.to_thread(_warm_cache)
            print("[startup] JSON-store cache warmed for the heavy investor views.")
        except Exception as e:
            print(f"[startup] Cache warm failed (non-fatal): {e}")

    asyncio.create_task(_run())


def _reload_registry():
    """Overlay the DB `clients` table onto the code seed so DB-defined/edited tenants are live.
    Runs FIRST (before auth seeding, which iterates CLIENT_REGISTRY to seed client_user logins)."""
    try:
        from config.client_config import reload_registry, CLIENT_REGISTRY
        reload_registry()
        print(f"[startup] client registry loaded: {list(CLIENT_REGISTRY)}")
    except Exception as e:
        print(f"[startup] registry reload failed (non-fatal, using code seed): {e}")


def _seed_auth():
    """First-boot / every-boot auth seeding. Idempotent: seeds the Praxis Point admin from
    ADMIN_EMAIL/ADMIN_PASSWORD only if no staff exists yet, then seeds per-tenant client_user
    logins (the two standard logins). Runs before any session, so the read-only guard is inactive
    and the writes go through."""
    try:
        from core import auth
        auth.seed_admin_from_env()
        made = auth.seed_all_client_users()
        if made:
            print(f"[startup] seeded client_user logins: "
                  + ", ".join(f"{cid}({len(u)})" for cid, u in made.items()))
    except Exception as e:
        print(f"[startup] Auth seeding failed (non-fatal): {e}")


def _kick_off_lighthouse_shadow():
    """Daily post-close Lighthouse Shadow run, in-process (no external cron). Idempotent; wrapped so
    a failure here can never affect app startup."""
    try:
        from lighthouse.scheduler import start as _lh_start
        _lh_start()
    except Exception as e:
        print(f"[startup] Lighthouse shadow scheduler failed to start (non-fatal): {e}")


def _poll_ir_inbox_once():
    """One IR-inbox sync — the timer version of the Meeting Hub 'Sync IR Inbox' button.
    The shared inbox routes into the tenant(s) named by MAIL_INBOX_CLIENT_IDS (comma-
    separated); with none set this is inert, so the poller never touches a tenant it
    wasn't deliberately pointed at. Analysts (CA()) are attributed by email; anything
    else relies on the accept-any fallback in mail_gateway."""
    import os
    from core import mail_gateway
    if not mail_gateway.is_configured():
        return
    cids = [c.strip() for c in (os.environ.get("MAIL_INBOX_CLIENT_IDS", "") or "").split(",") if c.strip()]
    if not cids:
        return
    from config.client_config import CA, set_active_client_id
    for cid in cids:
        try:
            set_active_client_id(cid)
            lookup = {a["email"].lower(): {"name": a.get("name"), "firm": a.get("firm"), "kind": "analyst"}
                      for a in (CA() or []) if a.get("email")}
            r = mail_gateway.sync_inbox(lookup, client_id=cid)
            if r.get("ok"):
                routed = sum(1 for m in (r.get("messages") or []) if m.get("category") != "general")
                if routed:
                    print(f"[inbox-poll] {cid}: {routed} item(s) filed for review")
        except Exception as e:
            print(f"[inbox-poll] {cid} failed (non-fatal): {e}")


async def _kick_off_ir_inbox_poll():
    """Poll the IR inbox on a timer (MAIL_INBOX_POLL_MINUTES, default 5) in a worker
    thread, so emailed models/notes file themselves with no one clicking Sync. Dormant
    until MAIL_IMAP_* + MAIL_INBOX_CLIENT_IDS are set."""
    import asyncio, os
    try:
        minutes = max(1, int(os.environ.get("MAIL_INBOX_POLL_MINUTES", "5")))
    except ValueError:
        minutes = 5

    async def _run():
        await asyncio.sleep(20)  # let startup settle
        from core import mail_gateway
        if not (mail_gateway.is_configured() and os.environ.get("MAIL_INBOX_CLIENT_IDS")):
            return  # nothing to poll — stay quiet
        print(f"[startup] IR inbox poller on — every {minutes} min into: {os.environ.get('MAIL_INBOX_CLIENT_IDS')}")
        while True:
            try:
                await asyncio.to_thread(_poll_ir_inbox_once)
            except Exception as e:
                print(f"[inbox-poll] cycle failed (non-fatal): {e}")
            await asyncio.sleep(minutes * 60)

    asyncio.create_task(_run())


app.on_startup(_reload_registry)
app.on_startup(_seed_auth)
app.on_startup(_kick_off_sec_refresh)
app.on_startup(_kick_off_market_data_refresh)
app.on_startup(_kick_off_peer_watch)
app.on_startup(_kick_off_holder_moves_refresh)
app.on_startup(_kick_off_ndr_reply_poll)
app.on_startup(_kick_off_cache_warm)
app.on_startup(_kick_off_lighthouse_shadow)
app.on_startup(_kick_off_ir_inbox_poll)


# ── Lighthouse digest engagement tracking (email opens + click-throughs) ──────────────────────────
# Public, unauthenticated endpoints an email client / browser hits: a 1x1 pixel logs an OPEN, and the
# digest CTA routes through the click endpoint (which logs then redirects to the app). Tokens are
# HMAC-signed so they can't be forged. Everything is best-effort — a tracking failure returns the
# pixel / redirect anyway and never surfaces to the reader.
_LH_PIXEL = base64.b64decode("R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7")  # 1x1 transparent GIF


@app.get("/lh/o/{token}")
def _lh_track_open(token: str, request: Request):
    from fastapi.responses import Response
    try:
        from lighthouse import telemetry
        did = telemetry.parse_token(token)
        if did is not None:
            telemetry.record_open(did, user_agent=request.headers.get("user-agent"))
    except Exception:
        pass
    return Response(content=_LH_PIXEL, media_type="image/gif",
                    headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                             "Pragma": "no-cache"})


@app.get("/lh/c/{token}")
def _lh_track_click(token: str, request: Request):
    from fastapi.responses import RedirectResponse
    # Land the reader on the Lighthouse page (where the weekly/daily read lives), not
    # the app root. Fixed page param -> no open-redirect risk.
    _base = (os.environ.get("LIGHTHOUSE_APP_URL", "") or "").rstrip("/")
    dest = (_base + "/?page=Lighthouse") if _base else "/?page=Lighthouse"
    try:
        from lighthouse import telemetry
        did = telemetry.parse_token(token)
        if did is not None:
            telemetry.record_click(did, user_agent=request.headers.get("user-agent"))
    except Exception:
        pass
    return RedirectResponse(url=dest)


@app.get("/calendar/{token}.ics")
def _calendar_feed(token: str):
    """Subscribable iCalendar feed for one tenant's IR calendar. The token is an
    HMAC-signed client id (conferences.feed_token) so the URL can't be guessed; an
    IR team subscribes once in Outlook/Google and every confirmed conference,
    earnings date and roadshow appears — and auto-refreshes."""
    from fastapi.responses import PlainTextResponse, Response
    try:
        from core import conferences
        cid = conferences.parse_feed_token(token)
        if not cid:
            return PlainTextResponse("Invalid or expired calendar link.", status_code=404)
        ics = conferences.events_to_ics(
            conferences.load_events(cid), cal_name=f"IRconnect — {cid.upper()} IR Calendar")
        return Response(content=ics, media_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": 'inline; filename="ir_calendar.ics"',
                                 "Cache-Control": "public, max-age=3600"})
    except Exception:
        from fastapi.responses import PlainTextResponse as _PTR
        return _PTR("Calendar unavailable.", status_code=500)


# ── PWA — installable home-screen app (manifest + icons + service worker) ──────────────────────────
# Makes IRconnect installable on a phone/desktop home screen. Conservative by design: the service
# worker never caches the live NiceGUI app (only our /pwa/ art + an offline page), so an install can't
# serve a stale UI. See scripts/make_pwa_icons.py for the branded lighthouse/IRconnect icons.
_PWA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "pwa")
app.add_static_files("/pwa", _PWA_DIR)


@app.get("/sw.js")
def _pwa_service_worker():
    from fastapi.responses import Response
    try:
        js = open(os.path.join(_PWA_DIR, "sw.js"), encoding="utf-8").read()
    except Exception:
        js = ""
    # served at root so its scope is "/" (covers the whole app)
    return Response(js, media_type="application/javascript",
                    headers={"Service-Worker-Allowed": "/", "Cache-Control": "no-cache"})


@app.get("/manifest.webmanifest")
def _pwa_manifest():
    from fastapi.responses import Response
    try:
        data = open(os.path.join(_PWA_DIR, "manifest.webmanifest"), encoding="utf-8").read()
    except Exception:
        data = "{}"
    return Response(data, media_type="application/manifest+json", headers={"Cache-Control": "no-cache"})


# Head: manifest + theme color + iOS home-screen tags (iOS has no manifest install, uses these).
ui.add_head_html(
    '<link rel="manifest" href="/manifest.webmanifest">'
    '<meta name="theme-color" content="#1E40AF">'
    '<meta name="mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-capable" content="yes">'
    '<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">'
    '<meta name="apple-mobile-web-app-title" content="IRconnect">'
    '<link rel="apple-touch-icon" href="/pwa/apple-touch-icon.png">'
    '<link rel="icon" type="image/png" sizes="192x192" href="/pwa/icon-192.png">',
    shared=True)

# Responsive tweak: the content column's generous desktop padding (48px right) wastes a phone's
# narrow width, so tighten it below 640px. Drawer responsiveness is handled by NiceGUI (see the
# left_drawer above); this only reclaims horizontal space for the content on small screens.
ui.add_head_html(
    "<style>"
    # ── Type scale (single source of truth) ──────────────────────────────────────────────
    # The app had ~18 ad-hoc inline font-sizes (9–26px). They're consolidated to these 11 steps,
    # erring UP from the old clusters — the small/body text (where legibility matters most) gains
    # ~1px each; larger display sizes lift slightly to keep proportion. Every inline font-size and
    # the .t-* classes reference these vars, so the whole app's type is retuned from here. Nests on
    # the desktop .app-content zoom (1.08), so effective sizes run ~8% larger again on desktop.
    ":root{"
    # Only sub-12px sizes get bumped up (user rule 2026-08-13: raise small text for legibility, leave
    # everything >=12 alone — the earlier all-over +15% read too big). --fs-micro is the reserved
    # footnote-fine-print exception. To resize the app, edit these values, not call sites.
    "--fs-micro:11px;"   # footnote fine print (the ONE small-text exception; was 10)
    "--fs-2xs:12px;"     # fine (was 11 — bumped to the 12 floor)
    "--fs-xs:12px;"      # meta / eyebrow
    "--fs-sm:13px;"      # body — the dominant size
    "--fs-base:14px;"    # body-large / subhead
    "--fs-md:15px;"      # lead
    "--fs-lg:16px;"      # section head / card title
    "--fs-xl:19px;"      # metric value
    "--fs-2xl:21px;"     # page heading / KPI
    "--fs-3xl:23px;"     # large heading
    "--fs-hero:26px;"    # hero
    "}"
    ".mobile-only{display:none;}"
    ".mobile-tabbar{display:none;}"                       # bottom tab bar — phones only (shown below)
    # Responsive swap pair for our OWN content (wide table <-> stacked cards). Deliberately
    # NOT named .mobile-only/.desktop-only: those are RESERVED Quasar visibility classes whose
    # platform-based rules (desktop platform emulating a small screen) override a plain media
    # query. Custom names like .mobile-tabbar are unaffected, so these are too.
    ".resp-wide{display:block;}"                          # e.g. a 5-column table: default (desktop)
    ".resp-stack{display:none;}"                          # its stacked-card equivalent: phones only
    ".nav-desktop-hint{padding:10px 12px 4px;color:#94A3B8;font-size:var(--fs-xs);line-height:1.4;}"
    "@media (max-width:640px){"
    ".app-content{padding:12px 14px 84px !important;}"   # reclaim phone width + clear the fixed tab bar
    ".nav-group--desktop-only{display:none !important;}"  # hide heavy authoring groups on phones
    ".mobile-only{display:block !important;}"
    ".mobile-tabbar{display:block !important;}"
    ".resp-wide{display:none !important;}"                # hide the wide table on phones...
    ".resp-stack{display:block !important;}"              # ...and show the stacked cards instead
    "}"
    # Header ☰ is redundant on desktop (drawer docked/visible); hide it at the docking breakpoint,
    # keep it on tablet/phone where the drawer is an overlay and it's the only way to open the nav.
    # The Earnings top tab strip is the same story — redundant with the sidebar's Earnings sub-items
    # on desktop, so hide it there too (kept below 1024px where there's no docked sidebar).
    "@media (min-width:1024px){.drawer-toggle,.page-tabstrip{display:none !important;}}"
    # .hidden-tabstrip: a tab bar kept in the DOM (its tab_panels model needs it) but never shown at
    # any width — used where clickable status cards ARE the navigation (Earnings workflow stages).
    ".hidden-tabstrip{display:none !important;}"
    # On-page tab strip styled as a SEGMENTED BUTTON control. Ownership/Targeting have no left-nav
    # sub-items, so their strip IS the nav — it must read as buttons, not floating text. Border+radius
    # on the content group (sized to content, centered), a divider between tabs, active tab filled.
    ".seg-tabs{justify-content:center;min-height:0;margin:10px 0 6px;}"
    ".seg-tabs .q-tabs__content{flex:0 0 auto;border:1.5px solid #64748B;border-radius:10px;"
    "overflow:hidden;background:#FFFFFF;box-shadow:0 1px 2px rgba(15,23,42,.06);}"
    ".seg-tabs .q-tab{min-height:0;padding:7px 22px;border-right:1.5px solid #64748B;border-radius:0;"
    "color:#475569;font-weight:700;text-transform:uppercase;letter-spacing:.03em;}"
    ".seg-tabs .q-tab:last-child{border-right:0;}"
    ".seg-tabs .q-tab--active{background:#1E40AF;color:#FFFFFF;}"
    ".seg-tabs .q-tab__label{font-size:12.5px;line-height:1.15;white-space:normal;text-align:center;}"
    ".seg-tabs .q-tab__indicator,.seg-tabs .q-tabs__indicator{display:none !important;}"
    # Ownership only: cap the label width so it wraps to two lines with 'OWNERSHIP' on the bottom line.
    ".seg-tabs-own .q-tab__label{max-width:92px;}"
    # Clickable cards read as buttons: lift + accent ring on hover so the affordance is obvious.
    # Generic (used by the workflow stage cards and the Prior-Qtr replay/transcript cards).
    ".click-card{transition:box-shadow .12s ease,transform .12s ease;}"
    ".click-card:hover{transform:translateY(-1px);box-shadow:0 4px 14px rgba(15,23,42,.14);"
    f"border-color:{COLORS['accent']} !important;}}"
    # ── Global input visibility (the one place inputs get styled) ─────────────────────────
    # Outlined inputs/textareas shipped with a TRANSPARENT fill + a faint border, so they blended
    # into whatever card/canvas sat behind them — which is why every page needed a per-field fix.
    # Give every outlined field a subtle fill + a clear border by default, and an accent border on
    # hover/focus, so an input always reads as a fillable box without page-by-page styling.
    # The border must read clearly against a white card, so it uses a medium slate (#94A3B8),
    # NOT the faint card-edge token — a whisper-gray border on white made inputs invisible (the
    # recurring "I can't tell where to click"). 1.5px so the box edge is unmistakable; the fill
    # stays subtle so text is still legible.
    # !important + full border shorthand so it beats Quasar's own :before border regardless of
    # stylesheet load order — without it, Quasar's faint default won (rest border invisible, only a
    # grey flash on hover). A solid 1.5px slate edge at REST is the floor; accent on hover/focus.
    # One plain grey box, the SAME in every state (rest/hover/focus) — a solid 1.5px slate on all four
    # sides. The :after element (Quasar's focus underline) is forced to the same grey too: left at its
    # default it overlays the bottom edge and made the bottom look open, and its accent colour made the
    # outline change on focus. Grey all the time, all sides.
    f".q-field--outlined .q-field__control{{background:{COLORS['surface_hover_bg']};}}"
    f".q-field--outlined .q-field__control:before{{border:1.5px solid {COLORS['text_muted2']} !important;}}"
    f".q-field--outlined:hover .q-field__control:before{{border:1.5px solid {COLORS['text_muted2']} !important;}}"
    f".q-field--outlined.q-field--focused .q-field__control:before{{border:1.5px solid {COLORS['text_muted2']} !important;}}"
    f".q-field--outlined .q-field__control:after{{border:0 !important;}}"
    # Desktop/tablet only: uniformly magnify the canvas ~8% so the content reads at a comfortable
    # size (the app's body type is inline 11-13px, well below the 17px nav) and uses the wide-monitor
    # space instead of sitting tiny in an empty frame. zoom scales type + cards + spacing + width
    # together (1180 max-width -> ~1274 effective). Phones are excluded so the full-width mobile
    # content can't zoom past the viewport into a horizontal scroll. Degrades gracefully where zoom
    # is unsupported (the wider max-width still applies).
    "@media (min-width:641px){.app-content{zoom:1.08;}}"
    # Per-section emphasis: bump a specific dashboard section ~15% larger than its siblings.
    # zoom scales type+cards+spacing together; the width:calc(100%/1.15) compensation keeps the
    # zoomed block exactly one column wide so it can't overflow into a horizontal scroll. Nests
    # on top of the .app-content 1.08 (so ~1.15x the current rendered size). Verified in-browser.
    ".emph-15{zoom:1.15;width:calc(100% / 1.15);}"
    # Dashboard section container: a grounded white panel (border + radius + soft shadow) so a
    # section's heading and its contents read as one card instead of floating loose on the canvas.
    # The light-grey inner tiles (#EEF2F7) nest cleanly inside it.
    ".today-panel{background:#FFFFFF;border:1px solid #64748B;border-radius:12px;padding:14px 16px;box-shadow:0 1px 3px rgba(15,23,42,.09),0 1px 1px rgba(15,23,42,.05);}"
    # THE ROOT-CAUSE FIX for invisible cards: many cards were styled with only a light fill and NO
    # border, so darkening the border TOKEN never touched them (there was no border to color). Give
    # EVERY card a visible border box by default. No !important, so a card that sets its own inline
    # border (accent/warning rails, the report cards) still wins; fill-only cards finally get a box.
    ".q-card{border:1px solid #64748B;}"
    # Chevrons were near-white and vanished into the background: force the select dropdown arrow
    # and the expansion toggle to a clear grey so they read as affordances.
    ".q-select__dropdown-icon{color:#64748B !important;}"
    ".q-expansion-item__toggle-icon{color:#475569 !important;}"
    # ══ REPORT DESIGN SYSTEM (the validation-scorecard look, applied app-wide) ════════════════════
    # Approved layout standard: report-style tables, colored active headers with count badges, status
    # pills, tasteful semantic colour, hairline separators. One place; classes reused across pages.
    # Separators win by IMPORTANCE (a higher cascade layer than every Quasar border rule, which are all
    # non-!important) AND by matching Quasar's own (0,3,4) specificity path — settled per the framework
    # source, not guesswork.
    # ---- real tables (ui.table) ----
    ".q-table__container{background:#FFFFFF;border:1px solid #64748B;border-radius:10px;overflow:hidden;"
    "box-shadow:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.06);}"
    ".q-table thead th{background:#EEF2F7 !important;color:#64748B !important;text-transform:uppercase;"
    "letter-spacing:.06em;font-weight:700;font-size:11.5px;border-bottom:1px solid #D3DBE4 !important;}"
    ".q-table.q-table>tbody>tr:not(:last-child)>td,.q-table__middle>table.q-table>tbody>tr:not(:last-child)>td"
    "{border-bottom:1px solid #64748B !important;}"
    ".q-table.q-table>tbody>tr:last-child>td{border-bottom:0 !important;}"
    ".q-table tbody td{color:#1F2733;padding:9px 14px;}"
    ".q-table tbody tr:hover td{background:#F8FAFC !important;}"
    # ---- report card + colored active header + count badge ----
    ".report-card{background:#FFFFFF !important;border:1px solid #64748B !important;border-radius:12px !important;"
    "overflow:hidden !important;box-shadow:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.06) !important;"
    "padding:0 !important;gap:0 !important;}"
    ".rhead{display:flex;align-items:center;gap:8px;width:100%;padding:10px 15px;font-size:12.5px;"
    "letter-spacing:.04em;text-transform:uppercase;font-weight:700;}"
    ".rhead .count{margin-left:auto;font-variant-numeric:tabular-nums;font-size:13px;"
    "background:rgba(255,255,255,.6);border-radius:999px;padding:1px 10px;}"
    ".rhead-good{background:#E7F4EC;color:#127A4A;border-bottom:1px solid #BFE2CD;}"
    ".rhead-bad{background:#FBE9E7;color:#B1352D;border-bottom:1px solid #F0C3BD;}"
    ".rhead-warn{background:#FBF0E0;color:#A35A06;border-bottom:1px solid #EECFA1;}"
    ".rhead-neutral{background:#EEF2F7;color:#64748B;border-bottom:1px solid #9AA6B8;}"
    ".rhead-accent{background:#ECEEF8;color:#2F3AA8;border-bottom:1px solid #C7CCEC;}"
    ".rrow{display:flex;align-items:center;gap:10px;width:100%;padding:10px 15px;"
    "border-bottom:1px solid #64748B;color:#1F2733;}"
    ".rrow:last-child{border-bottom:none;}"
    ".rrow:hover{background:#F8FAFC;}"
    ".rrow .rmeta{color:#727A89;font-size:12.5px;}"
    ".rrow .rval{margin-left:auto;font-variant-numeric:tabular-nums;font-weight:700;}"
    # ---- status pills (the "buttons") ----
    ".rpill{display:inline-block;font-size:10.5px;font-weight:700;letter-spacing:.03em;padding:2px 9px;"
    "border-radius:999px;white-space:nowrap;}"
    ".rpill-t1{background:#ECEEF8;color:#2F3AA8;}"
    ".rpill-good{background:#E7F4EC;color:#127A4A;}"
    ".rpill-bad{background:#FBE9E7;color:#B1352D;}"
    ".rpill-warn{background:#FBF0E0;color:#A35A06;}"
    ".rpill-def{background:#EEF2F7;color:#64748B;}"
    # ---- report KPI card ----
    ".rkpi{background:#FFFFFF !important;border:1px solid #64748B !important;border-radius:12px !important;"
    "box-shadow:0 1px 2px rgba(16,24,40,.05),0 1px 3px rgba(16,24,40,.06) !important;padding:15px 16px !important;gap:3px !important;}"
    ".rkpi-lab{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:#64748B;font-weight:700;}"
    # Titled header with an underline rule (header → number → analysis order).
    ".rkpi-head{font-size:14px;font-weight:700;color:#1F2733;width:100%;padding-bottom:6px;"
    "border-bottom:1.5px solid #64748B;}"
    ".rkpi-n{font-size:26px;font-weight:800;line-height:1.1;color:#141821;margin-top:8px;}"
    ".rkpi-sub{font-size:12.5px;color:#4A5160;}"
    ".rkpi-good{color:#127A4A;} .rkpi-bad{color:#B1352D;}"
    "</style>",
    shared=True)

# Body: register the SW, and show an "Install IRconnect" button when the browser offers the install
# (Android / desktop Chrome & Edge fire beforeinstallprompt; iOS installs via Share → Add to Home Screen).
ui.add_body_html(
    '<div id="pwa-install" style="display:none;position:fixed;right:16px;bottom:16px;z-index:9999;">'
    '<button id="pwa-install-btn" style="display:flex;align-items:center;gap:8px;background:#1E40AF;'
    'color:#fff;border:0;border-radius:10px;padding:10px 16px;font:600 13px -apple-system,Segoe UI,'
    'Roboto,sans-serif;box-shadow:0 6px 20px rgba(30,64,175,.35);cursor:pointer;">'
    '<img src="/pwa/icon-192.png" width="20" height="20" style="border-radius:5px;">Install IRconnect</button></div>'
    '<script>(function(){'
    "if('serviceWorker' in navigator){window.addEventListener('load',function(){navigator.serviceWorker.register('/sw.js').catch(function(){});});}"
    "var d=null,w=document.getElementById('pwa-install'),b=document.getElementById('pwa-install-btn');"
    "window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();d=e;if(w)w.style.display='block';});"
    "if(b)b.addEventListener('click',async function(){if(!d)return;d.prompt();await d.userChoice;d=null;if(w)w.style.display='none';});"
    "window.addEventListener('appinstalled',function(){if(w)w.style.display='none';});"
    '})();</script>',
    shared=True)


# ── Web Push (VAPID) — Lighthouse phone alerts ────────────────────────────────────────────────────
@app.get("/push/vapid-public-key")
def _push_vapid_key():
    from fastapi.responses import PlainTextResponse
    try:
        from lighthouse import push
        return PlainTextResponse(push.public_key())
    except Exception:
        return PlainTextResponse("", status_code=503)


@app.post("/push/subscribe")
async def _push_subscribe(request: Request):
    from fastapi.responses import JSONResponse
    try:
        body = await request.json()
        from lighthouse import push
        ok = push.save_subscription(body.get("client_id") or "usio",
                                    body.get("subscription") or body,
                                    user_agent=request.headers.get("user-agent"))
        return JSONResponse({"ok": bool(ok)})
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)


@app.post("/push/unsubscribe")
async def _push_unsubscribe(request: Request):
    from fastapi.responses import JSONResponse
    try:
        body = await request.json()
        sub = body.get("subscription") or body
        ep = sub.get("endpoint") if isinstance(sub, dict) else None
        if ep:
            from lighthouse import push
            push.delete_subscription(ep)
        return JSONResponse({"ok": True})
    except Exception:
        return JSONResponse({"ok": False}, status_code=400)


# Client-side subscribe helper. Exposed as window.irconnectSubscribePush(clientId); the Home page's
# "Enable phone alerts" button calls it from a real click (so Notification.requestPermission runs
# inside a user gesture, which browsers require). Feedback uses a DOM banner (_irToast), NOT alert() —
# iOS silently swallows alert()/confirm()/prompt() inside an installed home-screen PWA, so every status
# message would otherwise be invisible ("the button flickers but nothing happens").
ui.add_body_html('''<script>
function _irB64ToU8(b){var p="=".repeat((4-b.length%4)%4);var s=(b+p).replace(/-/g,"+").replace(/_/g,"/");var r=atob(s),a=new Uint8Array(r.length);for(var i=0;i<r.length;i++)a[i]=r.charCodeAt(i);return a;}
function _irToast(msg,ok){var t=document.getElementById("ir-toast");if(!t){t=document.createElement("div");t.id="ir-toast";t.style.cssText="position:fixed;left:14px;right:14px;bottom:22px;z-index:100000;padding:14px 16px;border-radius:12px;color:#fff;font:600 15px -apple-system,Segoe UI,Roboto,sans-serif;line-height:1.45;text-align:center;box-shadow:0 10px 34px rgba(0,0,0,.32);";document.body.appendChild(t);}t.style.background=ok?"#15803D":"#B45309";t.textContent=msg;t.style.display="block";clearTimeout(window._irTT);window._irTT=setTimeout(function(){t.style.display="none";},9000);}
window.irconnectSubscribePush=async function(clientId){
  try{
    var isIOS=/iphone|ipad|ipod/i.test(navigator.userAgent);
    var standalone=(window.matchMedia&&window.matchMedia("(display-mode: standalone)").matches)||window.navigator.standalone===true;
    if(!("serviceWorker" in navigator)||!("PushManager" in window)){
      _irToast(isIOS&&!standalone?"Open IRconnect from its Home Screen icon (not Safari), then tap Enable again.":"This browser can not do phone alerts. Add IRconnect to your Home Screen.",false);
      return;
    }
    if(typeof Notification!=="undefined"&&Notification.permission==="denied"){
      _irToast("Notifications are OFF for IRconnect. Open iPhone Settings > Notifications > IRconnect, turn Allow Notifications ON, then tap Enable again.",false);
      return;
    }
    _irToast("Setting up phone alerts...",true);
    var perm=await Notification.requestPermission();
    if(perm!=="granted"){
      _irToast("Permission was not granted. Open Settings > Notifications > IRconnect, turn Allow Notifications ON, then tap Enable again.",false);
      return;
    }
    var reg=await navigator.serviceWorker.ready;
    var key=await fetch("/push/vapid-public-key").then(function(r){return r.text();});
    if(!key){_irToast("Could not reach the alert service. Try again in a moment.",false);return;}
    var sub=await reg.pushManager.getSubscription();
    if(!sub){sub=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:_irB64ToU8(key)});}
    var res=await fetch("/push/subscribe",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({client_id:clientId||"usio",subscription:sub.toJSON()})});
    _irToast(res&&res.ok?"Phone alerts are ON for this device. Now tap Send test push.":"Saved on your phone, but the server did not confirm. Tap Send test push to check.",res&&res.ok);
  }catch(e){_irToast("Could not enable alerts: "+((e&&e.message)?e.message:e),false);}
};
// NiceGUI/Vue STRIPS inline onclick from ui.html content, so the Enable button carries no handler of
// its own. Delegate the click from document: this fires synchronously inside the real tap (preserving
// the user-gesture that Notification.requestPermission requires) and works for dynamically-added buttons.
document.addEventListener("click",function(e){var b=(e.target&&e.target.closest)?e.target.closest("[data-ir-enable]"):null;if(b){e.preventDefault();window.irconnectSubscribePush(b.getAttribute("data-ir-enable")||"usio");}},false);
</script>''', shared=True)


# storage_secret is REQUIRED for app.storage.user (the per-browser tenant
# selection). Set IRCONNECT_STORAGE_SECRET in the environment for any real
# deployment; the fallback is a dev-only default and is deliberately named so an
# unset production instance is obvious. Title is the product ("IRconnect"), not a
# single tenant — this app now serves multiple clients.
# PORT: a hosted deploy (Render/Railway/etc.) injects the port to bind via $PORT; locally it
# defaults to 8502. Host stays 0.0.0.0 so the platform's proxy can reach it.
ui.run(title="IRconnect",
       host="0.0.0.0",
       port=int(os.environ.get("PORT", "8502")),
       reload=False,
       storage_secret=os.environ.get("IRCONNECT_STORAGE_SECRET",
                                      "irconnect-dev-secret-set-in-env-for-prod"))
