"""
page_modules_nicegui/calendar_page.py — IR Conference & Events Calendar,
NiceGUI version. This is the proof-of-concept port validating that the
core patterns (data load/save, cards, edit dialogs, forms, notifications)
translate cleanly from Streamlit to NiceGUI before the bigger pages
(Investors, Earnings) get tackled.

Covered in this pass: summary metrics, deadline alerts, event list with
edit (dialog) and delete, add-event form, CSV export, client-scoped storage
(via core.db/SQLite, key "ir_conference_calendar.csv" — core.db imports
any pre-existing ir_conference_calendar.csv file from the earlier
client_data_path()-based version on first read, so switching between the
old and new app mid-migration doesn't lose data).

Not yet ported from the original (flagged here, not silently dropped):
- List vs. Timeline view toggle (this version only shows the list)
- Type/status/priority filter controls
- The "paste from email" and "scan transcript" AI-assisted event extraction
  tabs
- The NDR Trips section (reads outputs/ndr_trips.json)
These can be added in a follow-up pass — the data layer and page structure
below make that straightforward to slot in.
"""

from datetime import datetime, timedelta

import pandas as pd
from nicegui import ui

from config.client_config import get_active_client_id
from config.theme_tokens import ACTIVE as COLORS
from core import db
from data.seed.conferences import get_seed_conferences

STATUS_OPTIONS = [
    "Confirmed", "Invited — pending confirmation", "Scheduled",
    "Evaluating", "Not yet contacted", "Declined", "Completed",
]


def _load_conferences(key):
    """Returns (events, was_freshly_seeded) — the caller uses the second
    value to decide whether to persist the seed data immediately, same as
    the original writing the CSV to disk the first time it ran."""
    events = db.load_json(key, default=None)
    if events is not None:
        return events, False
    return get_seed_conferences(get_active_client_id()), True


def _save_conferences(key, events):
    db.save_json(key, events)


def _metric_card(label, value):
    with ui.card().classes("flex-1").style(
        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
        f"border-radius:10px;padding:16px;"
    ):
        ui.label(str(value)).classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']}")
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:12px;text-transform:uppercase;letter-spacing:.05em;")


