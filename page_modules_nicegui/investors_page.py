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
    conference invite / speak-to-management) and queues it here rather than
    acting on an AI guess unattended (see core/email_classifier.py's
    docstring for why). One card per pending item, prefilled from whatever
    was extracted, with a category-appropriate confirm action:
      - model              -> core/consensus.py (Markets → Consensus Matrix)
      - research_note      -> CFA-lens breakdown (rating/PT, valuation method,
                              variant view, catalysts/risks, sentiment) so the
                              reviewer can decide fast whether it's worth
                              circulating further internally; optionally also
                              updates consensus if a rating/PT was extracted.
                              "Internal Use Only" is just a flag recorded on
                              the queue entry — actual forwarding is a manual
                              human decision, not something this app sends
                              (sell-side research is licensed content anyway).
      - ndr_request        -> this page's own Inbound NDR/Meeting Requests list
      - conference_invite  -> the Calendar's conference list
      - speak_to_management -> this page's Meeting Hub (Scheduled Meetings)
      - meeting_confirmation -> this page's Meeting Hub (Scheduled Meetings),
                              pre-filled Status "Confirmed" — replaces app.py's
                              old ad hoc IMAP-scan-with-password-prompt button
                              (see core/email_classifier.py's docstring)
    Every card also has Dismiss, for anything that turns out mis-tagged."""
    pending = inbox_queue.list_pending_items()
    if not pending:
        return

    current = consensus.get_consensus()
    firms_with_data = {a["firm"] for a in CA()}

    with ui.card().classes("w-full").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['accent']};margin-top:8px;"):
        ui.label(f"📋 Pending Inbox Items ({len(pending)})").classes("font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label("Classified and pre-filled from the email by AI where possible — review, correct if needed, "
                  "and confirm to send it where it belongs, or dismiss if it was mis-tagged.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")

        for item in pending:
            extracted = item.get("extracted") or {}
            category = item.get("category", "general")
            with ui.card().classes("w-full").style(f"background:{COLORS['canvas_bg']};border:1px solid {COLORS['border']};margin-top:6px;"):
                with ui.row().classes("w-full items-center justify-between"):
                    ui.label(f"{_CATEGORY_LABELS.get(category, category)} — {item['contact']} ({item['firm']})") \
                        .classes("font-bold").style(f"color:{COLORS['accent_light']};")
                    ui.label(f"received {item['received_at']}").style(f"color:{COLORS['text_muted']};font-size:11px;")
                ui.label(f"Subject: {item.get('subject') or '(no subject)'}").style(f"color:{COLORS['text_muted']};font-size:12px;")

                if item.get("doc_id") is not None:
                    def _download(doc_id=item["doc_id"]):
                        result = documents.get_document_bytes(doc_id)
                        if result:
                            fname, _ctype, raw = result
                            ui.download(raw, filename=fname)
                    ui.button(f"📎 {item['filename']}", on_click=_download).props("flat dense size=sm").style(
                        f"color:{COLORS['accent_light']};font-size:11px;")

                def dismiss(item_id=item["id"]):
                    inbox_queue.dismiss_item(item_id)
                    ui.notify("Dismissed.")
                    _refresh()

                if category == "model":
                    firm = item["firm"] if item["firm"] in firms_with_data else (list(firms_with_data)[0] if firms_with_data else item["firm"])
                    default_period = extracted.get("period") if extracted.get("period") in ALL_PERIODS else ALL_PERIODS[0]
                    existing = current["period_estimates"].get(default_period, {}).get(firm, {})

                    with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
                        r_period = ui.select(ALL_PERIODS, value=default_period, label="Period").classes("flex-1")
                        r_rating = ui.select(["Buy", "Hold", "Sell", "Not Rated"],
                                              value=extracted.get("rating") or existing.get("Rating") or "Buy", label="Rating").classes("flex-1")
                    with ui.row().classes("w-full gap-3"):
                        r_pt = ui.number("Price Target ($)", value=extracted.get("price_target") or existing.get("Price Target") or 0.0, step=0.25).classes("flex-1")
                        r_eps = ui.number("EPS Est ($)", value=extracted.get("eps_est") or existing.get("EPS Est") or 0.0, step=0.01).classes("flex-1")
                        r_rev = ui.number("Revenue Est ($M)", value=extracted.get("revenue_est") or existing.get("Revenue Est ($M)") or 0.0, step=0.5).classes("flex-1")
                        r_ebd = ui.number("EBITDA Est ($M)", value=extracted.get("ebitda_est") or existing.get("EBITDA Est ($M)") or 0.0, step=0.1).classes("flex-1")
                    if extracted:
                        ui.label("Numbers pre-filled by AI from the attached file — check them before confirming.").style(
                            f"color:{COLORS['warning']};font-size:11px;")

                    def confirm(item_id=item["id"], firm=item["firm"], r_period=r_period, r_rating=r_rating,
                                r_pt=r_pt, r_eps=r_eps, r_rev=r_rev, r_ebd=r_ebd):
                        ok = consensus.confirm_model_review(
                            item_id, period=r_period.value, firm=firm, rating=r_rating.value,
                            price_target=r_pt.value or None, eps_est=r_eps.value if r_eps.value else None,
                            revenue_est=r_rev.value or None, ebitda_est=r_ebd.value or None,
                        )
                        if ok:
                            ui.notify(f"{firm} consensus updated for {r_period.value}.")
                        else:
                            ui.notify("That item was already actioned.", type="warning")
                        _refresh()
                    confirm_label = "✅ Confirm & Update Consensus"

                elif category == "research_note":
                    # CFA-lens breakdown, not just a summary — the reviewer
                    # (Head of IR) should be able to decide in seconds
                    # whether this is worth circulating further internally.
                    # Forwarding itself stays a manual human decision (see
                    # this function's docstring) — this just gets them a
                    # sharper read than a generic AI summary would.
                    with ui.column().classes("w-full gap-1").style("margin-top:6px;"):
                        if extracted.get("thesis_summary"):
                            ui.label(extracted["thesis_summary"]).style(f"color:{COLORS['text_body']};font-size:12.5px;")
                        meta_bits = []
                        if extracted.get("sentiment"):
                            meta_bits.append(f"Sentiment: {extracted['sentiment']}")
                        if extracted.get("variant_view"):
                            meta_bits.append(f"View: {extracted['variant_view']}")
                        if extracted.get("valuation_method"):
                            meta_bits.append(f"Method: {extracted['valuation_method']}")
                        if meta_bits:
                            ui.label(" · ".join(meta_bits)).style(f"color:{COLORS['accent_light']};font-size:11.5px;font-weight:bold;")
                        if extracted.get("key_assumptions"):
                            ui.label(f"Key assumptions: {extracted['key_assumptions']}").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
                        if extracted.get("catalysts_risks"):
                            ui.label(f"Catalysts/risks to watch: {extracted['catalysts_risks']}").style(f"color:{COLORS['warning']};font-size:11.5px;")
                        if extracted.get("prior_price_target") and extracted.get("price_target"):
                            ui.label(f"PT change: ${extracted['prior_price_target']} → ${extracted['price_target']}").style(
                                f"color:{COLORS['text_body']};font-size:11.5px;")

                    has_rating_or_pt = bool(extracted.get("rating") or extracted.get("price_target"))
                    if has_rating_or_pt:
                        firm = item["firm"] if item["firm"] in firms_with_data else (list(firms_with_data)[0] if firms_with_data else item["firm"])
                        default_period = extracted.get("period") if extracted.get("period") in ALL_PERIODS else ALL_PERIODS[0]
                        existing = current["period_estimates"].get(default_period, {}).get(firm, {})
                        with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
                            rn_period = ui.select(ALL_PERIODS, value=default_period, label="Period").classes("flex-1")
                            rn_rating = ui.select(["Buy", "Hold", "Sell", "Not Rated"],
                                                   value=extracted.get("rating") or existing.get("Rating") or "Buy", label="Rating").classes("flex-1")
                            rn_pt = ui.number("Price Target ($)", value=extracted.get("price_target") or existing.get("Price Target") or 0.0, step=0.25).classes("flex-1")
                        rn_update_consensus = ui.checkbox("Also update consensus with this rating/PT", value=True)
                        rn_internal_only = ui.checkbox("Internal Use Only (flag before any further internal circulation)", value=True)

                        def confirm(item_id=item["id"], firm=firm, rn_period=rn_period, rn_rating=rn_rating,
                                    rn_pt=rn_pt, rn_update_consensus=rn_update_consensus, rn_internal_only=rn_internal_only):
                            notes = []
                            if rn_update_consensus.value:
                                consensus.update_estimate(rn_period.value, firm, rating=rn_rating.value,
                                                           price_target=rn_pt.value or None, source="email_research_note")
                                notes.append(f"consensus updated for {firm}, {rn_period.value}")
                            notes.append("marked Internal Use Only" if rn_internal_only.value else "reviewed")
                            inbox_queue.mark_confirmed(item_id, outcome="; ".join(notes).capitalize())
                            ui.notify(f"Research note from {firm} — {', '.join(notes)}.")
                            _refresh()
                    else:
                        rn_internal_only = ui.checkbox("Internal Use Only (flag before any further internal circulation)", value=True)

                        def confirm(item_id=item["id"], firm=item["firm"], rn_internal_only=rn_internal_only):
                            outcome = "Marked Internal Use Only" if rn_internal_only.value else "Reviewed"
                            inbox_queue.mark_confirmed(item_id, outcome=outcome)
                            ui.notify(f"Research note from {firm} — {outcome.lower()}.")
                            _refresh()
                    confirm_label = "✅ Confirm Review"

                elif category == "ndr_request":
                    n_city = ui.input("City *", value=extracted.get("city") or "").classes("w-full").style("margin-top:6px;")
                    n_metro = ui.input("Metro region", value=extracted.get("metro") or "").classes("w-full")
                    n_reason = ui.textarea("Reason / context", value=extracted.get("reason") or "").classes("w-full")

                    def confirm(item_id=item["id"], contact=item["contact"], firm=item["firm"],
                                n_city=n_city, n_metro=n_metro, n_reason=n_reason):
                        if not n_city.value:
                            ui.notify("City is required.", type="warning")
                            return
                        reqs = _load_ndr_requests()
                        reqs.append({
                            "id": datetime.now().strftime("%Y%m%d%H%M%S"), "analyst": contact, "firm": firm,
                            "city": n_city.value, "metro": n_metro.value or n_city.value, "reason": n_reason.value or "—",
                            "received": datetime.now().strftime("%b %d, %Y"), "resolved": False, "seeded": False,
                        })
                        _save_ndr_requests(reqs)
                        inbox_queue.mark_confirmed(item_id, outcome=f"Logged NDR request for {n_city.value}")
                        ui.notify(f"NDR request from {contact} logged — see NDR Planner → Requests.")
                        _refresh()
                    confirm_label = "✅ Log NDR Request"

                elif category == "conference_invite":
                    c_event = ui.input("Event name *", value=extracted.get("event_name") or "").classes("w-full").style("margin-top:6px;")
                    c_date = ui.input("Date (YYYY-MM-DD)", value=extracted.get("date") or "").classes("w-full")
                    c_loc = ui.input("Location", value=extracted.get("location") or "").classes("w-full")

                    def confirm(item_id=item["id"], firm=item["firm"], c_event=c_event, c_date=c_date, c_loc=c_loc):
                        if not c_event.value:
                            ui.notify("Event name is required.", type="warning")
                            return
                        events = db.load_json("ir_conference_calendar.csv", None) or []
                        events.append({
                            "Event": c_event.value, "Type": "Conference", "Date": c_date.value or "TBD",
                            "Location": c_loc.value or "—", "Organizer": firm, "Status": "Invited — pending confirmation",
                            "Deadline": "—", "Notes": f"Invitation received by email from {item['contact']} ({firm}).",
                            "Source": "Email invite", "Attending": "TBD", "Priority": "Medium",
                        })
                        db.save_json("ir_conference_calendar.csv", events)
                        inbox_queue.mark_confirmed(item_id, outcome=f"Added '{c_event.value}' to Calendar")
                        ui.notify(f"'{c_event.value}' added to Calendar — confirm details there.")
                        _refresh()
                    confirm_label = "✅ Add to Calendar"

                elif category == "speak_to_management":
                    m_contact_role = ui.input("Requested contact", value=extracted.get("requested_contact") or "CFO / IR").classes("w-full").style("margin-top:6px;")
                    m_topic = ui.textarea("Topic", value=extracted.get("topic") or "").classes("w-full")
                    m_date = ui.input("Proposed date (YYYY-MM-DD)", value=(datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")).classes("w-full")

                    def confirm(item_id=item["id"], contact=item["contact"], firm=item["firm"],
                                m_topic=m_topic, m_date=m_date):
                        meetings = db.load_json("scheduled_meetings.json", None) or []
                        meetings.append({
                            "id": str(uuid.uuid4()), "Contact": contact, "Firm": firm, "Side": "Buy-side",
                            "Date": m_date.value, "Time": "", "Type": "Callback",
                            "Topic": m_topic.value or "Speak-to-management request from email — confirm date/time.",
                            "Status": "Requested", "Priority": "Medium",
                        })
                        db.save_json("scheduled_meetings.json", meetings)
                        inbox_queue.mark_confirmed(item_id, outcome=f"Scheduled meeting request for {contact}")
                        ui.notify(f"Meeting request from {contact} added to Meeting Hub — confirm date/time there.")
                        _refresh()
                    confirm_label = "✅ Schedule Meeting"

                else:  # meeting_confirmation
                    mc_type = ui.select(["1x1 call", "Conference call", "Video call", "In-person", "Other"],
                                         value=extracted.get("meeting_type") or "1x1 call", label="Meeting type").classes("w-full").style("margin-top:6px;")
                    mc_date = ui.input("Date (YYYY-MM-DD)", value=extracted.get("date") or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")).classes("w-full")
                    mc_time = ui.input("Time", value=extracted.get("time") or "").classes("w-full")
                    mc_notes = ui.textarea("Notes", value=extracted.get("notes") or "").classes("w-full")

                    def confirm(item_id=item["id"], contact=item["contact"], firm=item["firm"],
                                mc_type=mc_type, mc_date=mc_date, mc_time=mc_time, mc_notes=mc_notes):
                        meetings = db.load_json("scheduled_meetings.json", None) or []
                        meetings.append({
                            "id": str(uuid.uuid4()), "Contact": contact, "Firm": firm, "Side": "Buy-side",
                            "Date": mc_date.value, "Time": mc_time.value, "Type": mc_type.value,
                            "Topic": mc_notes.value or "Confirmed via email — see original message for details.",
                            "Status": "Confirmed", "Priority": "Medium",
                        })
                        db.save_json("scheduled_meetings.json", meetings)
                        inbox_queue.mark_confirmed(item_id, outcome=f"Logged confirmed meeting with {contact} on {mc_date.value}")
                        ui.notify(f"Confirmed meeting with {contact} added to Meeting Hub.")
                        _refresh()
                    confirm_label = "✅ Log Confirmed Meeting"

                with ui.row().classes("w-full gap-2").style("margin-top:6px;"):
                    ui.button(confirm_label, on_click=confirm).props("color=primary dense")
                    ui.button("Dismiss", on_click=dismiss).props("flat dense")


def _render_linked_documents(contact, firm):
    """Shown on an Upcoming Meetings card — "pull up the model the analyst
    sent in and the most recent note" in one place, instead of hunting
    through email or a shared drive. Looks up by contact+firm (the same
    join key used by post_meeting_notes.json and the Meeting Log), so this
    works whether the document was attached from Schedule Meeting, from
    Post-Meeting Notes, or (once wired) pulled in from the IR inbox."""
    model_doc = documents.get_latest_document(contact=contact, firm=firm, doc_type="model")
    note_doc = documents.get_latest_document(contact=contact, firm=firm, doc_type="note_attachment")
    if not (model_doc or note_doc):
        return

    def _download(doc_id):
        result = documents.get_document_bytes(doc_id)
        if result:
            fname, _ctype, raw = result
            ui.download(raw, filename=fname)

    with ui.row().classes("w-full gap-2").style("margin-top:4px;flex-wrap:wrap;"):
        if model_doc:
            ui.button(f"📎 Latest model — {model_doc['filename']}",
                      on_click=lambda doc_id=model_doc["id"]: _download(doc_id)) \
                .props("flat dense size=sm").style(f"color:{COLORS['accent_light']};font-size:11px;")
        if note_doc:
            ui.button(f"📝 Latest note attachment — {note_doc['filename']}",
                      on_click=lambda doc_id=note_doc["id"]: _download(doc_id)) \
                .props("flat dense size=sm").style(f"color:{COLORS['accent_light']};font-size:11px;")


def _hub_metric(label, value):
    with ui.card().classes("flex-1 text-center").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(str(value)).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:10px;")


def _safe_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return datetime.now().date()


# ─────────────────────────────────────────────────────────────────────────
# Target Database tab
# ─────────────────────────────────────────────────────────────────────────
def _render_target_db_tab(institutions, client_id):
    prospects = _load_json("prospects.json", [])

    ui.label("🎯 Target Database").classes("text-lg font-bold")
    ui.label("Search and filter the tracked institution universe, plus manually-added prospects. The automated "
             "prospecting pipeline below (Analyst Coverage Network, live-13F auto-generation, NOBO cross-reference, "
             "bulk paste) is ported and rebuilt on the live SEC 13F fetcher — see each section for details.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    search_in = ui.input("Search by fund name").classes("w-full")
    results = ui.column().classes("w-full gap-2")

    _OUTCOME_OPTIONS = {"— unresolved —": None, "Won (meeting set / met / owns)": "positive", "Passed": "negative"}
    _OUTCOME_REVERSE = {"positive": "Won (meeting set / met / owns)", "negative": "Passed", None: "— unresolved —"}

    def do_search():
        results.clear()
        q = (search_in.value or "").lower().strip()
        combined = [{"Fund": i["Fund"], "Metro": i["Metro"], "Type": i["Type"], "USIO_Holder": i["USIO_Holder"],
                    "Score": i["Engagement_Score"], "Source": "Tracked", "_pidx": None} for i in institutions]
        current_prospects = _load_json("prospects.json", [])
        combined += [{"Fund": p["fund"], "Metro": p.get("metro", "—"), "Type": p.get("style", "—"),
                     "USIO_Holder": False, "Score": p.get("score", 0), "Source": "Prospect", "_pidx": idx,
                     "_outcome": p.get("outcome"), "_has_score": bool(p.get("score_breakdown"))}
                     for idx, p in enumerate(current_prospects)]
        if q:
            combined = [c for c in combined if q in c["Fund"].lower()]
        combined.sort(key=lambda x: -x["Score"])
        with results:
            if not combined:
                ui.label("No matches.").style(f"color:{COLORS['text_muted']};")
            for c in combined:
                with ui.row().classes("w-full items-center justify-between").style(
                        f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                    ui.label(f"{c['Fund']} ({c['Source']})").style(f"color:{COLORS['text_body']};font-size:13px;")
                    ui.label(f"{c['Metro']} · {c['Type']} · {'Holder' if c['USIO_Holder'] else 'Non-holder'} · Score {c['Score']}").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
                    # Outcome marker — only for prospects that were added WITH a
                    # stored Fit Score breakdown (see run_fit_score_ranking's
                    # add_scored_prospect), since that's what
                    # core.fit_score.suggest_reweight() needs to learn from.
                    # Every "Won" or "Passed" logged here is a labeled data
                    # point the re-weight suggestion picks up next time it runs.
                    if c["Source"] == "Prospect" and c.get("_has_score"):
                        def set_outcome(e, pidx=c["_pidx"]):
                            plist = _load_json("prospects.json", [])
                            plist[pidx]["outcome"] = _OUTCOME_OPTIONS.get(e.value)
                            _save_json("prospects.json", plist)
                            ui.notify("Outcome saved.")

                        ui.select(list(_OUTCOME_OPTIONS.keys()), value=_OUTCOME_REVERSE.get(c.get("_outcome")),
                                  on_change=set_outcome).props("dense outlined").classes("min-w-[220px]")

    search_in.on("keydown.enter", do_search)
    ui.button("Search", on_click=do_search).props("dense")
    do_search()

    ui.markdown("---")
    with ui.expansion("✍️ Add a prospect manually").classes("w-full"):
        p_fund = ui.input("Fund name *").classes("w-full")
        p_metro = ui.input("Metro / region").classes("w-full")
        p_style = ui.input("Investment style").classes("w-full")
        p_score = ui.number("Fit score (0-100)", value=50, min=0, max=100)
        p_notes = ui.textarea("Notes").classes("w-full")

        def add_prospect():
            if not p_fund.value:
                ui.notify("Fund name is required.", type="warning")
                return
            plist = _load_json("prospects.json", [])
            plist.append({"fund": p_fund.value, "metro": p_metro.value, "style": p_style.value,
                          "score": p_score.value, "notes": p_notes.value, "added": datetime.now().strftime("%Y-%m-%d")})
            _save_json("prospects.json", plist)
            ui.notify(f"Added {p_fund.value} to the prospect list.")
            _refresh()

        ui.button("➕ Add Prospect", on_click=add_prospect).props("color=primary")

    ui.markdown("---")
    with ui.expansion("📋 Bulk paste-from-website", value=False).classes("w-full"):
        ui.label("Some sites (WhaleWisdom in particular) render holder tables as styled grids, not plain HTML "
                  "tables — copy/paste from those won't preserve columns cleanly through a file upload. Paste raw "
                  "text here instead; it's parsed by tab or by runs of 2+ spaces.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")
        bp_raw = ui.textarea("Paste table here", placeholder="Paste tab-separated or space-aligned rows here...").classes("w-full")
        bp_preview = ui.column().classes("w-full")
        bp_state = {"columns": [], "rows": [], "fund_col_idx": 0}

        def bp_parse():
            bp_preview.clear()
            columns, rows = prospecting.parse_pasted_table(bp_raw.value or "")
            bp_state["columns"], bp_state["rows"] = columns, rows
            with bp_preview:
                if not rows:
                    ui.label("Nothing parsed yet — paste some rows above.").style(f"color:{COLORS['text_muted']};")
                    return
                ui.label(f"Parsed {len(rows)} row(s) — check this looks right before adding.").style(
                    f"color:{COLORS['text_muted']};font-size:11.5px;")
                fund_col_sel = ui.select(columns, value=columns[0], label="Which column is the fund/investor name?").classes("w-full")

                def set_fund_col():
                    bp_state["fund_col_idx"] = columns.index(fund_col_sel.value)
                fund_col_sel.on_value_change(set_fund_col)

                with ui.column().classes("w-full").style(f"max-height:220px;overflow-y:auto;border:1px solid {COLORS['border']};border-radius:6px;padding:6px;"):
                    for r in rows[:30]:
                        ui.label(" | ".join(r)).style(f"color:{COLORS['text_body']};font-size:11px;")
                    if len(rows) > 30:
                        ui.label(f"... + {len(rows) - 30} more rows").style(f"color:{COLORS['text_muted']};font-size:11px;")

                def add_all():
                    plist = _load_json("prospects.json", [])
                    existing_names = {p["fund"] for p in plist}
                    added = 0
                    fi = bp_state["fund_col_idx"]
                    for r in bp_state["rows"]:
                        name = r[fi].strip() if fi < len(r) else ""
                        if not name or name.lower() in ("history", "nan", ""):
                            continue
                        if name in existing_names:
                            continue
                        other = {columns[i]: r[i] for i in range(len(r)) if i != fi and r[i]}
                        plist.append({
                            "fund": name, "metro": "—", "style": "Unknown", "score": 0,
                            "notes": " · ".join(f"{k}: {v}" for k, v in other.items()),
                            "added": datetime.now().strftime("%Y-%m-%d"), "source": "Bulk paste",
                        })
                        existing_names.add(name)
                        added += 1
                    _save_json("prospects.json", plist)
                    ui.notify(f"✅ Added {added} funds to the prospect queue.")
                    _refresh()

                ui.button(f"➕ Add all parsed rows to Prospect Queue", on_click=add_all).props("dense").style("margin-top:6px;")

        bp_raw.on_value_change(bp_parse)
        ui.button("Parse", on_click=bp_parse).props("dense flat")

    ui.markdown("---")
    with ui.expansion("🔬 Analyst Coverage Network Targeting", value=False).classes("w-full"):
        ui.label("Institutions already owning other stocks a covering analyst rates Buy have demonstrated they "
                  "trust that analyst's research and understand the surrounding sector thesis — the "
                  "highest-probability prospects once that analyst raises this client's target.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")

        coverage = analyst_coverage.get_coverage(client_id)
        if not coverage:
            ui.label("No covering analysts on file yet.").style(f"color:{COLORS['text_muted']};")
        else:
            analyst_keys = list(coverage.keys())
            analyst_sel = ui.select(analyst_keys, value=analyst_keys[0], label="Select analyst coverage network to mine").classes("w-full")
            coverage_list = ui.column().classes("w-full")

            def render_coverage_list():
                coverage_list.clear()
                cov = analyst_coverage.get_coverage(client_id)
                data = cov.get(analyst_sel.value)
                if not data:
                    return
                with coverage_list:
                    ui.label(f"{data['analyst']} — {data['firm']} · {data['email']} · "
                              f"{len(data['coverage'])} stocks in coverage universe").classes("font-bold").style(
                        f"color:{COLORS['text_heading']};font-size:12.5px;")
                    for stock in sorted(data["coverage"], key=lambda s: -s.get("relevance", 0)):
                        rel = stock.get("relevance", 0)
                        rel_clr = "#4ADE80" if rel >= 80 else "#F0A830" if rel >= 50 else "#94A3B8"
                        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};margin-top:4px;"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(f"{stock['ticker']} — {stock['name']} · {stock.get('sector', '—')}").classes("font-bold").style(
                                    f"color:{COLORS['text_heading']};font-size:12.5px;")
                                ui.label(f"{stock.get('rating', '—')} · PT ${stock.get('pt', 0):.2f} · Relevance {rel}/100").style(
                                    f"color:{rel_clr};font-size:11.5px;font-weight:bold;")
                            if stock.get("bridge"):
                                ui.label(stock["bridge"]).style(f"color:{COLORS['text_muted']};font-size:11px;")
                            if stock.get("shared_dna"):
                                ui.label(" · ".join(t.strip() for t in stock["shared_dna"].split("·") if t.strip())).style(
                                    f"color:{COLORS['accent_light']};font-size:10.5px;")

            analyst_sel.on_value_change(render_coverage_list)
            render_coverage_list()

            ui.markdown("---")
            with ui.expansion("➕ Add stock to this analyst's coverage").classes("w-full"):
                ac_ticker = ui.input("Ticker").classes("w-full")
                ac_name = ui.input("Company name").classes("w-full")
                ac_pt = ui.number("Price target ($)", value=0.0, step=0.25)
                ac_rating = ui.select(["Buy", "Neutral", "Sell"], value="Buy")
                ac_sector = ui.input("Sector").classes("w-full")
                ac_relevance = ui.number("USIO relevance (0-100)", value=50, min=0, max=100)
                ac_bridge = ui.textarea("Why holders of this ticker are prospects").classes("w-full")

                def add_coverage_entry():
                    if not (ac_ticker.value and ac_name.value):
                        ui.notify("Ticker and company name are required.", type="warning")
                        return
                    ok = analyst_coverage.add_coverage_stock(
                        analyst_sel.value, ac_ticker.value, ac_name.value, ac_pt.value, ac_rating.value,
                        ac_sector.value, relevance=int(ac_relevance.value), bridge=ac_bridge.value, client_id=client_id,
                    )
                    if ok:
                        ui.notify(f"{ac_ticker.value.upper()} added to {analyst_sel.value}'s coverage.")
                        render_coverage_list()
                    else:
                        ui.notify(f"{ac_ticker.value.upper()} is already in this analyst's coverage.", type="warning")

                ui.button("➕ Add", on_click=add_coverage_entry).props("dense")

    ui.markdown("---")
    with ui.expansion("🤖 Automated Prospecting Pipeline — Live 13F Holders of Coverage-Network Stocks", value=False).classes("w-full"):
        ui.label("For the selected analyst's other Buy-rated stocks scoring at or above the threshold, pulls real "
                  "SEC 13F institutional holders (already fetched via the SEC Intelligence tab's 'Refresh 13F "
                  "Institutional Holders' button — this does not trigger a new download itself), excludes anyone "
                  "already tracked or already in the prospect queue, and ranks the rest.").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")

        coverage2 = analyst_coverage.get_coverage(client_id)
        if not coverage2:
            ui.label("No covering analysts on file — add one above first.").style(f"color:{COLORS['text_muted']};")
        else:
            analyst_keys2 = list(coverage2.keys())
            auto_analyst = ui.select(analyst_keys2, value=analyst_keys2[0], label="Analyst coverage network").classes("w-full")
            ui.label("Minimum USIO relevance score to include:").style(f"color:{COLORS['text_muted']};font-size:11px;")
            auto_threshold = ui.slider(min=0, max=100, value=50, step=5).props("label-always")
            auto_results = ui.column().classes("w-full")

            def run_auto_prospecting():
                auto_results.clear()
                known_names = {i["Fund"] for i in institutions} | {p["fund"] for p in _load_json("prospects.json", [])}
                result = prospecting.generate_coverage_prospects(
                    auto_analyst.value, min_relevance=int(auto_threshold.value),
                    known_fund_names=known_names, client_id=client_id,
                )
                with auto_results:
                    if result["not_fetched_tickers"]:
                        ui.label(f"⚠️ No live 13F data cached yet for: {', '.join(result['not_fetched_tickers'])} — "
                                  f"add them to the Peer Universe below and refresh 13F on the SEC Intelligence tab "
                                  f"to include their holders here.").style(f"color:{COLORS['warning']};font-size:11px;")
                    if not result["prospects"]:
                        ui.label("No new prospects found at this relevance threshold.").style(f"color:{COLORS['text_muted']};")
                        return
                    ui.label(f"{len(result['prospects'])} prospect(s) found:").classes("font-bold")
                    for p in result["prospects"][:25]:
                        with ui.row().classes("w-full items-start justify-between").style(
                                f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                            with ui.column().classes("flex-1"):
                                ui.label(f"{p['fund']} — via {p['source_ticker']} ({p['source_name']})").classes("font-bold").style(
                                    f"color:{COLORS['text_heading']};font-size:12.5px;")
                                ui.label(p["talking_point"]).style(f"color:{COLORS['text_muted']};font-size:11px;")
                                # size_known=False means this holder came from the EDGAR full-text-search
                                # path (sec_filings._search_holders_for_ticker) — confirmed to hold a
                                # position, but exact share/dollar size wasn't fetched (see that
                                # function's docstring). Showing "1 shares · $0 reported" in that case
                                # would be misleadingly precise-looking for a value we don't actually have.
                                size_line = (f"{p['shares']:,} shares · ${p['value']:,} reported · relevance {p['relevance']}/100"
                                             if p.get("size_known", True)
                                             else f"confirmed holder (position size not available) · relevance {p['relevance']}/100")
                                ui.label(size_line).style(f"color:{COLORS['text_muted']};font-size:10.5px;")

                            def add_this(p=p):
                                plist = _load_json("prospects.json", [])
                                if any(x["fund"] == p["fund"] for x in plist):
                                    ui.notify(f"{p['fund']} is already in the prospect queue.", type="warning")
                                    return
                                plist.append({
                                    "fund": p["fund"], "metro": "—", "style": "Unknown", "score": p["relevance"],
                                    "notes": p["talking_point"], "added": datetime.now().strftime("%Y-%m-%d"),
                                    "source": f"Coverage Network — {p['source_ticker']}",
                                })
                                _save_json("prospects.json", plist)
                                ui.notify(f"{p['fund']} added to prospect queue.")
                                _refresh()

                            ui.button("➕ Add", on_click=add_this).props("flat dense")

            ui.button("🚀 Auto-Generate Prospect List", on_click=run_auto_prospecting).props("color=primary dense")
            run_auto_prospecting()

    ui.markdown("---")
    with ui.expansion("📋 NOBO Cross-Reference", value=False).classes("w-full"):
        ui.label("Request from the transfer agent (e.g. Computershare) quarterly — Excel or CSV with holder name "
                  "and shares. Compares a list of names (the prospect queue, tracked institutions, the call "
                  "listener log, the IR website visitor log, or a pasted list) against this client's actual NOBO "
                  "shareholder file — matches are already-identified shareholders; everyone else is a real, "
                  "unconfirmed prospect.").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

        nobo_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

        def refresh_nobo_status():
            cur = prospecting.get_nobo_list(client_id)
            if cur.get("rows"):
                nobo_status.text = f"✅ {cur['source_label']} — {len(cur['rows'])} holders on file (loaded {cur['_fetched_at'][:10]})"
            else:
                nobo_status.text = "No NOBO file on hand yet — request one from your transfer agent, or upload one below."
        refresh_nobo_status()

        async def handle_nobo_upload(e):
            try:
                raw = await e.file.read()
                fname = e.file.name
                if fname.lower().endswith(".csv"):
                    text = raw.decode("utf-8", errors="replace")
                    rows_in = list(csv.DictReader(io.StringIO(text)))
                else:
                    df = pd.read_excel(io.BytesIO(raw))
                    rows_in = df.to_dict("records")
                if not rows_in:
                    ui.notify("That file has no rows.", type="warning")
                    return

                def find_col(row, *keywords):
                    for k in row.keys():
                        if any(kw in str(k).lower() for kw in keywords):
                            return k
                    return None

                name_col = find_col(rows_in[0], "holder_name", "holder name", "name")
                shares_col = find_col(rows_in[0], "shares")
                if not (name_col and shares_col):
                    ui.notify("Couldn't find a holder-name and shares column — check this file's headers.", type="negative")
                    return
                parsed = []
                for r in rows_in:
                    try:
                        shares = int(float(r.get(shares_col, 0) or 0))
                    except (TypeError, ValueError):
                        shares = 0
                    name = str(r.get(name_col, "")).strip()
                    if name and name.lower() != "nan":
                        parsed.append({"holder_name": name, "shares": shares})
                prospecting.save_nobo_list(parsed, source_label=f"Uploaded: {fname}", client_id=client_id)
                ui.notify(f"✅ NOBO list updated — {len(parsed)} holders.")
                refresh_nobo_status()
            except Exception as ex:
                ui.notify(f"Couldn't read that file: {ex}", type="negative")

        ui.upload(on_upload=handle_nobo_upload, auto_upload=True).props("accept=.csv,.xlsx flat").classes("w-full")

        ui.markdown("---")
        nobo_source_options = ["Prospect Queue", "Tracked Institutions"]
        if os.path.exists(client_data_path("q1_2026_call_listener_log.csv", client_id)):
            nobo_source_options.append("Call Listener Log")
        if os.path.exists(client_data_path("ir_website_visitor_log.csv", client_id)):
            nobo_source_options.append("IR Website Visitor Log")
        nobo_source_options.append("Paste names")

        nobo_compare_src = ui.select(nobo_source_options, value="Prospect Queue", label="Compare against:").classes("w-full")
        nobo_paste = ui.textarea("Paste one name per line").classes("w-full")
        nobo_paste.set_visibility(False)
        nobo_compare_src.on_value_change(lambda: nobo_paste.set_visibility(nobo_compare_src.value == "Paste names"))
        nobo_results = ui.column().classes("w-full")

        def run_nobo_compare():
            nobo_results.clear()
            src = nobo_compare_src.value
            if src == "Prospect Queue":
                names = [p["fund"] for p in _load_json("prospects.json", [])]
            elif src == "Tracked Institutions":
                names = [i["Fund"] for i in institutions]
            elif src == "Call Listener Log":
                cl = pd.read_csv(client_data_path("q1_2026_call_listener_log.csv", client_id))
                names = cl["Firm"].dropna().unique().tolist() if "Firm" in cl.columns else []
            elif src == "IR Website Visitor Log":
                vl = pd.read_csv(client_data_path("ir_website_visitor_log.csv", client_id))
                names = vl["Visitor_Organization"].dropna().unique().tolist() if "Visitor_Organization" in vl.columns else []
            else:
                names = [n.strip() for n in (nobo_paste.value or "").split("\n") if n.strip()]

            with nobo_results:
                if not prospecting.get_nobo_list(client_id).get("rows"):
                    ui.label("Upload a NOBO file above first.").style(f"color:{COLORS['text_muted']};")
                    return
                if not names:
                    ui.label("Nothing to compare — that source is empty.").style(f"color:{COLORS['text_muted']};")
                    return
                matched, unmatched = prospecting.match_against_nobo(names, client_id=client_id)
                ui.label(f"{len(matched)} identified on the NOBO file · {len(unmatched)} not found — real "
                          f"prospects, not already-known shareholders").classes("font-bold")
                with ui.row().classes("w-full gap-4"):
                    with ui.column().classes("flex-1").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;padding:8px;"):
                        ui.label("✅ Identified shareholders").classes("font-bold").style("color:#4ADE80;font-size:12px;")
                        if matched:
                            for nm, mn, sh in matched:
                                ui.label(f"{nm} → {mn} — {sh:,} shares").style(f"color:{COLORS['text_body']};font-size:11px;")
                        else:
                            ui.label("None matched.").style(f"color:{COLORS['text_muted']};font-size:11px;")
                    with ui.column().classes("flex-1").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;padding:8px;"):
                        ui.label("🎯 Not on the NOBO file (genuine prospects)").classes("font-bold").style(
                            f"color:{COLORS['text_heading']};font-size:12px;")
                        if unmatched:
                            for nm in unmatched:
                                ui.label(nm).style(f"color:{COLORS['text_muted']};font-size:11px;")
                        else:
                            ui.label("Everything compared matched the NOBO file.").style(f"color:{COLORS['text_muted']};font-size:11px;")

        ui.button("Compare", on_click=run_nobo_compare).props("dense")

    ui.markdown("---")
    _render_peer_universe_manager(institutions)


def _render_peer_universe_manager(institutions):
    ui.label("🎯 Peer Cross-Targeting — Find Institutions Owning Peers But Not This Client").classes("font-bold")
    peers = _load_peer_universe()

    with ui.expansion("⚙️ Manage Peer Universe — Add or Remove Tickers", value=False).classes("w-full"):
        ui.label(f"Custom peer group saved to peer_universe.csv · Persists across restarts · {len(peers)} peers currently tracked").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")

        manage_list = ui.column().classes("w-full")

        def render_manage_list():
            manage_list.clear()
            current = _load_peer_universe()
            with manage_list:
                for idx, p in enumerate(current):
                    with ui.row().classes("w-full items-center justify-between").style(f"border-bottom:1px solid {COLORS['border']};padding:4px 0;"):
                        ev = f"{p['ev_rev']}x" if p.get("ev_rev") else "no EV/Rev on file"
                        ui.label(f"{p['ticker']} — {p['name']} · {p.get('sector','—')} · {ev}").style(f"color:{COLORS['text_body']};font-size:12.5px;")

                        def do_delete(idx=idx):
                            cur = _load_peer_universe()
                            removed = cur.pop(idx)
                            _save_peer_universe(cur)
                            ui.notify(f"{removed['ticker']} removed.")
                            render_manage_list()

                        # Fit Score inputs — tier drives Comparability fit +
                        # the P1-P4 tier's "core" bonus; weight drives Peer
                        # conviction (see core/fit_score.py). Saved
                        # immediately on change, no separate Save button —
                        # matches the delete button's immediate-effect pattern
                        # right next to it.
                        def set_tier(e, idx=idx):
                            cur = _load_peer_universe()
                            cur[idx]["tier"] = e.value
                            _save_peer_universe(cur)

                        def set_weight(e, idx=idx):
                            try:
                                w = float(e.value)
                            except (TypeError, ValueError):
                                return
                            cur = _load_peer_universe()
                            cur[idx]["weight"] = w
                            _save_peer_universe(cur)

                        ui.select(["core", "close", "large"], value=p.get("tier", "close"),
                                  on_change=set_tier).props("dense outlined").classes("min-w-[90px]")
                        ui.number(value=p.get("weight", 1.0), min=0.1, max=5.0, step=0.5,
                                  on_change=set_weight).props("dense outlined").classes("min-w-[70px]")
                        ui.button("🗑", on_click=do_delete).props("flat dense")

        render_manage_list()
        ui.label("Tier: \"core\" = closest-size direct comp (full Fit Score points, +5 conviction bonus) · "
                 "\"close\" = real but less-comparable peer (default) · \"large\" = mega-cap/weak-signal peer. "
                 "Weight scales Peer Conviction — higher for peers closest to this client's own size.").style(
            f"color:{COLORS['text_muted']};font-size:10.5px;font-style:italic;")
        ui.markdown("---")

        ui.label("Add a new peer ticker:").classes("font-bold").style("font-size:12.5px;")
        with ui.row().classes("w-full gap-2"):
            new_ticker = ui.input("Ticker", placeholder="e.g. PAYO").classes("flex-1")
            new_name = ui.input("Company name", placeholder="e.g. Payoneer Global").classes("flex-1")
            new_sector = ui.input("Sector / focus", placeholder="e.g. Cross-Border Payments").classes("flex-1")
            new_ev = ui.input("EV/Rev (optional)", placeholder="EV/Rev").classes("min-w-[100px]")
        with ui.row().classes("w-full gap-2"):
            new_tier = ui.select(["core", "close", "large"], value="close", label="Fit Score tier").classes("min-w-[120px]")
            new_weight = ui.number("Fit Score weight", value=1.0, min=0.1, max=5.0, step=0.5).classes("min-w-[120px]")

        def add_peer():
            tkr = (new_ticker.value or "").upper().strip()
            nm = (new_name.value or "").strip()
            if not (tkr and nm):
                ui.notify("Enter at least a ticker and company name.", type="warning")
                return
            cur = _load_peer_universe()
            if tkr in [p["ticker"] for p in cur]:
                ui.notify(f"{tkr} is already in the peer universe.", type="warning")
                return
            try:
                ev_val = float(new_ev.value) if new_ev.value and new_ev.value.strip() else None
            except ValueError:
                ev_val = None
            cur.append({"ticker": tkr, "name": nm, "sector": new_sector.value or "Payments / Fintech", "ev_rev": ev_val,
                        "tier": new_tier.value or "close", "weight": float(new_weight.value or 1.0)})
            _save_peer_universe(cur)
            ui.notify(f"✅ {tkr} — {nm} added and saved" + (f" with EV/Rev {ev_val}x." if ev_val else " — no EV/Rev yet, flagged as needing research."))
            new_ticker.value, new_name.value, new_sector.value, new_ev.value = "", "", "", ""
            new_tier.value, new_weight.value = "close", 1.0
            render_manage_list()
            _refresh()

        ui.button("➕ Add", on_click=add_peer).props("dense")

        missing_ev = [p["ticker"] for p in peers if not p.get("ev_rev")]
        if missing_ev:
            ui.label(f"⚠️ No EV/Revenue multiple on file for: {', '.join(missing_ev)} — these won't get a specific "
                     f"valuation comparison in outreach drafts until a multiple is added here.").style(
                f"color:{COLORS['text_muted']};font-size:11px;")

        ui.markdown("---")
        ui.label("Quick-add common fintech peers:").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
        quick_peers = [("PAYO", "Payoneer", "Cross-Border"), ("FLYW", "Flywire", "Ed/Healthcare Payments"),
                       ("RELY", "Remitly", "Digital Remittance"), ("EVTC", "EVERTEC", "LatAm Payments"),
                       ("I", "Inpay", "B2B Cross-Border")]
        with ui.row().classes("w-full gap-2"):
            for qt, qn, qs in quick_peers:
                existing_tickers = [p["ticker"] for p in peers]

                def add_quick(qt=qt, qn=qn, qs=qs):
                    cur = _load_peer_universe()
                    cur.append({"ticker": qt, "name": qn, "sector": qs, "ev_rev": None})
                    _save_peer_universe(cur)
                    ui.notify(f"{qt} added.")
                    render_manage_list()
                    _refresh()

                if qt in existing_tickers:
                    ui.label(f"✅ {qt}").style(f"color:{COLORS['text_muted']};font-size:11.5px;")
                else:
                    ui.button(f"+ {qt}", on_click=add_quick).props("flat dense")

    ui.markdown("---")
    all_tickers = [p["ticker"] for p in peers]

    # Data-freshness summary — shown BEFORE the selector so it's clear
    # up front which tickers this analysis can actually back with a real
    # SEC 13F filing right now vs. which are still on the original seed
    # guess (see _enrich_peer_holdings_with_live_13f). A ticker only
    # becomes "live" after someone clicks "Refresh 13F Institutional
    # Holders" on the SEC Intelligence tab for it — this list doesn't
    # trigger that fetch itself (13F refresh is heavy, see
    # core/sec_filings.py's module docstring).
    _live_tickers = [t for t in all_tickers if sec_filings.get_cached_13f_holders(t).get("quarter")]
    _seed_tickers = [t for t in all_tickers if t not in _live_tickers]
    _freshness_bits = []
    if _live_tickers:
        _freshness_bits.append(f"✅ Live SEC 13F data: {', '.join(_live_tickers)}")
    if _seed_tickers:
        _freshness_bits.append(f"⚠️ Seed data only (not yet 13F-refreshed): {', '.join(_seed_tickers)}")
    ui.label(" · ".join(_freshness_bits)).style(f"color:{COLORS['text_muted']};font-size:11px;")
    if _seed_tickers:
        ui.label("Refresh a ticker from the SEC Intelligence tab's \"Refresh 13F Institutional Holders\" "
                  "button to replace its seed guess with a real filing.").style(f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")

    with ui.row().classes("w-full gap-4"):
        peer_select = ui.select(all_tickers, multiple=True, value=all_tickers,
                                 label="Select peers to cross-reference").classes("flex-1")
        aum_select = ui.select(["Any", "$100M+", "$500M+", "$1B+"], value="$100M+", label="Min fund AUM").classes("min-w-[140px]")

    results_area = ui.column().classes("w-full")

    def run_cross_targeting(from_click=False):
        # This already runs once automatically on page load (see the
        # unconditional call at the bottom of this function), so the results
        # below are visible before anyone touches the button. Clicking
        # "Run cross-targeting" without first changing the peer selection or
        # AUM filter re-renders the identical list — which reads as "the
        # button did nothing" even though it worked. The ui.notify() calls
        # below give every click a visible confirmation regardless of
        # whether the underlying result list actually changed.
        results_area.clear()
        sel = peer_select.value or []
        aum_min = {"Any": 0.0, "$100M+": 100.0, "$500M+": 500.0, "$1B+": 1000.0}[aum_select.value]
        with results_area:
            if not sel:
                ui.label("Select at least one peer ticker to run cross-targeting analysis.").style(f"color:{COLORS['text_muted']};")
                if from_click:
                    ui.notify("Select at least one peer ticker first.", type="warning")
                return
            for t in sel:
                info = next((p for p in peers if p["ticker"] == t), None)
                if info:
                    ui.label(f"{t} — {info['name']} · {info.get('sector','—')}").style(f"color:{COLORS['text_muted']};font-size:11.5px;")

            cross_targets = [i for i in institutions
                              if not i["USIO_Holder"]
                              and any(p in i["Peer_Holdings"] for p in sel)
                              and _parse_aum_millions(i["AUM"]) >= aum_min]
            if not cross_targets:
                ui.label("No cross-target matches at this AUM threshold. This checks your tracked watchlist "
                         "institutions by exact legal-entity name against the live SEC 13F filer roster — a peer "
                         "can have real institutional holders (see the SEC Intelligence tab) without any of them "
                         "being one of the specific institutions on your watchlist. Add more institutions to the "
                         "watchlist above, or lower the AUM threshold.").style(f"color:{COLORS['text_muted']};margin-top:6px;")
                if from_click:
                    ui.notify("Cross-targeting run — no matches at this AUM threshold.", type="warning")
                return
            ui.label(f"{len(cross_targets)} institutions own {', '.join(sel)} but NOT this client (AUM ≥ {aum_select.value}):").classes("font-bold").style("margin-top:6px;")
            for ct in sorted(cross_targets, key=lambda x: x["Engagement_Score"], reverse=True):
                overlap = [p for p in sel if p in ct["Peer_Holdings"]]
                # Same ✅ = confirmed-by-real-13F-filing marker as the
                # institution card's "Peers held" line — kept consistent so
                # the same overlap doesn't look "more real" in one place
                # than the other.
                ct_src = ct.get("Peer_Holdings_Source", {})
                overlap_labels = [p + (" ✅" if ct_src.get(p) == "live" else "") for p in overlap]
                score = ct["Engagement_Score"]
                score_clr = "#4ADE80" if score >= 80 else "#F0A830" if score >= 50 else "#94A3B8"
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(f"{ct['Fund']} — {ct['Type']} · AUM {ct['AUM']}").classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                        ui.label(f"Score: {score}").style(f"color:{score_clr};font-weight:bold;")
                    ui.label(f"Owns: {', '.join(overlap_labels)} · IR visits (30d): {ct['IR_Visits_30d']} · "
                             f"Q1 call: {'✅ Yes' if ct['Call_Listener'] else '⭕ No'} · Does NOT own this client").style(
                        f"color:{COLORS['text_muted']};font-size:11.5px;")
            if from_click:
                ui.notify(f"Cross-targeting run — {len(cross_targets)} institution(s) found.", type="positive")

    ui.button("Run cross-targeting", on_click=lambda: run_cross_targeting(from_click=True)).props("color=primary dense")
    run_cross_targeting()

    ui.markdown("---")
    ui.label("🏆 Fit Score Ranking — All Confirmed Peer Holders (Live 13F)").classes("font-bold")
    ui.label(
        "Different scope from the watchlist-only Peer Cross-Targeting above: this scores EVERY institution with "
        "a confirmed live 13F position in your selected peers — not just names already on your tracked buy-side "
        "roster — using the full six-component Fit Score (Peer conviction /30, New-buyer /20, Comparability fit "
        "/15, Turnover /15, Purchasing power /10, Contactability /10 = /100, P1-P4 tier). Peer conviction/Fit are "
        "computed directly from the tier + weight set per peer above. Purchasing power is a real number for the "
        "top-ranked prospects shown below — each fund's whole 13F book, fetched on demand from its own SEC filing "
        "the first time it appears in a top result (falls back to a neutral placeholder until then). Turnover and "
        "Contactability are rough automated heuristics (name-pattern + existing-relationship matching) until "
        "real outcomes accumulate — see \"Which score signals are converting?\" below."
    ).style(f"color:{COLORS['text_muted']};font-size:11.5px;")

    fit_results_area = ui.column().classes("w-full")

    async def run_fit_score_ranking(from_click=False):
        # async + asyncio.to_thread: score_all_holders() now does a bounded
        # lazy backfill of real purchasing-power book totals for its top ~40
        # results (see fit_score.py's backfill_top_n, sec_filings.py's
        # ensure_book_totals) — up to ~40 sequential SEC network requests.
        # Same class of bug as the old blocking 13F-refresh buttons (see
        # refresh_13d13g/refresh_13f above): a plain synchronous handler here
        # would freeze the whole app's event loop for every connected user
        # long enough to trip "Connection lost." Running the scoring call in
        # a background thread keeps the UI responsive while it works.
        fit_results_area.clear()
        sel = peer_select.value or []
        if not sel:
            with fit_results_area:
                ui.label("Select at least one peer ticker above to run Fit Score ranking.").style(f"color:{COLORS['text_muted']};")
            if from_click:
                ui.notify("Select at least one peer ticker first.", type="warning")
            return
        if from_click:
            ui.notify("Scoring confirmed holders — fetching real purchasing-power figures for top results, this may take a few seconds.")
        try:
            scored = await asyncio.to_thread(fit_score.score_all_holders, sel, get_active_client_id())
        except Exception as e:
            with fit_results_area:
                ui.label(f"Fit Score ranking failed: {e}").style(f"color:{COLORS['warning']};")
            if from_click:
                ui.notify(f"Fit Score ranking failed: {e}", type="negative")
            return
        with fit_results_area:
            if not scored:
                ui.label("No confirmed holders yet for the selected peers — refresh 13F Institutional Holders "
                          "on the SEC Intelligence tab first.").style(f"color:{COLORS['text_muted']};")
                if from_click:
                    ui.notify("No confirmed 13F holders yet for these peers.", type="warning")
                return
            ui.label(f"{len(scored)} institution(s) scored, ranked by Fit Score:").classes("font-bold").style("margin-top:6px;")
            tier_clrs = {"P1": "#4ADE80", "P2": "#86EFAC", "P3": "#F0A830", "P4": "#94A3B8"}
            for r in scored[:40]:
                tier_clr = tier_clrs.get(r["tier"], "#94A3B8")
                def add_scored_prospect(r=r):
                    plist = _load_json("prospects.json", [])
                    if any(p.get("fund") == r["fund"] for p in plist):
                        ui.notify(f"{r['fund']} is already in the prospect queue.", type="warning")
                        return
                    plist.append({
                        "fund": r["fund"], "metro": "—", "style": r["tier_label"], "score": r["composite"],
                        "score_breakdown": r, "outcome": None,
                        "notes": f"Fit Score {r['composite']}/100 · {r['tier_label']} · holds {', '.join(r['peers_held'])} "
                                 f"· via Peer Cross-Targeting Fit Score ranking",
                        "added": datetime.now().strftime("%Y-%m-%d"), "source": "Fit Score ranking",
                    })
                    _save_json("prospects.json", plist)
                    ui.notify(f"✅ {r['fund']} added to prospect queue.")

                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(r["fund"]).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                        with ui.row().classes("items-center gap-2"):
                            ui.label(f"{r['tier_label']} · {r['composite']}/100").style(f"color:{tier_clr};font-weight:bold;font-size:12.5px;")
                            ui.button("➕ Add", on_click=add_scored_prospect).props("flat dense")
                    ui.label(f"Holds: {', '.join(r['peers_held'])}" +
                             (" · 🆕 NEW buyer this quarter" if r["newbuyer_pts"] else "")).style(
                        f"color:{COLORS['text_muted']};font-size:11.5px;")
                    with ui.row().classes("w-full gap-2").style("margin-top:2px;flex-wrap:wrap;"):
                        for label, val, maxv in [
                            ("Conviction", r["conviction"], 30), ("New-buyer", r["newbuyer_pts"], 20),
                            ("Fit", r["fit"], 15), ("Turnover", r["turnover_pts"], 15),
                            ("Purch. power", r["pp_pts"], 10), ("Contact", r["contact_pts"], 10),
                        ]:
                            ui.label(f"{label} {val}/{maxv}").style(
                                f"color:{COLORS['text_muted']};font-size:10.5px;background:{COLORS['surface_bg']};"
                                f"padding:1px 6px;border-radius:4px;")
                    ui.label(f"Turnover: {r['turnover_class']} ({r['turnover_why']}) · "
                              f"Purchasing power: {r['pp_class']} ({r['pp_why']}) · "
                              f"Contactability: {r['contact_class']} ({r['contact_why']})").style(
                        f"color:{COLORS['text_muted']};font-size:10px;font-style:italic;margin-top:2px;")
            if from_click:
                ui.notify(f"Fit Score ranking run — {len(scored)} institution(s) scored.", type="positive")

    ui.button("🏆 Rank by Fit Score", on_click=lambda: run_fit_score_ranking(from_click=True)).props("color=primary dense")

    with ui.expansion("⚙️ Fit Score Weights — Re-weight the Components", value=False).classes("w-full"):
        ui.label("Current weights (must sum to 100). Same 'transparent, re-weightable' design as the source — "
                  "every component always shows in its own column, the composite is never a black box.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        current_weights = fit_score.get_weights(get_active_client_id())
        weight_inputs = {}
        with ui.row().classes("w-full gap-2"):
            for key, label in [("conviction", "Conviction"), ("newbuyer", "New-buyer"), ("fit", "Fit"),
                                ("turnover", "Turnover"), ("pp", "Purch. power"), ("contact", "Contact")]:
                weight_inputs[key] = ui.number(label, value=current_weights.get(key, fit_score.DEFAULT_WEIGHTS[key]),
                                                min=0, max=100, step=1).classes("min-w-[100px]")

        def save_weight_changes():
            new_weights = {k: (inp.value or 0) for k, inp in weight_inputs.items()}
            total = sum(new_weights.values())
            if total != 100:
                ui.notify(f"Weights sum to {total}, not 100 — adjust before saving.", type="warning")
                return
            fit_score.save_weights(new_weights, get_active_client_id())
            ui.notify("✅ Weights saved — re-run Fit Score ranking to see the effect.", type="positive")

        ui.button("Save weights", on_click=save_weight_changes).props("dense")

        ui.markdown("---")
        ui.label("Which score signals are converting? Re-weight the score:").classes("font-bold").style("font-size:12.5px;")
        reweight_area = ui.column().classes("w-full")

        def run_reweight_suggestion():
            reweight_area.clear()
            result = fit_score.suggest_reweight(get_active_client_id())
            with reweight_area:
                if result["mode"] == "insufficient":
                    ui.label(result["message"]).style(f"color:{COLORS['text_muted']};font-size:11.5px;")
                    return
                ui.label(f"From {result['n_pos']} positive (met/owns) and {result['n_neg']} pass outcomes:").style(
                    f"color:{COLORS['text_muted']};font-size:11.5px;")
                for c in result["components"]:
                    move_str = f"+{c['move']}" if c["move"] > 0 else str(c["move"])
                    move_clr = "#4ADE80" if c["move"] > 0 else "#F87171" if c["move"] < 0 else COLORS["text_muted"]
                    ui.label(f"{c['label']}: current {c['cur']} → suggested {c['suggested']} ({move_str}) · "
                              f"lift {c['lift']} (avg {c['mean_pos']} converters vs {c['mean_neg']} passes)").style(
                        f"color:{move_clr};font-size:11.5px;")

        ui.button("Check for a re-weight suggestion", on_click=run_reweight_suggestion).props("dense")


# ─────────────────────────────────────────────────────────────────────────
# SEC Intelligence tab — 13D/13G ownership-stake alerts + 13F institutional
# holders for this client and its full peer universe (config.client_config
# .CP(), the same peer list Peer Cross-Targeting above manages). Data comes
# from core/sec_filings.py, which is cache-first: this tab reads whatever
# is cached (kept warm by app_nicegui.py's startup hook for 13D/13G) rather
# than blocking page render on a live SEC call — the two Refresh buttons
# below are the only things that hit the network from inside a page render,
# and both are explicit, user-initiated actions.
# ─────────────────────────────────────────────────────────────────────────
def _render_sec_intelligence_tab():
    ui.label("🏛️ SEC Intelligence").classes("text-lg font-bold")
    ui.label(
        "Ownership-stake filings (13D/13G) and institutional holders (13F) for this client and its full peer "
        "universe — tracked tickers come straight from the Peer Cross-Targeting list in Target Database, so "
        "adding a competitor there adds it here too."
    ).style(f"color:{COLORS['text_muted']};font-size:12px;")

    log = sec_filings.get_last_refresh_log()
    with ui.row().classes("w-full items-center gap-3").style("margin-top:6px;"):
        if log:
            ui.label(f"Last 13D/13G refresh: {log.get('finished_at', '—')[:19].replace('T', ' ')}").style(
                f"color:{COLORS['text_muted']};font-size:12px;"
            )
        else:
            ui.label("No refresh has run yet — the app's startup hook kicks one off automatically each launch, "
                      "or trigger one now:").style(f"color:{COLORS['text_muted']};font-size:12px;")

    # Surface a top-level 13F failure explicitly. Real bug found 2026-07-10:
    # if the SEC bulk download/unzip/parse itself fails (network error, SEC
    # blocking the request, an unexpected file format), refresh_all catches
    # it and stamps "13f_error" onto every entry in the run log — but NO
    # per-ticker 13F cache key ever gets written, since the failure happens
    # before refresh_13f_for_tracked_tickers's per-ticker loop even starts.
    # get_cached_13f_holders then returns its generic "not yet fetched"
    # default for every single ticker, indistinguishable from "nobody has
    # clicked Refresh 13F yet" — the real error was silently dropped, only
    # ever visible in this log dict which nothing rendered. Surfacing it
    # here means a top-level failure (e.g. this being the very first live
    # run against sec.gov from this machine) is visible instead of looking
    # like "no institutional data exists for any tracked ticker."
    if log:
        _13f_errors = {
            r["ticker"]: r["13f_error"]
            for r in log.get("results", [])
            if r.get("13f_error")
        }
        if _13f_errors:
            _sample_ticker, _sample_err = next(iter(_13f_errors.items()))
            with ui.row().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border-left:4px solid {COLORS['danger']};"
                f"border-radius:4px;padding:8px 12px;margin-top:4px;"
            ):
                ui.label(
                    f"⚠️ 13F refresh failed for all {len(_13f_errors)} tracked ticker(s) — the SEC bulk "
                    f"download/parse itself errored before any institutional-holder data could be saved. "
                    f"This is not \"no data exists\"; it's a failed fetch. Error: {_sample_err}"
                ).style(f"color:{COLORS['text_body']};font-size:12px;")

    sec_container = ui.column().classes("w-full gap-2").style("margin-top:8px;")

    def render_sec_list():
        sec_container.clear()
        with sec_container:
            for ticker, name in sec_filings.tracked_tickers():
                d13 = sec_filings.get_cached_13d_13g(ticker, refresh_if_stale=False)
                f13 = sec_filings.get_cached_13f_holders(ticker)
                filings = d13.get("filings", [])
                holders = f13.get("holders", [])
                label = f"{ticker} — {name} · {len(filings)} 13D/13G on file"
                if f13.get("quarter"):
                    label += f" · {len(holders)} institutional holders ({f13['quarter']})"
                with ui.expansion(label).classes("w-full"):
                    if d13.get("_error"):
                        ui.label(f"⚠️ 13D/13G fetch error: {d13['_error']}").style(f"color:{COLORS['warning']};font-size:11.5px;")
                    if not filings:
                        ui.label("No 13D/13G filings cached yet for this ticker.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    else:
                        for f in filings[:10]:
                            ui.label(f"{f['date']} · {f['form']} · {f['title']}").style(f"color:{COLORS['text_body']};font-size:12px;")
                            if f.get("link"):
                                ui.link("View on EDGAR ↗", f["link"], new_tab=True).style("font-size:11.5px;")

                    ui.markdown("---")
                    if f13.get("_error") and f13["_error"] != "not yet fetched":
                        ui.label(f"⚠️ 13F fetch error: {f13['_error']}").style(f"color:{COLORS['warning']};font-size:11.5px;")
                    if not holders:
                        ui.label("No 13F institutional-holder data cached yet — use 'Refresh 13F Institutional "
                                 "Holders' below.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    else:
                        for h in holders[:10]:
                            # size_known=False: confirmed via EDGAR full-text search, but this holder's
                            # exact share/dollar size wasn't fetched (see
                            # sec_filings._search_holders_for_ticker's docstring) — don't show the
                            # sentinel shares=1/value=0 as if it were a real reported figure.
                            size_text = f"{h['shares']:,} shares (${h['value']:,} reported)" if h.get("size_known", True) \
                                else "position size not available"
                            ui.label(f"{h['filer']} — {size_text}").style(
                                f"color:{COLORS['text_body']};font-size:12px;"
                            )

    render_sec_list()

    # Was: plain `def` handlers calling sec_filings.refresh_all(...)
    # directly — a real, blocking network call (13F alone downloads a
    # multi-ticker, tens-of-MB SEC bulk dataset). NiceGUI runs a sync
    # click handler straight on the server's single asyncio event loop, so
    # this froze the ENTIRE app for every connected user until the whole
    # download finished (or hung/timed out) — not just this button, and
    # often not even flushing the "Refreshing..." toast first, since a
    # non-yielding sync call blocks outgoing websocket messages too. That's
    # exactly what "I clicked it and nothing happened" looks like from the
    # browser: no toast, no error, no visible progress, just silence.
    # app_nicegui.py's startup hooks already established the correct fix
    # for this exact class of call (asyncio.to_thread, see
    # _kick_off_sec_refresh) — applying the same pattern here so a manual
    # refresh behaves like the automatic startup one: the UI stays
    # responsive and the toast/notify actually show up immediately.
    async def refresh_13d13g():
        # force_13d13g=True: a manual "Refresh Now" click must always hit
        # SEC live, not silently return an already-cached snapshot because
        # it's under the 24h TTL (see get_cached_13d_13g's force param —
        # without this, repeated clicks reported "refresh complete" while
        # actually doing nothing, which is exactly what "the data is stuck
        # on old filings" looks like from the browser).
        ui.notify("Refreshing 13D/13G filings from SEC EDGAR — this hits the network now and may take a few seconds per ticker.")
        try:
            await asyncio.to_thread(sec_filings.refresh_all, False, True)
            ui.notify("13D/13G refresh complete.", type="positive")
        except Exception as e:
            ui.notify(f"Refresh failed: {e}", type="negative")
        render_sec_list()

    async def refresh_13f():
        # As of 2026-07-12 this runs one lightweight EDGAR full-text search per
        # tracked ticker (see sec_filings.refresh_13f_for_tracked_tickers) instead
        # of downloading SEC's entire quarterly bulk dataset — much faster, but
        # still a handful of sequential network requests, so it stays behind
        # asyncio.to_thread and an explicit button rather than a page render.
        ui.notify(
            "Refreshing 13F institutional holders from SEC EDGAR (targeted per-ticker search) — "
            "this may take a few seconds per tracked ticker.",
            type="warning",
        )
        try:
            await asyncio.to_thread(sec_filings.refresh_all, True)
            ui.notify("13F refresh complete.", type="positive")
        except Exception as e:
            ui.notify(f"Refresh failed: {e}", type="negative")
        render_sec_list()

    with ui.row().classes("w-full gap-3").style("margin-top:8px;"):
        ui.button("🔄 Refresh 13D/13G Now", on_click=refresh_13d13g).props("color=primary dense")
        ui.button("📊 Refresh 13F Institutional Holders (slow)", on_click=refresh_13f).props("flat dense")

    ui.markdown("---")
    ui.label(
        "If a ticker fails to resolve to a SEC CIK (rare — recent IPOs, ADRs, or a ticker change), add a manual "
        "override in core/sec_filings.py's MANUAL_CIK_OVERRIDES dict."
    ).style(f"color:{COLORS['text_muted']};font-size:11px;")
