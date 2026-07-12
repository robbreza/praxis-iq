"""
page_modules_nicegui/investors_page.py — Investors (buy-side intelligence,
NDR planning, meeting hub, target database), NiceGUI version.

This is the largest, most complex page in the original app (~5,000 lines of
app.py's "Investors" section). Ported here with the same 4-tab structure and
the same information architecture, but with these documented simplifications
(nothing silently dropped — everything below is still reachable in app.py):

- Big Picture synthesis (including the recency cross-check and the
  most-visited-city contrast warning), the pre/post-earnings mode toggle,
  the engagement funnel, institution cards, a per-institution meeting log
  with the 45-day repeat-meeting alert (including the +20 ephemeral score
  boost and warning when a repeat meeting is logged, and the global
  "Repeat Meeting Alerts" banner above the full institution list), the
  full Buy-Side filter set (tier, holder status, min score, Turnover
  Style, Metro, Digital Intent Score, Active/Passive ownership), and the
  dynamic pre-earnings outreach generator are all ported with full
  fidelity. NOT ported: the post-earnings "Update Intelligence Data" panel
  (CSV upload for Q2 Chorus Call listeners / IR visitor surge, plus a
  manual analyst-upgrade log form) — post-earnings scoring still runs, it
  just falls back to the Q1 call-listener flag instead of an uploaded Q2
  list until that panel is ported. Still available in app.py.
- Peer Cross-Targeting is rebuilt as a real Peer Universe manager: a
  persisted peer list (core.db, key "peer_universe.csv" — the same key
  config.client_config.CP() already reads, so a peer added/edited here is
  immediately available in outreach-draft valuation comparisons too) with
  add/remove/quick-add, plus a cross-targeting analysis with a
  peer multi-select AND a working minimum-AUM filter. Note: app.py's
  original min-AUM selectbox was computed but never actually applied to
  the results (a no-op left in the original) — this port applies it for
  real. Placed in the Target Database tab here (app.py nests it inside
  Buy-Side Intelligence) since it's a targeting/prospecting tool, which
  is where a user would look for it alongside the prospect search.
- Meeting Hub is ported with full fidelity for its 3 core sub-tabs (Upcoming
  Meetings, Schedule Meeting, Post-Meeting Notes), including a real Claude
  API call to structure raw meeting notes (same prompt/model as the original
  structure_notes_with_ai, now reading the key via core.security instead of
  a raw environment-variable read), with the same rule-based fallback if the
  API call fails. NOT yet ported: the "Current Full Meeting Schedule" table
  (a sortable dataframe of every scheduled meeting, not just upcoming ones)
  and its "⬇️ Export schedule as CSV" / "⬇️ Export meeting notes CSV"
  download buttons, and the Q&A Theme Tracker (a 4th Meeting Hub view that
  aggregates recurring questions/concerns/positives across every structured
  post-meeting note, to surface what to address on the next earnings call).
  All still available in app.py.
- Buy-Side Intelligence has 3 remaining sub-features not yet ported, still
  in app.py: the Chorus Call Listener Log (CSV upload of the actual Q1
  earnings-call listener export — name/firm/duration — with automatic
  "HOT LEAD" flagging of non-covering listeners and a one-click add to the
  New Analyst Onboarding Pipeline); Retail Investor Communication Priority
  (cross-references inbound IR questions against the NOBO shareholder file
  and IR website visitor log to triage who gets a call-back vs. a form
  email); the Closed-Loop Earnings Call Outreach generator (personalized
  pre-earnings emails with call logistics, reviewed/approved before sending
  via IRConnect); and the New Analyst Onboarding Tracker (a 6-stage
  pipeline — Cold through Evangelist — for every new sell-side/buy-side
  analyst, separate from the Engagement Funnel above, which only tracks
  already-known buy-side institutions). Analyst Coverage Network Targeting
  (cross-references institutions against a covering analyst's other covered
  tickers) IS now ported — see Target Database below, where it's grouped
  with the rest of the prospecting pipeline instead of Buy-Side Intelligence
  (same reasoning as Peer Cross-Targeting's placement, below).
- The "📧 Scan IRConnect Inbox for Meeting Confirmations" feature is ported,
  but folded into the existing "🔄 Sync IR Inbox" pipeline above (see
  core/email_classifier.py's "meeting_confirmation" category) rather than
  rebuilt as its own ad hoc button — app.py's version prompted for the
  IRConnect mailbox password on every scan instead of using the .env-based
  IMAP credentials core/mail_gateway.py already uses for every other email
  feature; typing a mailbox password into a text field each time would have
  been a real regression in how this app handles secrets, not a faithful
  port. Confirmed meeting emails now go through the same AI
  classify-then-human-confirm flow as every other inbound category.
- NDR Planner: trip creation (name, sponsor, dates, type, city, focus, team,
  objectives) and the Active NDRs list with a plain-text itinerary export are
  ported. The original's auto-suggested, geographically-matched target list
  (a 25-institution curated database matched against the trip's city/type,
  with a two-column checkbox grid for building day-by-day schedules) is NOT
  ported in this pass — trips are created with objectives/team/dates, and
  specific meetings are added to a trip by hand. Prep Cards and Post-NDR
  Debrief sub-tabs are not yet ported; both remain available in app.py.
- Target Database: institution/prospect search+filter, a manual "add
  prospect" form, and the full automated prospecting pipeline are all
  ported — Analyst Coverage Network Targeting (core.analyst_coverage),
  live-13F-backed Automated Prospecting (core.prospecting.
  generate_coverage_prospects — rebuilt on core.sec_filings' real SEC 13F
  fetcher rather than app.py's original hardcoded KNOWN_13F_HOLDERS demo
  dict), NOBO cross-reference (core.prospecting.match_against_nobo), and
  bulk paste-from-website parsing (core.prospecting.parse_pasted_table).
  See each section's on-page caption for specifics — most notably, a ticker
  only contributes real Automated Prospecting results once its 13F data has
  actually been refreshed from the SEC Intelligence tab (13F refresh is
  heavy and stays a manual, explicit action — see core/sec_filings.py).

All per-client state persists via core.db (SQLite), under the keys
meeting_log.csv, peer_universe.csv, ndr_trips.json, scheduled_meetings.json,
post_meeting_notes.json, prospects.json, and buyside_mode.json — same
pattern as today_page.py, calendar_page.py, and reports_page.py. The two
external-system CSV exports this page reads in _render_big_picture()
(q1_2026_call_listener_log.csv from Chorus Call, ir_website_visitor_log.csv
from Google Analytics/Irwin/Q4) are deliberately still real files via
client_data_path() — they're meant to be replaced by literally uploading a
fresh export, not app-internal state. See core/db.py's module docstring for
the reasoning behind what moved to SQLite and what stayed as files.
"""

import asyncio
import csv
import io
import json
import os
import uuid
from datetime import datetime, timedelta
from urllib.parse import quote

import pandas as pd
from nicegui import ui

from config.client_config import CA, CE, CI, CP, CT, client_data_path, get_active_client_id
from config.theme_tokens import ACTIVE as COLORS
from core import analyst_coverage, consensus, db, documents, fit_score, inbox_queue, mail_gateway, market_data, prospecting, risk_scorecard, sec_filings
from core.investor_scoring import (
    INTERACTION_SCORE_MAX,
    OUTCOME_POINTS,
    compute_interaction_score as _compute_interaction_score,
    days_since_last_contact as _days_since_last_contact,
    get_fund_meetings as _get_fund_meetings,
    load_meeting_log as _load_meeting_log,
    save_meeting_log as _save_meeting_log,
    score_institutions as _score_institutions,
)
from core.security import get_anthropic_api_key
from data.seed.buyside_institutions import get_seed_buyside_institutions
from data.seed.conferences import get_seed_conferences
from data.seed.consensus_estimates import ALL_PERIODS
from data.seed.institution_contacts import get_institution_contacts
from page_modules_nicegui import nav

# Post-Meeting Notes topic scaffolding — shared between the "click a topic to
# add it" chip row (_render_meeting_hub_tab) and _structure_notes_with_ai's
# prompt/fallback, so the two stay in lockstep. A blank raw-notes textarea
# right after a call tends to get skipped or filled with two rushed
# sentences; these chips nudge coverage of the financial topics that matter
# most without forcing rigid per-topic fields, and the inserted headers give
# the AI a much stronger signal to structure from than unlabeled prose.
NOTE_TOPICS = ["Revenue growth", "Segment/product growth", "Margins", "Cash flow",
               "Guidance/outlook", "Balance sheet & capital allocation",
               "Competitive positioning", "Valuation/multiple"]

# ─────────────────────────────────────────────────────────────────────────
# Small persistence helpers — every one of these is client-scoped via
# core.db (SQLite), so client #2 never sees client #1's pipeline data. The
# key strings below are the same names these used to be as filenames before
# the SQLite migration — core.db imports any pre-existing file under that
# name on first read, so nothing from earlier testing is lost.
# ─────────────────────────────────────────────────────────────────────────
def _load_json(name, default):
    return db.load_json(name, default)


def _save_json(name, data):
    db.save_json(name, data)


# _load_meeting_log / _save_meeting_log now live in core/investor_scoring.py
# (imported near the top of this file) — today_page.py's Investor Pipeline
# widget reads/writes the exact same meeting log, so an email logged from
# either page shows up on that fund's record everywhere.


# ─────────────────────────────────────────────────────────────────────────
# NDR Requests — inbound analyst requests to slot a management meeting into
# a city ("Scott is asking to slot 1x1s while management is in NY"). Used
# to be a hardcoded literal list with fixed "received" dates (Jun 28-30,
# 2026) baked into _render_big_picture()'s Metro Priority scoring — those
# dates were already in the past the moment "today" moved past them, which
# meant the "This Week's Priority" recommendation kept citing a request as
# fresh signal long after it had gone stale. Now a real persisted,
# loggable/resolvable list (core.db, key "ndr_requests.json"), same pattern
# as ndr_trips.json — seeded once with 3 example requests whose "received"
# dates are computed relative to whenever the seed is first created (not
# hardcoded absolute dates), so they never render as literally impossible.
# ─────────────────────────────────────────────────────────────────────────
def _seed_ndr_requests():
    today = datetime.now().date()
    return [
        {"id": "seed-1", "analyst": "Scott Buck", "firm": "H.C. Wainwright", "city": "New York", "metro": "New York Metro",
         "reason": "H.C. Wainwright's Annual Global Investment Conference is coming up — Scott is asking to slot "
                   f"{CT('ticker')} 1x1s with attending funds while management is already in the city.",
         "received": (today - timedelta(days=11)).strftime("%b %d, %Y"), "resolved": False, "seeded": True},
        {"id": "seed-2", "analyst": "Gary Prestopino", "firm": "Barrington Research", "city": "Boston", "metro": "Boston / New England",
         "reason": "Gary is bringing two institutional accounts through Boston and wants to add a "
                   f"{CT('ticker')} management meeting to that itinerary.",
         "received": (today - timedelta(days=9)).strftime("%b %d, %Y"), "resolved": False, "seeded": True},
        {"id": "seed-3", "analyst": "Barry Sine", "firm": "Litchfield Hills Research", "city": "Chicago", "metro": "Chicago / Midwest",
         "reason": "Barry wants an in-person working session before he'll complete his model build — he missed the "
                   "last call entirely and says a call alone won't get him there.",
         "received": (today - timedelta(days=10)).strftime("%b %d, %Y"), "resolved": False, "seeded": True},
    ]


def _load_ndr_requests():
    records = db.load_json("ndr_requests.json", default=None)
    if records is not None:
        return records
    seeded = _seed_ndr_requests()
    db.save_json("ndr_requests.json", seeded)
    return seeded


def _save_ndr_requests(records):
    db.save_json("ndr_requests.json", records)


def _mailto(to, subject, body, label):
    href = f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"
    return ui.link(f"✉️ {label}", href).style(f"color:{COLORS['accent_light']};")


def _refresh():
    nav.go_to("Investors")


# ─────────────────────────────────────────────────────────────────────────
# Peer Universe — persisted via core.db under the "peer_universe.csv" key,
# the same key config.client_config.CP() reads (ticker/name/ev_rev), so
# peers added or edited here immediately show up in outreach-draft
# valuation comparisons too. sector is stored here for display but ignored
# by CP().
# ─────────────────────────────────────────────────────────────────────────
# weight/tier drive core/fit_score.py's Peer conviction + Comparability fit
# components — "core" = closest-size direct comp (weight 2, full Fit
# points, +5 conviction bonus for holding one), "close" = a real but
# less-comparable peer (weight 1, default), "large" = mega-cap/weak-signal
# peer (weight 0.5, weakest Fit tier). GDOT and PRTH are USIO's closest-size
# direct comps; EEFT/FOUR are larger-cap with weaker signal; the rest
# default to "close" until reviewed — same "seed is default, edit persists"
# pattern as everywhere else, editable in Manage Peer Universe below.
DEFAULT_PEER_UNIVERSE = [
    {"ticker": "GDOT", "name": "Green Dot Corporation", "sector": "Prepaid / Banking", "ev_rev": 1.2, "weight": 2.0, "tier": "core"},
    {"ticker": "PRTH", "name": "Priority Technology Holdings", "sector": "PayFac / SMB Payments", "ev_rev": 1.8, "weight": 2.0, "tier": "core"},
    {"ticker": "EEFT", "name": "Euronet Worldwide", "sector": "ACH / International Payments", "ev_rev": None, "weight": 0.5, "tier": "large"},
    {"ticker": "FOUR", "name": "Shift4 Payments", "sector": "PayFac / Hospitality", "ev_rev": 4.2, "weight": 0.5, "tier": "large"},
    {"ticker": "CASS", "name": "Cass Information Systems", "sector": "B2B Payments / AP Automation", "ev_rev": None, "weight": 1.0, "tier": "close"},
    {"ticker": "RPAY", "name": "Repay Holdings", "sector": "ACH / Vertical Payments", "ev_rev": 2.8, "weight": 1.0, "tier": "close"},
    {"ticker": "PAX", "name": "PAX Global Technology", "sector": "Payment Terminals", "ev_rev": None, "weight": 1.0, "tier": "close"},
]


