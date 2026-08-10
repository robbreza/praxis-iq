"""Home — the on-the-road mobile assistant.

Deliberately NOT the desktop app shrunk: a phone is for glancing and looking things up between
meetings, not authoring board decks or building target lists. This page leads with the handful of
things an IR lead actually pulls a phone out for:

  1. Pulse       — price / volume / the weekly context one-liner, with a jump to Lighthouse.
  2. Schedule    — upcoming conferences / NDR events (read), a jump to the full Calendar.
  3. Meeting prep — pick anyone you're seeing → a one-screen brief (holding, conviction, contact,
                    last note) and CAPTURE A NOTE right after the meeting (saved to the meeting log).
  4. Alerts      — enable phone push, jump to Lighthouse.

Reuses the same data sources Today uses (market_data, investor_scoring meeting log, targets,
institution contacts, conferences) — no new backend. Renders fine on desktop too, but it's tuned for
a single narrow column. Heavy authoring (Investor Targeting build-out, Earnings scripts, Reports,
Settings) is intentionally hidden from the mobile nav — see the nav-group--desktop-only CSS.
"""
from datetime import datetime

from nicegui import ui

from config.client_config import CT, get_active_client_id
from config.theme_tokens import ACTIVE as COLORS
from core import market_data
from core.textfmt import pretty_name
from page_modules_nicegui import nav


