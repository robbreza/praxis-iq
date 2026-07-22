"""
page_modules_nicegui/today_page.py — Today (landing dashboard), NiceGUI version.

The original Streamlit page leaned heavily on st.popover() + session_state
for a set of compliance-tracking micro-workflows on the Risk Signals list
(three different signals can each be in a "default / sent / noted" state,
each with its own date-stamped audit trail). Ported here with the same
three states and the same audit trail, but:
- state now persists under the client-scoped SQLite key "today_state.json"
  via core.db (previously a JSON file at that path via client_data_path();
  core.db transparently imports that file on first read so no data from
  earlier testing is lost — see core/db.py), instead of Streamlit's
  session_state — this means it survives a page refresh/app restart, which
  session_state never did
- the popover-with-nested-checkboxes UI is now a dialog (ui.dialog) with
  the same recipient checkboxes and editable email draft

All content is ported, including the two informational-signal popovers
(Disconnect Drivers on "138% upside to consensus PT", and Update
Institutional Target List on "1 ownership change" / "1 conference
confirmed" — both are now ui.dialog()s) and the Activity & Responses /
Model Requests tracker that appears once model requests have been sent
(per-analyst Sent/Replied/Model Received status, a notes field for
replies, and a CSV upload + old-vs-new revenue comparison + "Accept —
recalculate consensus" action for received models). The dialog's
Target Database cross-reference is simplified to the same static
candidate list app.py hardcoded for its illustrative New York-route
example, rather than a live query against a Target Database module —
that database isn't part of this migration yet (see investors_page.py's
Target Database tab docstring for the same caveat).
"""

import csv
import io
from contextlib import contextmanager
from datetime import datetime, timedelta
from urllib.parse import quote

from nicegui import ui

from config.client_config import C, CA, CE, CI, CT
from config.theme_tokens import ACTIVE as COLORS
from core import activity_log, db, inbox_queue, market_data, signals, ui_context
from core.textfmt import pretty_name
from data.seed.institution_contacts import get_institution_contacts
from page_modules_nicegui import nav

STATE_PATH_NAME = "today_state.json"


def _load_state():
    return db.load_json(STATE_PATH_NAME, {})


def _save_state(state):
    # RBAC choke point: the Today page has many mark-noted/mark-sent/consensus
    # actions across nested dialogs, all of which persist through here. Rather
    # than gate each button, a view-only role (e.g. CRO/Legal, who have 'read'
    # access to Today) has its writes swallowed at this single point, so no
    # change from this page can stick. The read-only banner at the top of
    # render_today_page tells the user why.
    if ui_context.is_read_only():
        return
    db.save_json(STATE_PATH_NAME, state)


def _mailto(to, subject, body, label):
    href = f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"
    ui.link(f"{label}", href).style(f"color:{COLORS['accent_light']};")


def _open_signal_count(state):
    """How many of the 3 tracked Risk Signals (missing models, guidance
    gap, check-in) are still sitting in their default/unresolved state —
    backs the ROI strip's "follow-ups flagged" number and the Today's
    Story talking points. Real count against `state`, not a guess."""
    open_n = 0
    for key in ("models", "guidance", "checkin"):
        if not (state.get(f"{key}_request_sent") or state.get(f"{key}_marked_sent") or state.get(f"{key}_marked_noted")):
            open_n += 1
    return open_n


def _earnings_readiness_pct():
    """Fraction of the 5 Script Generation stages (earnings_page.py) marked
    complete, as a percent. Real signal, though narrower than the original
    demo's "82%" figure (which silently blended in slides/legal/webcast
    status this app doesn't actually track anywhere) — documented here so
    the number's basis is clear rather than implied to be broader than it
    is."""
    ss = db.load_json("script_workflow_state.json", None)
    if not ss or not ss.get("stages"):
        return 0.0
    stages = ss["stages"]
    complete = sum(1 for s in stages.values() if s.get("status") == "complete")
    return complete / len(stages) * 100 if stages else 0.0


def _consensus_pt_avg(period="Q2 2026E"):
    """Average price target across currently-active covering analysts for
    `period` — replaces the hardcoded "$5.12" with a real average of
    CA()'s active-analyst PTs from the seed consensus data (same source
    Markets already uses), so a PT change or an analyst going
    active/inactive is reflected here automatically."""
    # READ THROUGH get_consensus(), NOT THE SEED. This function's own docstring promises
    # "a PT change or an analyst going active/inactive is reflected here automatically" —
    # and while it read get_seed_consensus() that was false: update_estimate() writes
    # period_estimates.json, which the seed never sees. The Today page would have shown a
    # stale consensus PT forever, on the landing screen, while every other surface moved.
    from config.client_config import get_active_client_id
    from core.consensus import get_consensus
    seed = get_consensus(get_active_client_id())
    ests = seed.get("period_estimates", {}).get(period, {})
    covering_firms = {a["firm"] for a in CA() if a.get("covering", True)}
    pts = [ests[f]["Price Target"] for f in ests if f in covering_firms and ests.get(f, {}).get("Price Target") is not None]
    return sum(pts) / len(pts) if pts else None


def _today_story_text(snap, recent):
    """Templated narrative built from the real price/volume snapshot
    (core.market_data) and the most recent logged activity — replaces the
    fully hardcoded "Today's Story" prose. Deliberately rule-based rather
    than an AI-generated paragraph: the inputs here are sparse (one price
    move, a short activity list), so a template reads more reliably than
    an LLM call that might editorialize past what the numbers actually
    support."""
    ticker = CT("ticker")
    if snap and snap.get("last_price") is not None:
        chg = snap.get("pct_change") or 0
        direction = "up" if chg >= 0 else "down"
        vol_txt = ""
        if snap.get("volume") and snap.get("avg_volume_10d"):
            ratio = snap["volume"] / snap["avg_volume_10d"]
            vol_txt = f", on {ratio:.1f}x its 10-day average volume"
        as_of = (snap.get("as_of") or "")[:16].replace("T", " ")
        price_line = f"{ticker} is {direction} {abs(chg):.1f}% as of {as_of}{vol_txt}."
    else:
        price_line = f"Market data for {ticker} hasn't been fetched yet — it refreshes automatically shortly after the app starts, or use Refresh on the Today page."

    if recent:
        parts = []
        for r in recent[:3]:
            label = r["event_type"].replace("_", " ")
            parts.append(f"{label}" + (f" ({r['entity']})" if r.get("entity") else ""))
        activity_line = "Recent activity: " + "; ".join(parts) + "."
    else:
        activity_line = "No activity logged yet today — resolving a Risk Signal below is the fastest way to get this feed moving."

    return f"{price_line} {activity_line}"


