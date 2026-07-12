"""
page_modules/calendar_page.py — IR Conference & Events Calendar page.

Extracted from the "elif page == 'Calendar':" branch of the original
single-file app.py. Named calendar_page.py (not calendar.py) to avoid any
ambiguity with Python's standard-library calendar module.

Shared helpers still defined in app.py (robust_read_csv, DEFAULT_CONFERENCES)
are reached via `import app` and touched only at call time inside
render_calendar_page(), same pattern as page_modules/outreach.py — avoids a
circular-import problem since app.py imports this module too.
"""

import os
import re
import json
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

import app
from config.client_config import client_data_path, CT


def render_calendar_page():
    st.markdown("<div style='padding:16px 4px 0;'><div class='section-eyebrow'>CALENDAR</div><div class='section-title'>Earnings &middot; Conferences &middot; NDR Trips</div></div>", unsafe_allow_html=True)
    if st.session_state.get("highlight_conference"):
        st.markdown(
            f"<div style='background:#1E3A5F;border:1px solid #3B82F6;border-radius:8px;padding:10px 16px;margin:10px 4px;'>"
            f"📍 Jumped here from Today's Calendar — <b style='color:#F1F5F9;'>{st.session_state['highlight_conference']}</b>."
            f"</div>", unsafe_allow_html=True
        )
        st.session_state["highlight_conference"] = None
    if st.session_state.get("highlight_ndr_trip"):
        st.markdown(
            f"<div style='background:#1E3A5F;border:1px solid #3B82F6;border-radius:8px;padding:10px 16px;margin:10px 4px;'>"
            f"📍 Jumped here from Today's Calendar — <b style='color:#F1F5F9;'>{st.session_state['highlight_ndr_trip']}</b>. See the NDR trip list below, or go to Investor Targeting → NDR Planner to manage it."
            f"</div>", unsafe_allow_html=True
        )
        st.session_state["highlight_ndr_trip"] = None

    st.markdown("## 📅 IR Conference & Events Calendar")
    st.caption("Track conferences, earnings calls, roadshows · Auto-extract from transcripts and press releases · Never miss a registration deadline")

    # Client-scoped so client #2's calendar CSV never mixes with USIO's
    # (was a single shared "conferences/" folder before this change).
    CONF_PATH = client_data_path("ir_conference_calendar.csv")

    def load_conferences():
        if os.path.exists(CONF_PATH):
            return app.robust_read_csv(CONF_PATH).to_dict("records")
        return app.DEFAULT_CONFERENCES

    def save_conferences(events):
        pd.DataFrame(events).to_csv(CONF_PATH, index=False)

    if "conferences" not in st.session_state:
        st.session_state.conferences = load_conferences()
        if not os.path.exists(CONF_PATH):
            save_conferences(st.session_state.conferences)

    # ── Summary metric cards ──
    today_str = datetime.now().date()
    events    = st.session_state.conferences

    upcoming  = [e for e in events if datetime.strptime(e["Date"],"%Y-%m-%d").date() >= today_str]
    deadlines = [e for e in upcoming if e.get("Deadline") and
                 datetime.strptime(e["Deadline"],"%Y-%m-%d").date() >= today_str and
                 (datetime.strptime(e["Deadline"],"%Y-%m-%d").date() - today_str).days <= 30]
    confirmed = [e for e in events if e["Status"] == "Confirmed"]
    high_pri  = [e for e in upcoming if e.get("Priority") == "High"]

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total events tracked", len(events))
    c2.metric("Upcoming",             len(upcoming), delta="on calendar")
    c3.metric("Deadlines in 30 days", len(deadlines), delta="act now" if deadlines else None,
              delta_color="inverse" if deadlines else "off")
    c4.metric("High priority",        len(high_pri))

    # ── Deadline alerts ──
    if deadlines:
        st.markdown("---")
        st.markdown("#### ⚠️ Registration Deadlines Coming Up")
        for e in sorted(deadlines, key=lambda x: x["Deadline"]):
            days_left = (datetime.strptime(e["Deadline"],"%Y-%m-%d").date() - today_str).days
            color = "#F87171" if days_left <= 7 else "#F0A830"
            bg = "#3A1F1F" if days_left <= 7 else "#3A2E15"
            st.markdown(
                f"<div style='border:1px solid {color};border-radius:8px;padding:8px 14px;margin-bottom:6px;"
                f"max-width:75%;background:{bg};'>"
                f"<b style='color:{color}'>{e['Event']}</b> · "
                f"<span style='color:{color}'>Deadline: {e['Deadline']} ({days_left} days)</span> · "
                f"<span style='color:#E2E8F0;'>Status: {e['Status']}</span></div>",
                unsafe_allow_html=True
            )

    st.markdown("---")

    # ── View toggle ──
    view_mode = st.radio("View", ["📋 List view", "🗓 Timeline view"], horizontal=True, label_visibility="collapsed")

    # ── Filter controls ──
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        type_filter = st.multiselect("Event type", ["Earnings","Investor Conference","Industry Conference","Roadshow","Other"],
                                     default=["Earnings","Investor Conference","Industry Conference"])
    with col_f2:
        status_filter = st.multiselect("Status", ["Confirmed","Invited — pending confirmation","Scheduled","Evaluating","Not yet contacted"],
                                       default=["Confirmed","Invited — pending confirmation","Scheduled","Evaluating"])
    with col_f3:
        pri_filter = st.multiselect("Priority", ["High","Medium","Low"], default=["High","Medium"])

    filtered_events = [
        e for e in events
        if (not type_filter   or e["Type"]     in type_filter)
        and (not status_filter or e["Status"]   in status_filter)
        and (not pri_filter    or e.get("Priority","Medium") in pri_filter)
    ]
    filtered_events = sorted(filtered_events, key=lambda x: x["Date"])

    st.markdown(f"**{len(filtered_events)} events** matching filters")
    st.markdown("---")

    if view_mode == "📋 List view":
        for idx, ev in enumerate(filtered_events):
            ev_date   = datetime.strptime(ev["Date"],"%Y-%m-%d").date()
            days_away = (ev_date - today_str).days
            is_past   = days_away < 0

            # Status color
            if ev["Status"] == "Confirmed":      s_clr,s_bg = "#27500A","#EAF3DE"
            elif "Invited" in ev["Status"]:      s_clr,s_bg = "#633806","#FAEEDA"
            elif ev["Status"] == "Evaluating":   s_clr,s_bg = "#888888","#F1EFE8"
            else:                                 s_clr,s_bg = "#888888","#F1EFE8"

            # Priority indicator
            p_dot = "🔴" if ev.get("Priority")=="High" else "🟡" if ev.get("Priority")=="Medium" else "⚪"
            # Type badge
            type_clr = {"Earnings":"#1565C0","Investor Conference":"#27500A","Industry Conference":"#854F0B"}.get(ev["Type"],"#888")
            type_bg  = {"Earnings":"#E3F2FD","Investor Conference":"#EAF3DE","Industry Conference":"#FAEEDA"}.get(ev["Type"],"#F1EFE8")

            col_ev, col_act = st.columns([3,1])
            with col_ev:
                deadline_str = f" · Reg deadline: <b style='color:#F87171'>{ev.get('Deadline','—')}</b>" if ev.get("Deadline") and not is_past else ""
                st.markdown(
                    f"<div style='border:0.5px solid #e0e0e0;border-radius:10px;padding:12px 16px;"
                    f"background:{"#F8F8F8" if is_past else "var(--surface-2)"};margin-bottom:6px;opacity:{"0.6" if is_past else "1"}'>"
                    f"<div style='display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:6px'>"
                    f"<div>"
                    f"{p_dot} <b style='font-size:14px'>{ev['Event']}</b> "
                    f"<span style='font-size:13px;background:{type_bg};color:{type_clr};padding:2px 8px;border-radius:8px;margin-left:6px'>{ev['Type']}</span>"
                    f"</div>"
                    f"<span style='font-size:12px;font-weight:500;background:{s_bg};color:{s_clr};padding:3px 10px;border-radius:8px'>{ev['Status']}</span>"
                    f"</div>"
                    f"<div style='display:grid;grid-template-columns:repeat(4,1fr);gap:8px;font-size:12px;margin-bottom:6px'>"
                    f"<div><span style='color:#94A3B8'>Date</span><br><b>{ev['Date']}</b> "
                    f"<span style='color:{"#C00000" if 0<=days_away<=14 else "#888"}'>"
                    f"({'Past' if is_past else f'{days_away}d away'})</span></div>"
                    f"<div><span style='color:#94A3B8'>Location</span><br><b>{ev['Location']}</b></div>"
                    f"<div><span style='color:#94A3B8'>Organizer</span><br><b>{ev['Organizer']}</b></div>"
                    f"<div><span style='color:#94A3B8'>Attending</span><br><b>{ev.get('Attending','TBD')}</b></div>"
                    f"</div>"
                    f"<div style='font-size:13px;color:#94A3B8'>{ev.get('Notes','')} {deadline_str}</div>"
                    f"<div style='font-size:12px;color:#94A3B8;margin-top:4px'>Source: {ev.get('Source','Manual entry')}</div>"
                    f"</div>",
                    unsafe_allow_html=True
                )
            with col_act:
                with st.popover("✏️ Edit", use_container_width=True, help="Update status, notes, and attendee for this event"):
                    new_status = st.selectbox("Update status", ["Confirmed","Invited — pending confirmation",
                        "Scheduled","Evaluating","Not yet contacted","Declined","Completed"],
                        index=["Confirmed","Invited — pending confirmation","Scheduled","Evaluating",
                               "Not yet contacted","Declined","Completed"].index(ev["Status"])
                        if ev["Status"] in ["Confirmed","Invited — pending confirmation","Scheduled","Evaluating",
                                             "Not yet contacted","Declined","Completed"] else 0,
                        key=f"status_{idx}")
                    new_notes = st.text_area("Notes", value=ev.get("Notes",""), key=f"notes_{idx}", height=80)
                    new_attend= st.text_input("Attending", value=ev.get("Attending","TBD"), key=f"attend_{idx}")
                    col_save, col_del = st.columns(2)
                    with col_save:
                        if st.button("💾 Save", key=f"save_{idx}", use_container_width=True):
                            st.session_state.conferences[
                                next(i for i,e in enumerate(st.session_state.conferences) if e["Event"]==ev["Event"])
                            ]["Status"]    = new_status
                            st.session_state.conferences[
                                next(i for i,e in enumerate(st.session_state.conferences) if e["Event"]==ev["Event"])
                            ]["Notes"]     = new_notes
                            st.session_state.conferences[
                                next(i for i,e in enumerate(st.session_state.conferences) if e["Event"]==ev["Event"])
                            ]["Attending"] = new_attend
                            save_conferences(st.session_state.conferences)
                            st.success("Saved")
                            st.rerun()
                    with col_del:
                        if st.button("🗑 Delete", key=f"del_{idx}", use_container_width=True):
                            st.session_state.conferences = [e for e in st.session_state.conferences if e["Event"]!=ev["Event"]]
                            save_conferences(st.session_state.conferences)
                            st.rerun()

    else:
        # ── Timeline view ── same edit capability as List view, just grouped
        #    by month instead of a flat list — previously this was plain text
        #    with no action button at all.
        st.markdown("#### 📅 6-Month Timeline")
        months = {}
        for ev in filtered_events:
            m = datetime.strptime(ev["Date"],"%Y-%m-%d").strftime("%B %Y")
            months.setdefault(m,[]).append(ev)
        for month, mevents in months.items():
            st.markdown(f"**{month}**")
            for ev in mevents:
                dot = "🔴" if ev.get("Priority")=="High" else "🟡"
                s_ico = "✅" if ev["Status"]=="Confirmed" else "⏳"
                _tl_col_ev, _tl_col_act = st.columns([5, 1])
                with _tl_col_ev:
                    st.markdown(f"&nbsp;&nbsp;&nbsp;{dot} {s_ico} `{ev['Date']}` — **{ev['Event']}** · {ev['Location']} · {ev['Status']}")
                with _tl_col_act:
                    with st.popover("✏️", use_container_width=True, help="Update status, notes, and attendee for this event"):
                        _tl_key = ev["Event"].replace(" ", "_")[:30]
                        _status_options = ["Confirmed","Invited — pending confirmation","Scheduled","Evaluating","Not yet contacted","Declined","Completed"]
                        _tl_status = st.selectbox("Update status", _status_options,
                            index=_status_options.index(ev["Status"]) if ev["Status"] in _status_options else 0,
                            key=f"tl_status_{_tl_key}")
                        _tl_notes = st.text_area("Notes", value=ev.get("Notes",""), key=f"tl_notes_{_tl_key}", height=80)
                        _tl_attend = st.text_input("Attending", value=ev.get("Attending","TBD"), key=f"tl_attend_{_tl_key}")
                        _tl_save, _tl_del = st.columns(2)
                        with _tl_save:
                            if st.button("💾 Save", key=f"tl_save_{_tl_key}", use_container_width=True):
                                _tl_idx = next(i for i,e in enumerate(st.session_state.conferences) if e["Event"]==ev["Event"])
                                st.session_state.conferences[_tl_idx]["Status"] = _tl_status
                                st.session_state.conferences[_tl_idx]["Notes"] = _tl_notes
                                st.session_state.conferences[_tl_idx]["Attending"] = _tl_attend
                                save_conferences(st.session_state.conferences)
                                st.success("Saved")
                                st.rerun()
                        with _tl_del:
                            if st.button("🗑 Delete", key=f"tl_del_{_tl_key}", use_container_width=True):
                                st.session_state.conferences = [e for e in st.session_state.conferences if e["Event"]!=ev["Event"]]
                                save_conferences(st.session_state.conferences)
                                st.rerun()
            st.markdown("")

    st.markdown("---")

    # ── NDR TRIPS ON THE CALENDAR — the one thing not already covered by the
    #    conference tool below (which handles conferences/earnings with far
    #    more detail — filters, status, deadlines, editing). NDR trips live in
    #    a separate file, so this is a real complement, not a duplicate. ──────
    st.markdown("#### ✈️ NDR Trips on the Calendar")
    _cal2_trips = []
    try:
        _cal2_trips = json.load(open("outputs/ndr_trips.json")) if os.path.exists("outputs/ndr_trips.json") else []
    except Exception:
        pass
    _ndr_cal_items = [t for t in _cal2_trips if t.get("city") and t.get("city") != "Virtual"]
    if not _ndr_cal_items:
        st.caption("No NDR trips on file yet — plan one in Investor Targeting → NDR Planner.")
    else:
        for _trip in _ndr_cal_items:
            st.markdown(
                f"<div style='background:#1E2D42;border-radius:8px;padding:10px 14px;margin-bottom:6px;max-width:75%;'>"
                f"<b style='color:#F1F5F9;'>✈️ {_trip.get('name','NDR Trip')}</b> "
                f"<span style='font-size:12px;color:#8B9DB8;'>· NDR Trip</span>"
                f"<div style='font-size:12px;color:#94A3B8;margin-top:2px;'>{_trip.get('city','—')} · {_trip.get('status','Planning')} · {_trip.get('dates','')}</div>"
                f"</div>", unsafe_allow_html=True
            )
    st.markdown("---")

    # ── ADD EVENT SECTION ──────────────────────────────────────────────────
    with st.expander("➕ Add Event to Calendar", expanded=False):
        add_tab1, add_tab2, add_tab3 = st.tabs(["✏️ Manual entry", "📧 Paste from email/press release", "📄 Extract from transcript"])

        with add_tab1:
            with st.form("add_conference_manual"):
                r1c1, r1c2, r1c3 = st.columns(3)
                with r1c1:
                    new_event    = st.text_input("Event name *")
                    new_type     = st.selectbox("Type", ["Investor Conference","Earnings","Industry Conference","Roadshow","Other"])
                    new_priority = st.selectbox("Priority", ["High","Medium","Low"])
                with r1c2:
                    new_date     = st.date_input("Event date *", value=datetime.now().date() + timedelta(days=30))
                    new_deadline = st.date_input("Registration deadline", value=datetime.now().date() + timedelta(days=14))
                    new_status   = st.selectbox("Status", ["Evaluating","Invited — pending confirmation","Confirmed","Not yet contacted"])
                with r1c3:
                    new_location = st.text_input("Location")
                    new_organizer= st.text_input("Organizer")
                    new_attending= st.text_input("Attending", value="TBD")
                new_notes  = st.text_area("Notes / logistics", height=80)
                new_source = st.selectbox("Source", ["Manual entry","Press release","Earnings transcript","Email","Analyst relationship","Industry"])
                if st.form_submit_button("📅 Add to Calendar", type="primary"):
                    if new_event:
                        st.session_state.conferences.append({
                            "Event":     new_event,
                            "Type":      new_type,
                            "Date":      str(new_date),
                            "Location":  new_location,
                            "Organizer": new_organizer,
                            "Status":    new_status,
                            "Deadline":  str(new_deadline),
                            "Notes":     new_notes,
                            "Source":    new_source,
                            "Attending": new_attending,
                            "Priority":  new_priority,
                        })
                        save_conferences(st.session_state.conferences)
                        st.success(f"✅ '{new_event}' added to calendar")
                        st.rerun()

        with add_tab2:
            st.caption("Paste raw text from an email or press release and the platform will extract conference details.")
            pasted_text = st.text_area("Paste email or press release text here", height=200,
                                       placeholder="e.g. 'Usio will present at the H.C. Wainwright Annual Global Investment Conference on September 8-10, 2026 in New York...'")
            if st.button("🔍 Extract Conference Details", type="primary"):
                if pasted_text:
                    # Simple extraction heuristics
                    extracted = []
                    # Look for conference name patterns
                    conf_patterns = [
                        r'(?:present at|attend|participate in|join us at)\s+(?:the\s+)?([A-Z][^.!?\n]{10,80}(?:Conference|Expo|Forum|Summit|Event|Meeting|Symposium|Convention))',
                        r'([A-Z][^.!?\n]{5,60}(?:Conference|Expo|Forum|Summit|Investor\s+Day))',
                    ]
                    # Look for dates
                    date_patterns = [
                        r'(?:on\s+)?(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}(?:-\d{1,2})?,?\s+202[5-9]',
                    ]
                    found_events = []
                    for pattern in conf_patterns:
                        matches = re.findall(pattern, pasted_text, re.IGNORECASE)
                        found_events.extend(matches[:3])
                    found_dates = re.findall(date_patterns[0], pasted_text, re.IGNORECASE)

                    if found_events:
                        st.success(f"Found {len(found_events)} potential event(s):")
                        for i, evt in enumerate(found_events[:3]):
                            date_guess = found_dates[i] if i < len(found_dates) else "Date not found — set manually"
                            st.markdown(f"**{evt.strip()}** · {date_guess}")
                            if st.button(f"➕ Add '{evt.strip()[:40]}...' to calendar", key=f"extract_add_{i}"):
                                st.session_state.conferences.append({
                                    "Event":     evt.strip(),
                                    "Type":      "Investor Conference",
                                    "Date":      str(datetime.now().date() + timedelta(days=60)),
                                    "Location":  "TBD — set manually",
                                    "Organizer": "TBD",
                                    "Status":    "Evaluating",
                                    "Deadline":  str(datetime.now().date() + timedelta(days=30)),
                                    "Notes":     f"Extracted from text: {pasted_text[:200]}...",
                                    "Source":    "Email / Press release",
                                    "Attending": "TBD",
                                    "Priority":  "Medium",
                                })
                                save_conferences(st.session_state.conferences)
                                st.success("Added — update the date and location manually")
                                st.rerun()
                    else:
                        st.warning("No conference names detected. Try the manual entry tab or check the text format.")

        with add_tab3:
            st.caption("Paste an earnings call transcript and the platform will scan for conference mentions.")
            transcript_text = st.text_area("Paste transcript text", height=200,
                                           placeholder="Paste the Q1 2026 or Q4 2025 earnings transcript here...")
            if st.button("🔍 Scan Transcript for Conference Mentions", type="primary", key="scan_transcript"):
                if transcript_text:
                    conf_keywords = ["conference","expo","forum","summit","investor day","roadshow","present at","attending"]
                    sentences = [s.strip() for s in re.split(r'[.!?\n]', transcript_text) if len(s.strip()) > 20]
                    hits = [s for s in sentences if any(kw in s.lower() for kw in conf_keywords)]
                    if hits:
                        st.success(f"Found {len(hits)} conference-related mention(s):")
                        for h in hits[:8]:
                            st.markdown(f"📌 *\"{h}\"*")
                            if st.button(f"➕ Add event from this mention", key=f"transcript_add_{hash(h)}"):
                                st.session_state.conferences.append({
                                    "Event":     h[:80].strip(),
                                    "Type":      "Investor Conference",
                                    "Date":      str(datetime.now().date() + timedelta(days=90)),
                                    "Location":  "TBD",
                                    "Organizer": "TBD",
                                    "Status":    "Evaluating",
                                    "Deadline":  str(datetime.now().date() + timedelta(days=45)),
                                    "Notes":     f"Transcript mention: {h}",
                                    "Source":    "Earnings transcript",
                                    "Attending": "TBD",
                                    "Priority":  "Medium",
                                })
                                save_conferences(st.session_state.conferences)
                                st.success("Added — update event name, date and location manually")
                                st.rerun()
                    else:
                        st.info("No conference mentions found in transcript.")

        st.markdown("---")

        # ── EXPORT ──
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            df_conf = pd.DataFrame(st.session_state.conferences)
            st.download_button(
                "⬇️ Export calendar as CSV",
                data=df_conf.to_csv(index=False),
                file_name=f"{CT('ticker')}_IR_Conference_Calendar_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
                use_container_width=True,
            )
        with col_ex2:
            st.caption(f"📁 Calendar saved to `{CONF_PATH}` · {len(st.session_state.conferences)} events · Updates persist across restarts")
