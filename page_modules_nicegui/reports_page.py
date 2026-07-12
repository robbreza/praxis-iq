"""
page_modules_nicegui/reports_page.py — Reports & Deliverables page, NiceGUI version.

Six tabs. The first five were ported from the original Streamlit "Reports"
section:
1. Board IR Reports        — embedded report-page images + reviewed tracking
2. Investor Materials      — PDF documents + reviewed tracking
3. Peer & Market Analysis  — embedded report-page images + key findings
4. Reg FD & Compliance     — the important one: quiet-period banner, log-an-
                              interaction form, full log with filters, risk
                              flags, and a CSV export. Legal audit trail.
5. All Downloads           — list of generated deliverables
6. Automation Tracker      — new, not in app.py. Same "expansion card with
                              a KEY FINDING" visual pattern as Peer & Market
                              Analysis, but live-computed from
                              core/activity_log.py instead of static
                              embedded report images — a per-category
                              breakdown of what's actually been automated,
                              not just the single headline number Today's
                              (now hideable, defaults off — see
                              render_today_page) ROI strip shows. Moved here
                              per the user, Jul 10 2026.

Two small improvements made during the port (both flagged, not silent):
- "Reviewed" checkboxes and the Reg FD log now persist via core.db
  (SQLite), instead of Streamlit's session_state (which only lived in one
  browser tab's memory and reset on restart). Was client-scoped JSON files
  via client_data_path() in an earlier pass — core.db imports any
  pre-existing file under the same key name on first read, so that data
  isn't lost.
- The quiet-period start/end dates now come from the client's earnings
  config (CE()) instead of being hardcoded to one specific quarter's dates.

Embedded report images (Q1_P1, Q2_P1-3, PBR_PAGES, PBD_PAGES, SES_PAGES)
are copied from app.py's base64 constants into data/seed/report_images.py
(via extract_report_images.py, run once at the project root) and imported
from there. Earlier this page did `import app` to reach them directly, but
the real app.py has st.set_page_config(...) and all its page-routing logic
sitting at module level — so a plain import doesn't just grab the
constants, it tries to execute the entire Streamlit script as a side
effect (accessing st.session_state, st.sidebar, etc. outside a running
Streamlit session), which is why this page rendered blank. app.py itself
is untouched — `streamlit run app.py` still works exactly as before.
"""

import base64
import os
from datetime import datetime

import pandas as pd
from nicegui import ui

from config.client_config import CE, CT
from config.theme_tokens import ACTIVE as COLORS
from core import activity_log, db, market_data
from data.seed.report_images import (
    PBD_PAGES, PBR_PAGES, Q1_P1, Q2_P1, Q2_P2, Q2_P3, SES_PAGES,
)
from page_modules_nicegui import nav

EVENT_LABELS = {
    "signal_resolved": "Risk signal resolved (Markets)",
    "signal_noted": "Risk signal noted — not pursued",
    "signal_muted": "Risk signal muted / snoozed",
    "email_sent": "Outreach email marked sent",
    "script_stage_complete": "Script Generation stage completed",
    "sec_filing_reviewed": "SEC filing reviewed",
    "model_request_sent": "Analyst model request sent",
    "model_received": "Analyst model received",
    "regfd_reviewed": "Reg FD interaction reviewed by legal",
    "regfd_8k_resolved": "8-K flag resolved",
    "transcript_ingested": "Call transcript ingested",
    "transcript_summarized": "Call transcript AI-summarized",
}

TEAM_OPTIONS = ["Louis Hoch (CEO)", "Michael White (CFO)", "Paul Manley (IR)", "Greg Carter (CRO)", "Legal"]
TOPIC_OPTIONS = [
    "Q1 2026 results (public)", "Q2 guidance range (public)", "ACH growth", "PayFac model",
    "Peer comparison", "Valuation", "Analyst coverage", "Conference scheduling",
    "FY2027 setup (public)", "CUSTOM",
]
MNPI_OPTIONS = ["No — public info only", "Uncertain — needs legal review", "Yes — 8-K may be required"]


def _load_json(key, default):
    return db.load_json(key, default)


def _save_json(key, data):
    db.save_json(key, data)


def _refresh():
    nav.go_to("Reports")


