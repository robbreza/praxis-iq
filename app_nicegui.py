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

from nicegui import app, ui

from config.client_config import (
    CT, get_client, role_roster, role_access_level, role_can_view,
    DEFAULT_ROLE_KEY,
)
from config.theme_tokens import ACTIVE as COLORS

# Nav icons are Material Symbols names (rendered via ui.icon), not emoji — a
# consistent monochrome line set reads more professional and inherits the
# nav's text color (graphite inactive, navy active) instead of fixed emoji.
NAV_GROUPS = [
    ("OVERVIEW", [
        ("Today",     "space_dashboard", "Today", "Morning brief · Alerts · Actions due"),
        ("Calendar",  "calendar_month", "Calendar", "Earnings · conferences · NDR trips — every upcoming event, one page"),
        ("Markets",   "trending_up", "Market Intelligence\nConsensus Estimates", "Consensus · PT tracker · Peer benchmarking"),
    ]),
    ("CORE WORKFLOWS", [
        ("Investors", "groups", "Investor Targeting\nPipeline, NDR & Meetings", "Buy-side intel · NDR planner · Meeting hub · Target database"),
        # Outreach (Mail Gateway) hidden from the sidebar for the demo — the
        # IMAP/SMTP mail workflow isn't ported to this interface yet, so it would
        # only surface a "use app.py" placeholder. Re-add this line to restore it;
        # its render mapping stays in PORTED below.
        ("Earnings",  "description", "Earnings Cycle\nScript Generation", "Script generation · Prior qtr review · Consensus tracker"),
    ]),
    ("REPORTS & SETTINGS", [
        ("Reports",   "assessment", "Reports", "Board report · Investor deck · Reg FD"),
        ("Settings",  "settings", "Settings", "Platform configuration · Data sources"),
    ]),
]

# Flat list of section names, derived from NAV_GROUPS — used anywhere the
# grouping doesn't matter (e.g. looking up which module renders a section).
NAV_SECTIONS = [page for _group, items in NAV_GROUPS for page, *_ in items]

# Sub-items surfaced under each content-heavy page in the sidebar — the page's
# own primary (top-level) tabs, so every real destination is visible in the nav
# and one click deep instead of hidden until you open the page. Labels MUST match
# the ui.tab(...) labels in each page module exactly: the sidebar passes the
# label as the deep-link target and the page opens its tab strip on it (see
# nav.consume_target_tab). Pages not listed here (Today, Calendar, Outreach) are
# single-view and render as plain nav buttons with no expander.
NAV_SUBITEMS = {
    "Markets":   ["IR Risk Dashboard", "Consensus / Guidance", "PT Drift Tracker"],
    "Investors": ["Buy-Side Intelligence", "NDR Planner", "Meeting Hub",
                  "Target Database", "SEC Intelligence", "NOBO Ownership", "Peer Prospects"],
    "Earnings":  ["Prior Qtr Review", "Script Generation", "Narrative Momentum",
                  "Consensus Tracker", "Call Transcripts", "Morning After"],
    "Reports":   ["Board IR Reports", "90-Day IR Plan",
                  "Peer & Market Analysis", "Reg FD & Compliance",
                  "Automation Tracker"],
    "Settings":  ["Platform Config", "Data Sources", "About"],
}

