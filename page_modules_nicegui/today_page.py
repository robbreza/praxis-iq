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


def _as_of_short(snap):
    """Quote timestamp in a form a person reads, not a log line.

    "2026-07-22 12:03 · up to 60-min delay" was the loudest text in the metrics card.
    Same-day quotes render as "12:03 today"; older ones as "Jul 21, 16:20"."""
    raw = (snap or {}).get("as_of") or ""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", ""))
    except ValueError:
        return str(raw)[:16].replace("T", " ") or "time unavailable"
    now = datetime.now()
    if dt.date() == now.date():
        return f"{dt:%H:%M} today"
    if (now.date() - dt.date()).days == 1:
        return f"{dt:%H:%M} yesterday"
    return f"{dt:%b} {dt.day}, {dt:%H:%M}"


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


def _guidance_midpoint(period="Q2 2026E"):
    """Real Q2 revenue-guidance midpoint from the consensus store, not a literal."""
    from config.client_config import get_active_client_id
    from core.consensus import get_consensus
    g = get_consensus(get_active_client_id()).get("period_guidance", {}).get(period, {})
    return g.get("Revenue Est ($M)")


def _street_rev_consensus(period="Q2 2026E"):
    """Real Street revenue consensus = mean of covering analysts' revenue estimates,
    or None when no covering analyst has a revenue model on file (USIO's actual
    state) — so callers can be honest that there's no Street number to compare to."""
    from config.client_config import get_active_client_id
    from core.consensus import get_consensus
    ests = get_consensus(get_active_client_id()).get("period_estimates", {}).get(period, {})
    covering = {a["firm"] for a in CA() if a.get("covering", True)}
    revs = [ests[f]["Revenue Est ($M)"] for f in ests
            if f in covering and ests.get(f, {}).get("Revenue Est ($M)") is not None]
    return sum(revs) / len(revs) if revs else None


def _upcoming_conferences():
    """Upcoming INVESTOR conferences with their REAL status, from the same source
    the Calendar uses (db 'ir_conference_calendar.csv', else the client seed) — not
    a hardcoded 'confirmed' literal."""
    from datetime import date
    from config.client_config import get_active_client_id
    rows = db.load_json("ir_conference_calendar.csv", None)
    if not rows:
        from data.seed.conferences import get_seed_conferences
        rows = get_seed_conferences(get_active_client_id())
    today_s = date.today().isoformat()
    out = [r for r in (rows or [])
           if "investor" in str(r.get("Type", "")).lower() and str(r.get("Date", "")) >= today_s]
    return sorted(out, key=lambda r: str(r.get("Date", "")))


def _today_story_parts(snap, recent):
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
        # No raw "as of 2026-07-22 12:03" mid-sentence — it reads like a log line and
        # breaks the narrative. The delay is disclosed in the Key market metrics footnote.
        price_line = f"{ticker} is {direction} {abs(chg):.1f}%{vol_txt}."
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

    return price_line, activity_line


def _today_story_text(snap, recent):
    """The full story paragraph (opening price sentence + activity sentence) as one
    string — kept for any caller that wants the whole narrative in one label."""
    _p, _a = _today_story_parts(snap, recent)
    return f"{_p} {_a}"


def _talking_points(state, overdue, readiness_pct, days_to_earnings=None):
    """Real, computed stand-ins for the old 3 hardcoded talking points —
    each line reflects an actual queryable fact (overdue count, script
    readiness, open signal count) rather than a fixed script."""
    points = []
    # Analyst follow-ups run BOTH ways: model requests we sent that nobody answered
    # (outbound), and meeting requests analysts sent US that are still unresolved
    # (inbound). This counted only the outbound half, so Today could report "no
    # analyst follow-ups are overdue" on the same day Investor Targeting said
    # "respond to Owen Pike before the quiet period" — two management to-do lists
    # contradicting each other. Today is the authoritative one, so it counts both.
    inbound = [r for r in (db.load_json("ndr_requests.json", default=[]) or [])
               if not r.get("resolved")]
    if overdue or inbound:
        bits = []
        if overdue:
            bits.append(f"{len(overdue)} model request(s) unanswered >24h ("
                        + ", ".join(o["entity"] for o in overdue[:3]) + ")")
        if inbound:
            bits.append(f"{len(inbound)} analyst meeting request(s) awaiting your reply ("
                        + ", ".join(f"{r.get('analyst','?')} — {r.get('city','?')}" for r in inbound[:3]) + ")")
        points.append(" · ".join(bits) + " — close these before the quiet period.")
    else:
        points.append("No analyst follow-ups are outstanding — nothing sent unanswered, nothing awaiting your reply.")

    # The earnings-script % clock only STARTS in the final two weeks before earnings (the last two
    # weeks of the quarter). Outside that window the review is intentionally NOT scored or flagged —
    # the event stays on the list, but with no % and no "needs attention" until the clock is running.
    if days_to_earnings is not None and days_to_earnings > 14:
        points.append(f"Earnings script review — the review clock starts in the final two weeks before "
                      f"earnings ({days_to_earnings - 14} day(s) out); nothing to measure yet.")
    elif readiness_pct >= 80:
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


def _open_lighthouse_nav():
    """Navigate to the Lighthouse page (with a telemetry ping), from the 'Full band
    on Lighthouse →' link now carried inside the Today's Focus card."""
    from config.client_config import get_active_client_id
    try:
        from lighthouse import telemetry as _tel
        _tel.record_view(get_active_client_id(), CT("ticker"), "today_mirror_click")
    except Exception:
        pass
    nav.go_to("Lighthouse")


def _weekly_context_data():
    """The cached weekly context for the active tenant, or None. Reads a context
    refreshed by the scheduler post-close and on any Lighthouse visit, so Today stays
    fast (no live attribution compute here). Wired for USIO in the MVP; other tenants
    skip it. Feeds the weekly sentence + 'Full band on Lighthouse' link now folded
    into the Today's Focus card (was the standalone 'This week in context' card)."""
    from config.client_config import get_active_client_id
    from core.curated_targets import _is_illustrative
    _cid, _tk = get_active_client_id(), CT("ticker")
    if _tk != "USIO" and not _is_illustrative(_cid):
        return None
    try:
        from lighthouse import weekly as _weekly
        wk = _weekly.load_context_cache(_cid, _tk)
    except Exception:
        wk = None
    if not wk or not wk.get("context") or not wk.get("context_read"):
        return None
    # ── Gate the weekly read so it can never contradict the fresh daily move shown right above it.
    # The daily line comes from core.market_data (a real-time-ish snapshot); this weekly comes from
    # Lighthouse's price model, which lags by up to a day. Its "latest ISO week" is therefore often a
    # 1-2 day PARTIAL that EXCLUDES today — e.g. USIO read -10.9% over just Aug 17-18 while the day was
    # +4.1%. Only surface it when it's a COMPLETE, recent week; otherwise show the daily line alone.
    # (Product decision: keep the peer/Russell context, but never let a stale partial window show.)
    from datetime import datetime as _dt, date as _date
    if (wk.get("trading_days") or 0) < 4:                 # a 1-3 day partial isn't "the week"
        return None
    if not _is_illustrative(_cid):                        # real data must also be recent, not a lagged
        try:                                              # snapshot; illustrative seed data is static
            _end = _date.fromisoformat((wk.get("week") or "").split("..")[-1].strip())
        except Exception:
            return None
        if (_dt.now().date() - _end).days > 7:
            return None
    return wk


def _panel(render_fn):
    """Render a dashboard section inside a grounded .today-panel card — but DROP the panel
    if the section produced nothing (some sections early-return, e.g. Activity & responses when
    no model requests are out). Without this, an empty section leaves a bare bordered box that
    reads as a mystery button. Returns True if a panel was kept."""
    panel = ui.element("div").classes("today-panel w-full")
    with panel:
        render_fn()
    if not panel.default_slot.children:
        panel.delete()
        return False
    return True


