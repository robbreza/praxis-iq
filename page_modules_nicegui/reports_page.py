"""
page_modules_nicegui/reports_page.py — Reports & Deliverables page, NiceGUI version.

Six tabs. The first five were ported from the original Streamlit "Reports"
section:
1. Board IR Reports        — embedded report-page images + reviewed tracking
3. Peer & Market Analysis  — embedded report-page images + key findings
4. Reg FD & Compliance     — the important one: quiet-period banner, log-an-
                              interaction form, full log with filters, risk
                              flags, and a CSV export. Legal audit trail.
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
import plotly.graph_objects as go
from nicegui import ui

from config.client_config import CE, CT, C, team_labels
from config.theme_tokens import ACTIVE as COLORS
from core import activity_log, benchmarking_engine, db, edgar_financials, market_data, ui_context
from core import nobo_engine, report_pdf, risk_scorecard, sec_filings
from data.seed.report_images import SES_PAGES
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

# Participant roster is derived from the active client's profile
# (config.client_config.team_labels) rather than hardcoded to USIO's people —
# see reports_page's use in the Reg FD "participants" picker below.
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
    """The brief's one-line headline for the card. The full sectioned brief (and
    its PDF) come from core.weekly_brief.compose() — this just borrows the same
    headline so the card and the document always agree."""
    from core import weekly_brief
    return weekly_brief.compose()["headline"]


def _render_live_weekly_brief():
    """This week's brief, rendered in full from core.weekly_brief.compose() —
    the readable document behind the card, plus the PDF. Same dict the PDF
    builds from, so screen and print can't drift."""
    from core import report_pdf, weekly_brief
    try:
        b = weekly_brief.compose()
    except Exception as e:
        ui.label(f"Weekly brief unavailable: {e}").style(f"color:#B45309;font-size:12px;")
        return

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:4px solid {COLORS['accent']};margin-top:6px;"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label(f"{b['week_label']} · live").classes("font-bold").style(
                f"color:{COLORS['text_heading']};")
            ui.label("Composed now").style(
                f"background:{COLORS['accent']};color:white;padding:2px 10px;border-radius:10px;font-size:12px;")
        ui.label(b["headline"]).style(f"color:{COLORS['text_muted']};font-size:12px;")

        if b["stats"]:
            with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
                for val, lbl, sub in b["stats"]:
                    with ui.card().classes("flex-1").style(
                            f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};"
                            "min-width:120px;padding:8px 10px;"):
                        ui.label(val).classes("font-bold").style(f"color:{COLORS['accent']};font-size:18px;")
                        ui.label(lbl).style(f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")
                        ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:10px;")

        for sec in b["sections"]:
            ui.label(sec["title"]).classes("section-head").style("margin-top:8px;")
            for line in sec["lines"]:
                ui.label("• " + line).style(f"color:{COLORS['text_muted']};font-size:11.5px;margin-left:4px;")

        def _dl():
            try:
                ui.download(report_pdf.weekly_brief_pdf(),
                            f"{CT('ticker')}_Weekly_IR_Brief_{datetime.now():%Y%m%d}.pdf")
            except Exception as e:
                ui.notify(f"PDF failed: {e}", type="negative")

        with ui.row().classes("gap-2").style("margin-top:10px;"):
            ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl).props("color=primary dense")
        ui.label("Live brief — every figure recomputes from the latest price, filing and activity log; the PDF "
                 "is generated on the spot from the same numbers.").style(
            f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:4px;")


def _b64_image(b64_string):
    ui.image(f"data:image/jpeg;base64,{b64_string}").classes("w-full").style("border-radius:8px;")


def _reviewed_row(reviews, review_path, key):
    checked = reviews.get(key, {}).get("reviewed", False)
    reviewed_date = reviews.get(key, {}).get("date", "")
    with ui.row().classes("items-center gap-3"):
        cb = ui.checkbox("Mark as reviewed", value=checked)
        note = ui.label(f"Reviewed {reviewed_date}" if checked else "").style(f"color:{COLORS['text_muted']};font-size:12px;")
        # View-only roles can see review status but not change it.
        if ui_context.is_read_only():
            cb.disable()
            return

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

    # RBAC: roles with only 'read' access to Reports (e.g. CEO, CRO) can view
    # everything here — including the Reg FD log and its CSV export — but not
    # create/modify records. Legal and IR/CFO keep full write access. Every
    # mutating control below calls ui_context.is_read_only() directly (not a
    # captured local), since some live in module-level helper functions
    # outside this closure; downloads stay available to all.
    if ui_context.is_read_only():
        ui_context.read_only_banner(ui)

    review_path = "report_reviews.json"
    reviews = _load_json(review_path, {})

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("Board IR Reports")
        t_plan = ui.tab("90-Day IR Plan")
        t3 = ui.tab("Peer & Market Analysis")
        t4 = ui.tab("Reg FD & Compliance")
        t6 = ui.tab("Automation Tracker")

    _panels = ui.tab_panels(tabs, value=nav.consume_target_tab() or t1).classes("w-full")
    _panels.on_value_change(lambda e: nav.tab_changed(e.value))
    with _panels:
        with ui.tab_panel(t1):
            _render_board_reports_tab(reviews, review_path)
        with ui.tab_panel(t_plan):
            _render_ir_plan(reviews, review_path)
            ui.markdown("---")
            with ui.expansion("NDR Coverage by City — where the money is vs where we're going · Live",
                              value=True).classes("w-full"):
                _render_ndr_by_city()
        with ui.tab_panel(t3):
            _render_peer_market_tab(reviews, review_path)
        with ui.tab_panel(t4):
            _render_regfd_tab()
        with ui.tab_panel(t6):
            _render_automation_tracker_tab()


def _render_board_reports_tab(reviews, review_path):
    ui.label("Board IR Reports").classes("text-lg font-bold")
    ui.label("Composed live from the latest SEC filing, valuation, and ownership data — not a static image, and "
             "always current.").style(f"color:{COLORS['text_muted']}")

    with ui.expansion("IR Quarterly Board Package · Live", value=True).classes("w-full"):
        _render_board_ir_report()
        _reviewed_row(reviews, review_path, "USIO_Board_IR_Report")

    with ui.expansion("Earnings Prep Brief — what management needs in the room · Live",
                      value=True).classes("w-full"):
        _render_earnings_prep()

    with ui.expansion("New Analyst Onboarding Kit — what we hand a new analyst · Live").classes(
            "w-full"):
        _render_onboarding_kit()

    with ui.expansion("IRConnect Client Onboarding — readiness, live").classes("w-full"):
        _render_onboarding_checklist()

    ui.markdown("---")
    ui.label("Weekly IR Intelligence Briefs").classes("text-lg font-bold").style("margin-top:12px;")
    ui.label("The first 3 below are historical examples from before this ran on live data (marked 'example'). "
             "Generate composes a full brief from what's actually on file today — price & volume, the earnings "
             "and quiet-period calendar, this week's logged IR activity, the investor pipeline, the NDR "
             "schedule, and peer moves/filings — readable below and downloadable as a PDF.").style(
        f"color:{COLORS['text_muted']}")

    # The live brief for THIS week, composed fresh on render — the full sectioned
    # document the old one-line card never had, with a PDF for the board packet.
    _render_live_weekly_brief()

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

    _wk_btn = ui.button(f"Generate Weekly Brief — Week of {datetime.now().strftime('%b %d')}", on_click=generate_weekly).props("color=primary").style("margin-top:8px;")
    if ui_context.is_read_only():
        _wk_btn.disable()


def _render_peer_market_tab(reviews, review_path):
    ui.label("Peer & Market Analysis Reports").classes("text-lg font-bold")

    # Peer Benchmarking Report v2 — now a LIVE analysis. It used to render a
    # single static image (the gross-margin page); the other four pages never
    # existed in report_images.py, so the rest of the analysis was simply
    # missing. Computed now from the peer universe + USIO financials + live
    # price/guidance (core/benchmarking_engine.py). See CHANGELOG 2026-07-15.
    with ui.expansion("Company Financial Analysis & Peer Benchmarking · Live", value=True).classes("w-full"):
        _render_company_financials()
        _render_benchmark_analysis()
        _reviewed_row(reviews, review_path, "USIO_Peer_Benchmarking_Report_v2")

    # Board summary — rebuilt LIVE off the same engine (was a static deck whose
    # 0.4x/82% figures contradicted the live read above once we fixed the math).
    with ui.expansion("Peer Benchmarking — Board Summary · Live").classes("w-full"):
        _render_board_deck_live()
        _reviewed_row(reviews, review_path, "USIO_Peer_Benchmarking_Board_Deck")

    # Script Effectiveness Scorecard — Q1 2026 historical example (static image).
    # The live Q2 scorecard is produced in the Script workflow after the call;
    # labeled honestly rather than implying it's current.
    with ui.expansion("Valuation Comp — what USIO is worth at its peers' multiple · Live",
                      value=True).classes("w-full"):
        _render_valuation_comp()

    with ui.expansion("Footnote Forensics — are peer margins even comparable? · Live",
                      value=True).classes("w-full"):
        _render_forensics()

    with ui.expansion("Script Effectiveness Scorecard · Live", value=True).classes("w-full"):
        _render_script_scorecard()
        with ui.expansion("Q1 2026 scorecard (historical example — static)").classes("w-full").style(
                "margin-top:8px;"):
            ui.label("The original spreadsheet image, kept for reference. Its two headline numbers "
                     "(+24.22% after-hours reaction, pre-empt score 8/12) are not reproduced live above "
                     "because both require call transcripts, and none are ingested yet.").style(
                f"color:{COLORS['text_muted']};font-size:11px;")
            for b64 in SES_PAGES:
                _b64_image(b64)
        _reviewed_row(reviews, review_path, "USIO_Script_Effectiveness_Scorecard")


def _render_valuation_comp():
    """Valuation Comp (core.valuation_comp) — the comp table plus the number it exists
    to produce: implied equity value at the peer median EV/Gross Profit.

    Leads with the RANGE, not a point estimate. The headline discount is not robust —
    it swings from ~+4% to ~+45% on whether two peers whose gross margins come from
    market data rather than filings are allowed to set the median.
    """
    from core import valuation_comp
    try:
        d = valuation_comp.build()
    except Exception as e:
        ui.label(f"Valuation comp unavailable: {e}").style("color:#B45309;font-size:12px;")
        return

    u, m, imp, sens = d["usio"], d["median"], d["implied"], d.get("sensitivity")

    if imp:
        lo = hi = imp["upside_pct"]
        if sens:
            lo, hi = sorted([sens["upside_backed"], sens["upside_all"]])
        with ui.row().classes("w-full gap-3"):
            _bm_stat(f"{CT('ticker')} EV/Gross Profit", f"{imp['current_multiple']:.1f}x",
                     f"rank #{u.get('rank','—')} of {d['n_primary']+1} · cheapest = best", None)
            _bm_stat("Peer median EV/GP", f"{imp['peer_median_multiple']:.1f}x",
                     f"primary peers only (n={d['n_primary']})", None)
            _bm_stat("Implied upside",
                     f"{lo:+.0f}% to {hi:+.0f}%" if sens and not sens["robust"] else f"{imp['upside_pct']:+.0f}%",
                     "at peer median, equity basis",
                     "#15803D" if lo > 0 else "#B91C1C")
        ui.label(d["read"]).style(f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")

    if sens and not sens["robust"]:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid #B45309;"
                "border-left:3px solid #B45309;padding:6px 10px;margin-top:4px;"):
            ui.label(f"The size of the discount is NOT robust — {sens['upside_backed']:+.0f}% vs "
                     f"{sens['upside_all']:+.0f}% depending on two unverifiable margins").style(
                "color:#B45309;font-size:12px;font-weight:700;")
            ui.label(sens["note"]).style(f"color:{COLORS['text_body']};font-size:11px;")

    ui.label("Comp table — ranked by EV/Gross Profit (cheapest first)").classes(
        "section-head").style("margin-top:8px;")
    cols = [{"name": "ticker", "label": "", "field": "ticker", "align": "left"},
            {"name": "name", "label": "Company", "field": "name", "align": "left"},
            {"name": "ev", "label": "EV ($M)", "field": "ev", "align": "right"},
            {"name": "ev_gp", "label": "EV/GP", "field": "ev_gp", "align": "right"},
            {"name": "ev_rev", "label": "EV/Rev*", "field": "ev_rev", "align": "right"},
            {"name": "gm", "label": "Gross margin*", "field": "gm", "align": "right"},
            {"name": "growth", "label": "Rev growth", "field": "growth", "align": "right"},
            {"name": "basis", "label": "GM basis", "field": "basis", "align": "left"}]
    BASIS = {"ok": "filing", "derived": "filing (derived)", "stale": "⚠ market · filing stale",
             "no_gross_profit_line": "⚠ market · none filed", "no_cik": "⚠ no EDGAR data"}
    rows = []
    for r in d["ranked"]:
        rows.append({
            "ticker": ("★ " if r["is_client"] else "") + r["ticker"],
            "name": r["name"],
            "ev": f"{r['enterprise_value']/1e6:,.0f}" if r["enterprise_value"] else "—",
            "ev_gp": f"{r['ev_gp']:.1f}x" if r["ev_gp"] else "—",
            "ev_rev": f"{r['ev_rev']:.2f}x" if r["ev_rev"] else "—",
            "gm": f"{r['gross_margin']:.1f}%" if r["gross_margin"] is not None else "—",
            "growth": f"{r['rev_growth']:+.0f}%" if r["rev_growth"] is not None else "—",
            "basis": BASIS.get(r["gm_basis"], r["gm_basis"] or "—")})
    rows.append({"ticker": "", "name": "— primary peer median —",
                 "ev": "", "ev_gp": f"{m['ev_gp']:.1f}x" if m["ev_gp"] else "—",
                 "ev_rev": f"{m['ev_rev']:.2f}x" if m["ev_rev"] else "—",
                 "gm": f"{m['gross_margin']:.1f}%" if m["gross_margin"] is not None else "—",
                 "growth": f"{m['rev_growth']:+.0f}%" if m["rev_growth"] is not None else "—",
                 "basis": ""})
    ui.table(columns=cols, rows=rows).classes("w-full dense-table").props("flat dense")
    ui.label("* EV/Revenue and gross margin are NOT comparable across these rows and are shown for "
             "context only — gross-vs-net revenue treatment varies across these companies. Revenue "
             "cancels out of EV/Gross Profit, which is why the ranking and the implied value use it "
             "and nothing else.").style(f"color:{COLORS['text_muted']};font-size:10.5px;")

    try:
        from core import valuation_comp as _vc
        bg = _vc.revenue_bridge()
    except Exception:
        bg = None
    if bg and bg.get("usio"):
        ui.label("The EV/Revenue bridge — why the 'revenue discount' was never real").classes(
            "section-head").style("margin-top:10px;")
        ui.label("Everyone quotes EV/Revenue, and across this peer set it is not comparable. But it "
                 "is derivable: EV/Revenue = EV/Gross Profit x gross margin. Apply the peer median "
                 "EV/Gross Profit — the multiple that IS comparable — to each company's OWN margin. "
                 "The margin never leaves its own filer, so nothing is compared that shouldn't be.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        cols = [{"name": "t", "label": "", "field": "t", "align": "left"},
                {"name": "g", "label": "EV/GP", "field": "g", "align": "right"},
                {"name": "m", "label": "Gross margin", "field": "m", "align": "right"},
                {"name": "a", "label": "EV/Rev today", "field": "a", "align": "right"},
                {"name": "w", "label": "EV/Rev warranted", "field": "w", "align": "right"},
                {"name": "v", "label": "vs warranted", "field": "v", "align": "right"}]
        ui.table(columns=cols, rows=[{
            "t": ("* " if r["is_client"] else "") + r["ticker"],
            "g": f"{r['ev_gp']:.2f}x", "m": f"{r['gross_margin']:.1f}%",
            "a": f"{r['ev_rev_actual']:.2f}x" if r["ev_rev_actual"] else "—",
            "w": f"{r['ev_rev_warranted']:.2f}x",
            "v": f"{r['vs_warranted_pct']:+.0f}%" if r["vs_warranted_pct"] is not None else "—",
        } for r in bg["rows"]]).classes("w-full dense-table").props("flat dense")
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                "border-left:3px solid #1E40AF;padding:6px 10px;margin-top:4px;"):
            ui.label("The finding").style("color:#1E40AF;font-size:12px;font-weight:700;")
            ui.label(bg["read"]).style(f"color:{COLORS['text_body']};font-size:11.5px;")

    if imp:
        with ui.expansion("The bridge — how the implied value is built").classes("w-full").style(
                "margin-top:6px;"):
            for label, val in [
                (f"{CT('ticker')} gross profit (EV ÷ current EV/GP)", f"${imp['gross_profit']/1e6:,.1f}M"),
                ("× peer median EV/Gross Profit", f"{imp['peer_median_multiple']:.2f}x"),
                ("= implied enterprise value", f"${imp['implied_ev']/1e6:,.1f}M"),
                (("+ net cash" if imp["net_debt"] < 0 else "− net debt"),
                 f"${abs(imp['net_debt'])/1e6:,.1f}M"),
                ("= implied equity value", f"${imp['implied_equity']/1e6:,.1f}M"),
                ("vs market cap today", f"${imp['current_equity']/1e6:,.1f}M"),
                ("implied upside", f"{imp['upside_pct']:+.0f}%"),
            ]:
                with ui.row().classes("w-full justify-between"):
                    ui.label(label).style(f"color:{COLORS['text_muted']};font-size:11px;")
                    ui.label(val).style(f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")

    if d["reference"]:
        with ui.expansion("Reference large caps — industry bar, not valuation comps").classes(
                "w-full").style("margin-top:4px;"):
            ui.label("Excluded from every median and rank: you don't apply a $100B processor's "
                     "multiple to a micro cap. Shown because they set the growth and margin bar.").style(
                f"color:{COLORS['text_muted']};font-size:10.5px;")
            for r in d["reference"]:
                ui.label("• {} {} — EV/GP {} · growth {}".format(
                    r["ticker"], r["name"],
                    f"{r['ev_gp']:.1f}x" if r["ev_gp"] else "—",
                    f"{r['rev_growth']:+.0f}%" if r["rev_growth"] is not None else "—")).style(
                    f"color:{COLORS['text_body']};font-size:11px;")


def _render_forensics():
    """Footnote Forensics (core.forensics) — from primary SEC filings only.

    Deliberately leads with what CANNOT be claimed. Two earlier versions of this
    panel printed confident, false findings sourced from a workbook whose 10-K
    citations turned out to be fabricated; the honest answer here is mostly
    "not comparable, and here is exactly why."
    """
    from core import forensics
    try:
        d = forensics.build()
    except Exception as e:
        ui.label(f"Forensics unavailable: {e}").style("color:#B45309;font-size:12px;")
        return

    pol, us = d.get("policy") or {}, d.get("usio") or {}
    tkr = CT("ticker")

    # USIO's gross-as-principal / interchange policy card — its policy is empty for other
    # tenants (which also means pol['basis'] would KeyError), so render only for USIO.
    if tkr == "USIO" and pol.get("basis"):
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid #B91C1C;"
                "border-left:3px solid #B91C1C;padding:8px 10px;"):
            ui.label(f"USIO reports revenue {pol['basis']} — verified from the filing").style(
                "color:#B91C1C;font-size:12px;font-weight:700;")
            ui.label(f"“{pol['quote']}”").style(
                f"color:{COLORS['text_body']};font-size:11px;font-style:italic;")
            ui.label(f"— {pol['form']} filed {pol['filed']}. {pol['verified']}").style(
                f"color:{COLORS['text_muted']};font-size:10px;")
            ui.label("This inverts the premise of the source workbook, which classified USIO as a net "
                     "reporter and concluded peers' margins fall below USIO's once adjusted. USIO's "
                     "~23% margin is depressed by its OWN gross presentation, not flattered by peers'.").style(
                f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")

    if us.get("gross_margin") is not None:
        with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
            _bm_stat(f"{tkr} gross margin", f"{us['gross_margin']*100:.1f}%",
                     f"FY{us['period'][:4]} · reported gross basis", None)
            # The net-basis / interchange column is USIO-specific.
            if tkr == "USIO":
                _bm_stat("Net-basis margin", "cannot compute",
                         "no interchange $ disclosed in the 10-K", "#B91C1C")
            _bm_stat("Peers comparable", f"{len(d['peers_comparable'])} of {d['n_primary']}",
                     f"{d['pct_comparable']}% of the primary comp set", "#B45309")

    ui.label("What each peer's own filing supports").classes("section-head").style("margin-top:8px;")
    cols = [{"name": "ticker", "label": "", "field": "ticker", "align": "left"},
            {"name": "gm", "label": "Gross margin", "field": "gm", "align": "right"},
            {"name": "period", "label": "Period", "field": "period", "align": "left"},
            {"name": "status", "label": "Usable?", "field": "status", "align": "left"},
            {"name": "detail", "label": "Why", "field": "detail", "align": "left"}]
    LBL = {"ok": "yes", "derived": "yes — derived", "ok_mda": "yes — 10-K MD&A",
           "stale": "NO — stale", "stale_mda": "NO — hand-carried fact is stale",
           "no_gross_profit_line": "NO — metric does not exist",
           "no_cik": "NO — no EDGAR data", "fetch_failed": "NO — fetch failed"}
    rd = []
    for t, r in sorted(d["rows"].items(), key=lambda kv: (kv[1]["status"] != "ok", kv[0])):
        rd.append({"ticker": t,
                   "gm": f"{r['gross_margin']*100:.1f}%" if r["gross_margin"] is not None else "—",
                   "period": (r["period"] or "—")[:7],
                   "status": LBL.get(r["status"], r["status"]),
                   "detail": r["detail"] or ""})
    ui.table(columns=cols, rows=rd).classes("w-full dense-table").props("flat dense wrap-cells")

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "border-left:3px solid #1E40AF;padding:8px 10px;margin-top:8px;"):
        ui.label("The finding").style("color:#1E40AF;font-size:12px;font-weight:700;")
        ui.label(d["verdict"]).style(f"color:{COLORS['text_body']};font-size:11.5px;")

    # The SBC-on-gross-profit interchange argument is USIO-specific.
    sb = d.get("sbc")
    if sb and sb.get("usio") and tkr == "USIO":
        ui.label("Stock-based compensation — measured against gross profit, not revenue").classes(
            "section-head").style("margin-top:10px;")
        ui.label("The denominator is the whole argument. USIO's revenue is GROSS, so '% of revenue' "
                 "inflates its denominator with interchange it never keeps and flatters it more than "
                 "any peer here. Gross profit is presentation-invariant — it is the only basis that "
                 "compares.").style(f"color:{COLORS['text_muted']};font-size:11px;")
        cols = [{"name": "ticker", "label": "", "field": "ticker", "align": "left"},
                {"name": "sbc", "label": "SBC ($M)", "field": "sbc", "align": "right"},
                {"name": "rev", "label": "% of revenue", "field": "rev", "align": "right"},
                {"name": "gp", "label": "% of gross profit", "field": "gp", "align": "right"},
                {"name": "rank", "label": "Rank (of GP)", "field": "rank", "align": "left"}]
        ui.table(columns=cols, rows=[{
            "ticker": ("★ " if r["is_client"] else "") + r["ticker"],
            "sbc": f"{r['sbc']/1e6:,.1f}", "rev": f"{r['pct_revenue']:.1f}%",
            "gp": f"{r['pct_gross_profit']:.1f}%", "rank": f"{r['rank_gp']} of {sb['n']}",
        } for r in sb["rows"]]).classes("w-full dense-table").props("flat dense")
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid #B91C1C;"
                "border-left:3px solid #B91C1C;padding:6px 10px;margin-top:4px;"):
            ui.label("The 'lean SBC' story does not survive the right denominator").style(
                "color:#B91C1C;font-size:12px;font-weight:700;")
            ui.label(sb["read"]).style(f"color:{COLORS['text_body']};font-size:11px;")

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid #B45309;"
            "border-left:3px solid #B45309;padding:6px 10px;margin-top:6px;"):
        ui.label("Source discipline — why this panel is thinner than the workbook's").style(
            "color:#B45309;font-size:11.5px;font-weight:700;")
        ui.label("Every figure here resolves to an SEC filing this code fetched itself. The prior "
                 "version of this analysis was built from USIO_Peer_Benchmarking_Report_v2_2.xlsx, "
                 "whose verbatim '10-K p.58 / p.38 / p.94' quotes do not appear in the respective "
                 "10-Ks. That workbook is quarantined at "
                 "data/seed/quarantine/peer_forensics_QUARANTINED.py with the evidence. Where a "
                 "figure cannot be sourced, this panel says so rather than estimating it.").style(
            f"color:{COLORS['text_muted']};font-size:10.5px;")


