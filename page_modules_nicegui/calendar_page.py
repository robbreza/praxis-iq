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
from core import db, ui_context
from data.seed.conferences import get_seed_conferences

STATUS_OPTIONS = [
    "Confirmed", "Needs to be Scheduled", "Invited — pending confirmation", "Scheduled",
    "Evaluating", "Not yet contacted", "Declined", "Completed",
]


def _attendee_options(client_id=None):
    """The client's actual roster (IR + named executives) for the Attending
    picker — real people, not a generic 'Management + IR' string."""
    from config.client_config import role_roster
    return [e["name"] for e in role_roster(client_id) if e.get("name")]


def _parse_attending(val):
    """Split a stored Attending string ('Louis Hoch, Michael White', or a legacy
    'Management + IR') into a list for the multi-select's initial value."""
    import re
    if not val or str(val).strip().upper() in ("TBD", ""):
        return []
    return [p.strip() for p in re.split(r"[,+/;]", str(val)) if p.strip()]


def _attend_select(current="", client_id=None, cls="w-full"):
    """A chips multi-select of the roster, pre-filled from `current`, that also
    lets you type a guest name not on the roster (new_value_mode add-unique)."""
    opts = _attendee_options(client_id)
    vals = _parse_attending(current)
    for v in vals:                       # keep any names/guests not in the roster
        if v not in opts:
            opts.append(v)
    return ui.select(opts, multiple=True, value=vals, label="Attending",
                     new_value_mode="add-unique").props("use-chips").classes(cls)


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


def _metric_card(label, value, hint, active, on_click):
    """A clickable summary card. Clicking it filters the event list below to
    the set it counts; the active one is highlighted with an accent edge so
    the number is connected to real content instead of being a static stat."""
    border = COLORS["accent"] if active else COLORS["border"]
    bg = COLORS["surface_hover_bg"] if active else COLORS["surface_bg"]
    edge = COLORS["accent"] if active else "transparent"
    card = ui.card().classes("flex-1 cursor-pointer").style(
        f"background:{bg};border:1px solid {border};border-left:4px solid {edge};"
        f"border-radius:8px;padding:16px;"
    )
    with card:
        ui.label(str(value)).classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']}")
        ui.label(label).style(f"color:{COLORS['text_secondary']};font-size:12px;font-weight:600;")
        ui.label(hint).style(f"color:{COLORS['text_muted']};font-size:11px;")
    card.on("click", on_click)
    return card


def _date_field(label, default):
    """Text field with a calendar-picker popup, still hand-editable. Value is
    a 'YYYY-MM-DD' string, matching how events are stored and parsed."""
    inp = ui.input(label, value=default).classes("flex-1")
    with inp:
        with ui.menu().props("no-parent-event") as menu:
            ui.date(value=default).bind_value(inp).props("today-btn")
        with inp.add_slot("append"):
            ui.icon("edit_calendar").on("click", menu.open).classes("cursor-pointer")
    return inp


