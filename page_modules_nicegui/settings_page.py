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


def _load_settings():
    return db.load_json("settings.json", {})


def _save_settings(data):
    db.save_json("settings.json", data)


def render_settings_page():
    ui.label("Platform Configuration").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("⚙️ Platform Config")
        t2 = ui.tab("📊 Data Sources")
        t3 = ui.tab("ℹ️ About")
    with ui.tab_panels(tabs, value=t1).classes("w-full"):
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
        ui.notify("✅ Saved.")

    ui.button("💾 Save Configuration", on_click=save).props("color=primary")
    ui.label("Note: this saves platform-level settings to this client's config file. Core earnings-date/quiet-period "
             "values used throughout the rest of the app still come from the client registry "
             "(config/client_config.py) until this is wired all the way through.").style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:6px;")


def _render_data_sources():
    sources = [
        ("✅ IRConnect", "IMAP+SMTP active"),
        ("✅ SEC EDGAR", "8-K/13F monitoring"),
        ("⚠️ FactSet", "Manual — API not connected"),
        ("⚠️ Bloomberg", "Manual — API not connected"),
    ]
    for status, desc in sources:
        clr = "#6BCB77" if "✅" in status else "#FFA040"
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            ui.label(f"{status} — {desc}").style(f"color:{clr};font-weight:600;font-size:13px;")


def _render_about():
    client = get_client()
    ir = CI()
    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(f"{CT('name').upper()} ENTERPRISE IR PLATFORM").style(f"color:{COLORS['text_muted']};font-size:11px;text-transform:uppercase;letter-spacing:.05em;")
        ui.label("Praxis Point IR · v2.0").classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:16px;")
        ui.label(f"Built for {ir.get('name','')}, {ir.get('title','')}, {client.get('name','')} ({client.get('ticker','')}) "
                 "· Praxis Point IR Advisory").style(f"color:{COLORS['text_muted']};font-size:13px;")
