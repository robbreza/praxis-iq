"""
page_modules_nicegui/settings_page.py — Settings (platform config, data
sources, about), NiceGUI version.

The original Settings section of app.py was small (~20 lines) but had
every value hardcoded to USIO specifically (irconnect@usio.com, "Paul
Manley, SVP IR, Usio Inc."). Ported here with those replaced by CI()/CT()
lookups from the active client record, so this page is actually correct
for whichever client is active rather than always saying "USIO" — this is
exactly the kind of hardcoded-name spot HANDOFF.md flagged as needing to
be client-agnostic. Platform Config values are persisted via core.db
(SQLite, key "settings.json") instead of just calling st.success() with
nothing actually saved (the original's save button didn't persist
anything).
"""

from nicegui import ui

from config.client_config import CE, CI, CT, get_client
from config.theme_tokens import ACTIVE as COLORS
from core import db
from page_modules_nicegui import nav


def _load_settings():
    return db.load_json("settings.json", {})


def _save_settings(data):
    db.save_json("settings.json", data)


def render_settings_page():
    ui.label("Platform Configuration").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("Platform Config")
        t2 = ui.tab("Data Sources")
        t3 = ui.tab("About")
    _panels = ui.tab_panels(tabs, value=nav.consume_target_tab() or t1).classes("w-full")
    _panels.on_value_change(lambda e: nav.tab_changed(e.value))
    with _panels:
        with ui.tab_panel(t1):
            _render_platform_config()
        with ui.tab_panel(t2):
            _render_data_sources()
        with ui.tab_panel(t3):
            _render_about()


def _render_platform_config():
    settings = _load_settings()
    ir = CI()
    earnings = CE()

    with ui.row().classes("w-full gap-4"):
        with ui.column().classes("flex-1"):
            irconnect_in = ui.input("IRConnect email", value=settings.get("irconnect_email", ir.get("irconnect", ""))).classes("w-full")
            smtp_in = ui.input("SMTP", value=settings.get("smtp", "smtpout.secureserver.net:465")).classes("w-full")
        with ui.column().classes("flex-1"):
            earnings_date_in = ui.input("Next earnings date (YYYY-MM-DD)", value=settings.get("earnings_date", earnings.get("earnings_date", ""))).classes("w-full")
            quiet_start_in = ui.input("Quiet period start (YYYY-MM-DD)", value=settings.get("quiet_start", earnings.get("quiet_start", ""))).classes("w-full")

    def save():
        _save_settings({
            "irconnect_email": irconnect_in.value, "smtp": smtp_in.value,
            "earnings_date": earnings_date_in.value, "quiet_start": quiet_start_in.value,
        })
        ui.notify("Saved.")

    ui.button("Save Configuration", on_click=save).props("color=primary")
    ui.label("Note: this saves platform-level settings to this client's config file. Core earnings-date/quiet-period "
             "values used throughout the rest of the app still come from the client registry "
             "(config/client_config.py) until this is wired all the way through.").style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:6px;")


def _render_routing_key():
    """OpenRouteService API key for real NDR itinerary driving distances/times.
    Stored in settings.json → 'routing_api_key'; core.routing reads it (or the
    ORS_API_KEY env var) and the itinerary falls back to offline estimates when
    it's blank. A Test button geocodes + routes a sample so the user gets
    immediate confirmation the key works."""
    import asyncio
    from core import routing

    settings = _load_settings()
    configured = bool((settings.get("routing_api_key") or "").strip())

    ui.markdown("---")
    with ui.row().classes("items-center gap-2").style("margin-top:4px;"):
        ui.icon("check_circle" if configured else "error_outline").style(
            f"color:{'#15803D' if configured else '#B45309'};font-size:18px;")
        ui.label("NDR routing — OpenRouteService (driving miles & time)").style(
            f"color:{COLORS['text_heading']};font-weight:700;font-size:14px;")
    ui.label("Turns the NDR itinerary's travel legs from straight-line estimates into real "
             "routed driving distance and time. Free key at openrouteservice.org — no credit "
             "card. Leave blank to keep offline estimates.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    key_in = ui.input("OpenRouteService API key",
                      value=settings.get("routing_api_key", ""),
                      password=True, placeholder="paste your ORS token").classes("w-full").props(
        "autocomplete=off")
    result_lbl = ui.label("").style("font-size:12px;margin-top:2px;")

    def save():
        s = _load_settings()
        s["routing_api_key"] = (key_in.value or "").strip()
        _save_settings(s)
        ui.notify("Routing key saved." if s["routing_api_key"] else "Routing key cleared — using offline estimates.")

    async def test():
        # Persist first so routing.test() reads the just-typed key.
        save()
        result_lbl.set_text("Testing…")
        result_lbl.style(f"color:{COLORS['text_muted']};")
        try:
            ok, msg = await asyncio.to_thread(routing.test)
        except Exception as e:
            ok, msg = False, f"Test error: {e}"
        result_lbl.set_text(("✓ " if ok else "✗ ") + msg)
        result_lbl.style(f"color:{'#15803D' if ok else '#B45309'};font-size:12px;margin-top:2px;")

    with ui.row().classes("gap-2"):
        ui.button("Save key", on_click=save).props("color=primary dense")
        ui.button("Test", on_click=test).props("outline dense")