def _load_peer_universe():
    records = db.load_json("peer_universe.csv", default=None)
    if records is not None:
        known_ev = {p["ticker"]: p["ev_rev"] for p in DEFAULT_PEER_UNIVERSE if p["ev_rev"] is not None}
        for r in records:
            if r.get("ev_rev") in (None, ""):
                r["ev_rev"] = known_ev.get(r.get("ticker"))
            if not r.get("sector"):
                r["sector"] = "Payments / Fintech"
            # Backfill for peers saved before core/fit_score.py's weight/tier
            # fields existed — default weight=1.0/tier="close" (neutral,
            # matches core.fit_score._DEFAULT_PEER_ENTRY) so an un-reviewed
            # peer degrades gracefully into the Fit Score instead of KeyError.
            if r.get("weight") in (None, ""):
                r["weight"] = 1.0
            if not r.get("tier"):
                r["tier"] = "close"
        # Backfill: an earlier save of this list only had a subset of the
        # 7 built-in DEFAULT_PEER_UNIVERSE tickers (e.g. GDOT/PRTH/EEFT but
        # not FOUR/CASS/RPAY/PAX) — the loop above only patches fields on
        # records that already exist, it never adds a default ticker that's
        # simply missing entirely. Add back any missing default so nobody's
        # stuck with a stale, incomplete peer set from before all 7 existed.
        # Only ADDS — never removes a peer the user deleted on purpose, and
        # never touches a peer the user added themselves.
        existing_tickers = {r.get("ticker") for r in records}
        missing_defaults = [dict(p) for p in DEFAULT_PEER_UNIVERSE if p["ticker"] not in existing_tickers]
        if missing_defaults:
            records = records + missing_defaults
            _save_peer_universe(records)
        return records
    return [dict(p) for p in DEFAULT_PEER_UNIVERSE]


def _save_peer_universe(peers):
    db.save_json("peer_universe.csv", peers)


def _parse_aum_millions(aum_str):
    """'$2.1B' -> 2100.0, '$380M' -> 380.0, '$8.2T' -> 8_200_000.0. Returns 0
    if it can't be parsed, so an unparseable AUM never satisfies a nonzero
    minimum filter."""
    if not aum_str:
        return 0.0
    s = str(aum_str).strip().upper().replace("$", "").replace(",", "")
    mult = {"T": 1_000_000.0, "B": 1_000.0, "M": 1.0}
    for suffix, m in mult.items():
        if s.endswith(suffix):
            try:
                return float(s[:-1]) * m
            except ValueError:
                return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _client_ev_rev(period="Q2 2026E"):
    """This client's own EV/Revenue multiple, computed the same way
    markets_page.py's PT Justification cards compute it (live price via
    core.market_data x shares outstanding + net debt, over the guidance
    revenue estimate for the given period) — was a hardcoded 0.4x literal
    in the pre-earnings outreach draft below; that number moves with the
    stock and shouldn't be typed in. Returns None if market data or the
    seed financial-position/guidance fields aren't available yet, so
    callers can fall back to a peer-agnostic outreach line instead of
    showing a stale or fabricated multiple."""
    from data.seed.consensus_estimates import get_seed_consensus
    snap = market_data.get_snapshot(CT("ticker"))
    last_price = snap["last_price"] if snap and snap.get("last_price") is not None else CT("last_price", None)
    if last_price is None:
        return None
    seed = get_seed_consensus(get_active_client_id())
    fin = seed.get("financial_position", {})
    shares_out = fin.get("shares_out_m")
    net_debt = fin.get("net_debt_m", 0)
    rev_est = seed.get("period_guidance", {}).get(period, {}).get("Revenue Est ($M)")
    if not shares_out or not rev_est:
        return None
    ev = last_price * shares_out + net_debt
    return round(ev / rev_est, 2)


# OUTCOME_POINTS, INTERACTION_SCORE_MAX, _compute_interaction_score,
# _score_institutions, and _get_fund_meetings now live in
# core/investor_scoring.py (imported near the top of this file) — pulled
# out so today_page.py's Investor Pipeline widget scores institutions the
# exact same way this page does, instead of a second hand-maintained copy.


def _get_repeat_signal(meetings):
    if len(meetings) < 2:
        return None
    try:
        dates = sorted([datetime.strptime(m["Date"], "%Y-%m-%d").date() for m in meetings], reverse=True)
    except Exception:
        return None
    gap = (dates[0] - dates[1]).days
    return gap if gap <= 45 else None


# ─────────────────────────────────────────────────────────────────────────
# AI note structuring — ported directly from app.py's structure_notes_with_ai.
# No Streamlit dependency in the original, so this is a straight port.
# ─────────────────────────────────────────────────────────────────────────
def _structure_notes_with_ai(raw_notes, contact, firm, meeting_type):
    import re
    try:
        import urllib.error
        import urllib.request
        topics_list = ", ".join(NOTE_TOPICS)
        prompt = f"""You are an expert IR analyst. Structure these raw post-meeting notes from a call with {contact} at {firm} ({meeting_type}) into the following JSON format:
{{
  "key_questions": ["list of questions the investor/analyst asked"],
  "concerns_raised": ["list of concerns or risks they mentioned"],
  "positive_signals": ["things they said that indicate interest or conviction"],
  "commitments_made": ["anything IR/management committed to follow up on"],
  "follow_up_actions": ["specific next steps"],
  "financial_kpi_takeaways": ["specific comments tied to financial/operating topics such as {topics_list} — one item per topic actually discussed, phrased as e.g. 'Revenue growth: investor pushed back on Q3 deceleration'; omit topics that weren't discussed"],
  "sentiment": "Positive / Neutral / Negative / Mixed",
  "summary": "2-3 sentence executive summary of the call"
}}

Raw notes:
{raw_notes}

Return ONLY valid JSON, no other text."""
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 1000,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={"Content-Type": "application/json", "x-api-key": get_anthropic_api_key(),
                     "anthropic-version": "2023-06-01"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            raw_text = "".join(
                block.get("text", "") for block in result.get("content", []) if block.get("type") == "text"
            ).strip()
            if raw_text.startswith("```"):
                # Claude sometimes wraps the JSON in a ```json ... ``` fence
                # even when told to return raw JSON only. json.loads chokes
                # on the leading backtick with "Expecting value: line 1
                # column 1 (char 0)" — this was the real cause of every
                # real (key-is-valid) call silently falling back to the
                # keyword-matching summary below. Strip the fence first.
                lines = raw_text.split("\n")
                if lines and lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                raw_text = "\n".join(lines).strip()
            if not raw_text:
                raise ValueError("Claude returned an empty response body")
            parsed = json.loads(raw_text)
            print("[ai_notes] Claude call succeeded — using real AI-structured summary.")
            return parsed
    except urllib.error.HTTPError as e:
        # Anthropic's real error body (e.g. authentication_error, a bad model
        # name, insufficient credit) — this used to be swallowed by a bare
        # `except Exception: pass`, so a bad/expired API key silently fell
        # back to the keyword-matching summary below with zero visible sign
        # anything was wrong. Logging it here (server console, not the UI —
        # this is a diagnostic, not something to alarm the end user with on
        # every call) makes that failure mode debuggable.
        try:
            body = e.read().decode(errors="replace")
        except Exception:
            body = "(no response body)"
        print(f"[ai_notes] Claude API call failed — HTTP {e.code}: {body} — falling back to keyword-based summary.")
    except Exception as e:
        print(f"[ai_notes] Claude API call failed — {type(e).__name__}: {e} — falling back to keyword-based summary.")

    questions = [s.strip() for s in re.split(r'[.!?\n]', raw_notes) if '?' in s and len(s.strip()) > 10]
    positives = [s.strip() for s in re.split(r'[.!\n]', raw_notes)
                 if any(w in s.lower() for w in ["interested", "positive", "like", "impressed", "compelling", "strong"]) and len(s.strip()) > 10]
    concerns = [s.strip() for s in re.split(r'[.!\n]', raw_notes)
                if any(w in s.lower() for w in ["concern", "worry", "risk", "decline", "miss", "issue", "problem"]) and len(s.strip()) > 10]
    actions = [s.strip() for s in re.split(r'[.!\n]', raw_notes)
               if any(w in s.lower() for w in ["follow", "send", "provide", "share", "schedule", "call back", "deck"]) and len(s.strip()) > 10]
    # Pulls "Revenue growth: ..." style lines left by the topic chips (see
    # NOTE_TOPICS) straight through as-is — this is the one part of the
    # fallback that doesn't need real NLP, since the topic label is already
    # right there in the text the chip inserted.
    kpi_takeaways = []
    for line in raw_notes.split("\n"):
        line = line.strip()
        if not line:
            continue
        for topic in NOTE_TOPICS:
            if line.lower().startswith(topic.lower() + ":"):
                detail = line[len(topic) + 1:].strip()
                if detail:
                    kpi_takeaways.append(f"{topic}: {detail}")
                break
    sentiment = "Positive" if len(positives) > len(concerns) else "Mixed" if positives else "Neutral"
    return {
        "key_questions": questions[:4], "concerns_raised": concerns[:3], "positive_signals": positives[:3],
        "commitments_made": [], "follow_up_actions": actions[:3], "financial_kpi_takeaways": kpi_takeaways[:6],
        "sentiment": sentiment,
        "summary": f"Meeting with {contact} at {firm}. {len(questions)} questions raised. Sentiment: {sentiment}.",
    }


def _enrich_peer_holdings_with_live_13f(institutions, peer_tickers):
    """Replaces each institution's seed Peer_Holdings with a freshness-
    aware effective value, mutating institutions in place (same pattern
    core.investor_scoring.score_institutions already uses on this list).

    Every original DEFAULT_PEER_UNIVERSE record before this feature had
    hand-typed Peer_Holdings — never real SEC data, even for the original
    3 tracked tickers (GDOT/PRTH/EEFT). Adding new peer tickers (FOUR,
    CASS, RPAY, PAX) made that visible: selecting a newly-added ticker in
    Peer Cross-Targeting could never surface a match, because nothing in
    the seed data has ever heard of those tickers. core.sec_filings has a
    real, working SEC 13F fetcher (see refresh_13f_holders / the "Refresh
    13F Institutional Holders" button on the SEC Intelligence tab) — this
    function is what actually connects that real data back into Peer
    Cross-Targeting and the "Peers held" display, instead of leaving them
    reading a permanently-static list.

    Per ticker, per institution:
    - If that ticker's 13F data has never been fetched (not_fetched):
      keep whatever the seed said, unchanged — so nothing regresses before
      anyone clicks Refresh, and the original 3 tickers keep behaving
      exactly as they always have until a real refresh happens for them.
    - If that ticker HAS been fetched: use ONLY the real, confirmed
      result — a real 13F filing always outranks a hand-typed seed guess,
      even when they disagree (see core.sec_filings.live_peer_overlap_map's
      docstring on why matching is exact-name, not fuzzy — some seed
      institutions are specific strategies, not 13F filers of record, and
      will legitimately show "no confirmed match" once real data exists).

    Also stamps inst["Peer_Holdings_Source"] = {ticker: "live"|"seed"} so
    the UI can show which tickers are backed by a real filing vs. still on
    the original seed guess, instead of presenting both identically."""
    overlap_map = sec_filings.live_peer_overlap_map([i["Fund"] for i in institutions], peer_tickers)
    for inst in institutions:
        overlap = overlap_map.get(inst["Fund"], {"confirmed": [], "not_fetched": peer_tickers})
        not_fetched = set(overlap["not_fetched"])
        seed_holdings = set(inst.get("Peer_Holdings", []))
        effective = set(overlap["confirmed"]) | {t for t in seed_holdings if t in not_fetched}
        inst["Peer_Holdings"] = sorted(effective)
        inst["Peer_Holdings_Source"] = {
            t: ("live" if t not in not_fetched else "seed") for t in peer_tickers
        }


# ─────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────
def render_investors_page():
    client_id = get_active_client_id()
    mode_state = _load_json("buyside_mode.json", {})
    earnings_date_str = CE().get("earnings_date", "2026-08-12")
    earnings_date = datetime.strptime(earnings_date_str, "%Y-%m-%d").date()
    days_to_earnings = (earnings_date - datetime.now().date()).days
    auto_post = days_to_earnings < 0
    mode = mode_state.get("mode", "post" if auto_post else "pre")

    q2_listeners = set(mode_state.get("q2_listeners", []))
    meeting_log = _load_meeting_log()
    raw_institutions = get_seed_buyside_institutions(client_id)
    # Upgrades Peer_Holdings from static seed data to real SEC 13F filings
    # wherever a ticker has actually been refreshed (see
    # _enrich_peer_holdings_with_live_13f's docstring) — must run BEFORE
    # scoring, since post-earnings mode's Catalyst Fit pillar reads
    # Peer_Holdings too, not just Peer Cross-Targeting below.
    _enrich_peer_holdings_with_live_13f(raw_institutions, [p["ticker"] for p in _load_peer_universe()])
    institutions = _score_institutions(raw_institutions, mode, q2_listeners, meeting_log)

    ui.label(f"{CT('name')} — Investor Pipeline & Engagement").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    _render_big_picture(institutions)
    ui.markdown("---")
    _render_mode_toggle(mode, mode_state)
    ui.markdown("---")

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("👥 Buy-Side Intelligence")
        t2 = ui.tab("✈️ NDR Planner")
        t3 = ui.tab("🤝 Meeting Hub")
        t4 = ui.tab("🎯 Target Database")
        t5 = ui.tab("🏛️ SEC Intelligence")

    # Lazy tab loading — this page used to build ALL FIVE tabs' content
    # (each with its own set of database reads) on every single visit,
    # whether or not the user ever looked past "Buy-Side Intelligence".
    # That's the actual cause behind "I click Investor Targeting and
    # nothing happens": ui.tab_panels builds every panel's Python content
    # immediately regardless of which one is selected — only the CSS
    # visibility toggles client-side, the server-side work (and every
    # Neon query in it) already happened for all 5 tabs before anything
    # painted. Now only the default-open tab (Buy-Side Intelligence) is
    # built eagerly; the other four start as a placeholder and are built
    # for real — with a visible spinner while that happens — the first
    # time each one is actually clicked, then cached so switching back
    # doesn't rebuild it again.
    with ui.tab_panels(tabs, value=t1).classes("w-full"):
        with ui.tab_panel(t1):
            _render_buyside_tab(institutions, meeting_log, mode)
        with ui.tab_panel(t2) as p2:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t3) as p3:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t4) as p4:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t5) as p5:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")

    lazy_panels = {
        t2.props["name"]: (p2, lambda: _render_ndr_tab(institutions, meeting_log, client_id)),
        t3.props["name"]: (p3, lambda: _render_meeting_hub_tab()),
        t4.props["name"]: (p4, lambda: _render_target_db_tab(institutions, client_id)),
        t5.props["name"]: (p5, lambda: _render_sec_intelligence_tab()),
    }
    loaded_tabs = set()

    async def _load_tab_on_demand(e):
        name = e.value
        if name not in lazy_panels or name in loaded_tabs:
            return
        loaded_tabs.add(name)
        container, build_fn = lazy_panels[name]
        # Yield to the event loop once so the spinner that's already in
        # `container` actually reaches the browser before this function
        # goes on to do the (synchronous) database reads that tab needs —
        # without this await, the spinner and the real content would both
        # get flushed to the browser in the same batch, i.e. no visible
        # "loading" feedback at all, just a delay.
        await asyncio.sleep(0)
        container.clear()
        with container:
            build_fn()

    tabs.on_value_change(_load_tab_on_demand)