# ─────────────────────────────────────────────────────────────────────────
# Weekly IR Intelligence Briefs — used to be 3 hardcoded literal entries
# (fake stock prices, fixed dates) plus a "Generate Weekly Brief" button
# that only called ui.notify() and produced nothing. Now a persisted list
# (core.db, key "weekly_briefs.json") seeded once with those same 3 entries
# — flagged "seeded": True since they're historical/example content, not
# reinvented as real — and Generate actually composes a new entry from
# live data: current price (core.market_data), this week's IR activity
# count (core.activity_log), and the Script Generation tab's current stage.
# ─────────────────────────────────────────────────────────────────────────
def _seed_weekly_briefs():
    return [
        {"week": "Week of Jun 23, 2026", "status": "Draft ready",
         "summary": "$2.15 stock price · Ancora intro completed · NDR planning initiated · Script workflow Stage 2",
         "seeded": True},
        {"week": "Week of Jun 16, 2026", "status": "Sent",
         "summary": "$1.98 stock price · Rutabaga 6th site visit logged · Q2 consensus $25.1M · Quiet period 34 days",
         "seeded": True},
        {"week": "Week of Jun 9, 2026", "status": "Sent",
         "summary": "$2.03 stock price · HCW conference registration opened · Perkins position increase noted",
         "seeded": True},
    ]


def _load_weekly_briefs():
    briefs = _load_json("weekly_briefs.json", default=None)
    if briefs is not None:
        return briefs
    seeded = _seed_weekly_briefs()
    _save_json("weekly_briefs.json", seeded)
    return seeded


def _compose_weekly_brief():
    """Builds one real weekly-brief summary line from whatever live data is
    actually available right now — never invents a figure it doesn't have."""
    snap = market_data.get_snapshot(CT("ticker"))
    price_part = f"${snap['last_price']:.2f} stock price" if snap and snap.get("last_price") is not None else "stock price not yet fetched"

    events_n = activity_log.count_this_week()
    activity_part = f"{events_n} IR action(s) logged this week"

    ss = db.load_json("script_workflow_state.json", None)
    if ss and ss.get("stages"):
        active_stage = next((s["name"] for s in [
            {"id": "cfo_numbers", "name": "CFO Numbers In"}, {"id": "ir_review", "name": "IR Review"},
            {"id": "exec_review", "name": "CFO+CEO+CRO Review"}, {"id": "consolidate", "name": "Consolidation"},
            {"id": "legal_signoff", "name": "Legal Sign-Off"},
        ] if ss["stages"].get(s["id"], {}).get("status") == "active"), None)
        if ss.get("current_stage") == "FINAL":
            script_part = "Earnings script FINALIZED"
        elif active_stage:
            script_part = f"Script workflow at {active_stage}"
        else:
            script_part = "Script workflow not yet started"
    else:
        script_part = "Script workflow not yet started"

    return f"{price_part} · {activity_part} · {script_part}"


def _b64_image(b64_string):
    ui.image(f"data:image/jpeg;base64,{b64_string}").classes("w-full").style("border-radius:8px;")


def _reviewed_row(reviews, review_path, key):
    checked = reviews.get(key, {}).get("reviewed", False)
    reviewed_date = reviews.get(key, {}).get("date", "")
    with ui.row().classes("items-center gap-3"):
        cb = ui.checkbox("Mark as reviewed", value=checked)
        note = ui.label(f"Reviewed {reviewed_date}" if checked else "").style(f"color:{COLORS['text_muted']};font-size:12px;")

        def on_change(e):
            reviews.setdefault(key, {})["reviewed"] = e.value
            if e.value:
                reviews[key]["date"] = datetime.now().strftime("%b %d, %Y %I:%M %p")
                note.text = f"Reviewed {reviews[key]['date']}"
            else:
                note.text = ""
            _save_json(review_path, reviews)

        cb.on_value_change(on_change)