def _panel_head(title, right=None):
    """A flush grey header band at the top of a .today-panel card, matching the
    hero cards' TODAY'S FOCUS / KEY MARKET METRICS bands so every section reads
    the same instead of a bare bold title. The negative margins cancel the panel's
    14px/16px padding so the band spans edge to edge, and the top corners round to
    the panel's 12px radius. `right`, if given, is a callable rendered flush-right
    inside the band (e.g. a collapse chevron)."""
    band = ui.row().classes("rhead rhead-neutral items-center no-wrap").style(
        "margin:-14px -16px 12px;width:calc(100% + 32px);"
        "border-top-left-radius:12px;border-top-right-radius:12px;"
        + ("justify-content:space-between;" if right else ""))
    with band:
        ui.label(title)
        if right:
            right()
    return band


def render_today_page():
    state = _load_state()
    today_d = datetime.now().date()
    earnings_date_str = CE().get("earnings_date", "2026-08-12")
    earnings_date = datetime.strptime(earnings_date_str, "%Y-%m-%d").date()
    days = max((earnings_date - today_d).days, 0)
    # Date moved to the app header (top bar), off the canvas — so the greeting and cards sit at the top.
    # Greet the persona currently selected in the "Logged in as" switcher (IR / CEO / CFO / CRO) so
    # the picker and the greeting stay aligned — the person for that role comes from the client
    # profile (role_roster), never a hardcoded name. Falls back to the signed-in account, then a
    # clean name-less greeting when there's no session (e.g. the smoke renderer).
    first_name = ""
    _is_team = False
    try:
        from config.client_config import role_roster as _rr
        _role = ui_context.current_role()
        _entry = next((r for r in _rr() if r.get("role_key") == _role), None)
        if _entry and _entry.get("name"):
            if _entry.get("is_team"):
                _is_team = True                      # generic desk (e.g. "Investor Relations") — greet the team
            else:
                first_name = _entry["name"].split(" ")[0]
    except Exception:
        first_name = ""
    if not first_name and not _is_team:
        try:
            from nicegui import app as _app
            from core import auth as _auth
            _uid = _app.storage.user.get("user_id")
            _u = _auth.get_user(_uid) if _uid else None
            first_name = ((_u or {}).get("display_name") or "").split(" ")[0]
        except Exception:
            first_name = ""
    _greeting = "Good morning, team." if _is_team else (f"Good morning, {first_name}." if first_name else "Good morning.")
    # Demoted from text-2xl: a compact salutation, not the biggest element on the page — the narrative
    # story is the hero (design-panel P0-3).
    ui.label(_greeting).classes("font-bold").style(
        f"color:{COLORS['text_heading']};font-size:var(--fs-xl);")

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
    # count_today() / minutes_saved_this_week() were read here only to feed the
    # removed automation-stats strip — dropped, which also spares Today two
    # activity_log round-trips per render. Reports → Automation Tracker still
    # reads both for its own (properly contextualised) view.
    overdue = activity_log.overdue_sent_without_response("model_request_sent", ["model_received"], hours=24)
    readiness_pct = _earnings_readiness_pct()
    snap = market_data.get_snapshot(CT("ticker"), refresh_if_stale=False)
    recent = activity_log.recent_events(limit=5)

    # ── (removed) ROI / "automation stats" strip ──
    # This showed "N tasks automated today" and "N hrs saved this week" behind a
    # Show/Hide toggle. Removed deliberately:
    #   * it answered the VENDOR's question, not the IR lead's, on the surface they
    #     open to find out who is buying and what needs a call today;
    #   * "hours saved" is an assumption (a per-event-type minute constant times a
    #     count), not a measurement — a soft number in the most prominent position
    #     on the app, which is exactly where a sharp CFO will poke at it;
    #   * it duplicated Reports → Automation Tracker, which presents the same
    #     activity with a real breakdown and trend, in the context (QBR / renewal)
    #     where the question is actually asked.
    # The Automation Tracker keeps every number; the ledger it reads
    # (core.activity_log) is untouched. Only this strip is gone, so the greeting
    # now flows straight into Today's Story.

    # ── Today's Story + Key Metrics ──
    # flex-col on phones so the two cards STACK (side-by-side at ~180px each made the story wrap one
    # word per line); md:flex-row restores the 7/3 split on desktop.
    # Same vertical height (items-stretch) + reduced padding so both hero cards are the same size.
    with ui.row().classes("w-full gap-4 items-stretch flex-col md:flex-row"):
        with ui.card().classes("w-full md:flex-[7]").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:12px;padding:0;overflow:hidden;"):
            # This card now absorbs the old "This week in context" and "Today's top
            # story" cards: the weekly stat slots in after the opening sentence, the
            # top story becomes the final talking point, and both cards' supporting
            # links ("Full band on Lighthouse →" / "More peer & competitor news ↓")
            # ride along.
            _wk = _weekly_context_data()
            with ui.row().classes("rhead rhead-neutral items-center").style(
                    "justify-content:space-between;" if _wk else ""):
                ui.label("Today's focus")
                if _wk:
                    ui.button("Full band on Lighthouse →", on_click=_open_lighthouse_nav) \
                        .props("flat dense size=sm no-caps")
            with ui.column().classes("w-full").style("padding:12px 20px 14px;gap:0;"):
                _price_line, _activity_line = _today_story_parts(snap, recent)
                ui.label(_price_line).style(f"color:{COLORS['text_body']};font-size:var(--fs-md);line-height:1.7;")
                if _wk:
                    # The weekly move in its yardstick (peers + Russell), right after the
                    # opening price sentence — the number is never shown without its comp.
                    ui.label(f"{CT('ticker')} {_wk['context_read']}").style(
                        f"color:{COLORS['text_heading']};font-size:var(--fs-md);font-weight:600;"
                        f"line-height:1.5;margin-top:3px;")
                ui.label("Talking points for management").classes("section-head").style("margin-top:12px;")
                # "Recent activity" now leads the talking points rather than sitting in
                # the story paragraph above.
                _points = [_activity_line] + _talking_points(state, overdue, readiness_pct, days)
                for i, pt in enumerate(_points, 1):
                    ui.label(f"{i}. {pt}").style(f"color:{COLORS['text_secondary']};font-size:var(--fs-base);line-height:1.6;")
                # Today's top story, folded in as the final talking point.
                _top, _own, _peer = _top_story_data()
                if _top:
                    _n = len(_points) + 1
                    _tag = CT("ticker") if _own else f"peer ({_top.get('ticker','')})"
                    with ui.row().classes("items-baseline").style("gap:6px;flex-wrap:wrap;line-height:1.6;margin-top:2px;"):
                        ui.label(f"{_n}. Today's top story · {_tag}:").style(
                            f"color:{COLORS['text_secondary']};font-size:var(--fs-base);")
                        # Link out only when there's a real URL — a None target makes NiceGUI's
                        # link component throw. Illustrative peer news can carry no URL.
                        if _top.get("url"):
                            ui.link(_top.get("title", ""), _top["url"]).props("target=_blank") \
                                .style(f"color:{COLORS['accent']};font-size:var(--fs-base);font-weight:600;text-decoration:none;")
                        else:
                            ui.label(_top.get("title", "")).style(
                                f"color:{COLORS['text_body']};font-size:var(--fs-base);font-weight:600;")
                    if _peer:
                        def _to_peer_news():
                            ui.run_javascript(
                                "document.getElementById('peer-news-anchor')?."
                                "scrollIntoView({behavior:'smooth', block:'start'});")
                        # A card footer: a divider rule above the link, flush to the card's
                        # side and bottom edges (negative margins cancel the body padding).
                        with ui.row().classes("w-full items-center").style(
                                f"margin:12px -20px -14px;width:calc(100% + 40px);"
                                f"border-top:1px solid {COLORS['border']};padding:8px 20px;"):
                            ui.button(f"More peer & competitor news ({len(_peer)}) ↓", on_click=_to_peer_news) \
                                .props("flat dense no-caps").style(f"color:{COLORS['accent']};font-size:var(--fs-sm);")

        with ui.card().classes("w-full md:flex-[3]").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:12px;padding:12px 20px;"):
            # Header band flush to the card edges (negative margins cancel the card's padding) so the
            # body below doesn't need re-indenting — matches the story card's neutral header.
            async def _refresh_metrics():
                # Acknowledge the click immediately (the fetch is a live network call and can take a
                # second or two), then confirm on completion. Runs the snapshot off the event loop so
                # the "Refreshing…" toast actually paints before the fetch blocks.
                import asyncio
                ui.notify("Refreshing market data…")
                await asyncio.to_thread(market_data.get_snapshot, CT("ticker"),
                                        refresh_if_stale=True, max_age_minutes=0)
                ui.notify("Market metrics updated.", type="positive")
                nav.go_to("Today")

            with ui.row().classes("rhead rhead-neutral items-center").style(
                    "margin:-12px -20px 10px;width:calc(100% + 40px);"):
                ui.label("Key market metrics")
                # Refresh control: the icon with the word "Refresh" beneath it (was a bare circle).
                with ui.column().classes("items-center gap-0").style("margin-left:auto;"):
                    ui.button(icon="refresh", on_click=_refresh_metrics).props("flat dense round size=sm")
                    ui.label("Refresh").style(
                        f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);line-height:1;margin-top:-2px;")
            # One metric pattern, repeated: eyebrow label · 18px value · semantic-
            # coloured delta. Consistent sizing is what makes it read as a designed
            # data panel rather than three differently-styled lines.
            def _kpi_label(text, top=True):
                ui.label(text).classes("t-eyebrow").style("margin-top:10px;" if top else "")

            def _kpi_value(text, color=None):
                ui.label(text).classes("font-bold").style(
                    f"color:{color or COLORS['text_heading']};font-size:var(--fs-xl);line-height:1.15;")

            if snap and snap.get("last_price") is not None:
                chg = snap.get("pct_change") or 0
                chg_clr = COLORS["success"] if chg >= 0 else COLORS["danger"]
                _kpi_label("Last price", top=False)
                with ui.row().classes("items-baseline gap-2"):
                    _kpi_value(f"${snap['last_price']:.2f}")
                    ui.label("*").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);") \
                        .tooltip("Delayed quote — see note below")
                    ui.label(f"{chg:+.1f}%").classes("font-bold").style(f"color:{chg_clr};font-size:var(--fs-sm);")
                _kpi_label("Volume vs 10-day avg")
                vol = (f"{snap['volume']/snap['avg_volume_10d']:.1f}x"
                       if (snap.get("volume") and snap.get("avg_volume_10d")) else "—")
                _kpi_value(vol)
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
                            "font-bold").style(f"color:{up_clr};font-size:var(--fs-sm);")
            else:
                ui.label("No active-analyst price targets on file.").classes("t-meta")

            # Footnote rather than a full "as of 2026-07-22 12:03 · up to 60-min delay"
            # line under the values — the raw stamp was the loudest thing in the card and
            # drew the eye away from the numbers. The asterisk carries it instead.
            if snap and snap.get("last_price") is not None:
                ui.label(f"* Delayed quote · {_as_of_short(snap)}").classes("t-fine").style(
                    "margin-top:10px;")

            # Key takeaway — one plain-language read so the card carries signal, not empty space
            # (design-panel P0-2). Grounded in the numbers above, no interpretation invented.
            if snap and snap.get("last_price") is not None and pt_avg is not None:
                _ups = (pt_avg / snap["last_price"] - 1) * 100
                _tk = (f"Trades {abs(_ups):.0f}% {'below' if _ups >= 0 else 'above'} the Street's "
                       f"${pt_avg:.2f} consensus target.")
                with ui.column().classes("w-full").style(
                        f"margin-top:14px;padding-top:12px;border-top:1px solid {COLORS['border']};gap:3px;"):
                    ui.label("Key takeaway").classes("t-eyebrow")
                    ui.label(_tk).style(f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);line-height:1.5;")

    # (The old "This week in context" and "Today's top story" cards used to render
    # here; both are now folded into the Today's Focus card above.)

    # ── Dashboard sections in two height-balanced columns ──
    # Sections are grouped to keep the two columns close in height rather than
    # pairing fixed rows (which left a tall section next to a short one with a
    # big empty void beneath it). Risk signals is the tallest block, so it
    # anchors the left column with analyst coverage below; the three shorter
    # sections stack on the right. `items-start` + this grouping keeps the
    # trailing whitespace minimal.
    # NOTE: the whole Today page is wrapped in one .emph-15 (~15% magnify) at the
    # render dispatch (app_nicegui.render_page), so every section here — plus the
    # header, hero and top story above — scales uniformly. Don't add a per-section
    # .emph-15 wrapper here or it would double-nest.
    with ui.row().classes("w-full gap-5 items-start flex-col md:flex-row").style("margin-top:4px;"):
        with ui.column().classes("w-full md:flex-1 gap-4"):
            _panel(lambda: _render_risk_signals(state, days, snap, pt_avg))
            _panel(lambda: _render_earnings_readiness(days))
            _panel(_render_peer_watch)
        with ui.column().classes("w-full md:flex-1 gap-4"):
            _panel(_render_investor_pipeline)
            _panel(_render_analyst_coverage)
            _panel(_render_insider_activity)
            _panel(lambda: _render_activity_responses(state))


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
    # Grey fill + a solid slate border so each signal reads as a bounded tile, not
    # loose text floating on the white parent card. #E6EBF2 sits a clear step below
    # the white card behind it, so the layering is visible; the explicit border
    # guarantees the box even where the global .q-card rule is overridden inline.
    with ui.card().classes("w-full").style(
            f"background:#E6EBF2;border:1px solid {COLORS['border']};border-radius:8px;"):
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
    _panel_head("Risk signals")

    # Covering analysts whose current PT we haven't logged — the concrete chase list.
    # "No PT on file" ≠ "dropped coverage": they cover, we just haven't collected it.
    missing_model_analysts = [a for a in CA() if a.get("pt") is None]

    # 1. Missing models — 5-state: complete / default / sent / noted / muted.
    # When every covering analyst's model is on file there is nothing to chase, so
    # this renders as a cleared signal rather than "0 of 5 analyst models missing —
    # — have no model on file", which is what the dynamic text produced at zero.
    if not missing_model_analysts:
        with _signal_card("", f"All {len(CA())} analyst models on file",
                          "Consensus is built from every covering analyst — no collection gap."):
            pass
    elif signals.is_muted(state, "models_request"):
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
        # Built from THIS client's own analysts. It used to hardcode "3 of 5 —
        # Maxim, Litchfield Hills, Barrington", so every tenant was shown USIO's
        # coverage list regardless of who they actually are.
        _n_missing, _n_total = len(missing_model_analysts), len(CA())
        _firms = ", ".join(a.get("firm", "?") for a in missing_model_analysts) or "—"
        with _signal_card("", f"{_n_missing} of {_n_total} analyst models missing",
                          f"{_firms} {'has' if _n_missing == 1 else 'have'} no model on file "
                          f"— consensus unreliable"):
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
        gm, street = _guidance_midpoint(), _street_rev_consensus()
        if gm is not None and street is not None:
            delta = (street - gm) / gm * 100
            g_title = f"Street {'above' if delta >= 0 else 'below'} guidance — {delta:+.1f}%"
            g_desc = f"Street revenue consensus ${street:.1f}M vs your ${gm:.1f}M guidance midpoint."
        elif gm is not None:
            g_title = "No Street revenue consensus to check guidance against"
            g_desc = (f"Q2 guidance midpoint is ${gm:.1f}M, but no covering analyst has a revenue model on "
                      f"file yet — there's no Street revenue number to compare it against.")
        else:
            g_title = "Guidance not on file"
            g_desc = "No Q2 revenue guidance midpoint is configured yet."
        with _signal_card("", g_title, g_desc):
            with _signal_actions():
                ui.button("Draft clarification", on_click=lambda: _open_guidance_dialog(state)).props("dense size=sm color=primary")
                _mute_button(state, "guidance_gap", "Today · Risk Signals · Guidance vs Street")

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
        _d = "day" if checkin_days == 1 else "days"
        with _signal_card("", f"{checkin_days} {_d} to consensus lock",
                          f"Quiet period starts in {checkin_days} {_d} — model requests need to close first"):
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
    # A permanent grey box with a solid border so the expander reads as a defined
    # control, not a loose "More market signals ⌄" line floating under the tiles.
    with ui.expansion("More market signals", value=False).classes("w-full").style(
            f"margin-top:6px;background:#E6EBF2;border:1px solid {COLORS['border']};border-radius:8px;"):
        with _signal_card("", pt_title, pt_desc):
            with _signal_actions():
                ui.button("Why the gap?", on_click=lambda: _open_disconnect_dialog(snap, pt_avg)).props("flat dense size=sm")

        _chg = _top_ownership_change()
        if _chg:
            with _signal_card("", "Ownership change", _chg):
                with _signal_actions():
                    ui.button("Cross-reference target list", on_click=_open_target_list_dialog).props("flat dense size=sm")

        _confs = _upcoming_conferences()
        if _confs:
            _c = _confs[0]
            _status = _c.get("Status", "") or "status unknown"
            _confirmed = _status.lower().startswith("confirmed")
            _c_title = f"Conference {'confirmed' if _confirmed else 'invite — pending'}: {_c.get('Event','')}"
            _c_desc = " · ".join(x for x in [_c.get("Date", ""), _c.get("Location", ""), _status] if x)
            with _signal_card("", _c_title, _c_desc):
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
        ui.label("HIGH PRIORITY").style(f"background:{COLORS['warning']};color:white;padding:2px 8px;border-radius:8px;font-size:var(--fs-xs);")
        ui.label("Recipients — uncheck anyone you don't want to include:").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);margin-top:8px;")
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
        reason_input = ui.input("Reason (optional, if not sending)").props("outlined dense").classes("w-full")

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
        guide_mid, street = _guidance_midpoint(), _street_rev_consensus()
        gm_str = f"${guide_mid:.1f}M" if guide_mid is not None else "not on file"
        if guide_mid is not None and street is not None:
            delta = street - guide_mid
            ui.label(f"Guidance midpoint: {gm_str} · Street consensus: ${street:.1f}M · "
                     f"Delta: {delta:+.1f}M / {delta/guide_mid*100:+.1f}%").style(
                f"background:{COLORS['surface_hover_bg']};padding:8px 12px;border-radius:8px;font-size:var(--fs-base);")
            street_line = f"We've noticed current Street consensus is modeling at ${street:.1f}M vs our {gm_str} midpoint."
        else:
            ui.label(f"Guidance midpoint: {gm_str} · No Street revenue consensus yet — no covering analyst "
                     f"has a revenue model on file.").style(
                f"background:{COLORS['surface_hover_bg']};padding:8px 12px;border-radius:8px;font-size:var(--fs-base);")
            street_line = ("We don't yet have Street revenue models on file, and want to make sure covering "
                           "analysts are building to our guidance.")
        memo = (f"Hi [Analyst],\n\nAhead of our upcoming earnings release, I'm reaching out to ensure all covering "
                f"models are closely aligned with our stated guidance parameters.\n\nManagement's Q2 guidance "
                f"midpoint stands at {gm_str}. {street_line} Let me know if you'd like to review the core "
                f"assumptions.\n\nBest,\n{CI().get('name','')}")
        ui.textarea("Memo template — edit before sending", value=memo).classes("w-full").props("rows=6 outlined")
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
        reason_input = ui.input("Reason (optional, if not sending)").props("outlined dense").classes("w-full").style("margin-top:8px;")

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
        ui.label("No live calendar integration — these are suggested slots to confirm manually.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
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
        reason_input = ui.input("Reason (optional, if not sending)").props("outlined dense").classes("w-full").style("margin-top:8px;")

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
                 "correlation.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        ui.html(
            "<div style='background:#EEF2F7;border-radius:8px;padding:10px 14px;font-size:var(--fs-base);color:#1E293B;line-height:1.6;'>"
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
            value=(f"The gap between our stock price and Street targets reflects thin, aging coverage more than a "
                   f"fundamental disagreement — {total_n - active_n} of {total_n} covering analysts don't have a "
                   f"current model on file."),
        ).classes("w-full").props("rows=4 outlined")
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
            f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        # No numeric "fit" here — these are illustrative same-profile names, and a two-digit score
        # would read as real precision the app can't back for this (unscored) list.
        candidates = [
            ("Royce Investment Partners", "Small-cap value"),
            ("Kennedy Capital Management", "Small-cap growth"),
            ("Conestoga Capital Advisors", "Small-cap growth"),
            ("Robotti & Company", "Deep value / special situations"),
        ]
        for name, mandate in candidates:
            ui.label(f"• {name} — {mandate}").style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def _render_activity_responses(state):
    # No email inbox integration exists in this app — status here is
    # self-reported by the user, not auto-detected from a reply. The one
    # genuinely automatable piece is real: uploading the actual model file
    # received recalculates the consensus input for that analyst.
    if not state.get("models_request_sent"):
        return
    _panel_head("Activity & responses — model requests")
    ui.label("You mark status yourself as replies come in — this app has no email inbox connected, so nothing "
             "here is auto-detected.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

    sent_names = state.get("models_sent_names", [])
    tracked_analysts = [a for a in CA() if a["name"] in sent_names] or [a for a in CA() if a.get("pt") is None]
    for a in tracked_analysts:
        _render_activity_row(state, a)


def _render_activity_row(state, a):
    status_key = f"activity_status_{a['name']}"
    with ui.row().classes("w-full items-start justify-between gap-4"):
        with ui.column().classes("flex-[2] gap-0"):
            ui.label(f"{a['name']} — {a['firm']}").classes("font-bold").style(f"color:{COLORS['text_body']};font-size:var(--fs-base);")
            status_sel = ui.select(["Sent", "Replied", "Model Received"], value=state.get(status_key, "Sent")).props("outlined dense").classes("w-full")
        ui.label(f"Sent {state.get('models_request_sent_date','')}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

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
                ).props("outlined autogrow").classes("w-full")

                def save_notes(notes_key=notes_key, notes=notes):
                    state[notes_key] = notes.value
                    _save_state(state)

                notes.on("blur", save_notes)

            elif status_sel.value == "Model Received":
                ui.label("Upload the file you actually received (Metric,Value CSV — e.g. Revenue,24.8 / EPS,0.06). "
                         "This app can't intelligently parse an arbitrary analyst spreadsheet format, so it needs "
                         "a simple structure to read reliably.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                result_area = ui.column().classes("w-full")

                async def handle_upload(e, a=a, result_area=result_area):
                    result_area.clear()
                    try:
                        content = await e.file.text()
                        rows = list(csv.reader(io.StringIO(content)))
                        new_vals = {r[0].strip(): r[1].strip() for r in rows if len(r) >= 2}
                        # The analyst's ACTUAL last committed figure, if any — never a hardcoded placeholder
                        # (this used to show a literal $24.1M "old model" for every analyst, a fabricated
                        # baseline inside a real workflow). Omit the OLD card entirely when none is on file.
                        old_rev = state.get(f"committed_model_{a['name']}")
                        _rev = new_vals.get("Revenue")
                        new_rev = float(_rev) if _rev else float(old_rev or 0)
                        with result_area:
                            with ui.row().classes("w-full gap-3"):
                                if old_rev is not None:
                                    ui.html(
                                        f"<div style='background:#EEF2F7;border-radius:8px;padding:8px 12px;'>"
                                        f"<span style='font-size:var(--fs-xs);color:#64748B;'>OLD MODEL</span><br>"
                                        f"<b style='color:#1E293B;'>Revenue: ${old_rev}M</b></div>"
                                    )
                                ui.html(
                                    f"<div style='background:#E9F6EF;border-radius:8px;padding:8px 12px;'>"
                                    f"<span style='font-size:var(--fs-xs);color:#64748B;'>NEW MODEL</span><br>"
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
                                     "and try again.").style("color:#B91C1C;font-size:var(--fs-sm);")

                ui.upload(on_upload=handle_upload, auto_upload=True).props("accept=.csv").classes("w-full")

    status_sel.on_value_change(render_detail)
    render_detail()


def _last_note_for_fund(fund):
    """Most recent logged meeting-note for a fund, or None."""
    try:
        from core.investor_scoring import load_meeting_log
        rows = [r for r in (load_meeting_log() or []) if r.get("Fund") == fund and r.get("Notes")]
        rows.sort(key=lambda r: r.get("Date", ""), reverse=True)
        return rows[0] if rows else None
    except Exception:
        return None


def _brief_talking_points(inst, full):
    """Meeting talking points built ONLY from this fund's real tracked fields — the
    13F direction, peer overlap, call-listening, engagement. No fabricated financial
    claims (that was the old hardcoded-per-ticker approach)."""
    points = []
    d = str((full or {}).get("Direction", "")).lower()
    if d == "new":
        points.append("New position this quarter — open with what changed in their thesis to initiate now.")
    elif d == "adding":
        points.append("Adding to the position — reinforce the thesis and ask what would make them size up further.")
    elif d == "trimming":
        points.append("Trimming — find out what changed and address the concern before it becomes an exit.")
    elif d == "exited":
        points.append("Recently exited — a win-back conversation: ask what would bring them back.")
    peers = (full or {}).get("Peer_Holdings") or inst.get("Peer_Holdings")
    if peers:
        points.append(f"Owns {', '.join(peers)} — draw the direct comparison to those peers' positioning.")
    if inst.get("Call_Listener") and inst.get("Listen_Duration"):
        points.append(f"Listened to the last earnings call ({inst['Listen_Duration']}) — reference the moments they engaged with.")
    if (inst.get("Engagement_Score") or 0) >= 80:
        points.append(f"Top-tier engagement ({inst['Engagement_Score']}/100) — a "
                      f"{'defend' if inst.get('USIO_Holder') else 'high-priority conversion'} meeting, not a cold intro.")
    if not points:
        points.append("No prior signal on file — treat as discovery: confirm mandate fit before going deep on the thesis.")
    return points


def _render_investor_brief(inst, full, nm):
    """A full investor brief from REAL tracked fields only — 13F position, peer
    overlap, engagement breakdown, behavioral signals, contact, last note. Anything
    not on file is omitted rather than invented."""
    C = COLORS

    def fact(label, value, vcolor=None):
        if value in (None, "", "—"):
            return
        with ui.row().classes("items-baseline no-wrap").style("gap:8px;margin-top:2px;"):
            ui.label(label).style(f"color:{C['text_muted']};font-size:var(--fs-xs);"
                                  f"text-transform:uppercase;letter-spacing:.04em;white-space:nowrap;min-width:78px;")
            ui.label(str(value)).style(f"color:{vcolor or C['text_body']};font-size:var(--fs-sm);font-weight:600;")

    # 1. 13F position — value, weight, conviction, direction, tenure
    if full and full.get("Position_Value"):
        pos = f"${full['Position_Value']/1e6:,.1f}M"
        if full.get("Book_Pct"):
            # Book_Pct is ALREADY a percentage (core.targets: value / book_total * 100) — the same
            # convention markets_page and the conviction tiers use. Do NOT multiply by 100 again;
            # that was showing a 0.75%-of-book position as "75.00% of their 13F book".
            pos += f" · {full['Book_Pct']:.2f}% of their 13F book"
        if full.get("AUM"):
            pos += f" · {full['AUM']} AUM"
        fact("Position", pos)
        sig = []
        if full.get("Conviction"):
            sig.append(f"{full['Conviction']} conviction")
        if full.get("Direction"):
            dtxt = str(full["Direction"]).title()
            nc = full.get("Net_Change_Shares")
            if nc:
                dtxt += f" ({nc:+,} sh)"
            sig.append(dtxt)
        dlow = str(full.get("Direction", "")).lower()
        scolor = C["danger"] if dlow in ("trimming", "exited") else (C["success"] if dlow in ("new", "adding") else None)
        if sig:
            fact("Signal", " · ".join(sig), scolor)
        if full.get("Held_Since_At_Least"):
            fact("Held since", full["Held_Since_At_Least"])
    else:
        fact("Position", "No 13F position on file — prospect / peer-owner")

    # Addressable size — ONLY for a peer-owning prospect (a holder already owns you, so
    # it's meaningless there). The takeaway is the PRIZE: if they took a position the size
    # of the capital they already hold in your comps, how big a USIO holder would that
    # make them (% of the company). Days-to-build is a feasibility caveat, shown only when
    # the stock is too thin to accumulate it quickly. Display-only, not a prediction.
    _hold = bool((full or {}).get("USIO_Holder"))
    _addr_val = (full or {}).get("peer_value")
    if not _hold and _addr_val:
        _shares = (C().get("financials", {}).get("shares_out_m") or 0) * 1e6
        _ar = market_data.addressable_readout(
            _addr_val, market_data.get_snapshot(CT("ticker"), refresh_if_stale=False),
            shares_out=_shares or None)
        if _ar:
            _pct = f" ≈ {_ar['pct_of_company'] * 100:.1f}% of {CT('ticker')}" if _ar.get("pct_of_company") else ""
            _dd = _ar.get("days_to_build")
            _feas = f" · ~{_dd:,.0f} days of ADV to build (thin)" if _dd and _dd >= 5 else ""
            fact("Potential size", f"${_ar['value'] / 1e6:,.2f}M in your comps{_pct}{_feas}")

    peers = (full or {}).get("Peer_Holdings") or inst.get("Peer_Holdings")
    if peers:
        fact("Also owns", ", ".join(peers))
    if inst.get("Action"):
        fact("Why now", inst["Action"], C["accent"])
    if inst.get("Call_Listener") and inst.get("Listen_Duration"):
        fact("Earnings call", f"Listened to the last call ({inst['Listen_Duration']})")
    if inst.get("IR_Visits_30d"):
        fact("IR site", f"{inst['IR_Visits_30d']} visit(s) in 30d · last {inst.get('Last_Visit', '—')}")
    if inst.get("Ownership_Style"):
        fact("Style", inst["Ownership_Style"])
    if inst.get("Metro"):
        fact("Location", inst["Metro"])
    cn = inst.get("Contact_Name")
    if cn and cn != "Contact":
        fact("Contact", cn + (f", {inst['Contact_Title']}" if inst.get("Contact_Title") else ""))
        if inst.get("Contact_Phone"):
            fact("Phone", inst["Contact_Phone"])

    # 2. Engagement score, broken down so the number is explainable
    bd = inst.get("Score_Breakdown")
    if bd:
        with ui.element("div").style(
                f"background:{C['surface_hover_bg']};border:1px solid {C['border']};"
                f"border-radius:8px;padding:6px 10px;margin-top:8px;"):
            ui.label(f"Engagement {inst.get('Engagement_Score', '—')}/100").style(
                f"color:{C['text_heading']};font-size:var(--fs-sm);font-weight:700;")
            ui.label(" · ".join(f"{c} {p if p is not None else 0}/{m}" for (c, p, m) in bd)).style(
                f"color:{C['text_muted']};font-size:var(--fs-xs);line-height:1.4;")

    # 3. Talking points — full-width divider under the header, matching the Peer Watch inner-card
    # treatment (title · rule · list) for cross-surface consistency.
    ui.label("Talking points").style(
        f"color:{C['text_heading']};font-size:var(--fs-sm);font-weight:700;margin-top:8px;width:100%;"
        f"border-bottom:1px solid {C['border']};padding-bottom:5px;margin-bottom:6px;")
    for p in _brief_talking_points(inst, full):
        ui.label(f"•  {p}").style(f"color:{C['text_secondary']};font-size:var(--fs-sm);line-height:1.45;")

    # 4. Last note on the fund
    ln = _last_note_for_fund(nm)
    if ln:
        with ui.element("div").style(
                f"background:{C['surface_hover_bg']};border:1px solid {C['border']};"
                f"border-radius:8px;padding:6px 10px;margin-top:8px;"):
            ui.label(f"Last note · {ln.get('Date', '')}").style(f"color:{C['text_muted']};font-size:var(--fs-xs);")
            ui.label(ln.get("Notes", "")).style(f"color:{C['text_body']};font-size:var(--fs-sm);")


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
    _panel_head("Investor pipeline — strongest signal")
    from core.investor_scoring import load_meeting_log, save_meeting_log, top_engagement_targets
    targets = top_engagement_targets(limit=5)
    if not targets:
        ui.label("No open signals right now — every tracked institution has a recent logged interaction. "
                 "Check back once one ages out, or a new signal moves a fund's score.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-base);"
        )
    contacts = get_institution_contacts()
    # The richer 13F record (position value, % of book, conviction, direction, peer
    # overlap) lives in targets_as_institutions, not the engagement row — join on the
    # fund so the brief can show the full picture. Loaded once, keyed by upper name.
    try:
        from core import targets as _tg
        from config.client_config import get_active_client_id as _gac
        _full_by_fund = {(r.get("Fund") or "").upper(): r
                         for r in (_tg.targets_as_institutions(client_id=_gac()) or [])}
    except Exception:
        _full_by_fund = {}
    for inst in targets:
        nm = inst["Fund"]
        score = inst["Engagement_Score"]
        hld = "Holder" if inst["USIO_Holder"] else "Non-holder"
        nt = inst.get("Action", "—")
        info = contacts.get(nm, {"name": "Contact", "email": ""})
        full = _full_by_fund.get((nm or "").upper())

        # Defined before the card so the Details button — now INSIDE the card,
        # in its own bottom action row — can bind to it.
        def open_detail(nm=nm, info=info, inst=inst, full=full, hld=hld, score=score):
            with ui.dialog() as d, ui.card().style(
                    f"background:{COLORS['surface_bg']};min-width:min(94vw,480px);"
                    f"max-height:88vh;overflow:auto;"):
                ui.label(f"{pretty_name(nm)} — {hld} · Engagement {score}/100").classes("font-bold") \
                    .style(f"color:{COLORS['text_heading']};font-size:var(--fs-md);")
                # Full investor brief (real tracked fields only).
                _render_investor_brief(inst, full, nm)
                _mailto(info.get("email", ""), f"{CT('ticker')} — Following up, {nm}", "Hi,\n\n", f"Email {info.get('name','Contact')}")

                ui.separator().style("margin:6px 0;")
                # Capture what you learned + schedule the next touch — recorded to the fund's Meeting
                # Log (the investor CRM interaction history) and the activity feed; a follow-up date
                # also becomes a scheduled meeting (shows in the Meeting Hub and the Mobile "Your
                # meetings" hero). No more dead-ending at "sent or nothing".
                note_in = ui.textarea("Add a note — what did you learn or decide?") \
                    .props("autogrow dense outlined").classes("w-full")
                fu_in = ui.input("Schedule a follow-up (optional)") \
                    .props("type=date dense outlined").classes("w-full")

                def _log_meeting(entry):
                    log = load_meeting_log()
                    log.append(entry)
                    save_meeting_log(log)

                def _base_entry():
                    return {"Fund": nm, "Date": datetime.now().strftime("%Y-%m-%d"),
                            "Attendees": info.get("name", ""), "Outcome": "No clear signal",
                            "Logged By": CI().get("name") or "IR Team", "Source": "Today Pipeline"}

                def save_to_crm(nm=nm, info=info, note_in=note_in, fu_in=fu_in):
                    import uuid
                    from core import db
                    did = []
                    note = (note_in.value or "").strip()
                    if note:
                        _log_meeting({**_base_entry(), "Type": "Note (Today Pipeline)", "Notes": note})
                        activity_log.log_event("meeting_note", entity=nm, launched_from="Today · Investor Pipeline")
                        # Wire the note onto the CONTACT record too — the note text lands on the
                        # person's own timeline (House Contacts), client-scoped, not just the fund's
                        # meeting log. Only for a real, resolved contact — never the "Contact"
                        # placeholder.
                        if info.get("name") and info["name"] != "Contact":
                            try:
                                from core import contacts as _contacts
                                _contacts.add_contact_note(info["name"], nm, note, source="Today Pipeline",
                                                           by=(CI().get("name") or "IR Team"),
                                                           email=(info.get("email") or None))
                            except Exception:
                                pass
                        did.append("note")
                    if (fu_in.value or "").strip():
                        sched = db.load_json("scheduled_meetings.json", []) or []
                        sched.append({"id": str(uuid.uuid4()), "Contact": info.get("name", ""),
                                      "Firm": nm, "Side": "Buy-side", "Date": fu_in.value, "Time": "",
                                      "Type": "Follow-up", "Topic": note or "Follow up on engagement signal",
                                      "Status": "Planned", "Priority": "Medium"})
                        db.save_json("scheduled_meetings.json", sched)
                        _log_meeting({**_base_entry(), "Type": "Follow-up scheduled (Today Pipeline)",
                                      "Notes": f"Follow-up set for {fu_in.value}" + (f": {note}" if note else "")})
                        activity_log.log_event("followup_scheduled", entity=nm, launched_from="Today · Investor Pipeline")
                        did.append(f"follow-up {fu_in.value}")
                    if not did:
                        ui.notify("Add a note or pick a follow-up date first.", type="warning")
                        return
                    ui.notify(f"Saved {' + '.join(did)} for {pretty_name(nm)} to the CRM.", type="positive")
                    d.close()
                    nav.go_to("Today")

                def mark_sent(nm=nm, info=info):
                    _log_meeting({**_base_entry(), "Type": "Email outreach (Today's Pipeline)",
                                  "Notes": "Quick outreach logged from Today's Investor Pipeline signal."})
                    activity_log.log_event("email_sent", entity=nm, launched_from="Today · Investor Pipeline")
                    ui.notify(f"Logged outreach to {nm} — clearing this card from the pipeline.")
                    d.close()
                    nav.go_to("Today")

                with ui.row().classes("w-full justify-end gap-2 items-center").style("margin-top:6px;"):
                    ui.button("Close", on_click=d.close).props("flat")
                    ui.button("Mark as sent", on_click=mark_sent).props("flat")
                    ui.button("Save note / follow-up", on_click=save_to_crm).props("color=primary")
            d.open()

        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label(pretty_name(nm)).classes("font-bold").style(f"color:{COLORS['accent_light']};font-size:var(--fs-base);")
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
    if role_can_view(ui_context.current_role(), "Targeting"):
        ui.button("Open Full Investor Pipeline →",
                  on_click=lambda: nav.go_to("Targeting", "Target Database")).props("color=primary")
    else:
        ui.label("The full pipeline lives in Investor Targeting — your current role doesn't have access to "
                 "that page.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")


def _render_earnings_readiness(days):
    from page_modules_nicegui.earnings_page import STAGES
    _panel_head("Earnings readiness")   # countdown lives in the card, not here

    # Earnings date/time from config, not a hardcoded literal.
    edate = CE().get("earnings_date", "")
    quarter = (CE().get("current_quarter", "") or "").strip()
    try:
        _dt = datetime.strptime(edate, "%Y-%m-%d")
        date_lbl = f"{_dt.strftime('%b')} {_dt.day}, {_dt.year}"
    except ValueError:
        date_lbl = edate or "date TBD"
    time_lbl = CE().get("earnings_time") or CE().get("call_time") or "4:30 PM ET"

    # One clear, LABELED header: what call, when, how far out — no repeated "30 days", and the date
    # is explicitly the earnings call (not a bare, ambiguous date).
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_hover_bg']};border:1px solid {COLORS['accent']};"):
        with ui.row().classes("w-full justify-between items-baseline"):
            ui.label(f"{quarter + ' ' if quarter else ''}earnings call".strip().capitalize()) \
                .classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:var(--fs-md);")
            ui.label(f"in {days} days").style(f"color:{COLORS['accent_light']};font-size:var(--fs-base);font-weight:700;")
        ui.label(f"{date_lbl}  ·  {time_lbl}").style(f"color:{COLORS['accent_light2']};font-size:var(--fs-sm);")

    # The stage-by-stage review is only "on the clock" in the final two weeks before earnings (the last
    # two weeks of the quarter). Outside that window, don't score it — keep the countdown above, but drop
    # the completion count + the checklist pressure and say when the clock starts. Same T-14 rule as
    # Today's Focus item 3 (see _talking_points).
    if days is not None and days > 14:
        ui.label(f"Script review opens in the final two weeks before earnings — the clock starts in "
                 f"{days - 14} day(s). Nothing to work yet.").classes("t-sec").style(
            f"color:{COLORS['text_muted']};margin-top:8px;line-height:1.5;")
        ui.button("Preview Script Generation →", icon="edit_note",
                  on_click=lambda: nav.go_to("Earnings", "Script Generation")).props("outline").classes(
                  "w-full").style("margin-top:8px;")
        return

    # The 5-stage Script Generation workflow — ALWAYS show all five, NUMBERED, so it's clear these
    # are the five stages whether or not the script has been started (the old version hid them
    # entirely on an un-started script, so the "5 stages" weren't evident). Real status from
    # script_workflow_state.json — nothing hardcoded.
    stages = (db.load_json("script_workflow_state.json", None) or {}).get("stages", {})
    _status = {
        "complete": ("Complete", COLORS["success"], "✓"),
        "active":   ("In progress", COLORS["warning"], "●"),
        "pending":  ("Not started", COLORS["text_muted"], "○"),
    }
    done = sum(1 for s in STAGES if stages.get(s["id"], {}).get("status") == "complete")
    total = len(STAGES)
    ui.label(f"Script — {done} of {total} review stages complete").classes("t-sec").style("margin-top:8px;")
    for i, s in enumerate(STAGES, 1):
        st = stages.get(s["id"], {}).get("status", "pending")
        lbl, clr, glyph = _status.get(st, _status["pending"])
        with ui.card().classes("w-full list-tile"):
          with ui.row().classes("w-full justify-between items-center no-wrap"):
            ui.label(f"{i}.  {s['name']}").classes("t-body")
            ui.label(f"{glyph} {lbl}").style(f"color:{clr};font-size:var(--fs-sm);font-weight:600;")

    # A clear, purposeful CTA (not a vague "Open Script Generation" link): this is the action that
    # advances the stages above. Primary/full-width when there's work to do; opens the right tab.
    _cta = "Start the script →" if not stages else ("Finish the script →" if done < total else "Review the script →")
    ui.button(_cta, icon="edit_note", on_click=lambda: nav.go_to("Earnings", "Script Generation")) \
        .props("color=primary" if done < total else "outline").classes("w-full").style("margin-top:8px;")


# ── Analyst-vs-guidance alignment ──────────────────────────────────────────────
# Status → (colour token, glyph, word). "above"/"below" = the analyst's estimate is
# out of line with the company's OWN guidance (a setup the IR team must manage);
# "inline" = within tolerance; "none" = no model on file (NOT fabricated — many
# small-cap analysts publish a rating/PT but no full model).
_ALIGN_PILL = {
    "above":  ("warning", "▲", "above"),   # ▲ analyst above our guide
    "below":  ("danger",  "▼", "below"),   # ▼ analyst below our guide
    "inline": ("success", "●", "in line"), # ● within tolerance
    "none":   ("text_muted2", "–", "no model"),  # –
}


def _alignment_rows(analysts, period_guidance, period_estimates, period):
    """Pure classifier (no I/O — unit-tested): for each analyst, compare their Revenue &
    EPS estimate for `period` against the company's own guidance and label each metric
    'above' / 'below' / 'inline' / 'none'. Rank OUT-OF-LINE analysts first (largest gap
    first) so the ones who disagree with guidance are never buried. Tolerance: revenue
    within 2% of guide is in line; EPS within max($0.01, 3%) (EPS guides can round to $0)."""
    guide = (period_guidance or {}).get(period) or {}
    g_rev, g_eps = guide.get("Revenue Est ($M)"), guide.get("EPS Est")
    firm_est = (period_estimates or {}).get(period) or {}

    def _classify(est, gv, rel, floor):
        if est is None or gv is None:
            return "none", None
        diff = est - gv
        band = max(floor, abs(gv) * rel)
        pct = (diff / gv) if gv else None
        if abs(diff) <= band:
            return "inline", pct
        return ("above" if diff > 0 else "below"), pct

    rows = []
    for a in analysts:
        firm = a.get("firm", "")
        est = firm_est.get(firm) or {}
        rs, rp = _classify(est.get("Revenue Est ($M)"), g_rev, 0.02, 0.0)
        es, ep = _classify(est.get("EPS Est"), g_eps, 0.03, 0.01)
        out_of_line = rs in ("above", "below") or es in ("above", "below")
        rows.append({
            "firm": firm, "name": a.get("name", ""), "pt": a.get("pt"),
            "rating": a.get("rating") or "—", "covering": a.get("covering", True),
            "rev_status": rs, "rev_pct": rp, "eps_status": es, "eps_pct": ep,
            "out_of_line": out_of_line, "has_model": (rs != "none" or es != "none"),
            "divergence": max(abs(rp or 0), abs(ep or 0)) if out_of_line else 0.0,
        })
    # out-of-line first (biggest divergence), then modeled & in line, then no-model.
    rows.sort(key=lambda r: (0 if r["out_of_line"] else (1 if r["has_model"] else 2), -r["divergence"]))
    return rows, {"period": period, "guide_rev": g_rev, "guide_eps": g_eps,
                  "has_guidance": (g_rev is not None or g_eps is not None)}


def _analyst_alignment():
    """Live wrapper: classify every analyst's estimate against the company's own
    guidance for the CURRENT REPORTING QUARTER — the forward quarter analysts model
    now (CE()['current_quarter'], e.g. 'Q3 2026' → 'Q3 2026E'), NOT the full year.
    A guidance-vs-estimate comparison is only meaningful on a forward period, and the
    header + every card must reference the SAME period the rest of Today uses."""
    from core import consensus, guidance_engine
    c = consensus.get_consensus(None)
    pg = c.get("period_guidance") or {}
    cq = (CE().get("current_quarter") or "").strip()
    period = f"{cq}E" if cq else ""
    if period not in pg:
        # Fall back to any quarter on file, then the guided FY (prior behavior).
        period = (next((p for p in pg if str(p)[:1] == "Q"), None)
                  or (guidance_engine.reporting_fy_label() if guidance_engine.reporting_fy_label() in pg else None)
                  or next(iter(pg), None))
    return _alignment_rows(CA(), pg, c.get("period_estimates") or {}, period)


def _render_analyst_coverage():
    _panel_head("Analyst coverage")
    # Real analyst registry (config.client_config.CA), not a hardcoded roster. Each card
    # ranks and flags the analyst by whether their Rev & EPS estimates sit IN LINE with
    # our own guidance — out-of-line analysts float to the top and stay visible.
    rows, meta = _analyst_alignment()
    if meta["has_guidance"]:
        gp = []
        if meta["guide_rev"] is not None:
            gp.append(f"Rev ${meta['guide_rev']:.1f}M")
        if meta["guide_eps"] is not None:
            gp.append(f"EPS ${meta['guide_eps']:.2f}")
        ui.label(f"vs {meta['period']} guidance ({' · '.join(gp)}) — out-of-line first").classes(
            "t-eyebrow").style(f"color:{COLORS['text_muted']};margin-top:-2px;").tooltip(
            "In line = estimate within tolerance of our guidance (rev 2% / EPS 3%). "
            "Above / Below = the analyst is out of line with what we've guided.")

    def _pill(label, status, pct):
        tok, glyph, word = _ALIGN_PILL[status]
        clr = COLORS[tok]
        txt = f"{label} {glyph} {word}"
        if pct is not None and status in ("above", "below"):
            txt = f"{label} {glyph} {word} {abs(pct) * 100:.0f}%"
        ui.label(txt).style(
            f"font-size:var(--fs-2xs);font-weight:700;letter-spacing:.02em;color:{clr};"
            f"border:1px solid {clr};border-radius:9px;padding:1px 7px;white-space:nowrap;")

    ool_rows = [r for r in rows if r["out_of_line"]]
    rest = [r for r in rows if not r["out_of_line"]]
    container = ui.column().classes("w-full gap-2")
    expanded = {"value": False}

    def render_list():
        container.clear()
        fill = rest if expanded["value"] else rest[:max(0, 3 - len(ool_rows))]
        visible = ool_rows + fill
        hidden_ct = len(rest) - len(fill)
        with container:
            for r in visible:
                pt, rating, covering = r["pt"], r["rating"], r["covering"]
                if pt is not None:
                    pt_str, clr = f"${pt:.2f}", (COLORS["success"] if rating == "Buy" else COLORS["warning"])
                elif covering:
                    pt_str, clr = "No PT", COLORS["warning"]
                else:
                    pt_str, clr = "—", COLORS["text_muted"]
                # Out-of-line cards get a soft amber left-rail so they read as "attention".
                rail = f"border-left:3px solid {COLORS['warning']};" if r["out_of_line"] else ""
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};{rail}"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(r["firm"]).classes("font-bold").style(
                            f"color:{COLORS['text_heading']};font-size:var(--fs-base);")
                        ui.label(pt_str).classes("font-bold").style(f"color:{clr};")
                    ui.label(f"{r['name']} · {rating}").classes("t-meta")
                    if meta["has_guidance"]:
                        with ui.row().classes("items-center").style("gap:5px;flex-wrap:wrap;"):
                            _pill("Rev", r["rev_status"], r["rev_pct"])
                            _pill("EPS", r["eps_status"], r["eps_pct"])
                    else:
                        note = "model not on file" if covering else "not covering"
                        ui.label(note).classes("t-meta").style(f"color:{COLORS['text_muted']};")
                    with _signal_actions():
                        # Deep-link straight to Consensus / Guidance with this analyst
                        # highlighted. Pass the tab explicitly (not just the highlight)
                        # so the sidebar's active-tab highlight matches the tab that
                        # opens; the `e=None` swallows the click event NiceGUI passes so
                        # it can't clobber the captured `firm`.
                        ui.button("Consensus →", on_click=lambda e=None, firm=r["firm"]: nav.go_to(
                            "Markets", "Consensus / Guidance", highlight_analyst=firm)).props("flat dense size=sm")

            if hidden_ct > 0:
                ui.button(f"+ Load {hidden_ct} more", on_click=toggle).props("flat")
            elif expanded["value"] and len(rest) > max(0, 3 - len(ool_rows)):
                ui.button("Show fewer ↑", on_click=toggle).props("flat")

    def toggle():
        expanded["value"] = not expanded["value"]
        render_list()

    render_list()