def _render_lexicon_licence():
    """Loughran-McDonald licence gate. The dictionary is free for academic
    research only; Praxis Point IR is commercial, so the hedging analytics stay
    switched OFF until terms are agreed. Exposed here rather than as a code edit
    so turning it on is an explicit, auditable decision by a person who knows the
    licence position — not something that happens quietly in a deploy."""
    from core import lexicon

    settings = _load_settings()
    current = settings.get("lm_license") or "unlicensed"

    ui.markdown("---")
    ok = current in ("commercial", "academic")
    with ui.row().classes("items-center gap-2").style("margin-top:4px;"):
        ui.icon("check_circle" if ok else "gpp_maybe").style(
            f"color:{'#15803D' if ok else '#B45309'};font-size:18px;")
        ui.label("Script hedging analytics — Loughran-McDonald dictionary").style(
            f"color:{COLORS['text_heading']};font-weight:700;font-size:14px;")
    ui.label("Measures whether the script commits or qualifies (Weak-Modal + Uncertainty vs "
             "Strong-Modal), using the finance-specific dictionary from Loughran & McDonald (2011), "
             "J. Finance 66(1). General sentiment lists misread financial prose — they score "
             "'liability', 'cost', 'tax' and 'capital' as negative when they're neutral accounting "
             "vocabulary.").style(f"color:{COLORS['text_muted']};font-size:12px;")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid #B45309;"
            "border-left:3px solid #B45309;padding:8px 10px;margin-top:4px;"):
        ui.label("Licence required before this ships to a client").style(
            "color:#B45309;font-size:12px;font-weight:700;")
        ui.label("The dictionary is free for ACADEMIC research. Commercial use requires a licence "
                 "(loughranmcdonald@gmail.com). Praxis Point IR is commercial. Leave this "
                 "Unlicensed until terms are agreed — the analytics stay disabled and nothing "
                 "derived from the dictionary can reach a client deliverable.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")

    sel = ui.select({"unlicensed": "Unlicensed — analytics disabled (default)",
                     "commercial": "Commercial licence agreed",
                     "academic": "Academic use only"},
                    value=current, label="Licence status").props("dense outlined").classes("w-full")
    status = ui.label("").style("font-size:11.5px;margin-top:2px;")

    def save():
        s = _load_settings()
        if sel.value == "unlicensed":
            s.pop("lm_license", None)
        else:
            s["lm_license"] = sel.value
        _save_settings(s)
        avail = lexicon.available()
        status.set_text(("✓ Hedging analytics ENABLED — " + sel.value) if avail
                        else "Analytics disabled. (Unlicensed, or the dictionary file is missing "
                             "from vendor/loughran_mcdonald/.)")
        status.style(f"color:{'#15803D' if avail else COLORS['text_muted']};font-size:11.5px;")
        ui.notify("Licence status saved.")

    ui.button("Save licence status", on_click=save).props("color=primary dense")


