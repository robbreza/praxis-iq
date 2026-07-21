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
from urllib.parse import quote

import plotly.graph_objects as go
from nicegui import ui

from config.client_config import CA, CE, CF, CGP, CT, get_active_client_id
from config.theme_tokens import ACTIVE as COLORS
from core import activity_log, board_slides, consensus as consensus_store
from core import db, guidance_engine, market_data, narrative_engine, nobo_engine, risk_scorecard, signals, ui_context
from data.seed.buyside_institutions import get_seed_buyside_institutions
from data.seed.institution_contacts import get_institution_contacts
from data.seed.consensus_estimates import ALL_PERIODS, DERIVED_PERIODS
from page_modules_nicegui import nav


def _load_json(name, default):
    return db.load_json(name, default)


def _save_json(name, data):
    # RBAC choke point for the signal actions (mark-resolved/noted/reset/mute)
    # that persist markets_state.json. A view-only role (e.g. CEO, 'read' on
    # Markets) has these writes swallowed. Consensus estimate/guidance saves go
    # through consensus_store, not here, so those buttons are gated separately.
    if ui_context.is_read_only():
        return
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

    # RBAC: view-only roles (e.g. CEO, 'read' on Markets) can browse consensus,
    # price targets, and signals and export the board slide, but not edit
    # estimates/guidance or resolve signals. Every mutating control below
    # calls ui_context.is_read_only() directly (not a captured local), since
    # some live in module-level helper functions outside this closure.
    if ui_context.is_read_only():
        ui_context.read_only_banner(ui)

    # Deep-link from Today's Analyst Coverage ("→" jump next to an analyst):
    # consume the highlight once per page visit — mirrors app.py's
    # st.session_state["highlight_analyst"] pattern (set, shown once, cleared).
    highlighted_analyst = nav.highlights.pop("highlight_analyst", None)

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("IR Risk Dashboard")
        t2 = ui.tab("Consensus / Guidance")
        t3 = ui.tab("PT Drift Tracker")
    # Narrative Momentum now lives with the narrative it grades — Earnings →
    # Script Generation → Tomorrow's Setup (imports _render_narrative_momentum
    # from here). NOBO Ownership moved to Investor Targeting (imports
    # _render_nobo from here). Both render functions stay in this module as the
    # shared home for the compute they wrap; only the tabs relocated.
    _panels = ui.tab_panels(tabs, value=nav.consume_target_tab() or (t2 if highlighted_analyst else t1)).classes("w-full")
    _panels.on_value_change(lambda e: nav.tab_changed(e.value))
    with _panels:
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
    # "Models ingested" must count models we actually HOLD (period_estimates), not the
    # covering-analyst count. The old `status == "active"` proxy reported 2/5 ingested when
    # zero models are on file — the same bug core/risk_scorecard.py already fixed for its tile.
    _period = (CE().get("current_quarter") or "") + "E"
    _ests = (seed.get("period_estimates", {}) or {}).get(_period, {}) or {}
    ingested = sum(1 for v in _ests.values() if v.get("Revenue Est ($M)") is not None)
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
    ui.label("IR Risk Dashboard").classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};")
    last_price_str = f"${last_price:.2f}" if isinstance(last_price, (int, float)) else f"${last_price}"
    ui.label(f"{CT('ticker')} · Last trade {last_price_str} · Earnings {CE().get('earnings_date','')} · "
             f"{days_to_earn} days to consensus lock").style(f"color:{COLORS['text_muted']};font-size:12px;")

    ui.markdown("---")
    ui.label("Actionable IR signals — what to do this week").classes("font-bold")
    ui.label(
        "Closed loop: click into any signal to resolve it or log it as reviewed-but-not-pursued — "
        "these cards track a decision, not just a readout."
    ).style(f"color:{COLORS['text_muted']};font-size:11px;margin-bottom:4px;")

    level_colors = {"red": ("#FDECEC", "#B91C1C"), "amber": ("#FCF0E0", "#B45309"),
                     "green": ("#E9F6EF", "#15803D"), "gray": ("#EEF2F7", "#475569")}
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
        bg, tc = level_colors.get(sig["level"], ("#EEF2F7", "#475569"))
        r_key, n_key, d_key, rs_key = f"risk_{i}_resolved", f"risk_{i}_noted", f"risk_{i}_date", f"risk_{i}_reason"
        m_key = f"risk_{i}"  # mute key — separate namespace from resolved/noted/date/reason above
        if signals.is_muted(state, m_key):
            with ui.card().classes("w-full").style("background:#EEF2F7;border:1px solid #D3DBE4;"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"{sig['title']} — muted").classes("font-bold").style("color:#0F172A;font-size:14px;")
                        ui.label(f"Snoozed until {signals.muted_until_label(state, m_key)} — still unresolved, just hidden till then.").style("color:#475569;font-size:12px;")
                    ui.button("Unmute now", on_click=lambda i=i, m_key=m_key: _unmute_signal(state, m_key)).props("flat dense")
        elif state.get(r_key):
            with ui.card().classes("w-full").style("background:#E9F6EF;border:1px solid #15803D55;"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"{sig['title']}").classes("font-bold").style("color:#0F172A;font-size:14px;")
                        ui.label(f"Resolved {state.get(d_key,'')}").style("color:#15803D;font-size:12px;")
                    ui.button("Reset", on_click=lambda i=i: _reset_signal(state, i)).props("flat dense")
        elif state.get(n_key):
            reason = f" — {state[rs_key]}" if state.get(rs_key) else ""
            with ui.card().classes("w-full").style("background:#EEF2F7;border:1px solid #D3DBE4;"):
                with ui.row().classes("w-full items-center justify-between"):
                    with ui.column().classes("gap-0"):
                        ui.label(f"{sig['title']}").classes("font-bold").style("color:#0F172A;font-size:14px;")
                        ui.label(f"Noted — not pursued {state.get(d_key,'')}{reason}").style("color:#475569;font-size:12px;")
                    ui.button("Reset", on_click=lambda i=i: _reset_signal(state, i)).props("flat dense")
        else:
            with ui.card().classes("w-full").style(f"background:{bg};border:1px solid {tc}55;"):
                with ui.row().classes("items-start gap-2"):
                    ui.label(sig["icon"]).style("font-size:18px;")
                    with ui.column().classes("gap-0"):
                        ui.label(sig["title"]).classes("font-bold").style("color:#0F172A;font-size:14px;")
                        ui.label(sig["desc"]).style(f"color:{COLORS['text_secondary']};font-size:12.5px;")
                        ui.label(f"→ {sig['action']}").style(f"color:{tc};font-size:12.5px;font-weight:600;")
                # Actions left-justified in a row beneath the text (not floated
                # to the far right, which read as disconnected on wide cards).
                with ui.row().classes("items-center gap-2").style("margin-top:8px;"):
                    ui.button(
                        f"{resolve_verb.get(sig['level'], 'Resolve')}",
                        on_click=lambda i=i, sig=sig: _open_signal_dialog(state, i, sig),
                    ).props("flat dense").style(f"color:{tc};")
                    _mute_button(state, m_key, f"Markets · IR Risk Dashboard · {sig['title']}")

    ui.markdown("---")
    ui.label("Problem — act this week · Watch — monitor · In line — no action · Blind spot — not tracked").style(f"color:{COLORS['text_muted']};font-size:11px;")

    # Computed from real data (core.risk_scorecard) — see that module's
    # docstring for exactly which of the 24 indicators are grounded in a
    # real source (market_data, sec_filings, Reg FD log, Script Generation
    # state, Consensus Tracker log) vs. still GRAY/Not Tracked because no
    # source exists anywhere in this app.
    risk_categories = risk_scorecard.compute_scorecard()
    risk_colors = {"RED": "#B91C1C", "ORANGE": "#B45309", "YELLOW": "#A16207", "GREEN": "#15803D", "GRAY": "#64748B"}
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
                  f"{len(all_items)-len(tracked_items)} marked Not Tracked, excluded rather than guessed at").style(
            f"color:{COLORS['text_muted']};font-size:11px;")

    ui.markdown("---")
    with ui.expansion("Show the 6 risk categories (24 indicators)", value=False).classes("w-full"):
        with ui.row().classes("w-full gap-6"):
            cat_names = list(risk_categories.keys())
            for col_start in (0, len(cat_names) // 2 + len(cat_names) % 2):
                with ui.column().classes("flex-1"):
                    for cat_name in cat_names[col_start:col_start + (len(cat_names) // 2 + len(cat_names) % 2)]:
                        ui.label(cat_name).classes("font-bold")
                        for label, status, reason in risk_categories[cat_name]:
                            sc = risk_colors[status]
                            with ui.card().classes("w-full").style(f"background:{sc}18;border-left:3px solid {sc};"):
                                with ui.row().classes("w-full justify-between"):
                                    ui.label(label).style(f"color:{COLORS['text_body']};font-size:12px;")
                                    ui.label(status if status != "GRAY" else "N/T").style(f"color:{sc};font-size:11px;font-weight:bold;")
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


def _vs_guidance(est, guid, money=False):
    """One analyst estimate vs. management guidance for the same period, as a
    signed delta plus direction. The whole point of this column is to show
    whether the analyst models above, below, or in line with the company's own
    guidance — an above-guidance analyst is a bar/miss risk into the print.
    Returns "—" when either value is missing (e.g. a period the company hasn't
    formally guided), so it never fabricates a comparison it can't make."""
    if est is None or guid is None:
        return "—"
    d = round(est - guid, 1 if money else 2)
    if d == 0:
        return "in line"
    amt = f"${abs(d):.1f}M" if money else f"${abs(d):.2f}"
    sign = "+" if d > 0 else "−"
    return f"{sign}{amt} {'above' if d > 0 else 'below'}"


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

        # Email action — for signals that carry recipients (e.g. the missing-model
        # request to the analysts with no model on file), draft the email right
        # here via a mailto link, the same way the NOBO and NDR surfaces do,
        # instead of pointing off to another page.
        em = sig.get("email")
        if em:
            _to = ",".join(em.get("to") or [])
            _href = f"mailto:{_to}?subject={quote(em['subject'])}&body={quote(em['body'])}"
            with ui.link(target=_href).style("text-decoration:none;margin-top:8px;display:inline-block;"):
                ui.button("Draft the email", icon="mail").props("color=primary")
            _rcpt = (f"Opens a draft to: {', '.join(em['to'])}" if em.get("to")
                     else "Opens a draft — add your recipient(s)")
            ui.label(_rcpt).style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:2px;")

        def mark_resolved():
            state[r_key] = True
            state[d_key] = datetime.now().strftime("%b %d, %Y")
            _save_json("markets_state.json", state)
            activity_log.log_event("signal_resolved", entity=f"risk_{i}", launched_from=f"Markets · IR Risk Dashboard · {sig['title']}")
            ui.notify("Marked resolved.")
            dialog.close()
            nav.go_to("Markets")

        ui.button("Mark Resolved", on_click=mark_resolved).props("color=primary").style("margin-top:10px;")

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

        ui.button("Note — not pursuing", on_click=mark_noted).props("flat")
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
    with ui.button("Mute").props("flat dense"):
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
        return "red", "No data yet"
    if cov < 0.5:
        return "red", "Problem"
    if abs(rev_var) > 5:
        return "red", "Beat/miss bar too wide"
    if cov < 0.8:
        return "amber", "Watch"
    if abs(rev_var) <= 3:
        return "green", "In line"
    return "amber", "Watch"


def _safe_avg(vals):
    v = [x for x in vals if x is not None]
    return round(sum(v) / len(v), 2) if v else None


# ─────────────────────────────────────────────────────────────────────────
# Guidance impact analysis — thin view over core.guidance_engine (the single
# source of truth shared with the Earnings Decision Engine). The primitives
# below are aliases so this file's render code and the engine can never drift.
# ─────────────────────────────────────────────────────────────────────────
def _street_period_avg(period_estimates, period, field):
    """Street consensus for a period/field — the mean of RECEIVED analyst models, falling back to
    the curated consensus for the CURRENT quarter's REVENUE when no models are on file. Without the
    fallback, a client with 0 received models (USIO's real state) showed "St —" and the whole
    guide-vs-Street comparison collapsed, even though a curated q2_consensus_rev ($25.1M) exists and
    IS the Street number the guide should be measured against."""
    v = guidance_engine.street_avg(period_estimates, period, field)
    if v is not None:
        return v
    if field == "Revenue Est ($M)":
        from config.client_config import CE
        cq = (CE().get("current_quarter") or "").strip()
        if cq and period == f"{cq}E":
            from core import market_data
            return market_data.consensus_rev_value()
    return None


_period_year = guidance_engine.period_year
_next_year_suffix = guidance_engine.next_year_suffix
_fy_from_quarters = guidance_engine.fy_from_quarters
_fmt_val = guidance_engine.fmt_val
_impact_delta = guidance_engine.impact_delta


def _render_guidance_impact(period, new_eps, new_rev, new_ebd, period_guidance, period_estimates):
    new_eps, new_rev, new_ebd = new_eps or 0.0, new_rev or 0.0, new_ebd or 0.0
    year = _period_year(period)
    is_quarter = period.startswith("Q")
    # Fold the last reported quarter's actuals into the full-year roll-up
    # (past quarters aren't in forward guidance) — via the shared engine.
    actuals = guidance_engine.reported_actuals()

    def _row(cells):
        with ui.row().classes("w-full items-center gap-2").style(
                f"border-bottom:1px solid {COLORS['border']};padding:3px 0;"):
            for text, clr, w in cells:
                mw = f"min-width:{w}px;" if w else ""
                ui.label(text).style(f"color:{clr};font-size:12px;{mw}")

    def _head(t):
        ui.label(t).style(f"color:{COLORS['text_muted']};font-size:11px;font-weight:700;"
                          f"letter-spacing:.03em;margin:8px 0 2px;")

    # ── Shared numbers, computed once via core.guidance_engine (no local
    #    formulas — the Decision Engine reads the same functions). ──
    fy_label = f"FY {year}"
    street_rev_q = _street_period_avg(period_estimates, period, "Revenue Est ($M)")
    implied_fy_rev = prior_fy_rev = h1_rev = backend = None
    seasonal_fy_rev = divergence = None
    if is_quarter:
        implied_fy_rev = _fy_from_quarters(period_guidance, year, "Revenue Est ($M)", period, new_rev, actuals=actuals)
        prior_fy_rev = period_guidance.get(fy_label, {}).get("Revenue Est ($M)")
        h1_rev = _fy_from_quarters(period_guidance, year, "Revenue Est ($M)", period, new_rev,
                                   quarters=("Q1", "Q2"), actuals=actuals)
        backend = guidance_engine.backend_weighting(implied_fy_rev, h1_rev)
        # Second lens: FY implied by extrapolating H1 at the seasonal weights.
        if h1_rev:
            seasonal_fy_rev = guidance_engine.seasonal_implied_fy(h1_rev)
            if implied_fy_rev and seasonal_fy_rev:
                divergence = round(implied_fy_rev - seasonal_fy_rev, 1)

    # ── HEADLINE (bottom-line-up-front): the morning-after read, first. ──
    parts = guidance_engine.morning_read_parts(period, fy_label, new_rev, street_rev_q,
                                               implied_fy_rev, prior_fy_rev, backend)
    if parts:
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1.5px solid {COLORS['accent']};"
                f"border-left:6px solid {COLORS['accent']};border-radius:10px;"
                f"padding:12px 16px;margin-bottom:10px;"):
            ui.label("THE MORNING-AFTER READ — what the buy-side detects first").style(
                f"color:{COLORS['accent_strong']};font-size:11px;font-weight:700;letter-spacing:.04em;")
            ui.label(" ".join(parts)).style(
                f"color:{COLORS['text_heading']};font-size:13.5px;line-height:1.65;font-weight:500;margin-top:4px;")

    # ── Supporting breakdown (the math behind the headline) ──
    ui.label("Supporting breakdown").style(
        f"color:{COLORS['text_muted']};font-size:10.5px;font-weight:700;letter-spacing:.05em;margin-top:2px;")

    _head(f"{period} guide vs Street consensus")
    for lbl, nv, field, money in [("Revenue", new_rev, "Revenue Est ($M)", True),
                                  ("EPS", new_eps, "EPS Est", False),
                                  ("EBITDA", new_ebd, "EBITDA Est ($M)", True)]:
        street = _street_period_avg(period_estimates, period, field)
        dt, dc = _impact_delta(nv, street, money)
        _row([(lbl, COLORS["text_secondary"], 74),
              (_fmt_val(nv, money), COLORS["text_heading"], 78),
              (f"St {_fmt_val(street, money)}", COLORS["text_muted"], 96),
              (dt, dc, 0)])

    if not is_quarter:
        ui.label("Full-year roll-up shows when guiding a specific quarter.").style(
            f"color:{COLORS['text_muted']};font-size:11px;margin-top:6px;")
        return

    _head(f"Effect on {fy_label} (implied from the four quarters)")
    for lbl, nv, field, money in [("Revenue", new_rev, "Revenue Est ($M)", True),
                                  ("EPS", new_eps, "EPS Est", False)]:
        implied = _fy_from_quarters(period_guidance, year, field, period, nv, actuals=actuals)
        prior = period_guidance.get(fy_label, {}).get(field)
        street_fy = _street_period_avg(period_estimates, fy_label, field)
        pt, pc = _impact_delta(implied, prior, money)
        st, sc = _impact_delta(implied, street_fy, money)
        _row([(lbl, COLORS["text_secondary"], 60),
              (f"impl {_fmt_val(implied, money)}", COLORS["text_heading"], 92),
              (f"vs prior {pt}", pc, 150),
              (f"vs St {st}", sc, 0)])

    # Two lenses on the implied full year — flag when they disagree.
    if seasonal_fy_rev is not None and implied_fy_rev is not None:
        _row([("FY revenue", COLORS["text_secondary"], 74),
              (f"quarters {_fmt_val(implied_fy_rev, True)}", COLORS["text_heading"], 132),
              (f"seasonal pace {_fmt_val(seasonal_fy_rev, True)}", COLORS["text_muted"], 0)])
        if divergence is not None and abs(divergence) >= 2:
            dclr = "#B45309" if divergence > 0 else "#1E40AF"
            side = "above" if divergence > 0 else "below"
            ui.label(f"Reconciliation gap: your quarterly path implies ${abs(divergence):.1f}M {side} the H1 "
                     f"run-rate extrapolation — the Street will read your H2 guide as "
                     f"{'aggressive' if divergence > 0 else 'conservative'} versus the pace you've set.").style(
                f"color:{dclr};font-size:11.5px;margin-top:4px;line-height:1.5;")

    if backend:
        if backend["level"] == "heavy":
            msg, clr = (f"Implied H2 = ${backend['h2_rev']:.1f}M = {backend['h2_pct']:.0f}% of FY vs "
                        f"{backend['seasonal_h2']:.0f}% seasonal norm (+{backend['skew']:.0f}pp) — more back-end "
                        f"weighted.", "#B45309")
        elif backend["level"] == "light":
            msg, clr = (f"Implied H2 = ${backend['h2_rev']:.1f}M = {backend['h2_pct']:.0f}% of FY vs "
                        f"{backend['seasonal_h2']:.0f}% norm ({backend['skew']:.0f}pp) — front-loaded, H2 de-risked.",
                        "#15803D")
        else:
            msg, clr = (f"Implied H2 = ${backend['h2_rev']:.1f}M = {backend['h2_pct']:.0f}% of FY — in line with the "
                        f"{backend['seasonal_h2']:.0f}% seasonal norm. Normal cadence.", "#475569")
        ui.label(msg).style(f"color:{clr};font-size:11.5px;margin-top:6px;line-height:1.5;")

    next_year = _next_year_suffix(year)
    nfy_label = f"FY {next_year}" if next_year else None
    if nfy_label:
        _head(f"Setup into {nfy_label}")
        for lbl, field, money in [("Revenue", "Revenue Est ($M)", True), ("EPS", "EPS Est", False)]:
            nfy_guide = period_guidance.get(nfy_label, {}).get(field)
            nfy_street = _street_period_avg(period_estimates, nfy_label, field)
            st, sc = _impact_delta(nfy_guide, nfy_street, money)
            _row([(lbl, COLORS["text_secondary"], 60),
                  (f"guide {_fmt_val(nfy_guide, money)}", COLORS["text_heading"], 96),
                  (f"Street {_fmt_val(nfy_street, money)}", COLORS["text_muted"], 118),
                  (f"gap {st}", sc, 0)])
        nfy_street_rev = _street_period_avg(period_estimates, nfy_label, "Revenue Est ($M)")
        if implied_fy_rev and nfy_street_rev:
            yoy = (nfy_street_rev / implied_fy_rev - 1) * 100
            ui.label(f"Street already models {yoy:+.0f}% revenue growth into {nfy_label} "
                     f"(${nfy_street_rev:.0f}M vs your implied {fy_label} ${implied_fy_rev:.0f}M) — this quarter "
                     f"re-bases that starting point.").style(
                f"color:{COLORS['text_secondary']};font-size:11.5px;margin-top:4px;line-height:1.5;")


def _render_consensus_matrix(seed, period_guidance, period_estimates, highlighted_analyst=None):
    last_price = _last_price()

    ui.label("Street Consensus Matrix").classes("text-lg font-bold")
    ui.label("Estimate horizon — where is the risk?").classes("font-bold").style("margin-top:8px;")
    ui.label("Street = analyst consensus estimate · Guidance = management's own number · In line (~2-3%) · "
             "Watch (partial coverage) · Flag (models missing, or the gap is wide enough to matter in a call).").style(
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
            bc = {"green": "#15803D", "amber": "#B45309", "red": "#B91C1C"}[level]
            # Guard each VALUE, not a single models_in flag: a firm can be ingested (Rating set)
            # while its Revenue/EPS estimate is still None — which is exactly USIO's "0 of 5
            # models received" state. models_in was 5, no_data False, con_rev None, and the
            # f-string raised TypeError: unsupported format string passed to NoneType.__format__,
            # taking the Markets page down. Guidance can be None too on a new tenant.
            no_data = models_in == 0
            _srev = "—" if con_rev is None else f"${con_rev:.1f}M"
            _seps = "—" if con_eps is None else f"${con_eps:.2f}"
            _grev = "—" if g.get("Revenue Est ($M)") is None else f"${g['Revenue Est ($M)']:.1f}M"
            _geps = "—" if g.get("EPS Est") is None else f"${g['EPS Est']:.2f}"
            upside_pct = round((con_pt - last_price) / last_price * 100, 1) if con_pt else None
            with ui.card().classes("flex-1").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:4px solid {bc};"):
                ui.label(period).style(f"color:{COLORS['accent_light2']};font-size:12px;font-weight:600;")
                ui.label(label).style(f"color:{bc};font-size:12px;font-weight:700;")
                ui.label(f"Models: {models_in}/{models_total}").style(f"color:{COLORS['text_body']};font-size:12px;margin-top:6px;")
                ui.label(f"Street rev: {_srev}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Guidance rev: {_grev}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Street EPS: {_seps}").style(f"color:{COLORS['text_body']};font-size:12px;")
                ui.label(f"Guidance EPS: {_geps}").style(f"color:{COLORS['text_body']};font-size:12px;")
                if con_pt:
                    ui.label(f"Consensus PT: ${con_pt:.2f} ({upside_pct:+.0f}%)").style("color:#15803D;font-size:12px;font-weight:600;")

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
                ui.label(f"{period} is derived from FY guidance via seasonal split — not a directly published "
                         "analyst quarterly estimate.").style("color:#B45309;font-size:11.5px;")

            ingested_ests = {f: v for f, v in est_data.items() if v.get("Rating") is not None}
            con_pt = _safe_avg([v.get("Price Target") for v in ingested_ests.values()])
            con_eps = _safe_avg([v.get("EPS Est") for v in ingested_ests.values()])
            con_rev = _safe_avg([v.get("Revenue Est ($M)") for v in ingested_ests.values()])
            con_ebitda = _safe_avg([v.get("EBITDA Est ($M)") for v in ingested_ests.values()])
            buy_count = sum(1 for v in ingested_ests.values() if v.get("Rating") == "Buy")

            # Card order mirrors the table columns below (Firm, Rating, Price
            # Target, EPS, Revenue) so each summary sits above its column:
            # Models Ingested → Firm, Street Rating → Rating, then PT/EPS/Rev.
            with ui.row().classes("w-full gap-3"):
                _metric("Models Ingested", f"{len(ingested_ests)}/{len(firms)}", period)
                _metric("Street Rating", f"{buy_count} Buy" if ingested_ests else "—", f"{len(ingested_ests)} rated")
                _metric("Consensus PT", f"${con_pt:.2f}" if con_pt else "—",
                        f"{(con_pt-last_price)/last_price*100:+.0f}% upside" if con_pt else "")
                _metric("Consensus EPS", f"${con_eps:.2f}" if con_eps is not None else "—", f"guidance {'—' if g.get('EPS Est') is None else '$' + format(g['EPS Est'], '.2f')}")
                _metric("Consensus Rev", f"${con_rev:.1f}M" if con_rev else "—", f"guidance {'—' if g.get('Revenue Est ($M)') is None else '$' + format(g['Revenue Est ($M)'], '.1f') + 'M'}")

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
            rows.append({"Firm": f"Street Consensus ({len(ingested_ests)}/{len(firms)})", "Rating": "Buy" if buy_count else "—",
                        "Price Target": f"${con_pt:.2f}" if con_pt else "—", "EPS Est": f"${con_eps:.2f}" if con_eps is not None else "—",
                        "Revenue ($M)": f"${con_rev:.1f}" if con_rev else "—", "EBITDA ($M)": f"${con_ebitda:.1f}" if con_ebitda else "—",
                        "Last Updated": datetime.now().strftime("%b %d %Y")})
            rows.append({"Firm": f"Guidance — {period}", "Rating": "N/A", "Price Target": "—", "EPS Est": f"${g['EPS Est']:.2f}",
                        "Revenue ($M)": f"${g['Revenue Est ($M)']:.1f}", "EBITDA ($M)": f"${g['EBITDA Est ($M)']:.1f}",
                        "Last Updated": "Mgmt disclosed"})

            ui.table(columns=[{"name": k, "label": k, "field": k, "align": "left"} for k in rows[0].keys()],
                      rows=rows, row_key="Firm").classes("w-full")

            ui.markdown("---")
            deep_linked = bool(highlighted_analyst and highlighted_analyst in firms)
            with ui.expansion("Track one analyst across every period", value=deep_linked).classes("w-full"):
                analyst_name_by_firm = {a["firm"]: a["name"] for a in CA()}
                if deep_linked:
                    ui.html(
                        f"<div style='background:#E8EEF7;border:1px solid #1E40AF55;border-radius:8px;"
                        f"padding:8px 12px;margin-bottom:10px;font-size:13px;color:#1E293B;'>"
                        f"Jumped here from Today's Analyst Coverage — showing "
                        f"<b style='color:#1E3A8A;'>{analyst_name_by_firm.get(highlighted_analyst, highlighted_analyst)}</b></div>"
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
                                an_rows.append({"period": p, "eps": "—", "eps_vs": "—",
                                                "rev": "—", "rev_vs": "—", "rating": "Awaiting", "pt": "—"})
                            else:
                                eps, rev = v.get("EPS Est"), v.get("Revenue Est ($M)")
                                an_rows.append({
                                    "period": p,
                                    "eps": f"${eps:.2f}" if eps is not None else "—",
                                    "eps_vs": _vs_guidance(eps, g_p.get("EPS Est"), money=False),
                                    "rev": f"${rev:.1f}" if rev else "—",
                                    "rev_vs": _vs_guidance(rev, g_p.get("Revenue Est ($M)"), money=True),
                                    "rating": v.get("Rating", "—"),
                                    "pt": f"${v['Price Target']:.2f}" if v.get("Price Target") else "—",
                                })
                                if eps is not None:
                                    eps_vals.append(eps)
                                    guidance_eps_vals.append(g_p.get("EPS Est"))
                        ui.label(f"{analyst_name_by_firm.get(firm, firm)} · {firm}").classes("font-bold")
                        an_cols = [
                            {"name": "period", "label": "Period", "field": "period", "align": "left"},
                            {"name": "eps", "label": "EPS Est", "field": "eps", "align": "left"},
                            {"name": "eps_vs", "label": "EPS vs. guidance", "field": "eps_vs", "align": "left"},
                            {"name": "rev", "label": "Rev Est ($M)", "field": "rev", "align": "left"},
                            {"name": "rev_vs", "label": "Rev vs. guidance", "field": "rev_vs", "align": "left"},
                            {"name": "rating", "label": "Rating", "field": "rating", "align": "left"},
                            {"name": "pt", "label": "PT", "field": "pt", "align": "left"},
                        ]
                        an_table = ui.table(columns=an_cols, rows=an_rows, row_key="period").classes("w-full")
                        # Colour the vs-guidance cells: amber = analyst models
                        # ABOVE guidance (a bar/miss risk into the print),
                        # green = in line, slate = below/conservative or blank.
                        _vg_cell = (
                            '<q-td :props="props">'
                            "<span :style=\"'color:' + "
                            "(String(props.value).includes('above') ? '#B45309' : "
                            "String(props.value).includes('below') ? '#64748B' : "
                            "String(props.value).includes('line') ? '#15803D' : '#94A3B8') + "
                            "';font-weight:500'\">{{ props.value }}</span></q-td>"
                        )
                        an_table.add_slot('body-cell-eps_vs', _vg_cell)
                        an_table.add_slot('body-cell-rev_vs', _vg_cell)
                        if eps_vals and guidance_eps_vals:
                            above = sum(1 for s, gg in zip(eps_vals, guidance_eps_vals) if gg is not None and s > gg)
                            below = sum(1 for s, gg in zip(eps_vals, guidance_eps_vals) if gg is not None and s < gg)
                            total = len(eps_vals)
                            if above >= total * 0.7 and total >= 2:
                                ui.label(f"Pattern: {firm} has been above guidance EPS in {above}/{total} periods on file "
                                         "— historically runs hot on EPS relative to guidance.").style("color:#B45309;font-size:12px;")
                            elif below >= total * 0.7 and total >= 2:
                                ui.label(f"Pattern: {firm} has been below guidance EPS in {below}/{total} periods on file "
                                         "— historically conservative relative to guidance.").style(f"color:{COLORS['accent_light']};font-size:12px;")

                an_select.on_value_change(render_analyst)
                render_analyst()

            ui.markdown("---")
            with ui.expansion("Manually update an analyst estimate").classes("w-full"):
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

                _se_btn = ui.button("Save Estimate", on_click=save_estimate).props("color=primary")
                if ui_context.is_read_only():
                    _se_btn.disable()

            # ── Guidance & Outlook — its own clearly-titled section on this
            #    tab (the tab is "Consensus / Guidance"), separating the
            #    guidance decision surface from the consensus data above.
            ui.markdown("---")
            ui.html("<div class='section-eyebrow'>GUIDANCE &amp; OUTLOOK</div>"
                    "<div class='section-title'>Guidance Decision Engine</div>")

            # ── Guidance decision read — surfaced from the full Decision
            #    Engine (Earnings → Script Generation) so the seasonality-
            #    adjusted analytics are discoverable here where guidance is
            #    entered, not just buried in the script workflow. ────────────
            _ss = db.load_json("script_workflow_state.json", {})
            _gm = None
            if _ss.get("q2_numbers", {}).get("rev"):
                try:
                    from page_modules_nicegui.earnings_page import _guidance_math
                    _m = _guidance_math(_ss)
                    _gm = _m if _m.get("fy_mid", 0) else None
                except Exception:
                    _gm = None
            if _gm:
                _sc_clr = {"RAISE_MID": "#15803D", "RAISE_LOW": "#1E40AF",
                           "REITERATE": "#B45309", "REITERATE_CAUTIOUS": "#B91C1C"}.get(_gm["scenario"], "#475569")
                with ui.card().classes("w-full").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                        f"border-left:4px solid {_sc_clr};margin-bottom:6px;"):
                    ui.label("GUIDANCE DECISION READ — reporting quarter").style(
                        f"color:{COLORS['text_muted']};font-size:10.5px;font-weight:700;letter-spacing:.04em;")
                    ui.label(_gm["scenario_label"]).classes("font-bold").style(f"color:{_sc_clr};font-size:13px;")
                    _dec = guidance_engine.current_decision()
                    if _dec:
                        _rng = (f" → FY ${_dec['new_low']:.1f}–{_dec['new_hi']:.1f}M"
                                if _dec.get("new_low") is not None else "")
                        ui.label(f"On record: {_dec['label']}{_rng} — decided in the Decision Engine and written "
                                 f"through to the FY guidance below.").style(
                            f"color:{COLORS['accent_strong']};font-size:12px;font-weight:600;")
                    ui.label(f"YTD ${_gm['ytd_rev']:.1f}M ({_gm['ytd_pct_of_mid']:.0f}% of ${_gm['fy_mid']:.1f}M "
                             f"midpoint) · pace {_gm['pace_vs_seasonal']:+.1f}pp vs seasonal · H2 needs "
                             f"{_gm['h2_growth_needed']:+.0f}% YoY · beat vs Street {_gm['beat_vs_street']:+.1f}M").style(
                        f"color:{COLORS['text_secondary']};font-size:12px;")

                    # The full Guidance & Outlook Decision Engine, INLINE — the
                    # CFO sets the decision right here (action → range → drafted
                    # guidance), and it writes through to the CEO's script and the
                    # FY guidance (see earnings_page._render_guidance_decision's
                    # submit / commit_fy_guidance). Collapsed by default; the
                    # chevron expands/collapses it in place instead of navigating
                    # away to the script workflow. This replaces the earlier
                    # quick-set buttons — the engine's own action controls are the
                    # single place the decision is set.
                    with ui.expansion("Open the full Guidance Decision Engine").classes("w-full").style(
                            "margin-top:6px;"):
                        from page_modules_nicegui.earnings_page import _render_guidance_decision
                        _render_guidance_decision(_ss, context="markets")
            else:
                with ui.card().classes("w-full").style(
                        f"background:{COLORS['surface_bg']};border:1px dashed {COLORS['border']};margin-bottom:6px;"):
                    ui.label("The seasonality-adjusted guidance decision read — pace vs seasonal, per-quarter H2 "
                             "targets, and the raise/reiterate/narrow recommendation — lives in the full engine. "
                             "Enter this quarter's actuals there to light it up.").style(
                        f"color:{COLORS['text_muted']};font-size:11.5px;")
                    ui.button("Open the Guidance Decision Engine →",
                              on_click=lambda: nav.go_to("Earnings", "Script Generation", earnings_tab="guidance")).props("flat dense")

            with ui.expansion("Update guidance for this period — live impact analysis",
                              value=True).classes("w-full"):
                with ui.row().classes("w-full gap-6 items-start"):
                    with ui.column().classes("flex-1").style("min-width:220px;"):
                        gu_eps = ui.number("Guidance EPS ($)", value=g["EPS Est"], step=0.01).classes("w-full")
                        gu_rev = ui.number("Guidance Revenue ($M)", value=g["Revenue Est ($M)"], step=0.5).classes("w-full")
                        gu_ebd = ui.number("Guidance EBITDA ($M)", value=g["EBITDA Est ($M)"], step=0.1).classes("w-full")

                        def save_guidance():
                            consensus_store.update_guidance(
                                period, eps_est=gu_eps.value, revenue_est=gu_rev.value, ebitda_est=gu_ebd.value,
                            )
                            ui.notify(f"{period} guidance updated.")
                            nav.go_to("Markets")

                        _sg_btn = ui.button("Save Guidance", on_click=save_guidance).props("color=primary")
                        if ui_context.is_read_only():
                            _sg_btn.disable()

                    # Live impact — recomputes as the CFO nudges the numbers,
                    # before anything is committed.
                    with ui.column().classes("flex-[2]").style("min-width:320px;"):
                        impact_area = ui.column().classes("w-full")

                        def _recompute_impact():
                            impact_area.clear()
                            with impact_area:
                                _render_guidance_impact(period, gu_eps.value, gu_rev.value, gu_ebd.value,
                                                        period_guidance, period_estimates)

                        gu_eps.on_value_change(_recompute_impact)
                        gu_rev.on_value_change(_recompute_impact)
                        gu_ebd.on_value_change(_recompute_impact)
                        _recompute_impact()

    period_select.on_value_change(render_table)
    render_table()


# ─────────────────────────────────────────────────────────────────────────
# Narrative Momentum — "guidance is only guidance" (Praxis_IQ_Handoff.md).
# Reads the story behind the numbers: catalysts in play, analyst conviction
# (PT direction), guidance stance, and whether the stock reflects the
# narrative yet — synthesized into one signal. Computed from real data
# (pt_history, guidance_policy, the guidance decision, consensus vs price),
# not a static tile.
# ─────────────────────────────────────────────────────────────────────────
def _render_narrative_momentum(seed, compact=False):
    """Render the Narrative Momentum read. Compute lives in
    core/narrative_engine.narrative_read (shared with Script Generation's
    Tomorrow's Setup panel, its primary home). compact=True renders the light
    Markets glance — signal, thesis, and a pointer to the full read — so this
    surface and Script Generation can't drift into two versions of the story."""
    ui.label("Narrative Momentum").classes("text-lg font-bold")
    ui.label("Guidance is only guidance — this reads the story behind the numbers: named catalysts in play, "
             "where analyst conviction is heading, and whether the stock has paid for the narrative yet.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    r = narrative_engine.narrative_read(seed)
    sig, sig_clr, thesis = r["signal"], r["color"], r["thesis"]
    raising, flat, cutting, net_pt = r["raising"], r["flat"], r["cutting"], r["net_pt"]
    catalysts, n_cat = r["catalysts"], r["n_cat"]
    stance_label, upside = r["stance_label"], r["upside"]

    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:5px solid {sig_clr};margin-top:8px;"):
        ui.label(f"NARRATIVE MOMENTUM: {sig}").classes("font-bold").style(f"color:{sig_clr};font-size:15px;")
        ui.label(thesis).style(f"color:{COLORS['text_secondary']};font-size:13px;line-height:1.6;")

    if compact:
        # Light Markets glance — the full read (analyst-PT breakdown, catalyst
        # drivers, and the morning-after guidance read alongside it) lives with
        # the narrative it grades, in Script Generation.
        ui.label("Full read — analyst-PT breakdown, the named catalyst drivers, and the morning-after guidance "
                 "read alongside it — lives in Script Generation → Tomorrow's Setup, with the narrative it grades.").style(
            f"color:{COLORS['text_muted']};font-size:11px;margin-top:8px;")
        return

    with ui.row().classes("w-full gap-3").style("margin-top:8px;"):
        _metric("Guidance stance", stance_label, "vs the formal range")
        _metric("H2 catalysts in play", str(n_cat), "named narrative drivers")
        _metric("Analyst PTs", f"{raising}↑ {flat}→ {cutting}↓", f"net {net_pt:+d} · active covering analysts")
        _metric("Narrative vs price", f"{upside:+.0f}%", "upside to consensus PT")

    if catalysts:
        with ui.expansion(f"H2 narrative drivers ({n_cat})").classes("w-full").style("margin-top:6px;"):
            for c in catalysts:
                ui.label(f"• {c}").style(f"color:{COLORS['text_body']};font-size:12px;")

    ui.label("Momentum = guidance stance + net analyst-PT direction + catalyst depth. A held/raised range with "
             "catalysts and a lagging stock is the setup where IR effort moves the price the most.").style(
        f"color:{COLORS['text_muted']};font-size:11px;margin-top:8px;")


# ─────────────────────────────────────────────────────────────────────────
# PT Drift Tracker
# ─────────────────────────────────────────────────────────────────────────
def _render_pt_drift(seed):
    from page_modules_nicegui.signals import waiting_signal
    from config.client_config import CA
    last_price = _last_price()

    ui.label("Price Target Drift Tracker").classes("text-lg font-bold")
    ui.label("Sell-side coverage · current price targets · drift history accumulates as PTs are logged each quarter").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    # Real coverage, from the registry. The 8-quarter "drift" chart + direction table that used to
    # sit here were fabricated seed data — invented quarter-by-quarter PT trajectories. The platform
    # doesn't snapshot PTs over time yet, so a historical series can't be real. What IS real, and
    # what we show instead: every covering analyst, their standing PT + upside where we've logged
    # one, and the covering analysts whose current PT we simply haven't logged yet. We split on
    # "is a PT on file" — NOT on the registry's status flag, which does NOT mean coverage dropped
    # (all these firms actively cover the name). The drift chart returns via the Intelligence Signal
    # once ≥2 quarters of PTs are actually logged.
    analysts = [a for a in (CA() or []) if a.get("firm")]
    with_pt = [a for a in analysts if a.get("pt") is not None]
    without_pt = [a for a in analysts if a.get("pt") is None]

    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label("Current price targets").classes("font-bold").style(f"color:{COLORS['text_heading']};")
        if with_pt:
            rows = []
            for a in sorted(with_pt, key=lambda x: -(x.get("pt") or 0)):
                pt = a["pt"]
                upside = round((pt - last_price) / last_price * 100, 1) if last_price else None
                rows.append({
                    "Firm": a.get("firm", "—"), "Analyst": a.get("name", "—"),
                    "Rating": a.get("rating") or "—",
                    "PT": f"${pt:.2f}",
                    "Upside vs last": f"{upside:+.1f}%" if upside is not None else "—",
                })
            ui.table(columns=[{"name": k, "label": k, "field": k, "align": "left"} for k in rows[0].keys()],
                     rows=rows, row_key="Firm").classes("w-full")
            pts = [a["pt"] for a in with_pt]
            ui.label(f"PT range ${min(pts):.2f}–${max(pts):.2f} · {len(with_pt)} of {len(analysts)} covering "
                     f"analysts with a PT logged vs ${last_price:.2f} last").style(
                f"color:{COLORS['text_muted']};font-size:11.5px;")
        else:
            ui.label("No analyst price targets logged yet.").style(f"color:{COLORS['text_muted']};font-size:12px;")

    if without_pt:
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            ui.label("Also covering — no desk-confirmed PT on file").classes("font-bold").style(
                f"color:{COLORS['text_heading']};")

            def _cov_line(a):
                bits = [a.get("rating") or "no rating logged"]
                if a.get("pt_provisional"):
                    bits.append(f"${a['pt_provisional']:.2f} PT")
                tail = " · provisional" if a.get("provisional") else ""
                return f"{a.get('firm')} ({a.get('name')} — {', '.join(bits)}{tail})"

            ui.label(", ".join(_cov_line(a) for a in without_pt if a.get('name'))).style(
                f"color:{COLORS['text_muted']};font-size:12px;")
            if any(a.get("provisional") for a in without_pt):
                _srcs = "; ".join(f"{a.get('firm')}: {a['rating_source']}"
                                  for a in without_pt if a.get("provisional") and a.get("rating_source"))
                ui.label(f"Provisional = from public aggregators, not folded into the range/median above — confirm "
                         f"with each desk, then log via Model Intake. Sources — {_srcs}.").style(
                    f"color:{COLORS['text_muted']};font-size:10.5px;font-style:italic;")
            else:
                ui.label("These analysts cover the name; log their latest PT (and rating) via Model Intake to bring "
                         "them into the range above and the drift history.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")

    _render_rating_actions()

    waiting_signal("logged analyst PTs over time",
                   detail="Each PT is captured as models and analyst notes are logged; a multi-quarter drift chart "
                          "appears once at least two quarters of PTs are on file.",
                   unlocks="the PT drift chart and raising/cutting direction per analyst over time.")


def _render_rating_actions():
    """Analyst rating CHANGES from Finnhub (upgrades/downgrades/initiations) — the quant &
    aggregator moves (Verus, Zacks) our covering desks don't include. Distinct signal, often a
    good market-timing read. No key -> a connect prompt; nothing fabricated."""
    from core import rating_actions
    from page_modules_nicegui.signals import waiting_signal

    ui.markdown("---")
    ui.label("Analyst rating changes — upgrades & downgrades").classes("font-bold")
    ui.label("Structured rating moves (Finnhub) from quant & aggregator shops — Verus, Zacks and the like — "
             "separate from the covering desks above. These can be early market-timing signals.").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    if not rating_actions.has_key():
        waiting_signal(
            "your Finnhub API key",
            detail="Add a free Finnhub key to .env (FINNHUB_API_KEY=...) to pull the full upgrade/downgrade "
                   "history for this ticker — including a one-time backfill of past rating changes.",
            unlocks="a dated feed of every analyst upgrade/downgrade/initiation, on the Today tab and weekly brief.")
        return

    items = rating_actions.recent(limit=8)
    if not items:
        ui.label("Finnhub key detected, but no rating changes are stored yet — run a refresh to backfill the "
                 "history (Settings → data refresh, or the Console ↻).").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
        return

    _tone = {"up": "#15803D", "down": "#B91C1C", "init": "#1E40AF"}
    for it in items:
        col = _tone.get(it.get("action"), COLORS["text_muted"])
        with ui.row().classes("w-full items-center").style("gap:10px;"):
            ui.label(rating_actions.glyph(it)).style(f"color:{col};font-weight:800;font-size:13px;")
            ui.label(it.get("date") or "—").style(f"color:{COLORS['text_muted']};font-size:11.5px;min-width:82px;")
            ui.label(rating_actions.describe(it)).style(f"color:{COLORS['text_body']};font-size:12.5px;")

    ui.markdown("---")
    ui.label("PT Justification & Valuation Methodology").classes("font-bold")
    ui.label("Reverse-engineering each analyst's implied multiple (their PT against our real share "
             "count and net debt) shows whether they're applying a premium, discount, or in-line "
             "multiple — and flags a PT that has drifted too far above the tape to stay credible.").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")
    # GATED (2026-07-21): the per-firm justification cards + PT Credibility Watchlist that used to
    # render here were built from seed `pt_justification`, whose PT-set dates, stock-at-set prices,
    # FY-basis revenue estimates and methodology prose were fabricated demo precision — exactly the
    # detail a covering analyst's own CEO would catch as wrong. There is no real source for it yet:
    # a genuine implied EV/Revenue multiple needs each analyst's FORWARD revenue basis, which
    # arrives when their model is logged in Earnings → Model Intake. Until then we surface the
    # dependency via the Intelligence Signal rather than invented numbers.
    waiting_signal("logged analyst models (PT basis + forward revenue)",
                   detail="Log each covering analyst's model in Earnings → Model Intake — PT, rating, and the "
                          "forward-year revenue their target is built on. This section then computes each "
                          "implied EV/Revenue multiple from real inputs and flags PTs that have drifted too "
                          "far above the tape to stay credible.",
                   unlocks="per-analyst implied multiple vs the peer median (premium/discount) and a PT "
                           "credibility watchlist.")

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

    # Re-enabled (2026-07-21): generate_pt_drift_slide() now reads the HONEST pt_history served by
    # core.consensus (empty until a real PT-snapshot series exists), so with no real drift it exports
    # a clean current-PTs slide via _pt_drift_placeholder_slide — no fabricated trajectories. Once a
    # real multi-period series accrues, the same function draws the drift chart automatically.
    ui.button("Generate PT Drift Board Slide (.pptx)", on_click=_export_board_slide).props("color=primary")
    ui.label("Exports the current price targets on file; the multi-quarter drift chart is added once PT "
             "history accrues (no fabricated trajectories).").style(
        f"color:{COLORS['text_muted']};font-size:10.5px;font-style:italic;")


# ─────────────────────────────────────────────────────────────────────────
# NOBO Ownership — the CEO's window into the (retail-heavy) base that 13F
# never captures. Compute lives in core.nobo_engine; this renders it.
# ─────────────────────────────────────────────────────────────────────────
def _render_nobo():
    cid = get_active_client_id()

    @ui.refreshable
    def _panel():
        pulls = nobo_engine.get_active_pulls(cid)
        so = pulls["shares_outstanding"]
        current, prior, source = pulls["current"], pulls["prior"], pulls["source"]

        # No real NOBO uploaded yet -> Intelligence Signal + upload, NOT the fabricated demo pull.
        # A client (esp. a NOBO-focused CEO) must never see 372 invented holders presented as an
        # ownership base. get_active_pulls falls back to source='demo' until a Broadridge file lands.
        if source == "demo":
            from page_modules_nicegui.signals import waiting_signal
            from core import targets as targets_mod
            ui.label("NOBO Ownership Analysis").classes("text-lg font-bold")

            # SURFACE-FIRST (2026-07-21): before any Broadridge NOBO file exists, tell the ownership
            # story we CAN tell from PUBLIC 13F filings — real institutional holders, concentration
            # and add/trim momentum. The Broadridge upload then ADDS the retail/beneficial layer 13F
            # can't see. Never the fabricated demo holders. See memory: surface-first-then-refine.
            def _fmtv(v):
                if not v:
                    return "—"
                if v >= 1e9:
                    return f"${v / 1e9:.1f}B"
                if v >= 1e6:
                    return f"${v / 1e6:.1f}M"
                return f"${v / 1e3:.0f}K"

            _act = {"new": "New — engage", "adding": "Adding", "trimming": "Trimming — why?",
                    "exited": "Exited", "flat": "Flat"}
            holders = targets_mod.targets_from_13f(cid)
            sized = [h for h in holders if h.get("Position_Value")]
            if sized:
                total_val = sum(h["Position_Value"] for h in sized)
                total_sh = sum(h.get("Shares") or 0 for h in sized)
                top10 = sorted(sized, key=lambda h: -(h["Position_Value"] or 0))[:10]
                top10_pct = round(sum(h["Position_Value"] for h in top10) / total_val * 100) if total_val else 0
                inst_pct = round(total_sh / so * 100, 1) if so else None
                dirs = [h.get("Direction") for h in holders]
                n_acc = sum(1 for d in dirs if d in ("new", "adding"))
                n_dist = sum(1 for d in dirs if d in ("trimming", "exited"))

                ui.label("Institutional ownership — live from public 13F filings").classes("font-bold").style(
                    "margin-top:6px;")
                ui.label("Your institutional base out of the box, sourced from EDGAR 13F. NOBO (below) adds the "
                         "retail & beneficial owners that 13F never captures.").style(
                    f"color:{COLORS['text_muted']};font-size:11.5px;")
                with ui.row().classes("w-full gap-3"):
                    _metric("13F holders", f"{len(sized)}", "institutions on file")
                    _metric("Institutional $ held", _fmtv(total_val), f"{total_sh:,} shares")
                    _metric("Held vs shares out", f"≥{inst_pct:.1f}%" if inst_pct is not None else "—",
                            "of shares outstanding · 13F filers only")
                    _metric("Top-10 concentration", f"{top10_pct}%", "of 13F-visible value")
                if n_acc or n_dist:
                    _tone = "net accumulation" if n_acc > n_dist else "net distribution" if n_dist > n_acc else "mixed"
                    ui.label(f"Position momentum — {n_acc} accumulating (new / adding) vs {n_dist} trimming / exited: "
                             f"{_tone}.").style(f"color:{COLORS['text_muted']};font-size:11.5px;margin-top:2px;")
                _rows = [{
                    "Holder": (h.get("Fund") or "—").title(),
                    "Value": _fmtv(h.get("Position_Value")),
                    "Book %": f"{h['Book_Pct']:.2f}%" if h.get("Book_Pct") is not None else "—",
                    "Conviction": h.get("Conviction") or "—",
                    "Action": _act.get(h.get("Direction"), "—"),
                } for h in top10]
                ui.table(columns=[{"name": k, "label": k, "field": k, "align": "left"} for k in _rows[0].keys()],
                         rows=_rows, row_key="Holder").classes("w-full").props("dense flat")
                ui.markdown("---")

            waiting_signal(
                "your Broadridge NOBO file",
                detail=("Above is your INSTITUTIONAL base from public 13F filings. Upload a Broadridge NOBO CSV to "
                        "add the retail & beneficial owners 13F can't see — completing the ownership picture."
                        if sized else
                        "No NOBO pull is loaded yet. Upload a Broadridge NOBO CSV to activate this section."),
                unlocks="retail & beneficial composition, coverage of shares outstanding, 5%+ threshold alerts, "
                        "and the two-pull flow read (who's accumulating vs trimming).")
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_hover_bg']};border-radius:8px;margin-top:8px;"):
                ui.label("Upload a NOBO pull").classes("font-bold").style("font-size:12px;")
                ui.label("Columns detected flexibly: holder name, shares/position, optionally city/state/type. "
                         "Upload two dated pulls to unlock the flow read.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;")
                with ui.row().classes("w-full gap-4 items-end"):
                    _rd = ui.input("Record date (YYYY-MM-DD)").props("dense outlined").classes("w-48")
                    _so = ui.number("Shares outstanding", value=so).props("dense outlined").classes("w-48")

                def _up(e, rd=_rd, so_in=_so):
                    try:
                        raw = e.content.read()
                        text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
                    except Exception as exc:
                        ui.notify(f"Could not read file: {exc}", type="negative"); return
                    pull = nobo_engine.parse_nobo_csv(text, rd.value or e.name)
                    if not pull["holders"]:
                        ui.notify("No holders parsed — the CSV needs at least name and shares columns.", type="warning"); return
                    n = nobo_engine.save_uploaded_pull(pull, int(so_in.value) if so_in.value else None, cid)
                    ui.notify(f"Loaded {len(pull['holders']):,} holders as pull '{pull['record_date']}'. "
                              f"{n} pull(s) stored.", type="positive")
                    _panel.refresh()
                ui.upload(on_upload=_up, auto_upload=True).props("accept=.csv flat").classes("max-w-full")
            return

        cur = nobo_engine.analyze_pull(current, so)
        pre = nobo_engine.analyze_pull(prior, so) if prior else None
        fl = nobo_engine.flow(current, prior) if prior else None
        alerts = nobo_engine.threshold_alerts(current, so)
        tracked = {i["Fund"] for i in get_seed_buyside_institutions(cid)}
        xref = nobo_engine.cross_reference(current, tracked)

        ui.label("NOBO Ownership Analysis").classes("text-lg font-bold")
        _vs = f" · vs prior pull {pre['record_date']}" if pre else " · single pull (snapshot)"
        ui.label(f"Non-Objecting Beneficial Owners · record date {cur['record_date']}{_vs} · "
                 f"{CT('ticker')} {so:,} shares outstanding").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
        _src_txt = {"demo": "Demo data", "uploaded": f"Uploaded · {pulls['n_pulls']} pulls",
                    "uploaded-single": "Uploaded · 1 pull"}.get(source, source)
        _src_clr = "#B45309" if source == "demo" else "#15803D"
        ui.label(f"● Data source: {_src_txt}").style(f"color:{_src_clr};font-size:11px;font-weight:700;")

        # BLUF — the CEO's read, up top (same pattern as the guidance morning-after).
        with ui.card().classes("w-full").style(
                "background:rgba(30,64,175,.06);border:1.5px solid #1E40AF;border-left:6px solid #1E40AF;"
                "border-radius:10px;margin-top:8px;"):
            ui.label("THE CEO'S NOBO READ — what the ownership base is telling you").style(
                "color:#1E3A8A;font-size:11px;font-weight:700;letter-spacing:.04em;")
            for p in nobo_engine.ceo_read(cur, pre, fl, alerts):
                ui.label("• " + p).style(
                    f"color:{COLORS['text_heading']};font-size:13px;line-height:1.6;font-weight:500;")

        # Composition & concentration
        ui.label("Composition & concentration").classes("font-bold").style("margin-top:10px;")
        _hhi_label = "diffuse" if cur["hhi"] < 1000 else ("moderate" if cur["hhi"] < 1800 else "concentrated")
        with ui.row().classes("w-full gap-3"):
            _metric("NOBO holders", f"{cur['n_holders']:,}", f"{cur['n_inst']} institutional · {cur['n_retail']:,} retail")
            _metric("NOBO shares", f"{cur['total_shares']:,}", f"{cur['nobo_pct_so']:.1f}% of shares outstanding")
            _metric("Institutional / retail", f"{cur['inst_pct']:.0f}% / {cur['retail_pct']:.0f}%", "of visible NOBO shares")
            _metric("Top-10 concentration", f"{cur['top10_pct']:.0f}%", f"HHI {cur['hhi']:.0f} · {_hhi_label}")

        # Coverage-of-float bar
        _visible = min(cur["nobo_pct_so"], 100)
        _rest = max(0, 100 - _visible)
        ui.label("Coverage of shares outstanding").classes("font-bold").style("margin-top:10px;")
        ui.html(
            "<div style='display:flex;width:100%;height:26px;border-radius:6px;overflow:hidden;"
            "font-size:11px;font-weight:600;'>"
            f"<div style='width:{_visible:.1f}%;background:#1E40AF;color:#fff;display:flex;align-items:center;"
            f"justify-content:center;white-space:nowrap;'>NOBO visible {_visible:.0f}%</div>"
            f"<div style='width:{_rest:.1f}%;background:#E2E8F0;color:#475569;display:flex;align-items:center;"
            f"justify-content:center;white-space:nowrap;'>OBO / registered / insider {_rest:.0f}%</div>"
            "</div>")

        # Two-pull flow — the deltas the CEO watches (only with a prior pull).
        ui.label("Two-pull flow — who moved since the prior record date").classes("font-bold").style("margin-top:12px;")
        if not fl:
            ui.label("Only one pull loaded — upload an earlier NOBO pull below to unlock the flow read "
                     "(accumulators, distributors, new, and exited holders).").style(
                f"color:{COLORS['text_muted']};font-size:12px;")
        else:
            with ui.row().classes("w-full gap-3"):
                _metric("Net change", f"{fl['net_change']:+,}", "NOBO shares vs prior pull")
                _metric("Accumulating", f"{fl['n_acc']}", f"+{fl['acc_shares']:,} sh incl. new")
                _metric("Trimming", f"{fl['n_dist']}", f"−{fl['dist_shares']:,} sh incl. exits")
                _metric("New / exited", f"{fl['n_new']} / {fl['n_exit']}", "holders")
            with ui.row().classes("w-full gap-6 items-start").style("margin-top:6px;"):
                with ui.column().classes("flex-1").style("min-width:240px;"):
                    ui.label("Top accumulators").style("color:#15803D;font-size:12px;font-weight:700;")
                    for h, d in fl["accumulators"][:6]:
                        ui.label(f"+{d:,} · {h['name']} ({h['type'][:4]})").style(
                            f"color:{COLORS['text_body']};font-size:12px;")
                with ui.column().classes("flex-1").style("min-width:240px;"):
                    ui.label("Top distributors").style("color:#B45309;font-size:12px;font-weight:700;")
                    for h, d in fl["distributors"][:6]:
                        ui.label(f"{d:,} · {h['name']} ({h['type'][:4]})").style(
                            f"color:{COLORS['text_body']};font-size:12px;")
            if fl["new"]:
                _nl = ", ".join(f"{h['name']} ({s:,})" for h, s in fl["new"][:5])
                ui.label(f"New holders ({fl['n_new']}): {_nl}{' …' if fl['n_new'] > 5 else ''}").style(
                    f"color:{COLORS['text_muted']};font-size:11px;margin-top:4px;")

        # Threshold watch
        ui.label("Ownership threshold watch (13D / 13G)").classes("font-bold").style("margin-top:12px;")
        if not alerts:
            ui.label("No holder is within range of a 5% filing threshold.").style(
                f"color:{COLORS['text_muted']};font-size:12px;")
        for a in alerts:
            h = a["holder"]
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                    f"border-left:4px solid {a['color']};padding:6px 10px;"):
                ui.label(f"{h['name']} — {a['pct']:.2f}% of shares outstanding · {a['level']}").style(
                    f"color:{a['color']};font-size:12.5px;font-weight:600;")
                ui.label(f"{h['shares']:,} shares · {h['type']} · {h.get('city','')}, {h.get('state','')}").style(
                    f"color:{COLORS['text_muted']};font-size:11px;")

        # Cross-reference with the tracked book — contactable holders are
        # actionable: Call / Email / Log outreach into the IR pipeline.
        ui.label("Cross-reference with your book").classes("font-bold").style("margin-top:12px;")
        ui.label(f"{len(xref['contactable'])} NOBO institutions are in your tracked universe — reach them "
                 "directly and log the touch into your pipeline activity.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")

        def _tel(phone):
            return "tel:" + "".join(c for c in str(phone) if c.isdigit() or c == "+")

        for h in xref["contactable"]:
            cc = get_institution_contacts().get(h["name"], {})
            pct = h["shares"] / so * 100 if so else 0
            with ui.row().classes("w-full items-center gap-2").style(
                    f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:4px 8px;margin:2px 0;"):
                with ui.column().classes("gap-0 flex-1"):
                    ui.label(h["name"]).style(f"color:{COLORS['text_body']};font-size:12.5px;font-weight:600;")
                    _sub = f"{h['shares']:,} sh · {pct:.2f}% of S/O"
                    if cc.get("name"):
                        _sub += f" · {cc['name']} ({cc.get('title','')})"
                    if cc.get("phone"):
                        _sub += f" · {cc['phone']}"
                    ui.label(_sub).style(f"color:{COLORS['text_muted']};font-size:11px;")
                if cc.get("phone"):
                    with ui.link(target=_tel(cc["phone"])).tooltip(f"Call {cc['phone']}"):
                        ui.icon("call").style(f"color:{COLORS['accent_light']};font-size:18px;")
                if cc.get("email"):
                    _first = cc.get("name", "").split()[0] if cc.get("name") else ""
                    _subj = f"{CT('ticker')} — connecting with a valued holder"
                    _body = (f"Hi {_first},\n\nWe noticed {h['name']} among our shareholders and wanted to make "
                             f"sure you have direct access to {CT('name')} management ahead of our upcoming print. "
                             f"Would you have time for a call or meeting?\n\n")
                    _href = f"mailto:{cc['email']}?subject={quote(_subj)}&body={quote(_body)}"
                    with ui.link(target=_href).tooltip(f"Email {cc['email']}"):
                        ui.icon("mail").style(f"color:{COLORS['accent_light']};font-size:18px;")

                def _log(h=h):
                    activity_log.log_event("nobo_outreach", entity=h["name"],
                                           launched_from="Investor Targeting · NOBO Ownership")
                    ui.notify(f"Logged outreach to {h['name']} — added to your pipeline activity.", type="positive")

                _lb = ui.button("Log outreach", on_click=_log).props("flat dense color=primary")
                if ui_context.is_read_only():
                    _lb.disable()
        ui.button("Open Investor Targeting →", on_click=lambda: nav.go_to("Investors")).props(
            "flat dense").style("margin-top:2px;")
        if xref["untracked"]:
            _ut = ", ".join(f"{h['name']} ({h['shares']:,})" for h in xref["untracked"])
            ui.label(f"Not in your tracked book: {_ut}").style("color:#B45309;font-size:11.5px;margin-top:4px;")
        else:
            ui.label("Every institutional NOBO holder is already in your tracked book — no blind spots this pull.").style(
                f"color:{COLORS['text_muted']};font-size:11px;margin-top:2px;")

        # Top holders
        with ui.expansion(f"Top {len(cur['top_holders'])} NOBO holders").classes("w-full").style("margin-top:10px;"):
            cols = ["Holder", "Type", "Location", "Shares", "% of S/O"]
            rows = [{"Holder": h["name"], "Type": h["type"],
                     "Location": f"{h.get('city','')}, {h.get('state','')}",
                     "Shares": f"{h['shares']:,}", "% of S/O": f"{h['shares'] / so * 100:.2f}%"}
                    for h in cur["top_holders"]]
            ui.table(columns=[{"name": c, "label": c, "field": c, "align": "left"} for c in cols],
                     rows=rows).classes("w-full").props("dense flat")

        # Data source + Broadridge NOBO file upload
        with ui.expansion("Load a Broadridge NOBO file (CSV)").classes("w-full").style("margin-top:10px;"):
            if ui_context.is_read_only():
                ui.label("Read-only role — NOBO file upload is disabled.").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")
            else:
                ui.label("Columns are detected flexibly: holder name, shares/position, and optionally city, "
                         "state, and type (inferred from the name when absent). Upload two dated pulls to unlock "
                         "the flow read.").style(f"color:{COLORS['text_muted']};font-size:11px;")
                with ui.row().classes("w-full gap-4 items-end"):
                    rd = ui.input("Record date (YYYY-MM-DD)").props("dense outlined").classes("w-48")
                    so_in = ui.number("Shares outstanding", value=so).props("dense outlined").classes("w-48")

                def _handle_upload(e, rd=rd, so_in=so_in):
                    try:
                        raw = e.content.read()
                        text = raw.decode("utf-8-sig", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
                    except Exception as exc:
                        ui.notify(f"Could not read file: {exc}", type="negative")
                        return
                    pull = nobo_engine.parse_nobo_csv(text, rd.value or e.name)
                    if not pull["holders"]:
                        ui.notify("No holders parsed — the CSV needs at least name and shares columns.", type="warning")
                        return
                    n = nobo_engine.save_uploaded_pull(pull, int(so_in.value) if so_in.value else None, cid)
                    ui.notify(f"Loaded {len(pull['holders']):,} holders as pull '{pull['record_date']}'. "
                              f"{n} pull(s) stored.", type="positive")
                    _panel.refresh()

                ui.upload(on_upload=_handle_upload, auto_upload=True).props("accept=.csv flat").classes("max-w-full")
                if source != "demo":
                    ui.button("Reset to demo data",
                              on_click=lambda: (nobo_engine.reset_to_demo(cid),
                                                ui.notify("Reset to demo NOBO data."), _panel.refresh())).props(
                        "flat dense color=negative")

        ui.label("A NOBO list captures only Non-Objecting Beneficial Owners as of the record date — Objecting "
                 "holders (OBO) and shares in registered/insider hands aren't shown, so read it alongside your 13F "
                 "and directly-registered lists.").style(
            f"color:{COLORS['text_muted']};font-size:11px;margin-top:10px;")

    _panel()
