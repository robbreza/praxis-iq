"""
page_modules_nicegui/markets_page.py — Markets (IR Risk Dashboard, Consensus
Matrix, PT Drift Tracker), NiceGUI version.

Ported from app.py's ~1,166-line "Markets" section with these documented
simplifications:

- IR Risk Dashboard is ported with full fidelity: the at-a-glance strip,
  the actionable IR signals list, the overall IR risk score, and the full
  6-category / 24-indicator risk grid.
- Consensus Matrix: the estimate-horizon summary cards, the full
  period-by-period consensus table (color-coded street-vs-guidance
  variance, consensus/guidance/variance rows), and the by-analyst
  cross-period view (with the "runs hot/conservative on EPS" pattern
  detection) are all ported. The manual "edit an analyst estimate" and
  "update guidance" forms are ported too, but now write directly to the
  same client-scoped JSON copy of the estimates/guidance that the table
  reads from — in the original, the edit form saved to a separate CSV file
  that the displayed table didn't actually read from, so edits silently
  didn't show up. That inconsistency is fixed here rather than reproduced.
  Retrieving a model from the IRConnect mailbox is now real, just not on
  this page: core/mail_gateway.py routes a sell-side analyst's model email
  into a review queue investors_page.py surfaces ("Pending Model Reviews"),
  and confirming one there calls the same core/consensus.py update this
  page's manual edit form calls — so a model that arrives by email and one
  typed in by hand land in the exact same place. The Today → Markets
  analyst deep-link (clicking "→" next to an analyst on Today's Analyst
  Coverage card) is wired up via nav.highlights: it jumps straight to this
  tab, auto-expands "Track one analyst," pre-selects the matching firm, and
  shows a one-time "Jumped here from Today" banner — mirroring app.py's
  st.session_state["highlight_analyst"] pattern.
- PT Drift Tracker: the 8-quarter PT-history chart (via NiceGUI's Plotly
  element), the analyst drift table, PT justification cards, the inactive-
  analyst credibility note, and the PT credibility watchlist are all
  ported. The "Export as Board Slide (.pptx)" button IS ported, but as a
  from-scratch rebuild rather than a port: app.py's version shelled out to
  a Node.js script (generate_pt_slide.js) that was never actually included
  anywhere in the project, so that button would have failed if clicked
  even in the demo. core/board_slides.py replaces it with a pure-Python
  (python-pptx) generator that runs in-process, no Node.js dependency —
  see that module's docstring for the design rationale.

Consensus estimates and guidance are seeded per-client from
data/seed/consensus_estimates.py, then overridden by any edits saved via
core.db (SQLite) under the keys period_estimates.json / period_guidance.json
— same pattern as every other ported page. (core.db imports any
pre-existing file under those names on first read, so edits saved before
the SQLite migration aren't lost. See core/db.py.)

As of this pass, that seed-then-override read/write logic lives in
core/consensus.py rather than inline here, since a second writer
(core/mail_gateway.py's model-intake review flow) now needs the exact same
merge logic and the exact same save calls — see that module's docstring.
This page calls core.consensus.get_consensus/update_estimate/update_guidance
instead of loading/saving period_estimates.json/period_guidance.json itself.
"""

from datetime import datetime

import plotly.graph_objects as go
from nicegui import ui

from config.client_config import CA, CE, CT, get_active_client_id
from config.theme_tokens import ACTIVE as COLORS
from core import activity_log, board_slides, consensus as consensus_store
from core import db, market_data, risk_scorecard, signals
from data.seed.consensus_estimates import ALL_PERIODS, DERIVED_PERIODS
from page_modules_nicegui import nav


def _load_json(name, default):
    return db.load_json(name, default)


def _save_json(name, data):
    db.save_json(name, data)


def render_markets_page():
    client_id = get_active_client_id()
    seed = consensus_store.get_consensus(client_id)
    period_guidance = seed["period_guidance"]
    period_estimates = seed["period_estimates"]
    state = _load_json("markets_state.json", {})

    earnings = CE()
    try:
        days_to_earn = (datetime.strptime(earnings.get("earnings_date", ""), "%Y-%m-%d").date() - datetime.now().date()).days
    except Exception:
        days_to_earn = 0

    ui.label("Consensus · Price Targets · Risk Signals").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    # Deep-link from Today's Analyst Coverage ("→" jump next to an analyst):
    # consume the highlight once per page visit — mirrors app.py's
    # st.session_state["highlight_analyst"] pattern (set, shown once, cleared).
    highlighted_analyst = nav.highlights.pop("highlight_analyst", None)

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("⚖️ IR Risk Dashboard")
        t2 = ui.tab("📊 Consensus Matrix")
        t3 = ui.tab("📈 PT Drift Tracker")
    with ui.tab_panels(tabs, value=t2 if highlighted_analyst else t1).classes("w-full"):
        with ui.tab_panel(t1):
            _render_risk_dashboard(seed, days_to_earn, state)
        with ui.tab_panel(t2):
            _render_consensus_matrix(seed, period_guidance, period_estimates, highlighted_analyst)
        with ui.tab_panel(t3):
            _render_pt_drift(seed)