def render_calendar_page():
    conf_path = "ir_conference_calendar.csv"
    events, was_freshly_seeded = _load_conferences(conf_path)
    if was_freshly_seeded:
        _save_conferences(conf_path, events)

    ui.html(
        "<div class='section-eyebrow'>CALENDAR</div>"
        "<div class='section-title'>Earnings &middot; Conferences &middot; NDR Trips</div>"
    )

    today = datetime.now().date()
    upcoming = [e for e in events if datetime.strptime(e["Date"], "%Y-%m-%d").date() >= today]
    deadlines = [
        e for e in upcoming if e.get("Deadline")
        and datetime.strptime(e["Deadline"], "%Y-%m-%d").date() >= today
        and (datetime.strptime(e["Deadline"], "%Y-%m-%d").date() - today).days <= 30
    ]
    high_pri = [e for e in upcoming if e.get("Priority") == "High"]

    with ui.row().classes("w-full gap-4"):
        _metric_card("Total events tracked", len(events))
        _metric_card("Upcoming", len(upcoming))
        _metric_card("Deadlines in 30 days", len(deadlines))
        _metric_card("High priority", len(high_pri))

    if deadlines:
        ui.label("⚠️ Registration Deadlines Coming Up").classes("text-lg font-bold").style(
            f"margin-top:20px;color:{COLORS['text_heading']}"
        )
        for e in sorted(deadlines, key=lambda x: x["Deadline"]):
            days_left = (datetime.strptime(e["Deadline"], "%Y-%m-%d").date() - today).days
            color = COLORS["danger"] if days_left <= 7 else COLORS["warning"]
            with ui.row().classes("items-center w-full").style(
                f"border:1px solid {color};border-radius:8px;padding:8px 14px;margin-bottom:6px;"
            ):
                ui.label(f"{e['Event']} · Deadline {e['Deadline']} ({days_left}d) · {e['Status']}").style(f"color:{color}")

    ui.label(f"{len(events)} events on file").classes("text-sm").style(
        f"color:{COLORS['text_muted']};margin-top:20px;"
    )

    events_container = ui.column().classes("w-full gap-2")

    def open_edit_dialog(ev):
        with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:400px;"):
            ui.label(ev["Event"]).classes("text-lg font-bold")
            status_sel = ui.select(STATUS_OPTIONS, value=ev["Status"], label="Status").classes("w-full")
            notes_input = ui.textarea("Notes", value=ev.get("Notes", "")).classes("w-full")
            attend_input = ui.input("Attending", value=ev.get("Attending", "TBD")).classes("w-full")

            def save():
                ev["Status"] = status_sel.value
                ev["Notes"] = notes_input.value
                ev["Attending"] = attend_input.value
                _save_conferences(conf_path, events)
                dialog.close()
                refresh_events()
                ui.notify("Saved")

            with ui.row():
                ui.button("Save", on_click=save).props("color=primary")
                ui.button("Cancel", on_click=dialog.close).props("flat")
        dialog.open()

    def delete_event(ev):
        events.remove(ev)
        _save_conferences(conf_path, events)
        refresh_events()
        ui.notify(f"Deleted '{ev['Event']}'")

    def refresh_events():
        events_container.clear()
        with events_container:
            for ev in sorted(events, key=lambda x: x["Date"]):
                with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:10px;"
                ):
                    # Title and its edit/delete icons share one tight row
                    # (gap, not justify-between) so the icons sit right next
                    # to the event they act on instead of pinned to the far
                    # right of a full-width row — the detail lines below
                    # still get the full card width to themselves.
                    with ui.column().classes("w-full gap-0"):
                        with ui.row().classes("items-center gap-1"):
                            ui.label(ev["Event"]).classes("font-bold").style(f"color:{COLORS['text_heading']}")
                            ui.button(icon="edit", on_click=lambda e=ev: open_edit_dialog(e)).props("flat round dense size=sm")
                            ui.button(icon="delete", on_click=lambda e=ev: delete_event(e)).props("flat round dense size=sm")
                        ui.label(f"{ev['Date']} · {ev['Location']} · {ev['Organizer']}").style(
                            f"color:{COLORS['text_muted']};font-size:12px;"
                        )
                        ui.label(f"Status: {ev['Status']} · Attending: {ev.get('Attending','TBD')}").style(
                            f"color:{COLORS['text_secondary']};font-size:12px;"
                        )
                        if ev.get("Notes"):
                            ui.label(ev["Notes"]).style(f"color:{COLORS['text_muted']};font-size:12px;")

    refresh_events()

    with ui.expansion("➕ Add Event to Calendar").classes("w-full").style("margin-top:20px;"):
        with ui.row().classes("w-full gap-4"):
            name_in = ui.input("Event name *").classes("flex-1")
            type_sel = ui.select(
                ["Investor Conference", "Earnings", "Industry Conference", "Roadshow", "Other"],
                value="Investor Conference", label="Type",
            ).classes("flex-1")
            priority_sel = ui.select(["High", "Medium", "Low"], value="Medium", label="Priority").classes("flex-1")
        with ui.row().classes("w-full gap-4"):
            date_in = ui.input("Event date (YYYY-MM-DD)", value=str(today + timedelta(days=30))).classes("flex-1")
            deadline_in = ui.input("Registration deadline (YYYY-MM-DD)", value=str(today + timedelta(days=14))).classes("flex-1")
            status_sel2 = ui.select(
                ["Evaluating", "Invited — pending confirmation", "Confirmed", "Not yet contacted"],
                value="Evaluating", label="Status",
            ).classes("flex-1")
        with ui.row().classes("w-full gap-4"):
            location_in = ui.input("Location").classes("flex-1")
            organizer_in = ui.input("Organizer").classes("flex-1")
            attending_in = ui.input("Attending", value="TBD").classes("flex-1")
        notes_in = ui.textarea("Notes / logistics").classes("w-full")

        def add_event():
            if not name_in.value:
                ui.notify("Event name is required", type="warning")
                return
            events.append({
                "Event": name_in.value, "Type": type_sel.value, "Date": date_in.value,
                "Location": location_in.value, "Organizer": organizer_in.value,
                "Status": status_sel2.value, "Deadline": deadline_in.value,
                "Notes": notes_in.value, "Source": "Manual entry",
                "Attending": attending_in.value, "Priority": priority_sel.value,
            })
            _save_conferences(conf_path, events)
            refresh_events()
            ui.notify(f"'{name_in.value}' added to calendar")
            name_in.value = ""

        ui.button("📅 Add to Calendar", on_click=add_event).props("color=primary").style("margin-top:8px;")

    def export_csv():
        df = pd.DataFrame(events)
        ui.download(df.to_csv(index=False).encode(), f"conference_calendar_{datetime.now().strftime('%Y%m%d')}.csv")

    with ui.row().classes("w-full justify-between items-center").style("margin-top:20px;"):
        ui.button("⬇️ Export calendar as CSV", on_click=export_csv).props("flat")
        ui.label("📁 Saved · updates persist across restarts").style(
            f"color:{COLORS['text_muted']};font-size:12px;"
        )