def render_reports_page():
    ui.html(
        "<div class='section-eyebrow'>REPORTS &amp; DELIVERABLES</div>"
        "<div class='section-title'>Board Package &middot; Weekly Reports &middot; Compliance &middot; Downloads</div>"
    )

    review_path = "report_reviews.json"
    reviews = _load_json(review_path, {})

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("📋 Board IR Reports")
        t2 = ui.tab("📊 Investor Materials")
        t3 = ui.tab("📈 Peer & Market Analysis")
        t4 = ui.tab("⚖️ Reg FD & Compliance")
        t5 = ui.tab("📁 All Downloads")
        t6 = ui.tab("🤖 Automation Tracker")

    with ui.tab_panels(tabs, value=t1).classes("w-full"):
        with ui.tab_panel(t1):
            _render_board_reports_tab(reviews, review_path)
        with ui.tab_panel(t2):
            _render_investor_materials_tab(reviews, review_path)
        with ui.tab_panel(t3):
            _render_peer_market_tab(reviews, review_path)
        with ui.tab_panel(t4):
            _render_regfd_tab()
        with ui.tab_panel(t5):
            _render_downloads_tab()
        with ui.tab_panel(t6):
            _render_automation_tracker_tab()


def _render_board_reports_tab(reviews, review_path):
    ui.label("Board IR Reports").classes("text-lg font-bold")
    ui.label("Embedded report pages, rendered directly here.").style(f"color:{COLORS['text_muted']}")

    embedded_pages = {
        "USIO_Board_IR_Report_Q1_2026.pdf": [Q1_P1],
        "USIO_Board_IR_Report_Q2_2026.pdf": [Q2_P1, Q2_P2, Q2_P3],
    }
    board_reports = [
        ("Q1 2026 Board IR Report", "USIO_Board_IR_Report_Q1_2026.pdf", "Prior quarter — 4 pages"),
        ("Q2 2026 Board IR Report", "USIO_Board_IR_Report_Q2_2026.pdf", "Current quarter — 6 pages"),
    ]
    for title, fname, note in board_reports:
        with ui.expansion(f"📄 {title} · {note}", value=fname.endswith("Q2_2026.pdf")).classes("w-full"):
            for b64 in embedded_pages.get(fname, []):
                _b64_image(b64)
            _reviewed_row(reviews, review_path, fname)

    ui.markdown("---")
    ui.label("Weekly IR Intelligence Briefs").classes("text-lg font-bold").style("margin-top:12px;")
    ui.label("The first 3 below are historical examples from before this ran on live data (marked 'example'). "
             "Generate composes a new one from what's actually on file today: live price, this week's logged IR "
             "activity, and the current script-workflow stage.").style(f"color:{COLORS['text_muted']}")

    briefs = _load_weekly_briefs()
    for b in briefs:
        status_color = "#C55A11" if b["status"] == "Draft ready" else "#375623"
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label(b["week"] + (" · example" if b.get("seeded") else "")).classes("font-bold")
                ui.label(b["status"]).style(f"background:{status_color};color:white;padding:2px 10px;border-radius:10px;font-size:13px;")
            ui.label(b["summary"]).style(f"color:{COLORS['text_muted']};font-size:12px;")

    def generate_weekly():
        week_label = f"Week of {datetime.now().strftime('%b %d, %Y')}"
        current = _load_weekly_briefs()
        if any(b["week"] == week_label for b in current):
            ui.notify(f"A brief for {week_label} already exists below.", type="warning")
            return
        current.insert(0, {
            "week": week_label, "status": "Draft ready", "summary": _compose_weekly_brief(),
            "seeded": False, "generated_at": datetime.now().isoformat(),
        })
        _save_json("weekly_briefs.json", current)
        ui.notify(f"{week_label} brief generated from live data. Review and send via IRConnect.", type="positive")
        _refresh()

    ui.button(f"📝 Generate Weekly Brief — Week of {datetime.now().strftime('%b %d')}", on_click=generate_weekly).props("color=primary").style("margin-top:8px;")


def _render_investor_materials_tab(reviews, review_path):
    ui.label("Investor Materials").classes("text-lg font-bold")
    inv_docs = [
        ("USIO Investor Presentation", "USIO_Investor_Deck_Shell.pdf", "Shell — management team & disclaimer slides need legal-approved content before external use"),
        ("New Analyst Onboarding Kit", "USIO_Analyst_Onboarding_Kit.pdf", "Current"),
        ("Q2 2026 Earnings Call Script", "USIO_Q2_2026_Earnings_Call_Script.pdf", "Draft v1 — Stage 2, IR Review, not legal-cleared"),
    ]
    # Project root is two levels up from this file (page_modules_nicegui/reports_page.py
    # -> page_modules_nicegui/ -> project root) — computed from this file's own
    # __file__ instead of app.__file__ now that `import app` is gone.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(project_root, "reports")
    for title, fname, note in inv_docs:
        with ui.expansion(f"📄 {title} · {note}").classes("w-full"):
            pdf_path = os.path.join(reports_dir, fname)
            if os.path.exists(pdf_path):
                def make_download(p=pdf_path, f=fname):
                    def _dl():
                        with open(p, "rb") as fh:
                            ui.download(fh.read(), f)
                    return _dl
                ui.button("📥 Download PDF", on_click=make_download()).props("flat")
            else:
                ui.label("PDF not found in reports/ yet.").style(f"color:{COLORS['text_muted']};font-size:12px;")
            _reviewed_row(reviews, review_path, fname)