def _render_script_scorecard():
    """Script Effectiveness Scorecard, live from core.script_scorecard.compose().
    Same dict the PDF renders from, so screen and print can't drift."""
    from core import report_pdf, script_scorecard
    try:
        d = script_scorecard.compose()
    except Exception as e:
        ui.label(f"Scorecard unavailable: {e}").style("color:#B45309;font-size:12px;")
        return

    score_clr = "#15803D" if d["score"] >= 80 else ("#B45309" if d["score"] >= 60 else "#B91C1C")
    with ui.row().classes("w-full gap-3").style("margin-top:4px;"):
        _bm_stat("Score / 100", str(d["score"]), "measurable components only", score_clr)
        _bm_stat("Consolidated script", f"{d['override_minutes']:.1f} min",
                 f"{d['override_words']} words @ 140 wpm")
        _bm_stat("Q1 topics closed",
                 f"{sum(1 for c in d['carryover'] if c['addressed'])}/{len(d['carryover'])}",
                 "carry-over into this script")
        _bm_stat("Workflow", str(d["stage"]).replace("_", " "),
                 f"{d['stages_done']}/{d['stages_total']} stages complete")

    ui.label("How the score is built").classes("section-head").style("margin-top:10px;")
    for name, val, mx, note in d["components"]:
        pct = (val / mx) if mx else 0
        clr = "#15803D" if pct >= 0.8 else ("#B45309" if pct >= 0.4 else "#B91C1C")
        with ui.row().classes("w-full items-center gap-2").style(
                f"border-bottom:1px solid {COLORS['border']};padding:4px 0;"):
            ui.label(name).style(f"color:{COLORS['text_body']};font-size:12px;font-weight:600;width:150px;")
            ui.label(f"{val}/{mx}").style(f"color:{clr};font-size:12px;font-weight:700;width:52px;")
            ui.label(note).style(f"color:{COLORS['text_muted']};font-size:11px;")

    ui.label("Section run-time vs target").classes("section-head").style("margin-top:10px;")
    rows = [{"section": s["label"], "words": s["words"], "time": f"{s['minutes']:.1f} min",
             "target": f"{s['target']:.1f} min", "read": s["status"]} for s in d["sections"]]
    ui.table(columns=[{"name": "section", "label": "Section", "field": "section", "align": "left"},
                      {"name": "words", "label": "Words", "field": "words", "align": "right"},
                      {"name": "time", "label": "Est. time", "field": "time", "align": "right"},
                      {"name": "target", "label": "Target", "field": "target", "align": "right"},
                      {"name": "read", "label": "Read", "field": "read", "align": "left"}],
             rows=rows, row_key="section").classes("w-full").props("dense flat")

    h = d.get("hedge")
    if h:
        ui.label("Commit or qualify? (Loughran-McDonald)").classes("section-head").style("margin-top:10px;")
        ratio = h["hedge_ratio"]
        clr = "#B91C1C" if (ratio is None or ratio >= 3) else ("#B45309" if ratio >= 1.5 else "#15803D")
        with ui.row().classes("w-full gap-3"):
            _bm_stat("Hedge ratio", ("∞" if ratio is None else f"{ratio}x"),
                     "qualifiers ÷ commitments", clr)
            _bm_stat("Hedging words", str(h["counts"]["Weak_Modal"] + h["counts"]["Uncertainty"]),
                     "weak-modal + uncertainty")
            _bm_stat("Commitments", str(h["counts"]["Strong_Modal"]), "strong-modal")
        ui.label(h["hedge_read"]).style(f"color:{clr};font-size:11.5px;")
        _ex = ", ".join(h["examples"]["Weak_Modal"] + h["examples"]["Uncertainty"])[:110]
        if _ex:
            ui.label(f"qualifiers found: {_ex}").style(f"color:{COLORS['text_muted']};font-size:10.5px;")
        ui.label(h["caveat"] + f"  Licence: {h['license']}.").style(
            f"color:{COLORS['text_muted']};font-size:10px;")

    g = d.get("guidance") or {}
    if g.get("conflicts") or g.get("needs_redraft"):
        ui.label("Guidance version conflict").classes("section-head").style("margin-top:10px;")
        gi = g.get("input") or {}
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid #B91C1C;"
                "border-left:3px solid #B91C1C;padding:8px 10px;"):
            ui.label(f"The input (CFO decision): {gi.get('action')} → ${gi.get('low')}M–${gi.get('hi')}M").style(
                "color:#15803D;font-size:12px;font-weight:700;")
            if g.get("needs_redraft"):
                ui.label("needs_redraft is set — the authored prose predates the current decision.").style(
                    "color:#B45309;font-size:11px;")
            for c in g["conflicts"]:
                ui.label(f"✗ {c['source']} states {c['stated']}").style(
                    "color:#B91C1C;font-size:11.5px;font-weight:600;margin-top:3px;")
                ui.label(c["excerpt"]).style(
                    f"color:{COLORS['text_muted']};font-size:10.5px;font-style:italic;")
            ui.label("Every stated range should come from the one input. Re-draft the guidance prose from "
                     "the decision, or re-decide — but don't leave two answers in one script.").style(
                f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:4px;")

    ui.label("Carry-over from last quarter's post-mortem").classes("section-head").style("margin-top:10px;")
    for c in d["carryover"]:
        ok = c["addressed"]
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                f"border-left:3px solid {'#15803D' if ok else '#B91C1C'};padding:6px 10px;margin-top:3px;"):
            ui.label(f"{'CLOSED' if ok else 'STILL OPEN'} · {c['priority']} — {c['topic']} ({c['target']})").style(
                f"color:{'#15803D' if ok else '#B91C1C'};font-size:12px;font-weight:700;")
            ui.label(f"Q1: {c['q1']}").style(f"color:{COLORS['text_muted']};font-size:11px;")
            if c["evidence"]:
                ui.label(f"Found in script: {c['evidence']}").style(
                    f"color:{COLORS['text_secondary']};font-size:10.5px;font-style:italic;")

    if d["gaps"]:
        ui.label("Not scored here — and why").classes("section-head").style("margin-top:10px;")
        for g in d["gaps"]:
            ui.label("• " + g).style("color:#B45309;font-size:11px;")

    def _dl():
        try:
            ui.download(report_pdf.script_scorecard_pdf(),
                        f"{CT('ticker')}_Script_Effectiveness_Scorecard_{datetime.now():%Y%m%d}.pdf")
        except Exception as e:
            ui.notify(f"PDF failed: {e}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl).props("color=primary dense").style("margin-top:10px;")
    ui.label(d["method"]).style(f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:4px;")


def _bm_stat(label, value, sub, color=None):
    with ui.card().classes("flex-1").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};min-width:150px;"):
        ui.label(value).classes("text-xl font-bold").style(f"color:{color or COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")
        ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:10.5px;")


def _bm_bar(bm, field, fmt, title, median=None, better_low=False):
    """One ranked bar chart across USIO + peers, USIO highlighted."""
    rows = [r for r in bm["rows"] if r.get(field) is not None]
    rows.sort(key=lambda r: r[field], reverse=not better_low)
    xs = [r["ticker"] for r in rows]
    ys = [r[field] for r in rows]
    colors = [COLORS["accent"] if r["is_client"] else "#CBD5E1" for r in rows]
    fig = go.Figure(go.Bar(x=xs, y=ys, marker_color=colors,
                           text=[fmt(v) for v in ys], textposition="outside",
                           cliponaxis=False))
    if median is not None:
        fig.add_hline(y=median, line_dash="dot", line_color="#94A3B8",
                      annotation_text=f"peer median {fmt(median)}", annotation_position="top right")
    fig.update_layout(title=dict(text=title, font=dict(size=13)), height=280,
                      margin=dict(l=44, r=16, t=40, b=28), showlegend=False,
                      plot_bgcolor="white", paper_bgcolor="white",
                      yaxis=dict(gridcolor="#EEF1F6"))
    ui.plotly(fig).classes("w-full")


def _talking_card(points):
    if not points:
        return
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:3px solid #15803D;margin-top:4px;"):
        ui.label("Talking points for investor meetings").style(
            "color:#15803D;font-size:11px;font-weight:700;letter-spacing:.03em;")
        for p in points:
            ui.label("• " + p).style(f"color:{COLORS['text_secondary']};font-size:12.5px;line-height:1.55;")


def _render_company_financials():
    s = edgar_financials.financial_summary(CT("ticker"))
    if not s or s.get("_error"):
        ui.label(f"Could not load financials from EDGAR{(' — ' + s['_error']) if s and s.get('_error') else ''}.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
        return
    inc, bs, cf = s["income"], s["balance"], s["cashflow"]
    tp = edgar_financials.talking_points(s)

    ui.label(f"{s['entity']} — Financial Analysis").classes("text-lg font-bold")
    ui.label(f"Quarter ended {s['quarter_end']} · pulled live from the SEC EDGAR 10-Q (XBRL) · CIK {s['cik']}").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    # ---- Income statement & operating metrics ----
    ui.label("Income statement & operating metrics").classes("section-head").style("margin-top:8px;")
    with ui.row().classes("w-full gap-3"):
        _bm_stat("Revenue", f"${inc['revenue']/1e6:.1f}M", f"{inc['rev_growth_yoy']:+.0f}% YoY",
                 "#15803D" if (inc['rev_growth_yoy'] or 0) >= 10 else None)
        _bm_stat("Gross profit", f"${inc['gross_profit']/1e6:.1f}M", f"{inc['gross_margin']:.0f}% margin")
        _bm_stat("EBITDA", f"${inc['ebitda']/1e3:.0f}K", f"{inc['ebitda_margin']:.0f}% margin")
        _bm_stat("Net income", f"${inc['net_income']/1e3:.0f}K", f"{inc['net_margin']:.0f}% margin",
                 "#15803D" if (inc['net_income'] or 0) > 0 else "#B45309")
    if inc.get("adjusted_ebitda") is not None and inc.get("ebitda") is not None:
        _adj = inc.get("ebitda_adjustments", {})
        _br = " ".join(f"+ {k.split()[0].lower()} ${v/1e3:.0f}K" for k, v in _adj.items())
        ui.label(f"Adjusted EBITDA bridge: GAAP EBITDA ${inc['ebitda']/1e3:.0f}K {_br} = "
                 f"${inc['adjusted_ebitda']/1e3:.0f}K adjusted ({inc['adj_ebitda_margin']:.0f}% margin). "
                 f"Adjustments are XBRL-tagged add-backs; the company's own non-GAAP Adjusted EBITDA may include "
                 f"further items.").style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:4px;")
    if isinstance(tp, dict):
        _talking_card(tp.get("income", []))

    # ---- Balance sheet ----
    ui.label("Balance sheet").classes("section-head").style("margin-top:8px;")
    with ui.row().classes("w-full gap-3"):
        _nc = bs.get('net_cash')
        if _nc is not None:
            _sub = (f"${bs['debt']/1e6:.1f}M debt · {bs['debt_to_equity']:.0f}% D/E"
                    if bs.get('debt') is not None and bs.get('debt_to_equity') is not None else "net of debt")
            _bm_stat("Net cash" if _nc >= 0 else "Net debt", f"${abs(_nc)/1e6:.1f}M", _sub,
                     "#15803D" if _nc >= 0 else "#B45309")
        if bs.get('equity') is not None:
            _bm_stat("Equity (book value)", f"${bs['equity']/1e6:.1f}M", "shareholders' equity")
        # Custody/settlement float is a payments-business concept — USIO-specific.
        if CT("ticker") == "USIO":
            if bs.get('cash_and_restricted') is not None:
                _bm_stat("Customer funds held", f"${bs['cash_and_restricted']/1e6:.0f}M", "cash + restricted, in custody")
            if bs.get('customer_deposits') is not None:
                _bm_stat("Settlement liabilities", f"${bs['customer_deposits']/1e6:.0f}M", "customer deposits — not debt")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:3px solid #B45309;margin-top:4px;"):
        ui.label("Reading the balance sheet").style(
            "color:#B45309;font-size:11px;font-weight:700;letter-spacing:.03em;")
        # The custody/settlement-float reading is USIO's (a payments business). Only for USIO.
        if CT("ticker") == "USIO" and all(bs.get(k) is not None for k in
                                          ("assets", "liabilities", "equity", "cash_and_restricted", "cash", "debt")):
            ui.label(f"Gross assets of ${bs['assets']/1e6:.0f}M and liabilities of ${bs['liabilities']/1e6:.0f}M look "
                     f"large against ${bs['equity']/1e6:.0f}M of equity — but roughly ${bs['cash_and_restricted']/1e6:.0f}M "
                     f"is customer settlement and prepaid-card float held in custody, offset by matching obligations. "
                     f"It's pass-through, not corporate leverage. On a corporate basis the business is net cash: "
                     f"${bs['cash']/1e6:.1f}M cash vs only ${bs['debt']/1e6:.1f}M debt.").style(
                f"color:{COLORS['text_secondary']};font-size:12.5px;line-height:1.55;")
        elif bs.get("assets") is not None and bs.get("liabilities") is not None and bs.get("equity") is not None:
            ui.label(f"Assets of ${bs['assets']/1e6:.0f}M against ${bs['liabilities']/1e6:.0f}M of liabilities and "
                     f"${bs['equity']/1e6:.0f}M of equity.").style(
                f"color:{COLORS['text_secondary']};font-size:12.5px;line-height:1.55;")
    if isinstance(tp, dict):
        _talking_card(tp.get("balance", []))

    # ---- Cash flow ----
    _cf = lambda v: f"${v/1e3:.0f}K" if isinstance(v, (int, float)) else "—"
    _cp = lambda v: f"{v:.0f}%" if isinstance(v, (int, float)) else "—"
    ui.label("Cash flow").classes("section-head").style("margin-top:8px;")
    with ui.row().classes("w-full gap-3"):
        _bm_stat("Operating cash flow", _cf(cf.get('operating_cf')), f"{_cp(cf.get('ocf_margin'))} of revenue")
        _bm_stat("Free cash flow", _cf(cf.get('fcf')), f"{_cp(cf.get('fcf_margin'))} margin",
                 "#15803D" if (cf.get('fcf') or 0) > 0 else "#B45309")
        _bm_stat("Capex + software", _cf(cf.get('capex')), "reinvestment")
    if isinstance(tp, dict):
        _talking_card(tp.get("cashflow", []))


def _render_benchmark_analysis():
    bm = benchmarking_engine.build_benchmark()
    u = bm["usio"]

    ui.label("Valuation & peer benchmarking").classes("section-head").style("margin-top:10px;")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent_strong']};"
            f"border-left:4px solid {COLORS['accent']};"):
        ui.label("Key finding").classes("section-head")
        ui.label(benchmarking_engine.key_finding(bm)).style(
            f"color:{COLORS['text_secondary']};font-size:13px;line-height:1.6;")
        _mc, _ev = u.get("market_cap"), u.get("enterprise_value")
        if _mc and _ev:
            _exc = ", ".join(e["ticker"] for e in bm.get("excluded", []))
            ui.label(f"{CT('ticker')}: market cap ${_mc/1e6:.0f}M, enterprise value ${_ev/1e6:.0f}M → {u['ev_rev']:.2f}x "
                     f"EV/Revenue, {u['ev_gp']:.1f}x EV/Gross Profit (gross margin {u['gross_margin']:.0f}% from "
                     f"the 10-Q). Peer EV/Revenue & gross margins from market data (Yahoo){(' — ' + _exc + ' excluded from EV (bank / net-cash EVs aren’t comparable)') if _exc else ''}.").style(
                f"color:{COLORS['text_muted']};font-size:11px;margin-top:6px;")

    faster = bm["median_gr"] is not None and u["rev_growth"] > bm["median_gr"]
    with ui.row().classes("w-full gap-3").style("margin-top:8px;"):
        _bm_stat("EV / Gross Profit", f"{u['ev_gp']:.1f}x", f"vs {bm['median_gp']:.1f}x peer median", COLORS["accent"])
        _bm_stat("Discount (EV/GP)", f"{bm['discount_gp']:.0f}%", "below peer median", "#15803D")
        _bm_stat("Revenue growth", f"{u['rev_growth']:.0f}%", f"vs {bm['median_gr']:.0f}% median",
                 "#15803D" if faster else None)
        _bm_stat("EV/GP rank", f"#{bm['usio_gp_rank']} of {len(bm['gp_ranked'])}", "cheapest = best",
                 COLORS["accent"] if bm["usio_gp_rank"] == 1 else None)

    with ui.row().classes("w-full gap-4 items-start").style("margin-top:6px;"):
        with ui.column().classes("flex-1").style("min-width:300px;"):
            _bm_bar(bm, "ev_gp", lambda v: f"{v:.1f}x",
                    "EV / Gross Profit — the payments-appropriate multiple (lower = cheaper)",
                    median=bm["median_gp"], better_low=True)
        with ui.column().classes("flex-1").style("min-width:300px;"):
            _bm_bar(bm, "ev_rev", lambda v: f"{v:.1f}x",
                    "EV / Revenue — NOT comparable; overstates how cheap USIO is",
                    median=bm["median_ev"], better_low=True)
    with ui.row().classes("w-full gap-4 items-start"):
        with ui.column().classes("flex-1").style("min-width:300px;"):
            # No median line here, deliberately: bm["median_gm"] is None. Each firm's
            # own margin is a fact, but they sit on different bases (USIO and FOUR
            # report revenue gross, others net or mixed), so a central tendency across
            # them describes no company. Say that rather than leave a bare chart.
            _bm_bar(bm, "gross_margin", lambda v: f"{v:.0f}%",
                    "Gross margin — each firm's own basis, NOT comparable", median=None)
            missing = [r["ticker"] for r in bm["primary"] if r.get("gross_margin") is None]
            ui.label(
                "No peer median shown, deliberately: gross-vs-net revenue treatment varies across "
                "these companies (some gross, some net or mixed per-contract under ASC 606). A median "
                "across those bases describes no company — use EV/Gross Profit, where revenue cancels."
                + (f" {', '.join(missing)} are absent because they report no gross profit line at all."
                   if missing else "")).style(f"color:{COLORS['text_muted']};font-size:10.5px;")
        with ui.column().classes("flex-1").style("min-width:300px;"):
            _bm_bar(bm, "rev_growth", lambda v: f"{v:.0f}%", "Revenue growth (YoY)", median=bm["median_gr"])

    # Comparison table (ranked by EV/Gross Profit — cheapest first)
    ui.label("Primary valuation peers — ranked by EV/Gross Profit").classes("section-head").style("margin-top:6px;")
    _seg_desc = ("USIO is a hybrid (Merchant Services + Output Solutions), so it's benchmarked against a "
                 "segmented peer set — integrated payments, billing/output, and prepaid — not one generic "
                 "payments median. ◆ marks the closest single operating analog."
                 if CT("ticker") == "USIO" else
                 "Benchmarked against an independently chosen peer set matched on business model, not a "
                 "generic sector median. ◆ marks the closest single operating analog.")
    ui.label(_seg_desc).style(f"color:{COLORS['text_muted']};font-size:11px;")
    cols = [
        {"name": "co", "label": "Company", "field": "co", "align": "left"},
        {"name": "seg", "label": "Comps to", "field": "seg", "align": "left"},
        {"name": "gp", "label": "EV/Gross Profit", "field": "gp", "align": "right"},
        {"name": "ev", "label": "EV/Rev", "field": "ev", "align": "right"},
        {"name": "gm", "label": "Gross margin", "field": "gm", "align": "right"},
        {"name": "gr", "label": "Rev growth", "field": "gr", "align": "right"},
    ]

    def _bm_row(r):
        marker = "★ " if r["is_client"] else ("◆ " if r.get("closest_analog") else "")
        return {
            "co": marker + f"{r['ticker']} · {r['name']}",
            "seg": "Client" if r["is_client"] else r.get("segment", ""),
            "gp": f"{r['ev_gp']:.1f}x" if r["ev_gp"] is not None else "—",
            "ev": f"{r['ev_rev']:.1f}x" if r["ev_rev"] else "—",
            "gm": (f"{r['gross_margin']:.0f}%" + ("*" if r.get("gm_source") == "est" else "")) if r["gross_margin"] is not None else "—",
            "gr": (f"{r['rev_growth']:+.0f}%" + ("*" if r.get("growth_source") == "est" else "")) if r["rev_growth"] is not None else "—",
        }

    ui.table(columns=cols, rows=[_bm_row(r) for r in bm["gp_ranked"]], row_key="co").classes("w-full").props("dense flat")

    if bm.get("reference"):
        ui.label("Large-cap reference — industry growth / margin bar, excluded from the median").classes(
            "section-head").style("margin-top:8px;")
        ui.label("You don't apply a mega-cap processor's multiple to a micro-cap; these set context only.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        ui.table(columns=cols, rows=[_bm_row(r) for r in bm["reference"]], row_key="co").classes("w-full").props("dense flat")

    ui.label("* estimated (not separately reported in the filing / market feed).").style(
        f"color:{COLORS['text_muted']};font-size:10px;")

    if bm["short"]:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                f"border-left:4px solid #15803D;margin-top:6px;"):
            ui.label("PAIR-TRADE READ").style(
                "color:#15803D;font-size:11px;font-weight:700;letter-spacing:.04em;")
            ui.label(f"LONG {u['ticker']} ({u['ev_gp']:.1f}x EV/Gross Profit, {bm['discount_gp']:.0f}% below the "
                     f"primary-peer median, #{bm['usio_gp_rank']} of {len(bm['gp_ranked'])}) / SHORT "
                     f"{bm['short']['ticker']} ({bm['short']['ev_gp']:.1f}x EV/Gross Profit, the priciest primary "
                     f"comp) — a valuation gap, not a growth gap.").style(
                f"color:{COLORS['text_secondary']};font-size:12.5px;line-height:1.55;")

    _exc_note = ", ".join(e["ticker"] for e in bm.get("excluded", [])) or "none"
    _no_gp = ", ".join(r["ticker"] for r in bm.get("primary", []) if r.get("gross_margin") is None) or "none"
    ui.label("Data provenance — gross profit and gross margin come from each company's own annual filing "
             "ONLY: there is no market or estimated fallback, because a vendor's constructed margin is not a "
             "reported one. A filer that reports no gross profit line shows no margin and leaves the median "
             f"({_no_gp}). Revenue growth: filing, then market. EV/Revenue: market, consistent trailing basis "
             "— and NOT comparable across these names, so it is context only. Excluded from the EV comparison "
             f"(net-cash / non-positive EV, not meaningful): {_exc_note}. A licensed feed (Capital IQ/"
             "Bloomberg) would add cleaner normalization and is the eventual upgrade; nothing here costs "
             "anything today.").style(f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:8px;")

    def _dl_bench_pdf():
        try:
            ui.download(report_pdf.peer_benchmarking_pdf(),
                        f"{CT('ticker')}_Peer_Benchmarking_{datetime.now():%Y%m%d}.pdf")
        except Exception as exc:
            ui.notify(f"PDF export failed: {exc}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl_bench_pdf).props(
        "color=primary dense").style("margin-top:6px;")


def _render_board_deck_live():
    """Board-ready valuation summary — rebuilt LIVE off the same benchmarking engine
    as the analysis above.

    REPLACES USIO_Peer_Benchmarking_Board_Deck.pptx, which was verified claim-by-claim
    against live filings on 2026-07-16: of 11 quantitative claims, ZERO survived. Its
    headline — "Implied USIO price ~$9–12 at peer median" — came from applying a peer
    EV/REVENUE median to USIO's GROSS revenue, which is the precise error the footnote
    forensics exists to prevent. The defensible figure is ~$3. Nothing was ported.
    """
    bm = benchmarking_engine.build_benchmark()
    u = bm["usio"]
    try:
        from core import valuation_comp
        imp = (valuation_comp.build() or {}).get("implied")
    except Exception:
        imp = None

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent_strong']};"
            f"border-left:4px solid {COLORS['accent']};"):
        ui.label("BOARD SUMMARY — VALUATION & PEER POSITION").style(
            f"color:{COLORS['text_muted']};font-size:10.5px;font-weight:700;letter-spacing:.05em;")
        ui.label(benchmarking_engine.key_finding(bm)).style(
            f"color:{COLORS['text_secondary']};font-size:13px;line-height:1.6;")
    faster = bm["median_gr"] is not None and u["rev_growth"] > bm["median_gr"]
    with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
        _bm_stat("EV / Gross Profit", f"{u['ev_gp']:.1f}x",
                 f"#{bm['usio_gp_rank']} of {len(bm['gp_ranked'])} · median {bm['median_gp']:.1f}x",
                 COLORS["accent"])
        if imp:
            _bm_stat("Implied upside", f"{imp['upside_pct']:+.0f}%",
                     f"at the {imp['peer_median_multiple']:.1f}x peer median, equity basis",
                     "#15803D" if imp["upside_pct"] > 0 else "#B91C1C")
        _bm_stat("Revenue growth", f"{u['rev_growth']:.0f}%", f"vs {bm['median_gr']:.0f}% median",
                 "#15803D" if faster else None)
        # EV/Revenue is NOT comparable across this peer set and is deliberately NOT
        # given a "% below median" or a green tick. USIO reports revenue gross of
        # interchange, so a low EV/Rev overstates how cheap it is — that artefact is
        # exactly what produced the retired deck's $9–12 price.
        _bm_stat("EV / Revenue", f"{u['ev_rev']:.2f}x", "context only — NOT comparable", None)
        if bm.get("short"):
            _bm_stat("Pair-trade", f"L {u['ticker']} / S {bm['short']['ticker']}",
                     f"{u['ev_gp']:.1f}x vs {bm['short']['ev_gp']:.1f}x EV/GP")
    ui.label("Board-ready summary — the same live figures as the full analysis above (SEC EDGAR "
             "filings + market data), recomputed on every render. No static slides that can drift "
             "out of sync with the numbers. Upside is stated as a percentage rather than a price "
             "target: the two share-count sources on file disagree by 7.6% (config 26.8M vs "
             "market-implied 28.8M), and a per-share figure would inherit that without saying so.").style(
        f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:6px;")


def _render_ndr_by_city():
    """NDR Coverage by City — where the money is vs where we're going.

    Built because the CFO asked for it. The ranking metric is the whole argument: metros
    are scored on the top-N non-holders you could actually fill a day with, NOT the average
    across every fund. Averaged, New York scores 51 (2nd-weakest of 8) because it has 15
    funds and a long tail; on the metric that matches how an NDR works it is the strongest
    market at 74 and the schedule is correctly built around it.
    """
    from core import ndr_by_city
    try:
        d = ndr_by_city.compose()
    except Exception as e:
        ui.label(f"NDR coverage unavailable: {e}").style("color:#B45309;font-size:12px;")
        return

    with ui.row().classes("w-full gap-3"):
        _bm_stat("Meetings booked", str(d["total_booked"]),
                 f"across {sum(1 for r in d['rows'] if r['booked'])} of {len(d['rows'])} metros", None)
        _bm_stat("Institutions on file", str(d["total_funds"]),
                 f"{sum(r['non_holders'] for r in d['rows'])} non-holders", None)
        if d["correlation"] is not None:
            good = d["correlation"] > 0.2
            _bm_stat("Schedule vs opportunity", f"{d['correlation']:+.2f}",
                     "tracks the opportunity" if good else "does NOT track the opportunity",
                     "#15803D" if good else "#B91C1C")
    ui.label(d["read"]).style(f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")

    ui.label("Every metro, ranked").classes("section-head").style("margin-top:8px;")
    ui.table(
        columns=[{"name": "r", "label": "#", "field": "r", "align": "left"},
                 {"name": "m", "label": "Metro", "field": "m", "align": "left"},
                 {"name": "s", "label": f"Top-{d['day_capacity']} score", "field": "s", "align": "right"},
                 {"name": "n", "label": "Non-holders", "field": "n", "align": "right"},
                 {"name": "b", "label": "Booked", "field": "b", "align": "right"},
                 {"name": "t", "label": "Trip on calendar", "field": "t", "align": "left"}],
        rows=[{"r": r["rank"], "m": r["metro"], "s": f"{r['top_avg']:.0f}",
               "n": r["non_holders"], "b": r["booked"],
               "t": ", ".join(f"{x['name']} ({x['meetings']})" for x in r["trips"]) or "—"}
              for r in d["rows"]]).classes("w-full dense-table").props("flat dense wrap-cells")
    ui.label(f"Ranked on the average engagement score of the top {d['day_capacity']} non-holders in "
             f"each metro — not the average across every fund. An NDR is {d['day_capacity']} meetings "
             f"in a day, not a survey; averaging the whole list penalises deep markets for their "
             f"tail.").style(f"color:{COLORS['text_muted']};font-size:10.5px;")

    for f in d["findings"]:
        col = "#B91C1C" if f["level"] == "red" else "#B45309"
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {col};"
                f"border-left:3px solid {col};padding:6px 10px;margin-top:4px;"):
            ui.label(f["title"]).style(f"color:{col};font-size:12px;font-weight:700;")
            ui.label(f["detail"]).style(f"color:{COLORS['text_body']};font-size:11px;")

    with ui.expansion(f"Who is in each market — the top {d['day_capacity']} non-holders per metro").classes(
            "w-full").style("margin-top:6px;"):
        for r in d["rows"]:
            if not r["top_targets"]:
                continue
            ui.label(f"#{r['rank']} {r['metro']} — top-{d['day_capacity']} avg {r['top_avg']:.0f}, "
                     f"{r['booked']} booked").style(
                f"color:{COLORS['text_body']};font-size:11px;font-weight:600;margin-top:4px;")
            ui.label(" · ".join(f"{x['fund']} ({x['score']})" for x in r["top_targets"])).style(
                f"color:{COLORS['text_muted']};font-size:10.5px;")

    def _dl_ndr():
        try:
            ui.download(report_pdf.ndr_by_city_pdf(),
                        f"{CT('ticker')}_NDR_Coverage_by_City_{datetime.now():%Y%m%d}.pdf")
        except Exception as exc:
            ui.notify(f"PDF export failed: {exc}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl_ndr).props(
        "color=primary dense").style("margin-top:8px;")


def _render_onboarding_checklist():
    """IRConnect client onboarding — live readiness.

    The .docx asked the client to tick boxes. A tick says someone typed an answer, not that
    the thing works. Every item here is answered by querying the platform.
    """
    from core import onboarding_checklist
    try:
        d = onboarding_checklist.compose()
    except Exception as e:
        ui.label(f"Onboarding checklist unavailable: {e}").style("color:#B45309;font-size:12px;")
        return
    ui.label(f"Answered from the platform, not from a form — {d['ready']} of {d['total']} items are "
             f"live and working. Items sourced from SEC filings are not asked of the client at "
             f"all.").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    for name, items in d["sections"]:
        ui.label(name).classes("section-head").style("margin-top:8px;")
        ui.table(
            columns=[{"name": "s", "label": "", "field": "s", "align": "left"},
                     {"name": "i", "label": "Item", "field": "i", "align": "left"},
                     {"name": "o", "label": "Owner", "field": "o", "align": "left"},
                     {"name": "l", "label": "Live status", "field": "l", "align": "left"}],
            rows=[{"s": "OK" if x["status"] == "ready" else "GAP", "i": x["item"],
                   "o": x["owner"], "l": x["live"] or "—"} for x in items]).classes(
            "w-full dense-table").props("flat dense wrap-cells")
        for x in items:
            if x.get("note"):
                ui.label(f"{x['item']}: {x['note']}").style(
                    f"color:{COLORS['text_muted']};font-size:10.5px;")

    pol = d["peer_policy"]
    ui.label("Policy change — the peer/comp group").classes("section-head").style("margin-top:10px;")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid #B91C1C;"
            "border-left:3px solid #B91C1C;padding:6px 10px;"):
        ui.label("What the checklist used to say").style("color:#B91C1C;font-size:12px;font-weight:700;")
        ui.label(pol["old"]).style(f"color:{COLORS['text_body']};font-size:11px;font-style:italic;")
        ui.label("That deference sounds respectful, and it is how this client came to be "
                 "benchmarked against a bank.").style(f"color:{COLORS['text_body']};font-size:11px;")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid #15803D;"
            "border-left:3px solid #15803D;padding:6px 10px;margin-top:4px;"):
        ui.label("What it says now").style("color:#15803D;font-size:12px;font-weight:700;")
        ui.label(pol["new"]).style(f"color:{COLORS['text_body']};font-size:11px;")
    for head, body in pol["criteria"]:
        ui.label(f"• {head} — {body}").style(f"color:{COLORS['text_body']};font-size:11px;")
    ui.label(pol["evidence"]).style(f"color:{COLORS['text_muted']};font-size:10.5px;")

    ui.label("Criteria run against the current comp set, live").classes(
        "section-head").style("margin-top:8px;")
    ui.table(
        columns=[{"name": "t", "label": "", "field": "t", "align": "left"},
                 {"name": "n", "label": "Company", "field": "n", "align": "left"},
                 {"name": "c", "label": "(c) comparable basis?", "field": "c", "align": "left"},
                 {"name": "d", "label": "Detail", "field": "d", "align": "left"}],
        rows=[{"t": r["ticker"], "n": r["name"] or "",
               "c": "PASS" if r["c_comparable_basis"] else "FAIL",
               "d": r["c_note"] + (f" · {r['flag_note']}" if r.get("flag_note") else "")}
              for r in d["peer_check"]]).classes("w-full dense-table").props("flat dense wrap-cells")
    ui.label("Criterion (a) — no pending or approved M&A — cannot be checked from XBRL and needs a "
             "human eye on each name's filings each quarter. It is the one that caught GDOT, and it "
             "caught it from an 8-K, not a feed.").style(
        f"color:{COLORS['text_muted']};font-size:10.5px;")

    def _dl_cl():
        try:
            ui.download(report_pdf.onboarding_checklist_pdf(),
                        f"{CT('ticker')}_IRConnect_Onboarding_Readiness_{datetime.now():%Y%m%d}.pdf")
        except Exception as exc:
            ui.notify(f"PDF export failed: {exc}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl_cl).props(
        "color=primary dense").style("margin-top:8px;")