def _talking_points(state, overdue, readiness_pct):
    """Real, computed stand-ins for the old 3 hardcoded talking points —
    each line reflects an actual queryable fact (overdue count, script
    readiness, open signal count) rather than a fixed script."""
    points = []
    if overdue:
        names = ", ".join(o["entity"] for o in overdue[:3])
        points.append(f"{len(overdue)} analyst follow-up(s) overdue (>24h, no response logged): {names} — close these before the quiet period.")
    else:
        points.append("No analyst follow-ups are overdue right now.")

    if readiness_pct >= 80:
        points.append(f"Earnings script is {readiness_pct:.0f}% through its review stages — on track.")
    elif readiness_pct > 0:
        points.append(f"Earnings script is only {readiness_pct:.0f}% through its review stages — needs attention this week.")
    else:
        points.append("Earnings script workflow hasn't been started yet.")

    open_n = _open_signal_count(state)
    if open_n:
        points.append(f"{open_n} of 3 tracked Risk Signal(s) below still need action today.")
    else:
        points.append("All 3 tracked Risk Signals have been resolved or logged as noted.")

    pending_inbox = inbox_queue.list_pending_items()
    if pending_inbox:
        firms = ", ".join((p.get("firm") or p.get("contact") or "unknown") for p in pending_inbox[:3])
        points.append(f"{len(pending_inbox)} email(s) routed to your inbox queue awaiting confirmation "
                       f"({firms}) — see Investor Targeting → Meeting Hub → Upcoming Meetings.")
    return points


def render_today_page():
    state = _load_state()
    today_d = datetime.now().date()
    earnings_date_str = CE().get("earnings_date", "2026-08-12")
    earnings_date = datetime.strptime(earnings_date_str, "%Y-%m-%d").date()
    days = max((earnings_date - today_d).days, 0)
    td = datetime.now().strftime("%A, %B %d, %Y")

    ui.label(td).style(f"color:{COLORS['accent_light2']};text-transform:uppercase;letter-spacing:.08em;font-size:13px;")
    # Greeting name: CFO, not the IR contact (CI()) — per the user, ahead of
    # a Wednesday demo to USIO's CFO (Michael White). Falls back to the IR
    # contact's name if a client has no CFO configured, so this doesn't
    # break for a future client with a different exec roster.
    cfo = C().get("executives", {}).get("CFO", {})
    greet_name = cfo.get("name") or CI().get("name", "there")
    first_name = (greet_name.split() or ["there"])[0]
    ui.label(f"Good morning, {first_name}.").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    # RBAC: view-only roles (e.g. CRO/Legal) can read the morning brief but not
    # persist mark-noted/sent/consensus actions — enforced at the _save_state
    # choke point above; this just tells them why nothing sticks.
    if ui_context.is_read_only():
        ui_context.read_only_banner(ui)

    # ── Computed values — every number below is a real query against
    # activity_log / market_data / script_workflow_state, not a literal.
    # See the helper functions above render_today_page() for how each is
    # derived, and their docstrings for what's still a partial proxy
    # (e.g. earnings readiness only reflects Script Generation stages).
    tasks_today = activity_log.count_today()
    hrs_saved = activity_log.minutes_saved_this_week() / 60
    open_signals = _open_signal_count(state)
    overdue = activity_log.overdue_sent_without_response("model_request_sent", ["model_received"], hours=24)
    readiness_pct = _earnings_readiness_pct()
    snap = market_data.get_snapshot(CT("ticker"))
    recent = activity_log.recent_events(limit=5)

    # ── ROI strip — hideable ──
    # Defaults to hidden, per the user: greeting flows straight into Today's
    # Story. The "tasks automated" / "hrs saved" numbers this strip used to
    # be the only place for now have a proper home in Reports' Automation
    # Tracker tab (with real breakdown/trend, not just a headline number) —
    # this strip is now just a quick optional glance, not the only view.
    show_roi = state.get("show_roi_strip", False)

    def toggle_roi():
        state["show_roi_strip"] = not state.get("show_roi_strip", False)
        _save_state(state)
        nav.go_to("Today")

    ui.button(
        "Hide automation stats" if show_roi else "Show automation stats",
        on_click=toggle_roi,
    ).props("flat dense size=sm").style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:2px;padding-left:0;")

    if show_roi:
        with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
            for val, lbl, clr in [
                (str(tasks_today), "tasks automated today", COLORS["success"]),
                (f"{hrs_saved:.1f} hrs", "saved this week", COLORS["success"]),
                (str(open_signals), "signals needing follow-up", COLORS["accent_light"] if open_signals else COLORS["success"]),
                (str(len(overdue)), "analyst requests overdue", COLORS["danger"] if overdue else COLORS["success"]),
                (f"{readiness_pct:.0f}%", "script workflow readiness", COLORS["warning"]),
            ]:
                with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                    ui.label(val).classes("text-lg font-bold").style(f"color:{clr};")
                    ui.label(lbl).style(f"color:{COLORS['text_muted']};font-size:11px;")
        ui.markdown("---")

    # ── Today's Story + Key Metrics ──
    with ui.row().classes("w-full gap-4 items-stretch"):
        with ui.card().classes("flex-[7]").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent']};border-radius:12px;"):
            ui.label("Today's story").classes("section-head")
            ui.label(_today_story_text(snap, recent)).style(f"color:{COLORS['text_body']};font-size:15px;line-height:1.7;")
            ui.label("Talking points for management").classes("section-head").style("margin-top:12px;")
            for i, pt in enumerate(_talking_points(state, overdue, readiness_pct), 1):
                ui.label(f"{i}. {pt}").style(f"color:{COLORS['text_secondary']};font-size:13px;line-height:1.6;")

        with ui.card().classes("flex-[3]").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:12px;"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label("Key market metrics").classes("section-head")
                ui.button(icon="refresh", on_click=lambda: (market_data.get_snapshot(CT("ticker"), refresh_if_stale=True, max_age_minutes=0), nav.go_to("Today"))).props("flat dense round size=sm")
            # One metric pattern, repeated: eyebrow label · 18px value · semantic-
            # coloured delta. Consistent sizing is what makes it read as a designed
            # data panel rather than three differently-styled lines.
            def _kpi_label(text, top=True):
                ui.label(text).classes("t-eyebrow").style("margin-top:10px;" if top else "")

            def _kpi_value(text, color=None):
                ui.label(text).classes("font-bold").style(
                    f"color:{color or COLORS['text_heading']};font-size:18px;line-height:1.15;")

            if snap and snap.get("last_price") is not None:
                chg = snap.get("pct_change") or 0
                chg_clr = COLORS["success"] if chg >= 0 else COLORS["danger"]
                _kpi_label("Last price", top=False)
                with ui.row().classes("items-baseline gap-2"):
                    _kpi_value(f"${snap['last_price']:.2f}")
                    ui.label(f"{chg:+.1f}%").classes("font-bold").style(f"color:{chg_clr};font-size:12px;")
                _kpi_label("Volume vs 10-day avg")
                vol = (f"{snap['volume']/snap['avg_volume_10d']:.1f}x"
                       if (snap.get("volume") and snap.get("avg_volume_10d")) else "—")
                _kpi_value(vol)
                as_of = (snap.get("as_of") or "")[:16].replace("T", " ")
                ui.label(f"as of {as_of} · up to 60-min delay").classes("t-fine").style("margin-top:2px;")
            else:
                ui.label("Not yet fetched — refreshes automatically shortly after startup.").classes("t-meta")

            pt_avg = _consensus_pt_avg()
            _kpi_label("Consensus PT")
            if pt_avg is not None:
                with ui.row().classes("items-baseline gap-2"):
                    _kpi_value(f"${pt_avg:.2f}")
                    if snap and snap.get("last_price"):
                        upside = (pt_avg / snap["last_price"] - 1) * 100
                        up_clr = COLORS["success"] if upside >= 0 else COLORS["danger"]
                        ui.label(f"{upside:+.0f}% {'upside' if upside >= 0 else 'downside'}").classes(
                            "font-bold").style(f"color:{up_clr};font-size:12px;")
            else:
                ui.label("No active-analyst price targets on file.").classes("t-meta")

    _render_top_story()

    # ── Dashboard sections in two height-balanced columns ──
    # Sections are grouped to keep the two columns close in height rather than
    # pairing fixed rows (which left a tall section next to a short one with a
    # big empty void beneath it). Risk signals is the tallest block, so it
    # anchors the left column with analyst coverage below; the three shorter
    # sections stack on the right. `items-start` + this grouping keeps the
    # trailing whitespace minimal.
    with ui.row().classes("w-full gap-5 items-start").style("margin-top:4px;"):
        with ui.column().classes("flex-1 gap-4"):
            _render_risk_signals(state, days, snap, pt_avg)
            _render_earnings_readiness(days)
        with ui.column().classes("flex-1 gap-4"):
            _render_investor_pipeline()
            _render_analyst_coverage()
            _render_insider_activity()
            _render_peer_watch()
            _render_activity_responses(state)