def _render_peer_market_tab(reviews, review_path):
    ui.label("Peer & Market Analysis Reports").classes("text-lg font-bold")
    embedded_peer_pages = {
        "USIO_Peer_Benchmarking_Report_v2": PBR_PAGES,
        "USIO_Peer_Benchmarking_Board_Deck": PBD_PAGES,
        "USIO_Script_Effectiveness_Scorecard": SES_PAGES,
    }
    peer_docs = [
        ("Peer Benchmarking Report v2", "USIO_Peer_Benchmarking_Report_v2", "Current",
         "USIO efficiency ratio 61.2 (Adj. GM ÷ EV/Rev) — #1 in peer group, more than double next-best (GDOT 30.0). Holds true even before forensic adjustment (55.0). LONG USIO / SHORT FOUR pair trade."),
        ("Peer Benchmarking Board Deck", "USIO_Peer_Benchmarking_Board_Deck", "Current",
         "USIO at 0.4x EV/Revenue vs peer median 2.3x — 82% discount not justified by fundamentals."),
        ("Script Effectiveness Scorecard", "USIO_Script_Effectiveness_Scorecard", "Q1 2026 filled — Q2 pending",
         "Q1 2026: Score 61/100 · +24.22% AH reaction · Pre-empt score 8/12 · Key lesson: interest income bridge was NOT pre-empted — fixed in Q2 script."),
    ]
    for title, base, status, key_finding in peer_docs:
        with ui.expansion(f"📈 {title} · {status}").classes("w-full"):
            with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent_strong']};"
                f"border-left:3px solid {COLORS['accent']};"
            ):
                ui.label("KEY FINDING").classes("section-eyebrow")
                ui.label(key_finding).style(f"color:{COLORS['text_secondary']};font-size:13px;")
            for b64 in embedded_peer_pages.get(base, []):
                _b64_image(b64)
            _reviewed_row(reviews, review_path, base)