def _render_onboarding_kit():
    """New Analyst Onboarding Kit — the .docx's framework, answers regenerated live.

    The only artifact in this platform built to be handed to a sell-side analyst. The prior
    edition's Q1 told analysts that PEERS report gross and inflate their denominator; USIO's
    own 10-K says USIO reports gross as a principal. Every answer here carries its source
    because the reader has the filing open.
    """
    from core import onboarding_kit
    try:
        d = onboarding_kit.compose()
    except Exception as e:
        ui.label(f"Onboarding kit unavailable: {e}").style("color:#B45309;font-size:12px;")
        return
    pol = d.get("policy") or {}
    ui.label("Built to be handed to a sell-side analyst. Every answer carries the source it can be "
             "checked against — the reader has the 10-K open.").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    # Gross-as-principal / interchange "start here" card is USIO-specific (pol empty otherwise).
    if CT("ticker") == "USIO" and pol.get("basis"):
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid #B91C1C;"
                "border-left:3px solid #B91C1C;padding:8px 10px;margin-top:4px;"):
            ui.label(f"Start here — we report revenue {pol['basis']}").style(
                "color:#B91C1C;font-size:12px;font-weight:700;")
            ui.label(f"\u201c{pol['quote']}\u201d").style(
                f"color:{COLORS['text_body']};font-size:11px;font-style:italic;")
            ui.label(f"— {pol['form']}, filed {pol['filed']}. This one fact explains our gross margin. "
                     f"Interchange we never keep sits in both revenue and cost of services; a peer "
                     f"reporting net shows 60–75% on identical economics. Gross margin is not "
                     f"comparable across payment processors — ours or anyone's.").style(
                f"color:{COLORS['text_body']};font-size:11px;")

    for i, q in enumerate(d["qa"], 1):
        with ui.expansion(f"Q{i}. {q['q']}", value=(i == 1)).classes("w-full").style("margin-top:4px;"):
            ui.label(q["a"]).style(f"color:{COLORS['text_body']};font-size:11.5px;")
            if q.get("flag"):
                ui.label("Note to IR: " + q["flag"]).style(
                    "color:#B45309;font-size:10.5px;font-weight:600;")
            ui.label("Source: " + " · ".join(q["sources"])).style(
                f"color:{COLORS['text_muted']};font-size:10px;font-style:italic;")

    ui.label("What this kit does not claim, and why").classes("section-head").style("margin-top:10px;")
    ui.label("A kit that quietly drops what it can't support looks thinner. One that says why is "
             "more credible than the version that made it up.").style(
        f"color:{COLORS['text_muted']};font-size:10.5px;")
    for g in d["gaps"]:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid #B45309;"
                "border-left:3px solid #B45309;padding:6px 10px;margin-top:4px;"):
            ui.label(g["item"]).style("color:#B45309;font-size:11.5px;font-weight:700;")
            ui.label(g["why"]).style(f"color:{COLORS['text_body']};font-size:11px;")

    def _dl_kit():
        try:
            ui.download(report_pdf.onboarding_kit_pdf(),
                        f"{CT('ticker')}_New_Analyst_Onboarding_Kit_{datetime.now():%Y%m%d}.pdf")
        except Exception as exc:
            ui.notify(f"PDF export failed: {exc}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl_kit).props(
        "color=primary dense").style("margin-top:8px;")


