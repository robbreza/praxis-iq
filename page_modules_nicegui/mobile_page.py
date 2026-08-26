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
        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:12px;")


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

    with ui.dialog() as dialog, ui.card().style(
            f"background:{COLORS['surface_bg']};min-width:min(92vw,440px);"
            f"max-height:88vh;overflow:auto;border-radius:12px;"):
        ui.label(pretty_name(fund)).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        if meeting:
            ctx = " · ".join(x for x in [meeting.get("Date"), meeting.get("Time"),
                                         meeting.get("Contact"), meeting.get("Type")] if x)
            if ctx:
                ui.label(ctx).style(f"color:{COLORS['accent']};font-size:var(--fs-sm);font-weight:600;")
            if meeting.get("Topic"):
                ui.label(f"Agenda: {meeting['Topic']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        # The SAME full investor brief the desktop uses (position, signal, peers, contact,
        # talking points, last note) — one consistent briefing everywhere instead of the old
        # lean mobile-only version. The institutions row carries both the 13F fields and the
        # contact/behavioral fields, so it serves as both args; the engagement-score
        # breakdown just omits itself when it isn't on the row.
        try:
            from page_modules_nicegui.today_page import _render_investor_brief
            _render_investor_brief(row, row, fund)
        except Exception:
            ui.label("No 13F position on file — prospect.").style(
                f"color:{COLORS['text_body']};font-size:var(--fs-base);")

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


def _ndr_meetings(cid):
    """Upcoming NDR trip meetings (today + future) — each row carries the RAW trip-meeting dict so the
    phone renders the SAME prep card the desktop does. Only non-Completed trips with a resolvable start
    date place onto the schedule; the meeting's absolute date = trip start + its day offset."""
    from datetime import timedelta
    from core import db
    from core.meetings import parse_trip_start
    today = datetime.now().date()
    out = []
    for t in (db.load_json("ndr_trips.json", [], client_id=cid) or []):
        if (t.get("status") or "").lower() == "completed":
            continue
        start = parse_trip_start(t.get("dates"))
        if start is None:
            continue
        for m in (t.get("meetings") or []):
            if m.get("type") == "break":
                continue
            try:
                d = start + timedelta(days=max(0, int(m.get("day", 1) or 1) - 1))
            except Exception:
                continue
            if d < today:
                continue
            out.append({
                "Firm": m.get("institution", ""), "Contact": m.get("contact", ""),
                "Date": d.strftime("%Y-%m-%d"),
                "Time": m.get("time", "") if m.get("time") != "—" else "",
                "Type": m.get("type", "1x1"), "_ndr": True, "_raw": m,
                "_trip": t.get("name", ""), "_metro": m.get("metro") or t.get("city", ""),
            })
    return out


def _prep_inst_lookup(cid):
    """Holders + promoted prospects, engagement-enriched — the institution rows the prep card reads
    (position for holders, fit for prospects). Mirrors what the desktop Prep Cards tab resolves, so the
    phone card is identical."""
    from core import targets
    insts = list(targets.targets_as_institutions(client_id=cid) or [])
    try:
        seen = {i.get("Fund") for i in insts}
        insts += [p for p in (targets.promoted_prospects(cid) or []) if p.get("Fund") not in seen]
    except Exception:
        pass
    try:
        from page_modules_nicegui.investors_page import _enrich_engagement_signals, _enrich_holders_vs_comps
        _enrich_engagement_signals(insts, cid)
        _enrich_holders_vs_comps(insts, cid)   # so the phone prep card shows the same peer-weight upsell
    except Exception:
        pass
    return {i.get("Fund"): i for i in insts if i.get("Fund")}


def _open_ndr_prep(raw, cid, inst_lookup):
    """The full NDR prep card on a phone — the SAME briefing the desktop Prep Cards tab shows (via the
    shared render_prep_card_body), so the CFO walks into the meeting ready straight off her phone. Plus
    one-tap note capture for right after."""
    from page_modules_nicegui.investors_page import render_prep_card_body, _last_meeting_brief
    firm = raw.get("institution", "")
    inst = inst_lookup.get(firm)
    prior = None
    try:
        prior = _last_meeting_brief(firm)
    except Exception:
        pass
    with ui.dialog() as dialog, ui.card().style(
            f"background:{COLORS['surface_bg']};min-width:min(94vw,460px);"
            f"max-height:90vh;overflow:auto;border-radius:12px;"):
        ui.label(pretty_name(firm)).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        _sc = raw.get("score")
        holder = inst.get("USIO_Holder") if inst else (raw.get("non_holder") is False)
        cap = [raw.get("time"), raw.get("metro"),
               "Existing holder" if holder else "Prospect",
               (f"Fit {int(_sc)}" if isinstance(_sc, (int, float)) else None)]
        ui.label(" · ".join(str(x) for x in cap if x)).style(
            f"color:{COLORS['accent']};font-size:var(--fs-sm);font-weight:600;margin-bottom:6px;")
        render_prep_card_body(raw, inst, prior)
        ui.separator().style("margin:8px 0;")
        ui.label("Capture a note").classes("font-bold").style(
            f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
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
                    "Fund": firm, "Date": datetime.now().strftime("%Y-%m-%d"),
                    "Type": "Note (mobile)", "Attendees": "", "Notes": text,
                    "Outcome": "No clear signal", "Logged By": (CI() or {}).get("name") or "IR Team",
                    "Source": "Mobile · NDR prep",
                })
                save_meeting_log(log)
                try:
                    activity_log.log_event("meeting_note", entity=firm, launched_from="Mobile · NDR prep")
                except Exception:
                    pass
                ui.notify(f"Note saved to {pretty_name(firm)}."); dialog.close()
            except Exception:
                ui.notify("Couldn't save the note — try again from desktop.", type="negative")

        with ui.row().classes("w-full justify-end gap-2").style("margin-top:6px;"):
            ui.button("Close", on_click=dialog.close).props("flat")
            ui.button("Save note", on_click=_save).props("color=primary")
    dialog.open()


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
    # Standalone 1x1s (scheduled_meetings) AND NDR trip meetings, merged & date-sorted — so a roadshow
    # planned on the desktop shows up on the phone, and each NDR stop opens the SAME prep card the CFO
    # would see at her desk (render_prep_card_body), straight off her phone before she walks in.
    sched, today = _upcoming_meetings(client_id)
    ndr = _ndr_meetings(client_id)
    # Sort by date, then by PARSED time-of-day — a plain string sort puts "8:00 AM" after "10:00 AM"
    # (lexical), which would bury the CFO's earliest meeting. None/unparseable times sort last.
    try:
        from page_modules_nicegui.investors_page import _parse_time_min as _tmin
    except Exception:
        _tmin = lambda s: None
    meetings = sorted(sched + ndr,
                      key=lambda x: ((x.get("Date") or "9999-99-99"),
                                     (_tmin(x.get("Time")) if _tmin(x.get("Time")) is not None else 9999)))
    inst_lookup = _prep_inst_lookup(client_id) if ndr else {}
    with _card():
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Your meetings").classes("section-head")
            ui.button("Schedule →", on_click=lambda: nav.go_to("Inbox")) \
                .props("flat dense size=sm")
        if meetings:
            for m in meetings[:8]:
                firm = m.get("Firm") or m.get("Contact") or "—"
                is_today = (m.get("Date") or "") == today
                when = "Today" if is_today else _fmt_date(m.get("Date"))
                _is_ndr = bool(m.get("_ndr"))
                if _is_ndr:
                    _tap = lambda m=m: _open_ndr_prep(m["_raw"], client_id, inst_lookup)
                else:
                    _tap = lambda m=m, f=firm: _open_brief(f, inst_by_fund, client_id, meeting=m)
                with ui.row().classes("w-full items-center gap-3").style(
                        f"padding:9px 0;border-top:1px solid {COLORS['border']};cursor:pointer;").on(
                        "click", _tap):
                    with ui.column().classes("gap-0 items-center").style("min-width:52px;"):
                        ui.label(when).style(
                            f"font-size:var(--fs-xs);font-weight:700;"
                            f"color:{COLORS['accent'] if is_today else COLORS['text_muted']};")
                        if m.get("Time"):
                            ui.label(m["Time"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    with ui.column().classes("gap-0").style("flex:1;min-width:0;"):
                        with ui.row().classes("items-center gap-2").style("min-width:0;"):
                            ui.label(pretty_name(firm)).style(
                                f"color:{COLORS['text_heading']};font-size:var(--fs-md);font-weight:600;line-height:1.3;")
                            if _is_ndr:
                                ui.label("NDR").style(
                                    f"background:{COLORS['accent']};color:#fff;font-size:9px;font-weight:700;"
                                    "padding:1px 6px;border-radius:8px;letter-spacing:.04em;")
                        sub = " · ".join(x for x in [m.get("Contact"),
                                                     (m.get("_metro") if _is_ndr else m.get("Type"))] if x)
                        if sub:
                            ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                    ui.icon("chevron_right").style(f"color:{COLORS['text_muted']};font-size:var(--fs-2xl);")
            ui.label("Tap a meeting for the prep card + to capture a note.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:6px;")
        else:
            ui.label("No meetings booked yet.").style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")
            ui.button("Schedule a meeting →", on_click=lambda: nav.go_to("Inbox")) \
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
    snap = market_data.get_snapshot(ticker, refresh_if_stale=False)
    pulse = _card().style(
        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:12px;"
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
