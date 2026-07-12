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

from config.client_config import CT, get_client
from config.theme_tokens import ACTIVE as COLORS

NAV_GROUPS = [
    ("OVERVIEW", [
        ("Today",     "🌅", "Today", "Morning brief · Alerts · Actions due"),
        ("Calendar",  "📅", "Calendar", "Earnings · conferences · NDR trips — every upcoming event, one page"),
        ("Markets",   "📈", "Market Intelligence\nConsensus Estimates", "Consensus · PT tracker · Peer benchmarking"),
    ]),
    ("CORE WORKFLOWS", [
        ("Investors", "👥", "Investor Targeting\nPipeline, NDR & Meetings", "Buy-side intel · NDR planner · Meeting hub · Target database"),
        ("Outreach",  "✉️", "Outreach\nMail Gateway", "Draft, review, and send — analyst and buy-side outreach"),
        ("Earnings",  "📝", "Earnings Cycle\nScript Generation", "Script generation · Prior qtr review · Consensus tracker"),
    ]),
    ("REPORTS & SETTINGS", [
        ("Reports",   "📁", "Reports", "Board report · Investor deck · Reg FD"),
        ("Settings",  "⚙️", "Settings", "Platform configuration · Data sources"),
    ]),
]

# Flat list of section names, derived from NAV_GROUPS — used anywhere the
# grouping doesn't matter (e.g. looking up which module renders a section).
NAV_SECTIONS = [page for _group, items in NAV_GROUPS for page, *_ in items]

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
        .nav-section {{
            font-size: 11px;
            color: {COLORS["text_muted"]};
            text-transform: uppercase;
            letter-spacing: .08em;
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
            font-size: 13.5px;
            font-weight: 600;
        }}
        .nav-btn-line2 {{
            font-size: 10.5px;
            font-weight: 400;
            color: {COLORS["text_muted"]};
        }}
        .nav-btn.active {{
            background: {COLORS["surface_bg"]} !important;
            border-left: 3px solid {COLORS["accent"]} !important;
            color: {COLORS["text_heading"]} !important;
        }}
        .nav-btn.active .nav-btn-line2 {{
            color: {COLORS["text_secondary"]};
        }}
    """)


@ui.page("/")
def main_page():
    apply_theme()
    client = get_client()
    state = {"page": "Today"}
    nav_buttons = {}

    # max-width caps how far content stretches on a wide desktop monitor —
    # without it, the column fills 100% of the space next to the drawer
    # (2000px+ on a wide screen), which pushes anything right-aligned (e.g.
    # a card's edit/delete icons) far from the text it belongs to and makes
    # every line of body text uncomfortably long to read. 1050px keeps
    # rows/cards at a scannable width; margin:0 auto centers the column in
    # the remaining space so it doesn't hug the drawer on the left.
    content = ui.column().classes("w-full").style(
        "padding: 24px 48px 24px 24px; max-width: 1050px; margin: 0 auto;"
    )

    def render_page():
        content.clear()
        for section, btn in nav_buttons.items():
            btn.classes(remove="active", add="active" if section == state["page"] else "")
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
                    ui.label(f"⚠️ {state['page']} failed to load").classes("text-xl font-bold").style(f"color:{COLORS['danger']}")
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

    def go_to(section):
        state["page"] = section
        render_page()

    from page_modules_nicegui import nav
    nav.register(go_to)

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
    ).props("width=240 bordered breakpoint=0")

    with ui.header().style(f"background:{COLORS['sidebar_bg']}; border-bottom:1px solid {COLORS['border']};"):
        ui.button(icon="menu", on_click=drawer.toggle).props("flat color=white round")
        ui.label(client.get("name", "")).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']}")

    with drawer:
        for group_label, items in NAV_GROUPS:
            ui.html(f'<div class="nav-section">{group_label}</div>')
            for section, icon, label, desc in items:
                lines = label.split("\n")
                line1, line2 = lines[0], (lines[1] if len(lines) > 1 else "")
                with ui.button(on_click=lambda s=section: go_to(s)).props("flat align=left no-caps").classes("nav-btn w-full") as btn:
                    with ui.column().classes("gap-0"):
                        ui.label(f"{icon}  {line1}").classes("nav-btn-line1")
                        if line2:
                            ui.label(line2).classes("nav-btn-line2")
                btn.tooltip(desc)
                nav_buttons[section] = btn

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
        try:
            log = await asyncio.to_thread(market_data.refresh_all)
            ok = sum(1 for r in log["results"] if r["ok"])
            print(f"[startup] Market data refresh complete for {ok}/{len(log['results'])} ticker(s).")
        except Exception as e:
            print(f"[startup] Market data refresh failed (non-fatal — cached/stale data will show instead): {e}")

    asyncio.create_task(_run())


app.on_startup(_kick_off_sec_refresh)
app.on_startup(_kick_off_market_data_refresh)

ui.run(title=f"{CT('name')} IR Platform", port=8502, reload=False)