def _render_mode_toggle(mode, mode_state):
    with ui.row().classes("w-full items-center gap-4"):
        toggle = ui.toggle({"pre": "🎯 Pre-Earnings — Engagement Mode", "post": "🚀 Post-Earnings — Prospecting Mode"}, value=mode)

        def on_change():
            mode_state["mode"] = toggle.value
            _save_json("buyside_mode.json", mode_state)
            _refresh()

        toggle.on_value_change(on_change)
    # Was: solid fixed-dark background (from the old dark theme) with the
    # descriptive text left uncolored — it inherited the page's default text
    # color, which under the active CREAM (light) theme resolves dark/near-
    # black, making it nearly invisible against the leftover dark green/navy
    # fill (the washed-out text in the screenshot). Same fix as _tier_card /
    # _render_repeat_alert_banner: light card, colored left border, explicit
    # theme-token text color throughout.
    if mode == "pre":
        accent = COLORS["accent"]
        ui.html(
            f"<div style='background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:4px solid {accent};"
            f"border-radius:8px;padding:8px 14px;font-size:12px;color:{COLORS['text_body']};'>"
            f"<b style='color:{accent};'>Pre-Earnings Mode</b> · Scoring weights: Call listener 40% · Peer holder 35% · "
            f"IR visits 25% · Goal: who already knows the story → send call invitation → close the loop</div>"
        )
    else:
        accent = COLORS["positive"]
        ui.html(
            f"<div style='background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:4px solid {accent};"
            f"border-radius:8px;padding:8px 14px;font-size:12px;color:{COLORS['text_body']};'>"
            f"<b style='color:{accent};'>Post-Earnings Prospecting Mode</b> · Scoring weights: Q2 call listener 40% · "
            f"Catalyst fit 35% · New IR activity 25% · Goal: who heard the beat → fits the upgrade thesis → call in first 5 days</div>"
        )


# ─────────────────────────────────────────────────────────────────────────
# Big Picture synthesis
# ─────────────────────────────────────────────────────────────────────────
def _render_big_picture(institutions):
    client_id = get_active_client_id()

    metro_lookup = {i["Fund"]: i["Metro"] for i in institutions}
    metro_lookup.update({
        "H.C. Wainwright": "New York Metro", "Ladenburg Thalmann": "New York Metro",
        "Maxim Group": "New York Metro", "Litchfield Hills Research": "New York Metro",
        "Barrington Research": "Chicago / Midwest", "Northland Securities": "Chicago / Midwest",
        "Royce Investment Partners": "New York Metro", "Kennedy Capital Management": "Chicago / Midwest",
        "Conestoga Capital Advisors": "Philadelphia / Baltimore", "Robotti & Company": "New York Metro",
    })

    trip_rows, total_meetings = [], 0
    trips = _load_json("ndr_trips.json", [])
    for t in trips:
        if t.get("city") and t.get("city") != "Virtual":
            n = sum(len(d.get("meetings", [])) for d in t.get("schedule", []))
            total_meetings += n
            trip_rows.append((t["city"], t.get("dates", "—"), ", ".join(t.get("team", [])) or "—",
                               t.get("sponsor_bank", "—") or "—", n))

    ndr_requests = [r for r in _load_ndr_requests() if not r.get("resolved")]
    conferences = get_seed_conferences(client_id)
    wainwright_conf = next((c for c in conferences if "Wainwright" in c.get("Event", "")), None)

    call_by_metro = {}
    try:
        cl_path = client_data_path("q1_2026_call_listener_log.csv")
        if os.path.exists(cl_path):
            cl = pd.read_csv(cl_path)
            hot = cl[cl["Flag"].astype(str).str.contains("HOT LEAD|Newly engaged", case=False, na=False)]
            for _, r in hot.iterrows():
                m = metro_lookup.get(r["Firm"], "Unmapped")
                call_by_metro[m] = call_by_metro.get(m, 0) + 1
    except Exception:
        pass
    call_signal = sum(call_by_metro.values())

    visitor_signal = 0
    try:
        vis_path = client_data_path("ir_website_visitor_log.csv")
        if os.path.exists(vis_path):
            vl = pd.read_csv(vis_path)
            visitor_signal = int((vl["Category"] == "New - Unidentified").sum())
    except Exception:
        pass
    prospects = _load_json("prospects.json", [])
    prospect_q_count = len(prospects)

    holders_by_metro = {}
    for i in institutions:
        if i["USIO_Holder"]:
            holders_by_metro[i["Metro"]] = holders_by_metro.get(i["Metro"], 0) + 1
    holder_count = sum(holders_by_metro.values())
    tracked_total = len(institutions)

    city_to_metro = {
        "Boston": "Boston / New England", "New York": "New York Metro",
        "San Francisco": "West Coast (SF/LA)", "Chicago": "Chicago / Midwest",
        "Minneapolis / Midwest": "Chicago / Midwest", "Texas / Denver": "Texas / Denver",
        "Philadelphia / Baltimore": "Philadelphia / Baltimore",
    }
    visited_metros = {city_to_metro.get(c, c) for c, *_ in trip_rows}

    new_total = call_signal + visitor_signal + prospect_q_count
    bp_denom = max(new_total + holder_count, 1)
    new_pct = round(new_total / bp_denom * 100)
    if new_pct >= 70:
        mix_label, mix_color = "🟢 Strong — well above the 50/50 baseline management would be happy with", "#4ADE80"
    elif new_pct >= 45:
        mix_label, mix_color = "🟡 Balanced — roughly the 50/50 mix management would be content with", "#F0A830"
    else:
        mix_label, mix_color = "🔴 Existing-heavy — below the mix that keeps management happy; needs more new-investor prospecting", "#F87171"

    new_from_recent_trip = sum(n for m, n in call_by_metro.items() if m in visited_metros)
    recency_note = ""
    if call_signal > 0 and visited_metros:
        recent_pct = round(new_from_recent_trip / call_signal * 100)
        if recent_pct >= 50:
            recency_note = (f"⚠️ {recent_pct}% of the call-engagement signal ties back to a city you just visited "
                             f"({', '.join(visited_metros & set(call_by_metro.keys()))}) — worth watching whether this holds up "
                             f"once that trip's momentum fades, not just banking it as durable growth.")
        else:
            recency_note = (f"Checked against your recent trip(s): only {recent_pct}% of the call-engagement signal "
                             f"ties back to a recently-visited city — this isn't just NDR afterglow, it's broader than that.")

    visits_by_metro = {}
    for city, *_r in trip_rows:
        m = city_to_metro.get(city, city)
        visits_by_metro[m] = visits_by_metro.get(m, 0) + 1

    metro_summary = {}
    for i in institutions:
        m = i["Metro"]
        d = metro_summary.setdefault(m, {"count": 0, "tier1_nonholder": 0, "holders": 0, "top": None, "top_score": -1})
        d["count"] += 1
        if i["Engagement_Score"] >= 80 and not i["USIO_Holder"]:
            d["tier1_nonholder"] += 1
        if i["USIO_Holder"]:
            d["holders"] += 1
        if i["Engagement_Score"] > d["top_score"]:
            d["top_score"], d["top"] = i["Engagement_Score"], i["Fund"]

    requests_by_metro = {}
    for req in ndr_requests:
        requests_by_metro[req["metro"]] = requests_by_metro.get(req["metro"], 0) + 1

    metro_priority = []
    for m in set(list(metro_summary.keys()) + list(requests_by_metro.keys())):
        d = metro_summary.get(m, {"count": 0, "tier1_nonholder": 0, "holders": 0, "top": None, "top_score": -1})
        visits = visits_by_metro.get(m, 0)
        req_count = requests_by_metro.get(m, 0)
        priority = (d["tier1_nonholder"] * 3 + d["holders"] * 1.5 + d["count"] + req_count * 2.5) / (visits + 1)
        metro_priority.append((m, priority, d, visits, req_count))
    metro_priority.sort(key=lambda x: -x[1])
    top_metro, _tp, top_d, top_visits, _tr = metro_priority[0]
    top_metro_request = next((r for r in ndr_requests if r["metro"] == top_metro), None)
    top_metro_conf = None
    if top_metro_request and wainwright_conf and "Wainwright" in top_metro_request["firm"]:
        top_metro_conf = wainwright_conf

    tier1_preview = [i for i in institutions if i["Engagement_Score"] >= 80]
    weakest_request = ndr_requests[-1] if ndr_requests else None
    quiet_start = CE().get("quiet_start", "")
    try:
        quiet_period_days = max((datetime.strptime(quiet_start, "%Y-%m-%d").date() - datetime.now().date()).days, 0)
    except Exception:
        quiet_period_days = 0

    ui.label("🧭 Big Picture — Where Things Stand").classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};margin-top:10px;")

    with ui.row().classes("w-full gap-3"):
        _bp_metric("NDR Requests/City", str(len(ndr_requests)),
                   [f"{r['analyst']} ({r['firm']}) → {r['city']}: {r['reason']} — received {r['received']}" for r in ndr_requests])
        _bp_metric("New Investor Signals", str(call_signal + visitor_signal),
                   [("Call engagement by city: " + ", ".join(f"{m} ({n})" for m, n in sorted(call_by_metro.items(), key=lambda x: -x[1]))) if call_by_metro else "No call-engagement signal on file.",
                    f"{visitor_signal} new site visitors (city unknown) · {prospect_q_count} in prospect queue"])
        _bp_metric("Existing Holders Tracked", f"{holder_count} / {tracked_total}",
                   [("By city: " + ", ".join(f"{m} ({n})" for m, n in sorted(holders_by_metro.items(), key=lambda x: -x[1]))) if holders_by_metro else "No holders tracked yet.",
                    f"{tracked_total - holder_count} active non-holder prospects being worked"])
        _bp_metric("Past NDRs & Meetings", str(len(trip_rows)),
                   [f"{c} — {dt} · {tm} · Sponsor: {sp} · {n} meetings" for c, dt, tm, sp, n in trip_rows] or ["No NDR trips logged yet"])

    ui.html(
        f"<div style='font-size:12.5px;color:{COLORS['text_muted']};margin-top:6px;'>New vs. existing — where the pipeline is weighted right now</div>"
        f"<div style='display:flex;height:20px;border-radius:5px;overflow:hidden;'>"
        f"<div style='width:{new_pct}%;background:#3B82F6;'></div>"
        f"<div style='width:{100-new_pct}%;background:#475569;'></div></div>"
        f"<div style='font-size:11.5px;color:{COLORS['text_muted']};margin-top:4px;'>🔵 New/prospective: {new_total} &nbsp; ⚪ Existing holders: {holder_count}</div>"
        f"<div style='font-size:12px;color:{mix_color};margin-top:4px;'>{mix_label} ({new_pct}% new / {100-new_pct}% existing)</div>"
        + (f"<div style='font-size:11px;color:{COLORS['text_muted']};margin-top:2px;'>{recency_note}</div>" if recency_note else "")
    )

    most_visited = max(visits_by_metro.items(), key=lambda x: x[1]) if visits_by_metro else None
    if most_visited and most_visited[1] >= 2 and most_visited[0] != top_metro:
        ui.html(
            f"<div style='font-size:13px;color:#F0A830;margin-top:10px;'>"
            f"⚠️ By contrast, <b>{most_visited[0]}</b> has had {most_visited[1]} trips already for only "
            f"{metro_summary.get(most_visited[0], {}).get('count', '?')} tracked institution(s) — before scheduling a third trip "
            f"there, weigh it against the untapped opportunity in {top_metro}.</div>"
        )

    ui.markdown("---")
    top_conf_html = (f" This lines up with their own <b>{top_metro_conf['Event']}</b> on {top_metro_conf['Date']} — three independent "
                      f"signals (investor demand, analyst request, and a real upcoming event) all pointing at the same city."
                      if top_metro_conf else "")
    top_req_html = (f" <b>Plus a direct request:</b> {top_metro_request['analyst']} ({top_metro_request['firm']}) asked for "
                     f"{top_metro_request['city']} meetings on {top_metro_request['received']} — {top_metro_request['reason']}"
                     if top_metro_request else "")
    ui.html(
        f"<div style='background:linear-gradient(135deg,#152230,#1A2D45);border:1px solid #3B82F6;border-radius:12px;padding:18px 22px;'>"
        f"<div class='section-eyebrow'>🧭 THIS WEEK'S PRIORITY</div>"
        f"<div style='font-size:16px;font-weight:700;color:#F1F5F9;margin-top:4px;'>Focus city: {top_metro}</div>"
        f"<div style='font-size:13px;color:#C8D8E8;line-height:1.6;margin-top:6px;'>"
        f"{top_d['count']} tracked institution(s) here"
        + (f", including <b>{top_d['top']}</b> (score {top_d['top_score']})" if top_d.get('top') else "")
        + f" — {top_d['tier1_nonholder']} non-holder(s) at Tier 1 ready to convert and {top_d['holders']} existing holder(s) to defend — "
        f"{'zero NDR trips logged here yet' if top_visits == 0 else f'only {top_visits} trip(s) so far'}."
        + top_req_html + top_conf_html + "</div></div>"
    )
    ui.html(
        f"<div style='font-size:13px;color:{COLORS['text_secondary']};margin-top:10px;'><b>Ranked actions for management this week:</b></div>"
        f"<ol style='font-size:13px;color:{COLORS['text_secondary']};margin-top:4px;line-height:1.7;'>"
        f"<li>Direct 1x1 call: <b>{next((i['Fund'] for i in tier1_preview if not i['USIO_Holder']), 'top Tier 1 non-holder')}</b> — highest-scoring active conversion target.</li>"
        f"<li>Defend the position: <b>{next((i['Fund'] for i in tier1_preview if i['USIO_Holder']), 'top Tier 1 holder')}</b> — actively adding shares, needs 15 minutes before the print.</li>"
        + (f"<li>Respond to <b>{weakest_request['analyst']}</b> ({weakest_request['firm']}) before the quiet period begins in {quiet_period_days} days — {weakest_request['reason']}</li>" if weakest_request else "")
        + f"<li>Scope a <b>{top_metro}</b> NDR as the next roadshow"
        + (f", timed around {top_metro_request['analyst']}'s request" if top_metro_request else "")
        + " — it now outranks every other market on an opportunity-per-visit-and-request basis.</li></ol>"
    )