def _top_story_data():
    """(top_item, is_own, peer_list) for the day's single most important headline,
    or (None, False, []). The client's OWN news wins when there is any (a microcap
    often has none); otherwise the freshest peer/competitor item. Folded into the
    Today's Focus card as the final talking point (was the 'Today's top story' card),
    with a pointer down to the full peer-news feed so that feature isn't lost."""
    from core import news_feed
    ticker = CT("ticker")
    own = news_feed.recent(ticker=ticker, limit=1)
    peer = [i for i in news_feed.recent(limit=8) if i.get("ticker") != ticker]
    top = own[0] if own else (peer[0] if peer else None)
    return top, bool(own), peer


def _collapsible_head(title, start_open=True):
    """A section-head with an expand/collapse chevron. Returns the body column to fill; its
    visibility toggles client-side (no re-fetch), so long front-page sections can be folded away."""
    # A holder for the chevron so it can render flush-right inside the header band.
    btn_holder = {}

    def _chevron():
        # White ring so the button stands out on the grey band (not near-white on near-white).
        btn_holder["btn"] = ui.button(icon="expand_less" if start_open else "expand_more").props(
            "flat dense round size=sm").style(
            f"color:{COLORS['text_secondary']};border:1.5px solid {COLORS['text_muted2']};"
            f"background:#FFFFFF;").tooltip("Collapse / expand this section")

    _panel_head(title, right=_chevron)
    btn = btn_holder["btn"]
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
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            return

        n = insider_feed.net_open_market()
        if n["buy_shares"] or n["sell_shares"]:
            tone_clr = COLORS["success"] if n["net_shares"] > 0 else COLORS["danger"] if n["net_shares"] < 0 else COLORS["text_muted"]
            tone = "net buying" if n["net_shares"] > 0 else "net selling" if n["net_shares"] < 0 else "flat"
            ui.label(f"Open-market: {n['buy_shares']:,.0f} bought vs {n['sell_shares']:,.0f} sold — {tone}").style(
                f"color:{tone_clr};font-size:var(--fs-sm);font-weight:600;")
        else:
            ui.label("No open-market buys/sells on file — recent Form 4s are routine grants/exercises.").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")

        _tone = {"P": COLORS["success"], "S": COLORS["danger"]}
        for t in txns[:6]:
            col = _tone.get(t.get("code"), COLORS["text_muted"])
            # Bullet inline-left, text flexing to its right — no-wrap + items-start so
            # the glyph sits on the first text line and wrapped lines hang under the text,
            # not under the bullet (previously the row wrapped and the dot floated above).
            with ui.row().classes("w-full items-start no-wrap").style("gap:8px;"):
                ui.label(insider_feed.glyph(t)).style(
                    f"color:{col};font-weight:800;font-size:var(--fs-sm);line-height:1.45;flex-shrink:0;")
                ui.label(insider_feed.describe(t)).classes("flex-1").style(
                    f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);line-height:1.45;")