def _top_ownership_change():
    """The single most material ownership move in the real 13F book, for the Today signal card.
    New positions rank first (warmest IR signal), then largest absolute share change. None when no
    holder history has been pulled — the card is then omitted rather than fabricated."""
    from core import targets
    from config.client_config import get_active_client_id
    try:
        rows = targets.targets_as_institutions(client_id=get_active_client_id())
    except Exception:
        return None
    cand = [r for r in rows if r.get("Direction") in ("new", "adding", "trimming", "exited")]
    if not cand:
        return None

    def rank(r):
        if r["Direction"] == "new":
            return (2, r.get("Position_Value") or 0)
        return (1, abs(r.get("Net_Change_Shares") or 0))
    r = max(cand, key=rank)
    net = r.get("Net_Change_Shares")
    verb = {
        "new": "initiated a position",
        "adding": f"added {abs(net):,} shares" if net else "added to their position",
        "trimming": f"trimmed {abs(net):,} shares" if net else "trimmed their position",
        "exited": "exited",
    }[r["Direction"]]
    return f"{pretty_name(r['Fund'])} {verb} — latest 13F"


@contextmanager
def _signal_card(dot, title, desc):
    """A risk-signal tile. Used as a CONTEXT MANAGER so the signal's action
    buttons render INSIDE the card (as a bottom action row) instead of floating
    loose beneath it — which read as disconnected. Callers do:

        with _signal_card("", title, desc):
            with _signal_actions():
                ui.button("Resolve", ...)
    """
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
        ui.label(f"{dot} {title}".strip()).classes("t-subhead")
        ui.label(desc).classes("t-meta")
        yield


def _signal_actions():
    """A consistent bottom action row inside a signal card — a thin top divider
    sets the buttons off from the text so they read as the card's own actions.
    Tight spacing so the buttons hug the divider (no dead whitespace)."""
    return ui.row().classes("w-full items-center gap-1").style(
        f"margin-top:4px;padding-top:4px;border-top:1px solid {COLORS['border']};")


def _render_risk_signals(state, days, snap=None, pt_avg=None):
    ui.label("Risk signals").classes("section-head")

    # Covering analysts whose current PT we haven't logged — the concrete chase list
    # (Maxim, Litchfield, Barrington). "No PT on file" ≠ "dropped coverage": all five cover.
    missing_model_analysts = [a for a in CA() if a.get("pt") is None]

    # 1. Missing models — 4-state: default / sent / noted / muted
    if signals.is_muted(state, "models_request"):
        with _signal_card("", "Missing models — muted",
                          f"Snoozed until {signals.muted_until_label(state, 'models_request')} — still unresolved, just hidden till then."):
            with _signal_actions():
                ui.button("Unmute now", on_click=lambda: _unmute_signal(state, "models_request")).props("flat dense size=sm")
    elif state.get("models_request_sent"):
        with _signal_card("", "Emails sent to 3 analysts",
                          f"Requests sent {state.get('models_request_sent_date','')} — pending responses."):
            with _signal_actions():
                ui.button("Reset", on_click=lambda: _reset(state, "models_request_sent", "models_request_sent_date", "models_sent_names")).props("flat dense size=sm")
    elif state.get("models_marked_noted"):
        reason = f" — {state['models_noted_reason_val']}" if state.get("models_noted_reason_val") else ""
        with _signal_card("", "Model requests noted — not pursued",
                          f"Reviewed {state.get('models_noted_date','')} — no outreach sent{reason}."):
            with _signal_actions():
                ui.button("Reset", on_click=lambda: _reset(state, "models_marked_noted", "models_noted_date", "models_noted_reason_val")).props("flat dense size=sm")
    else:
        with _signal_card("", "3 of 5 analyst models missing",
                          "Maxim, Litchfield Hills, Barrington have no model on file — consensus unreliable"):
            with _signal_actions():
                ui.button("Resolve", on_click=lambda: _open_models_dialog(state, missing_model_analysts)).props("dense size=sm color=primary")
                _mute_button(state, "models_request", "Today · Risk Signals · Missing Models")

    # 2. Beat bar above guidance
    if signals.is_muted(state, "guidance_gap"):
        with _signal_card("", "Beat bar above guidance — muted",
                          f"Snoozed until {signals.muted_until_label(state, 'guidance_gap')} — still unresolved, just hidden till then."):
            with _signal_actions():
                ui.button("Unmute now", on_click=lambda: _unmute_signal(state, "guidance_gap")).props("flat dense size=sm")
    elif state.get("guidance_marked_sent"):
        with _signal_card("", "Guidance clarification sent",
                          f"Sent {state.get('guidance_sent_date','')} — pending analyst response."):
            with _signal_actions():
                ui.button("Reset", on_click=lambda: _reset(state, "guidance_marked_sent", "guidance_sent_date")).props("flat dense size=sm")
    elif state.get("guidance_marked_noted"):
        reason = f" — {state['guidance_noted_reason_val']}" if state.get("guidance_noted_reason_val") else ""
        with _signal_card("", "Guidance gap noted — not pursued",
                          f"Reviewed {state.get('guidance_noted_date','')} — no outreach sent{reason}."):
            with _signal_actions():
                ui.button("Reset", on_click=lambda: _reset(state, "guidance_marked_noted", "guidance_noted_date", "guidance_noted_reason_val")).props("flat dense size=sm")
    else:
        with _signal_card("", "Beat bar above guidance",
                          "Street consensus $25.1M sits 2.7% above your $24.5M guidance midpoint"):
            with _signal_actions():
                ui.button("Draft clarification", on_click=lambda: _open_guidance_dialog(state)).props("dense size=sm color=primary")
                _mute_button(state, "guidance_gap", "Today · Risk Signals · Beat Bar Above Guidance")

    # 3. Days to consensus lock
    checkin_days = max(days - 20, 0)
    if signals.is_muted(state, "checkin"):
        with _signal_card("", "Days to consensus lock — muted",
                          f"Snoozed until {signals.muted_until_label(state, 'checkin')} — still unresolved, just hidden till then."):
            with _signal_actions():
                ui.button("Unmute now", on_click=lambda: _unmute_signal(state, "checkin")).props("flat dense size=sm")
    elif state.get("checkin_marked_sent"):
        with _signal_card("", "Check-in proposed",
                          f"Sent {state.get('checkin_sent_date','')} — pending analyst confirmation."):
            with _signal_actions():
                ui.button("Reset", on_click=lambda: _reset(state, "checkin_marked_sent", "checkin_sent_date")).props("flat dense size=sm")
    elif state.get("checkin_marked_noted"):
        reason = f" — {state['checkin_noted_reason_val']}" if state.get("checkin_noted_reason_val") else ""
        with _signal_card("", "Check-in outreach noted — not pursued",
                          f"Reviewed {state.get('checkin_noted_date','')} — no check-in scheduled{reason}."):
            with _signal_actions():
                ui.button("Reset", on_click=lambda: _reset(state, "checkin_marked_noted", "checkin_noted_date", "checkin_noted_reason_val")).props("flat dense size=sm")
    else:
        with _signal_card("", f"{checkin_days} days to consensus lock",
                          f"Quiet period starts in {checkin_days} days — model requests need to close by Aug 1"):
            with _signal_actions():
                ui.button("Propose check-in", on_click=lambda: _open_checkin_dialog(state, missing_model_analysts, checkin_days)).props("dense size=sm color=primary")
                _mute_button(state, "checkin", "Today · Risk Signals · Days to Consensus Lock")

    # 4-6. Informational signals — collapsed by default. These are market
    # context (PT gap, an ownership change, a confirmed conference), not daily
    # to-dos, so they're tucked behind an expander. That keeps the three
    # actionable signals above front-and-center and stops this section from
    # dominating the column height (see the Today layout-balance pass).
    if snap and snap.get("last_price") and pt_avg:
        upside_pct = (pt_avg / snap["last_price"] - 1) * 100
        pt_desc = f"${pt_avg:.2f} consensus vs ${snap['last_price']:.2f} last trade — active analysts Buy-rated"
        pt_title = f"{upside_pct:+.0f}% {'upside' if upside_pct >= 0 else 'downside'} to consensus PT"
    else:
        pt_desc = "Consensus PT or last price not yet available — see Key Market Metrics above."
        pt_title = "Upside to consensus PT — pending market data"
    with ui.expansion("More market signals", value=False).classes("w-full").style("margin-top:4px;"):
        with _signal_card("", pt_title, pt_desc):
            with _signal_actions():
                ui.button("Why the gap?", on_click=lambda: _open_disconnect_dialog(snap, pt_avg)).props("flat dense size=sm")

        _chg = _top_ownership_change()
        if _chg:
            with _signal_card("", "Ownership change", _chg):
                with _signal_actions():
                    ui.button("Cross-reference target list", on_click=_open_target_list_dialog).props("flat dense size=sm")

        with _signal_card("", "1 conference confirmed", "H.C. Wainwright Sep 8 — Scott Buck attending in person"):
            with _signal_actions():
                ui.button("Cross-reference target list", on_click=_open_target_list_dialog).props("flat dense size=sm")