def render_calendar_page():
    conf_path = "ir_conference_calendar.csv"
    events, was_freshly_seeded = _load_conferences(conf_path)
    if was_freshly_seeded:
        _save_conferences(conf_path, events)

    ui.html(
        "<div class='section-eyebrow'>CALENDAR</div>"
        "<div class='section-title'>Earnings &middot; Conferences &middot; NDR Trips</div>"
    )

    # RBAC: view-only roles (e.g. Legal) can browse the calendar and export it
    # but not add/edit/delete events. Mutating controls below call
    # ui_context.is_read_only() directly rather than a captured local.
    if ui_context.is_read_only():
        ui_context.read_only_banner(ui)

    today = datetime.now().date()

    # Compute-on-demand so the counts and filters stay correct after an event
    # is added or deleted (no stale snapshot from page-render time).
    def _upcoming():
        return [e for e in events if datetime.strptime(e["Date"], "%Y-%m-%d").date() >= today]

    def _deadlines():
        out = []
        for e in _upcoming():
            if e.get("Deadline"):
                dl = datetime.strptime(e["Deadline"], "%Y-%m-%d").date()
                if dl >= today and (dl - today).days <= 30:
                    out.append(e)
        return out

    def _high():
        return [e for e in _upcoming() if e.get("Priority") == "High"]

    # Each metric card is a clickable filter over the event list below.
    _filter = {"mode": "all"}
    _filter_sets = {
        "all": ("Total events tracked", "Everything on the calendar", lambda: events),
        "upcoming": ("Upcoming", "Events still ahead", _upcoming),
        "deadlines": ("Deadlines in 30 days", "Register before these close", _deadlines),
        "high": ("High priority", "Flagged must-attend", _high),
    }
    cards_row = ui.row().classes("w-full gap-4")

    def set_filter(mode):
        _filter["mode"] = mode
        render_cards()
        render_view()

    def render_cards():
        cards_row.clear()
        counts = {"all": len(events), "upcoming": len(_upcoming()),
                  "deadlines": len(_deadlines()), "high": len(_high())}
        with cards_row:
            for mode, (label, hint, _getter) in _filter_sets.items():
                _metric_card(label, counts[mode], hint, _filter["mode"] == mode,
                             lambda m=mode: set_filter(m))

    if _deadlines():
        ui.label("Registration Deadlines Coming Up").classes("text-lg font-bold").style(
            f"margin-top:20px;color:{COLORS['text_heading']}"
        )
        for e in sorted(_deadlines(), key=lambda x: x["Deadline"]):
            days_left = (datetime.strptime(e["Deadline"], "%Y-%m-%d").date() - today).days
            color = COLORS["danger"] if days_left <= 7 else COLORS["warning"]
            with ui.row().classes("items-center w-full").style(
                f"border:1px solid {color};border-radius:8px;padding:8px 14px;margin-bottom:6px;"
            ):
                ui.label(f"{e['Event']} · Deadline {e['Deadline']} ({days_left}d) · {e['Status']}").style(f"color:{color}")

    # View state (list vs. calendar) and calendar-month navigation.
    _view = {"mode": "list"}
    _cal = {"month": today.replace(day=1)}

    def open_edit_dialog(ev):
        with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:400px;"):
            ui.label(ev["Event"]).classes("text-lg font-bold")
            status_sel = ui.select(STATUS_OPTIONS, value=ev["Status"], label="Status").classes("w-full")
            notes_input = ui.textarea("Notes", value=ev.get("Notes", "")).classes("w-full")
            attend_input = _attend_select(ev.get("Attending", ""))

            def save():
                ev["Status"] = status_sel.value
                ev["Notes"] = notes_input.value
                ev["Attending"] = ", ".join(attend_input.value or [])
                _save_conferences(conf_path, events)
                dialog.close()
                render_view()
                ui.notify("Saved")

            with ui.row():
                ui.button("Save", on_click=save).props("color=primary")
                ui.button("Cancel", on_click=dialog.close).props("flat")
        dialog.open()

    def delete_event(ev):
        events.remove(ev)
        _save_conferences(conf_path, events)
        render_cards()
        render_view()
        ui.notify(f"Deleted '{ev['Event']}'")

    def _shift_month(delta):
        m = _cal["month"]
        idx = m.month - 1 + delta
        _cal["month"] = m.replace(year=m.year + idx // 12, month=idx % 12 + 1, day=1)
        render_view()

    def _render_list(shown, label):
        clear_hint = "" if _filter["mode"] == "all" else "  ·  click Total events tracked to clear"
        ui.label(f"Showing {len(shown)} event(s) — {label}{clear_hint}").classes("text-sm").style(
            f"color:{COLORS['text_muted']};"
        )
        if not shown:
            ui.label("No events match this filter.").style(f"color:{COLORS['text_muted']};font-size:13px;")
        for ev in shown:
            is_high = ev.get("Priority") == "High"
            caption = f"{ev['Date']} · {ev.get('Location','—')} · {ev['Status']}" + (
                " · High priority" if is_high else "")
            with ui.expansion(ev["Event"], caption=caption).classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;"
            ):
                ui.label(f"Type: {ev.get('Type','—')}  ·  Organizer: {ev.get('Organizer','—')}").style(
                    f"color:{COLORS['text_secondary']};font-size:13px;")
                ui.label(f"Attending: {ev.get('Attending','TBD')}").style(
                    f"color:{COLORS['text_secondary']};font-size:13px;")
                if ev.get("Deadline"):
                    ui.label(f"Registration deadline: {ev['Deadline']}").style(
                        f"color:{COLORS['text_secondary']};font-size:13px;")
                if ev.get("Notes"):
                    ui.label(ev["Notes"]).style(
                        f"color:{COLORS['text_muted']};font-size:12px;margin-top:4px;")
                if not ui_context.is_read_only():
                    with ui.row().classes("gap-2").style("margin-top:8px;"):
                        ui.button("Edit", icon="edit",
                                  on_click=lambda e=ev: open_edit_dialog(e)).props("flat dense")
                        ui.button("Delete", icon="delete",
                                  on_click=lambda e=ev: delete_event(e)).props("flat dense").style(
                            f"color:{COLORS['danger']};")

    def _day_cell(m, day, day_events):
        is_today = (m.year, m.month, day) == (today.year, today.month, today.day)
        bclr = COLORS["accent"] if is_today else COLORS["border"]
        with ui.element("div").style(
            f"border:1px solid {bclr};border-radius:6px;padding:4px 5px;min-height:82px;"
            f"background:{COLORS['surface_bg']};overflow:hidden;"
        ):
            ui.label(str(day)).style(
                f"color:{COLORS['text_heading'] if is_today else COLORS['text_secondary']};"
                f"font-size:12px;font-weight:{'700' if is_today else '500'};")
            for ev in day_events[:3]:
                clr = COLORS["danger"] if ev.get("Priority") == "High" else COLORS["accent"]
                chip = ui.label(ev["Event"]).classes("cursor-pointer").style(
                    f"background:{clr}22;color:{clr};font-size:10px;font-weight:600;border-radius:6px;"
                    f"padding:1px 5px;margin-top:2px;white-space:nowrap;overflow:hidden;"
                    f"text-overflow:ellipsis;max-width:100%;")
                chip.tooltip(f"{ev['Event']} · {ev.get('Status','')}")
                chip.on("click", lambda e=ev: open_edit_dialog(e))
            if len(day_events) > 3:
                ui.label(f"+{len(day_events) - 3} more").style(
                    f"color:{COLORS['text_muted']};font-size:10px;margin-top:2px;")

    def _render_calendar(shown):
        import calendar as _calmod
        m = _cal["month"]
        by_day = {}
        for ev in shown:
            try:
                d = datetime.strptime(ev["Date"], "%Y-%m-%d").date()
            except Exception:
                continue
            if d.year == m.year and d.month == m.month:
                by_day.setdefault(d.day, []).append(ev)
        with ui.row().classes("w-full items-center justify-between").style("margin-bottom:8px;"):
            ui.button(icon="chevron_left", on_click=lambda: _shift_month(-1)).props("flat dense round")
            ui.label(f"{_calmod.month_name[m.month]} {m.year}").classes("text-lg font-bold").style(
                f"color:{COLORS['text_heading']}")
            ui.button(icon="chevron_right", on_click=lambda: _shift_month(1)).props("flat dense round")
        with ui.grid(columns=7).classes("w-full gap-1"):
            for wd in ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]:
                ui.label(wd).style(
                    f"color:{COLORS['text_muted']};font-size:11px;font-weight:700;text-align:center;")
            for week in _calmod.Calendar(firstweekday=6).monthdayscalendar(m.year, m.month):
                for day in week:
                    if day == 0:
                        ui.element("div")
                    else:
                        _day_cell(m, day, by_day.get(day, []))
        if not shown:
            ui.label("No events match this filter.").style(
                f"color:{COLORS['text_muted']};font-size:13px;margin-top:6px;")

    def render_view():
        view_body.clear()
        label, _hint, getter = _filter_sets[_filter["mode"]]
        shown = sorted(getter(), key=lambda x: x["Date"])
        with view_body:
            if _view["mode"] == "calendar":
                _render_calendar(shown)
            else:
                _render_list(shown, label)

    with ui.row().classes("items-center gap-3").style("margin-top:16px;"):
        ui.label("View").style(f"color:{COLORS['text_muted']};font-size:12px;font-weight:600;")
        _view_toggle = ui.toggle({"list": "List", "calendar": "Calendar"}, value="list")

        def _on_view():
            _view["mode"] = _view_toggle.value
            render_view()

        _view_toggle.on_value_change(_on_view)

    view_body = ui.column().classes("w-full gap-2").style("margin-top:8px;")

    render_cards()
    render_view()

    with ui.expansion("Add Event to Calendar").classes("w-full").style("margin-top:20px;"):
        with ui.row().classes("w-full gap-4"):
            name_in = ui.input("Event name *").classes("flex-1")
            type_sel = ui.select(
                ["Investor Conference", "Earnings", "Industry Conference", "Roadshow", "Other"],
                value="Investor Conference", label="Type",
            ).classes("flex-1")
            priority_sel = ui.select(["High", "Medium", "Low"], value="Medium", label="Priority").classes("flex-1")
        with ui.row().classes("w-full gap-4"):
            date_in = _date_field("Event date", str(today + timedelta(days=30)))
            deadline_in = _date_field("Registration deadline", str(today + timedelta(days=14)))
            status_sel2 = ui.select(
                ["Evaluating", "Invited — pending confirmation", "Confirmed",
                 "Needs to be Scheduled", "Not yet contacted"],
                value="Evaluating", label="Status",
            ).classes("flex-1")
        with ui.row().classes("w-full gap-4"):
            location_in = ui.input("Location").classes("flex-1")
            organizer_in = ui.input("Organizer").classes("flex-1")
            attending_in = _attend_select("", cls="flex-1")
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
                "Attending": ", ".join(attending_in.value or []), "Priority": priority_sel.value,
            })
            _save_conferences(conf_path, events)
            render_cards()
            refresh_events()
            ui.notify(f"'{name_in.value}' added to calendar")
            name_in.value = ""

        _add_btn = ui.button("Add to Calendar", on_click=add_event).props("color=primary").style("margin-top:8px;")
        if ui_context.is_read_only():
            _add_btn.disable()

    def export_csv():
        df = pd.DataFrame(events)
        ui.download(df.to_csv(index=False).encode(), f"conference_calendar_{datetime.now().strftime('%Y%m%d')}.csv")

    with ui.row().classes("w-full justify-between items-center").style("margin-top:20px;"):
        ui.button("Export calendar as CSV", on_click=export_csv).props("flat")
        ui.label("Saved · updates persist across restarts").style(
            f"color:{COLORS['text_muted']};font-size:12px;"
        )