# ─────────────────────────────────────────────────────────────────────────
# IR Risk Dashboard
# ─────────────────────────────────────────────────────────────────────────
def _render_risk_dashboard(seed, days_to_earn, state):
    ingested = sum(1 for a in CA() if a.get("status") == "active")
    total_analysts = len(CA())
    snap = market_data.get_snapshot(CT("ticker"))
    last_price = snap["last_price"] if snap and snap.get("last_price") is not None else CT("last_price", 0)
    price_sub = (snap.get("as_of") or "")[:16].replace("T", " ") if snap and snap.get("last_price") is not None else CT("price_date", "not yet fetched")

    pt_avg = risk_scorecard._consensus_pt_avg()
    if pt_avg is not None and snap and snap.get("last_price"):
        pt_sub = f"{(pt_avg/snap['last_price']-1)*100:+.0f}% upside"
        pt_val = f"${pt_avg:.2f}"
    else:
        pt_sub = "see Consensus Matrix"
        pt_val = f"${pt_avg:.2f}" if pt_avg is not None else "—"

    with ui.row().classes("w-full gap-3"):
        _metric("Days to earnings", str(days_to_earn), CE().get("earnings_date", ""))
        _metric("Models ingested", f"{ingested} / {total_analysts}", f"{total_analysts-ingested} missing")
        _metric("Consensus PT", pt_val, pt_sub)
        _metric("Last price", f"${last_price:.2f}" if isinstance(last_price, (int, float)) else f"${last_price}", price_sub)

    ui.markdown("---")
    ui.label("🚨 IR Risk Dashboard").classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};")
    last_price_str = f"${last_price:.2f}" if isinstance(last_price, (int, float)) else f"${last_price}"
    ui.label(f"{CT('ticker')} · Last trade {last_price_str} · Earnings {CE().get('earnings_date','')} · "
             f"{days_to_earn} days to consensus lock").style(f"color:{COLORS['text_muted']};font-size:12px;")

    ui.markdown("---")
    ui.label("Actionable IR signals — what to do this week").classes("font-bold")
    ui.label(
        "Closed loop: click into any signal to resolve it or log it as reviewed-but-not-pursued — "
        "these cards track a decision, not just a readout."
    ).style(f"color:{COLORS['text_muted']};font-size:11px;margin-bottom:4px;")

    level_colors = {"red": ("#2D1212", "#FF6B6B"), "amber": ("#2D2210", "#F0A830"),
                     "green": ("#152A1E", "#6BCB77"), "gray": ("#1E2D42", "#94A3B8")}
    resolve_verb = {"red": "Resolve", "amber": "Resolve", "green": "Acknowledge", "gray": "Acknowledge"}
    # Computed from real data (core.risk_scorecard) wherever a source exists
    # — missing-models count, beat-bar gap, and PT upside are all real
    # queries now, not literals. The two "blind spot" cards and the NY
    # Metro NDR prompt are still pulled from seed — no real data source
    # exists in this app for insider trading / short interest, and NDR-trip
    # readiness isn't wired into this computation yet (see risk_scorecard.py
    # module docstring).
    actionable_signals = risk_scorecard.compute_actionable_signals()
    for i, sig in enumerate(actionable_signals):
        bg, tc = level_colors.get(sig["level"], ("#1E2D42", "#94A3B8"))
        r_key, n_key, d_key, rs_key = f"risk_{i}_resolved", f"risk_{i}_noted", f"risk_{i}_date", f"risk_{i}_reason"
        m_key = f"risk_{i}"  # mute key — separate namespace from resolved/noted/date/reason above
        if signals.is_muted(state, m_key):
            with ui.card().classes("w-full").style("background:#1E1E2D;border:1px solid #6C7A9455;"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"🔇 {sig['title']} — muted").classes("font-bold").style("color:#FFFFFF;font-size:14px;")
                        ui.label(f"Snoozed until {signals.muted_until_label(state, m_key)} — still unresolved, just hidden till then.").style("color:#94A3B8;font-size:12px;")
                    ui.button("🔔 Unmute now", on_click=lambda i=i, m_key=m_key: _unmute_signal(state, m_key)).props("flat dense")
        elif state.get(r_key):
            with ui.card().classes("w-full").style("background:#152A1E;border:1px solid #6BCB7755;"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"✅ {sig['title']}").classes("font-bold").style("color:#FFFFFF;font-size:14px;")
                        ui.label(f"Resolved {state.get(d_key,'')}").style("color:#6BCB77;font-size:12px;")
                    ui.button("↺ Reset", on_click=lambda i=i: _reset_signal(state, i)).props("flat dense")
        elif state.get(n_key):
            reason = f" — {state[rs_key]}" if state.get(rs_key) else ""
            with ui.card().classes("w-full").style("background:#1E2D42;border:1px solid #94A3B855;"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"🔵 {sig['title']}").classes("font-bold").style("color:#FFFFFF;font-size:14px;")
                        ui.label(f"Noted — not pursued {state.get(d_key,'')}{reason}").style("color:#94A3B8;font-size:12px;")
                    ui.button("↺ Reset", on_click=lambda i=i: _reset_signal(state, i)).props("flat dense")
        else:
            with ui.card().classes("w-full").style(f"background:{bg};border:1px solid {tc}55;"):
                with ui.row().classes("w-full items-start justify-between gap-2"):
                    with ui.row().classes("items-start gap-2"):
                        ui.label(sig["icon"]).style("font-size:18px;")
                        with ui.column().classes("gap-0"):
                            ui.label(sig["title"]).classes("font-bold").style("color:#FFFFFF;font-size:14px;")
                            ui.label(sig["desc"]).style(f"color:{COLORS['text_muted']};font-size:12.5px;")
                            ui.label(f"→ {sig['action']}").style(f"color:{tc};font-size:12.5px;font-weight:600;")
                    with ui.column().classes("items-end gap-1"):
                        ui.button(
                            f"▸ {resolve_verb.get(sig['level'], 'Resolve')}",
                            on_click=lambda i=i, sig=sig: _open_signal_dialog(state, i, sig),
                        ).props("flat dense").style(f"color:{tc};")
                        _mute_button(state, m_key, f"Markets · IR Risk Dashboard · {sig['title']}")

    ui.markdown("---")
    ui.label("🔴 Problem — act this week · ⚠️ Watch — monitor · ✅ In line — no action · ⚪ Blind spot — not tracked").style(f"color:{COLORS['text_muted']};font-size:11px;")

    # Computed from real data (core.risk_scorecard) — see that module's
    # docstring for exactly which of the 24 indicators are grounded in a
    # real source (market_data, sec_filings, Reg FD log, Script Generation
    # state, Consensus Tracker log) vs. still GRAY/Not Tracked because no
    # source exists anywhere in this app.
    risk_categories = risk_scorecard.compute_scorecard()
    risk_colors = {"RED": "#F87171", "ORANGE": "#F0A830", "YELLOW": "#F0D030", "GREEN": "#4ADE80", "GRAY": "#94A3B8"}
    tracked_scores = {"RED": 25, "ORANGE": 50, "YELLOW": 70, "GREEN": 100}
    all_items = [item for items in risk_categories.values() for item in items]
    tracked_items = [i for i in all_items if i[1] != "GRAY"]
    overall_score = round(sum(tracked_scores[i[1]] for i in tracked_items) / len(tracked_items)) if tracked_items else 0
    overall_level = "RED" if overall_score < 40 else "ORANGE" if overall_score < 60 else "YELLOW" if overall_score < 80 else "GREEN"
    oc = risk_colors[overall_level]

    with ui.card().classes("w-full text-center").style(f"background:{oc}22;border:1px solid {oc};"):
        ui.label("OVERALL IR RISK SCORE").style(f"color:{COLORS['text_muted']};font-size:11px;")
        ui.label(f"{overall_score} / 100 — {overall_level}").classes("text-2xl font-bold").style(f"color:{oc};")
        ui.label(f"{len(tracked_items)} of {len(all_items)} indicators actually tracked · "
                  f"{len(all_items)-len(tracked_items)} marked ⚪ Not Tracked, excluded rather than guessed at").style(
            f"color:{COLORS['text_muted']};font-size:11px;")

    ui.markdown("---")
    with ui.expansion("📋 Show the 6 risk categories (24 indicators)", value=True).classes("w-full"):
        with ui.row().classes("w-full gap-6"):
            cat_names = list(risk_categories.keys())
            for col_start in (0, len(cat_names) // 2 + len(cat_names) % 2):
                with ui.column().classes("flex-1"):
                    for cat_name in cat_names[col_start:col_start + (len(cat_names) // 2 + len(cat_names) % 2)]:
                        ui.label(cat_name).classes("font-bold")
                        for label, status, reason in risk_categories[cat_name]:
                            sc = risk_colors[status]
                            dot = "⚪" if status == "GRAY" else "🔴" if status == "RED" else "🟠" if status == "ORANGE" else "🟡" if status == "YELLOW" else "🟢"
                            with ui.card().classes("w-full").style(f"background:{sc}18;border-left:3px solid {sc};"):
                                with ui.row().classes("w-full justify-between"):
                                    ui.label(label).style(f"color:{COLORS['text_body']};font-size:12px;")
                                    ui.label(f"{dot} {status if status!='GRAY' else 'N/T'}").style(f"color:{sc};font-size:11px;font-weight:bold;")
                                ui.label(reason).style(f"color:{COLORS['text_muted']};font-size:10.5px;")


def _last_price():
    """Live last price (core.market_data) with a graceful fallback to the
    static CLIENT_REGISTRY value if market data hasn't been fetched yet —
    shared by the Consensus Matrix and PT Drift Tracker so both stay
    consistent with the Risk Dashboard's own price, instead of each
    reading a stale config literal independently."""
    snap = market_data.get_snapshot(CT("ticker"))
    if snap and snap.get("last_price") is not None:
        return snap["last_price"]
    return CT("last_price", 2.15)


def _metric(label, value, sub):
    with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(value).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_body']};font-size:11px;font-weight:600;")
        ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:10.5px;")


def _open_signal_dialog(state, i, sig):
    """Closed-loop dialog for one Actionable IR signal card — mirrors the
    resolve/note/reset pattern in today_page.py's Risk Signals (same three
    states, same state-persistence approach), so a signal raised here can
    actually be clicked through and closed out rather than just read."""
    r_key, n_key, d_key, rs_key = f"risk_{i}_resolved", f"risk_{i}_noted", f"risk_{i}_date", f"risk_{i}_reason"
    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:420px;"):
        ui.label(sig["title"]).classes("text-lg font-bold")
        ui.label(sig["desc"]).style(f"color:{COLORS['text_muted']};font-size:12.5px;")
        ui.label(f"Suggested action: {sig['action']}").style(
            f"color:{COLORS['accent_light']};font-size:13px;font-weight:600;margin-top:6px;"
        )

        def mark_resolved():
            state[r_key] = True
            state[d_key] = datetime.now().strftime("%b %d, %Y")
            _save_json("markets_state.json", state)
            activity_log.log_event("signal_resolved", entity=f"risk_{i}", launched_from=f"Markets · IR Risk Dashboard · {sig['title']}")
            ui.notify("Marked resolved.")
            dialog.close()
            nav.go_to("Markets")

        ui.button("✅ Mark Resolved", on_click=mark_resolved).props("color=primary").style("margin-top:10px;")

        reason_input = ui.input("Reason (optional, if noting instead)").classes("w-full").style("margin-top:6px;")

        def mark_noted():
            state[n_key] = True
            state[d_key] = datetime.now().strftime("%b %d, %Y")
            state[rs_key] = reason_input.value
            _save_json("markets_state.json", state)
            activity_log.log_event("signal_noted", entity=f"risk_{i}", reason=reason_input.value, launched_from=f"Markets · IR Risk Dashboard · {sig['title']}")
            ui.notify("Logged — no action taken, decision recorded.")
            dialog.close()
            nav.go_to("Markets")

        ui.button("🔵 Note — not pursuing", on_click=mark_noted).props("flat")
        ui.button("Cancel", on_click=dialog.close).props("flat")
    dialog.open()


def _reset_signal(state, i):
    for suffix in ("resolved", "noted", "date", "reason"):
        state.pop(f"risk_{i}_{suffix}", None)
    _save_json("markets_state.json", state)
    ui.notify("Reset")
    nav.go_to("Markets")


# Mute state logic lives in core/signals.py (shared with today_page.py) —
# see that module's docstring. Only the nicegui dropdown button lives here.
def _unmute_signal(state, key):
    signals.unmute(state, key)
    _save_json("markets_state.json", state)
    ui.notify("Unmuted")
    nav.go_to("Markets")


def _mute_button(state, key, launched_from):
    with ui.button("🔇 Mute").props("flat dense"):
        with ui.menu():
            for days, label in signals.MUTE_OPTIONS:
                ui.menu_item(label, on_click=lambda days=days: _mute_signal(state, key, days, launched_from))


def _mute_signal(state, key, days, launched_from):
    signals.mute(state, key, days, launched_from)
    _save_json("markets_state.json", state)
    ui.notify(f"Muted for {days} day{'s' if days != 1 else ''}.")
    nav.go_to("Markets")


# ─────────────────────────────────────────────────────────────────────────
# Consensus Matrix
# ─────────────────────────────────────────────────────────────────────────
def _risk_level(g, models_in, models_total):
    cov = models_in / models_total if models_total else 0
    rev_var = (g.get("street_rev", 0) - g["Revenue Est ($M)"]) / g["Revenue Est ($M)"] * 100 if g.get("Revenue Est ($M)") else 0
    if cov == 0:
        return "red", "🔴 No data yet"
    if cov < 0.5:
        return "red", "🔴 Problem"
    if abs(rev_var) > 5:
        return "red", "🔴 Beat/miss bar too wide"
    if cov < 0.8:
        return "amber", "⚠️ Watch"
    if abs(rev_var) <= 3:
        return "green", "✅ In line"
    return "amber", "⚠️ Watch"


def _safe_avg(vals):
    v = [x for x in vals if x is not None]
    return round(sum(v) / len(v), 2) if v else None


def _render_consensus_matrix(seed, period_guidance, period_estimates, highlighted_analyst=None):
    last_price = _last_price()

    ui.label("📊 Street Consensus Matrix").classes("text-lg font-bold")
    ui.label("Estimate horizon — where is the risk?").classes("font-bold").style("margin-top:8px;")
    ui.label("Street = analyst consensus estimate · Guidance = management's own number · 🟢 In line (~2-3%) · "
             "🟠 Watch (partial coverage) · 🔴 Flag (models missing, or the gap is wide enough to matter in a call).").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    horizon_periods = ["Q2 2026E", "Q3 2026E", "FY 2026E", "FY 2027E"]
    with ui.row().classes("w-full gap-3"):
        for period in horizon_periods:
            if period not in period_estimates or period not in period_guidance:
                continue
            ests = period_estimates[period]
            g = period_guidance[period]
            ingested = [v for v in ests.values() if v.get("Rating") is not None]
            models_in, models_total = len(ingested), len(ests)
            con_pt = _safe_avg([v.get("Price Target") for v in ingested])
            con_rev = _safe_avg([v.get("Revenue Est ($M)") for v in ingested])
            con_eps = _safe_avg([v.get("EPS Est") for v in ingested])
            level, label = _risk_level({"Revenue Est ($M)": g["Revenue Est ($M)"], "street_rev": con_rev or 0}, models_in, models_total)
            bc = {"green": "#6BCB77", "amber": "#F0A830", "red": "#FF6B6B"}[level]
            no_data = models_in == 0
            upside_pct = round((con_pt - last_price) / last_price * 100, 1) if con_pt else None
            with ui.card().classes("flex-1").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:4px solid {bc};"):
                ui.label(period).style(f"color:{COLORS['accent_light2']};font-size:12px;font-weight:600;")
                ui.label(label).style(f"color:{bc};font-size:12px;font-weight:700;")
                ui.label(f"Models: {models_in}/{models_total}").style(f"color:{COLORS['text_body']};font-size:12px;margin-top:6px;")
                ui.label(f"Street rev: {'—' if no_data else f'${con_rev:.1f}M'}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Guidance rev: ${g['Revenue Est ($M)']:.1f}M").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Street EPS: {'—' if no_data else f'${con_eps:.2f}'}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Guidance EPS: ${g['EPS Est']:.2f}").style(f"color:{COLORS['text_body']};font-size:12px;")
                if con_pt:
                    ui.label(f"Consensus PT: ${con_pt:.2f} ({upside_pct:+.0f}%)").style("color:#6BCB77;font-size:12px;font-weight:600;")

    ui.markdown("---")

    period_select = ui.select(ALL_PERIODS, value="Q2 2026E").classes("w-full").props("label='Estimate period'")
    table_container = ui.column().classes("w-full")

    def render_table():
        table_container.clear()
        period = period_select.value
        if period not in period_estimates or period not in period_guidance:
            with table_container:
                ui.label("No data seeded for this period.").style(f"color:{COLORS['text_muted']};")
            return
        g = period_guidance[period]
        est_data = period_estimates[period]
        firms = list(est_data.keys())
        with table_container:
            if period in DERIVED_PERIODS:
                ui.label(f"⚠️ {period} is derived from FY guidance via seasonal split — not a directly published "
                         "analyst quarterly estimate.").style("color:#F0A830;font-size:11.5px;")

            ingested_ests = {f: v for f, v in est_data.items() if v.get("Rating") is not None}
            con_pt = _safe_avg([v.get("Price Target") for v in ingested_ests.values()])
            con_eps = _safe_avg([v.get("EPS Est") for v in ingested_ests.values()])
            con_rev = _safe_avg([v.get("Revenue Est ($M)") for v in ingested_ests.values()])
            con_ebitda = _safe_avg([v.get("EBITDA Est ($M)") for v in ingested_ests.values()])
            buy_count = sum(1 for v in ingested_ests.values() if v.get("Rating") == "Buy")

            with ui.row().classes("w-full gap-3"):
                _metric("Models Ingested", f"{len(ingested_ests)}/{len(firms)}", period)
                _metric("Consensus PT", f"${con_pt:.2f}" if con_pt else "—",
                        f"{(con_pt-last_price)/last_price*100:+.0f}% upside" if con_pt else "")
                _metric("Consensus EPS", f"${con_eps:.2f}" if con_eps is not None else "—", f"guidance ${g['EPS Est']:.2f}")
                _metric("Consensus Rev", f"${con_rev:.1f}M" if con_rev else "—", f"guidance ${g['Revenue Est ($M)']:.1f}M")
                _metric("Street Rating", f"{buy_count} Buy" if ingested_ests else "—", f"{len(ingested_ests)} rated")

            rows = []
            analyst_dates = seed.get("analyst_dates", {})
            for firm in firms:
                v = est_data[firm]
                rows.append({
                    "Firm": firm, "Rating": v.get("Rating") or "Awaiting",
                    "Price Target": f"${v['Price Target']:.2f}" if v.get("Price Target") else "—",
                    "EPS Est": f"${v['EPS Est']:.2f}" if v.get("EPS Est") is not None else "—",
                    "Revenue ($M)": f"${v['Revenue Est ($M)']:.1f}" if v.get("Revenue Est ($M)") else "—",
                    "EBITDA ($M)": f"${v['EBITDA Est ($M)']:.1f}" if v.get("EBITDA Est ($M)") else "—",
                    "Last Updated": analyst_dates.get(firm, "—"),
                })
            rows.append({"Firm": f"⬛ Street Consensus ({len(ingested_ests)}/{len(firms)})", "Rating": "Buy" if buy_count else "—",
                        "Price Target": f"${con_pt:.2f}" if con_pt else "—", "EPS Est": f"${con_eps:.2f}" if con_eps is not None else "—",
                        "Revenue ($M)": f"${con_rev:.1f}" if con_rev else "—", "EBITDA ($M)": f"${con_ebitda:.1f}" if con_ebitda else "—",
                        "Last Updated": datetime.now().strftime("%b %d %Y")})
            rows.append({"Firm": f"🟢 Guidance — {period}", "Rating": "N/A", "Price Target": "—", "EPS Est": f"${g['EPS Est']:.2f}",
                        "Revenue ($M)": f"${g['Revenue Est ($M)']:.1f}", "EBITDA ($M)": f"${g['EBITDA Est ($M)']:.1f}",
                        "Last Updated": "Mgmt disclosed"})

            ui.table(columns=[{"name": k, "label": k, "field": k, "align": "left"} for k in rows[0].keys()],
                      rows=rows, row_key="Firm").classes("w-full")

            ui.markdown("---")
            deep_linked = bool(highlighted_analyst and highlighted_analyst in firms)
            with ui.expansion("🔍 Track one analyst across every period", value=deep_linked).classes("w-full"):
                analyst_name_by_firm = {a["firm"]: a["name"] for a in CA()}
                if deep_linked:
                    ui.html(
                        f"<div style='background:#1E3A5F;border:1px solid #3B82F6;border-radius:8px;"
                        f"padding:8px 12px;margin-bottom:10px;font-size:13px;color:#BAD4F0;'>"
                        f"📍 Jumped here from Today's Analyst Coverage — showing "
                        f"<b style='color:#F1F5F9;'>{analyst_name_by_firm.get(highlighted_analyst, highlighted_analyst)}</b></div>"
                    )
                default_firm = highlighted_analyst if deep_linked else firms[0]
                an_select = ui.select(firms, value=default_firm).classes("w-full").props("label='Analyst / firm'")
                an_container = ui.column().classes("w-full")

                def render_analyst():
                    an_container.clear()
                    firm = an_select.value
                    with an_container:
                        an_rows = []
                        eps_vals, guidance_eps_vals = [], []
                        for p in ALL_PERIODS:
                            v = period_estimates.get(p, {}).get(firm, {})
                            g_p = period_guidance.get(p, {})
                            if v.get("Rating") is None:
                                an_rows.append({"Period": p, "EPS Est": "—", "Rev Est ($M)": "—", "Rating": "Awaiting", "PT": "—"})
                            else:
                                an_rows.append({"Period": p, "EPS Est": f"${v['EPS Est']:.2f}" if v.get("EPS Est") is not None else "—",
                                               "Rev Est ($M)": f"${v['Revenue Est ($M)']:.1f}" if v.get("Revenue Est ($M)") else "—",
                                               "Rating": v.get("Rating", "—"), "PT": f"${v['Price Target']:.2f}" if v.get("Price Target") else "—"})
                                if v.get("EPS Est") is not None:
                                    eps_vals.append(v["EPS Est"])
                                    guidance_eps_vals.append(g_p.get("EPS Est"))
                        ui.label(f"{analyst_name_by_firm.get(firm, firm)} · {firm}").classes("font-bold")
                        ui.table(columns=[{"name": k, "label": k, "field": k, "align": "left"} for k in an_rows[0].keys()],
                                  rows=an_rows, row_key="Period").classes("w-full")
                        if eps_vals and guidance_eps_vals:
                            above = sum(1 for s, gg in zip(eps_vals, guidance_eps_vals) if gg is not None and s > gg)
                            below = sum(1 for s, gg in zip(eps_vals, guidance_eps_vals) if gg is not None and s < gg)
                            total = len(eps_vals)
                            if above >= total * 0.7 and total >= 2:
                                ui.label(f"📈 Pattern: {firm} has been above guidance EPS in {above}/{total} periods on file "
                                         "— historically runs hot on EPS relative to guidance.").style("color:#F0A830;font-size:12px;")
                            elif below >= total * 0.7 and total >= 2:
                                ui.label(f"📉 Pattern: {firm} has been below guidance EPS in {below}/{total} periods on file "
                                         "— historically conservative relative to guidance.").style(f"color:{COLORS['accent_light']};font-size:12px;")

                an_select.on_value_change(render_analyst)
                render_analyst()

            ui.markdown("---")
            with ui.expansion("✏️ Manually update an analyst estimate").classes("w-full"):
                e_firm = ui.select(firms, value=firms[0]).classes("w-full")
                e_rating = ui.select(["Buy", "Hold", "Sell", "Not Rated"], value="Buy").classes("w-full")
                e_pt = ui.number("Price Target ($)", value=0.0, step=0.25)
                e_eps = ui.number("EPS Estimate ($)", value=0.0, step=0.01)
                e_rev = ui.number("Revenue Estimate ($M)", value=0.0, step=0.5)
                e_ebd = ui.number("EBITDA Estimate ($M)", value=0.0, step=0.1)

                def save_estimate():
                    consensus_store.update_estimate(
                        period, e_firm.value, rating=e_rating.value, price_target=e_pt.value or None,
                        eps_est=e_eps.value if e_eps.value else None,
                        revenue_est=e_rev.value or None, ebitda_est=e_ebd.value or None,
                        source="manual",
                    )
                    ui.notify(f"{e_firm.value} estimates saved for {period}.")
                    # update_estimate() re-fetches and saves its own copy of
                    # period_estimates rather than mutating this closure's
                    # local dict in place, so a full page reload (not just
                    # render_table()) is needed to pick up the fresh values —
                    # same nav.go_to("Markets") pattern this file's other
                    # mutating actions already use.
                    nav.go_to("Markets")

                ui.button("💾 Save Estimate", on_click=save_estimate).props("color=primary")

            with ui.expansion("🟢 Update guidance for this period").classes("w-full"):
                gu_eps = ui.number("Guidance EPS ($)", value=g["EPS Est"], step=0.01)
                gu_rev = ui.number("Guidance Revenue ($M)", value=g["Revenue Est ($M)"], step=0.5)
                gu_ebd = ui.number("Guidance EBITDA ($M)", value=g["EBITDA Est ($M)"], step=0.1)

                def save_guidance():
                    consensus_store.update_guidance(
                        period, eps_est=gu_eps.value, revenue_est=gu_rev.value, ebitda_est=gu_ebd.value,
                    )
                    ui.notify(f"{period} guidance updated.")
                    nav.go_to("Markets")

                ui.button("💾 Save Guidance", on_click=save_guidance).props("color=primary")

    period_select.on_value_change(render_table)
    render_table()


# ─────────────────────────────────────────────────────────────────────────
# PT Drift Tracker
# ─────────────────────────────────────────────────────────────────────────
def _render_pt_drift(seed):
    pt_hist = seed.get("pt_history", {})
    labels = pt_hist.get("labels", [])
    stock_prices = pt_hist.get("stock_prices", [])
    by_firm = pt_hist.get("by_firm", {})
    colors = pt_hist.get("colors", {})
    last_price = _last_price()

    ui.label("📈 Price Target Drift Tracker").classes("text-lg font-bold")
    ui.label("8-quarter sell-side PT history · direction of travel · vs current stock price").style(f"color:{COLORS['text_muted']};font-size:12px;")

    fig = go.Figure()
    for firm, pts in by_firm.items():
        xs, ys = [], []
        for i, p in enumerate(pts):
            if p is not None and i < len(labels):
                xs.append(labels[i])
                ys.append(p)
        fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines+markers", name=firm,
                                  line=dict(color=colors.get(firm, "#888"), width=2.5), marker=dict(size=7)))
    if stock_prices:
        fig.add_trace(go.Scatter(x=labels, y=stock_prices, mode="lines+markers", name=f"{CT('ticker')} Stock Price",
                                  line=dict(color="#C00000", width=2, dash="dot"), marker=dict(size=5, symbol="diamond")))
    fig.update_layout(xaxis_title="Quarter", yaxis_title="Price Target ($)", height=380,
                       margin=dict(l=50, r=20, t=20, b=60),
                       legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
                       plot_bgcolor="#F8F9FA", paper_bgcolor="white")
    ui.plotly(fig).classes("w-full")

    ui.markdown("---")
    ui.label("Analyst PT direction — 8-quarter summary").classes("font-bold")
    drift_rows = []
    for firm, pts in by_firm.items():
        valid = [(labels[i], p) for i, p in enumerate(pts) if p is not None and i < len(labels)]
        if len(valid) >= 2:
            first_pt, last_pt = valid[0][1], valid[-1][1]
            chg_pct = round((last_pt - first_pt) / first_pt * 100, 1)
            direction = "▲ Raising" if chg_pct > 0 else ("▼ Cutting" if chg_pct < 0 else "● Flat")
            status = "Active" if pts[-1] is not None else "⚠️ Inactive"
        else:
            first_pt = last_pt = chg_pct = None
            direction, status = "—", "⚠️ Inactive"
        upside = round((last_pt - last_price) / last_price * 100, 1) if last_pt else None
        drift_rows.append({
            "Firm": firm, "First PT": f"${first_pt:.2f}" if first_pt else "—",
            "Current PT": f"${last_pt:.2f}" if last_pt else "—",
            "8Q Change": f"{chg_pct:+.1f}%" if chg_pct is not None else "—",
            "Direction": direction, "Upside": f"{upside:+.1f}%" if upside is not None else "—", "Status": status,
        })
    ui.table(columns=[{"name": k, "label": k, "field": k, "align": "left"} for k in drift_rows[0].keys()],
              rows=drift_rows, row_key="Firm").classes("w-full") if drift_rows else None

    ui.markdown("---")
    ui.label("PT Justification & Valuation Methodology").classes("font-bold")
    ui.label("Every analyst uses a valuation framework to justify their PT — reverse-engineering the implied "
             "multiple tells you whether they're applying a premium, discount, or in-line multiple.").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    fin = seed.get("financial_position", {})
    shares_out = fin.get("shares_out_m", 0)
    net_debt = fin.get("net_debt_m", 0)
    current_ev = last_price * shares_out + net_debt

    for firm, j in seed.get("pt_justification", {}).items():
        implied_ev = j["current_pt"] * shares_out + net_debt
        implied_multiple = round(implied_ev / j["rev_estimate"], 2) if j.get("rev_estimate") else 0
        distance_pct = round((j["current_pt"] / last_price - 1) * 100, 1)
        appreciation = round((last_price / j["stock_at_set"] - 1) * 100, 1) if j.get("stock_at_set") else 0
        if distance_pct > 150:
            risk_color, risk_label = "#F87171", "⚠️ PT credibility risk — research director may press for revision"
        elif distance_pct > 80:
            risk_color, risk_label = "#FCD34D", "📋 Watch — elevated upside, monitor for revision"
        else:
            risk_color, risk_label = "#4ADE80", "✅ PT credibility intact"
        mult_vs_peer = round(implied_multiple - j.get("peer_multiple", 0), 2)
        mult_label = "premium" if implied_multiple >= j.get("peer_multiple", 0) else "discount"

        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("w-full justify-between"):
                ui.label(f"{firm} — {j['analyst']}").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                ui.label(f"${j['current_pt']:.2f}  (set {j['pt_set_date']} at ${j['stock_at_set']:.2f})").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(f"{risk_label} · {distance_pct:+.0f}% above current price · stock up {appreciation:+.0f}% since PT was set").style(f"color:{risk_color};font-size:12px;font-weight:600;")
            with ui.row().classes("w-full gap-4"):
                ui.label(f"Methodology: {j['methodology']}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Implied multiple: {implied_multiple}x {j['basis_year']}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"vs peer median: {mult_vs_peer:+.2f}x {mult_label}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Current EV/Rev: {round(current_ev/j['rev_estimate'],2) if j.get('rev_estimate') else '—'}x").style(f"color:{COLORS['text_body']};font-size:12px;")
            ui.label(j["justification"]).style(f"color:{COLORS['text_muted']};font-size:11.5px;font-style:italic;")

    ui.markdown("---")
    ui.label("PT Credibility Watchlist").classes("font-bold")
    watch_rows = []
    for firm, j in seed.get("pt_justification", {}).items():
        dist = round((j["current_pt"] / last_price - 1) * 100, 1)
        implied_ev = j["current_pt"] * shares_out + net_debt
        imp_mult = round(implied_ev / j["rev_estimate"], 2) if j.get("rev_estimate") else 0
        flag = "⚠️ Credibility risk" if dist > 150 else ("📋 Elevated — watch" if dist > 80 else "✅ OK")
        watch_rows.append({"Firm": firm, "Analyst": j["analyst"], "PT": f"${j['current_pt']:.2f}",
                          "Distance": f"{dist:+.0f}%", "Implied multiple": f"{imp_mult}x", "Credibility": flag})
    if watch_rows:
        ui.table(columns=[{"name": k, "label": k, "field": k, "align": "left"} for k in watch_rows[0].keys()],
                  rows=watch_rows, row_key="Firm").classes("w-full")

    ui.markdown("---")

    def _export_board_slide():
        # Reuses this exact function's own already-computed seed/last_price;
        # revision_momentum comes from core.risk_scorecard's shared
        # get_revision_momentum() so the slide's number never disagrees with
        # the IR Risk Dashboard's "Revision Momentum" tile.
        rm = risk_scorecard.get_revision_momentum()
        pptx_bytes = board_slides.generate_pt_drift_slide(
            CT("name"), CT("ticker"), seed,
            revision_momentum={"headline": rm["headline"], "detail": rm["detail"], "status": rm["status"]},
        )
        fname = f"{CT('ticker')}_PT_Drift_Board_Slide_{datetime.now().strftime('%Y%m%d')}.pptx"
        ui.download(pptx_bytes, filename=fname)
        activity_log.log_event("board_slide_generated", entity="pt_drift",
                                launched_from="Markets · PT Drift Tracker")
        ui.notify("Board slide downloaded.", type="positive")

    ui.button("📊 Generate PT Drift Board Slide (.pptx)", on_click=_export_board_slide).props("color=primary")