def _bp_metric(label, value, detail_lines):
    with ui.card().classes("flex-1").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:11px;")
        ui.label(value).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        with ui.expansion("details", value=False).classes("w-full"):
            for line in detail_lines:
                ui.label(line).style(f"color:{COLORS['text_muted']};font-size:11px;")


# ─────────────────────────────────────────────────────────────────────────
# Buy-Side Intelligence tab
# ─────────────────────────────────────────────────────────────────────────
def _render_buyside_tab(institutions, meeting_log, mode):
    contacts = get_institution_contacts()

    if mode == "pre":
        ui.label("💼 Buy-Side Intelligence — Pre-Earnings Engagement").classes("text-lg font-bold")
        ui.label("Three-layer institutional targeting · Engagement score 0-100 · Prioritized by probability of buying into the re-rating story").style(f"color:{COLORS['text_muted']};font-size:12px;")
    else:
        ui.label("🚀 Buy-Side Intelligence — Post-Earnings Prospecting").classes("text-lg font-bold")
        ui.label("Post-earnings catalyst scoring · Who heard the beat · Who fits the upgrade thesis · 5-day prospecting window").style(f"color:{COLORS['text_muted']};font-size:12px;")

    tier1 = [i for i in institutions if i["Engagement_Score"] >= 80]
    tier2 = [i for i in institutions if 40 <= i["Engagement_Score"] < 80]
    tier3 = [i for i in institutions if i["Engagement_Score"] < 40]

    ui.label("🎯 Engagement Funnel").classes("font-bold").style("margin-top:10px;")
    with ui.row().classes("w-full gap-3"):
        _tier_card(tier1, "🟥 Tier 1 — Defend / Convert", "Direct 1x1 calls this week", COLORS["negative"])
        _tier_card(tier2, "🟨 Tier 2 — Nurture", "Send the Q2 preview deck", COLORS["warning"])
        _tier_card(tier3, "🟦 Tier 3 — Passive", "Add to the next NDR queue", COLORS["accent"])

    ui.markdown("---")

    with ui.row().classes("w-full items-center justify-between"):
        ui.label(f"{len(institutions)} institutions tracked").classes("font-bold")
        ui.label(f"Q1 call listeners: {sum(1 for i in institutions if i['Call_Listener'])}").style(f"color:{COLORS['text_muted']};font-size:12px;")

    with ui.expansion("🔍 Filter Criteria — Coverage Priority, Holder Status, Turnover, Metro, Intent, Ownership", value=False).classes("w-full"):
        ui.label("These narrow the institution list below — they don't affect the Engagement Funnel or metrics "
                 "above, which always show the complete tracked set. All defaults below are unfiltered (everything "
                 "shown), so the list you see with no filters applied matches the same ranked order Today's "
                 "Investor Pipeline widget pulls from — narrow it from here if you want a subset.").style(f"color:{COLORS['text_muted']};font-size:11px;")
        with ui.row().classes("w-full gap-4"):
            # Coverage Priority is a manually-assigned seed classification
            # (data/seed/buyside_institutions.py's "Coverage_Priority" field,
            # renamed from "Tier") — a different concept from the live
            # Engagement_Score-derived Tier 1/2/3 buckets in the Engagement
            # Funnel above, which recompute from real signals every render.
            # Was confusable with those (both called "Tier") and previously
            # defaulted to [1, 2] here, silently hiding every Coverage
            # Priority 3 fund regardless of its live Engagement_Score —
            # defaulting to all three so nothing is hidden until a user
            # deliberately narrows it.
            tier_filter = ui.select({1: "Priority 1", 2: "Priority 2", 3: "Priority 3"}, multiple=True, value=[1, 2, 3]).classes("min-w-[140px]").props("label='Coverage priority'")
            holder_filter = ui.select(["All", "Current holders", "Non-holders only"], value="All").classes("min-w-[160px]").props("label='Holder status'")
            score_filter = ui.number(label="Min score", value=0, min=0, max=100)
            metro_options = ["All Regions"] + sorted({i["Metro"] for i in institutions})
            metro_filter = ui.select(metro_options, value="All Regions").classes("min-w-[160px]").props("label='Metro'")
        turnover_options = ["Low (Long-Term Value)", "Medium (Growth/GARP)", "High (Hedge/Trading)"]
        # Previously defaulted to excluding "High (Hedge/Trading)" — same
        # silent-hiding issue as the tier filter above.
        turnover_filter = ui.select(turnover_options, multiple=True,
                                     value=list(turnover_options)).classes("w-full").props("label='Fund Turnover Style'")
        # Previously defaulted to 40, hiding any fund with Digital_Intent_Score
        # below that even if its Engagement_Score ranked it top-5 — that score
        # is an intentionally separate, unrelated metric (see
        # core/investor_scoring.py), not something that should gate visibility
        # by default.
        intent_filter = ui.number(label="Minimum Digital Intent Score (Web Traffic & Call Replays)", value=0, min=0, max=100, step=10).classes("w-full")
        ownership_filter = ui.toggle(["All", "Active only", "Passive only"], value="All")
        ui.label("Ownership Type is tagged per manager (not parsed from the 13F itself — filings don't carry an "
                 "active/passive flag). Excluding passive/index holders surfaces who can actually take a 1x1 meeting.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        filter_btn = ui.button("Apply filters")

    ui.markdown("---")
    banner_container = ui.column().classes("w-full")
    ui.label("Full Institution List").classes("font-bold")
    list_container = ui.column().classes("w-full gap-3")

    def apply_and_render():
        banner_container.clear()
        list_container.clear()
        sel_tiers = tier_filter.value or [1, 2, 3]
        sel_turnover = turnover_filter.value or turnover_options
        filtered = [i for i in institutions
                    if i["Coverage_Priority"] in sel_tiers
                    and (holder_filter.value == "All"
                         or (holder_filter.value == "Current holders" and i["USIO_Holder"])
                         or (holder_filter.value == "Non-holders only" and not i["USIO_Holder"]))
                    and i["Engagement_Score"] >= (score_filter.value or 0)
                    and (metro_filter.value == "All Regions" or i["Metro"] == metro_filter.value)
                    and i["Turnover_Style"] in sel_turnover
                    and i["Digital_Intent_Score"] >= (intent_filter.value or 0)
                    and (ownership_filter.value == "All"
                         or (ownership_filter.value == "Active only" and i["Ownership_Style"] == "Active")
                         or (ownership_filter.value == "Passive only" and i["Ownership_Style"] == "Passive"))]

        with banner_container:
            _render_repeat_alert_banner(filtered, meeting_log)

        with list_container:
            ui.label(f"{len(filtered)} institutions matching filters").style(f"color:{COLORS['text_muted']};font-size:12px;")
            if not filtered:
                ui.label("No institutions match these filters.").style(f"color:{COLORS['text_muted']};")
            for inst in filtered:
                _institution_card(inst, meeting_log, contacts)

    filter_btn.on_click(apply_and_render)
    apply_and_render()


def _render_repeat_alert_banner(filtered, meeting_log):
    """Global '🔔 Repeat Meeting Alerts' banner above the institution list —
    surfaces every institution in the current filter set with a repeat
    meeting inside the 45-day window, classified by QoQ direction and
    outcome tone, before the per-institution cards render."""
    alerts = []
    for inst in filtered:
        fund_meetings = _get_fund_meetings(meeting_log, inst["Fund"])
        gap = _get_repeat_signal(fund_meetings)
        if gap is not None:
            alerts.append({"inst": inst, "gap": gap, "meetings": fund_meetings})
    if not alerts:
        return

    ui.label("🔔 Repeat Meeting Alerts — Investigate Signal").classes("font-bold").style(f"color:{COLORS['text_heading']};")
    for alert in alerts:
        inst, gap, meetings = alert["inst"], alert["gap"], alert["meetings"]
        last_m, prev_m = meetings[0], meetings[1]
        outcome = last_m.get("Outcome", "")
        qoq = inst.get("QoQ_Change", 0)
        # Was: solid fixed-dark background per status (e.g. "#173321") plus
        # hardcoded light body text ("#E2E8F0"/"#94A3B8") — same leftover-
        # dark-theme pattern as _tier_card above, illegible/mismatched under
        # the active CREAM (light) theme. Now a light card with a colored
        # left border for the status, and theme-token text throughout.
        if qoq > 0:
            sig_icon, sig_txt, sig_clr = "🟢", "Likely diligence — shares increasing", COLORS["positive"]
        elif "positive" in outcome.lower() or "interested" in outcome.lower():
            sig_icon, sig_txt, sig_clr = "🟡", "Monitor — positive tone but verify intent", COLORS["warning"]
        elif qoq < 0:
            sig_icon, sig_txt, sig_clr = "🔴", "Flag — shares declining, possible exit diligence", COLORS["negative"]
        else:
            sig_icon, sig_txt, sig_clr = "🟡", "Unknown intent — escalate to CFO for next call", COLORS["warning"]

        ui.html(
            f"<div style='border:1px solid {COLORS['border']};border-left:4px solid {sig_clr};border-radius:8px;"
            f"padding:10px 14px;background:{COLORS['surface_bg']};margin-bottom:8px;'>"
            f"<div style='display:flex;justify-content:space-between;align-items:center;'>"
            f"<div style='color:{COLORS['text_heading']};'><b>{inst['Fund']}</b> requested a second meeting in <b>{gap} days</b> (within 45-day window)</div>"
            f"<span style='font-weight:600;color:{sig_clr};'>{sig_icon} {sig_txt}</span></div>"
            f"<div style='font-size:13px;color:{COLORS['text_muted']};margin-top:4px;'>"
            f"First: {prev_m['Date']} ({prev_m['Type']}) · Last: {last_m['Date']} ({last_m['Type']}) · "
            f"Last outcome: {last_m.get('Outcome','—')}</div></div>"
        )
    ui.markdown("---")


def _tier_card(institutions, label, action, accent_color):
    # Was: solid fixed-dark background (e.g. "#173321") + a fixed light
    # text_color passed in per call site — designed for the old dark theme.
    # Under the now-active CREAM (light) theme, COLORS['text_heading'] /
    # COLORS['text_muted'] resolve to near-black, which is illegible against
    # those leftover dark literals — same root cause as the earlier Earnings
    # stage-card contrast bug. Fixed the same way _institution_card already
    # does it below: theme-aware light card background + a colored left
    # border for the tier accent, so every text color in here can just use
    # the normal theme tokens and stay correct under either theme.
    with ui.card().classes("flex-1").style(
        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:4px solid {accent_color};"):
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-0"):
                ui.label(label).style(f"color:{accent_color};font-weight:bold;")
                ui.label(action).style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(str(len(institutions))).classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
        if institutions:
            with ui.expansion(f"Show {len(institutions)} institution(s)").classes("w-full"):
                for inst in institutions:
                    ui.label(f"{inst['Fund']} — {inst['Engagement_Score']}/100").style(f"color:{COLORS['text_body']};font-size:12px;")


def _institution_card(inst, meeting_log, contacts):
    fund_meetings = _get_fund_meetings(meeting_log, inst["Fund"])
    repeat_gap = _get_repeat_signal(fund_meetings)
    score = inst["Engagement_Score"]
    holder_badge = "✅ Current Holder" if inst["USIO_Holder"] else "🆕 Non-Holder"
    qoq_str = f"{inst['QoQ_Change']:+,}" if inst["QoQ_Change"] else "—"
    shares_str = f"{inst['Shares']:,}" if inst["Shares"] else "—"

    border_clr = "#F9A825" if repeat_gap else COLORS["border"]
    # Today's Investor Pipeline widget (top_engagement_targets) drops any
    # fund contacted within the last 7 days from its top-5, so it can look
    # "out of order" compared to this full list unless it's clear why a
    # given fund isn't showing up there — this badge makes that visible
    # here instead of the two pages silently disagreeing.
    days_contacted = _days_since_last_contact(inst["Fund"], meeting_log)
    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {border_clr};"):
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-0"):
                ownership_badge = "⚙️ Passive" if inst.get("Ownership_Style") == "Passive" else "🎯 Active"
                ui.label(f"{inst['Fund']}  ·  {inst['Type']}  ·  AUM {inst['AUM']}").classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:14px;")
                ui.label(f"📍 {inst['Metro']}  ·  🔄 {inst['Turnover_Style']}  ·  {ownership_badge}  ·  {holder_badge}").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
                if repeat_gap is not None:
                    ui.label(f"🔔 Repeat meeting in {repeat_gap}d").style(f"color:#FB923C;font-size:12px;font-weight:bold;")
                if days_contacted is not None and days_contacted <= 7:
                    ui.label(f"📞 Contacted {days_contacted}d ago — off Today's Investor Pipeline until day 8").style(
                        f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")
            with ui.column().classes("items-center"):
                ui.label(str(score)).classes("text-2xl font-bold").style(f"color:{COLORS['accent_light']};")
                ui.label("/100").style(f"color:{COLORS['text_muted']};font-size:10px;")

        with ui.row().classes("w-full gap-6").style("margin-top:6px;"):
            ui.label(f"Shares: {shares_str}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(f"QoQ: {qoq_str}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(f"Q1 call: {'✅ ' + inst['Listen_Duration'] if inst['Call_Listener'] else '⭕ Did not listen'}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(f"IR visits (30d): {inst['IR_Visits_30d']} · {inst['Last_Visit']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
        # ✅ marks a peer holding confirmed by a real SEC 13F filing (see
        # _enrich_peer_holdings_with_live_13f); an unmarked ticker is still
        # the original hand-typed seed guess — that ticker hasn't been
        # 13F-refreshed yet (SEC Intelligence tab's "Refresh 13F
        # Institutional Holders" button).
        _peer_src = inst.get("Peer_Holdings_Source", {})
        _peer_labels = [t + (" ✅" if _peer_src.get(t) == "live" else "") for t in inst["Peer_Holdings"]]
        ui.label(f"Peers held: {', '.join(_peer_labels) or '—'}").style(f"color:{COLORS['text_muted']};font-size:12px;")
        ui.label(f"Action: {inst['Action']}").style(f"color:{COLORS['accent_light']};font-size:12px;font-weight:bold;")

        contact = contacts.get(inst["Fund"], {})
        with ui.row().classes("gap-3 items-center").style("margin-top:6px;"):
            if contact.get("email"):
                _mailto(contact["email"], f"{CT('ticker')} — Following up, {inst['Fund']}", "Hi,\n\n", f"Email {contact.get('name','Contact')}")
            ui.button("📝 Draft Pre-Earnings Outreach", on_click=lambda inst=inst, contact=contact: _open_outreach_dialog(inst, contact)).props("flat dense")
            ui.button(f"📅 Meeting Log ({len(fund_meetings)})", on_click=lambda inst=inst, fm=fund_meetings, rg=repeat_gap: _open_meeting_log_dialog(inst, fm, rg)).props("flat dense")


def _open_outreach_dialog(inst, contact):
    peer_lookup = {p["ticker"]: p for p in CP()}
    usio_ev_rev = _client_ev_rev()
    peer_lines = []
    for tkr in inst["Peer_Holdings"]:
        p = peer_lookup.get(tkr)
        if p and p.get("ev_rev") and usio_ev_rev:
            disc = round(p["ev_rev"] / usio_ev_rev, 1)
            peer_lines.append(f"Since {inst['Fund']} holds {tkr} ({p['name']}), you might want to look at our latest "
                               f"numbers — {CT('ticker')} trades at {usio_ev_rev}x EV/Revenue vs {tkr} at {p['ev_rev']}x, "
                               f"roughly a {disc}x discount for comparable economics.")
        else:
            peer_lines.append(f"Since {inst['Fund']} holds {tkr}, our upcoming print is worth a look given the sector re-rating setup.")
    if not peer_lines:
        peer_lines = [f"{CT('ticker')}'s upcoming print is shaping up as a re-rating catalyst — EPS inflection, "
                       "multiple expansion, and analyst coverage resumption all in view."]
    engagement_line = (f"Given {inst['Fund']}'s "
                        f"{('attention to the call replay (' + inst['Listen_Duration'] + ')') if inst['Call_Listener'] else 'recent interest in our materials'} "
                        f"and {inst['IR_Visits_30d']} IR site visit(s) in the last 30 days, this feels like the right moment to reconnect ahead of the print.")
    greeting = contact.get("name", "[Contact Name]").split()[0] if contact.get("name") else "[Contact Name]"
    subject = f"{CT('ticker')} Pre-Earnings Note — {inst['Fund']}"
    body = (f"Hi {greeting},\n\n{peer_lines[0]}\n" + "\n".join(peer_lines[1:]) + f"\n\n{engagement_line}\n\n"
            f"{CI().get('name','')}\n{CI().get('title','')} · {CT('name')} (NASDAQ: {CT('ticker')})")

    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:480px;"):
        ui.label(f"Draft Outreach — {inst['Fund']}").classes("text-lg font-bold")
        ui.textarea(value=body).classes("w-full").props("rows=12")
        to_email = contact.get("email", "")
        if to_email:
            _mailto(to_email, subject, body, f"Email {contact.get('name','Contact')}")
        else:
            ui.label("No email on file for this contact yet.").style(f"color:{COLORS['text_muted']};font-size:12px;")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


def _open_meeting_log_dialog(inst, fund_meetings, repeat_gap):
    with ui.dialog() as dialog, ui.card().style(f"background:{COLORS['surface_bg']};min-width:480px;"):
        ui.label(f"Meeting Log — {inst['Fund']}").classes("text-lg font-bold")
        if repeat_gap is not None:
            qoq = inst.get("QoQ_Change", 0)
            if qoq > 0:
                ui.label(f"🟢 Likely diligence — shares +{qoq:,} and repeat meeting in {repeat_gap}d. Escalate to CFO.").style("color:#4ADE80;font-size:12px;")
            elif qoq < 0:
                ui.label(f"🔴 Flag — shares {qoq:,} and repeat meeting in {repeat_gap}d. Possible pre-exit diligence.").style("color:#F87171;font-size:12px;")
            else:
                ui.label(f"🟡 Intent unclear — repeat meeting in {repeat_gap}d, no share change. Ask directly.").style("color:#F0A830;font-size:12px;")

        if fund_meetings:
            for mtg in fund_meetings:
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};"):
                    ui.label(f"{mtg['Date']} · {mtg['Type']} — {mtg.get('Outcome','—')}").classes("font-bold").style("font-size:12.5px;")
                    ui.label(f"Attendees: {mtg.get('Attendees','—')}").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
                    ui.label(f"Notes: {mtg.get('Notes','—')}").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
                    if mtg.get("Logged By"):
                        ui.label(f"Logged by: {mtg['Logged By']}").style(f"color:{COLORS['text_muted']};font-size:10.5px;font-style:italic;")
        else:
            ui.label("No meetings logged yet.").style(f"color:{COLORS['text_muted']};font-size:12px;")

        # Pre-fill attendees from the known contact on file for this
        # institution, if there is one — previously always blank, which
        # meant re-typing a name that's already stored in
        # institution_contacts.py on every single meeting.
        known_contact = get_institution_contacts().get(inst["Fund"], {})
        default_attendees = known_contact.get("name", "")

        # "Logged by" is auto-filled from this client's own IR contact
        # (config.client_config.CI()) rather than a free-text field — there's
        # no multi-user login in this app yet, so the configured IR contact
        # is the closest available notion of "who is using this session."
        logged_by = CI().get("name") or "IR Team"

        ui.markdown("**➕ Log a new meeting**")
        m_date = ui.input("Date (YYYY-MM-DD)", value=datetime.now().strftime("%Y-%m-%d")).classes("w-full")
        m_type = ui.select(["1x1 — Investor Conference", "Intro call", "Follow-up call", "NDR meeting",
                             "Earnings call Q&A", "Other"], label="Meeting Type", value="Follow-up call").classes("w-full")
        m_attend = ui.input("Attendees", value=default_attendees).classes("w-full")
        m_notes = ui.textarea("Notes").classes("w-full")
        m_outcome = ui.select(["Positive — follow up", "Neutral — maintain", "Warm — send materials",
                                "Flag — possible exit", "CFO follow-up required", "No clear signal"],
                               label="Meeting Outcome (scored)", value="Positive — follow up").classes("w-full")
        ui.label(f"Outcome feeds this fund's Interaction Score (0–{INTERACTION_SCORE_MAX} pts of the 100-pt "
                 "Engagement Score) — a positive/CFO-escalation outcome raises it, a Flag lowers it.") \
            .style(f"color:{COLORS['text_muted']};font-size:11px;")
        ui.label(f"Logging as: {logged_by}").style(f"color:{COLORS['text_muted']};font-size:11px;")

        def log_meeting():
            log = _load_meeting_log()
            log.append({"Fund": inst["Fund"], "Date": m_date.value, "Type": m_type.value,
                        "Attendees": m_attend.value, "Notes": m_notes.value, "Outcome": m_outcome.value,
                        "Logged By": logged_by, "Source": "Manual"})
            _save_meeting_log(log)
            # Interaction Score is derived fresh from meeting_log on every
            # render (see _compute_interaction_score / _score_institutions),
            # so this recomputes what it will actually be on next render —
            # a real persisted number, not the old ephemeral same-render-only
            # "+20 repeat meeting" flash that never got saved anywhere.
            updated = _get_fund_meetings(log, inst["Fund"])
            new_interaction = _compute_interaction_score(updated)
            old_interaction = inst.get("Interaction_Score", 0)
            new_engagement = min(100, inst["Engagement_Score"] - old_interaction + new_interaction)
            new_gap = _get_repeat_signal(updated)
            delta = new_interaction - old_interaction
            delta_str = f"+{delta}" if delta >= 0 else str(delta)
            if new_gap is not None:
                ui.notify(f"⚠️ Repeat meeting alert — {inst['Fund']} met {len(updated)}x in {new_gap}d. "
                          f"Interaction Score {delta_str} → {new_interaction}/{INTERACTION_SCORE_MAX} · "
                          f"Engagement Score → {new_engagement}/100", type="warning")
            else:
                ui.notify(f"✅ Meeting logged for {inst['Fund']} · Interaction Score {delta_str} → "
                          f"{new_interaction}/{INTERACTION_SCORE_MAX} · Engagement Score → {new_engagement}/100")
            dialog.close()
            _refresh()

        ui.button("📅 Log Meeting", on_click=log_meeting).props("color=primary")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


# ─────────────────────────────────────────────────────────────────────────
# NDR Planner tab
# ─────────────────────────────────────────────────────────────────────────
def _build_ndr_itinerary(trip, ticker):
    lines = [f"{ticker} — NON-DEAL ROADSHOW ITINERARY", trip["name"],
              f"{trip['dates']}  ·  {trip['city']}  ·  {'Virtual' if trip['ndr_type']=='virtual' else 'In-Person'}"]
    if trip.get("sponsor_bank"):
        lines.append(f"Sponsoring Bank: {trip['sponsor_bank']}")
    lines.append(f"Attendees: {', '.join(trip.get('team', [])) or '—'}")
    lines.append(f"Focus: {trip.get('focus','—')}")
    if trip.get("notes"):
        lines.append(f"Trip Objectives: {trip['notes']}")
    lines.append("=" * 64)
    # Grouped by day (falls back to a single unlabeled block for meetings
    # added the old way, before the "day" field existed — see
    # _render_ndr_tab's schema-upgrade note below).
    by_day = {}
    for m in trip.get("meetings", []):
        by_day.setdefault(m.get("day", 1), []).append(m)
    for day_num in sorted(by_day.keys()):
        if len(by_day) > 1:
            lines.append(f"DAY {day_num}")
            lines.append("-" * 64)
        for m in by_day[day_num]:
            tag = "Non-Holder — Priority Target" if m.get("non_holder", True) else "Existing Holder"
            time_lbl = m.get("time") or "—"
            lines.append(f"  {time_lbl:>10}   {m.get('institution','')}")
            if m.get("score") is not None:
                lines.append(f"              {m.get('format','In-person')} · {tag} · Engagement Score {m['score']}/100")
            else:
                lines.append(f"              {m.get('format','In-person')} · {tag}")
            if m.get("notes"):
                lines.append(f"              Note: {m['notes']}")
    lines.append("=" * 64)
    lines.append(f"Prepared {datetime.now().strftime('%b %d, %Y')}")
    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────
# NDR target auto-suggestion — real institutions instead of a hardcoded
# 25-row USIO-specific database (app.py's INST_DB). Reuses the SAME
# per-client institutions list (core.investor_scoring.score_institutions
# output, computed once in render_investors_page() and threaded down here)
# that Buy-Side Intelligence and Target Database already read, so "who's a
# good NDR target in Boston" is always the same live answer as "who's a
# good prospect in Boston" everywhere else on this page — no second,
# drifting copy of the tracked-institution universe to maintain.
# ─────────────────────────────────────────────────────────────────────────
def _ndr_location_options(institutions):
    """Metro-region labels straight from the live institutions list, not a
    hardcoded city list — stays correct for whatever a given client
    actually has tracked, matching the same Metro values already used by
    the NDR Requests tab's metro dropdown and the Big Picture panel's
    Metro Priority scoring."""
    return sorted({i["Metro"] for i in institutions})


def _ndr_target_candidates(institutions, location, ndr_type):
    """Port of app.py's get_institutions_for_location, onto real per-client
    data. In-person: exact match on Metro (the institutions list already
    stores metro-REGION labels like 'Boston / New England', not raw
    cities, so no fuzzy city->region translation table is needed the way
    app.py's INST_DB required). Virtual: every non-holder scoring >=40
    anywhere — same threshold app.py used, since a virtual trip isn't
    geography-bound. Non-holders are sorted first (conversion is the
    point of an NDR), holders after (relationship maintenance)."""
    if ndr_type == "virtual":
        candidates = [i for i in institutions if not i["USIO_Holder"] and i["Engagement_Score"] >= 40]
    else:
        candidates = [i for i in institutions if i["Metro"] == location]
    non_holders = sorted([i for i in candidates if not i["USIO_Holder"]], key=lambda x: -x["Engagement_Score"])
    holders = sorted([i for i in candidates if i["USIO_Holder"]], key=lambda x: -x["Engagement_Score"])
    return non_holders + holders


def _last_city_visit(trips, city):
    past = [t for t in trips if str(t.get("city", "")).lower() == str(city).lower()]
    if not past:
        return None
    past.sort(key=lambda t: t.get("created", ""), reverse=True)
    return past[0]


def _ndr_talking_points(inst):
    """Grounded in THIS fund's own real tracked fields (Action, Conviction,
    Peer_Holdings, Call_Listener, Engagement_Score) rather than app.py's
    hardcoded per-peer financial claims (specific EV/Revenue multiples,
    margin comparisons keyed to literal ticker strings like 'GDOT'/'PRTH'
    baked into if/elif branches). Those were real, true facts for one
    specific client at one specific moment — porting them verbatim would
    mean every future client (or even the same client next quarter) sees
    stale, misattributed numbers presented as current talking points.
    Same 'honest, disclosed approximation over fabricated precision'
    philosophy as core/fit_score.py's turnover/contactability heuristics."""
    points = []
    if inst.get("Action"):
        points.append(inst["Action"])
    if inst.get("Peer_Holdings"):
        points.append(f"Owns {', '.join(inst['Peer_Holdings'])} — draw the direct comparison to those peers' "
                       f"positioning rather than starting from a blank slate.")
    if inst.get("Call_Listener") and inst.get("Listen_Duration"):
        points.append(f"Listened to the last earnings call ({inst['Listen_Duration']}) — reference the specific "
                       f"moments they engaged with instead of re-covering the whole deck.")
    if inst.get("Engagement_Score", 0) >= 80:
        points.append(f"Top-tier engagement score ({inst['Engagement_Score']}/100) — this is a "
                       f"{'defend' if inst.get('USIO_Holder') else 'high-priority conversion'} meeting, not a cold intro.")
    if inst.get("Conviction"):
        points.append(f"Conviction on file: {inst['Conviction']}.")
    if not points:
        points.append("No prior signal on file yet — treat as a discovery meeting: confirm mandate fit before "
                       "going deep on the thesis.")
    return points


def _render_ndr_tab(institutions, meeting_log, client_id):
    with ui.tabs().classes("w-full") as ndr_tabs:
        nt1 = ui.tab("🗺️ Plan New NDR")
        nt2 = ui.tab("📋 Active NDRs")
        nt3 = ui.tab("📨 Requests")
        nt4 = ui.tab("📄 Prep Cards")
        nt5 = ui.tab("📊 Post-NDR Debrief")
    with ui.tab_panels(ndr_tabs, value=nt1).classes("w-full"):
        with ui.tab_panel(nt1):
            ui.label("Plan a New Non-Deal Roadshow").classes("font-bold")
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    name_in = ui.input("NDR name / label", placeholder="Post-Q2 Boston NDR").classes("w-full")
                    bank_options = [f"{a['firm']} — {a['name']}" for a in CA()] + ["Other / Non-Covering Bank"]
                    sponsor_in = ui.select(bank_options, value=bank_options[0]).classes("w-full").props("label='Sponsoring Bank'")
                    dates_in = ui.input("Dates", placeholder="e.g. Aug 20-21, 2026").classes("w-full")
                    type_in = ui.toggle({"in_person": "✈️ In-Person", "virtual": "💻 Virtual"}, value="in_person")
                    # Combo box over the real, live Metro labels (same ones the NDR
                    # Requests tab and Big Picture's Metro Priority scoring already
                    # use) — with_input still allows typing a city that isn't in the
                    # tracked list yet; it just won't have any auto-suggested targets.
                    city_in = ui.select(_ndr_location_options(institutions), label="City / Region", with_input=True) \
                        .classes("w-full").props("use-input hide-selected fill-input input-debounce=0 new-value-mode=add-unique")
                with ui.column().classes("flex-1"):
                    focus_in = ui.select([
                        "Post-earnings — deliver results story", "Pre-earnings — build anticipation",
                        "New institution discovery", "Existing holder relationship maintenance",
                        "Analyst initiation support", "Other",
                    ], value="Post-earnings — deliver results story").classes("w-full").props("label='NDR focus'")
                    team_in = ui.select([f"{v['name']} ({k})" for k, v in CT("executives", {}).items()] + [CI().get("name", "")],
                                         multiple=True).classes("w-full").props("label='Attendees'")
                    notes_in = ui.textarea("Trip objectives", placeholder="e.g. Re-introduce to Putnam. Get Fidelity Small Cap on record post-print.").classes("w-full")
                    with ui.row().classes("w-full gap-3"):
                        days_in = ui.number("Days", value=1, min=1, max=3).classes("flex-1")
                        slots_in = ui.number("Meetings per day", value=5, min=3, max=10).classes("flex-1")

            # ── Auto-suggested targets — real tracked institutions instead of
            # app.py's hardcoded 25-row database (see _ndr_target_candidates).
            # Rebuilds whenever city/type/days/slots change, since all four
            # affect either WHICH institutions qualify or WHICH ones default-
            # check; a stale grid left over from a prior city selection would
            # silently mis-target the whole trip. ──────────────────────────
            ui.markdown("---")
            ui.label("Recommended targets").classes("font-bold")
            targets_caption = ui.label(
                "Geographically matched, non-holders prioritized. Pick a city/region above (or Virtual) to see candidates."
            ).style(f"color:{COLORS['text_muted']};font-size:11.5px;")
            target_checks = {}  # Fund name -> (checkbox, institution dict) — read by save_trip()

            def rebuild_targets(e=None):
                targets_area.clear()
                target_checks.clear()
                ndr_type = type_in.value
                location = (city_in.value or "").strip() if ndr_type == "in_person" else "Virtual"
                with targets_area:
                    if ndr_type == "in_person" and not location:
                        return
                    if ndr_type == "in_person":
                        prior = _last_city_visit(_load_json("ndr_trips.json", []), location)
                        if prior:
                            ui.label(f"📍 Last time in {location}: {prior.get('dates','—')} — \"{prior.get('name','')}\" "
                                      f"({len(prior.get('meetings', []))} meeting(s) scheduled).").style(
                                f"color:{COLORS['text_muted']};font-size:11.5px;margin-bottom:4px;")
                        else:
                            ui.label(f"📍 No prior NDR trip on file to {location} — this would be a first visit.").style(
                                f"color:{COLORS['text_muted']};font-size:11.5px;margin-bottom:4px;")
                    candidates = _ndr_target_candidates(institutions, location, ndr_type)
                    if not candidates:
                        ui.label(f"No tracked institutions {'score >=40 for virtual outreach' if ndr_type == 'virtual' else f'in {location}'} yet — "
                                  "add prospects via Target Database or Buy-Side Intelligence first, or add meetings to this trip "
                                  "by hand from the Active NDRs tab.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                        return
                    n_non = sum(1 for i in candidates if not i["USIO_Holder"])
                    max_auto = int((days_in.value or 1) * (slots_in.value or 5))
                    ui.label(f"{len(candidates)} tracked institution(s) — {n_non} non-holder(s) prioritized, "
                              f"{len(candidates) - n_non} existing holder(s). Top {min(max_auto, n_non)} non-holder(s) pre-checked "
                              f"for {int(days_in.value or 1)} day(s) × {int(slots_in.value or 5)} meeting(s)/day.").style(
                        f"color:{COLORS['text_muted']};font-size:11.5px;margin-bottom:6px;")
                    with ui.row().classes("w-full gap-3"):
                        col_a = ui.column().classes("flex-1 gap-2")
                        col_b = ui.column().classes("flex-1 gap-2")
                    cols = [col_a, col_b]
                    for idx, inst in enumerate(candidates):
                        default_check = idx < max_auto and not inst["USIO_Holder"]
                        days_since = _days_since_last_contact(inst["Fund"], meeting_log)
                        border_clr = "#4ADE80" if inst["Engagement_Score"] >= 80 else "#F0A830" if inst["Engagement_Score"] >= 50 else "#94A3B8"
                        with cols[idx % 2]:
                            with ui.row().classes("w-full items-start gap-2").style(
                                    f"background:{COLORS['surface_hover_bg']};border-left:3px solid {border_clr};"
                                    f"border-radius:8px;padding:8px 10px;"):
                                cb = ui.checkbox(value=default_check)
                                with ui.column().classes("gap-0"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.label(inst["Fund"]).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                                        ui.label(str(inst["Engagement_Score"])).style(
                                            f"background:{border_clr}22;color:{border_clr};font-size:11px;font-weight:700;"
                                            f"padding:1px 6px;border-radius:5px;")
                                    ui.label(f"{inst['Metro']} · {'✅ Holder' if inst['USIO_Holder'] else '🆕 Non-holder'} · {inst.get('Type','—')}").style(
                                        f"color:{COLORS['text_muted']};font-size:11px;")
                                    ui.label(f"🤝 Contacted {days_since}d ago" if days_since is not None else "🤝 No prior contact logged").style(
                                        f"color:{COLORS['text_muted']};font-size:10.5px;")
                            target_checks[inst["Fund"]] = (cb, inst)

            targets_area = ui.column().classes("w-full")
            city_in.on_value_change(rebuild_targets)
            type_in.on_value_change(rebuild_targets)
            days_in.on_value_change(rebuild_targets)
            slots_in.on_value_change(rebuild_targets)
            rebuild_targets()

            def save_trip():
                if not name_in.value:
                    ui.notify("NDR name is required.", type="warning")
                    return
                selected = [(name, inst) for name, (cb, inst) in target_checks.items() if cb.value]
                days = int(days_in.value or 1)
                slots = max(1, int(slots_in.value or 5))
                meetings = []
                for idx, (fund_name, inst) in enumerate(selected):
                    day = idx // slots + 1
                    slot_in_day = idx % slots
                    hr = 9 + slot_in_day * 90 // 60
                    mn = (slot_in_day * 90) % 60
                    hr12 = hr if hr <= 12 else hr - 12
                    time_label = f"{hr12 or 12}:{mn:02d} {'AM' if hr < 12 else 'PM'}"
                    meetings.append({
                        "institution": fund_name, "day": day, "time": time_label,
                        "type": "virtual" if type_in.value == "virtual" else "1x1",
                        "format": "Zoom" if type_in.value == "virtual" else "In-person",
                        "status": "scheduled", "notes": inst.get("Action", ""),
                        "non_holder": not inst["USIO_Holder"], "score": inst["Engagement_Score"], "contact": "",
                    })
                trips = _load_json("ndr_trips.json", [])
                trips.append({
                    "name": name_in.value, "sponsor_bank": sponsor_in.value, "dates": dates_in.value or "TBD",
                    "ndr_type": type_in.value, "city": city_in.value or ("Virtual" if type_in.value == "virtual" else "TBD"),
                    "focus": focus_in.value, "team": team_in.value or [], "notes": notes_in.value,
                    "meetings": meetings, "status": "Planning", "debrief": {},
                    "created": datetime.now().strftime("%Y-%m-%d"),
                })
                _save_json("ndr_trips.json", trips)
                n_non = sum(1 for _, i in selected if not i["USIO_Holder"])
                ui.notify(f"NDR '{name_in.value}' created — {len(selected)} meeting(s) scheduled "
                          f"({n_non} non-holders, {len(selected) - n_non} holders) across {days} day(s).")
                _refresh()

            ui.button("✈️ Create NDR Trip", on_click=save_trip).props("color=primary").style("margin-top:8px;")

        with ui.tab_panel(nt2):
            trips = _load_json("ndr_trips.json", [])
            if not trips:
                ui.label("No NDR trips logged yet.").style(f"color:{COLORS['text_muted']};")
            status_options = ["scheduled", "completed", "cancelled", "no-show"]
            for idx, trip in enumerate(trips):
                all_meetings = trip.get("meetings", [])
                real_meetings = [m for m in all_meetings if m.get("type") != "break"]
                done_m = sum(1 for m in real_meetings if m.get("status") == "completed")
                non_h = sum(1 for m in real_meetings if m.get("non_holder", True))
                trip_status = trip.get("status", "Planning")
                status_icon = {"Planning": "🟡", "In Progress": "🔵", "Completed": "🟢"}.get(trip_status, "🟡")
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                    with ui.row().classes("w-full justify-between items-start"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"{status_icon} {trip['name']}").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                            ui.label(f"{trip['dates']} · {trip['city']} · {'Virtual' if trip['ndr_type']=='virtual' else 'In-Person'} · Sponsor: {trip.get('sponsor_bank','—')}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                            ui.label(f"Focus: {trip.get('focus','—')} · Attendees: {', '.join(trip.get('team',[])) or '—'}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                            if trip.get("notes"):
                                ui.label(f"Objectives: {trip['notes']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                        with ui.column().classes("items-end gap-1"):
                            ui.label(f"{done_m}/{len(real_meetings)} completed · {non_h} non-holder(s)").style(f"color:{COLORS['accent_light']};font-size:12px;")

                            def set_trip_status(e, idx=idx):
                                trips_ = _load_json("ndr_trips.json", [])
                                trips_[idx]["status"] = e.value
                                _save_json("ndr_trips.json", trips_)
                                ui.notify(f"Trip marked {e.value}.")
                                _refresh()

                            ui.select(["Planning", "In Progress", "Completed"], value=trip_status,
                                      on_change=set_trip_status).props("dense outlined").classes("min-w-[130px]")

                    meetings_with_idx = sorted(enumerate(all_meetings), key=lambda x: (x[1].get("day", 1), x[0]))
                    current_day = None
                    for flat_idx, m in meetings_with_idx:
                        d = m.get("day", 1)
                        if d != current_day:
                            current_day = d
                            ui.label(f"Day {d}" if len(meetings_with_idx) and any(mm.get("day", 1) != 1 for _, mm in meetings_with_idx) else "Meetings").style(
                                f"color:{COLORS['text_muted']};font-size:11px;font-weight:700;margin-top:8px;")
                        nh_badge = "🆕" if m.get("non_holder", True) else "✅"
                        fmt_badge = "💻" if m.get("format") in ("Zoom", "Teams") else "🏢"
                        with ui.row().classes("w-full items-center gap-2").style(
                                f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:4px 8px;margin:2px 0;"):
                            ui.label(f"{fmt_badge} {m.get('time','—')}").style(f"color:{COLORS['text_muted']};font-size:11.5px;width:110px;")
                            ui.label(f"{nh_badge} {m.get('institution','')}").classes("flex-1").style(f"color:{COLORS['text_body']};font-size:12.5px;")
                            if m.get("score") is not None:
                                ui.label(f"{m['score']}/100").style(f"color:{COLORS['text_muted']};font-size:11px;")

                            def set_meeting_status(e, idx=idx, flat_idx=flat_idx):
                                trips_ = _load_json("ndr_trips.json", [])
                                trips_[idx]["meetings"][flat_idx]["status"] = e.value
                                _save_json("ndr_trips.json", trips_)
                                _refresh()

                            ui.select(status_options, value=m.get("status", "scheduled"),
                                      on_change=set_meeting_status).props("dense outlined").classes("min-w-[110px]")
                        if m.get("notes"):
                            ui.label(f"   💬 {m['notes']}").style(f"color:{COLORS['text_muted']};font-size:11px;margin-left:6px;")

                    with ui.expansion("➕ Add a meeting to this trip by hand").classes("w-full").style("margin-top:6px;"):
                        inst_in = ui.input("Institution").classes("w-full")
                        notes_m = ui.input("Notes").classes("w-full")

                        def add_meeting(idx=idx, inst_in=inst_in, notes_m=notes_m):
                            trips_ = _load_json("ndr_trips.json", [])
                            trips_[idx].setdefault("meetings", []).append({
                                "institution": inst_in.value, "notes": notes_m.value, "day": 1, "time": "—",
                                "type": "1x1", "format": "In-person", "status": "scheduled",
                                "non_holder": True, "score": None, "contact": "",
                            })
                            _save_json("ndr_trips.json", trips_)
                            ui.notify("Meeting added to trip.")
                            _refresh()

                        ui.button("Add", on_click=add_meeting).props("dense")

                    def download_itinerary(trip=trip):
                        ui.download(_build_ndr_itinerary(trip, CT("ticker")).encode(), filename=f"{trip['name'].replace(' ','_')}_itinerary.txt")

                    ui.button("⬇️ Export itinerary (.txt)", on_click=download_itinerary).props("flat dense").style("margin-top:6px;")

        with ui.tab_panel(nt3):
            _render_ndr_requests_tab()

        with ui.tab_panel(nt4):
            _render_ndr_prep_cards_tab(institutions, meeting_log)

        with ui.tab_panel(nt5):
            _render_ndr_debrief_tab()


def _render_ndr_requests_tab():
    ui.label("📨 Inbound NDR / Meeting Requests").classes("font-bold")
    ui.label(
        "Analyst requests to slot a management meeting into a city — feeds the Big Picture panel's Metro "
        "Priority scoring and 'This Week's Priority' recommendation above. Resolve a request once it's been "
        "scheduled (or declined) so it stops counting as open demand."
    ).style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    with ui.expansion("➕ Log a new request", value=False).classes("w-full"):
        with ui.row().classes("w-full gap-4"):
            r_analyst = ui.input("Analyst name *").classes("flex-1")
            bank_options = [a["firm"] for a in CA()] + ["Other / Non-Covering Bank"]
            r_firm = ui.select(bank_options, value=bank_options[0], label="Firm").classes("flex-1")
        with ui.row().classes("w-full gap-4"):
            r_city = ui.input("City *").classes("flex-1")
            r_metro = ui.select(sorted({i["Metro"] for i in get_seed_buyside_institutions(get_active_client_id())}),
                                 label="Metro region").classes("flex-1")
        r_reason = ui.textarea("Reason / context", placeholder="What did they ask for, and why?").classes("w-full")

        def log_request():
            if not (r_analyst.value and r_city.value):
                ui.notify("Analyst name and city are required.", type="warning")
                return
            reqs = _load_ndr_requests()
            reqs.append({
                "id": datetime.now().strftime("%Y%m%d%H%M%S"), "analyst": r_analyst.value, "firm": r_firm.value,
                "city": r_city.value, "metro": r_metro.value or r_city.value, "reason": r_reason.value or "—",
                "received": datetime.now().strftime("%b %d, %Y"), "resolved": False, "seeded": False,
            })
            _save_ndr_requests(reqs)
            ui.notify(f"Request from {r_analyst.value} logged.")
            _refresh()

        ui.button("💾 Log Request", on_click=log_request).props("color=primary")

    ui.markdown("---")
    reqs = _load_ndr_requests()
    open_reqs = [r for r in reqs if not r.get("resolved")]
    resolved_reqs = [r for r in reqs if r.get("resolved")]

    ui.label(f"{len(open_reqs)} open request(s)").classes("font-bold")
    if not open_reqs:
        ui.label("No open requests.").style(f"color:{COLORS['text_muted']};")
    for r in open_reqs:
        with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
            with ui.row().classes("w-full items-start justify-between"):
                with ui.column().classes("gap-0"):
                    seed_tag = " · example" if r.get("seeded") else ""
                    ui.label(f"{r['analyst']} ({r['firm']}) → {r['city']}{seed_tag}").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                    ui.label(f"Received {r['received']}").style(f"color:{COLORS['text_muted']};font-size:11px;")
                    ui.label(r["reason"]).style(f"color:{COLORS['text_body']};font-size:12px;")

                def mark_resolved(rid=r["id"]):
                    current = _load_ndr_requests()
                    for rr in current:
                        if rr["id"] == rid:
                            rr["resolved"] = True
                            rr["resolved_at"] = datetime.now().strftime("%b %d, %Y")
                    _save_ndr_requests(current)
                    ui.notify("Marked resolved.")
                    _refresh()

                ui.button("✅ Resolve", on_click=mark_resolved).props("flat dense")

    if resolved_reqs:
        with ui.expansion(f"✅ {len(resolved_reqs)} resolved").classes("w-full").style("margin-top:8px;"):
            for r in resolved_reqs:
                ui.label(f"{r['analyst']} ({r['firm']}) → {r['city']} · resolved {r.get('resolved_at','—')}").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")


# ─────────────────────────────────────────────────────────────────────────
# NDR — Prep Cards tab
# ─────────────────────────────────────────────────────────────────────────
def _render_ndr_prep_cards_tab(institutions, meeting_log):
    """Per-meeting prep cards for an NDR trip. Ported from app.py's Prep
    Cards tab, but the talking points are no longer hardcoded per-ticker
    (app.py branched on literal strings like `"GDOT" in inst_data["peer"]`,
    which only ever worked for USIO) — they're generated live from each
    institution's own tracked fields via _ndr_talking_points, so this works
    unchanged for any client's roster. A meeting whose institution isn't in
    the tracked list (added by hand, or a name typo) still gets a card, just
    without the institution-specific detail — it degrades gracefully instead
    of crashing or silently disappearing."""
    trips = _load_json("ndr_trips.json", [])
    if not trips:
        ui.label("No NDR trips yet — create one in Plan New NDR.").style(f"color:{COLORS['text_muted']};")
        return

    ui.label("📄 Meeting Prep Cards").classes("font-bold")
    ui.label("Pick a trip to generate a prep card per meeting — pulled live from tracked institution data.").style(
        f"color:{COLORS['text_muted']};font-size:11.5px;")

    trip_names = [t["name"] for t in trips]
    trip_sel = ui.select(trip_names, value=trip_names[-1], label="Trip").classes("w-full max-w-md")
    cards_area = ui.column().classes("w-full")

    inst_by_name = {i["Fund"]: i for i in institutions}

    def rebuild_cards(e=None):
        cards_area.clear()
        trip = next((t for t in trips if t["name"] == trip_sel.value), None)
        with cards_area:
            if not trip:
                return
            meetings = [m for m in trip.get("meetings", []) if m.get("type") != "break"]
            if not meetings:
                ui.label("No meetings on this trip yet.").style(f"color:{COLORS['text_muted']};")
                return
            meetings_sorted = sorted(enumerate(meetings), key=lambda x: (x[1].get("day", 1), x[0]))
            current_day = None
            for _, m in meetings_sorted:
                d = m.get("day", 1)
                if d != current_day:
                    current_day = d
                    ui.label(f"Day {d}").style(f"color:{COLORS['text_muted']};font-size:12px;font-weight:700;margin-top:10px;")
                inst = inst_by_name.get(m.get("institution", ""))
                fmt_badge = "💻" if m.get("format") in ("Zoom", "Teams") else "🏢"
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                    with ui.row().classes("w-full justify-between items-start"):
                        with ui.column().classes("gap-0"):
                            ui.label(f"{fmt_badge} {m.get('time','—')} — {m.get('institution','—')}").classes("font-bold").style(
                                f"color:{COLORS['text_heading']};")
                            if inst:
                                holder_tag = "✅ Existing holder" if inst["USIO_Holder"] else "🆕 Non-holder"
                                ui.label(f"{inst.get('Metro','—')} · {inst.get('Type','—')} · {holder_tag}").style(
                                    f"color:{COLORS['text_muted']};font-size:12px;")
                            else:
                                ui.label("Not in tracked institution list — added by hand.").style(
                                    f"color:{COLORS['text_muted']};font-size:12px;font-style:italic;")
                        if inst:
                            score = inst["Engagement_Score"]
                            score_clr = COLORS["positive"] if score >= 80 else COLORS["warning"] if score >= 50 else COLORS["text_muted"]
                            ui.label(f"{score}/100").style(f"color:{score_clr};font-size:16px;font-weight:700;")

                    days_since = _days_since_last_contact(m.get("institution", ""), meeting_log) if inst else None
                    if days_since is not None:
                        ui.label(f"🤝 Last contact: {days_since} day(s) ago").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

                    if m.get("notes"):
                        ui.label(f"💬 Strategy note: {m['notes']}").style(f"color:{COLORS['text_body']};font-size:12px;margin-top:4px;")

                    ui.label("Talking points").style(f"color:{COLORS['text_muted']};font-size:11px;font-weight:700;margin-top:6px;")
                    if inst:
                        for pt in _ndr_talking_points(inst):
                            ui.label(f"• {pt}").style(f"color:{COLORS['text_body']};font-size:12px;")
                    else:
                        ui.label("• No tracked signal on file — treat as a discovery meeting.").style(
                            f"color:{COLORS['text_body']};font-size:12px;")

    trip_sel.on_value_change(rebuild_cards)
    rebuild_cards()


# ─────────────────────────────────────────────────────────────────────────
# NDR — Post-NDR Debrief tab
# ─────────────────────────────────────────────────────────────────────────
def _render_ndr_debrief_tab():
    """Debrief form for a completed NDR trip. Ported from app.py, with one
    real enhancement: app.py's caption said "Key objections will feed into
    next Q&A prep" but never actually wired that anywhere — here, saving a
    debrief with a key objection or narrative gap calls
    risk_scorecard.log_ndr_objection(), which is what turns the Markets IR
    Risk Dashboard's "KPI Understanding" / "Investor Objection Trend" tiles
    from permanently-GRAY (no data source) to a real, disclosed YELLOW
    signal. Only trips marked Completed (Active NDRs tab) show up here —
    debriefing a trip that hasn't happened yet doesn't make sense."""
    trips = _load_json("ndr_trips.json", [])
    completed = [t for t in trips if t.get("status") == "Completed"]

    ui.label("📊 Post-NDR Debrief").classes("font-bold")
    if not completed:
        ui.label("No completed NDR trips yet — mark a trip \"Completed\" in Active NDRs once it wraps, "
                  "then debrief it here.").style(f"color:{COLORS['text_muted']};")
        return

    trip_names = [t["name"] for t in completed]
    trip_sel = ui.select(trip_names, value=trip_names[-1], label="Trip").classes("w-full max-w-md")
    form_area = ui.column().classes("w-full")

    def rebuild_form(e=None):
        form_area.clear()
        trip = next((t for t in completed if t["name"] == trip_sel.value), None)
        with form_area:
            if not trip:
                return
            meetings = [m for m in trip.get("meetings", []) if m.get("type") != "break"]
            debrief = trip.get("debrief", {})
            n_held = sum(1 for m in meetings if m.get("status") == "completed")

            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    held_in = ui.number("Meetings actually held", value=debrief.get("meetings_held", n_held), min=0).classes("w-full")
                    eff_in = ui.number("Effectiveness score (0-100)", value=debrief.get("effectiveness", 70), min=0, max=100).classes("w-full")
                    meeting_names = [m.get("institution", "") for m in meetings] or ["—"]
                    best_in = ui.select(meeting_names, value=debrief.get("best_meeting", meeting_names[0]),
                                         label="Best meeting").classes("w-full")
                with ui.column().classes("flex-1"):
                    follow_in = ui.textarea("Follow-ups needed", value=debrief.get("follow_ups", "")).classes("w-full")
                    new_pos_in = ui.textarea("New positions initiated (if known)", value=debrief.get("new_positions", "")).classes("w-full")

            ui.markdown("---")
            ui.label("Feeds the IR Risk Dashboard (Markets page) once saved:").style(f"color:{COLORS['text_muted']};font-size:11px;")
            with ui.row().classes("w-full gap-4"):
                objection_in = ui.textarea("Key objection heard", value=debrief.get("key_objection", ""),
                                            placeholder="e.g. \"Concerned about customer concentration in top 3 accounts.\"").classes("flex-1")
                gap_in = ui.textarea("Narrative gap (question the current deck/script doesn't answer)",
                                      value=debrief.get("narrative_gap", "")).classes("flex-1")
            next_in = ui.textarea("Next targets for this metro", value=debrief.get("next_targets", "")).classes("w-full")

            def save_debrief(trip_name=trip["name"]):
                trips_ = _load_json("ndr_trips.json", [])
                for t in trips_:
                    if t["name"] == trip_name:
                        t["debrief"] = {
                            "meetings_held": int(held_in.value or 0), "effectiveness": int(eff_in.value or 0),
                            "best_meeting": best_in.value, "follow_ups": follow_in.value,
                            "new_positions": new_pos_in.value, "key_objection": objection_in.value,
                            "narrative_gap": gap_in.value, "next_targets": next_in.value,
                            "saved_at": datetime.now().isoformat(),
                        }
                _save_json("ndr_trips.json", trips_)
                risk_scorecard.log_ndr_objection(trip_name=trip_name, objection=objection_in.value, narrative_gap=gap_in.value)
                ui.notify(f"Debrief saved for '{trip_name}'.")
                _refresh()

            ui.button("💾 Save Debrief", on_click=save_debrief).props("color=primary").style("margin-top:8px;")

            if debrief:
                ui.markdown("---")
                ui.label("Saved debrief").classes("font-bold")
                with ui.row().classes("w-full gap-3"):
                    _bp_metric("Meetings held", str(debrief.get("meetings_held", "—")), [])
                    _bp_metric("Effectiveness", f"{debrief.get('effectiveness', '—')}/100", [])
                    _bp_metric("Best meeting", debrief.get("best_meeting") or "—", [])
                if debrief.get("key_objection"):
                    ui.label(f"⚠️ Key objection: {debrief['key_objection']}").style(f"color:{COLORS['warning']};font-size:12px;margin-top:6px;")
                if debrief.get("narrative_gap"):
                    ui.label(f"📉 Narrative gap: {debrief['narrative_gap']}").style(f"color:{COLORS['warning']};font-size:12px;")
                if debrief.get("next_targets"):
                    ui.label(f"➡️ Next targets: {debrief['next_targets']}").style(f"color:{COLORS['accent_light']};font-size:12px;")

    trip_sel.on_value_change(rebuild_form)
    rebuild_form()


# ─────────────────────────────────────────────────────────────────────────
# Meeting Hub tab
# ─────────────────────────────────────────────────────────────────────────
def _render_meeting_hub_tab():
    scheduled = _load_json("scheduled_meetings.json", [])
    notes = _load_json("post_meeting_notes.json", [])
    today = datetime.now().date()

    # Firm lookup — union of every tracked institution (Buy-Side Intelligence)
    # and every institution with a known contact on file, so the dropdown
    # covers both "funds we're already scoring" and "funds we just have a
    # contact for." with_input + new-value-mode=add-unique makes this a
    # type-to-filter combo box that still accepts a firm that isn't in
    # either list yet (e.g. a brand-new prospect) rather than locking the
    # form to only known names.
    known_contacts = get_institution_contacts()
    firm_options = sorted({i["Fund"] for i in get_seed_buyside_institutions(get_active_client_id())}
                           | set(known_contacts.keys()))

    def _autofill_contact(e, contact_field):
        typed = (e.value or "").strip()
        if not typed:
            return
        info = known_contacts.get(typed)
        if not info:
            # The Firm combo box allows free text (new-value-mode=add-unique)
            # so it's the browser, not us, deciding whether a click on the
            # filtered suggestion or a plain blur/tab-out committed the
            # value — and a blur commits whatever's still typed (e.g.
            # "rutabaga") rather than snapping to the full matched option
            # ("Rutabaga Capital Management"), so an exact-key lookup alone
            # missed this case. Fall back to a case-insensitive, then
            # substring, match against the known contact list.
            typed_lower = typed.lower()
            info = next((v for k, v in known_contacts.items() if k.lower() == typed_lower), None)
            if not info:
                partial = [v for k, v in known_contacts.items() if typed_lower in k.lower()]
                info = partial[0] if len(partial) == 1 else None
        if info and not contact_field.value:
            contact_field.value = info["name"]

    with ui.tabs().classes("w-full") as hub_tabs:
        h1 = ui.tab("📅 Upcoming Meetings")
        h2 = ui.tab("➕ Schedule Meeting")
        h3 = ui.tab("📝 Post-Meeting Notes")
    with ui.tab_panels(hub_tabs, value=h1).classes("w-full"):
        with ui.tab_panel(h1):
            upcoming = sorted([m for m in scheduled if _safe_date(m["Date"]) >= today], key=lambda x: x["Date"])
            with ui.row().classes("w-full gap-3"):
                _hub_metric("Upcoming", len(upcoming))
                _hub_metric("Sell-side", sum(1 for m in upcoming if m["Side"] == "Sell-side"))
                _hub_metric("Buy-side", sum(1 for m in upcoming if m["Side"] == "Buy-side"))
                _hub_metric("Notes captured", len(notes))

            def sync_inbox():
                # "kind" tells mail_gateway who's who — sell-side analysts
                # (CA()) get their models/notes/NDR asks routed for review;
                # buy-side/institutional contacts are classified too (e.g.
                # "speak to management" requests) but never treated as a
                # model source. See core/mail_gateway.py's module docstring.
                contact_lookup = {}
                for firm_name, info in known_contacts.items():
                    if info.get("email"):
                        contact_lookup[info["email"].lower()] = {"name": info["name"], "firm": firm_name, "kind": "institution"}
                for a in CA():
                    if a.get("email"):
                        contact_lookup[a["email"].lower()] = {"name": a["name"], "firm": a.get("firm"), "kind": "analyst"}
                result = mail_gateway.sync_inbox(contact_lookup)
                if not result["ok"]:
                    ui.notify(f"📧 {result['message']}", type="warning")
                else:
                    n = len(result["messages"])
                    routed = sum(1 for m in result["messages"] if m.get("category") != "general")
                    if n:
                        extra = f" · {routed} item(s) flagged for review below" if routed else ""
                        ui.notify(f"📧 Synced — {n} message(s) from known contacts.{extra}")
                    else:
                        ui.notify("📧 Synced — no new messages from known contacts.")
                    _refresh()

            ui.button("🔄 Sync IR Inbox", on_click=sync_inbox).props("flat dense").style(
                f"color:{COLORS['accent_light']};font-size:12px;margin-top:4px;")
            if not mail_gateway.is_configured():
                ui.label("Email sync isn't configured yet (no IMAP credentials in .env) — this button will "
                          "explain that rather than pretend to have fetched anything.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;")

            _render_pending_inbox_items()

            if not upcoming:
                ui.label("No upcoming meetings scheduled.").style(f"color:{COLORS['text_muted']};")
            for mtg in upcoming:
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
                    ui.label(f"{mtg['Date']} {mtg.get('Time','')} — {mtg['Contact']} ({mtg['Firm']})").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                    ui.label(f"{mtg['Type']} · {mtg.get('Status','—')} · Priority: {mtg.get('Priority','—')}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    if mtg.get("Topic"):
                        ui.label(f"Topic: {mtg['Topic']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    _render_linked_documents(mtg["Contact"], mtg["Firm"])

        with ui.tab_panel(h2):
            ui.label("Schedule a New Meeting or Callback").classes("font-bold")
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    s_contact = ui.input("Contact name *").classes("w-full")
                    s_firm = ui.select(firm_options, label="Firm *", with_input=True).classes("w-full") \
                        .props("use-input hide-selected fill-input input-debounce=0 new-value-mode=add-unique")
                    s_firm.on_value_change(lambda e: _autofill_contact(e, s_contact))
                    s_side = ui.select(["Buy-side", "Sell-side"], value="Buy-side").classes("w-full")
                    s_priority = ui.select(["High", "Medium", "Low"], value="Medium").classes("w-full")
                with ui.column().classes("flex-1"):
                    s_date = ui.input("Date (YYYY-MM-DD)", value=(today + timedelta(days=7)).strftime("%Y-%m-%d")).classes("w-full")
                    s_time = ui.input("Time", placeholder="e.g. 2:00 PM ET").classes("w-full")
                    s_status = ui.select(["Confirmed", "Tentative", "Pending", "Requested"], value="Pending").classes("w-full")
                    s_type = ui.select(["Intro call", "Follow-up call", "1x1 — Investor Conference", "Model update call",
                                         "PT discussion", "NDR meeting", "Callback", "Earnings call Q&A", "Other"], value="Intro call").classes("w-full")
                s_topic = ui.textarea("Topic / agenda").classes("w-full")

            # Optional model/document attach — the file itself is held in
            # memory (pending_upload) until "Add to Meeting Queue" actually
            # creates the meeting record, so the saved document can be
            # linked to that meeting's id rather than floating unattached.
            pending_upload = {"filename": None, "content_type": None, "bytes": None}
            upload_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

            async def handle_model_upload(e):
                pending_upload["bytes"] = await e.file.read()
                pending_upload["filename"] = e.file.name
                pending_upload["content_type"] = e.file.type
                upload_status.text = f"📎 Attached: {e.file.name} — will be saved when you add this to the queue."
                upload_status.style(f"color:#4ADE80;font-size:11.5px;")

            ui.label("Attach the analyst's model or agenda doc (optional):").style(
                f"color:{COLORS['text_muted']};font-size:12px;margin-top:6px;")
            ui.upload(on_upload=handle_model_upload, auto_upload=True).props("flat").classes("w-full")

            def add_meeting():
                if not (s_contact.value and s_firm.value):
                    ui.notify("Contact and firm are required.", type="warning")
                    return
                meeting_id = str(uuid.uuid4())
                sched = _load_json("scheduled_meetings.json", [])
                sched.append({"id": meeting_id, "Contact": s_contact.value, "Firm": s_firm.value, "Side": s_side.value,
                              "Date": s_date.value, "Time": s_time.value, "Type": s_type.value,
                              "Topic": s_topic.value, "Status": s_status.value, "Priority": s_priority.value})
                _save_json("scheduled_meetings.json", sched)
                if pending_upload["bytes"]:
                    documents.save_document(
                        contact=s_contact.value, firm=s_firm.value, doc_type="model",
                        filename=pending_upload["filename"], file_bytes=pending_upload["bytes"],
                        content_type=pending_upload["content_type"], source="manual_upload",
                        uploaded_by=CI().get("name"), linked_meeting_id=meeting_id,
                    )
                ui.notify(f"{s_contact.value} at {s_firm.value} scheduled for {s_date.value}"
                          + (" — model attached" if pending_upload["bytes"] else ""))
                _refresh()

            ui.button("📅 Add to Meeting Queue", on_click=add_meeting).props("color=primary")

        with ui.tab_panel(h3):
            ui.label("Post-Meeting Note Capture — AI Structures Your Raw Notes").classes("font-bold")
            ui.label("Type your raw notes immediately after the call — an AI model organizes them into questions, concerns, signals, and actions.").style(f"color:{COLORS['text_muted']};font-size:12px;")
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    n_contact = ui.input("Contact name").classes("w-full")
                    n_firm = ui.select(firm_options, label="Firm", with_input=True).classes("w-full") \
                        .props("use-input hide-selected fill-input input-debounce=0 new-value-mode=add-unique")
                    n_firm.on_value_change(lambda e: _autofill_contact(e, n_contact))
                    n_side = ui.select(["Buy-side", "Sell-side"], label="Side", value="Buy-side").classes("w-full")
                    n_type = ui.select(["Intro call", "Follow-up call", "1x1 — Investor Conference",
                                         "Model update call", "Callback", "Other", "Remove"],
                                        label="Meeting Type", value="Intro call").classes("w-full")
                with ui.column().classes("flex-1"):
                    n_raw = ui.textarea("Raw notes", placeholder="Type exactly what you heard and said, no need to format").classes("w-full").props("rows=8")

                    # Topic chips — a blank textarea right after a call tends
                    # to get skipped or filled with two rushed sentences.
                    # These don't force structure (still one freeform box,
                    # since real calls don't happen in a fixed topic order)
                    # but nudge coverage of the financial topics that matter
                    # most, and the inserted headers also give the AI a much
                    # stronger signal to pull from than unlabeled prose.
                    ui.label("Click a topic to add it to your notes:").style(
                        f"color:{COLORS['text_muted']};font-size:11px;margin-top:2px;")
                    with ui.row().classes("gap-1.5").style("flex-wrap:wrap;"):
                        for topic in NOTE_TOPICS:
                            def _insert_topic(t=topic):
                                prefix = "\n" if n_raw.value and not n_raw.value.endswith("\n") else ""
                                n_raw.value = f"{n_raw.value}{prefix}{t}: "
                            ui.button(topic, on_click=_insert_topic).props("flat dense size=sm").style(
                                f"background:{COLORS['surface_hover_bg']};font-size:11px;padding:2px 8px;")

            n_pending_upload = {"filename": None, "content_type": None, "bytes": None}
            n_upload_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

            async def handle_note_upload(e):
                n_pending_upload["bytes"] = await e.file.read()
                n_pending_upload["filename"] = e.file.name
                n_pending_upload["content_type"] = e.file.type
                n_upload_status.text = f"📎 Attached: {e.file.name}"
                n_upload_status.style("color:#4ADE80;font-size:11.5px;")

            ui.label("Attach anything that came with this note (updated model, PDF, etc.) — optional:").style(
                f"color:{COLORS['text_muted']};font-size:12px;")
            ui.upload(on_upload=handle_note_upload, auto_upload=True).props("flat").classes("w-full")

            result_area = ui.column().classes("w-full")

            def structure_notes():
                if not (n_raw.value and n_contact.value):
                    ui.notify("Contact name and raw notes are required.", type="warning")
                    return
                ui.notify("Structuring notes...")
                structured = _structure_notes_with_ai(n_raw.value, n_contact.value, n_firm.value, n_type.value)
                all_notes = _load_json("post_meeting_notes.json", [])
                all_notes.append({"Contact": n_contact.value, "Firm": n_firm.value, "Side": n_side.value,
                                  "Date": today.strftime("%Y-%m-%d"), "Type": n_type.value, "Raw": n_raw.value,
                                  "Structured": structured})
                _save_json("post_meeting_notes.json", all_notes)
                if n_pending_upload["bytes"]:
                    documents.save_document(
                        contact=n_contact.value, firm=n_firm.value, doc_type="note_attachment",
                        filename=n_pending_upload["filename"], file_bytes=n_pending_upload["bytes"],
                        content_type=n_pending_upload["content_type"], source="manual_upload",
                        uploaded_by=CI().get("name"),
                    )
                result_area.clear()
                with result_area:
                    _render_structured_note(structured)
                ui.notify(f"✅ Submitted — notes saved for {n_contact.value} at {n_firm.value}"
                          + (" (with attachment)" if n_pending_upload["bytes"] else ""))

            ui.button("🤖 Structure Notes with AI", on_click=structure_notes).props("color=primary")
            ui.markdown("---")

            if notes:
                ui.label("Previous Meeting Notes").classes("font-bold")
                for note in sorted(notes, key=lambda x: x.get("Date", ""), reverse=True)[:10]:
                    structured = note.get("Structured", {})
                    sent = structured.get("sentiment", "—") if isinstance(structured, dict) else "—"
                    with ui.expansion(f"{note['Date']} · {note['Contact']} — {note['Firm']} · Sentiment: {sent}").classes("w-full"):
                        _render_structured_note(structured if isinstance(structured, dict) else {})


def _render_structured_note(structured):
    sent = structured.get("sentiment", "—")
    sent_clr = "#4ADE80" if sent == "Positive" else "#F87171" if sent == "Negative" else "#F0A830"
    ui.label(f"Sentiment: {sent}").style(f"color:{sent_clr};font-weight:bold;")
    if structured.get("summary"):
        ui.label(structured["summary"]).style(f"color:{COLORS['text_body']};font-size:13px;")
    for key, title in [("financial_kpi_takeaways", "📊 Financial/KPI takeaways"),
                        ("key_questions", "❓ Key questions"), ("positive_signals", "✅ Positive signals"),
                        ("concerns_raised", "⚠️ Concerns raised"), ("follow_up_actions", "📋 Follow-up actions"),
                        ("commitments_made", "🤝 Commitments made")]:
        items = structured.get(key)
        if items:
            ui.label(title).style("font-weight:bold;font-size:12.5px;margin-top:4px;")
            for it in items:
                ui.label(f"- {it}").style(f"color:{COLORS['text_muted']};font-size:12px;")


_CATEGORY_LABELS = {
    "model": "📊 Model", "research_note": "📄 Research Note", "ndr_request": "✈️ NDR Request",
    "conference_invite": "🎤 Conference Invite", "speak_to_management": "☎️ Speak to Management",
    "meeting_confirmation": "📅 Meeting Confirmation",
}


def _render_pending_inbox_items():
    """The human half of the email-routing pipeline: core/mail_gateway.py
    classifies an inbound email (model / research note / NDR request /
    conference invite / speak-to-management) and queues it here rath