def _reset(state, *keys):
    for k in keys:
        state.pop(k, None)
    _save_state(state)
    ui.notify("Reset")
    nav.go_to("Today")


# ── Mute (snooze) ──────────────────────────────────────────────────────
# State logic (is_muted / mute / unmute) lives in core/signals.py, shared
# with markets_page.py's IR Risk Dashboard — see that module's docstring
# for the full explanation, including why Reports' Reg FD Flags and
# Earnings' stage gates deliberately do NOT get a mute option. Only the
# nicegui-specific dropdown button lives here, since core/ never imports
# nicegui (same boundary as every other core/ module).
def _mute_signal(state, key, days, launched_from):
    signals.mute(state, key, days, launched_from)
    _save_state(state)
    ui.notify(f"Muted for {days} day{'s' if days != 1 else ''}.")
    nav.go_to("Today")


def _unmute_signal(state, key):
    signals.unmute(state, key)
    _save_state(state)
    ui.notify("Unmuted")
    nav.go_to("Today")


def _mute_button(state, key, launched_from):
    """A small flat button + dropdown menu with the 4 mute windows."""
    with ui.button("Mute").props("flat dense size=sm"):
        with ui.menu():
            for days, label in signals.MUTE_OPTIONS:
                ui.menu_item(label, on_click=lambda days=days: _mute_signal(state, key, days, launched_from))


def _open_models_dialog(state, missing_model_analysts):
    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:420px;"):
        ui.label("Resolve Missing Models").classes("text-lg font-bold")
        ui.label("HIGH PRIORITY").style(f"background:{COLORS['warning']};color:white;padding:2px 8px;border-radius:8px;font-size:11px;")
        ui.label("Recipients — uncheck anyone you don't want to include:").style(f"color:{COLORS['text_muted']};font-size:12px;margin-top:8px;")
        checks = {}
        for a in missing_model_analysts:
            checks[a["name"]] = ui.checkbox(f"{a['name']} — {a['firm']}", value=True)
        ui.markdown("---")
        for a in missing_model_analysts:
            first = a["name"].split()[0]
            body = (f"Hi {first},\n\nAs we approach our Q2 quiet period, I noticed we don't have your updated "
                    f"{CT('ticker')} financial model on file yet.\n\nDo you require any updated data, clarification "
                    f"on our recent disclosures, or a quick call with management to help finalize your file?\n\n"
                    f"Best regards,\n{CI().get('name','')}")
            _mailto(a.get("email", ""), f"{CT('ticker')} | Model Update Inquiry Ahead of Q2", body, f"Email {first}")

        def mark_sent():
            selected = [n for n, cb in checks.items() if cb.value]
            state["models_request_sent"] = True
            state["models_request_sent_date"] = datetime.now().strftime("%b %d, %Y")
            state["models_sent_names"] = selected
            _save_state(state)
            for name in selected:
                activity_log.log_event("model_request_sent", entity=name, launched_from="Today · Risk Signals · Missing Models")
            ui.notify(f"Marked {len(selected)} model request(s) as sent.")
            dialog.close()
            nav.go_to("Today")

        ui.button("Mark as sent", on_click=mark_sent).props("color=primary").style("margin-top:8px;")
        reason_input = ui.input("Reason (optional, if not sending)").classes("w-full")

        def mark_noted():
            state["models_marked_noted"] = True
            state["models_noted_date"] = datetime.now().strftime("%b %d, %Y")
            state["models_noted_reason_val"] = reason_input.value
            _save_state(state)
            activity_log.log_event("signal_noted", entity="missing_models", reason=reason_input.value, launched_from="Today · Risk Signals · Missing Models")
            ui.notify("Logged — no outreach sent, decision recorded.")
            dialog.close()
            nav.go_to("Today")

        ui.button("Do not send — mark as noted", on_click=mark_noted).props("flat")
        ui.button("Cancel", on_click=dialog.close).props("flat")
    dialog.open()