def _render_automation_tracker_tab():
    """Same visual pattern as _render_peer_market_tab (expansion card with
    a KEY FINDING headline) but live-computed from core/activity_log.py
    instead of static embedded report images — no _reviewed_row here since
    there's nothing to sign off on, this is a live dashboard, not a
    document. See this module's docstring, tab 6."""
    ui.label("Automation Tracker").classes("text-lg font-bold")
    ui.label(
        "Live, not a static report — every number below is a real query against the activity ledger "
        "(core/activity_log.py), the same one behind Today's automation stats (now hideable there — "
        "click Show/Hide automation stats at the top of Today). Moved here so there's room for the "
        "per-category breakdown a quick-glance strip doesn't have space for."
    ).style(f"color:{COLORS['text_muted']}")

    tasks_today = activity_log.count_today()
    tasks_week = activity_log.count_this_week()
    hrs_week = activity_log.minutes_saved_this_week() / 60
    breakdown = activity_log.breakdown_this_week()

    if breakdown:
        top = breakdown[0]
        top_label = EVENT_LABELS.get(top["event_type"], top["event_type"].replace("_", " ").title())
        key_finding = (
            f"{hrs_week:.1f} hrs saved this week across {tasks_week} logged action"
            f"{'s' if tasks_week != 1 else ''} — most from \"{top_label}\" "
            f"({top['count']}× · {top['minutes']} min)."
        )
    else:
        key_finding = (
            "No actions logged yet this week — this fills in automatically as signals get resolved, "
            "emails get marked sent, script stages complete, and so on across the app."
        )

    with ui.expansion(f"🤖 This Week's Automation · {tasks_week} action{'s' if tasks_week != 1 else ''} logged", value=True).classes("w-full"):
        with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent_strong']};"
            f"border-left:3px solid {COLORS['accent']};"
        ):
            ui.label("KEY FINDING").classes("section-eyebrow")
            ui.label(key_finding).style(f"color:{COLORS['text_secondary']};font-size:13px;")

        with ui.row().classes("w-full gap-3").style("margin-top:8px;"):
            for val, lbl in [
                (str(tasks_today), "actions today"),
                (str(tasks_week), "actions this week"),
                (f"{hrs_week:.1f} hrs", "saved this week"),
            ]:
                with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};"):
                    ui.label(val).classes("text-lg font-bold").style(f"color:{COLORS['success']};")
                    ui.label(lbl).style(f"color:{COLORS['text_muted']};font-size:10px;")

        ui.label("BREAKDOWN BY CATEGORY — THIS WEEK").classes("section-eyebrow").style("margin-top:14px;")
        if breakdown:
            for item in breakdown:
                label = EVENT_LABELS.get(item["event_type"], item["event_type"].replace("_", " ").title())
                with ui.row().classes("w-full justify-between items-center").style(f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                    ui.label(label).style(f"color:{COLORS['text_body']};font-size:12.5px;")
                    ui.label(f"{item['count']}× · {item['minutes']} min").style(f"color:{COLORS['text_muted']};font-size:12px;")
        else:
            ui.label("Nothing logged yet this week.").style(f"color:{COLORS['text_muted']};font-size:12px;")

    with ui.expansion("ℹ️ Where these numbers come from", value=False).classes("w-full"):
        ui.label(
            "Every logged action across Today, Markets, and Earnings — resolving or muting a risk "
            "signal, marking an email sent, completing a script stage, reviewing an SEC filing, "
            "receiving an analyst model, resolving a Reg FD flag or 8-K, ingesting or summarizing a "
            "call transcript — writes one row to the activity ledger the moment it happens. "
            "EVENT_MINUTES_SAVED (core/activity_log.py) is a judgment-call estimate of how long each "
            "action type takes to do by hand, not a measured fact — adjust it there if a number here "
            "looks off."
        ).style(f"color:{COLORS['text_muted']};font-size:12px;")


def _render_regfd_tab():
    regfd_path = "regfd_log.json"
    log = _load_json(regfd_path, [])

    ui.label("⚖️ Regulation FD Compliance Logger").classes("text-xl font-bold")
    ui.label("Log every material investor interaction · Track quiet period · Flag MNPI · Maintain audit trail for legal review").style(
        f"color:{COLORS['text_muted']}"
    )

    earnings = CE()
    try:
        quiet_start = datetime.strptime(earnings.get("quiet_start", ""), "%Y-%m-%d").date()
        quiet_end = datetime.strptime(earnings.get("quiet_end", ""), "%Y-%m-%d").date()
    except ValueError:
        quiet_start = quiet_end = None

    today_d = datetime.now().date()
    in_quiet = bool(quiet_start and quiet_end and quiet_start <= today_d <= quiet_end)
    days_to_q = max((quiet_start - today_d).days, 0) if quiet_start and not in_quiet else 0

    if in_quiet:
        ui.label(
            f"🔴 QUIET PERIOD ACTIVE {quiet_start.strftime('%b %d')}–{quiet_end.strftime('%b %d, %Y')}. "
            f"No MNPI may be shared. All investor contact must be logged immediately."
        ).style(f"background:{COLORS['danger']};color:white;padding:10px 16px;border-radius:8px;")
    elif quiet_start and days_to_q > 0:
        ui.label(f"🟡 Quiet period begins in {days_to_q} days ({quiet_start.strftime('%B %d')}). Complete all analyst outreach before then.").style(
            f"background:{COLORS['warning']};color:white;padding:10px 16px;border-radius:8px;"
        )
    else:
        ui.label("🟢 Open window — normal communications permitted.").style(
            f"background:{COLORS['success']};color:white;padding:10px 16px;border-radius:8px;"
        )

    with ui.tabs().classes("w-full") as fd_tabs:
        fd1 = ui.tab("📝 Log Interaction")
        fd2 = ui.tab("📋 Full Log")
        fd3 = ui.tab("⚠️ Flags")
        fd4 = ui.tab("📊 Summary")

    log_container_ref = {}

    def refresh_all_tabs():
        log_container_ref["full"]()
        log_container_ref["flags"]()
        log_container_ref["summary"]()

    with ui.tab_panels(fd_tabs, value=fd1).classes("w-full"):
        with ui.tab_panel(fd1):
            ui.label("Log New Investor Interaction").classes("text-lg font-bold")
            ui.label("Every material conversation must be logged within 24 hours — this is a legal record.").style(
                f"color:{COLORS['text_muted']}"
            )
            with ui.row().classes("w-full gap-4"):
                fd_date = ui.input("Date (YYYY-MM-DD)", value=str(today_d)).classes("flex-1")
                fd_type = ui.select(
                    ["1x1 investor meeting", "Earnings call", "Conference", "Analyst call", "NDR meeting", "Email", "Impromptu contact"],
                    value="1x1 investor meeting", label="Type",
                ).classes("flex-1")
                fd_chan = ui.select(["In-person", "Phone", "Video", "Email", "Conference"], value="In-person", label="Channel").classes("flex-1")
            with ui.row().classes("w-full gap-4"):
                fd_inst = ui.input("Institution *").classes("flex-1")
                fd_cont = ui.input("Contact name(s)").classes("flex-1")
                fd_quiet = ui.checkbox("During quiet period", value=in_quiet)
            fd_team = ui.select(TEAM_OPTIONS, multiple=True, label="Usio participants").classes("w-full")
            fd_topics = ui.select(TOPIC_OPTIONS, multiple=True, label="Topics").classes("w-full")
            fd_mnpi = ui.radio(MNPI_OPTIONS, value=MNPI_OPTIONS[0]).classes("w-full")
            fd_summ = ui.textarea("Summary *", placeholder="Key topics, questions asked, information shared. Be specific — this is a legal record.").classes("w-full")
            fd_fuac = ui.textarea("Follow-up actions").classes("w-full")
            fd_8k = ui.checkbox("8-K disclosure required or under review")

            def log_interaction():
                if not fd_inst.value or not fd_summ.value:
                    ui.notify("Institution and summary required.", type="warning")
                    return
                risk = "HIGH" if fd_mnpi.value != MNPI_OPTIONS[0] or fd_quiet.value else "LOW"
                entry = {
                    "id": datetime.now().strftime("%Y%m%d%H%M%S"),
                    "date": fd_date.value, "type": fd_type.value, "channel": fd_chan.value,
                    "institution": fd_inst.value, "contact": fd_cont.value,
                    "usio_team": fd_team.value or [], "in_quiet": fd_quiet.value,
                    "topics": fd_topics.value or [], "mnpi_status": fd_mnpi.value,
                    "summary": fd_summ.value, "followup": fd_fuac.value, "8k_required": fd_8k.value,
                    "risk_level": risk, "logged_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "reviewed": False,
                }
                log.append(entry)
                _save_json(regfd_path, log)
                if risk == "HIGH":
                    ui.notify("🔴 HIGH RISK — legal review required immediately.", type="negative")
                else:
                    ui.notify("Logged.", type="positive")
                fd_inst.value = ""
                fd_summ.value = ""
                refresh_all_tabs()

            ui.button("💾 Log Interaction", on_click=log_interaction).props("color=primary").style("margin-top:8px;")

        with ui.tab_panel(fd2):
            full_log_container = ui.column().classes("w-full gap-2")

            def render_full_log():
                full_log_container.clear()
                with full_log_container:
                    if not log:
                        ui.label("No interactions logged yet.").style(f"color:{COLORS['text_muted']}")
                        return
                    for entry in reversed(log):
                        icon = "🔴" if entry.get("risk_level") == "HIGH" else "🟢"
                        qb = " · 🔇 QUIET" if entry.get("in_quiet") else ""
                        rb = " · ✅ Reviewed" if entry.get("reviewed") else " · ⬜ Pending"
                        with ui.expansion(f"{icon} {entry.get('date')} · {entry.get('institution')} · {entry.get('type')}{qb}{rb}").classes("w-full"):
                            ui.label(f"Topics: {', '.join(entry.get('topics', []))}")
                            ui.label(f"MNPI: {entry.get('mnpi_status', '—')}")
                            ui.label(f"Summary: {entry.get('summary', '—')}")
                            if entry.get("8k_required"):
                                if entry.get("8k_resolved"):
                                    ui.label(f"✅ 8-K resolved {entry.get('8k_resolved_date','')}").style(f"color:{COLORS['success']};font-weight:bold;")
                                else:
                                    ui.label("⚠️ 8-K DISCLOSURE FLAGGED").style(f"color:{COLORS['danger']};font-weight:bold;")
                            if not entry.get("reviewed"):
                                def mark_reviewed(e=entry):
                                    e["reviewed"] = True
                                    _save_json(regfd_path, log)
                                    refresh_all_tabs()
                                ui.button("✅ Mark Reviewed by Legal", on_click=mark_reviewed).props("flat")

            log_container_ref["full"] = render_full_log
            render_full_log()

        with ui.tab_panel(fd3):
            flags_container = ui.column().classes("w-full gap-2")

            def render_flags():
                flags_container.clear()
                with flags_container:
                    high_risk = [e for e in log if e.get("risk_level") == "HIGH" and not e.get("reviewed")]
                    k8_open = [e for e in log if e.get("8k_required") and not e.get("8k_resolved")]
                    k8_resolved = [e for e in log if e.get("8k_required") and e.get("8k_resolved")]
                    with ui.row().classes("w-full gap-4"):
                        _metric("HIGH risk unreviewed", len(high_risk))
                        _metric("8-K flagged (open)", len(k8_open))
                        _metric("Total unreviewed", sum(1 for e in log if not e.get("reviewed")))

                    if high_risk or k8_open:
                        ui.label(
                            "Closed loop: resolve a flag right here — no need to go find the same entry in Full Log."
                        ).style(f"color:{COLORS['text_muted']};font-size:11px;margin:4px 0;")

                    for e in high_risk:
                        with ui.card().classes("w-full").style(f"background:#2D1212;border:1px solid {COLORS['danger']}55;"):
                            with ui.row().classes("w-full items-center justify-between"):
                                with ui.column().classes("gap-0"):
                                    ui.label(f"🔴 {e['date']} · {e['institution']}").classes("font-bold").style("color:#FFFFFF;font-size:13.5px;")
                                    ui.label(f"MNPI: {e['mnpi_status']}").style(f"color:{COLORS['text_muted']};font-size:12px;")

                                def mark_reviewed(e=e):
                                    e["reviewed"] = True
                                    _save_json(regfd_path, log)
                                    ui.notify("Marked reviewed by legal.")
                                    refresh_all_tabs()

                                ui.button("✅ Mark Reviewed", on_click=mark_reviewed).props("flat dense").style(f"color:{COLORS['danger']};")

                    for e in k8_open:
                        with ui.card().classes("w-full").style(f"background:#2D2210;border:1px solid {COLORS['warning']}55;"):
                            with ui.row().classes("w-full items-center justify-between"):
                                with ui.column().classes("gap-0"):
                                    ui.label(f"⚠️ {e['date']} · {e['institution']} · 8-K required").classes("font-bold").style("color:#FFFFFF;font-size:13.5px;")
                                    ui.label((e.get("summary") or "")[:120]).style(f"color:{COLORS['text_muted']};font-size:12px;")

                                def mark_8k_resolved(e=e):
                                    e["8k_resolved"] = True
                                    e["8k_resolved_date"] = datetime.now().strftime("%b %d, %Y")
                                    _save_json(regfd_path, log)
                                    ui.notify("8-K marked filed/resolved.")
                                    refresh_all_tabs()

                                ui.button("✅ Mark 8-K Filed/Resolved", on_click=mark_8k_resolved).props("flat dense").style(f"color:{COLORS['warning']};")

                    if not high_risk and not k8_open:
                        ui.label("No open flags. 🎉").style(f"color:{COLORS['text_muted']};")

                    if k8_resolved:
                        with ui.expansion(f"✅ {len(k8_resolved)} 8-K item(s) resolved").classes("w-full").style("margin-top:8px;"):
                            for e in k8_resolved:
                                ui.label(f"{e['date']} · {e['institution']} · resolved {e.get('8k_resolved_date','')}").style(
                                    f"color:{COLORS['text_muted']};font-size:12px;"
                                )

            log_container_ref["flags"] = render_flags
            render_flags()

        with ui.tab_panel(fd4):
            summary_container = ui.column().classes("w-full gap-2")

            def render_summary():
                summary_container.clear()
                with summary_container:
                    total_fd = len(log)
                    if total_fd:
                        rev_n = sum(1 for e in log if e.get("reviewed"))
                        with ui.row().classes("w-full gap-4"):
                            _metric("Total logged", total_fd)
                            _metric("Reviewed", rev_n)
                            _metric("Compliance rate", f"{rev_n/total_fd*100:.0f}%")

                        def export_csv():
                            df = pd.DataFrame(log)
                            ui.download(df.to_csv(index=False).encode(), f"{CT('ticker')}_RegFD_{datetime.now().strftime('%Y%m%d')}.csv")

                        ui.button("📥 Download Full Reg FD Log (CSV)", on_click=export_csv).props("color=primary")
                    else:
                        ui.label("No interactions logged yet.").style(f"color:{COLORS['text_muted']}")

            log_container_ref["summary"] = render_summary
            render_summary()


def _metric(label, value):
    with ui.card().classes("flex-1").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};padding:12px;"):
        ui.label(str(value)).classes("text-xl font-bold").style(f"color:{COLORS['text_heading']}")
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:12px;text-transform:uppercase;")