# Which sections have been ported to NiceGUI so far. Update this as each
# page_modules_nicegui/<name>.py lands (see task list — ported incrementally,
# smallest/lowest-risk pages first).
PORTED = {
    "Today": "page_modules_nicegui.today_page",
    "Investors": "page_modules_nicegui.investors_page",
    "Earnings": "page_modules_nicegui.earnings_page",
    "Markets": "page_modules_nicegui.markets_page",
    "Outreach": "page_modules_nicegui.outreach",
    "Calendar": "page_modules_nicegui.calendar_page",
    "Reports": "page_modules_nicegui.reports_page",
    "Settings": "page_modules_nicegui.settings_page",
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
            font-size: 11px;
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: .10em;
            font-weight: 500;
            margin-bottom: 4px;
        }}
        .section-title {{
            font-size: 20px;
            font-weight: 700;
            color: {COLORS["text_heading"]};
            margin-bottom: 16px;
        }}
        /* Real section heading — sentence case, sized/weighted to carry
           hierarchy on its own, replacing 11px uppercase eyebrows that were
           doing heading duty (see the hierarchy pass, 2026-07-13). */
        .section-head {{
            font-size: 16px;
            font-weight: 600;
            color: {COLORS["text_heading"]};
            letter-spacing: -0.01em;
            margin: 18px 0 8px;
        }}
        .nav-section {{
            font-size: 14px;
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
            font-size: 17px;
            font-weight: 600;
            /* Force graphite over Quasar's default primary (purple) label
               color — inactive items read as high-contrast body text, and
               the accent is reserved for the active item below, so the
               selected page stands out instead of every item being purple. */
            color: {COLORS["text_body"]} !important;
        }}
        .nav-btn-line2 {{
            font-size: 13.5px;
            font-weight: 400;
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
            font-size: 21px !important;
            color: {COLORS["text_secondary"]} !important;
        }}
        .nav-btn.active .nav-icon {{
            color: {COLORS["accent_strong"]} !important;
        }}
        .nav-chevron {{
            font-size: 18px !important;
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
            font-size: 14.5px !important;
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
    """)


@ui.page("/")
def main_page():
    apply_theme()
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
    state = {"page": "Today", "role": DEFAULT_ROLE_KEY, "expanded": None, "active_tab": None}
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
    content = ui.column().classes("w-full").style(
        "padding: 24px 48px 24px 24px; max-width: 1050px; margin: 0 auto; gap: 12px;"
    )

    def render_page():
        content.clear()
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
                    getattr(module, render_fn_name)()
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
        # Accordion: expand the section we're navigating to (collapses any other);
        # single-view pages collapse everything.
        state["expanded"] = section if subs else None
        # Highlight the requested sub-item, or the page's first tab when arriving
        # via the parent (which opens on that first tab).
        state["active_tab"] = (tab or (subs[0] if subs else None))
        # Hand the target page the tab to open on (its tab strip reads this once).
        nav.set_target_tab(tab)
        render_nav()
        render_page()

    def on_tab_change(tab_name):
        # Page → sidebar sync: user switched a tab inside the current page, so
        # move the sidebar's sub-item highlight to match.
        if tab_name and tab_name != state["active_tab"]:
            state["active_tab"] = tab_name
            render_nav()

    def _on_role_change(e):
        state["role"] = e.value
        # If the current page isn't allowed for the newly-selected role, jump
        # to the first page that role can view.
        if not role_can_view(state["role"], state["page"]):
            allowed = [s for s in NAV_SECTIONS if role_can_view(state["role"], s)]
            state["page"] = allowed[0] if allowed else "Today"
        # Re-sync the accordion to whatever page is now active (role gating in
        # render_nav locks the rest).
        _subs = NAV_SUBITEMS.get(state["page"])
        state["expanded"] = state["page"] if _subs else None
        state["active_tab"] = _subs[0] if _subs else None
        render_nav()
        render_page()

    from page_modules_nicegui import nav
    nav.register(go_to, on_tab_change)

    # value=True forces the drawer open on load — without it, NiceGUI/Quasar
    # can default a drawer to closed depending on screen width, which is
    # almost certainly why the sidebar wasn't showing up at all.
    # breakpoint=0 stops Quasar's QDrawer from switching into its "mobile"
    # overlay mode (a dark backdrop over the dimmed page content, like a
    # modal) below a width threshold — without it, the drawer's own two-line
    # nav labels can make the effective layout narrow enough to trigger that
    # mode, which is why the sidebar was rendering as a translucent overlay
    # on top of a grayed-out page instead of docking beside it.
    drawer = ui.left_drawer(value=True).style(
        f"background:{COLORS['sidebar_bg']}; border-right:1px solid {COLORS['border']};"
    ).props("width=280 bordered breakpoint=0")

    with ui.header().style(f"background:{COLORS['sidebar_bg']}; border-bottom:1px solid {COLORS['border']};"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat color=white round")
        ui.label(client.get("name", "")).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']}")
        ui.space()

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
                        "padding:10px 16px;color:#64748B;font-size:12.5px;")
                else:
                    grouped = {}
                    for r in hits:
                        grouped.setdefault(r["type"], []).append(r)
                    for typ, label in _SEARCH_GROUPS.items():
                        grp = grouped.get(typ)
                        if not grp:
                            continue
                        ui.label(f"{label} ({len(grp)})").style(
                            "padding:7px 16px 2px;font-size:10px;letter-spacing:.06em;"
                            "color:#94A3B8;font-weight:700;text-transform:uppercase;")
                        for r in grp:
                            with ui.item(on_click=lambda r=r: _search_go(r)).props("clickable dense"):
                                with ui.item_section():
                                    ui.item_label(r["label"]).style("font-size:13px;font-weight:600;color:#0F172A;")
                                    ui.item_label(r["sublabel"]).props("caption").style("font-size:11px;color:#64748B;")
            smenu.open()

        search.on_value_change(lambda: _run_search())

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
                ui.html(f'<div class="nav-section">{group_label}</div>')
                for section, icon, label, desc in items:
                    subs = NAV_SUBITEMS.get(section)
                    access = role_access_level(state["role"], section)
                    is_active = section == state["page"]
                    is_open = state["expanded"] == section
                    lines = label.split("\n")
                    line1, line2 = lines[0], (lines[1] if len(lines) > 1 else "")
                    cls = "nav-btn w-full" + (" active" if is_active else "")
                    with ui.button(on_click=lambda s=section: go_to(s)).props("flat align=left no-caps").classes(cls) as btn:
                        with ui.row().classes("items-center no-wrap w-full").style("gap:12px;"):
                            ui.icon(icon).classes("nav-icon")
                            with ui.column().classes("gap-0"):
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
                        with ui.column().classes("nav-subwrap w-full gap-0"):
                            for sub in subs:
                                sub_cls = "nav-sub w-full" + (
                                    " active" if (is_active and sub == state["active_tab"]) else "")
                                ui.button(sub, on_click=lambda s=section, t=sub: go_to(s, t)).props(
                                    "flat align=left no-caps dense").classes(sub_cls)

    render_nav()
    render_page()


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


app.on_startup(_kick_off_sec_refresh)
app.on_startup(_kick_off_market_data_refresh)
app.on_startup(_kick_off_peer_watch)
app.on_startup(_kick_off_cache_warm)

ui.run(title=f"{CT('name')} IR Platform", port=8502, reload=False)