def _render_zoom_creds():
    """Zoom Server-to-Server OAuth credentials so the NDR planner can auto-create
    Zoom meetings and fill the join link. Stored in settings.json; core.zoom_meetings
    reads them (or ZOOM_* env vars). Blank → the planner keeps the paste field."""
    import asyncio
    from core import zoom_meetings

    settings = _load_settings()
    configured = all((settings.get(k) or "").strip()
                     for k in ("zoom_account_id", "zoom_client_id", "zoom_client_secret"))

    ui.markdown("---")
    with ui.row().classes("items-center gap-2").style("margin-top:4px;"):
        ui.icon("check_circle" if configured else "error_outline").style(
            f"color:{'#15803D' if configured else '#B45309'};font-size:18px;")
        ui.label("Zoom meetings — auto-create join links").style(
            f"color:{COLORS['text_heading']};font-weight:700;font-size:14px;")
    ui.label("Server-to-Server OAuth app credentials (free with your Zoom account). Lets "
             "'Create Zoom meeting' on a virtual NDR stop mint the join link automatically. "
             "Leave blank to keep pasting links by hand.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    acct_in = ui.input("Account ID", value=settings.get("zoom_account_id", "")).classes("w-full").props("autocomplete=off")
    cid_in = ui.input("Client ID", value=settings.get("zoom_client_id", "")).classes("w-full").props("autocomplete=off")
    sec_in = ui.input("Client Secret", value=settings.get("zoom_client_secret", ""),
                      password=True).classes("w-full").props("autocomplete=off")
    result_lbl = ui.label("").style("font-size:12px;margin-top:2px;")

    def save():
        s = _load_settings()
        s["zoom_account_id"] = (acct_in.value or "").strip()
        s["zoom_client_id"] = (cid_in.value or "").strip()
        s["zoom_client_secret"] = (sec_in.value or "").strip()
        _save_settings(s)
        ui.notify("Zoom credentials saved." if all([s["zoom_account_id"], s["zoom_client_id"], s["zoom_client_secret"]])
                  else "Zoom credentials cleared.")

    async def test():
        save()
        result_lbl.set_text("Testing…")
        result_lbl.style(f"color:{COLORS['text_muted']};font-size:12px;margin-top:2px;")
        try:
            ok, msg = await asyncio.to_thread(zoom_meetings.test)
        except Exception as e:
            ok, msg = False, f"Test error: {e}"
        result_lbl.set_text(("✓ " if ok else "✗ ") + msg)
        result_lbl.style(f"color:{'#15803D' if ok else '#B45309'};font-size:12px;margin-top:2px;")

    with ui.row().classes("gap-2"):
        ui.button("Save Zoom credentials", on_click=save).props("color=primary dense")
        ui.button("Test", on_click=test).props("outline dense")


def _render_data_sources():
    sources = [
        ("IRConnect", "IMAP+SMTP active", True),
        ("SEC EDGAR", "8-K/13F monitoring", True),
        ("FactSet", "Manual — API not connected", False),
        ("Bloomberg", "Manual — API not connected", False),
    ]
    for name, desc, ok in sources:
        clr = "#15803D" if ok else "#B45309"
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("items-center gap-2"):
                ui.icon("check_circle" if ok else "error_outline").style(f"color:{clr};font-size:18px;")
                ui.label(f"{name} — {desc}").style(f"color:{clr};font-weight:600;font-size:13px;")

    _render_routing_key()
    _render_zoom_creds()
    _render_lexicon_licence()

    # ── Data pulls ──────────────────────────────────────────────────────────
    # The single, deliberate place to kick off an expensive network refresh, so
    # navigating tabs elsewhere never triggers one. Each runs in a worker thread
    # (asyncio.to_thread) so the UI stays responsive and the toast shows
    # immediately. The results land in core.db's cache, so reopening the relevant
    # tab shows fresh data.
    import asyncio
    from core import sec_filings, market_data

    ui.markdown("---")
    ui.label("Data pulls").style(
        f"color:{COLORS['text_heading']};font-weight:700;font-size:14px;margin-top:4px;")
    ui.label("Manual refreshes that hit the network. Consolidated here so opening a tab never kicks off a pull.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    async def _pull_full_universe():
        ui.notify("Refreshing from SEC EDGAR — ~100MB quarterly 13F bulk (complete, by CUSIP) + 13D/13G. "
                  "1–3 minutes.", type="warning")
        try:
            # holder_pull_tickers = peer universe + analyst coverage network. One
            # scan covers both; the coverage tickers feed the prospecting pipeline
            # without ever entering the valuation peer set.
            await asyncio.to_thread(sec_filings.refresh_13f_bulk_all,
                                    sec_filings.holder_pull_tickers())
            await asyncio.to_thread(sec_filings.refresh_all, False, True)
            ui.notify("SEC EDGAR refresh complete — reopen Investor Targeting to see fresh holders/prospects.",
                      type="positive")
        except Exception as e:
            ui.notify(f"Refresh failed: {e}", type="negative")

    async def _pull_market():
        ui.notify("Refreshing market prices & fundamentals from Yahoo…")
        try:
            log = await asyncio.to_thread(market_data.refresh_all)
            ok = sum(1 for r in log["results"] if r["ok"])
            ui.notify(f"Market data refreshed ({ok}/{len(log['results'])} tickers).", type="positive")
        except Exception as e:
            ui.notify(f"Refresh failed: {e}", type="negative")

    async def _pull_peer_watch():
        ui.notify("Refreshing peer watch — filings + the rolling 7-day news window…")
        try:
            from core import news_feed, peer_watch
            await asyncio.to_thread(peer_watch.refresh)
            n = await asyncio.to_thread(news_feed.refresh)
            ui.notify(f"Peer watch refreshed · {len(n)} news article(s) in the window.", type="positive")
        except Exception as e:
            ui.notify(f"Refresh failed: {e}", type="negative")

    async def _pull_13dg():
        ui.notify("Refreshing 13D/13G ownership-stake filings from SEC EDGAR…")
        try:
            await asyncio.to_thread(sec_filings.refresh_all, False, True)
            ui.notify("13D/13G refresh complete.", type="positive")
        except Exception as e:
            ui.notify(f"Refresh failed: {e}", type="negative")

    async def _pull_addresses():
        # Fill the fund address book from SEC business addresses BY CIK — exact,
        # no name-matching — for every cached 13F filer. Feeds NDR itinerary
        # routing. Manual/seed entries are preserved.
        ui.notify("Fetching fund office addresses from SEC EDGAR (by CIK)…")
        try:
            from core import fund_addresses

            def _run():
                pairs, seen = [], set()
                # tracked_tickers() yields (ticker, name) tuples.
                for tk, _name in sec_filings.tracked_tickers():
                    for h in (sec_filings.get_cached_13f_holders(tk).get("holders", []) or []):
                        name, cik = (h.get("filer") or "").strip(), h.get("cik")
                        if name and cik and cik not in seen:
                            seen.add(cik)
                            pairs.append((name, cik))
                return fund_addresses.refresh_from_sec(pairs)

            res = await asyncio.to_thread(_run)
            ui.notify(f"Address book updated · {res['updated']} fetched, {res['skipped']} skipped "
                      "(already set or no SEC address).", type="positive")
        except Exception as e:
            ui.notify(f"Address pull failed: {e}", type="negative")

    def _pull_row(label, desc, handler, primary=False):
        with ui.row().classes("w-full items-center justify-between no-wrap").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;"
                "padding:8px 12px;margin-top:4px;"):
            with ui.column().classes("gap-0").style("flex:1;min-width:0;"):
                ui.label(label).style(f"color:{COLORS['text_body']};font-size:13px;font-weight:600;")
                ui.label(desc).style(f"color:{COLORS['text_muted']};font-size:11px;")
            ui.button("Run", on_click=handler).props("color=primary dense" if primary else "flat dense")

    _pull_row("Full investor universe (SEC 13F, complete by CUSIP)",
              "~100MB bulk download · 1–3 min · exact, complete holder lists + 13D/13G. Feeds Peer Prospects.",
              _pull_full_universe, primary=True)
    _pull_row("Market prices & fundamentals",
              "Yahoo snapshots for the tracked universe · seconds. Feeds Today + benchmarking.", _pull_market)
    _pull_row("Peer watch (SEC filings + news)",
              "Recent peer 8-K/10-Q/10-K filings and the rolling 7-day news window. Feeds Today's Peer Watch.",
              _pull_peer_watch)
    _pull_row("13D/13G only", "5%+ ownership-stake filings — the fast, targeted refresh.", _pull_13dg)
    _pull_row("Fund office addresses (SEC EDGAR, by CIK)",
              "Authoritative business address for every cached 13F filer — exact match on CIK, no "
              "name guessing. Feeds NDR itinerary driving routes.", _pull_addresses)


def _render_about():
    client = get_client()
    ir = CI()
    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(f"{CT('name').upper()} ENTERPRISE IR PLATFORM").style(f"color:{COLORS['text_muted']};font-size:11px;text-transform:uppercase;letter-spacing:.05em;")
        ui.label("Praxis Point IR · v2.0").classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:16px;")
        ui.label(f"Built for {ir.get('name','')}, {ir.get('title','')}, {client.get('name','')} ({client.get('ticker','')}) "
                 "· Praxis Point IR Advisory").style(f"color:{COLORS['text_muted']};font-size:13px;")