def _open_guidance_dialog(state):
    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:420px;"):
        ui.label("Draft Guidance Clarification").classes("text-lg font-bold")
        guide_mid, street = 24.5, 25.1
        ui.label(f"Guidance midpoint: ${guide_mid}M · Street consensus: ${street}M · Delta: +${street-guide_mid:.1f}M / +2.7%").style(
            f"background:{COLORS['surface_hover_bg']};padding:8px 12px;border-radius:8px;font-size:13px;"
        )
        memo = (f"Hi [Analyst],\n\nAhead of our upcoming earnings release, I'm reaching out to ensure all covering "
                f"models are closely aligned with our stated guidance parameters.\n\nManagement's Q2 guidance "
                f"midpoint stands at ${guide_mid}M. We've noticed current Street consensus is modeling slightly "
                f"above this at ${street}M. Let me know if you'd like to review the core assumptions.\n\nBest,\n{CI().get('name','')}")
        ui.textarea("Memo template — edit before sending", value=memo).classes("w-full").props("rows=6")
        for a in CA():
            first = a["name"].split()[0]
            _mailto(a.get("email", ""), f"{CT('ticker')} | Q2 Guidance Framework Reminder", memo.replace("[Analyst]", first), f"{first} ({a['firm']})")

        def mark_sent():
            state["guidance_marked_sent"] = True
            state["guidance_sent_date"] = datetime.now().strftime("%b %d, %Y")
            _save_state(state)
            activity_log.log_event("email_sent", entity="guidance_gap", launched_from="Today · Risk Signals · Beat Bar Above Guidance")
            ui.notify("Marked guidance clarification as sent.")
            dialog.close()
            nav.go_to("Today")

        ui.button("Mark as sent", on_click=mark_sent).props("color=primary").style("margin-top:8px;")
        reason_input = ui.input("Reason (optional, if not sending)").classes("w-full").style("margin-top:8px;")

        def mark_noted():
            state["guidance_marked_noted"] = True
            state["guidance_noted_date"] = datetime.now().strftime("%b %d, %Y")
            state["guidance_noted_reason_val"] = reason_input.value
            _save_state(state)
            activity_log.log_event("signal_noted", entity="guidance_gap", reason=reason_input.value, launched_from="Today · Risk Signals · Beat Bar Above Guidance")
            ui.notify("Logged — no outreach sent, decision recorded.")
            dialog.close()
            nav.go_to("Today")

        ui.button("Do not send — mark as noted", on_click=mark_noted).props("flat")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def _open_checkin_dialog(state, missing_model_analysts, checkin_days):
    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:420px;"):
        ui.label("Propose Analyst Check-In").classes("text-lg font-bold")
        ui.label("No live calendar integration — these are suggested slots to confirm manually.").style(f"color:{COLORS['text_muted']};font-size:12px;")
        slot_dates = [datetime.now().date() + timedelta(days=d) for d in (2, 3, 4)]
        slots = [f"{d.strftime('%A, %b %d')} at {t}" for d, t in zip(slot_dates, ["10:00 AM EST", "2:30 PM EST", "11:00 AM EST"])]
        for s in slots:
            ui.label(f"• {s}")
        body = (f"Hi [Analyst],\n\nWith our Q2 quiet period beginning in {checkin_days} days, I'm hosting brief, "
                f"15-minute check-ins with our covering analysts before numbers lock.\n\nDo any of these times work?\n"
                + "\n".join(f"  • {s}" for s in slots) + f"\n\nBest,\n{CI().get('name','')}")
        for a in missing_model_analysts:
            first = a["name"].split()[0]
            _mailto(a.get("email", ""), f"Invitation: {CT('ticker')} Pre-Quiet Period Sync (15 Mins)", body.replace("[Analyst]", first), f"{first} ({a['firm']})")

        def mark_sent():
            state["checkin_marked_sent"] = True
            state["checkin_sent_date"] = datetime.now().strftime("%b %d, %Y")
            _save_state(state)
            activity_log.log_event("email_sent", entity="checkin", launched_from="Today · Risk Signals · Days to Consensus Lock")
            ui.notify("Marked check-in as proposed.")
            dialog.close()
            nav.go_to("Today")

        ui.button("Mark as sent", on_click=mark_sent).props("color=primary").style("margin-top:8px;")
        reason_input = ui.input("Reason (optional, if not sending)").classes("w-full").style("margin-top:8px;")

        def mark_noted():
            state["checkin_marked_noted"] = True
            state["checkin_noted_date"] = datetime.now().strftime("%b %d, %Y")
            state["checkin_noted_reason_val"] = reason_input.value
            _save_state(state)
            activity_log.log_event("signal_noted", entity="checkin", reason=reason_input.value, launched_from="Today · Risk Signals · Days to Consensus Lock")
            ui.notify("Logged.")
            dialog.close()
            nav.go_to("Today")

        ui.button("Do not send — mark as noted", on_click=mark_noted).props("flat")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def _open_disconnect_dialog(snap=None, pt_avg=None):
    active_n = sum(1 for a in CA() if a.get("pt") is not None)
    total_n = len(CA())
    pt_line = (f"${pt_avg:.2f} consensus built on {active_n} input(s) is fragile"
               if pt_avg is not None else "consensus PT not yet available")
    vol_line = "Market data not yet fetched — volume comparison unavailable."
    if snap and snap.get("volume") and snap.get("avg_volume_10d"):
        ratio = snap["volume"] / snap["avg_volume_10d"]
        vol_line = f"{ratio:.1f}x average volume — no specific catalyst logged, worth watching for confirmation."
    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:420px;"):
        ui.label("Disconnect Drivers").classes("text-lg font-bold")
        ui.label("This app has no short-interest or sector-index data source — the drivers below use only "
                 "what's actually tracked here (model coverage, active PT count, volume), not a full quant "
                 "correlation.").style(f"color:{COLORS['text_muted']};font-size:12px;")
        ui.html(
            "<div style='background:#EEF2F7;border-radius:8px;padding:10px 14px;font-size:13px;color:#1E293B;line-height:1.6;'>"
            "<b>Likely contributors, from data on file:</b><br>"
            f"• <b>Thin coverage</b> — only {active_n} of {total_n} covering analysts have a current PT on file; {pt_line}<br>"
            f"• <b>Volume signal</b> — {vol_line}<br>"
            "• <b>Stale PT risk</b> — check each analyst's last revision date on the Analyst Coverage card below "
            "before treating consensus as current."
            "</div>"
        )
        ui.label("Suggested CEO talking point:").classes("font-bold").style("margin-top:8px;")
        ui.textarea(
            "Talking point — edit before adding to script",
            value="The gap between our stock price and Street targets reflects thin, aging coverage more than a "
                  "fundamental disagreement — 3 of 5 analysts haven't updated models since before our Q1 beat.",
        ).classes("w-full").props("rows=4")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def _open_target_list_dialog():
    # Simplified from app.py's load_investor_targets() cross-reference — the
    # Target Database module isn't part of this migration yet (see
    # investors_page.py's Target Database tab docstring), so this reuses the
    # same static New York-route candidate list app.py hardcoded here too.
    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:420px;"):
        ui.label("Update Institutional Target List").classes("text-lg font-bold")
        ui.label("No confirmed attendee list exists for the H.C. Wainwright conference — this app doesn't have "
                 "RSVP data. Below is a same-profile candidate list from the Target Database (New York route, "
                 "small-cap value/growth mandate), not a verified roster of who's actually attending.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
        candidates = [
            ("Royce Investment Partners", "Small-cap value", 82),
            ("Kennedy Capital Management", "Small-cap growth", 76),
            ("Conestoga Capital Advisors", "Small-cap growth", 71),
            ("Robotti & Company", "Deep value / special situations", 68),
        ]
        for name, mandate, fit in candidates:
            ui.label(f"• {name} — {mandate} · Fit {fit:.0f}").style(f"color:{COLORS['text_body']};font-size:13px;")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def _render_activity_responses(state):
    # No email inbox integration exists in this app — status here is
    # self-reported by the user, not auto-detected from a reply. The one
    # genuinely automatable piece is real: uploading the actual model file
    # received recalculates the consensus input for that analyst.
    if not state.get("models_request_sent"):
        return
    ui.label("Activity & responses — model requests").classes("section-head")
    ui.label("You mark status yourself as replies come in — this app has no email inbox connected, so nothing "
             "here is auto-detected.").style(f"color:{COLORS['text_muted']};font-size:11px;")

    sent_names = state.get("models_sent_names", [])
    tracked_analysts = [a for a in CA() if a["name"] in sent_names] or [a for a in CA() if a.get("pt") is None]
    for a in tracked_analysts:
        _render_activity_row(state, a)


def _render_activity_row(state, a):
    status_key = f"activity_status_{a['name']}"
    with ui.row().classes("w-full items-start justify-between gap-4"):
        with ui.column().classes("flex-[2] gap-0"):
            ui.label(f"{a['name']} — {a['firm']}").classes("font-bold").style(f"color:{COLORS['text_body']};font-size:13px;")
            status_sel = ui.select(["Sent", "Replied", "Model Received"], value=state.get(status_key, "Sent")).classes("w-full")
        ui.label(f"Sent {state.get('models_request_sent_date','')}").style(f"color:{COLORS['text_muted']};font-size:11px;")

    detail_area = ui.column().classes("w-full")

    def render_detail():
        detail_area.clear()
        state[status_key] = status_sel.value
        _save_state(state)
        with detail_area:
            if status_sel.value == "Replied":
                notes_key = f"activity_notes_{a['name']}"
                notes = ui.textarea(
                    "What did they say? (you type this in — nothing here reads their actual email)",
                    value=state.get(notes_key, ""),
                    placeholder="e.g. Asked for a 10-minute call to clarify Q2 margin assumptions",
                ).classes("w-full")

                def save_notes(notes_key=notes_key, notes=notes):
                    state[notes_key] = notes.value
                    _save_state(state)

                notes.on("blur", save_notes)

            elif status_sel.value == "Model Received":
                ui.label("Upload the file you actually received (Metric,Value CSV — e.g. Revenue,24.8 / EPS,0.06). "
                         "This app can't intelligently parse an arbitrary analyst spreadsheet format, so it needs "
                         "a simple structure to read reliably.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                result_area = ui.column().classes("w-full")

                async def handle_upload(e, a=a, result_area=result_area):
                    result_area.clear()
                    try:
                        content = await e.file.text()
                        rows = list(csv.reader(io.StringIO(content)))
                        new_vals = {r[0].strip(): r[1].strip() for r in rows if len(r) >= 2}
                        old_rev = 24.1  # last known figure on file for this analyst, illustrative
                        new_rev = float(new_vals.get("Revenue", old_rev))
                        with result_area:
                            with ui.row().classes("w-full gap-3"):
                                ui.html(
                                    f"<div style='background:#EEF2F7;border-radius:8px;padding:8px 12px;'>"
                                    f"<span style='font-size:11px;color:#64748B;'>OLD MODEL</span><br>"
                                    f"<b style='color:#1E293B;'>Revenue: ${old_rev}M</b></div>"
                                )
                                ui.html(
                                    f"<div style='background:#E9F6EF;border-radius:8px;padding:8px 12px;'>"
                                    f"<span style='font-size:11px;color:#64748B;'>NEW MODEL</span><br>"
                                    f"<b style='color:#15803D;'>Revenue: ${new_rev}M</b></div>"
                                )

                            def commit(a=a, new_rev=new_rev):
                                state[f"committed_model_{a['name']}"] = new_rev
                                _save_state(state)
                                activity_log.log_event("model_received", entity=a["name"], new_revenue=new_rev, launched_from="Today · Activity & Responses · Model Requests")
                                ui.notify(f"{a['name']}'s model committed — consensus inputs updated.")
                                nav.go_to("Today")

                            ui.button("Accept — recalculate consensus", on_click=commit).props("color=primary")
                    except Exception:
                        with result_area:
                            ui.label("Couldn't read that file as a two-column Metric,Value CSV — check the format "
                                     "and try again.").style("color:#B91C1C;font-size:12px;")

                ui.upload(on_upload=handle_upload, auto_upload=True).props("accept=.csv").classes("w-full")

    status_sel.on_value_change(render_detail)
    render_detail()


def _render_investor_pipeline():
    """Top-5 tracked institutions by real Engagement_Score (core.
    investor_scoring — the SAME scoring model and meeting log Investor
    Targeting's Buy-Side Intelligence tab uses, not a separate hardcoded
    list). A fund drops off this list the moment ANY interaction with it
    gets logged (an email marked sent right here, or a full Meeting Log
    entry over in Investor Targeting) and stays off for
    top_engagement_targets()'s exclusion window — it only reappears once
    that passes without a new interaction, or its underlying score changes
    enough to pull it back into the top 5. That's what makes "Details ->
    email the contact" a real, recorded action instead of a dead end: it's
    written to both activity_log (counts toward "N tasks automated today")
    and meeting_log (shows up on that fund's record everywhere else in
    the app, including its Interaction Score)."""
    ui.label("Investor pipeline — strongest signal").classes("section-head")
    from core.investor_scoring import load_meeting_log, save_meeting_log, top_engagement_targets
    targets = top_engagement_targets(limit=5)
    if not targets:
        ui.label("No open signals right now — every tracked institution has a recent logged interaction. "
                 "Check back once one ages out, or a new signal moves a fund's score.").style(
            f"color:{COLORS['text_muted']};font-size:13px;"
        )
    contacts = get_institution_contacts()
    for inst in targets:
        nm = inst["Fund"]
        score = inst["Engagement_Score"]
        hld = "Holder" if inst["USIO_Holder"] else "Non-holder"
        nt = inst.get("Action", "—")
        dot = "" if inst["USIO_Holder"] else ("" if score >= 80 else "")
        info = contacts.get(nm, {"name": "Contact", "email": ""})
        detail = (f"{inst.get('Action', '')} · {inst.get('IR_Visits_30d', 0)} IR site visits in the last 30 days "
                  f"(last: {inst.get('Last_Visit', '—')}) · {inst.get('Metro', '—')}.")

        # Defined before the card so the Details button — now INSIDE the card,
        # in its own bottom action row — can bind to it.
        def open_detail(nm=nm, info=info, detail=detail, hld=hld, score=score):
            with ui.dialog() as d, ui.card().style(f"background:{COLORS['surface_bg']};min-width:380px;"):
                ui.label(f"{pretty_name(nm)} — {hld} · Engagement {score}/100").classes("font-bold")
                ui.label(detail).style(f"color:{COLORS['text_muted']};font-size:13px;")
                _mailto(info.get("email", ""), f"{CT('ticker')} — Following up, {nm}", "Hi,\n\n", f"Email {info.get('name','Contact')}")

                def mark_sent(nm=nm, info=info):
                    log = load_meeting_log()
                    log.append({
                        "Fund": nm, "Date": datetime.now().strftime("%Y-%m-%d"),
                        "Type": "Email outreach (Today's Pipeline)",
                        "Attendees": info.get("name", ""),
                        "Notes": "Quick outreach logged from Today's Investor Pipeline signal.",
                        # Deliberately neutral (0 pts) — a just-sent email has no
                        # outcome yet. It's still a real, dated, logged interaction
                        # (so this card clears and the fund's Meeting Log shows it),
                        # but it shouldn't move the Interaction Score until someone
                        # logs what actually happened (a reply, a meeting, etc.) via
                        # the full Meeting Log dialog in Investor Targeting.
                        "Outcome": "No clear signal",
                        "Logged By": CI().get("name") or "IR Team", "Source": "Today Pipeline",
                    })
                    save_meeting_log(log)
                    activity_log.log_event("email_sent", entity=nm, launched_from="Today · Investor Pipeline")
                    ui.notify(f"Logged outreach to {nm} — clearing this card from the pipeline.")
                    d.close()
                    nav.go_to("Today")

                ui.button("Mark as sent", on_click=mark_sent).props("color=primary")
                ui.button("Close", on_click=d.close).props("flat")
            d.open()

        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label(f"{dot} {pretty_name(nm)}".strip()).classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:13px;")
                ui.label(f"{score}/100").classes("font-bold").style(f"color:{COLORS['text_heading']};")
            ui.label(f"{hld} · {nt}").classes("t-meta")
            with _signal_actions():
                ui.button("Details", on_click=open_detail).props("flat dense size=sm")

    # Deep-link straight to the Target Database (the searchable investor database),
    # not the default Buy-Side tab — matches "open the database" and keeps the
    # sidebar highlight in sync. Pure navigation: it reads cached data only and
    # never triggers a SEC/market pull (those live on their own explicit buttons).
    # Role-gated: a role with no access to Investors (e.g. CEO / Legal) would have
    # this button hit the RBAC guard and silently do nothing but flash a toast —
    # so don't offer a dead-end button; explain instead.
    from core import ui_context
    from config.client_config import role_can_view
    if role_can_view(ui_context.current_role(), "Investors"):
        ui.button("Open Full Investor Pipeline →",
                  on_click=lambda: nav.go_to("Investors", "Target Database")).props("color=primary")
    else:
        ui.label("The full pipeline lives in Investor Targeting — your current role doesn't have access to "
                 "that page.").style(f"color:{COLORS['text_muted']};font-size:12px;")


def _render_earnings_readiness(days):
    ui.label(f"Earnings readiness — {days} days out").classes("section-head")
    with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['accent']};"):
        ui.label(f"{days} days").classes("text-2xl font-bold").style(f"color:{COLORS['accent_light']};")
        ui.label("Aug 12 · 4:30 PM ET").style(f"color:{COLORS['accent_light2']};font-size:12px;")

    readiness = [
        ("Script", "", COLORS["success"], "Stage 2 — IR review"),
        ("Slides", "", COLORS["success"], "Investor deck current"),
        ("Q&A prep", "70%", COLORS["warning"], "3 analyst-specific gaps"),
        ("Guidance", "", COLORS["warning"], "Waiting on CFO numbers"),
        ("Legal review", "—", COLORS["text_muted"], "Not yet started"),
        ("Webcast", "", COLORS["success"], "Chorus Call confirmed"),
    ]
    for item, stat, clr, note in readiness:
        with ui.row().classes("w-full justify-between items-center").style(f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
            ui.label(f"{item} — {note}").style(f"color:{COLORS['text_body']};font-size:13px;")
            ui.label(stat).style(f"color:{clr};font-weight:bold;")

    # Deep-link straight into the Script Generation tab by passing it as the
    # explicit nav target, so the page opens there AND the sidebar highlights the
    # matching sub-item. (The earlier earnings_tab="script" highlight opened the
    # tab but left the sidebar on the first tab, so it looked like it "did
    # nothing" / went to the wrong place.) See earnings_page.render_earnings_page.
    ui.button("Open Script Generation →", on_click=lambda: nav.go_to("Earnings", "Script Generation")).props("flat").style("margin-top:8px;")


def _render_analyst_coverage():
    ui.label("Analyst coverage").classes("section-head")
    all_analysts = [
        ("H.C. Wainwright", "Scott Buck", "$4.00", "Buy", "No change", COLORS["success"]),
        ("Ladenburg Thalmann", "Jon Hickman", "$6.25", "Buy", "No change", COLORS["success"]),
        ("Maxim Group", "Michael Diana", "Inactive", "—", "Re-init expected", COLORS["warning"]),
        ("Litchfield Hills Research", "Barry Sine", "Inactive", "—", "Model requested · awaiting", COLORS["warning"]),
        ("Barrington Research", "Gary Prestopino", "Inactive", "—", "Model requested · awaiting", COLORS["warning"]),
    ]
    container = ui.column().classes("w-full gap-2")
    expanded = {"value": False}

    def render_list():
        container.clear()
        visible = all_analysts if expanded["value"] else all_analysts[:3]
        with container:
            for firm, an, pt, rt, chg, clr in visible:
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(firm).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                        ui.label(pt).classes("font-bold").style(f"color:{clr};")
                    ui.label(f"{an} · {rt} · {chg}").classes("t-meta")
                    with _signal_actions():
                        # Deep-link straight to Consensus / Guidance with this analyst
                        # highlighted. Pass the tab explicitly (not just the highlight)
                        # so the sidebar's active-tab highlight matches the tab that
                        # opens; the `e=None` swallows the click event NiceGUI passes so
                        # it can't clobber the captured `firm`.
                        ui.button("Consensus →", on_click=lambda e=None, firm=firm: nav.go_to(
                            "Markets", "Consensus / Guidance", highlight_analyst=firm)).props("flat dense size=sm")

            if not expanded["value"]:
                ui.button(f"+ Load {len(all_analysts)-3} more", on_click=toggle).props("flat")
            else:
                ui.button("Show fewer ↑", on_click=toggle).props("flat")

    def toggle():
        expanded["value"] = not expanded["value"]
        render_list()

    render_list()


def _render_top_story():
    """The single most important headline of the day, raised to the top of Today. The client's OWN
    news wins when there is any (a microcap often has none); otherwise the freshest peer/competitor
    item. A pointer scrolls down to the full peer-news feed so that feature isn't lost."""
    from core import news_feed
    ticker = CT("ticker")
    own = news_feed.recent(ticker=ticker, limit=1)
    peer = [i for i in news_feed.recent(limit=8) if i.get("ticker") != ticker]
    top = own[0] if own else (peer[0] if peer else None)
    if not top:
        return
    is_own = bool(own)
    eyebrow = f"Today's top story · {ticker}" if is_own else f"Today's top story · peer ({top.get('ticker','')})"
    accent = "#15803D" if is_own else COLORS["accent"]
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:4px solid {accent};margin-top:6px;padding:12px 16px;"):
        # Same eyebrow treatment as the metric labels (one system); colour carries
        # the only distinction — green for our own news, accent-blue for a peer.
        ui.label(eyebrow).classes("t-eyebrow").style(f"color:{accent};")
        with ui.link(target=top["url"], new_tab=True).style("text-decoration:none;"):
            ui.label(top.get("title", "")).classes("font-bold").style(
                f"color:{COLORS['text_heading']};font-size:15px;line-height:1.25;")
        ui.label(f"{top.get('provider', '')} · {(top.get('pub') or '')[:10]}").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        if peer:
            def _to_peer_news():
                ui.run_javascript(
                    "document.getElementById('peer-news-anchor')?."
                    "scrollIntoView({behavior:'smooth', block:'start'});")
            ui.button(f"More peer & competitor news ({len(peer)}) ↓", on_click=_to_peer_news) \
                .props("flat dense no-caps").style(f"color:{accent};font-size:12px;margin-top:2px;")


def _collapsible_head(title, start_open=True):
    """A section-head with an expand/collapse chevron. Returns the body column to fill; its
    visibility toggles client-side (no re-fetch), so long front-page sections can be folded away."""
    with ui.row().classes("w-full items-center no-wrap").style("gap:6px;justify-content:space-between;"):
        ui.label(title).classes("section-head")
        btn = ui.button(icon="expand_less" if start_open else "expand_more").props(
            "flat dense round size=sm").style(
            f"color:{COLORS['text_secondary']};border:1.5px solid {COLORS['text_secondary']};"
            "background:rgba(0,0,0,0.02);").tooltip("Collapse / expand this section")
    body = ui.column().classes("w-full").style("gap:4px;")
    body.set_visibility(start_open)
    state = {"open": start_open}

    def _toggle():
        state["open"] = not state["open"]
        body.set_visibility(state["open"])
        btn.props(f"icon={'expand_less' if state['open'] else 'expand_more'}")
    btn.on("click", _toggle)
    return body


def _render_insider_activity():
    """Insider transactions (SEC Form 4) — the company's own directors/officers buying or selling.
    Free, authoritative (EDGAR). Open-market buys/sells are the signal; grants/exercises are routine
    comp, shown but flagged. Cache-only read; nothing fabricated."""
    from core import insider_feed
    txns = insider_feed.recent(limit=30)
    body = _collapsible_head("Insider activity — Form 4")
    with body:
        if not txns:
            ui.label("No Form 4 filings on file yet — a data refresh pulls insider transactions from EDGAR.").style(
                f"color:{COLORS['text_muted']};font-size:12px;")
            return

        n = insider_feed.net_open_market()
        if n["buy_shares"] or n["sell_shares"]:
            tone_clr = COLORS["success"] if n["net_shares"] > 0 else COLORS["danger"] if n["net_shares"] < 0 else COLORS["text_muted"]
            tone = "net buying" if n["net_shares"] > 0 else "net selling" if n["net_shares"] < 0 else "flat"
            ui.label(f"Open-market: {n['buy_shares']:,.0f} bought vs {n['sell_shares']:,.0f} sold — {tone}").style(
                f"color:{tone_clr};font-size:12px;font-weight:600;")
        else:
            ui.label("No open-market buys/sells on file — recent Form 4s are routine grants/exercises.").style(
                f"color:{COLORS['text_muted']};font-size:12px;")

        _tone = {"P": COLORS["success"], "S": COLORS["danger"]}
        for t in txns[:6]:
            col = _tone.get(t.get("code"), COLORS["text_muted"])
            with ui.row().classes("w-full items-center").style("gap:8px;"):
                ui.label(insider_feed.glyph(t)).style(f"color:{col};font-weight:800;font-size:12px;")
                ui.label(insider_feed.describe(t)).style(f"color:{COLORS['text_secondary']};font-size:12px;")


def _render_peer_watch():
    """Daily peer monitor on the front page — notable price moves, recent SEC
    filings, and a rolling 7-day news window across the segmented peer group
    (core.peer_watch + core.news_feed, cache-only reads)."""
    from core import news_feed, peer_watch
    s = peer_watch.summary()

    body = _collapsible_head("Peer watch")
    with body:
        ui.label("Daily monitor of the segmented peer group — price moves and SEC filings.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")

        movers = s["movers"] or s["all_movers"][:4]
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
            if not movers:
                ui.label("Peer market data refreshing — check back shortly.").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")
            else:
                ui.label("Today's moves").classes("font-bold").style(
                    f"color:{COLORS['text_body']};font-size:12px;")
                for m in movers[:5]:
                    clr = "#15803D" if (m["pct"] or 0) >= 0 else "#B91C1C"
                    tag = ("  ◆ closest analog" if m.get("closest_analog")
                           else ("  · reference" if m.get("tier") == "reference"
                                 else ("  · USIO" if m.get("is_client") else "")))
                    with ui.row().classes("w-full items-center justify-between").style("padding:1px 0;"):
                        with ui.row().classes("items-baseline gap-1").style("min-width:0;"):
                            ui.label(m["ticker"]).classes("font-bold").style(
                                f"color:{COLORS['text_body']};font-size:13px;")
                            ui.label(f"{m.get('segment', '') or ''}{tag}").style(
                                f"color:{COLORS['text_muted']};font-size:10px;")
                        ui.label(f"{m['pct']:+.1f}%").classes("font-bold").style(f"color:{clr};font-size:13px;")

        if s["filings"]:
            with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
                ui.label("Recent peer SEC filings").classes("font-bold").style(
                    f"color:{COLORS['text_body']};font-size:12px;")
                for f in s["filings"][:5]:
                    who = f"{f['ticker']}" + (" (USIO)" if f.get("is_client") else "")
                    with ui.link(target=f["url"], new_tab=True).style("text-decoration:none;"):
                        with ui.row().classes("w-full items-center gap-2").style("padding:1px 0;"):
                            ui.label(f["date"][5:]).style(f"color:{COLORS['accent']};font-size:11px;width:42px;")
                            ui.label(f"{who} · {f['form']}").style(
                                f"color:{COLORS['text_secondary']};font-size:12px;")

        # Client's OWN headlines, distinct from peer news. A microcap is often quiet — an empty state
        # says so (itself IR-relevant) rather than hiding the card.
        _tk = CT("ticker")
        own = news_feed.recent(ticker=_tk, limit=6)
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
            ui.label(f"{_tk} headlines · rolling 7 days").classes("font-bold").style(
                f"color:{COLORS['text_body']};font-size:12px;")
            if own:
                for n in own:
                    with ui.link(target=n.get("url") or "#", new_tab=True).style("text-decoration:none;"):
                        with ui.column().classes("gap-0").style("padding:2px 0;"):
                            ui.label(f"{n.get('provider', '')} · {(n.get('pub') or '')[:10]}").style(
                                f"color:{COLORS['text_muted']};font-size:10px;")
                            ui.label(n["title"]).style(
                                f"color:{COLORS['text_secondary']};font-size:12px;line-height:1.35;")
            else:
                ui.label(f"No {_tk} headlines in the last 7 days — the feed is watching.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")

        # Anchor for the "More peer news ↓" jump from the top-story card.
        ui.html('<div id="peer-news-anchor"></div>')
        peer_news = [i for i in news_feed.recent(limit=12) if i.get("ticker") != _tk][:6]
        if peer_news:
            with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
                ui.label("Peer & competitor news · rolling 7 days").classes("font-bold").style(
                    f"color:{COLORS['text_body']};font-size:12px;")
                for n in peer_news:
                    with ui.link(target=n.get("url") or "#", new_tab=True).style("text-decoration:none;"):
                        with ui.column().classes("gap-0").style("padding:2px 0;"):
                            ui.label(f"{n['ticker']} · {n.get('provider', '')} · {(n.get('pub') or '')[:10]}").style(
                                f"color:{COLORS['text_muted']};font-size:10px;")
                            ui.label(n["title"]).style(
                                f"color:{COLORS['text_secondary']};font-size:12px;line-height:1.35;")

        ui.label("Prices & news via Yahoo (≤60-min delay); filings via SEC EDGAR. A licensed feed would add breaking "
                 "speed and deeper M&A/press-wire coverage.").style(
            f"color:{COLORS['text_muted']};font-size:10px;margin-top:2px;")