def _card():
    return ui.card().classes("w-full").style(
        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:14px;")


def _last_note_for(fund):
    try:
        from core.investor_scoring import load_meeting_log
        rows = [r for r in (load_meeting_log() or []) if r.get("Fund") == fund and r.get("Notes")]
        rows.sort(key=lambda r: r.get("Date", ""), reverse=True)
        return rows[0] if rows else None
    except Exception:
        return None


def _institutions(client_id):
    try:
        from core import targets
        return targets.targets_as_institutions(client_id=client_id) or []
    except Exception:
        return []


def _open_brief(fund, inst_by_fund, client_id, meeting=None):
    """One-screen meeting brief + note capture for a fund/holder. Kept lean and fast for a phone:
    it reads only the (already-loaded) holder row + the last note — no heavy CRM/contact resolution,
    which is a desktop concern and was slow enough to risk a slow tap / oversized socket message.
    `meeting` (an optional scheduled_meetings row) adds the who/when/agenda context at the top when
    the brief is opened from an actual booked meeting rather than a bare holder lookup."""
    row = inst_by_fund.get(fund, {"Fund": fund})
    note = _last_note_for(fund)

    with ui.dialog() as dialog, ui.card().style(
            f"background:{COLORS['surface_bg']};min-width:min(92vw,440px);border-radius:14px;"):
        ui.label(pretty_name(fund)).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        if meeting:
            ctx = " · ".join(x for x in [meeting.get("Date"), meeting.get("Time"),
                                         meeting.get("Contact"), meeting.get("Type")] if x)
            if ctx:
                ui.label(ctx).style(f"color:{COLORS['accent']};font-size:var(--fs-sm);font-weight:600;")
            if meeting.get("Topic"):
                ui.label(f"Agenda: {meeting['Topic']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        # holding / conviction / direction — only what we actually have
        bits = []
        if row.get("Position_Value"):
            bits.append(f"${row['Position_Value']/1e6:,.1f}M held")
        if row.get("Conviction"):
            bits.append(str(row["Conviction"]))
        if row.get("Direction"):
            bits.append(str(row["Direction"]).title())
        if row.get("Metro"):
            bits.append(str(row["Metro"]))
        ui.label(" · ".join(bits) if bits else "No 13F position on file — prospect.") \
            .style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")
        if row.get("Coverage_Priority"):
            ui.label(f"Coverage priority: {row['Coverage_Priority']}").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        # last note
        if note:
            with ui.element("div").style(
                    f"background:{COLORS['surface_hover_bg']};border-radius:8px;padding:8px 10px;margin-top:6px;"):
                ui.label(f"Last note ({note.get('Date','')})").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                ui.label(note.get("Notes", "")).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")

        ui.separator().style("margin:8px 0;")
        ui.label("Capture a note").classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
        note_in = ui.textarea(placeholder="What did they say? Objections, follow-ups, buy signal…") \
            .props("autogrow").classes("w-full")

        def _save():
            text = (note_in.value or "").strip()
            if not text:
                ui.notify("Nothing to save yet.", type="warning"); return
            try:
                from core.investor_scoring import load_meeting_log, save_meeting_log
                from core import activity_log
                from config.client_config import CI
                log = load_meeting_log() or []
                log.append({
                    "Fund": fund, "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Type": "Note (mobile)", "Attendees": "",
                    "Notes": text, "Outcome": "No clear signal",
                    "Logged By": (CI() or {}).get("name") or "IR Team", "Source": "Mobile · Meeting prep",
                })
                save_meeting_log(log)
                try:
                    activity_log.log_event("meeting_note", entity=fund, launched_from="Mobile · Meeting prep")
                except Exception:
                    pass
                ui.notify(f"Note saved to {pretty_name(fund)}.")
                dialog.close()
            except Exception:
                ui.notify("Couldn't save the note — try again from desktop.", type="negative")

        with ui.row().classes("w-full justify-end gap-2").style("margin-top:6px;"):
            ui.button("Close", on_click=dialog.close).props("flat")
            ui.button("Save note", on_click=_save).props("color=primary")
    dialog.open()


def _upcoming_meetings(client_id):
    """This client's booked investor meetings (scheduled_meetings.json), today + future, soonest
    first. String date compare is fine for ISO YYYY-MM-DD; undated rows sort last but still show."""
    from core import db
    rows = db.load_json("scheduled_meetings.json", default=[], client_id=client_id) or []
    today = datetime.now().strftime("%Y-%m-%d")
    upcoming = [m for m in rows if not (m.get("Date") or "") or (m.get("Date") or "") >= today]
    upcoming.sort(key=lambda m: ((m.get("Date") or "9999-99-99"), (m.get("Time") or "")))
    return upcoming, today


def _fmt_date(d):
    try:
        return datetime.strptime(d, "%Y-%m-%d").strftime("%b %d")
    except Exception:
        return d or ""


def render_home_page():
    client_id = get_active_client_id()
    ticker = CT("ticker")
    ui.label(datetime.now().strftime("%A, %B %d").upper()) \
        .style(f"color:{COLORS['accent_light2']};letter-spacing:.08em;font-size:var(--fs-sm);")
    ui.label("On the road").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    insts = _institutions(client_id)
    inst_by_fund = {r.get("Fund"): r for r in insts if r.get("Fund")}

    # ── 1. YOUR MEETINGS (the hero — the one job a phone view has on the road) ──────────────────
    meetings, today = _upcoming_meetings(client_id)
    with _card():
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Your meetings").classes("section-head")
            ui.button("Schedule →", on_click=lambda: nav.go_to("Investors", "Meeting Hub")) \
                .props("flat dense size=sm")
        if meetings:
            for m in meetings[:6]:
                firm = m.get("Firm") or m.get("Contact") or "—"
                is_today = (m.get("Date") or "") == today
                when = "Today" if is_today else _fmt_date(m.get("Date"))
                with ui.row().classes("w-full items-center gap-3").style(
                        f"padding:9px 0;border-top:1px solid {COLORS['border']};cursor:pointer;").on(
                        "click", lambda m=m, f=firm: _open_brief(f, inst_by_fund, client_id, meeting=m)):
                    with ui.column().classes("gap-0 items-center").style("min-width:52px;"):
                        ui.label(when).style(
                            f"font-size:var(--fs-xs);font-weight:700;"
                            f"color:{COLORS['accent'] if is_today else COLORS['text_muted']};")
                        if m.get("Time"):
                            ui.label(m["Time"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    with ui.column().classes("gap-0").style("flex:1;min-width:0;"):
                        ui.label(pretty_name(firm)).style(
                            f"color:{COLORS['text_heading']};font-size:var(--fs-md);font-weight:600;line-height:1.3;")
                        sub = " · ".join(x for x in [m.get("Contact"), m.get("Type")] if x)
                        if sub:
                            ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                    ui.icon("chevron_right").style(f"color:{COLORS['text_muted']};font-size:var(--fs-2xl);")
            ui.label("Tap a meeting for the brief + to capture a note.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:6px;")
        else:
            ui.label("No meetings booked yet.").style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")
            ui.button("Schedule a meeting →", on_click=lambda: nav.go_to("Investors", "Meeting Hub")) \
                .props("flat dense").style(f"color:{COLORS['accent']};margin-top:2px;")
        # Secondary: prep anyone who isn't booked (the old holder lookup, now clearly subordinate).
        if inst_by_fund:
            ranked = sorted(insts, key=lambda r: (r.get("Position_Value") or 0), reverse=True)
            names = [r["Fund"] for r in ranked[:40] if r.get("Fund")]
            ui.separator().style("margin:8px 0 4px;")
            ui.label("Seeing someone not on the list? Look up any holder:").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            sel = ui.select(options=names, with_input=True, label="Search a holder") \
                .props("outlined dense clearable").classes("w-full")
            sel.on_value_change(lambda e: (e.value and _open_brief(e.value, inst_by_fund, client_id)))

    # ── 2. PULSE (a glance — the whole card taps through to Lighthouse) ─────────────────────────
    snap = market_data.get_snapshot(ticker)
    pulse = _card().style(
        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:14px;"
        "cursor:pointer;").on("click", lambda: nav.go_to("Lighthouse"))
    with pulse:
        ui.label(f"{ticker} · pulse").classes("section-head")
        if snap and snap.get("last_price") is not None:
            chg = snap.get("pct_change") or 0
            clr = COLORS["success"] if chg >= 0 else COLORS["danger"]
            with ui.row().classes("items-baseline gap-3"):
                ui.label(f"${snap['last_price']:.2f}").classes("font-bold").style(
                    f"color:{COLORS['text_heading']};font-size:var(--fs-hero);")
                ui.label(f"{chg:+.1f}%").classes("font-bold").style(f"color:{clr};font-size:var(--fs-md);")
                if snap.get("volume") and snap.get("avg_volume_10d"):
                    ui.label(f"{snap['volume']/snap['avg_volume_10d']:.1f}× vol").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        else:
            ui.label("Market data refreshing…").style(f"color:{COLORS['text_muted']};font-size:var(--fs-base);")
        try:
            from core.curated_targets import _is_illustrative
            if ticker == "USIO" or _is_illustrative(client_id):
                from lighthouse import weekly as _weekly
                wk = _weekly.load_context_cache(client_id, ticker)
                if wk and wk.get("context_read"):
                    ui.label(f"This week: {ticker} {wk['context_read']}").style(
                        f"color:{COLORS['text_body']};font-size:var(--fs-sm);margin-top:4px;line-height:1.5;")
        except Exception:
            pass
        # Prominent action, full-width — not a shrunk top-right link.
        ui.button("Why is it moving? Open Lighthouse →",
                  on_click=lambda: nav.go_to("Lighthouse")).props("flat dense").classes("w-full").style(
            f"color:{COLORS['accent']};justify-content:flex-start;margin-top:6px;text-transform:none;")

    # ── 3. UPCOMING EVENTS (conferences — each row taps through to the Calendar) ────────────────
    with _card():
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Upcoming events").classes("section-head")
            ui.button("Full calendar →", on_click=lambda: nav.go_to("Calendar")).props("flat dense size=sm")
        confs = []
        try:
            from page_modules_nicegui.today_page import _upcoming_conferences
            confs = _upcoming_conferences() or []
        except Exception:
            confs = []
        if confs:
            for cf in confs[:5]:
                status = cf.get("Status", "") or ""
                line = " · ".join(x for x in [cf.get("Date", ""), cf.get("Event", ""), cf.get("Location", "")] if x)
                with ui.row().classes("w-full items-center gap-2").style(
                        f"padding:6px 0;border-top:1px solid {COLORS['border']};cursor:pointer;").on(
                        "click", lambda: nav.go_to("Calendar")):
                    ui.icon("event").style(f"color:{COLORS['accent']};font-size:var(--fs-xl);")
                    with ui.column().classes("gap-0").style("flex:1;min-width:0;"):
                        ui.label(line).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);line-height:1.4;")
                        if status:
                            ui.label(status).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    ui.icon("chevron_right").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xl);")
        else:
            ui.label("No upcoming investor events on the calendar.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-base);")

    # ── 4. ALERTS ─────────────────────────────────────────────────────────────
    from core.curated_targets import _is_illustrative as _isillus_m
    if ticker == "USIO" or _isillus_m(client_id):
        with _card():
            ui.label("Alerts").classes("section-head")
            ui.label("Get a phone notification when the stock makes an abnormal move.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            # No inline onclick — NiceGUI/Vue strips it from ui.html, leaving the button dead. Instead a
            # document-level delegated listener (in app_nicegui's body script) fires on [data-ir-enable],
            # which keeps the handler INSIDE the tap gesture that Notification.requestPermission needs.
            # user-select/touch-callout=none stops iOS from treating a tap as "select text → Copy".
            ui.html(f'<button data-ir-enable="{client_id}" '
                    'style="display:inline-flex;align-items:center;gap:6px;background:#1E40AF;color:#fff;'
                    'border:0;border-radius:8px;padding:11px 16px;font:600 14px -apple-system,Segoe UI,Roboto,'
                    'sans-serif;cursor:pointer;margin-top:6px;-webkit-user-select:none;user-select:none;'
                    '-webkit-touch-callout:none;touch-action:manipulation;'
                    '-webkit-tap-highlight-color:rgba(255,255,255,.25);">🔔 Enable phone alerts</button>')

            def _test_push():
                try:
                    import os as _os
                    from lighthouse import push
                    rep = push.send_to_client(client_id, "IRconnect test alert",
                                              "If you can read this, phone alerts are working. 🎉",
                                              url=(_os.environ.get("LIGHTHOUSE_APP_URL") or "/"))
                    if rep.get("sent"):
                        ui.notify(f"Test push sent to {rep['sent']} device(s).", type="positive")
                    elif rep.get("total") == 0:
                        ui.notify("No phone subscribed yet — tap “Enable phone alerts” from the installed "
                                  "app first, then try again.", type="warning")
                    else:
                        ui.notify("Couldn't deliver — the subscription looks stale; re-enable alerts.",
                                  type="warning")
                except Exception:
                    ui.notify("Test push failed — see server logs.", type="negative")

            ui.button("Send test push", on_click=_test_push).props("flat dense size=sm") \
                .style("margin-top:4px;")