def _render_peer_watch():
    """Daily peer monitor on the front page — notable price moves, recent SEC
    filings, and a rolling 7-day news window across the segmented peer group
    (core.peer_watch + core.news_feed, cache-only reads)."""
    from core import news_feed, peer_watch
    s = peer_watch.summary()

    body = _collapsible_head("Peer watch")
    with body:
        ui.label("Daily monitor of the segmented peer group — price moves and SEC filings.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")

        # Consistent inner-card header: bold title + a full-width divider rule under it, so every
        # sub-card (moves · filings · headlines · peer news) reads the same way.
        def _inner_head(text):
            ui.label(text).classes("font-bold").style(
                f"color:{COLORS['text_body']};font-size:var(--fs-sm);width:100%;"
                f"border-bottom:1px solid {COLORS['border']};padding-bottom:5px;margin-bottom:6px;")

        movers = s["movers"] or s["all_movers"][:4]
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
            if not movers:
                ui.label("Peer market data refreshing — check back shortly.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            else:
                _inner_head("Today's moves")
                for m in movers[:5]:
                    clr = "#15803D" if (m["pct"] or 0) >= 0 else "#B91C1C"
                    tag = ("  ◆ closest analog" if m.get("closest_analog")
                           else ("  · reference" if m.get("tier") == "reference"
                                 else ("  · you" if m.get("is_client") else "")))
                    with ui.row().classes("w-full items-center justify-between").style("padding:1px 0;"):
                        with ui.row().classes("items-baseline gap-1").style("min-width:0;"):
                            ui.label(m["ticker"]).classes("font-bold").style(
                                f"color:{COLORS['text_body']};font-size:var(--fs-base);")
                            ui.label(f"{m.get('segment', '') or ''}{tag}").style(
                                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")
                        ui.label(f"{m['pct']:+.1f}%").classes("font-bold").style(f"color:{clr};font-size:var(--fs-base);")

        if s["filings"]:
            with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
                _inner_head("Recent peer SEC filings")
                for f in s["filings"][:5]:
                    who = f"{f['ticker']}" + (" (you)" if f.get("is_client") else "")
                    def _filing_line():
                        with ui.row().classes("w-full items-center gap-2").style("padding:1px 0;"):
                            ui.label(f["date"][5:]).style(f"color:{COLORS['accent']};font-size:var(--fs-xs);width:42px;")
                            ui.label(f"{who} · {f['form']}").style(
                                f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);")
                    # Link only when a real URL is present — target=None crashes the link component.
                    if f.get("url"):
                        with ui.link(target=f["url"], new_tab=True).style("text-decoration:none;"):
                            _filing_line()
                    else:
                        _filing_line()

        # Client's OWN headlines, distinct from peer news. A microcap is often quiet — an empty state
        # says so (itself IR-relevant) rather than hiding the card.
        _tk = CT("ticker")
        own = news_feed.recent(ticker=_tk, limit=6)
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
            _inner_head(f"{_tk} headlines · rolling 7 days")
            if own:
                for n in own:
                    with ui.link(target=n.get("url") or "#", new_tab=True).style("text-decoration:none;"):
                        with ui.column().classes("gap-0").style("padding:2px 0;"):
                            ui.label(f"{n.get('provider', '')} · {(n.get('pub') or '')[:10]}").style(
                                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")
                            ui.label(n["title"]).style(
                                f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);line-height:1.35;")
            else:
                ui.label(f"No {_tk} headlines in the last 7 days — the feed is watching.").style(
                    f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;")

        # Anchor for the "More peer news ↓" jump from the top-story card.
        ui.html('<div id="peer-news-anchor"></div>')
        peer_news = [i for i in news_feed.recent(limit=12) if i.get("ticker") != _tk][:6]
        if peer_news:
            with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;"):
                _inner_head("Peer & competitor news · rolling 7 days")
                for n in peer_news:
                    with ui.link(target=n.get("url") or "#", new_tab=True).style("text-decoration:none;"):
                        with ui.column().classes("gap-0").style("padding:2px 0;"):
                            ui.label(f"{n['ticker']} · {n.get('provider', '')} · {(n.get('pub') or '')[:10]}").style(
                                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);")
                            ui.label(n["title"]).style(
                                f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);line-height:1.35;")

        ui.label("Prices & news via Yahoo (≤60-min delay); filings via SEC EDGAR. A licensed feed would add breaking "
                 "speed and deeper M&A/press-wire coverage.").style(
            f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);margin-top:2px;")