def _render_downloads_tab():
    ui.label("All Downloads").classes("text-lg font-bold")
    ui.label("Every deliverable this platform can produce. Files that don't exist in reports/ yet are marked "
             "'Not generated yet' rather than offering a download that wouldn't actually contain anything — "
             "same real-file check the Investor Materials tab uses.").style(f"color:{COLORS['text_muted']}")

    download_items = [
        ("📋", "USIO_Board_IR_Report_Q2_2026.docx", "Board IR Package", "6 pages · Word doc"),
        ("📊", "USIO_Peer_Benchmarking_Report_v2.xlsx", "Peer Benchmarking", "Excel · 5 tabs"),
        ("📊", "USIO_Peer_Benchmarking_Board_Deck.pptx", "Peer Benchmarking Deck", "PowerPoint · 5 slides"),
        ("📝", "USIO_Q2_2026_Earnings_Call_Script_v2.docx", "Earnings Call Script", "Word doc · Draft v1"),
        ("📊", "USIO_Script_Effectiveness_Scorecard.xlsx", "Script Effectiveness", "Excel · 5 tabs"),
        ("📝", "USIO_New_Analyst_Onboarding_Kit.docx", "Analyst Onboarding Kit", "9 pages · Word doc"),
        ("🖼", "USIO_Investor_Presentation.pptx", "Investor Presentation", "PowerPoint · 8 slides"),
    ]
    # Same project_root/reports_dir computation as _render_investor_materials_tab
    # above — real file presence check instead of a notify() that pretended
    # the download would work regardless.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    reports_dir = os.path.join(project_root, "reports")
    for icon, filename, label, meta in download_items:
        with ui.row().classes("w-full items-center justify-between").style(f"border-bottom:1px solid {COLORS['border']};padding:8px 0;"):
            with ui.column().classes("gap-0"):
                ui.label(f"{icon} {label} · {filename}").classes("font-bold")
                ui.label(meta).style(f"color:{COLORS['text_muted']};font-size:12px;")

            file_path = os.path.join(reports_dir, filename)
            if os.path.exists(file_path):
                def make_download(p=file_path, f=filename):
                    def _dl():
                        with open(p, "rb") as fh:
                            ui.download(fh.read(), f)
                    return _dl
                ui.button("📥 Download", on_click=make_download()).props("flat")
            else:
                ui.label("Not generated yet").style(f"color:{COLORS['text_muted']};font-size:12px;font-style:italic;")

    ui.markdown("---")
    ui.label("Reg FD Export").classes("text-lg font-bold")
    regfd_path = "regfd_log.json"
    log = _load_json(regfd_path, [])
    if log:
        def export_csv():
            df = pd.DataFrame(log)
            ui.download(df.to_csv(index=False).encode(), f"{CT('ticker')}_RegFD_Log_{datetime.now().strftime('%Y%m%d')}.csv")
        ui.button("📥 Download Full Reg FD Log (CSV)", on_click=export_csv).props("color=primary")
    else:
        ui.label("Log interactions in the Reg FD tab to generate the compliance export.").style(f"color:{COLORS['text_muted']}")