def _render_earnings_prep():
    """Earnings Prep Brief (core.earnings_prep) — what management needs in the room.

    Leads with the sharpest TRUE fact rather than the friendliest. Currently that is
    that USIO's own quarterly guides sum ABOVE its own FY ceiling, and that USIO can
    hit its guide and still miss a 2-analyst "consensus".
    """
    from core import earnings_prep
    try:
        d = earnings_prep.compose()
    except Exception as e:
        ui.label(f"Earnings prep unavailable: {e}").style("color:#B45309;font-size:12px;")
        return

    b, r, q = d.get("bar"), d.get("reconciliation"), d.get("qa")
    last_q = (q or {}).get("from_quarter", "last")

    ui.label(f"{d['quarter']} call · {d['earnings_date']} · {d['days_out']} days out — composed live "
             f"from the consensus file, the CFO's guidance decision, the risk scorecard and the "
             f"{last_q} transcript.").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid #B91C1C;"
            "border-left:3px solid #B91C1C;padding:8px 10px;margin-top:4px;"):
        ui.label("Read this first").style("color:#B91C1C;font-size:12px;font-weight:700;")
        ui.label(earnings_prep.headline(d)).style(
            f"color:{COLORS['text_body']};font-size:11.5px;font-weight:600;")

    if b and not b.get("unavailable"):
        with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
            _bm_stat("Our guidance", f"${b['guidance']:.1f}M", "what we promised", None)
            _bm_stat("The street", f"${b['street']:.2f}M",
                     f"mean of {b['n']} analysts · {b.get('source','')}",
                     "#15803D" if b.get("guide_above_all") else "#B91C1C")
            _bm_stat("Guide vs street", f"{b['gap_pct']:+.1f}%",
                     "our guide is above the street" if b["gap_pct"] < 0 else "street is above our guide",
                     "#15803D" if b["gap_pct"] < 0 else "#B91C1C")
        ui.label(b["read"]).style(f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")

        cols = [{"name": "k", "label": "Street estimate", "field": "k", "align": "left"},
                {"name": "v", "label": "Revenue", "field": "v", "align": "right"},
                {"name": "g", "label": "vs our guide", "field": "g", "align": "right"}]
        rows = []
        for label, val in [("Low", b.get("low")), ("Average", b.get("street")), ("High", b.get("high"))]:
            if val is not None:
                rows.append({"k": label, "v": f"${val:.2f}M",
                             "g": f"{(val/b['guidance']-1)*100:+.1f}%"})
        rows.append({"k": "Our guidance", "v": f"${b['guidance']:.2f}M", "g": "—"})
        ui.table(columns=cols, rows=rows).classes("w-full dense-table").props("flat dense")

        if b.get("coverage"):
            with ui.expansion("Covering analysts — per the market feed").classes("w-full").style(
                    "margin-top:4px;"):
                ccols = [{"name": "f", "label": "Firm", "field": "f", "align": "left"},
                         {"name": "r", "label": "Rating", "field": "r", "align": "left"},
                         {"name": "p", "label": "Price target", "field": "p", "align": "right"},
                         {"name": "d", "label": "Last action", "field": "d", "align": "left"}]
                ui.table(columns=ccols, rows=[{
                    "f": c["firm"], "r": c.get("grade") or "—",
                    "p": f"${c['price_target']:.2f}" if c.get("price_target") else "—",
                    "d": c.get("date") or "—"} for c in b["coverage"]]).classes(
                    "w-full dense-table").props("flat dense")

        if b.get("on_file_outside_range"):
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid #B45309;"
                    "border-left:3px solid #B45309;padding:6px 10px;margin-top:4px;"):
                ui.label("The estimates on file in this platform are DEMO data — not used above").style(
                    "color:#B45309;font-size:12px;font-weight:700;")
                ui.label(f"{', '.join(b['on_file_outside_range'])} fall outside the street's entire "
                         f"published range (${b['low']:.2f}–{b['high']:.2f}M). period_estimates has "
                         f"never been written for this client, so the platform falls back to a demo "
                         f"seed. The street figures above come from the market feed, with the period "
                         f"mapping reconciled against filed actuals. Entering the real analyst models "
                         f"would let this cross-check do its job.").style(
                    f"color:{COLORS['text_body']};font-size:11px;")
    elif b and b.get("unavailable"):
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid #B45309;"
                "border-left:3px solid #B45309;padding:6px 10px;margin-top:4px;"):
            ui.label("No street read available").style("color:#B45309;font-size:12px;font-weight:700;")
            ui.label(b["read"]).style(f"color:{COLORS['text_body']};font-size:11px;")

    if r and r.get("complete"):
        ui.label("Do our own numbers add up?").classes("section-head").style("margin-top:8px;")
        cols = [{"name": "p", "label": "Period", "field": "p", "align": "left"},
                {"name": "src", "label": "Source", "field": "src", "align": "left"},
                {"name": "rev", "label": "Revenue", "field": "rev", "align": "right"}]
        rows = [{"p": x["period"], "src": x["source"] or "—",
                 "rev": f"${x['used']:.2f}M" if x["used"] is not None else "—"} for x in r["parts"]]
        rows.append({"p": "Sum of quarters", "src": "", "rev": f"${r['sum']:.2f}M"})
        if r.get("fy_low") is not None:
            rows.append({"p": f"Stated {r['fy_label']} guidance", "src": "CFO decision",
                         "rev": f"${r['fy_low']:.1f} – {r['fy_high']:.1f}M"})
        ui.table(columns=cols, rows=rows).classes("w-full dense-table").props("flat dense")
        ui.label(r["read"]).style(
            "color:{};font-size:11.5px;font-weight:600;".format(
                "#15803D" if r.get("reconciles") else "#B91C1C"))
        ui.label("Nothing else in the platform checks this. The guidance-consistency engine verifies "
                 "the script's PROSE states the same FY range the CFO decided — it does not add the "
                 "quarters up.").style(f"color:{COLORS['text_muted']};font-size:10.5px;")

    if d.get("scenarios"):
        ui.label("Beat / miss scenarios").classes("section-head").style("margin-top:8px;")
        ui.label("Thresholds are the street's published LOW / AVERAGE / HIGH plus our guide. The "
                 "market feed gives the distribution but not per-analyst attribution, so these do not "
                 "name which firm writes 'miss' — the only per-analyst numbers on file are demo seed "
                 "values that sit outside the real range.").style(
            f"color:{COLORS['text_muted']};font-size:10.5px;")
        cols = [{"name": "rev", "label": "If revenue is", "field": "rev", "align": "right"},
                {"name": "g", "label": "vs guide", "field": "g", "align": "right"},
                {"name": "s", "label": "vs Street", "field": "s", "align": "right"},
                {"name": "l", "label": "Reads as", "field": "l", "align": "left"},
                {"name": "dsc", "label": "What happens", "field": "dsc", "align": "left"}]
        ui.table(columns=cols, rows=[{
            "rev": f"${x['revenue']:.2f}M", "g": f"{x['vs_guide_pct']:+.1f}%",
            "s": f"{x['vs_street_pct']:+.1f}%", "l": x["label"], "dsc": x["desc"],
        } for x in d["scenarios"]]).classes("w-full dense-table").props("flat dense wrap-cells")

    if q and q.get("open"):
        ui.label(f"Q&A prep — unpaid from the {q['from_quarter']} call").classes(
            "section-head").style("margin-top:8px;")
        ui.label(q["read"]).style(f"color:{COLORS['text_body']};font-size:11.5px;")
        for f in q["open"]:
            with ui.expansion(f"{f.get('verdict')} — {str(f.get('anchor'))[:70]}").classes(
                    "w-full").style("margin-top:4px;"):
                ui.label(f"The number was {f.get('valence')} — so the answer owed was "
                         f"{f.get('demand')}.").style(
                    f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")
                ui.label(str(f.get("why"))).style(f"color:{COLORS['text_muted']};font-size:11px;")
        ui.label("Method: every analyst question anchors on a number; that number's valence sets what "
                 "kind of answer is owed (a GOOD number owes REPEATABILITY, a CLAIM owes BACKING); the "
                 "verdict records whether it was paid. MISMATCH and DEFERRED are unpaid debts, and "
                 "analysts carry debts forward.").style(
            f"color:{COLORS['text_muted']};font-size:10.5px;")

    for s in d.get("risks", []):
        col = "#B91C1C" if s.get("level") == "red" else "#B45309"
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {col};"
                f"border-left:3px solid {col};padding:6px 10px;margin-top:4px;"):
            ui.label(str(s.get("title"))).style(f"color:{col};font-size:12px;font-weight:700;")
            ui.label(str(s.get("desc"))).style(f"color:{COLORS['text_body']};font-size:11px;")

    def _dl_prep_pdf():
        try:
            qlabel = (d.get("quarter") or "").replace(" ", "_")
            ui.download(report_pdf.earnings_prep_pdf(),
                        f"{CT('ticker')}_{qlabel}_Earnings_Prep_Brief_{datetime.now():%Y%m%d}.pdf")
        except Exception as exc:
            ui.notify(f"PDF export failed: {exc}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl_prep_pdf).props(
        "color=primary dense").style("margin-top:8px;")


def _render_board_ir_report():
    """Live Board IR Report — composed from the real filing, valuation, and
    ownership data, replacing the old static (and page-count-overstated) images."""
    s = edgar_financials.financial_summary(CT("ticker"))
    if not s or s.get("_error"):
        ui.label("Financials unavailable from EDGAR right now.").style(f"color:{COLORS['text_muted']};font-size:12px;")
        return
    inc, bs, cf = s["income"], s["balance"], s["cashflow"]
    bm = benchmarking_engine.build_benchmark()
    u = bm["usio"]

    # Ownership & the Street (best-effort; each guarded)
    try:
        n13f = len([h for h in sec_filings.get_cached_13f_holders(CT("ticker")).get("holders", []) if h.get("filer")])
    except Exception:
        n13f = None
    try:
        pt = risk_scorecard._consensus_pt_avg()
    except Exception:
        pt = None
    snap = market_data.get_snapshot(CT("ticker"))
    price = snap.get("last_price") if snap else None
    upside = ((pt / price - 1) * 100) if (pt and price) else None
    nobo_cov = nobo_ret = None
    try:
        pulls = nobo_engine.get_active_pulls(get_active_client_id())
        nb = nobo_engine.analyze_pull(pulls["current"], pulls["shares_outstanding"])
        nobo_cov, nobo_ret = nb["nobo_pct_so"], nb["retail_pct"]
    except Exception:
        pass

    ui.label(f"{s['entity']} — Board IR Report").classes("text-lg font-bold")
    ui.label(f"As of the {s['quarter_end']} 10-Q · composed live from SEC EDGAR filings + market data").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    # Executive summary (BLUF)
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent_strong']};"
            f"border-left:4px solid {COLORS['accent']};"):
        ui.label("EXECUTIVE SUMMARY").style(
            f"color:{COLORS['text_muted']};font-size:10.5px;font-weight:700;letter-spacing:.05em;")
        # The old text asserted "cheap on a growing base" on every branch and quoted
        # EV/Revenue as supporting evidence. Both are claims, not facts: the discount can
        # be a premium, and EV/Revenue is not comparable across this peer set at all.
        _disc = bm.get("discount_gp")
        _med = bm.get("median_gp")
        if _disc is None or _med is None:
            _val = "not directly comparable on the current peer set"
        elif _disc > 0:
            _val = "a {:.0f}% discount to the {:.1f}x peer median".format(_disc, _med)
        else:
            _val = "a {:.0f}% PREMIUM to the {:.1f}x peer median".format(abs(_disc), _med)
        # Built defensively: a recent IPO / non-payments issuer has None for figures USIO
        # always has (net cash — SARO carries net DEBT), and the interchange line is USIO's.
        _nc = bs.get("net_cash")
        _seg = []
        if inc.get("revenue") is not None:
            _seg.append(f"Revenue ${inc['revenue']/1e6:.1f}M"
                        + (f", up {inc['rev_growth_yoy']:.0f}% year-over-year" if inc.get("rev_growth_yoy") is not None else ""))
        if inc.get("gross_profit") is not None:
            _seg.append(f"${inc['gross_profit']/1e6:.1f}M gross profit")
        if inc.get("adjusted_ebitda") is not None:
            _seg.append(f"${inc['adjusted_ebitda']/1e3:.0f}K adjusted EBITDA")
        _txt = ", with ".join(_seg) + "." if _seg else ""
        if _nc is not None:
            _txt += (f" Balance sheet is net cash (${_nc/1e6:.1f}M) — self-funding."
                     if _nc >= 0 else f" Balance sheet carries net debt (${abs(_nc)/1e6:.1f}M).")
        if u.get("ev_gp") is not None:
            _txt += f" Shares trade at {u['ev_gp']:.1f}x EV/Gross Profit — {_val}."
        _txt += (" EV/Revenue is NOT a usable comparison here and is excluded from that read: USIO "
                 "reports revenue gross of interchange."
                 if CT("ticker") == "USIO" else
                 " EV/Revenue is not comparable across this peer set and is excluded from that read.")
        if inc.get("operating_margin") is not None:
            _txt += f" The re-rating hinges on operating-margin expansion (currently {inc['operating_margin']:.1f}%)."
        ui.label(_txt.strip()).style(
            f"color:{COLORS['text_secondary']};font-size:13px;line-height:1.6;")

    # None-safe formatters: a recent IPO / non-payments issuer has None for figures USIO
    # always carries (net cash, settlement float, some margins). Show "—" rather than crash.
    def _m(v, scale=1e6, dec=1, pre="$", suf="M"):
        return f"{pre}{v/scale:.{dec}f}{suf}" if isinstance(v, (int, float)) else "—"

    def _pct(v, dec=0):
        return f"{v:.{dec}f}%" if isinstance(v, (int, float)) else "—"

    ui.label("Quarter financials").classes("section-head").style("margin-top:8px;")
    with ui.row().classes("w-full gap-3"):
        _bm_stat("Revenue", _m(inc.get('revenue')),
                 f"{_pct(inc.get('rev_growth_yoy'))} YoY" if inc.get('rev_growth_yoy') is not None else "",
                 "#15803D" if (inc.get('rev_growth_yoy') or 0) >= 10 else None)
        _bm_stat("Gross profit", _m(inc.get('gross_profit')), f"{_pct(inc.get('gross_margin'))} margin")
        _bm_stat("Adjusted EBITDA", _m(inc.get('adjusted_ebitda'), 1e3, 0, '$', 'K'), f"{_pct(inc.get('adj_ebitda_margin'))} margin")
        _bm_stat("Net income", _m(inc.get('net_income'), 1e3, 0, '$', 'K'), f"{_pct(inc.get('net_margin'))} margin")

    ui.label("Balance sheet & cash flow").classes("section-head").style("margin-top:8px;")
    with ui.row().classes("w-full gap-3"):
        _nc2 = bs.get('net_cash')
        _bm_stat("Net cash" if (_nc2 or 0) >= 0 else "Net debt",
                 _m(abs(_nc2) if _nc2 is not None else None),
                 f"{_m(bs.get('debt'))} debt · {_pct(bs.get('debt_to_equity'))} D/E",
                 "#15803D" if (_nc2 or 0) >= 0 else "#B45309")
        _bm_stat("Equity", _m(bs.get('equity')), "book value")
        _bm_stat("Free cash flow", _m(cf.get('fcf'), 1e3, 0, '$', 'K'), f"{_pct(cf.get('fcf_margin'))} margin",
                 "#15803D" if (cf.get('fcf') or 0) > 0 else "#B45309")
        # Settlement float is a payments concept — USIO only.
        if CT("ticker") == "USIO" and bs.get('customer_deposits') is not None:
            _bm_stat("Settlement float", _m(bs.get('customer_deposits'), 1e6, 0, '$', 'M'), "customer money — not debt")

    ui.label("Valuation & peer position").classes("section-head").style("margin-top:8px;")
    with ui.row().classes("w-full gap-3"):
        _rank_sub = (f"#{bm['usio_gp_rank']} of {len(bm['gp_ranked'])} · median {bm['median_gp']:.1f}x"
                     if bm.get('usio_gp_rank') is not None and bm.get('median_gp') is not None
                     and bm.get('gp_ranked') else "peer rank n/a")
        _bm_stat("EV / Gross Profit", f"{u['ev_gp']:.1f}x" if u.get('ev_gp') is not None else "—",
                 _rank_sub, COLORS["accent"])
        # NOT green, and no "% below median": EV/Revenue is not comparable across this
        # peer set. Colouring it as a favourable fact is the error that produced the
        # retired deck's $9-12 price target.
        _bm_stat("EV / Revenue", f"{u['ev_rev']:.2f}x" if u.get('ev_rev') is not None else "—",
                 "context only — NOT comparable", None)
        _bm_stat("Growth vs peers", _pct(u.get('rev_growth')), f"vs {_pct(bm.get('median_gr'))} median")

    ui.label("Ownership & the Street").classes("section-head").style("margin-top:8px;")
    with ui.row().classes("w-full gap-3"):
        if pt and upside is not None:
            _bm_stat("Consensus PT", f"${pt:.2f}", f"{upside:+.0f}% vs ${price:.2f}", "#15803D" if upside > 0 else "#B45309")
        if n13f is not None:
            _bm_stat("Institutional holders", f"{n13f}", "real 13F filers (SEC)")
        if nobo_cov is not None:
            _bm_stat("NOBO coverage", f"{nobo_cov:.0f}%", f"{nobo_ret:.0f}% retail")

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:4px solid #B45309;margin-top:8px;"):
        ui.label("THE BOARD TAKEAWAY").style("color:#B45309;font-size:10.5px;font-weight:700;letter-spacing:.05em;")
        _om = inc.get('operating_margin')
        if CT("ticker") == "USIO":
            _take = (f"Cheap, clean, and self-funding — but the re-rating case rests on operating-margin "
                     f"expansion (currently {_om:.1f}%). Revenue growth is proven; profit conversion is not. "
                     f"The IR priority is arming the Street with a credible operating-leverage bridge, and "
                     f"reframing the balance-sheet float (customer money, not leverage) and gross-vs-net "
                     f"revenue so the discount is understood, not just observed."
                     if _om is not None else
                     "The re-rating case rests on profit conversion. The IR priority is arming the Street "
                     "with a credible operating-leverage bridge.")
        else:
            _take = ("The re-rating case rests on how the multiple is framed against the right peer set and "
                     "on the demand backdrop"
                     + (f", with operating margin currently {_om:.1f}%" if _om is not None else "")
                     + ". The IR priority is a credible, model-matched valuation bridge and a clear "
                       "operating-leverage story — not a headline discount taken at face value.")
        ui.label(_take).style(f"color:{COLORS['text_secondary']};font-size:12.5px;line-height:1.55;")

    try:
        tp = edgar_financials.talking_points(s)
        _talking_card(tp["income"] + tp["balance"] + tp["cashflow"])
    except Exception as exc:
        print(f"[reports_page] talking points unavailable for {CT('ticker')}: {exc}")

    # ---- sections merged in from the Quarterly Board Package ----
    try:
        from core import board_package
        _pkg = board_package.compose()
    except Exception as _e:
        _pkg = None

    if _pkg and _pkg.get("sell_side"):
        _ss = _pkg["sell_side"]
        ui.label("Sell-side coverage").classes("section-head").style("margin-top:10px;")
        ui.table(
            columns=[{"name": "f", "label": "Firm", "field": "f", "align": "left"},
                     {"name": "r", "label": "Rating", "field": "r", "align": "left"},
                     {"name": "p", "label": "Price target", "field": "p", "align": "right"},
                     {"name": "d", "label": "Last action", "field": "d", "align": "left"},
                     {"name": "s", "label": "Status", "field": "s", "align": "left"}],
            rows=[{"f": c["firm"], "r": c.get("grade") or "—",
                   "p": f"${c['price_target']:.2f}" if c.get("price_target") else "—",
                   "d": c.get("date") or "—", "s": "DORMANT" if c.get("stale") else "active"}
                  for c in _ss["coverage"]]).classes("w-full dense-table").props("flat dense")
        ui.label(_ss["read"]).style(f"color:{COLORS['text_body']};font-size:11.5px;")

    if _pkg and _pkg.get("buy_side", {}).get("note"):
        _bs = _pkg["buy_side"]
        ui.label("Buy-side & retail").classes("section-head").style("margin-top:10px;")
        with ui.row().classes("w-full gap-3"):
            if _bs.get("activists_recent") is not None:
                _bm_stat("Schedule 13D", str(_bs["activists_recent"]),
                         f"last {_bs['window_days']//365}y ({_bs['activists_all_time']} all-time)",
                         "#15803D" if _bs["activists_recent"] == 0 else "#B91C1C")
            if _bs.get("passive_recent") is not None:
                _bm_stat("Schedule 13G", str(_bs["passive_recent"]),
                         f"last {_bs['window_days']//365}y (passive)", None)
        ui.label(_bs["note"]).style(f"color:{COLORS['text_body']};font-size:11.5px;")

    if _pkg and _pkg.get("open_items"):
        ui.label("Open items for board awareness").classes("section-head").style("margin-top:10px;")
        for _s in _pkg["open_items"]:
            _c = "#B91C1C" if _s.get("level") == "red" else "#B45309"
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {_c};"
                    f"border-left:3px solid {_c};padding:6px 10px;margin-top:4px;"):
                ui.label(str(_s.get("title"))).style(f"color:{_c};font-size:12px;font-weight:700;")
                ui.label(str(_s.get("desc"))).style(f"color:{COLORS['text_body']};font-size:11px;")

    if _pkg and _pkg.get("appendix"):
        with ui.expansion("Appendix A — comparable companies, and why each is here").classes(
                "w-full").style("margin-top:8px;"):
            ui.label("Every name carries the reason it is in the set. A comp sheet without a written "
                     "rationale is how the prior package listed an acquired company, a pending "
                     "acquisition and a bank as 'Active' for a quarter.").style(
                f"color:{COLORS['text_muted']};font-size:10.5px;")
            ui.table(
                columns=[{"name": "t", "label": "", "field": "t", "align": "left"},
                         {"name": "n", "label": "Company", "field": "n", "align": "left"},
                         {"name": "g", "label": "Gross margin", "field": "g", "align": "right"},
                         {"name": "m", "label": "In median?", "field": "m", "align": "left"},
                         {"name": "w", "label": "Why it is here", "field": "w", "align": "left"}],
                rows=[{"t": r["ticker"], "n": r["name"] or "",
                       "g": f"{r['gm']:.1f}%" if r["gm"] is not None else "—",
                       "m": "yes" if r["in_median"] else f"no ({r['gm_basis']})",
                       "w": r["rationale"]} for r in _pkg["appendix"]]).classes(
                "w-full dense-table").props("flat dense wrap-cells")

    def _dl_board_pdf():
        try:
            ui.download(report_pdf.board_package_pdf(),
                        f"{CT('ticker')}_IR_Quarterly_Board_Package_{datetime.now():%Y%m%d}.pdf")
        except Exception as exc:
            ui.notify(f"PDF export failed: {exc}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl_board_pdf).props(
        "color=primary dense").style("margin-top:8px;")
    ui.label("Live package — every figure recomputes from the latest filing, the market feed and this "
             "platform's activity log. The quarter it reports is derived from the filing, never from a "
             "title. Where a number cannot be sourced (short interest, per-analyst models) it is "
             "reported as absent rather than estimated.").style(
        f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:6px;")


def _render_ir_plan(reviews, review_path):
    from core import ir_plan
    p = ir_plan.compose_ir_plan()
    ctx = p["context"]

    ui.label(f"{ctx['name']} — 90-Day IR Plan").classes("text-lg font-bold")
    ui.label(f"{p['as_of']:%b %d} – {p['window_end']:%b %d, %Y} · forward action plan, composed live from the "
             f"earnings calendar, roadshow schedule, catalysts, and ownership signals.").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
        if ctx.get("rev_growth") is not None:
            _bm_stat("Revenue growth", f"{ctx['rev_growth']:.0f}%", "the proven half", "#15803D")
        if ctx.get("op_margin") is not None:
            _bm_stat("Operating margin", f"{ctx['op_margin']:.1f}%", "the story to change", "#B45309")
        if ctx.get("ev_gp") is not None:
            _bm_stat("EV / Gross Profit", f"{ctx['ev_gp']:.1f}x", f"{ctx['discount_gp']:.0f}% below median", COLORS["accent"])
        if ctx.get("consensus_pt") and ctx.get("upside") is not None:
            _bm_stat("Consensus PT", f"${ctx['consensus_pt']:.2f}", f"{ctx['upside']:+.0f}% upside", "#15803D")

    # Objectives
    ui.label("Objectives this quarter").classes("section-head").style("margin-top:10px;")
    for i, (title, detail) in enumerate(p["objectives"], 1):
        with ui.row().classes("w-full items-start gap-3").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:10px;"
                f"padding:11px 14px;margin:3px 0;"):
            ui.label(str(i)).style(
                f"background:{COLORS['accent_soft'] if 'accent_soft' in COLORS else 'rgba(30,64,175,.08)'};"
                f"color:{COLORS['accent']};width:26px;height:26px;border-radius:7px;display:flex;"
                "align-items:center;justify-content:center;font-weight:700;flex-shrink:0;")
            with ui.column().classes("gap-0"):
                ui.label(title).style(f"color:{COLORS['text_body']};font-size:13px;font-weight:600;")
                ui.label(detail).style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    # Timeline
    ui.label("Key dates & milestones").classes("section-head").style("margin-top:10px;")
    if not p["timeline"]:
        ui.label("No dated milestones in the window.").style(f"color:{COLORS['text_muted']};font-size:12px;")
    for d, lbl, det in p["timeline"]:
        with ui.row().classes("w-full items-center gap-3").style(
                f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:5px 10px;margin:2px 0;"):
            ui.label(f"{d:%b %d}").style(f"color:{COLORS['accent']};font-size:12px;font-weight:700;width:64px;")
            ui.label(lbl).style(f"color:{COLORS['text_body']};font-size:12.5px;font-weight:600;width:230px;")
            ui.label(det).classes("flex-1").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    # Targeting
    ui.label("Targeting & outreach").classes("section-head").style("margin-top:10px;")
    if p["trips"]:
        ui.label("Booked roadshows").style(f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
        for t in p["trips"]:
            ui.label(f"• {t['city']} · {t['dates']} · {t['meetings']} meetings — {t['name']}").style(
                f"color:{COLORS['text_muted']};font-size:11.5px;")
    if p["prospects"]:
        ui.label("Priority prospects — non-holders by engagement").style(
            f"color:{COLORS['text_body']};font-size:12px;font-weight:600;margin-top:6px;")
        with ui.row().classes("w-full gap-2 flex-wrap"):
            for pr in p["prospects"]:
                ui.label(f"{pr['fund']} · {pr['score']}").style(
                    f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:2px 9px;"
                    f"color:{COLORS['text_body']};font-size:11.5px;")

    # Catalysts
    if p["catalysts"]:
        ui.label("Catalysts to communicate").classes("section-head").style("margin-top:10px;")
        with ui.row().classes("w-full gap-2 flex-wrap"):
            for c in p["catalysts"]:
                ui.label(c).style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:999px;"
                    f"padding:4px 11px;color:{COLORS['text_secondary']};font-size:11.5px;")

    # Positioning
    ui.label("Positioning — the messages to land").classes("section-head").style("margin-top:10px;")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:3px solid #15803D;"):
        for msg in p["positioning"]:
            ui.label("• " + msg).style(f"color:{COLORS['text_secondary']};font-size:12.5px;line-height:1.5;")

    # Ownership actions
    if p["ownership"]:
        ui.label("Ownership actions").classes("section-head").style("margin-top:10px;")
        for action, detail in p["ownership"]:
            with ui.row().classes("w-full items-baseline gap-2").style(
                    f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:6px 10px;margin:2px 0;"):
                ui.label(action).style(f"color:{COLORS['text_body']};font-size:12.5px;font-weight:600;")
                ui.label(detail).classes("flex-1").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    def _dl_plan_pdf():
        try:
            ui.download(report_pdf.ir_plan_pdf(), f"{CT('ticker')}_90_Day_IR_Plan_{datetime.now():%Y%m%d}.pdf")
        except Exception as exc:
            ui.notify(f"PDF export failed: {exc}", type="negative")

    ui.button("Download PDF", icon="picture_as_pdf", on_click=_dl_plan_pdf).props(
        "color=primary dense").style("margin-top:10px;")
    ui.label("Live plan — recomposes from the earnings calendar, NDR schedule, catalysts, and ownership signals "
             "each time you open it.").style(f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:6px;")
    _reviewed_row(reviews, review_path, "USIO_90_Day_IR_Plan")


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

    with ui.expansion(f"This Week's Automation · {tasks_week} action{'s' if tasks_week != 1 else ''} logged", value=True).classes("w-full"):
        with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent_strong']};"
            f"border-left:3px solid {COLORS['accent']};"
        ):
            ui.label("Key finding").classes("section-head")
            ui.label(key_finding).style(f"color:{COLORS['text_secondary']};font-size:13px;")

        with ui.row().classes("w-full gap-3").style("margin-top:8px;"):
            for val, lbl in [
                (str(tasks_today), "actions today"),
                (str(tasks_week), "actions this week"),
                (f"{hrs_week:.1f} hrs", "saved this week"),
            ]:
                with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};"):
                    ui.label(val).classes("text-lg font-bold").style(f"color:{COLORS['success']};")
                    ui.label(lbl).style(f"color:{COLORS['text_muted']};font-size:10.5px;")

        ui.label("Breakdown by category — this week").classes("section-head").style("margin-top:14px;")
        if breakdown:
            for item in breakdown:
                label = EVENT_LABELS.get(item["event_type"], item["event_type"].replace("_", " ").title())
                with ui.row().classes("w-full justify-between items-center").style(f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                    ui.label(label).style(f"color:{COLORS['text_body']};font-size:12.5px;")
                    ui.label(f"{item['count']}× · {item['minutes']} min").style(f"color:{COLORS['text_muted']};font-size:12px;")
        else:
            ui.label("Nothing logged yet this week.").style(f"color:{COLORS['text_muted']};font-size:12px;")

    with ui.expansion("Where these numbers come from", value=False).classes("w-full"):
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

    ui.label("Regulation FD Compliance Logger").classes("text-xl font-bold")
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
            f"QUIET PERIOD ACTIVE {quiet_start.strftime('%b %d')}–{quiet_end.strftime('%b %d, %Y')}. "
            f"No MNPI may be shared. All investor contact must be logged immediately."
        ).style(f"background:{COLORS['danger']};color:white;padding:10px 16px;border-radius:8px;")
    elif quiet_start and days_to_q > 0:
        ui.label(f"Quiet period begins in {days_to_q} days ({quiet_start.strftime('%B %d')}). Complete all analyst outreach before then.").style(
            f"background:{COLORS['warning']};color:white;padding:10px 16px;border-radius:8px;"
        )
    else:
        ui.label("Open window — normal communications permitted.").style(
            f"background:{COLORS['success']};color:white;padding:10px 16px;border-radius:8px;"
        )

    with ui.tabs().classes("w-full") as fd_tabs:
        fd1 = ui.tab("Log Interaction")
        fd2 = ui.tab("Full Log")
        fd3 = ui.tab("Flags")
        fd4 = ui.tab("Summary")

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
            fd_team = ui.select(team_labels(), multiple=True,
                                label=f"{C().get('name','Company')} participants").classes("w-full")
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
                    ui.notify("HIGH RISK — legal review required immediately.", type="negative")
                else:
                    ui.notify("Logged.", type="positive")
                fd_inst.value = ""
                fd_summ.value = ""
                refresh_all_tabs()

            _log_btn = ui.button("Log Interaction", on_click=log_interaction).props("color=primary").style("margin-top:8px;")
            if ui_context.is_read_only():
                _log_btn.disable()

        with ui.tab_panel(fd2):
            full_log_container = ui.column().classes("w-full gap-2")

            def render_full_log():
                full_log_container.clear()
                with full_log_container:
                    if not log:
                        ui.label("No interactions logged yet.").style(f"color:{COLORS['text_muted']}")
                        return
                    for entry in reversed(log):
                        icon = "" if entry.get("risk_level") == "HIGH" else ""
                        qb = " · QUIET" if entry.get("in_quiet") else ""
                        rb = " · Reviewed" if entry.get("reviewed") else " · Pending"
                        with ui.expansion(f"{icon} {entry.get('date')} · {entry.get('institution')} · {entry.get('type')}{qb}{rb}").classes("w-full"):
                            ui.label(f"Topics: {', '.join(entry.get('topics', []))}")
                            ui.label(f"MNPI: {entry.get('mnpi_status', '—')}")
                            ui.label(f"Summary: {entry.get('summary', '—')}")
                            if entry.get("8k_required"):
                                if entry.get("8k_resolved"):
                                    ui.label(f"8-K resolved {entry.get('8k_resolved_date','')}").style(f"color:{COLORS['success']};font-weight:bold;")
                                else:
                                    ui.label("8-K DISCLOSURE FLAGGED").style(f"color:{COLORS['danger']};font-weight:bold;")
                            if not entry.get("reviewed"):
                                def mark_reviewed(e=entry):
                                    e["reviewed"] = True
                                    _save_json(regfd_path, log)
                                    refresh_all_tabs()
                                _mr_btn = ui.button("Mark Reviewed by Legal", on_click=mark_reviewed).props("flat")
                                if ui_context.is_read_only():
                                    _mr_btn.disable()

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
                        _metric("HIGH risk unreviewed", len(high_risk), "Need legal sign-off")
                        _metric("8-K flagged (open)", len(k8_open), "Possible disclosure")
                        _metric("Total unreviewed", sum(1 for e in log if not e.get("reviewed")), "Pending legal review")

                    if high_risk or k8_open:
                        ui.label(
                            "Closed loop: resolve a flag right here — no need to go find the same entry in Full Log."
                        ).style(f"color:{COLORS['text_muted']};font-size:11px;margin:4px 0;")

                    for e in high_risk:
                        with ui.card().classes("w-full").style(f"background:#FDECEC;border:1px solid {COLORS['danger']}55;"):
                            with ui.row().classes("w-full items-center justify-between"):
                                with ui.column().classes("gap-0"):
                                    ui.label(f"{e['date']} · {e['institution']}").classes("font-bold").style("color:#0F172A;font-size:13.5px;")
                                    ui.label(f"MNPI: {e['mnpi_status']}").style(f"color:{COLORS['text_muted']};font-size:12px;")

                                def mark_reviewed(e=e):
                                    e["reviewed"] = True
                                    _save_json(regfd_path, log)
                                    ui.notify("Marked reviewed by legal.")
                                    refresh_all_tabs()

                                _mr2_btn = ui.button("Mark Reviewed", on_click=mark_reviewed).props("flat dense").style(f"color:{COLORS['danger']};")
                                if ui_context.is_read_only():
                                    _mr2_btn.disable()

                    for e in k8_open:
                        with ui.card().classes("w-full").style(f"background:#FCF0E0;border:1px solid {COLORS['warning']}55;"):
                            with ui.row().classes("w-full items-center justify-between"):
                                with ui.column().classes("gap-0"):
                                    ui.label(f"{e['date']} · {e['institution']} · 8-K required").classes("font-bold").style("color:#0F172A;font-size:13.5px;")
                                    ui.label((e.get("summary") or "")[:120]).style(f"color:{COLORS['text_muted']};font-size:12px;")

                                def mark_8k_resolved(e=e):
                                    e["8k_resolved"] = True
                                    e["8k_resolved_date"] = datetime.now().strftime("%b %d, %Y")
                                    _save_json(regfd_path, log)
                                    ui.notify("8-K marked filed/resolved.")
                                    refresh_all_tabs()

                                _k8_btn = ui.button("Mark 8-K Filed/Resolved", on_click=mark_8k_resolved).props("flat dense").style(f"color:{COLORS['warning']};")
                                if ui_context.is_read_only():
                                    _k8_btn.disable()

                    if not high_risk and not k8_open:
                        ui.label("No open flags. ").style(f"color:{COLORS['text_muted']};")

                    if k8_resolved:
                        with ui.expansion(f"{len(k8_resolved)} 8-K item(s) resolved").classes("w-full").style("margin-top:8px;"):
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
                            _metric("Total logged", total_fd, "All interactions")
                            _metric("Reviewed", rev_n, "Cleared by legal")
                            _metric("Compliance rate", f"{rev_n/total_fd*100:.0f}%", "Reviewed / logged")

                        def export_csv():
                            df = pd.DataFrame(log)
                            ui.download(df.to_csv(index=False).encode(), f"{CT('ticker')}_RegFD_{datetime.now().strftime('%Y%m%d')}.csv")

                        ui.button("Download Full Reg FD Log (CSV)", on_click=export_csv).props("color=primary")
                    else:
                        ui.label("No interactions logged yet.").style(f"color:{COLORS['text_muted']}")

            log_container_ref["summary"] = render_summary
            render_summary()


def _metric(label, value, hint=""):
    with ui.card().classes("flex-1").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};padding:12px;"):
        ui.label(str(value)).classes("text-xl font-bold").style(f"color:{COLORS['text_heading']}")
        ui.label(label).style(f"color:{COLORS['text_secondary']};font-size:12px;font-weight:600;")
        if hint:
            ui.label(hint).style(f"color:{COLORS['text_muted']};font-size:10.5px;")


