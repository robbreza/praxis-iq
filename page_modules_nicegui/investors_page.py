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
  and its "Export schedule as CSV" / "Export meeting notes CSV"
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
- The "Scan IRConnect Inbox for Meeting Confirmations" feature is ported,
  but folded into the existing "Sync IR Inbox" pipeline above (see
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
from core import analyst_coverage, consensus, db, documents, fit_score, inbox_queue, mail_gateway, market_data, nobo_engine, prospecting, risk_scorecard, sec_filings
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
from core.textfmt import pretty_name
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

def _load_ndr_requests():
    """This client's inbound NDR requests. EMPTY when none have been logged.

    There used to be a hardcoded fallback here — three invented requests naming real
    sell-side analysts (Scott Buck / H.C. Wainwright, Gary Prestopino / Barrington,
    Barry Sine / Litchfield Hills). Because it fired for ANY tenant with no saved
    requests, every client's pipeline showed USIO's analysts asking for meetings —
    and it PERSISTED them to that tenant's store. Northlake's "Ranked actions for
    management" read "Respond to Barry Sine (Litchfield Hills Research)".

    That is the same trap load_meeting_log documents: a fabricated REQUEST asserts a
    named person asked for something they didn't. An unworked request list is empty."""
    return db.load_json("ndr_requests.json", default=[]) or []


def _save_ndr_requests(records):
    db.save_json("ndr_requests.json", records)


def _mailto(to, subject, body, label):
    href = f"mailto:{to}?subject={quote(subject)}&body={quote(body)}"
    return ui.link(f"{label}", href).style(f"color:{COLORS['accent_light']};")


def _tel_href(phone):
    """A tel: link target from a display phone string — keeps digits and a
    leading +, drops spaces/dashes/parens so the dialer gets a clean number."""
    return "tel:" + "".join(ch for ch in str(phone) if ch.isdigit() or ch == "+")


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
# Aligned with the valuation peer set (config.CP()). The Fit-Score tier vocab is
# core (tight comp, weight 2) / close (broader, weight 1) / large (mega-cap
# reference, weight 0.5); CP() normalizes "large" -> valuation "reference" (out
# of the median) and core/close -> "primary". segment / closest_analog feed the
# benchmarking display. Kept in sync so the two systems (which share the DB key
# "peer_universe.csv") never fight — dropping the retired PRTH/EEFT/PAX here is
# what stops _load_peer_universe re-adding them.
DEFAULT_PEER_UNIVERSE = [
    {"ticker": "RPAY", "name": "Repay Holdings", "sector": "Integrated card + ACH + billing/output", "ev_rev": 2.8, "weight": 2.0, "tier": "core", "segment": "Integrated card + ACH + billing/output", "closest_analog": True},
    {"ticker": "CASS", "name": "Cass Information Systems", "sector": "Payment information / billing", "ev_rev": 2.2, "weight": 2.0, "tier": "core", "segment": "Payment information / billing"},
    {"ticker": "CSGS", "name": "CSG Systems", "sector": "Billing / customer comms", "ev_rev": 2.2, "weight": 2.0, "tier": "core", "segment": "Billing / customer comms (output)"},
    {"ticker": "PSFE", "name": "Paysafe", "sector": "Integrated payments", "ev_rev": 1.5, "weight": 2.0, "tier": "core", "segment": "Integrated payments"},
    {"ticker": "PAY", "name": "Paymentus Holdings", "sector": "Bill presentment / EBPP", "ev_rev": 2.5, "weight": 2.0, "tier": "core", "segment": "Bill presentment / EBPP (output)"},
    {"ticker": "FOUR", "name": "Shift4 Payments", "sector": "Card acceptance / PayFac", "ev_rev": 4.2, "weight": 1.0, "tier": "close", "segment": "Card acceptance / PayFac"},
    {"ticker": "GDOT", "name": "Green Dot", "sector": "Prepaid / card issuing", "ev_rev": 1.2, "weight": 1.0, "tier": "close", "segment": "Prepaid / card issuing"},
    {"ticker": "FI", "name": "Fiserv", "sector": "Large-cap processor", "ev_rev": 5.0, "weight": 0.5, "tier": "large", "segment": "Large-cap processor (reference)"},
    {"ticker": "GPN", "name": "Global Payments", "sector": "Large-cap processor", "ev_rev": 4.5, "weight": 0.5, "tier": "large", "segment": "Large-cap processor (reference)"},
    {"ticker": "TOST", "name": "Toast", "sector": "Large-cap fintech", "ev_rev": 3.5, "weight": 0.5, "tier": "large", "segment": "Large-cap fintech (reference)"},
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
    # get_consensus(), not the seed: this reads period_guidance to build an EV/Revenue
    # multiple for outreach copy, and the guidance override is exactly the thing that
    # moves when the CFO revises. Reading the seed here would put a stale multiple in
    # front of an investor — which is the failure this function's docstring says it
    # exists to avoid.
    from core.consensus import get_consensus
    snap = market_data.get_snapshot(CT("ticker"))
    last_price = snap["last_price"] if snap and snap.get("last_price") is not None else CT("last_price", None)
    if last_price is None:
        return None
    seed = get_consensus(get_active_client_id())
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
# Data provenance — every name in the universe carries a Source tag so the UI
# shows where it came from. The seed is "Seed (demo)"; real SEC-sourced names
# (13F holders, 13D/13G filers, funds holding the peer set) are merged in from
# cached EDGAR data, each with its own tag. This is the honest answer to "why
# isn't the database bigger": it grows from authoritative sources, not by hand.
# ─────────────────────────────────────────────────────────────────────────
SOURCE_COLORS = {
    "Seed (demo)": "#64748B", "Seed + SEC-confirmed": "#0F766E",
    "SEC 13F": "#15803D", "SEC 13D/G": "#B45309", "SEC 13F + 13D/G": "#15803D",
    "Peer 13F": "#1E40AF", "Peer 13F (T1)": "#1E3A8A", "Peer 13F (T2)": "#4F46E5",
}

# Comp tiering for peer-overlap prospecting — peers first, then industry.
# Tier 1 = tightest small/mid-cap payment comps (highest-signal holders — a fund
# in Repay or Cass but not USIO is a real conversion target); Tier 2 = broader
# payments names. Anything not listed defaults to T2. The large-cap REFERENCE
# peers (FI / GPN / TOST) are deliberately excluded from prospecting entirely —
# a fund holding Fiserv because it's in the S&P 500 tells you nothing about
# micro-cap-payments interest, so their index/pension holders would be pure noise
# (see the tier=="reference" skip in _sec_universe_records).
_PEER_TIER = {"RPAY": 1, "CASS": 1, "CSGS": 1, "PSFE": 1, "PAY": 1, "FOUR": 2, "GDOT": 2}


def _source_color(src):
    return SOURCE_COLORS.get(src, "#15803D")


def _apply_peer_tier(rec, tier):
    """Stamp a peer-overlap prospect with its comp tier — the tighter the comp
    it holds, the higher-signal the prospect."""
    rec["_peer_tier"] = tier
    rec["Source"] = f"Peer 13F (T{tier})"
    rec["Peer_Score"] = 35 if tier == 1 else 20
    rec["Action"] = ("Holds a close comp — high-signal NDR prospect" if tier == 1
                     else "Holds an industry name — broader prospect")


_NORM_SUFFIXES = {"inc", "incorporated", "llc", "lp", "llp", "corp", "corporation", "co", "company",
                  "ltd", "limited", "plc", "trust", "sa", "ag", "nv", "the", "group", "holdings"}


def _norm_name(n):
    """Normalize a manager name for cross-source dedup — lowercase, drop
    punctuation, and strip common corporate suffixes so 'Dimensional Fund
    Advisors' (seed) and 'DIMENSIONAL FUND ADVISORS LP' (SEC) match."""
    tokens = "".join(c if c.isalnum() else " " for c in str(n).lower()).split()
    return "".join(t for t in tokens if t not in _NORM_SUFFIXES)


# SEC 13F filer cities → the same metro-region labels the seed universe uses,
# so real filers unify into the geographic breakdown ("Where they are") instead
# of a flat "Unknown (SEC)" bucket. Keyed by uppercase city. Unmapped US cities
# fall back to "City, ST"; non-US filers group under "International".
_US_STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI",
              "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI",
              "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC",
              "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
              "VT", "VA", "WA", "WV", "WI", "WY", "DC"}
# Roadshow metros — a ~60-mile radius (a day's drive), the way an IR team actually plans an NDR,
# NOT a broad Census region. Cities beyond 60mi of a hub are their OWN stop; a state full of those
# (Wisconsin: Milwaukee ~90mi from Chicago, Madison further) is a scattered, hard-to-cover book.
# The old map lumped Wayzata + Minneapolis + Milwaukee into "Chicago / Midwest" — 350+ miles you
# can't roadshow in one trip — and did the same to Texas (Dallas/Austin/Houston) and Florida.
_SEC_CITY_METRO = {
    # New York metro — incl. lower-CT (Gold Coast) + near-NJ + Westchester, all inside 60mi
    "NEW YORK": "New York, NY", "BROOKLYN": "New York, NY", "NEW YORK CITY": "New York, NY",
    "GREENWICH": "New York, NY", "STAMFORD": "New York, NY", "DARIEN": "New York, NY",
    "WESTPORT|CT": "New York, NY", "NORWALK|CT": "New York, NY", "NEW CANAAN": "New York, NY",
    "RYE|NY": "New York, NY", "WHITE PLAINS": "New York, NY", "PURCHASE": "New York, NY",
    "JERSEY CITY": "New York, NY", "SHORT HILLS": "New York, NY", "SUMMIT|NJ": "New York, NY",
    "GARDEN CITY|NY": "New York, NY", "MELVILLE": "New York, NY",
    # Boston
    "BOSTON": "Boston, MA", "CAMBRIDGE|MA": "Boston, MA", "WELLESLEY": "Boston, MA",
    "WALTHAM": "Boston, MA", "NEWTON|MA": "Boston, MA", "NEEDHAM": "Boston, MA", "PLYMOUTH|MA": "Boston, MA",
    # Chicago (NOT Minneapolis/Milwaukee)
    "CHICAGO": "Chicago, IL", "OAK BROOK": "Chicago, IL", "NAPERVILLE": "Chicago, IL",
    "EVANSTON|IL": "Chicago, IL", "NORTHBROOK": "Chicago, IL", "LAKE FOREST|IL": "Chicago, IL",
    "ROSEMONT": "Chicago, IL", "LISLE": "Chicago, IL",
    # Minneapolis–St. Paul (Twin Cities) — its own stop, ~60mi radius
    "MINNEAPOLIS": "Minneapolis-St. Paul, MN", "ST. PAUL": "Minneapolis-St. Paul, MN",
    "WAYZATA": "Minneapolis-St. Paul, MN", "ROSEMOUNT": "Minneapolis-St. Paul, MN",
    "MINNETONKA": "Minneapolis-St. Paul, MN", "PLYMOUTH|MN": "Minneapolis-St. Paul, MN",
    "EDEN PRAIRIE": "Minneapolis-St. Paul, MN", "EDINA": "Minneapolis-St. Paul, MN",
    "BLOOMINGTON|MN": "Minneapolis-St. Paul, MN", "MENDOTA HEIGHTS": "Minneapolis-St. Paul, MN",
    # Wisconsin — the toughest book: Milwaukee is ~90mi from Chicago (a flight/long haul), Madison
    # further, and funds scatter across the state with no dense hub.
    "MILWAUKEE": "Milwaukee / Wisconsin", "BROOKFIELD": "Milwaukee / Wisconsin",
    "MADISON|WI": "Milwaukee / Wisconsin", "MEQUON": "Milwaukee / Wisconsin",
    # SoCal / Bay / Philly
    "SOUTH PASADENA": "Los Angeles, CA", "PASADENA": "Los Angeles, CA",
    "LOS ANGELES": "Los Angeles, CA", "IRVINE": "Los Angeles, CA", "NEWPORT BEACH": "Los Angeles, CA",
    "SANTA MONICA": "Los Angeles, CA", "EL SEGUNDO": "Los Angeles, CA",
    "SAN FRANCISCO": "San Francisco / Bay Area", "FOLSOM": "San Francisco / Bay Area",
    "SAN MATEO": "San Francisco / Bay Area", "PALO ALTO": "San Francisco / Bay Area",
    "MENLO PARK": "San Francisco / Bay Area", "SAN JOSE": "San Francisco / Bay Area",
    "OAKLAND": "San Francisco / Bay Area", "BERKELEY": "San Francisco / Bay Area",
    "MALVERN": "Philadelphia, PA", "BALA CYNWYD": "Philadelphia, PA",
    "PHILADELPHIA": "Philadelphia, PA", "RADNOR": "Philadelphia, PA", "CONSHOHOCKEN": "Philadelphia, PA",
    "WAYNE|PA": "Philadelphia, PA", "WEST CONSHOHOCKEN": "Philadelphia, PA",
    "BALTIMORE": "Baltimore / DC", "WASHINGTON": "Baltimore / DC", "BETHESDA": "Baltimore / DC",
    "MCLEAN": "Baltimore / DC", "ARLINGTON": "Baltimore / DC",
    # Texas — three separate stops (Dallas–Austin–Houston are 200+ mi apart)
    "DALLAS": "Dallas, TX", "FORT WORTH": "Dallas, TX", "PLANO": "Dallas, TX", "IRVING": "Dallas, TX",
    "AUSTIN": "Austin, TX",
    "HOUSTON": "Houston, TX",
    "DENVER": "Denver, CO", "BOULDER": "Denver, CO", "GREENWOOD VILLAGE": "Denver, CO",
    # Florida — Miami/South-FL vs Tampa are ~280mi apart, separate
    "MIAMI": "Miami / South FL", "PALM BEACH": "Miami / South FL", "BOCA RATON": "Miami / South FL",
    "NAPLES": "Miami / South FL", "FORT LAUDERDALE": "Miami / South FL", "AVENTURA": "Miami / South FL",
    "TAMPA": "Tampa, FL", "ST. PETERSBURG": "Tampa, FL",
    "ATLANTA": "Atlanta, GA", "SEATTLE": "Seattle, WA", "BELLEVUE": "Seattle, WA",
    # St. Louis — all spelling variants normalise to "ST. LOUIS" (see _norm_city) — + inner-ring suburbs
    "ST. LOUIS": "St. Louis, MO", "CLAYTON|MO": "St. Louis, MO", "CHESTERFIELD": "St. Louis, MO",
    "DES PERES": "St. Louis, MO", "CREVE COEUR": "St. Louis, MO", "TOWN AND COUNTRY": "St. Louis, MO",
    "BALLWIN": "St. Louis, MO", "KIRKWOOD": "St. Louis, MO", "MARYLAND HEIGHTS": "St. Louis, MO",
    # Kansas City metro (spans MO/KS)
    "KANSAS CITY": "Kansas City, MO", "OVERLAND PARK": "Kansas City, MO", "LEAWOOD": "Kansas City, MO",
    # ── Fuller CA coverage — state-qualified. Bay Area (Marin/East Bay/Peninsula), LA, San Diego,
    #    Sacramento — NOT all lumped into LA; each city to its true ~60-mile metro. ──
    "MILL VALLEY|CA": "San Francisco / Bay Area", "ORINDA|CA": "San Francisco / Bay Area",
    "WALNUT CREEK|CA": "San Francisco / Bay Area", "GREENBRAE|CA": "San Francisco / Bay Area",
    "NOVATO|CA": "San Francisco / Bay Area", "BURLINGAME|CA": "San Francisco / Bay Area",
    "FOSTER CITY|CA": "San Francisco / Bay Area", "LAFAYETTE|CA": "San Francisco / Bay Area",
    "CONCORD|CA": "San Francisco / Bay Area", "LARKSPUR|CA": "San Francisco / Bay Area",
    "SAN RAFAEL|CA": "San Francisco / Bay Area", "TIBURON|CA": "San Francisco / Bay Area",
    "SAUSALITO|CA": "San Francisco / Bay Area", "EMERYVILLE|CA": "San Francisco / Bay Area",
    "REDWOOD CITY|CA": "San Francisco / Bay Area", "SAN CARLOS|CA": "San Francisco / Bay Area",
    "MOUNTAIN VIEW|CA": "San Francisco / Bay Area",
    "LAGUNA BEACH|CA": "Los Angeles, CA", "VALENCIA|CA": "Los Angeles, CA", "CALABASAS|CA": "Los Angeles, CA",
    "TORRANCE|CA": "Los Angeles, CA", "MANHATTAN BEACH|CA": "Los Angeles, CA", "BEVERLY HILLS|CA": "Los Angeles, CA",
    "WESTLAKE VILLAGE|CA": "Los Angeles, CA", "LONG BEACH|CA": "Los Angeles, CA", "MARINA DEL REY|CA": "Los Angeles, CA",
    "CULVER CITY|CA": "Los Angeles, CA", "GLENDALE|CA": "Los Angeles, CA", "SHERMAN OAKS|CA": "Los Angeles, CA",
    "SAN DIEGO|CA": "San Diego, CA", "CORONADO|CA": "San Diego, CA", "RANCHO SANTA FE|CA": "San Diego, CA",
    "ENCINITAS|CA": "San Diego, CA", "LA JOLLA|CA": "San Diego, CA", "DEL MAR|CA": "San Diego, CA",
    "CARLSBAD|CA": "San Diego, CA", "SOLANA BEACH|CA": "San Diego, CA",
    "SACRAMENTO|CA": "Sacramento, CA", "WEST SACRAMENTO|CA": "Sacramento, CA", "FOLSOM|CA": "Sacramento, CA",
    "ROSEVILLE|CA": "Sacramento, CA", "EL DORADO HILLS|CA": "Sacramento, CA",
    # ── Fuller PA coverage — Philadelphia (Main Line) vs Pittsburgh (both real in the book) ──
    "PITTSBURGH|PA": "Pittsburgh, PA", "WARRENDALE|PA": "Pittsburgh, PA", "SEWICKLEY|PA": "Pittsburgh, PA",
    "CRANBERRY TOWNSHIP|PA": "Pittsburgh, PA", "WEXFORD|PA": "Pittsburgh, PA",
    "BERWYN|PA": "Philadelphia, PA", "NEWTOWN SQUARE|PA": "Philadelphia, PA", "OAKS|PA": "Philadelphia, PA",
    "DEVON|PA": "Philadelphia, PA", "PAOLI|PA": "Philadelphia, PA", "VILLANOVA|PA": "Philadelphia, PA",
    "WEST CHESTER|PA": "Philadelphia, PA", "KING OF PRUSSIA|PA": "Philadelphia, PA",
    # ── Sweep (2026-07-21): fold remaining suburbs into their true ~60-mile metro, state-qualified. ──
    # Detroit / Grand Rapids (MI)
    "HUNTINGTON WOODS|MI": "Detroit, MI", "BINGHAM FARMS|MI": "Detroit, MI", "BLOOMFIELD HILLS|MI": "Detroit, MI",
    "NOVI|MI": "Detroit, MI", "SOUTHFIELD|MI": "Detroit, MI", "BIRMINGHAM|MI": "Detroit, MI", "PLYMOUTH|MI": "Detroit, MI",
    "TROY|MI": "Detroit, MI", "FARMINGTON HILLS|MI": "Detroit, MI", "ANN ARBOR|MI": "Detroit, MI",
    "HOLLAND|MI": "Grand Rapids, MI", "ADA|MI": "Grand Rapids, MI", "GRAND RAPIDS|MI": "Grand Rapids, MI",
    # Richmond (VA) + NoVa / Baltimore into the Baltimore/DC cluster
    "RICHMOND|VA": "Richmond, VA", "GLEN ALLEN|VA": "Richmond, VA",
    "HERNDON|VA": "Baltimore / DC", "MCLEAN|VA": "Baltimore / DC", "RESTON|VA": "Baltimore / DC",
    "ALEXANDRIA|VA": "Baltimore / DC", "ROCKVILLE|MD": "Baltimore / DC", "HUNT VALLEY|MD": "Baltimore / DC",
    "TOWSON|MD": "Baltimore / DC", "COLUMBIA|MD": "Baltimore / DC",
    # Upstate NY + Long Island / CT gold-coast into New York
    "ALBANY|NY": "Albany, NY", "GLENMONT|NY": "Albany, NY",
    "BUFFALO|NY": "Buffalo, NY", "ORCHARD PARK|NY": "Buffalo, NY",
    "ROCHESTER|NY": "Rochester, NY", "FAIRPORT|NY": "Rochester, NY", "PITTSFORD|NY": "Rochester, NY",
    "HAUPPAUGE|NY": "New York, NY", "ROWAYTON|CT": "New York, NY",
    # Salt Lake City
    "SALT LAKE CITY|UT": "Salt Lake City, UT", "PARK CITY|UT": "Salt Lake City, UT", "MIDVALE|UT": "Salt Lake City, UT",
    "MURRAY|UT": "Salt Lake City, UT", "SANDY|UT": "Salt Lake City, UT", "DRAPER|UT": "Salt Lake City, UT",
    "COTTONWOOD HEIGHTS|UT": "Salt Lake City, UT",
    # Denver suburbs
    "ENGLEWOOD|CO": "Denver, CO", "LONE TREE|CO": "Denver, CO", "GOLDEN|CO": "Denver, CO",
    "LITTLETON|CO": "Denver, CO", "CENTENNIAL|CO": "Denver, CO", "AURORA|CO": "Denver, CO",
    # Hartford
    "HARTFORD|CT": "Hartford, CT", "FARMINGTON|CT": "Hartford, CT", "WINDSOR|CT": "Hartford, CT",
    "MERIDEN|CT": "Hartford, CT", "WATERBURY|CT": "Hartford, CT", "WEST HARTFORD|CT": "Hartford, CT",
    # Phoenix
    "PHOENIX|AZ": "Phoenix, AZ", "PEORIA|AZ": "Phoenix, AZ", "SCOTTSDALE|AZ": "Phoenix, AZ",
    "MESA|AZ": "Phoenix, AZ", "TEMPE|AZ": "Phoenix, AZ", "CHANDLER|AZ": "Phoenix, AZ", "GILBERT|AZ": "Phoenix, AZ",
    # Chicago suburbs
    "OAKBROOK TERRACE|IL": "Chicago, IL", "SCHAUMBURG|IL": "Chicago, IL", "WHEATON|IL": "Chicago, IL",
    "HINSDALE|IL": "Chicago, IL", "ITASCA|IL": "Chicago, IL", "DEERFIELD|IL": "Chicago, IL",
    # Nashville / Indianapolis
    "NASHVILLE|TN": "Nashville, TN", "BRENTWOOD|TN": "Nashville, TN", "FRANKLIN|TN": "Nashville, TN",
    "CARMEL|IN": "Indianapolis, IN", "INDIANAPOLIS|IN": "Indianapolis, IN", "FISHERS|IN": "Indianapolis, IN",
    "ZIONSVILLE|IN": "Indianapolis, IN",
    # Atlanta suburbs
    "ALPHARETTA|GA": "Atlanta, GA", "SUWANEE|GA": "Atlanta, GA", "ROSWELL|GA": "Atlanta, GA",
    "MARIETTA|GA": "Atlanta, GA", "SANDY SPRINGS|GA": "Atlanta, GA",
    # Charlotte (+ SC border suburbs)
    "CHARLOTTE|NC": "Charlotte, NC", "ROCK HILL|SC": "Charlotte, NC", "FORT MILL|SC": "Charlotte, NC",
    # Portland OR (state-qualified vs Portland ME) + Seattle
    "PORTLAND|OR": "Portland, OR", "LAKE OSWEGO|OR": "Portland, OR", "TIGARD|OR": "Portland, OR",
    "BEAVERTON|OR": "Portland, OR", "CAMAS|WA": "Portland, OR",
    "PUYALLUP|WA": "Seattle, WA", "TACOMA|WA": "Seattle, WA", "REDMOND|WA": "Seattle, WA", "KIRKLAND|WA": "Seattle, WA",
    "BOTHELL|WA": "Seattle, WA", "ISSAQUAH|WA": "Seattle, WA", "SAMMAMISH|WA": "Seattle, WA",
    "MERCER ISLAND|WA": "Seattle, WA", "RENTON|WA": "Seattle, WA", "EVERETT|WA": "Seattle, WA",
    "WOODINVILLE|WA": "Seattle, WA", "BAINBRIDGE ISLAND|WA": "Seattle, WA", "EDMONDS|WA": "Seattle, WA",
    # Kansas City (KS side)
    "SHAWNEE MISSION|KS": "Kansas City, MO", "LENEXA|KS": "Kansas City, MO",
}


# Major international financial hubs — a foreign fund lands in its city cluster (a real roadshow
# stop: a London or Toronto swing) rather than one undifferentiated "International" blob. Keyed by
# normalised city; province/country suffixes ("TORONTO ONTARIO", "PARIS FRANCE") are stripped first.
# Only reached for non-US state codes, so ambiguous names (Burlington ON) can't collide with US.
_INTL_CITY_METRO = {
    "TORONTO": "Toronto, ON", "MISSISSAUGA": "Toronto, ON", "OAKVILLE": "Toronto, ON",
    "MARKHAM": "Toronto, ON", "VAUGHAN": "Toronto, ON", "RICHMOND HILL": "Toronto, ON",
    "BURLINGTON": "Toronto, ON", "WATERLOO": "Toronto, ON",
    "MONTREAL": "Montreal, QC", "VANCOUVER": "Vancouver, BC", "CALGARY": "Calgary, AB",
    "LONDON": "London, UK", "EDINBURGH": "Edinburgh, UK",
    "PARIS": "Paris, FR", "FRANKFURT": "Frankfurt, DE", "FRANKFURT AM MAIN": "Frankfurt, DE",
    "MUNICH": "Munich, DE", "BERLIN": "Berlin, DE",
    # Switzerland — German-Swiss hub (Zurich, incl. the Zug/Pfäffikon hedge-fund belt) vs French-
    # Swiss (Geneva). Zurich↔Geneva is ~175mi, so two stops even at a 60-mile radius.
    "ZURICH": "Zurich, CH", "ZUG": "Zurich, CH", "BASEL": "Zurich, CH", "BERN": "Zurich, CH",
    "PFAFFIKON": "Zurich, CH", "LUCERNE": "Zurich, CH", "WINTERTHUR": "Zurich, CH",
    "SCHINDELLEGI": "Zurich, CH", "BAAR": "Zurich, CH", "WOLLERAU": "Zurich, CH", "FREIENBACH": "Zurich, CH",
    "GENEVA": "Geneva, CH", "GENEVE": "Geneva, CH", "CAROUGE": "Geneva, CH", "LAUSANNE": "Geneva, CH",
    "NYON": "Geneva, CH", "COLOGNY": "Geneva, CH", "VEVEY": "Geneva, CH",
    # Italian-Swiss (Ticino) private-banking centre — its own stop; ~30mi to Milan but a
    # distinct cross-border booking hub, so kept Swiss rather than folded into Milan.
    "LUGANO": "Lugano, CH", "PARADISO": "Lugano, CH", "BELLINZONA": "Lugano, CH",
    "MANNO": "Lugano, CH", "CHIASSO": "Lugano, CH", "MENDRISIO": "Lugano, CH",
    "TOKYO": "Tokyo, JP", "HONG KONG": "Hong Kong", "CAUSEWAY BAY": "Hong Kong", "CENTRAL": "Hong Kong",
    "SINGAPORE": "Singapore", "SEOUL": "Seoul, KR", "DUBAI": "Dubai, AE", "MILAN": "Milan, IT",
    "BRUSSELS": "Brussels, BE", "LUXEMBOURG": "Luxembourg", "SENNINGERBERG": "Luxembourg",
    "STOCKHOLM": "Stockholm, SE", "AMSTERDAM": "Amsterdam, NL", "OSLO": "Oslo, NO",
    "COPENHAGEN": "Copenhagen, DK", "COPENHAGEN V": "Copenhagen, DK", "HELSINKI": "Helsinki, FI",
    "SYDNEY": "Sydney, AU", "MELBOURNE": "Melbourne, AU", "SAO PAULO": "Sao Paulo, BR",
    "WARSAW": "Warsaw, PL", "DUBLIN": "Dublin, IE",
}


def _norm_city(city):
    """Collapse the St. / Saint / St spelling variants that otherwise fragment a metro into
    separate rows (the data carries 'ST LOUIS', 'ST. LOUIS' and 'SAINT LOUIS' for the same city)."""
    c = (city or "").strip().upper()
    if c.startswith("SAINT "):
        return "ST. " + c[6:]
    if c.startswith("ST ") and not c.startswith("ST. "):
        return "ST. " + c[3:]
    return c


def _metro_from_city(city, state):
    """Map a 13F filer's HQ city/state to a ~60-mile roadshow metro label, so SEC-sourced holders
    and prospects land in the same geographic buckets. Spelling variants are normalised first (see
    _norm_city). Falls back to the normalised 'City, ST' for unmapped US cities and 'International'
    for non-US filers (SEC uses non-US state codes like X0/V8/M0/K3)."""
    c = _norm_city(city)
    st = (state or "").strip().upper()
    # State-qualified key first ("CONCORD|CA" ≠ Concord MA; "LONG BEACH|CA" ≠ Long Beach NY),
    # then the plain city key for unambiguous majors.
    if f"{c}|{st}" in _SEC_CITY_METRO:
        return _SEC_CITY_METRO[f"{c}|{st}"]
    if c in _SEC_CITY_METRO:
        return _SEC_CITY_METRO[c]
    if st and st not in _US_STATES:
        # Cluster the major international hubs (Toronto, London, Zurich...) — real roadshow stops —
        # rather than one undifferentiated "International" bucket. Foreign city strings vary wildly:
        # "TORONTO ONTARIO" / "TORONTO, ONTARIO" (city+province), "LONDON, EC4N 8AF" (city+postcode),
        # "CHIYODA-KU, TOKYO" (ward+city). Try the whole string and each comma-separated token, with
        # province/country suffixes stripped, and take the first that matches a known hub.
        parts = [c] + [p.strip() for p in c.split(",")]
        for cand in parts:
            for _suf in (" ONTARIO", " QUEBEC", " FRANCE", " GERMANY", " ENGLAND", " JAPAN", " CANADA",
                         " SWITZERLAND", " UK"):
                if cand.endswith(_suf):
                    cand = cand[: -len(_suf)].strip()
            if cand in _INTL_CITY_METRO:
                return _INTL_CITY_METRO[cand]
        return "International"
    if c and st:
        return f"{c.title()}, {st}"      # normalised so St / St. / Saint variants don't split
    if c:
        return c.title()
    return "Unknown (SEC)"


def _loc_line(r):
    """A prospect card's location, reconciled with the roadshow-metro aggregation. Shows the raw
    'City, ST' and, when the fund clusters into a DIFFERENT metro (e.g. Greenwich, CT → New York),
    appends that metro so the card matches the by-metro table instead of contradicting it."""
    city, state = r.get("city"), r.get("state")
    raw = ", ".join(x for x in [city, state] if x)
    metro = _metro_from_city(city, state)
    if not raw:
        return metro or "—"
    if metro and metro not in ("International", "Unknown (SEC)") and metro != raw:
        return f"{raw} · {metro} metro"
    return raw


def _shortlist_record(c):
    """A peer-prospect candidate captured as a 'shortlisted' NDR target (pipeline entry, no slot
    yet). Kept in trip['shortlist'] — NOT trip['meetings'] — so the slot-based schedule renderer is
    untouched until a target confirms (see NDR-pipeline design, phases 1→3)."""
    from datetime import datetime as _dt
    comps = ", ".join(sorted((c.get("comps") or {}).keys()))
    return {
        "institution": c.get("filer"),
        "city": c.get("city"), "state": c.get("state"),
        "metro": _metro_from_city(c.get("city"), c.get("state")),
        "conviction": c.get("conviction"),
        "peers": comps or ("Curated target" if c.get("kind") == "curated" else ""),
        "bucket": c.get("tier"),
        "status": "shortlisted", "source": "outbound",
        "added_at": _dt.now().strftime("%Y-%m-%d %H:%M"),
    }


def _shortlist_from_inst(inst):
    """Shortlist record from a scored Buy-Side institution (different shape than a peer-prospect
    candidate). Lets the Buy-Side list feed the same NDR pipeline (Phase 4B)."""
    from datetime import datetime as _dt
    peers = inst.get("Peer_Holdings") or []
    return {
        "institution": inst.get("Fund"),
        "city": inst.get("City"), "state": None, "metro": inst.get("Metro"),
        "conviction": inst.get("Engagement_Score"),
        "peers": ", ".join(peers) if peers else "",
        "bucket": "Holder" if inst.get("USIO_Holder") else "Tracked",
        "status": "shortlisted", "source": "outbound",
        "added_at": _dt.now().strftime("%Y-%m-%d %H:%M"),
    }


def _open_metro_select_dialog(metro, funds):
    """Click-a-metro → tick peer-owners → shortlist them onto an NDR. Used by the unified
    'Where they are' metro table (NDR pipeline — one list)."""
    funds = sorted(funds, key=lambda c: -(c.get("conviction") or 0))
    with ui.dialog() as dlg, ui.card().style("min-width:min(840px,95vw);max-width:95vw;"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label(f"{metro} — {len(funds)} peer-owner{'s' if len(funds) != 1 else ''} "
                     "(own a comp, not us)").classes("text-lg font-bold")
            ui.button(icon="close", on_click=dlg.close).props("flat round dense")
        if not funds:
            ui.label("No peer-owners in this metro.").style(f"color:{COLORS['text_muted']};")
            dlg.open(); return
        cand_by_filer = {c.get("filer"): c for c in funds}
        _open = [(i, t) for i, t in enumerate(_load_json("ndr_trips.json", [])) if t.get("status") != "Completed"]
        trip_opts = {str(i): (t.get("name") or f"NDR {i+1}") for i, t in _open}
        trip_opts["__new__"] = "＋ New NDR…"
        with ui.row().classes("w-full items-end gap-2").style(
                f"background:{COLORS['surface_hover_bg']};border-radius:8px;padding:8px 10px;margin-bottom:6px;"):
            ui.label("Tick funds below, then add them to an NDR as shortlisted targets.").style(
                f"color:{COLORS['text_muted']};font-size:12px;flex:1;")
            trip_sel = ui.select(trip_opts, value="__new__", label="NDR").props("dense outlined").style("min-width:170px;")
            new_name = ui.input("New NDR name", value=f"{metro} NDR").props("dense outlined").style("min-width:150px;")
            new_name.bind_visibility_from(trip_sel, "value", backward=lambda v: v == "__new__")
            add_btn = ui.button("Add selected", icon="playlist_add").props("dense color=primary")
        d_rows = []
        for c in funds:
            conv = c.get("conviction")
            peers = ", ".join(sorted((c.get("comps") or {}).keys()))
            d_rows.append({
                "_filer": c.get("filer"), "Fund": pretty_name(c.get("filer") or "—"),
                "City": c.get("city") or "—", "Category": c.get("tier") or "—",
                "Conviction": round(conv) if conv is not None else "—",
                "Peers held": peers or ("Curated target" if c.get("kind") == "curated" else "—"),
            })
        d_cols = [{"name": k, "label": k, "field": k, "align": "right" if k == "Conviction" else "left"}
                  for k in d_rows[0].keys() if k != "_filer"]
        tbl = ui.table(columns=d_cols, rows=d_rows, row_key="_filer",
                       selection="multiple").classes("w-full").props("dense flat")

        def _do_add():
            sel = tbl.selected
            if not sel:
                ui.notify("Tick at least one fund first.", type="warning"); return
            trips2 = _load_json("ndr_trips.json", [])
            if trip_sel.value == "__new__":
                nm = (new_name.value or "").strip()
                if not nm:
                    ui.notify("Name the new NDR.", type="warning"); return
                trips2.append({
                    "name": nm, "sponsor_bank": "", "dates": "TBD", "ndr_type": "in-person",
                    "city": metro, "focus": "", "team": [], "notes": "", "meetings": [], "shortlist": [],
                    "status": "Planning", "debrief": {}, "days": 2, "slots_per_day": 6,
                    "created": datetime.now().strftime("%Y-%m-%d"),
                })
                target, tname = trips2[-1], nm
            else:
                target = trips2[int(trip_sel.value)]
                tname = target.get("name") or "NDR"
            target.setdefault("shortlist", [])
            have = {s.get("institution") for s in target["shortlist"]} | \
                   {m.get("institution") for m in target.get("meetings", [])}
            added = 0
            for row in sel:
                c = cand_by_filer.get(row.get("_filer"))
                if not c or c.get("filer") in have:
                    continue
                target["shortlist"].append(_shortlist_record(c))
                have.add(c.get("filer")); added += 1
            _save_json("ndr_trips.json", trips2)
            skipped = len(sel) - added
            ui.notify(f"Shortlisted {added} fund(s) to '{tname}'"
                      + (f" · {skipped} already on it" if skipped else "")
                      + ". See NDR Planner → Active NDRs.", type="positive")
            dlg.close()
        add_btn.on_click(_do_add)
    dlg.open()


def _open_shortlist_outreach(entry, contact, on_invited):
    """NDR pipeline Phase 2 — the 'Contact' draft. Opens a pre-filled outreach email the user
    SENDS themselves (never auto-sent), and a button to mark the target Invited + log it. If no
    email is on file, the draft is still shown so they can reach out via their own channel."""
    fund = entry.get("institution", "")
    tkr, cname = CT("ticker"), CT("name")
    ir = CI()
    where = entry.get("metro") or entry.get("city") or "your area"
    peers = entry.get("peers") or "names in our space"
    greeting = (contact.get("name", "").split()[0] if contact.get("name") else "there")
    subject = f"{tkr} — meeting request during our {where} investor visit"
    body = (f"Hi {greeting},\n\nWe're planning an investor visit around {where} and would value 30 "
            f"minutes with your team. {pretty_name(fund)} holds {peers}, so {tkr}'s story should be "
            f"directly relevant.\n\nWould a meeting work during that window?\n\n"
            f"{ir.get('name', '')}\n{ir.get('title', 'Investor Relations')} · {cname} (NASDAQ: {tkr})")
    with ui.dialog() as dlg, ui.card().style(f"background:{COLORS['surface_bg']};min-width:min(520px,94vw);"):
        ui.label(f"Contact — {pretty_name(fund)}").classes("text-lg font-bold")
        ui.textarea(value=body).classes("w-full").props("rows=10")
        email = contact.get("email", "")
        if email:
            _mailto(email, subject, body, f"✉ Open email to {contact.get('name', 'the contact')} ({email})")
        else:
            ui.label("No contact email on file — reach out via your own channel, then mark Invited below.").style(
                f"color:{COLORS['text_muted']};font-size:12px;")
        with ui.row().classes("w-full justify-end gap-2").style("margin-top:6px;"):
            ui.button("Cancel", on_click=dlg.close).props("flat")

            def _mark():
                on_invited()
                dlg.close()
                ui.notify(f"{pretty_name(fund)} marked Invited and logged.", type="positive")
            ui.button("Mark as invited & log", icon="outgoing_mail", on_click=_mark).props("color=primary")
    dlg.open()


def _slot_time(slot_index):
    """Clock time for the Nth slot of a day — 90-min cadence from 9:00 AM (matches the Plan New NDR
    grid). Slot 0 → 9:00 AM, slot 1 → 10:30 AM, …"""
    total = slot_index * 90
    hr, mn = 9 + total // 60, total % 60
    hr12 = hr if hr <= 12 else hr - 12
    return f"{hr12 or 12}:{mn:02d} {'AM' if hr < 12 else 'PM'}"


def _ndr_capacity(trip):
    return int(trip.get("days") or 2), int(trip.get("slots_per_day") or 6)


def _next_open_slot(trip):
    """(day, slot_index) of the next free slot in the trip's day×slots grid, filling days in order.
    Counts existing meetings per day (works for legacy trips with no slot_index). (None, None) = full."""
    days, per = _ndr_capacity(trip)
    count = {}
    for m in trip.get("meetings", []):
        if m.get("type") == "break":
            continue
        d = m.get("day") or 1
        count[d] = count.get(d, 0) + 1
    for d in range(1, days + 1):
        if count.get(d, 0) < per:
            return d, count.get(d, 0)
    return None, None


def _open_schedule_request_dialog(request, on_done):
    """NDR pipeline Phase 4 — an inbound analyst request IS a confirmation, so it goes straight into
    an NDR's schedule at the next open slot (flagged source='inbound'), and the request is resolved.
    Inbound and outbound converge into one Active NDR instead of two tabs."""
    trips = _load_json("ndr_trips.json", [])
    open_trips = [(i, t) for i, t in enumerate(trips) if t.get("status") != "Completed"]

    def _match(t):
        tc = (t.get("city") or "").lower()
        rm, rc = (request.get("metro") or "").lower(), (request.get("city") or "").lower()
        return bool(tc) and (rm and (rm in tc or tc in rm) or rc and (rc in tc or tc in rc))

    opts = {str(i): (("★ " if _match(t) else "") + (t.get("name") or f"NDR {i+1}")) for i, t in open_trips}
    opts["__new__"] = "＋ New NDR…"
    default = next((str(i) for i, t in open_trips if _match(t)),
                   (str(open_trips[0][0]) if open_trips else "__new__"))
    with ui.dialog() as dlg, ui.card().style(f"background:{COLORS['surface_bg']};min-width:min(520px,94vw);"):
        ui.label(f"Schedule request — {request.get('analyst', '')} ({request.get('firm', '')}) → {request.get('city', '')}").classes("text-lg font-bold")
        ui.label("An inbound request is a confirmed meeting — it drops straight into the schedule at the "
                 "next open slot.").style(f"color:{COLORS['text_muted']};font-size:12px;")
        sel = ui.select(opts, value=default, label="Add to NDR").props("dense outlined").classes("w-full")
        new_name = ui.input("New NDR name", value=f"{request.get('city', '')} NDR").props("dense outlined").classes("w-full")
        new_name.bind_visibility_from(sel, "value", backward=lambda v: v == "__new__")
        with ui.row().classes("w-full justify-end gap-2").style("margin-top:6px;"):
            ui.button("Cancel", on_click=dlg.close).props("flat")

            def _go():
                trips2 = _load_json("ndr_trips.json", [])
                if sel.value == "__new__":
                    nm = (new_name.value or "").strip()
                    if not nm:
                        ui.notify("Name the new NDR.", type="warning"); return
                    trips2.append({
                        "name": nm, "sponsor_bank": request.get("firm", ""), "dates": "TBD",
                        "ndr_type": "in-person", "city": request.get("city", ""), "focus": "", "team": [],
                        "notes": "", "meetings": [], "shortlist": [], "status": "Planning", "debrief": {},
                        "days": 2, "slots_per_day": 6, "created": datetime.now().strftime("%Y-%m-%d"),
                    })
                    trip, tname = trips2[-1], nm
                else:
                    trip = trips2[int(sel.value)]
                    tname = trip.get("name") or "NDR"
                day, slot = _next_open_slot(trip)
                if day is None:
                    ui.notify("That NDR's slots are full — raise its capacity or pick another.", type="warning"); return
                trip.setdefault("meetings", []).append({
                    "institution": request.get("firm", ""), "contact": request.get("analyst", ""),
                    "day": day, "slot_index": slot, "time": _slot_time(slot), "type": "1x1",
                    "format": "In-person", "status": "scheduled", "notes": request.get("reason", ""),
                    "non_holder": True, "score": None, "source": "inbound",
                    "inbound_request_id": request.get("id"),
                    "confirmed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                _save_json("ndr_trips.json", trips2)
                reqs = _load_ndr_requests()
                for rr in reqs:
                    if rr.get("id") == request.get("id"):
                        rr["resolved"] = True
                        rr["resolved_at"] = datetime.now().strftime("%b %d, %Y")
                        rr["scheduled_into"] = tname
                _save_ndr_requests(reqs)
                try:
                    from core import activity_log
                    activity_log.log_event("ndr_inbound_scheduled", entity=request.get("firm", ""),
                                           launched_from=f"NDR · {tname}")
                except Exception:
                    pass
                dlg.close()
                ui.notify(f"Scheduled {request.get('analyst', '')} → Day {day} · {_slot_time(slot)}. Request resolved.",
                          type="positive")
                on_done()
            ui.button("Schedule into NDR", icon="event_available", on_click=_go).props("color=primary")
    dlg.open()


def _sec_holder_record(name, source, holder, peer_of=None, city=None, state=None):
    """A full institution record for a real SEC-sourced name, with honest
    'unknown' defaults for every enrichment field the scorer and cards read —
    so a 13F/13D-G/peer-overlap holder lives in the same universe as the seed
    without breaking scoring. It simply scores low until it's enriched.
    city/state (from the 13F filing address) drive the Metro breakdown."""
    action = {
        "SEC 13F": "Confirmed 13F holder — enrich & prioritize",
        "Peer 13F": "Holds a peer — real NDR prospect",
        "SEC 13D/G": "Filed a 5%+ stake — engage directly",
    }.get(source, "SEC-sourced name")
    return {
        "Fund": name, "Type": "Institutional (SEC)", "AUM": "—", "Coverage_Priority": 3,
        "USIO_Holder": holder, "Shares": 0, "QoQ_Change": 0, "Call_Listener": False,
        "Listen_Duration": "—", "Peer_Holdings": ([peer_of] if peer_of else []),
        "IR_Visits_30d": 0, "Last_Visit": "—", "Conviction": "—",
        "Call_Score": 0, "Peer_Score": 0, "Visit_Score": 0,
        "Turnover_Style": "Unknown (SEC)", "Metro": _metro_from_city(city, state), "Ownership_Style": "Active",
        "Action": action, "Source": source,
    }


def _sec_universe_records(client_id):
    """Build source-tagged institution records from CACHED SEC data (no live
    calls at render): USIO 13F holders, 13D/13G filers, and funds holding the
    peer set (real NDR prospects). Deduped by filer name."""
    recs = {}
    ticker = CT("ticker")
    for h in (sec_filings.get_cached_13f_holders(ticker).get("holders", []) or []):
        name = (h.get("filer") or "").strip()
        if not name:
            continue
        r = recs.setdefault(name, _sec_holder_record(
            name, "SEC 13F", True, city=h.get("city"), state=h.get("state")))
        # Real, exact position size from the bulk 13F dataset (size_known).
        if h.get("size_known") and h.get("shares"):
            r["Shares"] = h["shares"]
        # Backfill metro if this record was first created from a 13D/G (no city).
        if r.get("Metro") == "Unknown (SEC)" and h.get("city"):
            r["Metro"] = _metro_from_city(h.get("city"), h.get("state"))
    for f in (sec_filings.get_cached_13d_13g(ticker, refresh_if_stale=False).get("filings", []) or []):
        name = (f.get("filer") or f.get("name") or "").strip()
        if not name:
            continue
        if name in recs:
            recs[name]["Source"] = "SEC 13F + 13D/G"
            recs[name]["Action"] = "Holder with a 5%+ filing — engage directly"
        else:
            recs[name] = _sec_holder_record(name, "SEC 13D/G", True)
    # Peer-overlap prospects are NO LONGER auto-injected here. Dumping every
    # comp's top holders into the universe filled it with index/passive noise and
    # false positives (funds that already own USIO sub-13F-threshold). They now go
    # through a reviewed, conviction-ranked queue (core.peer_prospects, the "Peer
    # Prospects" tab) and only enter the pipeline when the IR lead promotes one —
    # at which point it lands in prospects.json like any other manual prospect.
    for r in recs.values():
        r.pop("_peer_tier", None)  # internal ranking key — not part of the record
    return list(recs.values())


def _promoted_prospect_records(client_id):
    """Promoted non-holders. Delegates to core.targets.promoted_prospects — the report generators
    need the same list, and a second copy here would drift."""
    from core import targets as targets_mod
    return targets_mod.promoted_prospects(client_id)


def _score_val(inst, key="Engagement_Score"):
    """A score for COMPARISON / sorting only.

    Scores are None when nothing was measurable — there is no website-analytics or call-listener
    integration, so Digital_Intent_Score is None for every real 13F institution and
    Engagement_Score is None when no pillar has an input. None can't be compared to an int, and
    that TypeError takes the entire page down (see tests/smoke_render.py).

    Treated as 0 for filtering/tiering, while the UI still DISPLAYS "—" for None — so an absent
    measurement is never rendered as a confident zero.
    """
    v = inst.get(key)
    return 0 if v is None else v


def _merge_sec_universe(seed_institutions, client_id):
    """Append real SEC-sourced names to the seed universe. A name that already
    matches a seed fund (normalized) doesn't duplicate — the seed record wins
    and is marked 'Seed + SEC-confirmed' so the demo shows it's validated by a
    real filing."""
    by_norm = {}
    for i in seed_institutions:
        by_norm.setdefault(_norm_name(i["Fund"]), i)
    for rec in _sec_universe_records(client_id):
        key = _norm_name(rec["Fund"])
        if key in by_norm:
            s = by_norm[key]
            if "SEC" not in s.get("Source", ""):
                s["Source"] = "Seed + SEC-confirmed"
            continue
        seed_institutions.append(rec)
    return seed_institutions


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
    # REAL 13F holders are the target universe (core/targets.py) — position size, % of the
    # holder's own book, add/trim/new direction, and the contact behind the filing. This replaced
    # data/seed/buyside_institutions.py, whose 62 records carried fabricated conviction and
    # engagement scores; showing a client an invented "Conviction: High" next to a real filing is
    # exactly the credibility risk this platform exists to avoid.
    from core import targets as targets_mod
    raw_institutions = targets_mod.targets_as_institutions(client_id=client_id)
    # Merge real SEC-sourced names (13D/G filers, peer-overlap prospects) from cached EDGAR data —
    # each carries its own Source tag, and this is what the "Refresh from SEC EDGAR" button on the
    # SEC Intelligence tab grows. Reads cache only here (no live network call at page render).
    raw_institutions = _merge_sec_universe(raw_institutions, client_id)
    # Promoted non-holders from the Peer Prospects queue. Without this the universe is holders-only
    # — a target database with no targets to win.
    _existing = {_norm_name(i["Fund"]) for i in raw_institutions}
    raw_institutions += [p for p in _promoted_prospect_records(client_id)
                         if _norm_name(p["Fund"]) not in _existing]
    # Upgrades Peer_Holdings from static seed data to real SEC 13F filings
    # wherever a ticker has actually been refreshed (see
    # _enrich_peer_holdings_with_live_13f's docstring) — must run BEFORE
    # scoring, since post-earnings mode's Catalyst Fit pillar reads
    # Peer_Holdings too, not just Peer Cross-Targeting below.
    _enrich_peer_holdings_with_live_13f(raw_institutions, [p["ticker"] for p in _load_peer_universe()])
    institutions = _score_institutions(raw_institutions, mode, q2_listeners, meeting_log)

    ui.label(f"{CT('name')} — Investor Pipeline & Engagement").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")

    # Mode-dependent sections re-render in place when the Pre/Post toggle
    # changes — no full page reload (which was fragile on a reconnecting tab
    # and reset the whole page). Only the parts that actually depend on mode
    # refresh: Big Picture, the mode description, and the Buy-Side tab (the
    # other four tabs don't use mode).
    _mode_ctx = {"mode": mode, "institutions": institutions}

    @ui.refreshable
    def _big_picture_section():
        _render_big_picture(_mode_ctx["institutions"])

    @ui.refreshable
    def _mode_desc_section():
        _render_mode_description(_mode_ctx["mode"])

    @ui.refreshable
    def _buyside_section():
        _render_buyside_tab(_mode_ctx["institutions"], meeting_log, _mode_ctx["mode"])

    def on_mode_change(new_mode):
        _mode_ctx["mode"] = new_mode
        _mode_ctx["institutions"] = _score_institutions(raw_institutions, new_mode, q2_listeners, meeting_log)
        mode_state["mode"] = new_mode
        _save_json("buyside_mode.json", mode_state)
        _big_picture_section.refresh()
        _mode_desc_section.refresh()
        _buyside_section.refresh()
        _invalidate_mode_tabs()

    _big_picture_section()
    ui.markdown("---")
    _render_mode_toggle_control(_mode_ctx["mode"], on_mode_change)
    _mode_desc_section()
    ui.markdown("---")

    with ui.tabs().classes("w-full") as tabs:
        t1 = ui.tab("Buy-Side Intelligence")
        t2 = ui.tab("NDR Planner")
        t3 = ui.tab("Meeting Hub")
        t4 = ui.tab("Target Database")
        t5 = ui.tab("SEC Intelligence")
        t6 = ui.tab("NOBO Ownership")
        t7 = ui.tab("Peer Prospects")

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
    # A sidebar sub-item can deep-link straight to any tab; map the label back to
    # its tab object so lazy loading opens (and eager-builds) the right one. All
    # tabs are lazy now — whichever we open on is built by the eager block below.
    _by_name = {t.props["name"]: t for t in (t1, t2, t3, t4, t5, t6, t7)}
    default_tab = _by_name.get(nav.consume_target_tab(), t1)
    with ui.tab_panels(tabs, value=default_tab).classes("w-full"):
        with ui.tab_panel(t1) as p1:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t2) as p2:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t3) as p3:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t4) as p4:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t5) as p5:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t6) as p6:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")
        with ui.tab_panel(t7) as p7:
            ui.spinner(size="lg").classes("mx-auto").style("margin-top:32px;")

    # NDR Planner and Target Database read the mode-scored institutions, so
    # they pull from _mode_ctx (current mode) rather than capturing the initial
    # list — a tab built after a mode toggle uses the fresh scores.
    lazy_panels = {
        t1.props["name"]: (p1, lambda: _buyside_section()),
        t2.props["name"]: (p2, lambda: _render_ndr_tab(_mode_ctx["institutions"], meeting_log, client_id)),
        t3.props["name"]: (p3, lambda: _render_meeting_hub_tab()),
        t4.props["name"]: (p4, lambda: _render_target_db_tab(_mode_ctx["institutions"], client_id)),
        t5.props["name"]: (p5, lambda: _render_sec_intelligence_tab()),
        # NOBO Ownership relocated here from Market Intelligence — its render
        # (with the Broadridge upload) is the shared one in markets_page, called
        # cross-module the same way Earnings calls _render_narrative_momentum.
        t6.props["name"]: (p6, lambda: _render_nobo_tab()),
        t7.props["name"]: (p7, lambda: _render_peer_prospects_tab(client_id)),
    }
    loaded_tabs = set()
    # A mode toggle also invalidates the two mode-dependent lazy tabs so they
    # rebuild with fresh scores next time they're opened (harmless no-op if
    # they haven't been built yet).
    _mode_dependent_tabs = (t2.props["name"], t4.props["name"])
    _invalidate_mode_tabs = lambda: [loaded_tabs.discard(n) for n in _mode_dependent_tabs]

    async def _load_tab_on_demand(e):
        name = e.value
        # Keep the sidebar's sub-item highlight in sync with in-page tab clicks.
        # Guard it: on a STALE client (e.g. after a server restart while the
        # page stayed open) render_nav() raises "client has been deleted".
        # That must not abort the tab build below and strand the panel on its
        # spinner forever.
        try:
            nav.tab_changed(name)
        except Exception:
            pass
        if name not in lazy_panels or name in loaded_tabs:
            return
        container, build_fn = lazy_panels[name]
        # Yield to the event loop once so the spinner that's already in
        # `container` actually reaches the browser before this function
        # goes on to do the (synchronous) database reads that tab needs —
        # without this await, the spinner and the real content would both
        # get flushed to the browser in the same batch, i.e. no visible
        # "loading" feedback at all, just a delay.
        await asyncio.sleep(0)
        try:
            container.clear()
            with container:
                build_fn()
        except Exception as ex:
            # Never leave the tab stuck on its spinner. Replace it with an
            # actionable error and — critically — do NOT mark the tab loaded,
            # so re-selecting it retries the build.
            try:
                container.clear()
                with container:
                    ui.label("This tab didn't finish loading.").style(
                        f"color:{COLORS['text_heading']};font-weight:600;")
                    ui.label(str(ex)).style(f"color:{COLORS['text_muted']};font-size:12px;")
                    ui.label("If this persists, reload the page (Ctrl-R) — the server may "
                             "have restarted.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    ui.button("Reload page", on_click=lambda: ui.navigate.reload()).props("outline dense")
            except Exception:
                pass  # client is truly gone; only a browser refresh can recover
            return
        # Success — now it's safe to remember it's built.
        loaded_tabs.add(name)

    tabs.on_value_change(_load_tab_on_demand)

    # Eager-build whichever tab we open on (deep-linked or the default t1) — its
    # panel currently shows only a spinner and _load_tab_on_demand fires on
    # change, not initial load.
    _dname = default_tab.props["name"]
    loaded_tabs.add(_dname)
    _dcont, _dbuild = lazy_panels[_dname]
    _dcont.clear()
    with _dcont:
        _dbuild()


def _render_nobo_tab():
    """NOBO Ownership tab — relocated here from Market Intelligence, where it sat
    among market-data views; it belongs with the investor base. The renderer
    (CEO's-read BLUF, composition/concentration, two-pull flow, 13D/13G threshold
    watch, pipeline cross-reference, and the Broadridge NOBO-file upload) stays in
    markets_page as the single home for the nobo_engine surface; imported lazily
    to keep module load order simple."""
    from page_modules_nicegui.markets_page import _render_nobo
    _render_nobo()


def _render_curated_targets(client_id):
    """Hand-curated NDR targets — accounts you KNOW are a fit but that the 13F
    peer-holder crawl can't surface because they don't hold a comp today (a
    Geneva/Lugano private bank, a relationship carried from a prior seat). Two
    scopes: this client's own book, and a shared global book that accretes as we
    onboard more issuers. Shown in the metro view above tagged 'Curated'."""
    from core import curated_targets, peer_prospects

    ui.label("Curated targets — known accounts the crawl can't find").classes(
        "text-md font-bold").style(f"color:{COLORS['text_heading']};margin-top:6px;")
    ui.label("A peer-holder crawl only finds funds that already own a comp. Accounts you know are a fit but "
             "that don't hold a peer today — a Geneva/Lugano private bank, a relationship from a prior seat — "
             "go here by hand and appear in the metro view above, tagged 'Curated' (never 'holds a comp'). "
             "Client scope is this issuer's own book; Global is the house book, shared across every client and "
             "growing as we scale.").style(f"color:{COLORS['text_muted']};font-size:11px;")

    @ui.refreshable
    def _panel():
        cc = curated_targets.counts(client_id)
        with ui.row().classes("gap-3").style("margin-top:6px;"):
            for lbl, val, clr in [("This client", cc["client"], COLORS["accent"]),
                                  ("Global (house book)", cc["global"], "#6D28D9"),
                                  ("Total in view", cc["total"], COLORS["text_secondary"])]:
                with ui.card().classes("flex-1").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};min-width:110px;"):
                    ui.label(str(val)).classes("font-bold").style(f"color:{clr};font-size:20px;")
                    ui.label(lbl).style(f"color:{COLORS['text_muted']};font-size:11px;")

        # ── Add form ──────────────────────────────────────────────────────────
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};margin-top:6px;"):
            ui.label("Add a curated target").classes("font-bold").style(
                f"color:{COLORS['text_heading']};font-size:13px;")
            with ui.row().classes("w-full gap-2 items-end no-wrap").style("flex-wrap:wrap;"):
                f_name = ui.input("Firm name").props("dense outlined").style("min-width:220px;flex:2;")
                f_city = ui.input("City").props("dense outlined").style("min-width:120px;flex:1;")
                f_state = ui.input("State / country", placeholder="NY · Switzerland").props(
                    "dense outlined").style("min-width:130px;flex:1;")
            f_why = ui.input("Why (rationale)").props("dense outlined").classes("w-full").style("margin-top:4px;")
            with ui.row().classes("items-center gap-3").style("margin-top:4px;"):
                f_scope = ui.toggle({"client": "This client", "global": "Global (house book)"},
                                    value="client").props("dense no-caps")
                # Live metro preview, so you see where it will cluster before saving.
                _preview = ui.label("").style(f"color:{COLORS['text_muted']};font-size:11px;")

                def _refresh_preview():
                    c, s = (f_city.value or "").strip(), (f_state.value or "").strip()
                    _preview.set_text(f"→ clusters into: {_metro_from_city(c, s)}" if c else "")
                f_city.on("blur", lambda *_: _refresh_preview())
                f_state.on("blur", lambda *_: _refresh_preview())

                def _add():
                    if not (f_name.value or "").strip():
                        ui.notify("Firm name is required.", type="warning")
                        return
                    curated_targets.add(f_name.value, f_city.value, f_state.value,
                                        f_why.value, scope=f_scope.value, cid=client_id)
                    ui.notify(f"Added {f_name.value.strip()} to the "
                              f"{'global house book' if f_scope.value == 'global' else 'client'} list.",
                              type="positive")
                    _panel.refresh()
                ui.button("Add target", icon="add", on_click=_add).props("dense color=primary")

        # ── Current list ──────────────────────────────────────────────────────
        entries = curated_targets.merged(client_id)
        if not entries:
            return
        for r in sorted(entries, key=lambda x: (x.get("scope") != "client", x.get("filer", "").lower())):
            is_client = r.get("scope") == "client"
            badge_clr = COLORS["accent"] if is_client else "#6D28D9"
            metro = _metro_from_city(r.get("city"), r.get("state"))
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                    f"border-left:4px solid {badge_clr};margin-top:4px;"):
                with ui.column().classes("gap-0").style("min-width:0;"):
                    with ui.row().classes("items-center gap-2"):
                        ui.label(r.get("filer")).classes("font-bold").style(
                            f"color:{COLORS['text_heading']};font-size:13px;")
                        ui.label("This client" if is_client else "Global").style(
                            f"background:{'rgba(30,64,175,.10)' if is_client else 'rgba(109,40,217,.10)'};"
                            f"color:{badge_clr};border-radius:6px;padding:1px 7px;font-size:10px;font-weight:700;")
                        if r.get("seed"):
                            ui.label("default").style(
                                f"color:{COLORS['text_muted']};font-size:10px;border:1px solid {COLORS['border']};"
                                "border-radius:6px;padding:0 6px;")
                    loc = _loc_line(r)
                    ui.label(f"{loc}  ·  metro: {metro}").style(
                        f"color:{COLORS['text_muted']};font-size:11px;")
                    if r.get("rationale"):
                        ui.label(r["rationale"]).style(f"color:{COLORS['text_secondary']};font-size:11px;")
                # Actions in a bottom row set off by a thin divider — consistent with the
                # peer-prospect, institution, and Today dashboard cards.
                with ui.row().classes("w-full gap-1 items-center").style(
                        f"margin-top:4px;padding-top:4px;border-top:1px solid {COLORS['border']};"):
                    ui.button("Add to pipeline", on_click=lambda r=r: (
                        peer_prospects.promote(r, cid=client_id),
                        ui.notify(f"Added {r['filer']} to the pipeline (Target Database).", type="positive"),
                    )).props("dense size=sm color=primary")
                    if not r.get("seed"):
                        ui.button(icon="delete", on_click=lambda r=r: (
                            curated_targets.remove(r["key"], scope=r.get("scope", "client"), cid=client_id),
                            _panel.refresh(),
                        )).props("flat dense size=sm color=negative")

    _panel()


def _render_peer_prospects_tab(client_id):
    """Reviewed, conviction-ranked peer-overlap candidates (core.peer_prospects).
    Funds that hold a close comp but not the client, filtered for noise and false
    positives, each with its evidence and a promote/dismiss gate — nothing enters
    the pipeline unvetted."""
    from core import peer_prospects

    # Ticker and comp names come from THIS client. They were hardcoded to USIO's, so
    # every other tenant read "…but not USIO (Repay / Cass / CSG…)" on their own page.
    _tk = CT("ticker")
    _tight = sorted(peer_prospects.tight_comps(client_id))
    _comps = " / ".join(_tight[:5]) if _tight else "its closest comps"
    ui.label("Peer Prospects — comp overlap, to qualify").classes("text-lg font-bold")
    ui.label(f"Funds that hold a close comp ({_comps}) but not {_tk}, "
             "ranked by conviction — position weight in their own book, focus on the tightest comps, active "
             "vs. index breadth, and size fit. Anyone already yours (13F / NOBO / tracked / 13D-G), plus "
             "passive/index and quasi-index books, is filtered out. Nothing hits the pipeline until you promote it.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    # The roadshow-metro view (with click-to-select) is now the single "Where they are" table in
    # Buy-Side Intelligence — no duplicate here. The conviction-ranked prospects below feed the
    # same NDR pipeline.
    ui.label("📍 Roadshow metro view — with click-a-metro → select → Add to NDR — now lives in "
             "Buy-Side Intelligence → “Where they are”. The conviction-ranked prospects below feed the "
             "same pipeline.").style(
        f"color:{COLORS['text_muted']};font-size:12px;background:{COLORS['surface_hover_bg']};"
        "border-radius:8px;padding:8px 10px;")
    ui.markdown("---")
    _render_curated_targets(client_id)
    ui.markdown("---")

    # Sort toggle — conviction (the smart default) vs raw 13F position size (what
    # a plain 13F screen shows) vs concentration. Lives outside the refreshable so
    # flipping it just re-ranks the list.
    _state = {"sort": "conviction", "show_all": False}
    with ui.row().classes("items-center gap-2").style("margin-top:6px;"):
        ui.label("Rank by").style(f"color:{COLORS['text_muted']};font-size:12px;")
        _sort_toggle = ui.toggle(
            {"conviction": "Conviction", "size": "Position size", "concentration": "Concentration"},
            value="conviction").props("dense no-caps")

    @ui.refreshable
    def _list():
        # Show ALL qualified peer-owners by default is heavy (222 cards), so start at 40 with a
        # one-click "show all" — but never a silent cap: the count card says how many exist and the
        # control lists every one (same principle as the RIA/diversified buckets below).
        _lim = None if _state.get("show_all") else 40
        cands = peer_prospects.build_candidates(client_id, limit=_lim, sort=_state["sort"])
        c = peer_prospects.counts(client_id)
        with ui.row().classes("w-full gap-3").style("margin-top:6px;"):
            for lbl, val, clr in [("To qualify", c["candidates"], COLORS["accent"]),
                                  ("RIA / wealth", c.get("rias", 0), "#B45309"),
                                  ("Diversified", c.get("diversified", 0), "#6D28D9"),
                                  ("Promoted", c["promoted"], "#15803D"),
                                  ("Dismissed", c["dismissed"], COLORS["text_muted"])]:
                with ui.card().classes("flex-1").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};min-width:110px;"):
                    ui.label(str(val)).classes("font-bold").style(f"color:{clr};font-size:20px;")
                    ui.label(lbl).style(f"color:{COLORS['text_muted']};font-size:11px;")

        if not cands:
            ui.label("No candidates to qualify. Run the SEC 13F refresh on the SEC Intelligence tab if you "
                     "haven't yet, or you've reviewed them all.").style(
                f"color:{COLORS['text_muted']};font-size:12px;margin-top:8px;")
            return

        for r in cands:
            promoted = r.get("promoted")
            border = "#15803D" if promoted else COLORS["border"]
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {border};"
                    f"border-left:4px solid {'#15803D' if promoted else COLORS['accent']};margin-top:4px;"):
                with ui.row().classes("w-full items-start justify-between no-wrap"):
                    with ui.column().classes("gap-0").style("flex:1;min-width:0;"):
                        _nm = pretty_name(r["filer"]) + ("  ✓ promoted" if promoted else "")
                        ui.label(_nm).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                        loc = _loc_line(r)
                        conc = f"{r['concentration']*100:.1f}% of book" if r.get("concentration") is not None else "book n/a"
                        bp = f"{r['book_positions']} positions" if r.get("book_positions") else "breadth n/a"
                        pv = f"${r['peer_value']/1e6:.1f}M position" if r.get("peer_value") else ""
                        ui.label(f"{loc} · {conc} in payment comps{(' · ' + pv) if pv else ''} · {bp} · "
                                 f"filed {(r.get('file_date') or '—')}").style(
                            f"color:{COLORS['text_muted']};font-size:11px;")
                        with ui.row().classes("gap-1 flex-wrap").style("margin-top:3px;"):
                            for ct, cv in sorted(r["comps"].items(), key=lambda kv: -kv[1]["value"]):
                                tight = cv["tight"]
                                ui.label(ct + (" ◆" if tight else "")).style(
                                    f"background:{'rgba(30,64,175,.10)' if tight else COLORS['surface_hover_bg']};"
                                    f"color:{COLORS['accent_strong'] if tight else COLORS['text_secondary']};"
                                    "border-radius:6px;padding:1px 7px;font-size:11px;font-weight:600;")
                    with ui.column().classes("gap-0 items-end").style("flex-shrink:0;"):
                        ui.label(f"{r['conviction']:.0f}").classes("font-bold").style(
                            f"color:{COLORS['accent']};font-size:20px;line-height:1;")
                        ui.label("conviction").style(f"color:{COLORS['text_muted']};font-size:10px;")
                # Actions in a bottom row set off by a thin divider — same treatment as the
                # Today dashboard and institution cards.
                with ui.row().classes("w-full gap-1 items-center").style(
                        f"margin-top:4px;padding-top:4px;border-top:1px solid {COLORS['border']};"):
                    if promoted:
                        ui.button("Undo", on_click=lambda r=r: (peer_prospects.reset(r["key"]), _list.refresh())).props(
                            "flat dense size=sm")
                    else:
                        def _promote(r=r):
                            peer_prospects.promote(r)
                            ui.notify(f"Promoted {r['filer']} to the pipeline (Target Database).", type="positive")
                            _list.refresh()

                        def _dismiss(r=r):
                            peer_prospects.dismiss(r["key"])
                            _list.refresh()

                        ui.button("Promote", on_click=_promote).props("dense size=sm color=primary")
                        ui.button("Dismiss", on_click=_dismiss).props("flat dense size=sm")

        # Show-all control — every qualified peer-owner is listable, not just the top 40.
        _total = c["candidates"]
        if _total > len(cands) and not _state.get("show_all"):
            def _showall():
                _state["show_all"] = True
                _list.refresh()
            ui.button(f"Show all {_total} funds that own a peer but not {CT('ticker')}",
                      icon="expand_more", on_click=_showall).props("flat dense").style("margin-top:8px;")
        elif _state.get("show_all"):
            ui.label(f"Showing all {len(cands)} qualified peer-owners (funds holding a comp, not USIO).").style(
                f"color:{COLORS['text_muted']};font-size:11px;margin-top:8px;")

            def _showtop():
                _state["show_all"] = False
                _list.refresh()
            ui.button("Show top 40 only", icon="expand_less", on_click=_showtop).props("flat dense")

        # ── RIA / wealth bucket ─────────────────────────────────────────────
        # These genuinely own the comps but have no PM to pitch, so they're a
        # video-call tier rather than an NDR target. Previously discarded
        # outright; now surfaced separately, ranked by position size.
        # No limit: the header count must match the "RIA / wealth" card above, and
        # a capped list would silently hide names the card says exist.
        _rias = peer_prospects.build_candidates(client_id, limit=None, kind="ria")
        if _rias:
            with ui.expansion(f"RIA / wealth managers holding your comps ({len(_rias)})",
                              icon="account_balance_wallet", value=False).classes("w-full").style(
                    f"border:1px solid {COLORS['border']};border-radius:8px;margin-top:12px;"):
                ui.label("Real positions in your peer set, but held through client accounts — no portfolio "
                         "manager to pitch. Video-call tier: an assistant can set these up, no management "
                         "travel. Ranked by position size; a large one can still be worth a call.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;")
                for r in _rias:
                    with ui.row().classes("w-full items-center justify-between no-wrap").style(
                            f"border-bottom:1px solid {COLORS['border']};padding:5px 0;"):
                        with ui.column().classes("gap-0").style("flex:1;min-width:0;"):
                            ui.label(pretty_name(r["filer"])).style(
                                f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
                            loc = _loc_line(r)
                            comps = ", ".join(sorted(r["comps"].keys()))
                            ui.label(f"{loc} · ${r['peer_value']/1e6:.1f}M across {comps}").style(
                                f"color:{COLORS['text_muted']};font-size:11px;")
                        with ui.row().classes("gap-1").style("flex-shrink:0;"):
                            if r.get("promoted"):
                                ui.button("Undo", on_click=lambda r=r: (
                                    peer_prospects.reset(r["key"]), _list.refresh())).props("flat dense size=sm")
                            else:
                                def _promote_ria(r=r):
                                    peer_prospects.promote(r)
                                    ui.notify(f"Promoted {r['filer']} — video-call tier.", type="positive")
                                    _list.refresh()

                                def _dismiss_ria(r=r):
                                    peer_prospects.dismiss(r["key"])
                                    _list.refresh()

                                ui.button("Promote", on_click=_promote_ria).props("flat dense size=sm color=primary")
                                ui.button("Dismiss", on_click=_dismiss_ria).props("flat dense size=sm")

        # ── Large diversified / index-family managers ───────────────────────
        # These were DROPPED outright on the assumption that a big book "never takes a micro-cap
        # NDR". That's a bad assumption: they may not chase a meeting, but if you're already in
        # their city and they own you or a comp they'll usually take one — and their analysts often
        # WANT to meet a competitor they DON'T own, for candid industry colour. So they're a review
        # bucket now, ranked by how much of the peer set they actually own.
        _div = peer_prospects.build_candidates(client_id, limit=None, kind="diversified")
        if _div:
            with ui.expansion(f"Large diversified & index-family managers ({len(_div)})",
                              icon="corporate_fare", value=False).classes("w-full").style(
                    f"border:1px solid {COLORS['border']};border-radius:8px;margin-top:12px;"):
                ui.label("Index families, bank asset-management arms, and wide-book active managers "
                         "(Capital Group, Fidelity, Clearbridge…). They run real fundamental strategies. "
                         "Worth a meeting when you're already in their city, when they own a comp, or "
                         "when they want industry colour on a name they don't own. Ranked by peer position.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;")
                for r in _div:
                    with ui.row().classes("w-full items-center justify-between no-wrap").style(
                            f"border-bottom:1px solid {COLORS['border']};padding:5px 0;"):
                        with ui.column().classes("gap-0").style("flex:1;min-width:0;"):
                            ui.label(pretty_name(r["filer"])).style(
                                f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
                            loc = _loc_line(r)
                            comps = ", ".join(sorted(r["comps"].keys()))
                            why = "wide book" if r.get("broad_book") else "index / bank AM"
                            ui.label(f"{loc} · ${r['peer_value']/1e6:.1f}M across {comps} · {why}").style(
                                f"color:{COLORS['text_muted']};font-size:11px;")
                        with ui.row().classes("gap-1").style("flex-shrink:0;"):
                            if r.get("promoted"):
                                ui.button("Undo", on_click=lambda r=r: (
                                    peer_prospects.reset(r["key"]), _list.refresh())).props("flat dense size=sm")
                            else:
                                def _promote_div(r=r):
                                    peer_prospects.promote(r)
                                    ui.notify(f"Promoted {r['filer']} for review.", type="positive")
                                    _list.refresh()

                                def _dismiss_div(r=r):
                                    peer_prospects.dismiss(r["key"])
                                    _list.refresh()

                                ui.button("Promote", on_click=_promote_div).props("flat dense size=sm color=primary")
                                ui.button("Dismiss", on_click=_dismiss_div).props("flat dense size=sm")

        # ── Market makers / HFT / ETF mechanics ─────────────────────────────
        # Genuinely no fundamental PM to meet — they hold the comps as inventory or index
        # mechanics. Shown for completeness/transparency (so a holder isn't silently missing from
        # the count), but read-only: there's no promote, because there's nobody to put on an NDR.
        _mm = peer_prospects.build_candidates(client_id, limit=None, kind="market_maker")
        if _mm:
            with ui.expansion(f"Market makers / HFT / ETF mechanics ({len(_mm)}) — no PM to meet",
                              icon="bolt", value=False).classes("w-full").style(
                    f"border:1px solid {COLORS['border']};border-radius:8px;margin-top:12px;"):
                ui.label("These hold your comps as trading inventory or index mechanics, not a "
                         "fundamental view — there is no portfolio manager to pitch. Listed for a "
                         "complete picture of who owns the peer set; not an NDR queue.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;")
                for r in sorted(_mm, key=lambda x: -(x.get("peer_value") or 0)):
                    loc = _loc_line(r)
                    comps = ", ".join(sorted(r["comps"].keys()))
                    ui.label(f"{r['filer']} · {loc} · ${(r.get('peer_value') or 0)/1e6:.1f}M across {comps}").style(
                        f"color:{COLORS['text_muted']};font-size:11px;border-bottom:1px solid {COLORS['border']};"
                        "padding:4px 0;")

    _sort_toggle.on_value_change(lambda e: (_state.update(sort=e.value), _list.refresh()))
    _list()


def _render_mode_toggle_control(mode, on_change_cb):
    """Just the Pre/Post toggle buttons. Stays put when the mode changes (it's
    not inside the refreshed region), so it keeps focus and doesn't flicker;
    the change is applied in place by on_change_cb rather than a page reload."""
    with ui.row().classes("w-full items-center gap-4"):
        toggle = ui.toggle({"pre": "Pre-Earnings — Engagement Mode", "post": "Post-Earnings — Prospecting Mode"}, value=mode)
        toggle.on_value_change(lambda: on_change_cb(toggle.value))


def _render_mode_description(mode):
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
def _open_account_profile(rec):
    """Account 360 — one card fusing the AUTO-derived book (holdings, peers, fund
    lineup, NDR pipeline) with the HUMAN relationship layer (quality, last contact,
    notes). `rec` is the original candidate/institution dict from wherever it was
    clicked. Prototype: read-rich, with an editable relationship strip that persists
    to the global house book (core.relationship_notes)."""
    from core import fund_lineup, account_api

    name = rec.get("filer") or rec.get("Fund") or "—"
    disp = pretty_name(name)
    is_cand = "filer" in rec
    comps = rec.get("comps") or {}
    peers = ", ".join(sorted(comps.keys()))
    metro = rec.get("Metro") or _metro_from_city(rec.get("city"), rec.get("state")) if is_cand else rec.get("Metro")
    loc = (rec.get("city") or rec.get("City") or metro or "—")
    category = rec.get("tier") or ("Current holder" if rec.get("USIO_Holder") else "Non-holder")
    score = rec.get("conviction") if is_cand else rec.get("Engagement_Score")

    def _section(title):
        ui.label(title).style(f"color:{COLORS['text_muted']};font-size:11px;font-weight:600;"
                              "letter-spacing:.04em;text-transform:uppercase;margin-top:10px;")

    def _kv(label, value):
        with ui.row().classes("w-full items-baseline gap-2").style("padding:1px 0;"):
            ui.label(label).style(f"color:{COLORS['text_muted']};font-size:12px;min-width:130px;")
            ui.label(str(value)).style(f"color:{COLORS['text_secondary']};font-size:12px;")

    acct_cik = rec.get("cik")
    acct = account_api.get_account(name=name, cik=acct_cik)   # one read: identity + both layers
    note = acct["relationship"]

    with ui.dialog() as dlg, ui.card().style("min-width:min(680px,95vw);max-width:95vw;"):
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-0"):
                ui.label(disp).classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};")
                ui.label(f"{category} · {loc}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            with ui.row().classes("items-center gap-2"):
                q = note.get("quality")
                if q:
                    ui.label(account_api.QUALITY.get(q, q)).style(
                        f"background:{COLORS['positive'] if q in ('good','responsive') else COLORS['surface_hover_bg']};"
                        f"color:{'#fff' if q in ('good','responsive') else COLORS['text_secondary']};"
                        "font-size:11px;font-weight:600;padding:2px 8px;border-radius:6px;")
                ui.button(icon="close", on_click=dlg.close).props("flat round dense")

        # ── Ownership & filings (auto) ─────────────────────────────
        _section("Ownership & filings")
        if is_cand:
            _kv("Owns (your comps)", peers or "—")
            _kv("Peer position value", f"${(rec.get('peer_value') or 0):,.0f}")
            _kv("Conviction", round(score) if isinstance(score, (int, float)) else "—")
            _kv("Book breadth", f"{rec.get('book_positions') or '—'} positions")
        else:
            _kv("Relationship to you", "Holder" if rec.get("USIO_Holder") else "Non-holder")
            if rec.get("Position_Value") is not None:
                _kv("Position value", f"${(rec.get('Position_Value') or 0):,.0f}")
            _kv("Engagement score", round(score) if isinstance(score, (int, float)) else "—")
            if peers:
                _kv("Owns (your comps)", peers)
            if rec.get("Action"):
                _kv("Signal", rec.get("Action"))

        # ── Fund lineup (auto) ─────────────────────────────────────
        lu = fund_lineup.lineup_for_manager(name)
        if lu and lu.get("funds"):
            _section(f"Fund lineup — {lu.get('registrant')}")
            names = [f["name"] for f in lu["funds"]]
            ui.label(" · ".join(names[:8]) + (f"  (+{len(names) - 8} more)" if len(names) > 8 else "")).style(
                f"color:{COLORS['text_secondary']};font-size:12px;")

        # ── Interactions (derived — touches & last contact are computed, not typed) ──
        _section("Interactions")

        @ui.refreshable
        def _interactions():
            summ = account_api.get_account(name=name, cik=acct_cik)["interactions"]
            with ui.row().classes("items-baseline gap-4"):
                ui.label(f"{summ['touches']} touch{'es' if summ['touches'] != 1 else ''}").style(
                    f"color:{COLORS['text_heading']};font-weight:700;font-size:13px;")
                ui.label(f"Last contact: {summ['last_contact'] or '—'}").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")
            for e in summ["events"][:6]:
                src = " · NDR" if e.get("source") == "ndr" else ""
                with ui.row().classes("w-full items-baseline gap-2").style("padding:1px 0;"):
                    ui.label(e.get("date") or "—").style(
                        f"color:{COLORS['text_muted']};font-size:11px;min-width:88px;")
                    ui.label(f"{account_api.TYPES.get(e.get('type'), e.get('type'))} — "
                             f"{e.get('summary') or ''}{src}").style(
                        f"color:{COLORS['text_secondary']};font-size:12px;")
            if not summ["events"]:
                ui.label("No interactions logged yet.").style(f"color:{COLORS['text_muted']};font-size:12px;")

        _interactions()
        # log an event → appends (never overwrites); touches/last-contact recompute
        with ui.row().classes("w-full items-end gap-2").style("margin-top:6px;"):
            it_type = ui.select({k: v for k, v in account_api.TYPES.items()}, value="meeting",
                                label="Type").props("dense outlined").style("min-width:120px;")
            it_date = ui.input("Date", value=datetime.now().strftime("%Y-%m-%d")).props("dense outlined").style("min-width:130px;")
            it_sum = ui.input("What happened").props("dense outlined").style("flex:1;min-width:150px;")

            def _log_it():
                account_api.log_interaction(name=name, cik=acct_cik, type=it_type.value,
                                            date=(it_date.value or "").strip() or None,
                                            summary=(it_sum.value or "").strip() or None)
                it_sum.value = ""
                ui.notify(f"Logged {account_api.TYPES.get(it_type.value, 'event').lower()} for {disp}.",
                          type="positive")
                _interactions.refresh()
            ui.button("Log", icon="add", on_click=_log_it).props("dense color=primary")

        # ── Relationship (human opinion — quality + free note; global to the firm) ──
        _section("Relationship — your notes")
        q_opts = {"": "— quality —", **account_api.QUALITY}
        q_sel = ui.select(q_opts, value=note.get("quality") or "", label="Quality").props(
            "dense outlined").style("min-width:200px;")
        note_box = ui.textarea(value=note.get("note") or "", label="Note").classes("w-full").props("rows=2")

        def _save_note():
            account_api.save_relationship(name=name, cik=acct_cik, quality=(q_sel.value or None),
                                          note=(note_box.value or "").strip() or None)
            ui.notify(f"Saved relationship note for {disp}.", type="positive")
            dlg.close()
        with ui.row().classes("w-full justify-end gap-2").style("margin-top:6px;"):
            ui.button("Save note", icon="save", on_click=_save_note).props("dense color=primary")
    dlg.open()


def _fund_lineup_label(manager_name, head=4):
    """Short inline lineup for a 13F manager: the individual fund names EDGAR shows
    for that family ('Value Fund · Value Plus · Mid Cap Value'), or "" if the manager
    doesn't resolve to a registered fund family. Cache-backed (see core.fund_lineup);
    unmapped managers return "" after a cheap no-network check, so it's safe to call
    per row. Never guesses — a name we can't confidently map shows nothing."""
    try:
        from core import fund_lineup
        if not fund_lineup.has_lineup(manager_name):
            return ""
        lu = fund_lineup.lineup_for_manager(manager_name)
        if not lu or not lu.get("funds"):
            return ""
        # Always DISPLAY the fund names we have — a reader who knows the family spots a
        # gap, and showing something beats a blank. State the true total from the
        # authoritative ticker-file count, and mark "partial" only when we genuinely
        # couldn't capture the whole roster (rare now that we aggregate across filings).
        names = [f["name"] for f in lu["funds"]]
        total = lu.get("expected_series") or len(names)
        total = max(total, len(names))
        label = " · ".join(names[:head])
        extra = total - min(len(names), head)
        if extra > 0:
            label += f"  (+{extra} more)"
        if not lu.get("complete"):
            label += " · partial"
        return label
    except Exception:
        return ""


def _open_lineup_crosswalk_dialog():
    """Human-in-the-loop review of the manager→fund-family crosswalk — the links that
    let the drill-down show a holder's individual funds. Confirm the ambiguous matches,
    reject any wrong auto-match; decisions survive a re-scan (they're never clobbered)."""
    from core import fund_lineup as fl
    dlg = ui.dialog()

    def _row(manager, norm):
        return pretty_name(manager or norm)

    @ui.refreshable
    def _body():
        entries = fl.crosswalk_entries()
        pend = [e for e in entries if not e.get("confirmed") and not e.get("rejected")]
        review = [e for e in pend if e.get("confidence") == "review"]
        high = [e for e in pend if e.get("confidence") == "high"]
        confirmed = [e for e in entries if e.get("confirmed")]
        rejected = [e for e in entries if e.get("rejected")]

        ui.label(f"Needs your confirmation ({len(review)})").classes("text-md font-bold").style(
            f"color:{COLORS['text_heading']};margin-top:4px;")
        if not review:
            ui.label("Nothing waiting — every ambiguous match is resolved.").style(
                f"color:{COLORS['text_muted']};font-size:12px;")
        for e in review:
            with ui.row().classes("w-full items-center gap-2").style(
                    f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                ui.label(_row(e.get("manager"), e["norm"])).style("min-width:210px;font-weight:600;")
                if e.get("note"):
                    ui.label(e["note"]).style(f"color:{COLORS['warning']};font-size:11px;max-width:200px;")
                cands = fl.candidate_names(e.get("ciks", []))
                opts = {str(c["cik"]): f"{pretty_name(c['name'])} (CIK {c['cik']})" for c in cands}
                opts["__none__"] = "No registered fund family"
                sel = ui.select(opts, value=next(iter(opts)), label="Correct fund family").props(
                    "dense outlined").style("min-width:300px;flex:1;")

                def _do(ev=None, norm=e["norm"], sel=sel):
                    if sel.value == "__none__":
                        fl.reject_entry(norm); ui.notify("Marked: no fund family", type="info")
                    else:
                        fl.confirm_entry(norm, int(sel.value)); ui.notify("Confirmed", type="positive")
                    _body.refresh()
                ui.button("Confirm", on_click=_do).props("dense color=primary")

        ui.label(f"Auto-matched — high confidence ({len(high)})").classes("text-md font-bold").style(
            f"color:{COLORS['text_heading']};margin-top:14px;")
        ui.label("Validated against the family's current SEC name. Skim for anything off.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        for e in high:
            reg = e.get("registrant") or fl._registrant_name(e.get("cik"))
            roster = fl.series_roster(e.get("cik"))
            cnt = (roster or {}).get("expected_series")
            with ui.row().classes("w-full items-center gap-2").style(
                    f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                ui.label(_row(e.get("manager"), e["norm"])).style("min-width:210px;font-weight:600;")
                ui.label(f"→ {pretty_name(reg or '—')}" + (f"  ·  {cnt} funds" if cnt else "")).style(
                    f"color:{COLORS['text_secondary']};font-size:12px;flex:1;")
                ui.button("Looks right", on_click=lambda ev=None, n=e["norm"]: (
                    fl.confirm_entry(n), ui.notify("Locked in", type="positive"), _body.refresh())).props(
                    "dense flat color=positive")
                ui.button("Wrong", on_click=lambda ev=None, n=e["norm"]: (
                    fl.reject_entry(n), ui.notify("Removed", type="warning"), _body.refresh())).props(
                    "dense flat color=negative")

        if confirmed:
            with ui.expansion(f"Confirmed ({len(confirmed)})", value=False).classes("w-full").style("margin-top:8px;"):
                for e in confirmed:
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.label(_row(e.get("manager"), e["norm"])).style("min-width:210px;")
                        ui.label(f"→ {pretty_name(e.get('registrant') or '—')}").style(
                            f"color:{COLORS['text_muted']};font-size:12px;flex:1;")
                        ui.button("Undo", on_click=lambda ev=None, n=e["norm"]: (
                            fl.restore_entry(n), _body.refresh())).props("dense flat")
        if rejected:
            with ui.expansion(f"Rejected ({len(rejected)})", value=False).classes("w-full"):
                for e in rejected:
                    with ui.row().classes("w-full items-center gap-2"):
                        ui.label(_row(e.get("manager"), e["norm"])).style(
                            f"min-width:210px;color:{COLORS['text_muted']};")
                        ui.button("Restore", on_click=lambda ev=None, n=e["norm"]: (
                            fl.restore_entry(n), _body.refresh())).props("dense flat")

    def _rescan():
        res = fl.bootstrap_from_book(get_active_client_id())
        ui.notify(f"Re-scanned book — {len(res['high'])} matched, {len(res['review'])} to confirm",
                  type="info")
        _body.refresh()

    with dlg, ui.card().style("min-width:min(920px,96vw);max-width:96vw;max-height:90vh;overflow:auto;"):
        with ui.row().classes("w-full justify-between items-center"):
            ui.label("Fund-lineup matches — manager → registered fund family").classes("text-lg font-bold")
            with ui.row().classes("items-center gap-1"):
                ui.button("Re-scan book", icon="refresh", on_click=_rescan).props("dense flat")
                ui.button(icon="close", on_click=dlg.close).props("flat round dense")
        ui.label("These links are what let the drill-down name a holder's individual funds. Confirm the "
                 "ambiguous ones, reject any wrong auto-match — your decisions stick across re-scans.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
        _body()
    dlg.open()


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
        mix_label, mix_color = "Strong — well above the 50/50 baseline management would be happy with", "#15803D"
    elif new_pct >= 45:
        mix_label, mix_color = "Balanced — roughly the 50/50 mix management would be content with", "#B45309"
    else:
        mix_label, mix_color = "Existing-heavy — below the mix that keeps management happy; needs more new-investor prospecting", "#B91C1C"

    new_from_recent_trip = sum(n for m, n in call_by_metro.items() if m in visited_metros)
    recency_note = ""
    if call_signal > 0 and visited_metros:
        recent_pct = round(new_from_recent_trip / call_signal * 100)
        if recent_pct >= 50:
            recency_note = (f"{recent_pct}% of the call-engagement signal ties back to a city you just visited "
                             f"({', '.join(visited_metros & set(call_by_metro.keys()))}) — worth watching whether this holds up "
                             f"once that trip's momentum fades, not just banking it as durable growth.")
        else:
            recency_note = (f"Checked against your recent trip(s): only {recent_pct}% of the call-engagement signal "
                             f"ties back to a recently-visited city — this isn't just NDR afterglow, it's broader than that.")

    visits_by_metro = {}
    for city, *_r in trip_rows:
        m = city_to_metro.get(city, city)
        visits_by_metro[m] = visits_by_metro.get(m, 0) + 1

    # Cluster raw "City, ST" holder metros into the same ~60-mile roadshow metros the unified
    # prospect view uses (Twin Cities as one stop, not Wayzata/Minneapolis split). Holders don't
    # carry raw city/state, so parse the "City, ST" label back through _metro_from_city.
    def _cluster(label):
        if not label or label in ("Unknown (SEC)", "International") or ", " not in label:
            return label or "Unknown (SEC)"
        city, st = label.rsplit(", ", 1)
        return _metro_from_city(city, st)

    metro_summary = {}
    for i in institutions:
        m = _cluster(i["Metro"])
        d = metro_summary.setdefault(m, {"count": 0, "tier1_nonholder": 0, "holders": 0, "top": None, "top_score": -1,
                                         "insts": [], "holder_list": [], "t1_list": []})
        d["count"] += 1
        d["insts"].append(i)
        if _score_val(i) >= 80 and not i["USIO_Holder"]:
            d["tier1_nonholder"] += 1
            d["t1_list"].append(i)                  # exact list behind the "Tier-1 ready" count, for the cell drill-down
        if i["USIO_Holder"]:
            d["holders"] += 1
            d["holder_list"].append(i)              # exact list behind the "Holders" count
        if _score_val(i) > (d["top_score"] or 0):
            d["top_score"], d["top"] = i["Engagement_Score"], i["Fund"]

    # Fold the qualified peer-prospect universe into the metro rollup as NON-HOLDERS — the funds
    # that own a peer/comp but not us, i.e. the actual NDR conversion targets. Without this the table
    # counts only current holders, so a prospect-rich metro (New York = 30 real prospects) reads
    # "0 non-holders" — the biggest roadshow opportunity, invisible. See peer_prospects.build_candidates.
    try:
        from core import peer_prospects
        _prospects = peer_prospects.build_candidates(get_active_client_id(), limit=None) or []
    except Exception:
        _prospects = []
    for c in _prospects:
        city, state = (c.get("city") or "").strip(), (c.get("state") or "").strip()
        m = _metro_from_city(city, state)     # same ~60-mile roadshow clustering as the holders above
        d = metro_summary.setdefault(m, {"count": 0, "tier1_nonholder": 0, "holders": 0,
                                         "top": None, "top_score": -1, "insts": [],
                                         "holder_list": [], "t1_list": []})
        d["count"] += 1
        _pinst = {"Fund": c.get("filer"), "Metro": m, "USIO_Holder": False,
                  "City": city.title(), "Position_Value": c.get("peer_value"),
                  "Conviction": None, "Engagement_Score": c.get("conviction"), "AUM": None,
                  "comps": c.get("comps"),          # carry the specific comps so the drill-down
                  "Action": "Prospect — owns a peer/comp, not you"}  # can show "owns CASS, FOUR"
        if (c.get("conviction") or 0) >= 70:        # strong, meeting-worthy prospect (Tier-1 proxy)
            d["tier1_nonholder"] += 1
            d["t1_list"].append(_pinst)             # prospects also count toward Tier-1 ready
        if d["top"] is None:                        # prospect-only metro: name its top prospect
            d["top"] = c.get("filer")
        d["insts"].append(_pinst)
    tracked_total = len(institutions) + len(_prospects)

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
    if not metro_priority:
        # A genuinely new client — no 13F holders on file and no inbound NDR requests
        # logged yet — has no metros to rank. This crashed until the fabricated seed
        # requests were removed; the seed had been masking it by guaranteeing three.
        ui.label("No geography to prioritise yet.").classes("section-head")
        ui.label("This view ranks where to spend roadshow time from your 13F holder book and any inbound "
                 "NDR requests. Neither is on file for this client yet — run a 13F refresh on the SEC "
                 "Intelligence tab, and log requests as they come in.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
        return
    top_metro, _tp, top_d, top_visits, _tr = metro_priority[0]
    top_metro_request = next((r for r in ndr_requests if r["metro"] == top_metro), None)
    top_metro_conf = None
    if top_metro_request and wainwright_conf and "Wainwright" in top_metro_request["firm"]:
        top_metro_conf = wainwright_conf

    tier1_preview = [i for i in institutions if _score_val(i) >= 80]
    # weakest_request / quiet_period_days removed with the "respond before the quiet
    # period begins in N days" line. That countdown collapsed "not configured" and
    # "already started" to the same 0, so BOTH tenants rendered "in 0 days". Reports'
    # quiet-period banner is the correct pattern if a countdown is wanted again: it
    # renders only when a quiet_start exists AND the count is positive.

    ui.label("Big Picture — Where Things Stand").classes("text-xl font-bold").style(f"color:{COLORS['text_heading']};margin-top:10px;")

    with ui.row().classes("w-full gap-3"):
        _bp_metric("NDR Requests/City", str(len(ndr_requests)),
                   [f"{r['analyst']} ({r['firm']}) → {r['city']}: {r['reason']} — received {r['received']}" for r in ndr_requests])
        # Was "New Investor Signals" = call-listener + website-visitor counts. Both read
        # CSVs that exist for NO client (there is no call or web-analytics integration),
        # so this headline tile was structurally pinned at 0 for every customer, forever.
        # New positions ARE measurable — they come from the 13F holder history — and
        # "who just bought in" is the more useful number anyway.
        _new_pos = [i for i in institutions if (i.get("Direction") or "").lower() == "new"]
        _bp_metric("New Positions (13F)", str(len(_new_pos)),
                   [f"{pretty_name(i['Fund'])} — {i.get('Metro') or '—'}"
                    f"{(' · ' + i['Conviction']) if i.get('Conviction') else ''}" for i in _new_pos[:6]]
                   or ["No new positions in the latest 13F cycle."])
        _bp_metric("Existing Holders Tracked", f"{holder_count} / {tracked_total}",
                   [("By city: " + ", ".join(f"{m} ({n})" for m, n in sorted(holders_by_metro.items(), key=lambda x: -x[1]))) if holders_by_metro else "No holders tracked yet.",
                    f"{tracked_total - holder_count} active non-holder prospects being worked"])
        _bp_metric("Past NDRs & Meetings", str(len(trip_rows)),
                   [f"{c} — {dt} · {tm} · Sponsor: {sp} · {n} meetings" for c, dt, tm, sp, n in trip_rows] or ["No NDR trips logged yet"])

    ui.html(
        f"<div style='font-size:13px;color:{COLORS['text_muted']};margin-top:6px;'>New vs. existing — where the pipeline is weighted right now</div>"
        f"<div style='display:flex;height:20px;border-radius:6px;overflow:hidden;'>"
        f"<div style='width:{new_pct}%;background:#3B82F6;'></div>"
        f"<div style='width:{100-new_pct}%;background:#475569;'></div></div>"
        f"<div style='font-size:12px;color:{COLORS['text_muted']};margin-top:4px;'>New/prospective: {new_total} &nbsp; Existing holders: {holder_count}</div>"
        f"<div style='font-size:12px;color:{mix_color};margin-top:4px;'>{mix_label} ({new_pct}% new / {100-new_pct}% existing)</div>"
        + (f"<div style='font-size:11px;color:{COLORS['text_muted']};margin-top:2px;'>{recency_note}</div>" if recency_note else "")
    )

    most_visited = max(visits_by_metro.items(), key=lambda x: x[1]) if visits_by_metro else None
    if most_visited and most_visited[1] >= 2 and most_visited[0] != top_metro:
        ui.html(
            f"<div style='font-size:13px;color:#B45309;margin-top:10px;'>"
            f"By contrast, <b>{most_visited[0]}</b> has had {most_visited[1]} trips already for only "
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
        f"<div style='background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:3px solid {COLORS['accent']};border-radius:12px;padding:18px 22px;'>"
        f"<div class='section-head' style='margin:0;'>This week's priority</div>"
        f"<div style='font-size:16px;font-weight:600;color:{COLORS['text_heading']};margin-top:4px;'>Focus city: {top_metro}</div>"
        f"<div style='font-size:13px;color:{COLORS['text_secondary']};line-height:1.6;margin-top:6px;'>"
        f"{top_d['count']} tracked institution(s) here"
        + (f", including <b>{top_d['top']}</b> (score {top_d['top_score']})" if top_d.get('top') else "")
        + f" — {top_d['tier1_nonholder']} non-holder(s) at Tier 1 ready to convert and {top_d['holders']} existing holder(s) to defend — "
        f"{'zero NDR trips logged here yet' if top_visits == 0 else f'only {top_visits} trip(s) so far'}."
        + top_req_html + top_conf_html + "</div></div>"
    )
    # Targeting moves only. The "respond to <analyst> before the quiet period" line
    # used to live here too, which put a second, competing "actions for management"
    # list one page away from Today's — and the two could disagree (Today reported
    # no outstanding analyst follow-ups while this urged replying to one). Inbound
    # requests are now counted in Today's follow-up line, which is the surface for
    # things with a clock on them; what's left here is the tier/metro read that the
    # table below substantiates.
    ui.html(
        f"<div style='font-size:13px;color:{COLORS['text_secondary']};margin-top:10px;'><b>Targeting moves this week:</b></div>"
        f"<ol style='font-size:13px;color:{COLORS['text_secondary']};margin-top:4px;line-height:1.7;'>"
        f"<li>Direct 1x1 call: <b>{next((i['Fund'] for i in tier1_preview if not i['USIO_Holder']), 'top Tier 1 non-holder')}</b> — highest-scoring active conversion target.</li>"
        f"<li>Defend the position: <b>{next((i['Fund'] for i in tier1_preview if i['USIO_Holder']), 'top Tier 1 holder')}</b> — actively adding shares, needs 15 minutes before the print.</li>"
        + f"<li>Scope a <b>{top_metro}</b> NDR as the next roadshow"
        + (f", timed around {top_metro_request['analyst']}'s request" if top_metro_request else "")
        + " — it now outranks every other market on an opportunity-per-visit-and-request basis.</li></ol>"
    )

    # Geographic breakdown — answers the obvious question the counts above raise:
    # "these institutions... where ARE they?" One row per metro with its holders,
    # ready-to-convert Tier-1 non-holders, NDR trips so far, and its top name.
    ui.markdown("---")
    ui.label("Where they are — tracked institutions & peer-owners by metro").classes("section-head").style("margin-top:6px;")

    # Join the all-bucket peer-owner universe (Peer Prospects' data) onto the same metro rows, so this
    # is the ONE metro list — no separate "peer-owners by metro" table. Uses all_candidates (every
    # bucket) rather than build_candidates (institutional only), matching the Peer Prospects counts.
    try:
        from core import peer_prospects as _pp
        _all_cands = _pp.all_candidates(get_active_client_id())
    except Exception:
        _all_cands = []
    _tier_key = {"Institutional": "inst", "RIA / wealth": "ria", "Diversified": "div",
                 "Market maker": "mm", "Curated": "curated"}
    peer_by_metro = {}
    peer_funds_by_metro = {}          # metro -> [candidate dicts], for the click-to-select dialog
    for _c in _all_cands:
        _m = _metro_from_city(_c.get("city"), _c.get("state"))
        peer_funds_by_metro.setdefault(_m, []).append(_c)
        _pm = peer_by_metro.setdefault(_m, {"funds": 0, "inst": 0, "ria": 0, "div": 0, "mm": 0, "curated": 0})
        _pm["funds"] += 1
        _k = _tier_key.get(_c.get("tier"))
        if _k:
            _pm[_k] += 1

    def _roadshow_read(metro, n):
        if metro == "International":
            return "Intl — virtual"
        if n >= 4:
            return "Full-day NDR stop"
        if n >= 2:
            return "Half-day"
        return "Single stop" if n else "—"

    # Union all metro keys (a metro may have holders but no peer-owners, or vice-versa).
    _all_metros = set(metro_summary) | set(peer_by_metro)
    _blank_pm = {"funds": 0, "inst": 0, "ria": 0, "div": 0, "mm": 0, "curated": 0}
    geo_rows = sorted(
        [{"metro": m, "holders": (d := metro_summary.get(m, {})).get("holders", 0),
          "t1": d.get("tier1_nonholder", 0), "trips": visits_by_metro.get(m, 0),
          "funds": (pm := peer_by_metro.get(m, _blank_pm))["funds"], "inst": pm["inst"],
          "ria": pm["ria"], "div": pm["div"], "mm": pm["mm"], "curated": pm["curated"],
          "read": _roadshow_read(m, pm["funds"]), "top": pretty_name(d.get("top")) if d.get("top") else "—"}
         for m in _all_metros],
        key=lambda r: (-r["funds"], -r["holders"], -r["t1"]))
    geo_cols = [
        {"name": "metro", "label": "Metro / region", "field": "metro", "align": "left", "sortable": True},
        {"name": "holders", "label": "Holders", "field": "holders", "align": "right", "sortable": True},
        {"name": "t1", "label": "Tier-1\nready", "field": "t1", "align": "right", "sortable": True},        # two-row header
        {"name": "funds", "label": "Peer-\nowners", "field": "funds", "align": "right", "sortable": True},  # two-row header
        {"name": "inst", "label": "Inst", "field": "inst", "align": "right", "sortable": True},
        {"name": "ria", "label": "RIA", "field": "ria", "align": "right", "sortable": True},
        {"name": "div", "label": "Divsfd", "field": "div", "align": "right", "sortable": True,
         "tooltip": "Diversified — large multi-strategy / bank-AM houses"},
        {"name": "mm", "label": "MM", "field": "mm", "align": "right", "sortable": True,
         "tooltip": "Market makers — no fundamental PM to pitch"},
        {"name": "curated", "label": "Curated", "field": "curated", "align": "right", "sortable": True},
        {"name": "trips", "label": "NDRs", "field": "trips", "align": "right", "sortable": True},
        {"name": "read", "label": "Roadshows", "field": "read", "align": "left", "sortable": True},
        {"name": "top", "label": "Top holder", "field": "top", "align": "left", "sortable": True,
         "style": "white-space:normal;min-width:220px;", "headerStyle": "white-space:normal;"},
    ]
    # Click a metro row to see exactly WHO is there — the counts above always
    # raised "which 5 institutions?"; this opens the named list on demand
    # Click a metro row → tick the peer-owners there → shortlist onto an NDR (one selectable list;
    # replaces the old tracked-only readout and the separate Peer Prospects metro table).
    # ── Cell drill-down: click any number to see the exact names behind it ────────────
    # Every count in this table is backed by a real list, so a number is a doorway, not a
    # dead end. Holders/Tier-1 come from the lists captured while counting (can't disagree
    # with the cell); the bucket counts filter the same peer-owner universe the row uses.
    _CLICKABLE = {"holders": "Holders", "t1": "Tier-1 ready", "funds": "Peer-owners",
                  "inst": "Institutional", "ria": "RIA / wealth", "div": "Diversified",
                  "mm": "Market maker", "curated": "Curated targets"}

    def _drill_list(metro, col):
        d = metro_summary.get(metro, {})
        if col == "holders":
            return d.get("holder_list", [])
        if col == "t1":
            return d.get("t1_list", [])
        funds = peer_funds_by_metro.get(metro, [])
        if col == "funds":
            return funds
        return [c for c in funds if _tier_key.get(c.get("tier")) == col]

    def _drill_row(x):
        # Two shapes reach here: peer-owner candidates ("filer"/"tier"/"conviction"/"comps")
        # and tracked-institution dicts ("Fund"/"USIO_Holder"/"Engagement_Score"). Normalise both.
        raw_name = x.get("filer") or x.get("Fund") or ""
        if "filer" in x:
            conv = x.get("conviction")
            peers = ", ".join(sorted((x.get("comps") or {}).keys()))
            return {"_filer": x.get("filer"),          # row key for selection (not a column)
                    "Fund": pretty_name(x.get("filer") or "—"),
                    "City": (x.get("city") or "—").title(),
                    "Category": x.get("tier") or "—",
                    "Score": round(conv) if isinstance(conv, (int, float)) else "—",
                    "Detail": (f"Owns {peers}" if peers else ("Curated target" if x.get("kind") == "curated" else "—")),
                    "Funds": _fund_lineup_label(raw_name)}
        sc = x.get("Engagement_Score")
        # A peer-prospect carried its comps in — show which comp it owns ("owns CASS, FOUR"),
        # matching the Peer-owners drill. Real tracked institutions have no comps → fall back.
        peers = ", ".join(sorted((x.get("comps") or {}).keys()))
        detail = f"Owns {peers}" if peers else (x.get("Conviction") or x.get("Action") or "—")
        return {"Fund": pretty_name(x.get("Fund") or "—"),
                "City": x.get("City") or (x.get("Metro") or "—"),
                "Category": "Holder" if x.get("USIO_Holder") else "Non-holder",
                "Score": round(sc) if isinstance(sc, (int, float)) else "—",
                "Detail": detail,
                "Funds": _fund_lineup_label(raw_name)}

    _drill_dialog = ui.dialog()

    # Peer-owner buckets are NDR candidates, so their drill-down is selectable → Add to NDR
    # (same shortlist flow as the metro row-click). Holders / Tier-1 are tracked institutions,
    # not prospecting targets, so those stay read-only.
    _selectable_cols = {"funds", "inst", "ria", "div", "mm", "curated"}

    def _open_cell_drill(e):
        metro, col = e.args.get("metro"), e.args.get("col")
        items = _drill_list(metro, col)
        d_rows = [_drill_row(x) for x in items]
        is_peer = col in _selectable_cols
        _drill_dialog.clear()
        with _drill_dialog, ui.card().style("min-width:min(900px,95vw);max-width:95vw;"):
            with ui.row().classes("w-full justify-between items-center"):
                ui.label(f"{metro} — {_CLICKABLE.get(col, col)} · {len(d_rows)} "
                         f"name{'s' if len(d_rows) != 1 else ''}").classes("text-lg font-bold")
                ui.button(icon="close", on_click=_drill_dialog.close).props("flat round dense")
            if not d_rows:
                ui.label("No names behind this number.").style(f"color:{COLORS['text_muted']};")
            else:
                _n_lineups = sum(1 for r in d_rows if r.get("Funds"))
                # Add-to-NDR bar (restored) — only for the peer-owner buckets, which are the
                # NDR-prospecting universe. Tick names → shortlist onto a new or existing trip.
                trip_sel = new_name = tbl = None
                cand_by_filer = {c.get("filer"): c for c in items} if is_peer else {}
                if is_peer:
                    _open = [(i, t) for i, t in enumerate(_load_json("ndr_trips.json", [])) if t.get("status") != "Completed"]
                    trip_opts = {str(i): (t.get("name") or f"NDR {i+1}") for i, t in _open}
                    trip_opts["__new__"] = "＋ New NDR…"
                    with ui.row().classes("w-full items-end gap-2").style(
                            f"background:{COLORS['surface_hover_bg']};border-radius:8px;padding:8px 10px;margin-bottom:6px;"):
                        ui.label("Tick names, then add them to an NDR as shortlisted targets.").style(
                            f"color:{COLORS['text_muted']};font-size:12px;flex:1;")
                        trip_sel = ui.select(trip_opts, value="__new__", label="NDR").props("dense outlined").style("min-width:170px;")
                        new_name = ui.input("New NDR name", value=f"{metro} NDR").props("dense outlined").style("min-width:150px;")
                        new_name.bind_visibility_from(trip_sel, "value", backward=lambda v: v == "__new__")
                        add_btn = ui.button("Add selected", icon="playlist_add").props("dense color=primary")
                _dcol_label = {"Funds": "Fund lineup (SEC)", "Category": "Category"}
                dcols = [{"name": k, "label": _dcol_label.get(k, k),
                          "field": k, "sortable": True,
                          "align": "right" if k == "Score" else "left",
                          **({"style": "white-space:normal;min-width:230px;",
                              "headerStyle": "white-space:normal;"} if k == "Funds" else {})}
                         for k in ("Fund", "City", "Category", "Score", "Detail", "Funds")]
                _extra = {"selection": "multiple"} if is_peer else {}
                tbl = ui.table(columns=dcols, rows=d_rows, row_key=("_filer" if is_peer else "Fund"),
                               pagination=25, **_extra).classes("w-full").props("dense flat")   # 25 per page
                # Fund name → Account 360 profile. @click.stop so it doesn't toggle the row checkbox.
                _orig_by_fund = {pretty_name(it.get("filer") or it.get("Fund") or ""): it for it in items}
                tbl.add_slot("body-cell-Fund", (
                    '<q-td :props="props">'
                    '<span class="cursor-pointer" '
                    f'style="color:{COLORS["accent"]};text-decoration:underline dotted;text-underline-offset:2px;" '
                    '@click.stop="() => $parent.$emit(\'openProfile\', props.row.Fund)">'
                    '{{ props.value }}</span></q-td>'))
                tbl.on("openProfile", lambda e: _open_account_profile(
                    _orig_by_fund.get(e.args) or {"Fund": e.args}))

                if is_peer:
                    def _do_add():
                        sel = tbl.selected
                        if not sel:
                            ui.notify("Tick at least one name first.", type="warning"); return
                        trips2 = _load_json("ndr_trips.json", [])
                        if trip_sel.value == "__new__":
                            nm = (new_name.value or "").strip()
                            if not nm:
                                ui.notify("Name the new NDR.", type="warning"); return
                            trips2.append({
                                "name": nm, "sponsor_bank": "", "dates": "TBD", "ndr_type": "in-person",
                                "city": metro, "focus": "", "team": [], "notes": "", "meetings": [], "shortlist": [],
                                "status": "Planning", "debrief": {}, "days": 2, "slots_per_day": 6,
                                "created": datetime.now().strftime("%Y-%m-%d"),
                            })
                            target, tname = trips2[-1], nm
                        else:
                            target = trips2[int(trip_sel.value)]
                            tname = target.get("name") or "NDR"
                        target.setdefault("shortlist", [])
                        have = {s.get("institution") for s in target["shortlist"]} | \
                               {m.get("institution") for m in target.get("meetings", [])}
                        added = 0
                        for row in sel:
                            c = cand_by_filer.get(row.get("_filer"))
                            if not c or c.get("filer") in have:
                                continue
                            target["shortlist"].append(_shortlist_record(c))
                            have.add(c.get("filer")); added += 1
                        _save_json("ndr_trips.json", trips2)
                        skipped = len(sel) - added
                        ui.notify(f"Shortlisted {added} name(s) to '{tname}'"
                                  + (f" · {skipped} already on it" if skipped else "")
                                  + ". See NDR Planner → Active NDRs.", type="positive")
                        _drill_dialog.close()
                    add_btn.on_click(_do_add)
                if _n_lineups:
                    ui.label(f"“Fund lineup” names the individual '40-Act funds the manager runs (from its "
                             f"latest SEC N-CEN/485 filing) — the strategy sleeve a 13F hides. Shown for "
                             f"{_n_lineups} of {len(d_rows)} here; blank where the holder has no registered "
                             "fund family (hedge fund / SMA) or isn't yet confirmed in the crosswalk.").style(
                        f"color:{COLORS['text_muted']};font-size:11px;margin-top:6px;")
        _drill_dialog.open()

    # pagination=25 → the metro list itself pages 25 at a time; sortable headers sort the full set.
    geo_table = ui.table(columns=geo_cols, rows=geo_rows, row_key="metro", pagination=25).classes(
        "w-full cursor-pointer").props("dense flat")
    # Custom header so a "\n" in a label renders as a two-row heading (pre-line) — lets the numeric
    # columns stay narrow and hands the freed width to Top name so it isn't truncated. QTh with
    # :props keeps the sort click/arrow, so the two-row header stays sortable.
    geo_table.add_slot("header", r'''
        <q-tr :props="props">
          <q-th v-for="col in props.cols" :key="col.name" :props="props"
                style="white-space:pre-line;vertical-align:bottom;line-height:1.15;"
                :class="col.tooltip ? 'cursor-help' : ''">
            {{ col.label }}
            <q-tooltip v-if="col.tooltip">{{ col.tooltip }}</q-tooltip>
          </q-th>
        </q-tr>
    ''')
    # Make each count a clickable, underlined link that opens the drill-down. @click.stop keeps the
    # row-click ("Add to NDR" select dialog) from also firing. Zero renders as a muted, inert number.
    for _cc in _CLICKABLE:
        geo_table.add_slot(f"body-cell-{_cc}", (
            '<q-td :props="props" class="text-right">'
            '<span v-if="props.value" class="cursor-pointer" '
            f'style="color:{COLORS["accent"]};text-decoration:underline dotted;text-underline-offset:2px;" '
            '@click.stop="() => $parent.$emit(\'cellClick\', {metro: props.row.metro, col: \'%s\'})">'
            '{{ props.value }}</span>'
            '<span v-else style="opacity:.45;">{{ props.value }}</span>'
            '</q-td>'
        ) % _cc)
    geo_table.on("cellClick", _open_cell_drill)
    geo_table.on("rowClick", lambda e: _open_metro_select_dialog(
        e.args[1]["metro"], peer_funds_by_metro.get(e.args[1]["metro"], [])))
    _peer_total = sum(v["funds"] for v in peer_by_metro.values())
    ui.label(f"{holder_count} current holders and {_peer_total} peer-owners (own a comp, not you) across "
             f"{len(_all_metros)} metros. Holders = own you · Peer-owners break into Inst / RIA / Diversified / MM / "
             "Curated (they sum to Peer-owners). Click any column header to sort · click any underlined number to see "
             "the exact names behind it (25 per page) · click a metro row to shortlist its peer-owners onto an NDR.").style(
        f"color:{COLORS['text_muted']};font-size:11px;")
    ui.button("Manage fund-lineup matches", icon="account_tree",
              on_click=_open_lineup_crosswalk_dialog).props("flat dense").style("font-size:11px;margin-top:2px;")


def _bp_metric(label, value, detail_lines):
    with ui.card().classes("flex-1").style(f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"):
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:11px;")
        ui.label(value).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        with ui.expansion("Details", value=False).classes("w-full"):
            for line in detail_lines:
                ui.label(line).style(f"color:{COLORS['text_muted']};font-size:11px;")


# ─────────────────────────────────────────────────────────────────────────
# Buy-Side Intelligence tab
# ─────────────────────────────────────────────────────────────────────────
def _render_buyside_tab(institutions, meeting_log, mode):
    contacts = get_institution_contacts()

    if mode == "pre":
        ui.label("Buy-Side Intelligence — Pre-Earnings Engagement").classes("text-lg font-bold")
        ui.label("Three-layer institutional targeting · Engagement score 0-100 · Prioritized by probability of buying into the re-rating story").style(f"color:{COLORS['text_muted']};font-size:12px;")
    else:
        ui.label("Buy-Side Intelligence — Post-Earnings Prospecting").classes("text-lg font-bold")
        ui.label("Post-earnings catalyst scoring · Who heard the beat · Who fits the upgrade thesis · 5-day prospecting window").style(f"color:{COLORS['text_muted']};font-size:12px;")

    tier1 = [i for i in institutions if _score_val(i) >= 80]
    tier2 = [i for i in institutions if 40 <= _score_val(i) < 80]
    tier3 = [i for i in institutions if _score_val(i) < 40]

    ui.label("Engagement Funnel").classes("font-bold").style("margin-top:10px;")
    with ui.row().classes("w-full gap-3 items-stretch"):
        _tier_card(tier1, "Tier 1 — Defend / Convert", "Direct 1x1 calls this week", COLORS["negative"])
        _tier_card(tier2, "Tier 2 — Nurture", "Send the Q2 preview deck", COLORS["warning"])
        _tier_card(tier3, "Tier 3 — Passive", "Add to the next NDR queue", COLORS["accent"])

    ui.markdown("---")

    # One left-aligned summary line — "Q1 call listeners" reads as a
    # continuation of the tracked count rather than floating off to the far
    # right (justify-between) disconnected from anything.
    with ui.row().classes("items-baseline gap-2"):
        ui.label(f"{len(institutions)} institutions tracked").classes("font-bold")
        ui.label(f"· {sum(1 for i in institutions if i['Call_Listener'])} were Q1 call listeners").style(f"color:{COLORS['text_muted']};font-size:12px;")

    with ui.expansion("Filter Criteria — Coverage Priority, Holder Status, Turnover, Metro, Intent, Ownership", value=False).classes("w-full"):
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
            # Coerce to str: a record with Metro=None makes sorted() raise
            # TypeError('<' not supported between NoneType and str) and takes the whole
            # page down. Defensive here as well as at the source, because this list is fed
            # by several record shapes (13F holders, promoted prospects, SEC universe).
            metro_options = ["All Regions"] + sorted({(i.get("Metro") or "Unknown (SEC)")
                                                      for i in institutions})
            metro_filter = ui.select(metro_options, value="All Regions").classes("min-w-[160px]").props("label='Metro'")
        turnover_options = ["Low (Long-Term Value)", "Medium (Growth/GARP)", "High (Hedge/Trading)"]
        # Include any other turnover value actually present in the universe
        # (e.g. "Unknown (SEC)" on real SEC-sourced names) so the default
        # all-selected filter doesn't silently hide them — same silent-hiding
        # issue as the tier filter above.
        turnover_options = turnover_options + sorted(
            {i["Turnover_Style"] for i in institutions} - set(turnover_options))
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

    # ── Add-to-NDR bar (NDR pipeline Phase 4B) — the Buy-Side list feeds the same
    # pipeline as Peer Prospects. Filter to the set you want (metro, holder, score),
    # tick institutions, and shortlist them onto an NDR.
    bs_checks = {}
    _bs_open = [(i, t) for i, t in enumerate(_load_json("ndr_trips.json", [])) if t.get("status") != "Completed"]
    _bs_opts = {str(i): (t.get("name") or f"NDR {i+1}") for i, t in _bs_open}
    _bs_opts["__new__"] = "＋ New NDR…"
    with ui.row().classes("w-full items-end gap-2").style(
            f"background:{COLORS['surface_hover_bg']};border-radius:8px;padding:8px 10px;margin:6px 0;"):
        ui.label("Tick institutions below, then add them to an NDR as shortlisted targets.").style(
            f"color:{COLORS['text_muted']};font-size:12px;flex:1;")
        _bs_sel = ui.select(_bs_opts, value="__new__", label="NDR").props("dense outlined").style("min-width:170px;")
        _bs_name = ui.input("New NDR name", value="Buy-Side NDR").props("dense outlined").style("min-width:150px;")
        _bs_name.bind_visibility_from(_bs_sel, "value", backward=lambda v: v == "__new__")

        def _bs_add():
            picked = [(f, inst) for f, (cb, inst) in bs_checks.items() if cb.value]
            if not picked:
                ui.notify("Tick at least one institution first.", type="warning"); return
            trips2 = _load_json("ndr_trips.json", [])
            if _bs_sel.value == "__new__":
                nm = (_bs_name.value or "").strip()
                if not nm:
                    ui.notify("Name the new NDR.", type="warning"); return
                trips2.append({
                    "name": nm, "sponsor_bank": "", "dates": "TBD", "ndr_type": "in-person",
                    "city": "Multiple", "focus": "", "team": [], "notes": "", "meetings": [],
                    "shortlist": [], "status": "Planning", "debrief": {}, "days": 2, "slots_per_day": 6,
                    "created": datetime.now().strftime("%Y-%m-%d"),
                })
                target, tname = trips2[-1], nm
            else:
                target = trips2[int(_bs_sel.value)]
                tname = target.get("name") or "NDR"
            target.setdefault("shortlist", [])
            have = {s.get("institution") for s in target["shortlist"]} | \
                   {m.get("institution") for m in target.get("meetings", [])}
            added = 0
            for f, inst in picked:
                if f in have:
                    continue
                target["shortlist"].append(_shortlist_from_inst(inst))
                have.add(f); added += 1
            _save_json("ndr_trips.json", trips2)
            skipped = len(picked) - added
            ui.notify(f"Shortlisted {added} to '{tname}'"
                      + (f" · {skipped} already on it" if skipped else "")
                      + ". See NDR Planner → Active NDRs.", type="positive")
        ui.button("Add selected", icon="playlist_add", on_click=_bs_add).props("dense color=primary")

    list_container = ui.column().classes("w-full gap-3")

    def apply_and_render():
        banner_container.clear()
        list_container.clear()
        bs_checks.clear()
        sel_tiers = tier_filter.value or [1, 2, 3]
        sel_turnover = turnover_filter.value or turnover_options
        filtered = [i for i in institutions
                    if i["Coverage_Priority"] in sel_tiers
                    and (holder_filter.value == "All"
                         or (holder_filter.value == "Current holders" and i["USIO_Holder"])
                         or (holder_filter.value == "Non-holders only" and not i["USIO_Holder"]))
                    and _score_val(i) >= (score_filter.value or 0)
                    and (metro_filter.value == "All Regions" or i["Metro"] == metro_filter.value)
                    and i["Turnover_Style"] in sel_turnover
                    and _score_val(i, "Digital_Intent_Score") >= (intent_filter.value or 0)
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
                # Checkbox lives OUTSIDE the card (no change to _institution_card), so ticking a
                # fund registers it for the Add-to-NDR bar above.
                with ui.row().classes("w-full items-start no-wrap gap-2"):
                    bs_checks[inst["Fund"]] = (
                        ui.checkbox().props("dense").style("margin-top:12px;flex:0 0 auto;"), inst)
                    with ui.column().classes("flex-1").style("min-width:0;"):
                        _institution_card(inst, meeting_log, contacts)

    filter_btn.on_click(apply_and_render)
    apply_and_render()


def _render_repeat_alert_banner(filtered, meeting_log):
    """Global 'Repeat Meeting Alerts' banner above the institution list —
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

    ui.label("Repeat Meeting Alerts — Investigate Signal").classes("font-bold").style(f"color:{COLORS['text_heading']};")
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
            sig_icon, sig_txt, sig_clr = "", "Likely diligence — shares increasing", COLORS["positive"]
        elif "positive" in outcome.lower() or "interested" in outcome.lower():
            sig_icon, sig_txt, sig_clr = "", "Monitor — positive tone but verify intent", COLORS["warning"]
        elif qoq < 0:
            sig_icon, sig_txt, sig_clr = "", "Flag — shares declining, possible exit diligence", COLORS["negative"]
        else:
            sig_icon, sig_txt, sig_clr = "", "Unknown intent — escalate to CFO for next call", COLORS["warning"]

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
    with ui.card().classes("flex-1 column").style(
        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-left:4px solid {accent_color};"):
        with ui.row().classes("w-full justify-between items-start"):
            with ui.column().classes("gap-0"):
                ui.label(label).style(f"color:{accent_color};font-weight:bold;")
                ui.label(action).style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(str(len(institutions))).classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
        ui.space()
        # Always render the disclosure — even when empty — so all three tier
        # cards share the same structure and height and each gets an arrow
        # (Tier 1 with 0 institutions used to have none, so it sat shorter).
        with ui.expansion(f"Show {len(institutions)} institution(s)").classes("w-full"):
            if institutions:
                for inst in institutions:
                    ui.label(f"{pretty_name(inst['Fund'])} — {inst['Engagement_Score']}/100").style(f"color:{COLORS['text_body']};font-size:12px;")
            else:
                ui.label("No institutions currently in this tier.").style(f"color:{COLORS['text_muted']};font-size:12px;")


def _institution_card(inst, meeting_log, contacts):
    fund_meetings = _get_fund_meetings(meeting_log, inst["Fund"])
    repeat_gap = _get_repeat_signal(fund_meetings)
    score = inst["Engagement_Score"]
    holder_badge = "Current Holder" if inst["USIO_Holder"] else "Non-Holder"
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
                ownership_badge = "Passive" if inst.get("Ownership_Style") == "Passive" else "Active"
                with ui.row().classes("items-center gap-2"):
                    ui.label(f"{pretty_name(inst['Fund'])}  ·  {inst['Type']}  ·  AUM {inst['AUM']}").classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:14px;")
                    _src = inst.get("Source", "Seed (demo)")
                    ui.label(_src).style(
                        f"background:{_source_color(_src)};color:#fff;border-radius:6px;padding:1px 6px;"
                        "font-size:10px;font-weight:700;letter-spacing:.02em;white-space:nowrap;")
                ui.label(f"{inst['Metro']}  ·  {inst['Turnover_Style']}  ·  {ownership_badge}  ·  {holder_badge}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                if repeat_gap is not None:
                    ui.label(f"Repeat meeting in {repeat_gap}d").style(f"color:#B45309;font-size:12px;font-weight:bold;")
                if days_contacted is not None and days_contacted <= 7:
                    ui.label(f"Contacted {days_contacted}d ago — off Today's Investor Pipeline until day 8").style(
                        f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")
            with ui.column().classes("items-center"):
                ui.label(str(score)).classes("text-2xl font-bold").style(f"color:{COLORS['accent_light']};")
                ui.label("/100").style(f"color:{COLORS['text_muted']};font-size:11px;")

        with ui.row().classes("w-full gap-6").style("margin-top:6px;"):
            ui.label(f"Shares: {shares_str}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(f"QoQ: {qoq_str}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            # None means UNKNOWN, not "no". There is no call-listener or website-analytics
            # integration, so rendering "Did not listen" / "None · None" for a real 13F holder
            # asserts a negative we never measured. Say we don't know.
            if inst.get("Call_Listener") is None:
                _call_str = "no call data"
            elif inst["Call_Listener"]:
                _call_str = inst.get("Listen_Duration") or "listened"
            else:
                _call_str = "Did not listen"
            _visits_str = ("no visit data" if inst.get("IR_Visits_30d") is None
                           else f"{inst['IR_Visits_30d']} · {inst.get('Last_Visit') or '—'}")
            ui.label(f"Q1 call: {_call_str}").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(f"IR visits (30d): {_visits_str}").style(f"color:{COLORS['text_muted']};font-size:12px;")
        # marks a peer holding confirmed by a real SEC 13F filing (see
        # _enrich_peer_holdings_with_live_13f); an unmarked ticker is still
        # the original hand-typed seed guess — that ticker hasn't been
        # 13F-refreshed yet (SEC Intelligence tab's "Refresh 13F
        # Institutional Holders" button).
        # Defensive: several record shapes feed this list; Peer_Holdings_Source is a
        # {ticker: "live"} dict for enriched 13F holders but can be a bare string (or
        # missing) on SEC/peer-prospect records, and Peer_Holdings can be a str — either
        # of which used to crash the whole Buy-Side tab here.
        _peer_src = inst.get("Peer_Holdings_Source") or {}
        if not isinstance(_peer_src, dict):
            _peer_src = {}
        _peers = inst.get("Peer_Holdings") or []
        if isinstance(_peers, str):
            _peers = [_peers]
        _peer_labels = [t + (" " if _peer_src.get(t) == "live" else "") for t in _peers]
        ui.label(f"Peers held: {', '.join(_peer_labels) or '—'}").style(f"color:{COLORS['text_muted']};font-size:12px;")
        ui.label(f"Action: {inst['Action']}").style(f"color:{COLORS['accent_light']};font-size:12px;font-weight:bold;")

        contact = contacts.get(inst["Fund"], {})
        # Actions sit in a bottom row set off by a thin top divider — same treatment
        # as the Today dashboard cards, so the whole app reads consistently.
        with ui.row().classes("w-full gap-3 items-center").style(
                f"margin-top:4px;padding-top:4px;border-top:1px solid {COLORS['border']};"):
            if contact.get("email"):
                _mailto(contact["email"], f"{CT('ticker')} — Following up, {inst['Fund']}", "Hi,\n\n", f"Email {contact.get('name','Contact')}")
            ui.button("Draft Pre-Earnings Outreach", on_click=lambda inst=inst, contact=contact: _open_outreach_dialog(inst, contact)).props("flat dense")
            ui.button(f"Meeting Log ({len(fund_meetings)})", on_click=lambda inst=inst, fm=fund_meetings, rg=repeat_gap: _open_meeting_log_dialog(inst, fm, rg)).props("flat dense")


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
                ui.label(f"Likely diligence — shares +{qoq:,} and repeat meeting in {repeat_gap}d. Escalate to CFO.").style("color:#15803D;font-size:12px;")
            elif qoq < 0:
                ui.label(f"Flag — shares {qoq:,} and repeat meeting in {repeat_gap}d. Possible pre-exit diligence.").style("color:#B91C1C;font-size:12px;")
            else:
                ui.label(f"Intent unclear — repeat meeting in {repeat_gap}d, no share change. Ask directly.").style("color:#B45309;font-size:12px;")

        if fund_meetings:
            for mtg in fund_meetings:
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};"):
                    ui.label(f"{mtg['Date']} · {mtg['Type']} — {mtg.get('Outcome','—')}").classes("font-bold").style("font-size:13px;")
                    ui.label(f"Attendees: {mtg.get('Attendees','—')}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    ui.label(f"Notes: {mtg.get('Notes','—')}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    if mtg.get("Logged By"):
                        ui.label(f"Logged by: {mtg['Logged By']}").style(f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")
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

        ui.markdown("**Log a new meeting**")
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
                ui.notify(f"Repeat meeting alert — {inst['Fund']} met {len(updated)}x in {new_gap}d. "
                          f"Interaction Score {delta_str} → {new_interaction}/{INTERACTION_SCORE_MAX} · "
                          f"Engagement Score → {new_engagement}/100", type="warning")
            else:
                ui.notify(f"Meeting logged for {inst['Fund']} · Interaction Score {delta_str} → "
                          f"{new_interaction}/{INTERACTION_SCORE_MAX} · Engagement Score → {new_engagement}/100")
            dialog.close()
            _refresh()

        ui.button("Log Meeting", on_click=log_meeting).props("color=primary")
        ui.button("Close", on_click=dialog.close).props("flat")
    dialog.open()


# ─────────────────────────────────────────────────────────────────────────
# NDR Planner tab
# ─────────────────────────────────────────────────────────────────────────
def _parse_time_min(s):
    """A meeting time string ('2:00 PM', '14:00', '9 AM') → minutes since
    midnight, or None if unscheduled/unparseable."""
    s = (s or "").strip().upper().replace(".", "")
    if not s or s == "—":
        return None
    for fmt in ("%I:%M %p", "%I %p", "%H:%M"):
        try:
            t = datetime.strptime(s, fmt)
            return t.hour * 60 + t.minute
        except Exception:
            continue
    return None


def _meeting_street(m):
    """The best STREET address for a meeting: its own address override, else the
    fund's office address from the address book (SEC-sourced or manual). Returns
    '' when only a metro/city is known — i.e. no street-level location."""
    own = (m.get("address") or "").strip()
    if own:
        return own
    try:
        from core import fund_addresses
        return (fund_addresses.address_for(m.get("institution", "")) or "").strip()
    except Exception:
        return ""


def _meeting_loc(m, trip):
    """Best location string for the travel calc: the meeting's own address, then
    the fund's office address, then its stored metro, then the trip city."""
    return (_meeting_street(m)
            or (m.get("metro") or "").strip()
            or (trip.get("city") or "").strip())


def _sorted_day_meetings(meetings):
    """Meetings ordered by parsed time; unscheduled ones sink to the end keeping
    their original order (stable), so the itinerary reads chronologically."""
    keyed = [(_parse_time_min(m.get("time")), i, m) for i, m in enumerate(meetings)]
    scheduled = sorted((k for k in keyed if k[0] is not None), key=lambda x: (x[0], x[1]))
    unscheduled = [k for k in keyed if k[0] is None]
    return [m for _, _, m in scheduled] + [m for _, _, m in unscheduled]


def _travel_leg_between(prev_m, m, trip):
    """Travel estimate between two consecutive in-person stops, plus a
    feasibility read from their scheduled times. Prefers REAL routed driving
    distance/time (core.routing / OpenRouteService) and falls back to the
    offline great-circle estimate (core.geo) when there's no API key or an
    address can't be resolved. Returns (leg_dict, tight_note_or_None) or
    (None, None) when a leg can't be estimated (virtual stop or unknown city)."""
    if (prev_m.get("format", "In-person") != "In-person"
            or m.get("format", "In-person") != "In-person"):
        return None, None
    from_loc, to_loc = _meeting_loc(prev_m, trip), _meeting_loc(m, trip)
    # Real routing is only meaningful when BOTH stops have a real street address.
    # If either falls back to a metro/city label, both endpoints collapse to the
    # same city point and routing would report a misleading "0 mi · 0 min" — so
    # for those we use the offline "same city — allow ~20 min" allowance instead.
    both_have_addr = bool(_meeting_street(prev_m)) and bool(_meeting_street(m))
    lg = None
    try:
        from core import routing
        if routing.is_configured() and both_have_addr:
            # Bias geocoding toward the trip's business district so ambiguous
            # street addresses (e.g. "745 5th Ave") resolve in the right metro.
            focus = routing.focus_for(trip.get("city")) or routing.focus_for(from_loc)
            lg = routing.leg(from_loc, to_loc, focus=focus)
            if lg and lg.get("miles", 0) < 0.1:
                lg = None  # addresses collapsed to one point — not a real leg
    except Exception:
        lg = None
    if not lg:
        from core import geo
        lg = geo.leg(from_loc, to_loc)
    if not lg:
        return None, None
    tight = None
    t0, t1 = _parse_time_min(prev_m.get("time")), _parse_time_min(m.get("time"))
    if t0 is not None and t1 is not None and lg.get("drive_min") is not None:
        gap = t1 - t0
        needed = lg["drive_min"] + 30  # +30 min minimum turnaround after a meeting
        if 0 <= gap < needed:
            tight = f"TIGHT — {gap} min between starts vs ~{needed} min needed (meeting + travel)"
    return lg, tight


def _travel_total_line(total_miles, leg_count, routed_count, routing_on=False):
    """The trip-level travel summary, honestly labelled by whether the legs were
    really routed (driving) or fell back to the offline straight-line estimate."""
    if not leg_count:
        return None
    miles = f"~{total_miles:,.0f} mi"
    if routed_count == leg_count:
        return (f"Est. driving distance: {miles} across {leg_count} leg(s) — "
                "real driving miles/time, routed via OpenRouteService.")
    if routed_count:
        return (f"Est. travel: {miles} across {leg_count} leg(s) — {routed_count} routed "
                "(driving), the rest straight-line city-level (stops without a street "
                "address). Confirm with your car service.")
    # No leg routed. If the key IS set, the blocker is missing addresses, not the key.
    nudge = ("add a street address to each meeting to get routed driving miles/time"
             if routing_on else "add a maps API key in Settings for routed driving miles")
    return (f"Est. in-person travel: {miles} across {leg_count} leg(s) — straight-line, "
            f"city-level (not driving miles). To upgrade, {nudge}.")


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
    try:
        from core import routing as _routing
        _routing_on = _routing.is_configured()
    except Exception:
        _routing_on = False
    total_miles, leg_count, routed_count = 0.0, 0, 0
    for day_num in sorted(by_day.keys()):
        if len(by_day) > 1:
            lines.append(f"DAY {day_num}")
            lines.append("-" * 64)
        day_ms = _sorted_day_meetings(by_day[day_num])
        prev = None
        for m in day_ms:
            if prev is not None:
                lg, tight = _travel_leg_between(prev, m, trip)
                if lg:
                    total_miles += lg["miles"]
                    leg_count += 1
                    routed_count += 1 if lg.get("basis") == "routed" else 0
                    lines.append(f"        ↳ travel: {lg['label']}"
                                 + (f"   [!] {tight}" if tight else ""))
            tag = "Non-Holder — Priority Target" if m.get("non_holder", True) else "Existing Holder"
            time_lbl = m.get("time") or "—"
            lines.append(f"  {time_lbl:>10}   {m.get('institution','')}")
            if m.get("score") is not None:
                lines.append(f"              {m.get('format','In-person')} · {tag} · Engagement Score {m['score']}/100")
            else:
                lines.append(f"              {m.get('format','In-person')} · {tag}")
            known_c = get_institution_contacts().get(m.get("institution", ""), {})
            who = m.get("contact") or ", ".join(p for p in (known_c.get("name"), known_c.get("title")) if p)
            if who:
                lines.append(f"              Meeting with: {who}")
            if m.get("address"):
                lines.append(f"              Location: {m['address']}")
            _virtual = m.get("format", "In-person") != "In-person"
            if _virtual:
                _link = (m.get("meeting_link") or "").strip()
                lines.append(f"              Join ({m.get('format')}): {_link or 'link TBD — add on the Active NDRs tab'}")
            if m.get("notes"):
                lines.append(f"              Note: {m['notes']}")
            prev = m
    lines.append("=" * 64)
    _tl = _travel_total_line(total_miles, leg_count, routed_count, _routing_on)
    if _tl:
        lines.append(_tl)
    lines.append(f"Prepared {datetime.now().strftime('%b %d, %Y')}")
    return "\n".join(lines)


def _build_ndr_itinerary_html(trip, ticker):
    """Print-formatted itinerary — a clean, self-contained HTML document opened
    in a new window for the browser's print dialog, so the app chrome/nav isn't
    printed. Same content as the .txt export, laid out as a schedule table."""
    import html as _html

    def esc(s):
        return _html.escape(str(s))

    rows = []
    by_day = {}
    for m in trip.get("meetings", []):
        by_day.setdefault(m.get("day", 1), []).append(m)
    try:
        from core import routing as _routing
        _routing_on = _routing.is_configured()
    except Exception:
        _routing_on = False
    total_miles, leg_count, routed_count = 0.0, 0, 0
    for day_num in sorted(by_day.keys()):
        if len(by_day) > 1:
            rows.append(f'<tr><td class="day" colspan="2">Day {day_num}</td></tr>')
        prev = None
        for m in _sorted_day_meetings(by_day[day_num]):
            if prev is not None:
                lg, tight = _travel_leg_between(prev, m, trip)
                if lg:
                    total_miles += lg["miles"]
                    leg_count += 1
                    routed_count += 1 if lg.get("basis") == "routed" else 0
                    warn = (f' <span class="tight">&#9888; {esc(tight)}</span>') if tight else ""
                    rows.append(
                        f'<tr><td class="time travel">&#8627;</td>'
                        f'<td class="travel">{esc(lg["label"])}{warn}</td></tr>')
            known_c = get_institution_contacts().get(m.get("institution", ""), {})
            who = m.get("contact") or ", ".join(p for p in (known_c.get("name"), known_c.get("title")) if p)
            tag = "Non-Holder — Priority Target" if m.get("non_holder", True) else "Existing Holder"
            meta = " · ".join(x for x in [m.get("format", "In-person"), tag,
                    (f"Score {m['score']}/100" if m.get("score") is not None else "")] if x)
            _virtual = m.get("format", "In-person") != "In-person"
            _link = (m.get("meeting_link") or "").strip()
            _join = ""
            if _virtual:
                _join = (f'<b>Join ({esc(m.get("format"))}):</b> <a href="{esc(_link)}">{esc(_link)}</a>'
                         if _link else f'<b>Join ({esc(m.get("format"))}):</b> link TBD')
            det = "<br>".join(filter(None, [
                f"<b>Meeting with:</b> {esc(who)}" if who else "",
                f"<b>Location:</b> {esc(m['address'])}" if m.get("address") else "",
                _join,
                f"<b>Note:</b> {esc(m['notes'])}" if m.get("notes") else "",
            ]))
            rows.append(
                f'<tr><td class="time">{esc(m.get("time", "—"))}</td>'
                f'<td class="firm">{esc(m.get("institution", ""))}'
                f'<div class="meta">{esc(meta)}</div>'
                f'{("<div class=det>" + det + "</div>") if det else ""}</td></tr>')
            prev = m
    _tl = _travel_total_line(total_miles, leg_count, routed_count, _routing_on)
    if _tl:
        rows.append(f'<tr><td class="time travel"></td>'
                    f'<td class="travel"><b>{esc(_tl)}</b></td></tr>')

    meta_line = (f"{esc(trip.get('dates', ''))} &nbsp;·&nbsp; {esc(trip.get('city', ''))} &nbsp;·&nbsp; "
                 f"{'Virtual' if trip.get('ndr_type') == 'virtual' else 'In-Person'}")
    blocks = []
    if trip.get("sponsor_bank"):
        blocks.append(f"<div><b>Sponsoring Bank:</b> {esc(trip['sponsor_bank'])}</div>")
    blocks.append(f"<div><b>Company Attendees:</b> {esc(', '.join(trip.get('team', [])) or '—')}</div>")
    blocks.append(f"<div><b>Focus:</b> {esc(trip.get('focus', '—'))}</div>")
    if trip.get("notes"):
        blocks.append(f"<div><b>Objectives:</b> {esc(trip['notes'])}</div>")

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{esc(ticker)} NDR — {esc(trip.get('name', ''))}</title><style>"
        "body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#0F172A;margin:32px;}"
        "h1{font-size:20px;margin:0 0 2px;}.sub{color:#475569;font-size:13px;margin-bottom:12px;}"
        ".meta-block div{font-size:13px;margin:2px 0;color:#334155;}"
        "table{width:100%;border-collapse:collapse;margin-top:14px;}"
        "td{border-bottom:1px solid #E2E8F0;padding:8px 6px;vertical-align:top;font-size:13px;}"
        "td.time{white-space:nowrap;width:90px;color:#475569;font-weight:600;}"
        "td.firm{font-weight:600;}.meta{font-weight:400;color:#64748B;font-size:11px;margin-top:2px;}"
        ".det{font-weight:400;color:#334155;font-size:12px;margin-top:4px;}"
        "td.travel{border-bottom:none;color:#64748B;font-size:11px;font-style:italic;padding:2px 6px;}"
        "td.time.travel{text-align:right;color:#94A3B8;font-weight:400;}"
        ".tight{color:#B45309;font-style:normal;font-weight:600;}"
        "td.day{background:#F1F5F9;font-weight:700;font-size:12px;letter-spacing:.03em;}"
        ".foot{margin-top:18px;color:#94A3B8;font-size:11px;}"
        "@media print{body{margin:12px;}}"
        "</style></head><body>"
        f"<h1>{esc(ticker)} — Non-Deal Roadshow Itinerary</h1>"
        f"<div class='sub'>{esc(trip.get('name', ''))} &nbsp;|&nbsp; {meta_line}</div>"
        f"<div class='meta-block'>{''.join(blocks)}</div>"
        f"<table>{''.join(rows)}</table>"
        f"<div class='foot'>Prepared {datetime.now().strftime('%b %d, %Y')} · {esc(ticker)} Investor Relations</div>"
        "</body></html>"
    )


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
    # Same None-safety as the region filter: one record with Metro=None would raise
    # TypeError here and break the NDR planner.
    return sorted({(i.get("Metro") or "Unknown (SEC)") for i in institutions})


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
        candidates = [i for i in institutions if not i["USIO_Holder"] and _score_val(i) >= 40]
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


def _fmt_time_12h(t):
    """Convert a picker's 24-hour 'HH:MM' into the '2:00 PM' style the rest of
    the itinerary displays and _build_ndr_itinerary expects. Leaves anything it
    can't parse (incl. a hand-typed '2:00 PM') untouched, so the field stays
    manually editable."""
    try:
        hh, mm = t.split(":")[:2]
        h, m = int(hh), int(mm)
        ap = "AM" if h < 12 else "PM"
        return f"{h % 12 or 12}:{m:02d} {ap}"
    except Exception:
        return t


def _time_picker_input(label="Time", placeholder="e.g. 2:00 PM", value=""):
    """A text time field with an attached clock (ui.time in a popup menu). The
    field stays hand-editable — the clock just fills it — so a planner can nudge
    a time freely to absorb travel, which is the whole point of an NDR schedule.
    Returns the ui.input element (read .value)."""
    ti = ui.input(label, placeholder=placeholder, value=value).classes("flex-1")
    with ti:
        with ui.menu().props("no-parent-event") as _tmenu:
            ui.time(on_change=lambda e: ti.set_value(_fmt_time_12h(e.value)))
        with ti.add_slot("append"):
            ui.icon("schedule").on("click", _tmenu.open).classes("cursor-pointer")
    return ti


def _open_add_to_trip_dialog(idx, fund, contact, non_holder, score, default_metro, on_added):
    """Ask for a time (with a clock) before dropping an investor onto a trip,
    instead of the old silent time='—' quick-add. Captures day / time / format /
    optional address, and stashes the metro so the itinerary's travel calc can
    resolve a city even when no street address is entered yet."""
    # RIAs / wealth managers are a low-touch tier: no PM to pitch, so they get a
    # video call an assistant can set up — never management travel time. Default
    # the format to Virtual so they can't silently land on the in-person route
    # (and so they never enter the itinerary's driving-distance calc).
    try:
        from core import peer_prospects as _pp
        _is_ria_fund = _pp.is_ria(fund)
    except Exception:
        _is_ria_fund = False

    dialog = ui.dialog()
    with dialog, ui.card().style("min-width:380px;"):
        ui.label(f"Schedule {fund}").style(
            f"color:{COLORS['text_heading']};font-weight:700;font-size:15px;")
        ui.label("Pick a meeting time — flexible, adjust later for travel.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
        if _is_ria_fund:
            with ui.row().classes("items-center gap-1").style("margin-top:2px;"):
                ui.icon("videocam").style("color:#B45309;font-size:15px;")
                ui.label("RIA / wealth manager — video call tier. An assistant can set this up; "
                         "it doesn't need management travel.").style("color:#B45309;font-size:12px;")
        with ui.row().classes("w-full gap-3 items-end").style("margin-top:6px;"):
            day_in = ui.number("Day", value=1, min=1, step=1).classes("w-20")
            time_in = _time_picker_input()
            format_in = ui.select(["In-person", "Virtual", "Zoom", "Teams", "Phone", "Jitsi"],
                                  value=("Zoom" if _is_ria_fund else "In-person"),
                                  label="Format").props("dense outlined").classes("w-32")
        address_in = ui.input("Address / location (optional — powers the travel calc)",
                              placeholder=f"street, {default_metro or 'city'}").classes("w-full")
        # Virtual meetings carry a join link that flows onto the itinerary. Shown
        # only when the format isn't in-person.
        link_in = ui.input("Meeting link", placeholder="Zoom / Teams / Meet URL").classes("w-full")
        link_in.bind_visibility_from(format_in, "value", backward=lambda v: v != "In-person")

        def commit():
            trips_ = _load_json("ndr_trips.json", [])
            trips_[idx].setdefault("meetings", []).append({
                "institution": fund, "contact": contact,
                "address": (address_in.value or "").strip(), "notes": "",
                "day": int(day_in.value or 1),
                "time": (time_in.value or "").strip() or "—",
                "type": "1x1", "format": format_in.value, "status": "scheduled",
                "meeting_link": (link_in.value or "").strip(),
                "non_holder": non_holder, "score": score, "metro": default_metro or "",
            })
            _save_json("ndr_trips.json", trips_)
            _t = (time_in.value or "").strip()
            ui.notify(f"{fund} added to trip{(' at ' + _t) if _t else ' — time TBD'}.")
            dialog.close()
            on_added()

        with ui.row().classes("gap-2").style("margin-top:8px;"):
            ui.button("Add to trip", on_click=commit).props("color=primary")
            ui.button("Cancel", on_click=dialog.close).props("flat")
    dialog.open()


def _render_ndr_tab(institutions, meeting_log, client_id):
    with ui.tabs().classes("w-full") as ndr_tabs:
        nt1 = ui.tab("Plan New NDR")
        nt2 = ui.tab("Active NDRs")
        nt3 = ui.tab("Requests")
        nt4 = ui.tab("Prep Cards")
        nt5 = ui.tab("Post-NDR Debrief")
    with ui.tab_panels(ndr_tabs, value=nt1).classes("w-full"):
        with ui.tab_panel(nt1):
            ui.label("Plan a New Non-Deal Roadshow").classes("font-bold")
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    name_in = ui.input("NDR name / label", placeholder="Post-Q2 Boston NDR").classes("w-full")
                    bank_options = [f"{a['firm']} — {a['name']}" for a in CA()] + ["Other / Non-Covering Bank"]
                    sponsor_in = ui.input("Sponsoring Bank", value=bank_options[0],
                                          autocomplete=bank_options).classes("w-full")
                    # Calendar-backed date field — click the field (or the
                    # calendar icon) to pick a start/end range; the input shows
                    # a friendly "Aug 20–21, 2026" and is what save_trip stores.
                    dates_in = ui.input("Dates", placeholder="Click to pick trip dates").classes("w-full")

                    def _fmt_ndr_dates():
                        v = _dates_picker.value
                        if isinstance(v, dict) and v.get("from"):
                            a = datetime.strptime(v["from"], "%Y-%m-%d")
                            b = datetime.strptime(v["to"], "%Y-%m-%d") if v.get("to") else a
                            if a == b:
                                dates_in.value = f"{a.strftime('%b')} {a.day}, {a.year}"
                            elif a.month == b.month and a.year == b.year:
                                dates_in.value = f"{a.strftime('%b')} {a.day}–{b.day}, {a.year}"
                            else:
                                dates_in.value = f"{a.strftime('%b')} {a.day} – {b.strftime('%b')} {b.day}, {b.year}"
                        elif isinstance(v, str) and v:
                            d = datetime.strptime(v, "%Y-%m-%d")
                            dates_in.value = f"{d.strftime('%b')} {d.day}, {d.year}"

                    with dates_in:
                        with ui.menu().props("no-parent-event") as _dates_menu:
                            _dates_picker = ui.date().props("range")
                            _dates_picker.on_value_change(lambda: _fmt_ndr_dates())
                        with dates_in.add_slot("append"):
                            ui.icon("edit_calendar").on("click", _dates_menu.open).classes("cursor-pointer")
                    type_in = ui.toggle({"in_person": "In-Person", "virtual": "Virtual"}, value="in_person")
                    # Free-text city with autocomplete suggestions from the live
                    # Metro labels (same ones the NDR Requests tab and Metro
                    # Priority scoring use). A plain input guarantees manual entry
                    # always works — a QSelect's new-value-add did not reliably
                    # commit a typed city. Typing a metro that isn't tracked yet
                    # just yields no auto-suggested targets.
                    city_in = ui.input("City / Region", placeholder="Type a city, or pick a tracked metro",
                                       autocomplete=_ndr_location_options(institutions)).classes("w-full")
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
            ).style(f"color:{COLORS['text_muted']};font-size:12px;")
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
                            ui.label(f"Last time in {location}: {prior.get('dates','—')} — \"{prior.get('name','')}\" "
                                      f"({len(prior.get('meetings', []))} meeting(s) scheduled).").style(
                                f"color:{COLORS['text_muted']};font-size:12px;margin-bottom:4px;")
                        else:
                            ui.label(f"No prior NDR trip on file to {location} — this would be a first visit.").style(
                                f"color:{COLORS['text_muted']};font-size:12px;margin-bottom:4px;")
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
                        f"color:{COLORS['text_muted']};font-size:12px;margin-bottom:6px;")
                    with ui.row().classes("w-full gap-3"):
                        col_a = ui.column().classes("flex-1 gap-2")
                        col_b = ui.column().classes("flex-1 gap-2")
                    cols = [col_a, col_b]
                    for idx, inst in enumerate(candidates):
                        default_check = idx < max_auto and not inst["USIO_Holder"]
                        days_since = _days_since_last_contact(inst["Fund"], meeting_log)
                        border_clr = "#15803D" if _score_val(inst) >= 80 else "#B45309" if _score_val(inst) >= 50 else "#94A3B8"
                        with cols[idx % 2]:
                            with ui.row().classes("w-full items-start gap-2").style(
                                    f"background:{COLORS['surface_hover_bg']};border-left:3px solid {border_clr};"
                                    f"border-radius:8px;padding:8px 10px;"):
                                cb = ui.checkbox(value=default_check)
                                with ui.column().classes("gap-0"):
                                    with ui.row().classes("items-center gap-2"):
                                        ui.label(pretty_name(inst["Fund"])).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                                        ui.label(str(inst["Engagement_Score"])).style(
                                            f"background:{border_clr}22;color:{border_clr};font-size:11px;font-weight:700;"
                                            f"padding:1px 6px;border-radius:6px;")
                                    ui.label(f"{inst['Metro']} · {'Holder' if inst['USIO_Holder'] else 'Non-holder'} · {inst.get('Type','—')}").style(
                                        f"color:{COLORS['text_muted']};font-size:11px;")
                                    ui.label(f"Contacted {days_since}d ago" if days_since is not None else "No prior contact logged").style(
                                        f"color:{COLORS['text_muted']};font-size:11px;")
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
                ui.notify(f"NDR '{name_in.value}' created — {len(selected)} meeting(s) "
                          f"({n_non} non-holders, {len(selected) - n_non} holders) across {days} day(s). "
                          "Now showing under Active NDRs.")
                # Refresh just the Active NDRs list and switch to it, instead of
                # a full page reload that bounced the user back to Buy-Side
                # Intelligence (the "I created it but where did it go?" problem).
                _active_ndrs_panel.refresh()
                ndr_tabs.set_value(nt2)

            ui.button("Create NDR Trip", on_click=save_trip).props("color=primary").style("margin-top:8px;")

        @ui.refreshable
        def _active_ndrs_panel():
            trips = _load_json("ndr_trips.json", [])
            if not trips:
                ui.label("No NDR trips logged yet.").style(f"color:{COLORS['text_muted']};")
            status_options = ["scheduled", "completed", "cancelled", "no-show"]

            # ── Shortlist status transitions (NDR pipeline Phase 2) ──────────────
            def _sl_set(ti, si, new_status):
                trips_ = _load_json("ndr_trips.json", [])
                try:
                    entry = trips_[ti]["shortlist"][si]
                except (IndexError, KeyError):
                    _active_ndrs_panel.refresh(); return
                entry["status"] = new_status
                stamp = {"invited": "contacted_at", "confirmed": "confirmed_at",
                         "declined": "declined_at"}.get(new_status)
                if stamp:
                    entry[stamp] = datetime.now().strftime("%Y-%m-%d %H:%M")
                _save_json("ndr_trips.json", trips_)
                try:
                    from core import activity_log
                    ev = {"invited": "ndr_outreach", "confirmed": "ndr_confirmed",
                          "declined": "ndr_declined"}.get(new_status, "ndr_update")
                    activity_log.log_event(ev, entity=entry.get("institution", ""),
                                           launched_from=f"NDR · {trips_[ti].get('name', '')}")
                except Exception:
                    pass
                _active_ndrs_panel.refresh()

            def _sl_contact(ti, si, entry):
                contact = get_institution_contacts().get(entry.get("institution", ""), {})
                _open_shortlist_outreach(entry, contact, lambda: _sl_set(ti, si, "invited"))

            # Confirm → move the target out of the pipeline and into the schedule at the next open
            # slot (NDR pipeline Phase 3). This is the "slot on confirmation" rule: only confirmed
            # targets take calendar capacity; declines never do.
            def _sl_confirm_and_slot(ti, si):
                trips_ = _load_json("ndr_trips.json", [])
                try:
                    trip_ = trips_[ti]
                    entry = trip_["shortlist"][si]
                except (IndexError, KeyError):
                    _active_ndrs_panel.refresh(); return
                day, slot = _next_open_slot(trip_)
                if day is None:
                    ui.notify("This NDR's slots are full — raise its days or meetings/day to schedule more.",
                              type="warning")
                    return
                trip_.setdefault("meetings", []).append({
                    "institution": entry.get("institution"), "day": day, "slot_index": slot,
                    "time": _slot_time(slot), "type": "1x1", "format": "In-person", "status": "scheduled",
                    "notes": entry.get("peers", ""), "non_holder": True, "score": entry.get("conviction"),
                    "contact": "", "confirmed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "source": entry.get("source", "outbound"),
                })
                del trip_["shortlist"][si]
                _save_json("ndr_trips.json", trips_)
                try:
                    from core import activity_log
                    activity_log.log_event("ndr_confirmed", entity=entry.get("institution", ""),
                                           launched_from=f"NDR · {trip_.get('name', '')}")
                except Exception:
                    pass
                ui.notify(f"{pretty_name(entry.get('institution', ''))} confirmed → Day {day} · {_slot_time(slot)}.",
                          type="positive")
                _active_ndrs_panel.refresh()

            def _set_capacity(ti, field, value):
                # Persist silently (no refresh) so the number input keeps focus while you type.
                trips_ = _load_json("ndr_trips.json", [])
                try:
                    trips_[ti][field] = max(1, int(value or 1))
                except (IndexError, ValueError, TypeError):
                    return
                _save_json("ndr_trips.json", trips_)

            for idx, trip in enumerate(trips):
                all_meetings = trip.get("meetings", [])
                real_meetings = [m for m in all_meetings if m.get("type") != "break"]
                done_m = sum(1 for m in real_meetings if m.get("status") == "completed")
                non_h = sum(1 for m in real_meetings if m.get("non_holder", True))
                trip_status = trip.get("status", "Planning")
                status_icon = {"Planning": "", "In Progress": "", "Completed": ""}.get(trip_status, "")
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
                                _active_ndrs_panel.refresh()

                            ui.select(["Planning", "In Progress", "Completed"], value=trip_status,
                                      on_change=set_trip_status).props("dense outlined").classes("min-w-[130px]")

                    # Capacity grid (NDR pipeline Phase 3) — days × meetings/day. Confirmed targets
                    # fill it in order. Editable inline; persists silently to keep input focus.
                    _cap_d, _cap_p = _ndr_capacity(trip)
                    _filled = len([m for m in all_meetings if m.get("type") != "break"])
                    with ui.row().classes("w-full items-center gap-2").style("margin-top:4px;"):
                        ui.label("Capacity").style(f"color:{COLORS['text_muted']};font-size:11px;")
                        ui.number(value=_cap_d, min=1, max=10,
                                  on_change=lambda e, ti=idx: _set_capacity(ti, "days", e.value)).props("dense outlined").style("width:66px;").tooltip("Days")
                        ui.label("days ×").style(f"color:{COLORS['text_muted']};font-size:11px;")
                        ui.number(value=_cap_p, min=1, max=12,
                                  on_change=lambda e, ti=idx: _set_capacity(ti, "slots_per_day", e.value)).props("dense outlined").style("width:66px;").tooltip("Meetings per day")
                        ui.label(f"/day  ·  {_filled} of {_cap_d * _cap_p} slots filled").style(
                            f"color:{COLORS['text_muted']};font-size:11px;")

                    # NDR pipeline (Phase 2) — shortlisted → invited → confirmed → declined.
                    # Held in trip['shortlist'], separate from the slot schedule below (Phase 3
                    # moves a confirmed target into meetings[] with a slot).
                    shortlist = trip.get("shortlist", [])
                    if shortlist:
                        _counts = {}
                        for s in shortlist:
                            k = s.get("status", "shortlisted")
                            _counts[k] = _counts.get(k, 0) + 1
                        _order = ["shortlisted", "invited", "confirmed", "declined"]
                        _summ = " · ".join(f"{_counts[k]} {k}" for k in _order if _counts.get(k))
                        _badge = {"shortlisted": ("#64748B", "Shortlisted"), "invited": ("#B45309", "Invited"),
                                  "confirmed": ("#15803D", "Confirmed"), "declined": ("#94A3B8", "Declined")}
                        with ui.expansion(f"NDR pipeline — {len(shortlist)} target(s) · {_summ}",
                                          icon="filter_alt").classes("w-full").style("margin-top:6px;"):
                            for si, s in enumerate(shortlist):
                                st = s.get("status", "shortlisted")
                                clr, lbl = _badge.get(st, ("#64748B", st.title()))
                                with ui.row().classes("w-full items-center gap-2").style(
                                        f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:4px 8px;"
                                        f"margin:2px 0;{'opacity:.55;' if st == 'declined' else ''}"):
                                    ui.label(lbl).style(f"background:{clr}22;color:{clr};border-radius:6px;"
                                                        "padding:1px 8px;font-size:10px;font-weight:700;white-space:nowrap;")
                                    ui.label(pretty_name(s.get("institution", ""))).classes("flex-1").style(
                                        f"color:{COLORS['text_body']};font-size:13px;")
                                    _sl_loc = ", ".join(x for x in [s.get("city"), s.get("state")] if x) or s.get("metro", "—")
                                    ui.label(_sl_loc).style(f"color:{COLORS['text_muted']};font-size:11px;")
                                    if s.get("conviction") is not None:
                                        ui.label(f"{s['conviction']}/100").style(f"color:{COLORS['text_muted']};font-size:11px;")
                                    # Per-status actions
                                    if st == "shortlisted":
                                        ui.button("Contact", icon="mail",
                                                  on_click=lambda ti=idx, si=si, e=s: _sl_contact(ti, si, e)).props("flat dense size=sm color=primary")
                                        ui.button("Decline", on_click=lambda ti=idx, si=si: _sl_set(ti, si, "declined")).props("flat dense size=sm")
                                    elif st == "invited":
                                        ui.button("Confirm & slot", icon="event_available",
                                                  on_click=lambda ti=idx, si=si: _sl_confirm_and_slot(ti, si)).props("flat dense size=sm color=positive")
                                        ui.button("Re-contact", on_click=lambda ti=idx, si=si, e=s: _sl_contact(ti, si, e)).props("flat dense size=sm")
                                        ui.button("Decline", on_click=lambda ti=idx, si=si: _sl_set(ti, si, "declined")).props("flat dense size=sm")
                                    elif st == "confirmed":
                                        # Legacy Phase-2 confirmed (still in the pipeline) — slot it now.
                                        ui.button("Slot now", icon="event_available",
                                                  on_click=lambda ti=idx, si=si: _sl_confirm_and_slot(ti, si)).props("flat dense size=sm color=positive")
                                        ui.button("Undo", on_click=lambda ti=idx, si=si: _sl_set(ti, si, "invited")).props("flat dense size=sm")
                                    elif st == "declined":
                                        ui.button("Restore", on_click=lambda ti=idx, si=si: _sl_set(ti, si, "shortlisted")).props("flat dense size=sm")
                            ui.label("Contact opens a draft you send yourself and marks the target Invited (logged). "
                                     "Confirm → automatic slot assignment arrives in Phase 3.").style(
                                f"color:{COLORS['text_muted']};font-size:10.5px;margin-top:4px;")

                    meetings_with_idx = sorted(enumerate(all_meetings), key=lambda x: (x[1].get("day", 1), x[0]))
                    current_day = None
                    for flat_idx, m in meetings_with_idx:
                        d = m.get("day", 1)
                        if d != current_day:
                            current_day = d
                            ui.label(f"Day {d}" if len(meetings_with_idx) and any(mm.get("day", 1) != 1 for _, mm in meetings_with_idx) else "Meetings").style(
                                f"color:{COLORS['text_muted']};font-size:11px;font-weight:700;margin-top:8px;")
                        nh_badge = "" if m.get("non_holder", True) else ""
                        fmt_badge = "" if m.get("format") in ("Zoom", "Teams") else ""
                        with ui.row().classes("w-full items-center gap-2").style(
                                f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:4px 8px;margin:2px 0;"):
                            ui.label(f"{fmt_badge} {m.get('time','—')}").style(f"color:{COLORS['text_muted']};font-size:12px;width:110px;")
                            with ui.row().classes("flex-1 items-center gap-1").style("min-width:0;"):
                                ui.label(f"{nh_badge} {pretty_name(m.get('institution',''))}").style(f"color:{COLORS['text_body']};font-size:13px;")
                                if m.get("source") == "inbound":
                                    ui.label("inbound").style("background:#B4530922;color:#B45309;border-radius:6px;"
                                                              "padding:0 6px;font-size:9.5px;font-weight:700;")
                            if m.get("score") is not None:
                                ui.label(f"{m['score']}/100").style(f"color:{COLORS['text_muted']};font-size:11px;")

                            def set_meeting_status(e, idx=idx, flat_idx=flat_idx):
                                trips_ = _load_json("ndr_trips.json", [])
                                trips_[idx]["meetings"][flat_idx]["status"] = e.value
                                _save_json("ndr_trips.json", trips_)
                                _active_ndrs_panel.refresh()

                            ui.select(status_options, value=m.get("status", "scheduled"),
                                      on_change=set_meeting_status).props("dense outlined").classes("min-w-[110px]")

                            # Call / email the contact at this institution —
                            # to reschedule or send materials. Uses the known
                            # institution contact; each icon only appears when
                            # we actually have that number/email on file (a
                            # hand-added firm with no contact shows neither).
                            _mc = get_institution_contacts().get(m.get("institution", ""), {})
                            if _mc.get("phone"):
                                with ui.link(target=_tel_href(_mc["phone"])).tooltip(
                                        f"Call {_mc.get('name', '')} · {_mc['phone']}"):
                                    ui.icon("call").style(f"color:{COLORS['accent_light']};font-size:18px;")
                            if _mc.get("email"):
                                _first = _mc.get("name", "").split()[0] if _mc.get("name") else ""
                                _slot = f" for our {m.get('time')} slot" if m.get("time") and m.get("time") != "—" else ""
                                _subj = f"{CT('ticker')} — {m.get('institution', '')} meeting during {trip.get('city', '')} NDR"
                                _bodym = (f"Hi {_first},\n\nLooking forward to our meeting during the "
                                          f"{trip.get('city', '')} NDR ({trip.get('dates', '')}). I wanted to confirm "
                                          f"logistics{_slot} and share some materials ahead of time.\n\n")
                                _href = f"mailto:{_mc['email']}?subject={quote(_subj)}&body={quote(_bodym)}"
                                with ui.link(target=_href).tooltip(f"Email {_mc.get('name', '')} · {_mc['email']}"):
                                    ui.icon("mail").style(f"color:{COLORS['accent_light']};font-size:18px;")

                            # Per-meeting remove — confirmed, since it's
                            # destructive and there's no undo. flat_idx is the
                            # index into the trip's own meetings list, so the
                            # delete lands on the right row even though the
                            # display is re-sorted by day.
                            _m_name = m.get("institution") or "this meeting"
                            with ui.dialog() as _del_dialog, ui.card():
                                ui.label(f"Remove {_m_name} from this trip?").classes("font-bold")
                                ui.label("This can't be undone.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                                with ui.row().classes("justify-end w-full"):
                                    ui.button("Cancel", on_click=_del_dialog.close).props("flat dense")

                                    def do_remove(idx=idx, flat_idx=flat_idx, name=_m_name, dlg=_del_dialog):
                                        trips_ = _load_json("ndr_trips.json", [])
                                        try:
                                            del trips_[idx]["meetings"][flat_idx]
                                        except (IndexError, KeyError):
                                            dlg.close()
                                            ui.notify("List changed — reloading.", type="warning")
                                            _active_ndrs_panel.refresh()
                                            return
                                        _save_json("ndr_trips.json", trips_)
                                        dlg.close()
                                        ui.notify(f"Removed {name} from trip.")
                                        _active_ndrs_panel.refresh()

                                    ui.button("Remove", on_click=do_remove).props("color=negative dense")

                            # Edit meeting — set/adjust time, format, address, and
                            # (for a virtual meeting) the join link that flows to
                            # the itinerary. The key path for making a stop virtual
                            # and pushing its link to the schedule.
                            with ui.dialog() as _edit_dialog, ui.card().classes("w-96"):
                                ui.label(f"Edit — {_m_name}").classes("font-bold").style(f"color:{COLORS['text_heading']};")
                                with ui.row().classes("w-full gap-3 items-end"):
                                    _e_time = ui.input("Time", value=m.get("time", "")).classes("flex-1")
                                    with _e_time:
                                        with ui.menu().props("no-parent-event") as _etmenu:
                                            ui.time(on_change=lambda e, ti=_e_time: ti.set_value(_fmt_time_12h(e.value)))
                                        with _e_time.add_slot("append"):
                                            ui.icon("schedule").on("click", _etmenu.open).classes("cursor-pointer")
                                    _e_fmt = ui.select(["In-person", "Virtual", "Zoom", "Teams", "Phone", "Jitsi"],
                                                       value=m.get("format", "In-person"),
                                                       label="Format").props("dense outlined").classes("w-32")
                                _e_addr = ui.input("Address / location", value=m.get("address", "")).classes("w-full")
                                _e_link = ui.input("Meeting link", value=m.get("meeting_link", ""),
                                                   placeholder="Zoom / Teams / Meet URL").classes("w-full")
                                _e_link.bind_visibility_from(_e_fmt, "value", backward=lambda v: v != "In-person")

                                async def create_zoom(idx=idx, flat_idx=flat_idx, trip=trip, m=m,
                                                      e_time=_e_time, e_link=_e_link, dlg=_edit_dialog):
                                    import asyncio
                                    from zoneinfo import ZoneInfo
                                    from core import ndr_calendar, zoom_meetings
                                    if not zoom_meetings.is_configured():
                                        ui.notify("Add Zoom credentials in Settings → Data Sources first.", type="warning")
                                        return
                                    m_now = dict(m); m_now["time"] = (e_time.value or "").strip()
                                    local = ndr_calendar.meeting_datetime(trip, m_now)
                                    start_utc = local.astimezone(ZoneInfo("UTC")) if local else None
                                    tzname = ndr_calendar.tz_name_for(trip.get("city"))
                                    topic = f"{CT('ticker')} NDR — {m.get('institution', '')}"
                                    ui.notify("Creating Zoom meeting…")
                                    try:
                                        res = await asyncio.to_thread(
                                            zoom_meetings.create_meeting, topic, start_utc, 45, tzname)
                                    except Exception as ex:
                                        ui.notify(f"Zoom create failed: {ex}", type="negative")
                                        return
                                    link = res.get("join_url") or ""
                                    e_link.value = link
                                    # Persist immediately so a created Zoom meeting is never orphaned.
                                    trips_ = _load_json("ndr_trips.json", [])
                                    try:
                                        mm = trips_[idx]["meetings"][flat_idx]
                                    except (IndexError, KeyError):
                                        ui.notify("List changed — reloading.", type="warning")
                                        dlg.close(); _active_ndrs_panel.refresh(); return
                                    mm["format"] = "Zoom"; mm["meeting_link"] = link
                                    mm["zoom_meeting_id"] = str(res.get("id") or "")
                                    _save_json("ndr_trips.json", trips_)
                                    ui.notify("Zoom meeting created — join link added to the schedule.", type="positive")

                                _zoom_btn = ui.button("Create Zoom meeting", icon="videocam",
                                                      on_click=create_zoom).props("outline dense color=primary")
                                _zoom_btn.bind_visibility_from(_e_fmt, "value", backward=lambda v: v == "Zoom")

                                def create_jitsi(idx=idx, flat_idx=flat_idx, m=m, e_link=_e_link, dlg=_edit_dialog):
                                    from core import jitsi_meetings
                                    link = jitsi_meetings.create_link(f"{CT('ticker')} NDR {m.get('institution', '')}")
                                    e_link.value = link
                                    trips_ = _load_json("ndr_trips.json", [])
                                    try:
                                        mm = trips_[idx]["meetings"][flat_idx]
                                    except (IndexError, KeyError):
                                        ui.notify("List changed — reloading.", type="warning")
                                        dlg.close(); _active_ndrs_panel.refresh(); return
                                    mm["format"] = "Jitsi"; mm["meeting_link"] = link
                                    _save_json("ndr_trips.json", trips_)
                                    ui.notify("Jitsi link generated — added to the schedule.", type="positive")

                                _jitsi_btn = ui.button("Generate Jitsi link", icon="link",
                                                       on_click=create_jitsi).props("outline dense color=primary")
                                _jitsi_btn.bind_visibility_from(_e_fmt, "value", backward=lambda v: v == "Jitsi")
                                with ui.row().classes("justify-end w-full"):
                                    ui.button("Cancel", on_click=_edit_dialog.close).props("flat dense")

                                    def do_edit(idx=idx, flat_idx=flat_idx, dlg=_edit_dialog,
                                                e_time=_e_time, e_fmt=_e_fmt, e_addr=_e_addr, e_link=_e_link):
                                        trips_ = _load_json("ndr_trips.json", [])
                                        try:
                                            mm = trips_[idx]["meetings"][flat_idx]
                                        except (IndexError, KeyError):
                                            dlg.close(); ui.notify("List changed — reloading.", type="warning")
                                            _active_ndrs_panel.refresh(); return
                                        mm["time"] = (e_time.value or "").strip() or "—"
                                        mm["format"] = e_fmt.value
                                        mm["address"] = (e_addr.value or "").strip()
                                        mm["meeting_link"] = (e_link.value or "").strip() if e_fmt.value != "In-person" else ""
                                        _save_json("ndr_trips.json", trips_)
                                        dlg.close()
                                        ui.notify("Meeting updated.")
                                        _active_ndrs_panel.refresh()

                                    ui.button("Save", on_click=do_edit).props("color=primary dense")

                            ui.button(icon="edit", on_click=_edit_dialog.open).props(
                                "flat dense round size=sm color=grey-7").tooltip("Edit meeting")
                            ui.button(icon="close", on_click=_del_dialog.open).props(
                                "flat dense round size=sm color=grey-7").tooltip("Remove meeting")
                        # Who they're meeting at the firm — the meeting's own
                        # contact if set, else fall back to the known
                        # institution contact so seeded meetings still show a
                        # name instead of a blank.
                        _known_c = get_institution_contacts().get(m.get("institution", ""), {})
                        _who = m.get("contact") or (
                            ", ".join(p for p in (_known_c.get("name"), _known_c.get("title")) if p))
                        if _who:
                            ui.label(f"   Meeting with: {_who}").style(f"color:{COLORS['text_muted']};font-size:11px;margin-left:6px;")
                        if m.get("address"):
                            ui.label(f"   Location: {m['address']}").style(f"color:{COLORS['text_muted']};font-size:11px;margin-left:6px;")
                        if m.get("format", "In-person") != "In-person":
                            _lk = (m.get("meeting_link") or "").strip()
                            if _lk:
                                with ui.row().classes("items-center gap-1").style("margin-left:6px;"):
                                    ui.label(f"   Join ({m.get('format')}):").style(f"color:{COLORS['text_muted']};font-size:11px;")
                                    with ui.link(target=_lk, new_tab=True):
                                        ui.label(_lk[:48] + ("…" if len(_lk) > 48 else "")).style(f"color:{COLORS['accent_light']};font-size:11px;")
                            else:
                                ui.label(f"   {m.get('format')} · link TBD — click ✎ to add").style(
                                    f"color:#B45309;font-size:11px;margin-left:6px;")
                        if m.get("notes"):
                            ui.label(f"   {m['notes']}").style(f"color:{COLORS['text_muted']};font-size:11px;margin-left:6px;")

                    # Filler-meeting finder — a light day (like 3 meetings)
                    # is the IR person's cue to fill open slots. Rather than
                    # hunting around, surface tracked funds in this trip's metro
                    # that aren't already scheduled, ranked by engagement score
                    # (non-holders first — the conversion targets), each with
                    # one-click Call / Email / Add-to-trip. Same targeting
                    # engine as Plan New NDR.
                    _scheduled = {mm.get("institution") for mm in all_meetings}
                    _all_cands = [c for c in _ndr_target_candidates(
                                      institutions, trip.get("city"), trip.get("ndr_type", "in-person"))
                                  if c["Fund"] not in _scheduled]
                    _fillers = _all_cands[:6]
                    if _fillers:
                        with ui.expansion(
                                f"Fill open slots — {len(_all_cands)} available targets in {trip.get('city', 'this metro')}",
                                value=len(real_meetings) < 4).classes("w-full").style("margin-top:6px;"):
                            _n_non = sum(1 for c in _all_cands if not c.get("USIO_Holder", False))
                            _more = f" Showing the top {len(_fillers)}." if len(_all_cands) > len(_fillers) else ""
                            ui.label(f"Tracked funds in this metro you're not already meeting, ranked by engagement "
                                     f"score — non-holders first ({_n_non} non-holder{'s' if _n_non != 1 else ''}, "
                                     f"{len(_all_cands) - _n_non} holder{'s' if (len(_all_cands) - _n_non) != 1 else ''}). "
                                     f"Call or email to invite, then add them to the trip.{_more}").style(
                                f"color:{COLORS['text_muted']};font-size:11px;")
                            for c in _fillers:
                                cc = get_institution_contacts().get(c["Fund"], {})
                                with ui.row().classes("w-full items-center gap-2").style(
                                        f"background:{COLORS['surface_hover_bg']};border-radius:6px;padding:4px 8px;margin:2px 0;"):
                                    ui.label(str(c["Engagement_Score"])).style(
                                        f"color:{COLORS['accent_light']};font-size:12px;font-weight:700;width:34px;")
                                    with ui.column().classes("gap-0 flex-1"):
                                        ui.label(c["Fund"]).style(f"color:{COLORS['text_body']};font-size:13px;font-weight:600;")
                                        _bits = [c.get("Metro"), c.get("Type")]
                                        if cc.get("name"):
                                            _bits.append(f"{cc['name']} ({cc.get('title', '')})")
                                        _bits.append(cc.get("phone") or "no contact on file")
                                        ui.label(" · ".join(x for x in _bits if x)).style(
                                            f"color:{COLORS['text_muted']};font-size:11px;")
                                    if cc.get("phone"):
                                        ui.link("Call", _tel_href(cc["phone"])).style(
                                            f"color:{COLORS['accent_light']};font-size:12px;")
                                    if cc.get("email"):
                                        _first = cc.get("name", "").split()[0] if cc.get("name") else ""
                                        _mailto(cc["email"],
                                                f"{CT('ticker')} — meeting during {trip.get('city', '')} NDR?",
                                                f"Hi {_first},\n\nWe'll be in {trip.get('city', '')} for a non-deal "
                                                f"roadshow ({trip.get('dates', '')}). Would you have time to meet with "
                                                f"{CT('name')} management? Happy to work around your schedule.\n\n",
                                                "Email")

                                    def add_filler(c=c, cc=cc, idx=idx):
                                        _open_add_to_trip_dialog(
                                            idx, c["Fund"],
                                            ", ".join(p for p in (cc.get("name"), cc.get("title")) if p),
                                            not c.get("USIO_Holder", False),
                                            c.get("Engagement_Score"), c.get("Metro"),
                                            _active_ndrs_panel.refresh)

                                    ui.button("Add to trip", on_click=add_filler).props("flat dense color=primary")

                    with ui.expansion("Add a meeting to this trip by hand").classes("w-full").style("margin-top:6px;"):
                        with ui.row().classes("w-full gap-4"):
                            inst_in = ui.input("Institution *").classes("flex-1")
                            contact_in = ui.input(
                                "Who you're meeting (name / title)",
                                placeholder="e.g. Jane Smith, PM; John Doe, Analyst").classes("flex-1")
                        with ui.row().classes("w-full gap-4"):
                            address_in = ui.input(
                                "Address / location",
                                placeholder="e.g. 55 E 52nd St, 12th Fl, New York, NY").classes("flex-1")
                        with ui.row().classes("w-full gap-4 items-end"):
                            day_in = ui.number("Day", value=1, min=1, step=1).classes("w-20")
                            time_in = ui.input("Time", placeholder="e.g. 2:00 PM").classes("flex-1")
                            with time_in:
                                with ui.menu().props("no-parent-event") as _tmenu:
                                    ui.time(on_change=lambda e, ti=time_in: ti.set_value(_fmt_time_12h(e.value)))
                                with time_in.add_slot("append"):
                                    ui.icon("schedule").on("click", _tmenu.open).classes("cursor-pointer")
                            type_in = ui.select(["1x1", "Group", "Fireside", "Call"], value="1x1",
                                                label="Type").props("dense outlined").classes("w-32")
                            format_in = ui.select(["In-person", "Virtual", "Zoom", "Teams", "Phone", "Jitsi"], value="In-person",
                                                  label="Format").props("dense outlined").classes("w-32")
                        with ui.row().classes("w-full gap-4 items-end"):
                            holder_in = ui.select(["Non-holder", "Holder"], value="Non-holder",
                                                  label="Holder status").props("dense outlined").classes("w-40")
                            notes_m = ui.input("Notes").classes("flex-1")
                        link_m = ui.input("Meeting link (virtual)",
                                          placeholder="Zoom / Teams / Meet URL").classes("w-full")
                        link_m.bind_visibility_from(format_in, "value", backward=lambda v: v != "In-person")

                        def add_meeting(idx=idx, inst_in=inst_in, contact_in=contact_in, address_in=address_in,
                                        day_in=day_in, time_in=time_in, type_in=type_in, format_in=format_in,
                                        holder_in=holder_in, notes_m=notes_m, link_m=link_m):
                            if not (inst_in.value or "").strip():
                                ui.notify("Institution is required.", type="warning")
                                return
                            trips_ = _load_json("ndr_trips.json", [])
                            trips_[idx].setdefault("meetings", []).append({
                                "institution": inst_in.value.strip(),
                                "contact": (contact_in.value or "").strip(),
                                "address": (address_in.value or "").strip(),
                                "notes": notes_m.value,
                                "day": int(day_in.value or 1),
                                "time": (time_in.value or "").strip() or "—",
                                "type": type_in.value, "format": format_in.value, "status": "scheduled",
                                "meeting_link": (link_m.value or "").strip(),
                                "non_holder": holder_in.value == "Non-holder", "score": None,
                                "metro": trip.get("city", ""),
                            })
                            _save_json("ndr_trips.json", trips_)
                            ui.notify(f"{inst_in.value.strip()} added to trip.")
                            _active_ndrs_panel.refresh()

                        ui.button("Add", on_click=add_meeting).props("dense")

                    def download_itinerary(trip=trip):
                        ui.download(_build_ndr_itinerary(trip, CT("ticker")).encode(), filename=f"{trip['name'].replace(' ','_')}_itinerary.txt")

                    def download_calendar(trip=trip):
                        from core import fund_addresses, ndr_calendar
                        ics = ndr_calendar.build_ics(
                            trip, CT("ticker"),
                            contacts=get_institution_contacts(),
                            address_for=fund_addresses.address_for)
                        ui.download(ics.encode(),
                                    filename=f"{trip['name'].replace(' ','_')}.ics")
                        ui.notify("Calendar file downloaded — open it to add every meeting "
                                  "(with join links) to your calendar.")

                    def print_itinerary(trip=trip):
                        # Open the print-formatted itinerary in a new window and
                        # trigger the browser print dialog, so app nav isn't
                        # printed. Pop-up-blocked case falls back to an alert.
                        doc = _build_ndr_itinerary_html(trip, CT("ticker"))
                        ui.run_javascript(
                            "const w=window.open('','_blank');"
                            "if(w){"
                            f"w.document.write({json.dumps(doc)});"
                            "w.document.close();w.focus();setTimeout(()=>w.print(),350);"
                            "}else{alert('Please allow pop-ups to print the itinerary.');}"
                        )

                    def email_itinerary(trip=trip):
                        # Opens the user's own mail client (mailto) with the
                        # itinerary pre-filled — no recipient, they choose who.
                        href = (f"mailto:?subject={quote(CT('ticker') + ' NDR Itinerary — ' + trip['name'])}"
                                f"&body={quote(_build_ndr_itinerary(trip, CT('ticker')))}")
                        ui.run_javascript(f"window.location.href={json.dumps(href)};")

                    with ui.row().classes("gap-2 items-center").style("margin-top:6px;"):
                        ui.button("Export itinerary (.txt)", on_click=download_itinerary).props("flat dense")
                        ui.button("Add to calendar (.ics)", icon="event", on_click=download_calendar).props("flat dense")
                        ui.button("Print", icon="print", on_click=print_itinerary).props("flat dense")
                        ui.button("Email", icon="mail", on_click=email_itinerary).props("flat dense")

        with ui.tab_panel(nt2):
            _active_ndrs_panel()

        with ui.tab_panel(nt3):
            _render_ndr_requests_tab()

        with ui.tab_panel(nt4):
            _render_ndr_prep_cards_tab(institutions, meeting_log)

        with ui.tab_panel(nt5):
            _render_ndr_debrief_tab()


def _render_ndr_requests_tab():
    ui.label("Inbound NDR / Meeting Requests").classes("font-bold")
    ui.label(
        "Analyst requests to slot a management meeting into a city — feeds the Big Picture panel's Metro "
        "Priority scoring and 'This Week's Priority' recommendation above. Resolve a request once it's been "
        "scheduled (or declined) so it stops counting as open demand."
    ).style(f"color:{COLORS['text_muted']};font-size:12px;")

    with ui.expansion("Log a new request", value=False).classes("w-full"):
        with ui.row().classes("w-full gap-4"):
            r_analyst = ui.input("Analyst name *").classes("flex-1")
            bank_options = [a["firm"] for a in CA()] + ["Other / Non-Covering Bank"]
            r_firm = ui.input("Firm", value=bank_options[0], autocomplete=bank_options).classes("flex-1")
        with ui.row().classes("w-full gap-4"):
            r_city = ui.input("City *").classes("flex-1")
            r_metro = ui.input("Metro region",
                               autocomplete=sorted({i["Metro"] for i in get_seed_buyside_institutions(get_active_client_id())})).classes("flex-1")
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

        ui.button("Log Request", on_click=log_request).props("color=primary")

    ui.markdown("---")
    reqs = _load_ndr_requests()
    open_reqs = [r for r in reqs if not r.get("resolved")]
    resolved_reqs = [r for r in reqs if r.get("resolved")]

    ui.label(f"{len(open_reqs)} open request(s)").classes("font-bold")
    if not open_reqs:
        ui.label("No open requests.").style(f"color:{COLORS['text_muted']};")
    for r in open_reqs:
        seed_tag = " · example" if r.get("seeded") else ""
        with ui.expansion(f"{r['analyst']} ({r['firm']}) → {r['city']}{seed_tag}",
                          caption=f"Received {r['received']}").classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;"):
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

            with ui.row().classes("gap-2").style("margin-top:6px;"):
                ui.button("Schedule into NDR", icon="event_available",
                          on_click=lambda r=r: _open_schedule_request_dialog(r, _refresh)).props("flat dense color=primary")
                ui.button("Resolve without scheduling", on_click=mark_resolved).props("flat dense")

    if resolved_reqs:
        with ui.expansion(f"{len(resolved_reqs)} resolved").classes("w-full").style("margin-top:8px;"):
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

    ui.label("Meeting Prep Cards").classes("font-bold")
    ui.label("Pick a trip to generate a prep card per meeting — pulled live from tracked institution data.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

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
                # Collapsed to a scannable agenda line (time — institution,
                # with holder status + score in the caption); expand a meeting
                # to see last-contact, strategy note, and talking points.
                if inst:
                    holder_tag = "Existing holder" if inst["USIO_Holder"] else "Non-holder"
                    caption = f"{inst.get('Metro','—')} · {inst.get('Type','—')} · {holder_tag} · score {inst['Engagement_Score']}/100"
                else:
                    caption = "Not in tracked institution list — added by hand"
                with ui.expansion(f"{m.get('time','—')} — {m.get('institution','—')}", caption=caption).classes("w-full").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;"):
                    days_since = _days_since_last_contact(m.get("institution", ""), meeting_log) if inst else None
                    if days_since is not None:
                        ui.label(f"Last contact: {days_since} day(s) ago").style(f"color:{COLORS['text_muted']};font-size:12px;")

                    if m.get("notes"):
                        ui.label(f"Strategy note: {m['notes']}").style(f"color:{COLORS['text_body']};font-size:12px;margin-top:4px;")

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

    ui.label("Post-NDR Debrief").classes("font-bold")
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

            ui.button("Save Debrief", on_click=save_debrief).props("color=primary").style("margin-top:8px;")

            if debrief:
                ui.markdown("---")
                ui.label("Saved debrief").classes("font-bold")
                with ui.row().classes("w-full gap-3"):
                    _bp_metric("Meetings held", str(debrief.get("meetings_held", "—")), [])
                    _bp_metric("Effectiveness", f"{debrief.get('effectiveness', '—')}/100", [])
                    _bp_metric("Best meeting", debrief.get("best_meeting") or "—", [])
                if debrief.get("key_objection"):
                    ui.label(f"Key objection: {debrief['key_objection']}").style(f"color:{COLORS['warning']};font-size:12px;margin-top:6px;")
                if debrief.get("narrative_gap"):
                    ui.label(f"Narrative gap: {debrief['narrative_gap']}").style(f"color:{COLORS['warning']};font-size:12px;")
                if debrief.get("next_targets"):
                    ui.label(f"Next targets: {debrief['next_targets']}").style(f"color:{COLORS['accent_light']};font-size:12px;")

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
        h1 = ui.tab("Upcoming Meetings")
        h2 = ui.tab("Schedule Meeting")
        h3 = ui.tab("Post-Meeting Notes")
    with ui.tab_panels(hub_tabs, value=h1).classes("w-full"):
        with ui.tab_panel(h1):
            upcoming = sorted([m for m in scheduled if _safe_date(m["Date"]) >= today], key=lambda x: x["Date"])
            # Tiles are clickable filters over the meeting list below (by side);
            # "Notes captured" jumps to the Post-Meeting Notes tab.
            _hub_filter = {"mode": "all"}
            hub_cards_row = ui.row().classes("w-full gap-3")

            def _hub_shown():
                if _hub_filter["mode"] == "sell":
                    return [m for m in upcoming if m["Side"] == "Sell-side"]
                if _hub_filter["mode"] == "buy":
                    return [m for m in upcoming if m["Side"] == "Buy-side"]
                return upcoming

            def set_hub_filter(mode):
                _hub_filter["mode"] = mode
                render_hub_cards()
                render_hub_list()

            def render_hub_cards():
                hub_cards_row.clear()
                with hub_cards_row:
                    _hub_metric("Upcoming", len(upcoming), "All scheduled ahead",
                                _hub_filter["mode"] == "all", lambda: set_hub_filter("all"))
                    _hub_metric("Sell-side", sum(1 for m in upcoming if m["Side"] == "Sell-side"),
                                "Analyst meetings", _hub_filter["mode"] == "sell", lambda: set_hub_filter("sell"))
                    _hub_metric("Buy-side", sum(1 for m in upcoming if m["Side"] == "Buy-side"),
                                "Investor meetings", _hub_filter["mode"] == "buy", lambda: set_hub_filter("buy"))
                    _hub_metric("Notes captured", len(notes), "Open the Notes tab", False,
                                lambda: hub_tabs.set_value(h3))

            render_hub_cards()

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
                    ui.notify(f"{result['message']}", type="warning")
                else:
                    n = len(result["messages"])
                    routed = sum(1 for m in result["messages"] if m.get("category") != "general")
                    if n:
                        extra = f" · {routed} item(s) flagged for review below" if routed else ""
                        ui.notify(f"Synced — {n} message(s) from known contacts.{extra}")
                    else:
                        ui.notify("Synced — no new messages from known contacts.")
                    _refresh()

            ui.button("Sync IR Inbox", on_click=sync_inbox).props("flat dense").style(
                f"color:{COLORS['accent_light']};font-size:12px;margin-top:4px;")
            if not mail_gateway.is_configured():
                ui.label("Email sync isn't configured yet (no IMAP credentials in .env) — this button will "
                          "explain that rather than pretend to have fetched anything.").style(
                    f"color:{COLORS['text_muted']};font-size:11px;")

            _render_pending_inbox_items()

            hub_list = ui.column().classes("w-full gap-2").style("margin-top:8px;")

            def render_hub_list():
                hub_list.clear()
                shown = _hub_shown()
                with hub_list:
                    label = {"all": "Upcoming", "sell": "Sell-side", "buy": "Buy-side"}[_hub_filter["mode"]]
                    clear = "" if _hub_filter["mode"] == "all" else "  ·  click Upcoming to clear"
                    ui.label(f"Showing {len(shown)} meeting(s) — {label}{clear}").style(
                        f"color:{COLORS['text_muted']};font-size:12px;")
                    if not shown:
                        ui.label("No upcoming meetings in this view.").style(f"color:{COLORS['text_muted']};")
                    for mtg in shown:
                        cap = f"{mtg['Date']} {mtg.get('Time','')} · {mtg['Firm']} · {mtg.get('Side','')} · {mtg.get('Status','—')}"
                        with ui.expansion(f"{mtg['Contact']} ({mtg['Firm']})", caption=cap).classes("w-full").style(
                                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};border-radius:8px;"):
                            ui.label(f"{mtg['Type']} · Priority: {mtg.get('Priority','—')}").style(
                                f"color:{COLORS['text_secondary']};font-size:13px;")
                            if mtg.get("Topic"):
                                ui.label(f"Topic: {mtg['Topic']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                            _render_linked_documents(mtg["Contact"], mtg["Firm"])

            render_hub_list()

        with ui.tab_panel(h2):
            ui.label("Schedule a New Meeting or Callback").classes("font-bold")
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    s_contact = ui.input("Contact name *").classes("w-full")
                    s_firm = ui.input("Firm *", autocomplete=firm_options).classes("w-full")
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
            upload_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:12px;")

            async def handle_model_upload(e):
                pending_upload["bytes"] = await e.file.read()
                pending_upload["filename"] = e.file.name
                pending_upload["content_type"] = e.file.type
                upload_status.text = f"Attached: {e.file.name} — will be saved when you add this to the queue."
                upload_status.style(f"color:#15803D;font-size:12px;")

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

            ui.button("Add to Meeting Queue", on_click=add_meeting).props("color=primary")

        with ui.tab_panel(h3):
            ui.label("Post-Meeting Note Capture — AI Structures Your Raw Notes").classes("font-bold")
            ui.label("Type your raw notes immediately after the call — an AI model organizes them into questions, concerns, signals, and actions.").style(f"color:{COLORS['text_muted']};font-size:12px;")
            with ui.row().classes("w-full gap-4"):
                with ui.column().classes("flex-1"):
                    n_contact = ui.input("Contact name").classes("w-full")
                    n_firm = ui.input("Firm", autocomplete=firm_options).classes("w-full")
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
            n_upload_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:12px;")

            async def handle_note_upload(e):
                n_pending_upload["bytes"] = await e.file.read()
                n_pending_upload["filename"] = e.file.name
                n_pending_upload["content_type"] = e.file.type
                n_upload_status.text = f"Attached: {e.file.name}"
                n_upload_status.style("color:#15803D;font-size:12px;")

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
                ui.notify(f"Submitted — notes saved for {n_contact.value} at {n_firm.value}"
                          + (" (with attachment)" if n_pending_upload["bytes"] else ""))

            ui.button("Structure Notes with AI", on_click=structure_notes).props("color=primary")
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
    sent_clr = "#15803D" if sent == "Positive" else "#B91C1C" if sent == "Negative" else "#B45309"
    ui.label(f"Sentiment: {sent}").style(f"color:{sent_clr};font-weight:bold;")
    if structured.get("summary"):
        ui.label(structured["summary"]).style(f"color:{COLORS['text_body']};font-size:13px;")
    for key, title in [("financial_kpi_takeaways", "Financial/KPI takeaways"),
                        ("key_questions", "Key questions"), ("positive_signals", "Positive signals"),
                        ("concerns_raised", "Concerns raised"), ("follow_up_actions", "Follow-up actions"),
                        ("commitments_made", "Commitments made")]:
        items = structured.get(key)
        if items:
            ui.label(title).style("font-weight:bold;font-size:13px;margin-top:4px;")
            for it in items:
                ui.label(f"- {it}").style(f"color:{COLORS['text_muted']};font-size:12px;")


_CATEGORY_LABELS = {
    "model": "Model", "research_note": "Research Note", "ndr_request": "NDR Request",
    "conference_invite": "Conference Invite", "speak_to_management": "Speak to Management",
    "meeting_confirmation": "Meeting Confirmation",
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
        ui.label(f"Pending Inbox Items ({len(pending)})").classes("font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label("Classified and pre-filled from the email by AI where possible — review, correct if needed, "
                  "and confirm to send it where it belongs, or dismiss if it was mis-tagged.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")

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
                    ui.button(f"{item['filename']}", on_click=_download).props("flat dense size=sm").style(
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
                    confirm_label = "Confirm & Update Consensus"

                elif category == "research_note":
                    # CFA-lens breakdown, not just a summary — the reviewer
                    # (Head of IR) should be able to decide in seconds
                    # whether this is worth circulating further internally.
                    # Forwarding itself stays a manual human decision (see
                    # this function's docstring) — this just gets them a
                    # sharper read than a generic AI summary would.
                    with ui.column().classes("w-full gap-1").style("margin-top:6px;"):
                        if extracted.get("thesis_summary"):
                            ui.label(extracted["thesis_summary"]).style(f"color:{COLORS['text_body']};font-size:13px;")
                        meta_bits = []
                        if extracted.get("sentiment"):
                            meta_bits.append(f"Sentiment: {extracted['sentiment']}")
                        if extracted.get("variant_view"):
                            meta_bits.append(f"View: {extracted['variant_view']}")
                        if extracted.get("valuation_method"):
                            meta_bits.append(f"Method: {extracted['valuation_method']}")
                        if meta_bits:
                            ui.label(" · ".join(meta_bits)).style(f"color:{COLORS['accent_light']};font-size:12px;font-weight:bold;")
                        if extracted.get("key_assumptions"):
                            ui.label(f"Key assumptions: {extracted['key_assumptions']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
                        if extracted.get("catalysts_risks"):
                            ui.label(f"Catalysts/risks to watch: {extracted['catalysts_risks']}").style(f"color:{COLORS['warning']};font-size:12px;")
                        if extracted.get("prior_price_target") and extracted.get("price_target"):
                            ui.label(f"PT change: ${extracted['prior_price_target']} → ${extracted['price_target']}").style(
                                f"color:{COLORS['text_body']};font-size:12px;")

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
                    confirm_label = "Confirm Review"

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
                    confirm_label = "Log NDR Request"

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
                    confirm_label = "Add to Calendar"

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
                    confirm_label = "Schedule Meeting"

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
                    confirm_label = "Log Confirmed Meeting"

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
            ui.button(f"Latest model — {model_doc['filename']}",
                      on_click=lambda doc_id=model_doc["id"]: _download(doc_id)) \
                .props("flat dense size=sm").style(f"color:{COLORS['accent_light']};font-size:11px;")
        if note_doc:
            ui.button(f"Latest note attachment — {note_doc['filename']}",
                      on_click=lambda doc_id=note_doc["id"]: _download(doc_id)) \
                .props("flat dense size=sm").style(f"color:{COLORS['accent_light']};font-size:11px;")


def _hub_metric(label, value, hint="", active=False, on_click=None):
    """Summary tile shared across Meeting Hub / Target Database / SEC
    Intelligence. `hint` adds a one-line explanation so it isn't just a bare
    number; passing `on_click` makes it a clickable filter that highlights
    (accent top edge) when `active`."""
    border = COLORS["accent"] if active else COLORS["border"]
    bg = COLORS["surface_hover_bg"] if active else COLORS["surface_bg"]
    edge = COLORS["accent"] if active else "transparent"
    classes = "flex-1 text-center" + (" cursor-pointer" if on_click else "")
    card = ui.card().classes(classes).style(
        f"background:{bg};border:1px solid {border};border-top:3px solid {edge};")
    with card:
        ui.label(str(value)).classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label(label).style(f"color:{COLORS['text_secondary']};font-size:12px;font-weight:600;")
        if hint:
            ui.label(hint).style(f"color:{COLORS['text_muted']};font-size:11px;")
    if on_click:
        card.on("click", on_click)
    return card


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

    ui.label("Target Database").classes("text-lg font-bold")
    ui.label("Search and filter the tracked institution universe, plus manually-added prospects. The automated "
             "prospecting pipeline below (Analyst Coverage Network, live-13F auto-generation, NOBO cross-reference, "
             "bulk paste) is ported and rebuilt on the live SEC 13F fetcher — see each section for details.").style(
        f"color:{COLORS['text_muted']};font-size:12px;")

    _db_filter = {"mode": "all"}
    db_cards_row = ui.row().classes("w-full gap-3").style("margin-top:6px;")
    # The full 91-row list dominated the tab, so search + results live in a
    # collapsed expansion — the cards above are the summary. It auto-opens when
    # a card filter is clicked, a search runs, or a global-search prefill lands,
    # so a filtered view is never hidden behind a closed panel.
    _search_exp = ui.expansion("Search by fund name", icon="search", value=False).classes("w-full").style(
        f"border:1px solid {COLORS['border']};border-radius:8px;margin-top:8px;")
    with _search_exp:
        search_in = ui.input("Search by fund name").classes("w-full")
        _search_btn_row = ui.row().classes("gap-2 items-center")
        results = ui.column().classes("w-full gap-2")

    _OUTCOME_OPTIONS = {"— unresolved —": None, "Won (meeting set / met / owns)": "positive", "Passed": "negative"}
    _OUTCOME_REVERSE = {"positive": "Won (meeting set / met / owns)", "negative": "Passed", None: "— unresolved —"}

    def _db_combined():
        combined = [{"Fund": i["Fund"], "Metro": i["Metro"], "Type": i["Type"], "USIO_Holder": i["USIO_Holder"],
                    "Score": i["Engagement_Score"], "Source": "Tracked", "_pidx": None} for i in institutions]
        for idx, p in enumerate(_load_json("prospects.json", [])):
            combined.append({"Fund": p["fund"], "Metro": p.get("metro", "—"), "Type": p.get("style", "—"),
                             "USIO_Holder": False, "Score": p.get("score", 0), "Source": "Prospect", "_pidx": idx,
                             "_outcome": p.get("outcome"), "_has_score": bool(p.get("score_breakdown"))})
        return combined

    def do_search():
        results.clear()
        q = (search_in.value or "").lower().strip()
        combined = _db_combined()
        if q:
            combined = [c for c in combined if q in c["Fund"].lower()]
        mode = _db_filter["mode"]
        if mode == "holders":
            combined = [c for c in combined if c["USIO_Holder"]]
        elif mode == "nonholders":
            combined = [c for c in combined if not c["USIO_Holder"]]
        elif mode == "prospects":
            combined = [c for c in combined if c["Source"] == "Prospect"]
        combined.sort(key=lambda x: -x["Score"])
        with results:
            _labels = {"all": "All targets", "holders": "Current holders",
                       "nonholders": "Non-holders", "prospects": "Prospects"}
            clear = "" if mode == "all" else "  ·  click All targets to clear"
            ui.label(f"{len(combined)} result(s) — {_labels[mode]}{clear}").style(
                f"color:{COLORS['text_muted']};font-size:12px;")
            if not combined:
                ui.label("No matches.").style(f"color:{COLORS['text_muted']};")
            for c in combined:
                with ui.row().classes("w-full items-center justify-between").style(
                        f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                    ui.label(f"{c['Fund']} ({c['Source']})").style(f"color:{COLORS['text_body']};font-size:13px;")
                    ui.label(f"{c['Metro']} · {c['Type']} · {'Holder' if c['USIO_Holder'] else 'Non-holder'} · Score {c['Score']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
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

    def set_db_filter(mode):
        _db_filter["mode"] = mode
        render_db_cards()
        do_search()
        _search_exp.set_value(True)  # a filtered list must not stay hidden

    def render_db_cards():
        c = _db_combined()
        db_cards_row.clear()
        with db_cards_row:
            _hub_metric("All targets", len(c), "Tracked + prospects",
                        _db_filter["mode"] == "all", lambda: set_db_filter("all"))
            _hub_metric("Current holders", sum(1 for x in c if x["USIO_Holder"]), "Own USIO now",
                        _db_filter["mode"] == "holders", lambda: set_db_filter("holders"))
            _hub_metric("Non-holders", sum(1 for x in c if not x["USIO_Holder"]), "Conversion targets",
                        _db_filter["mode"] == "nonholders", lambda: set_db_filter("nonholders"))
            _hub_metric("Prospects", sum(1 for x in c if x["Source"] == "Prospect"), "Added to database",
                        _db_filter["mode"] == "prospects", lambda: set_db_filter("prospects"))

    # A global-search result for a fund lands here pre-searched (nav.go_to passes
    # the fund name as search_prefill), so the user sees exactly the record they
    # clicked instead of the full list.
    _prefill = nav.pop_highlight("search_prefill", None)
    if _prefill:
        search_in.value = _prefill
        _search_exp.set_value(True)  # arrived from global search — show the hit
    search_in.on("keydown.enter", do_search)
    with _search_btn_row:
        ui.button("Search", on_click=do_search).props("dense")
    render_db_cards()
    do_search()

    ui.markdown("---")
    with ui.expansion("Add a prospect manually").classes("w-full"):
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

        ui.button("Add Prospect", on_click=add_prospect).props("color=primary")

    ui.markdown("---")
    with ui.expansion("Bulk paste-from-website", value=False).classes("w-full"):
        ui.label("Some sites (WhaleWisdom in particular) render holder tables as styled grids, not plain HTML "
                  "tables — copy/paste from those won't preserve columns cleanly through a file upload. Paste raw "
                  "text here instead; it's parsed by tab or by runs of 2+ spaces.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")
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
                    f"color:{COLORS['text_muted']};font-size:12px;")
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
                    ui.notify(f"Added {added} funds to the prospect queue.")
                    _refresh()

                ui.button(f"Add all parsed rows to Prospect Queue", on_click=add_all).props("dense").style("margin-top:6px;")

        bp_raw.on_value_change(bp_parse)
        ui.button("Parse", on_click=bp_parse).props("dense flat")

    ui.markdown("---")
    with ui.expansion("Analyst Coverage Network Targeting", value=False).classes("w-full"):
        ui.label("Institutions already owning other stocks a covering analyst rates Buy have demonstrated they "
                  "trust that analyst's research and understand the surrounding sector thesis — the "
                  "highest-probability prospects once that analyst raises this client's target.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")

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
                        f"color:{COLORS['text_heading']};font-size:13px;")
                    for stock in sorted(data["coverage"], key=lambda s: -s.get("relevance", 0)):
                        rel = stock.get("relevance", 0)
                        rel_clr = "#15803D" if rel >= 80 else "#B45309" if rel >= 50 else "#94A3B8"
                        with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};margin-top:4px;"):
                            with ui.row().classes("w-full justify-between items-center"):
                                ui.label(f"{stock['ticker']} — {stock['name']} · {stock.get('sector', '—')}").classes("font-bold").style(
                                    f"color:{COLORS['text_heading']};font-size:13px;")
                                ui.label(f"{stock.get('rating', '—')} · PT ${stock.get('pt', 0):.2f} · Relevance {rel}/100").style(
                                    f"color:{rel_clr};font-size:12px;font-weight:bold;")
                            if stock.get("bridge"):
                                ui.label(stock["bridge"]).style(f"color:{COLORS['text_muted']};font-size:11px;")
                            if stock.get("shared_dna"):
                                ui.label(" · ".join(t.strip() for t in stock["shared_dna"].split("·") if t.strip())).style(
                                    f"color:{COLORS['accent_light']};font-size:11px;")

            analyst_sel.on_value_change(render_coverage_list)
            render_coverage_list()

            ui.markdown("---")
            with ui.expansion("Add stock to this analyst's coverage").classes("w-full"):
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

                ui.button("Add", on_click=add_coverage_entry).props("dense")

    ui.markdown("---")
    with ui.expansion("Automated Prospecting Pipeline — Live 13F Holders of Coverage-Network Stocks", value=False).classes("w-full"):
        ui.label("For the selected analyst's other Buy-rated stocks scoring at or above the threshold, pulls real "
                  "SEC 13F institutional holders (already fetched via the SEC Intelligence tab's 'Refresh 13F "
                  "Institutional Holders' button — this does not trigger a new download itself), excludes anyone "
                  "already tracked or already in the prospect queue, and ranks the rest.").style(
            f"color:{COLORS['text_muted']};font-size:12px;")

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
                        ui.label(f"No live 13F data cached yet for: {', '.join(result['not_fetched_tickers'])} — "
                                  f"add them to the Peer Universe below and refresh 13F on the SEC Intelligence tab "
                                  f"to include their holders here.").style(f"color:{COLORS['warning']};font-size:11px;")
                    # Show what the quality gates removed, so a short (or empty) list
                    # reads as "the filter worked", not "the pipeline is broken".
                    _filt = result.get("filtered_passive", 0) + result.get("filtered_breadth", 0)
                    if not result["prospects"]:
                        msg = ("No new prospects found at this relevance threshold."
                               if not _filt else
                               f"No qualifying institutional prospects — {_filt} holder(s) were found but "
                               "filtered out as index/passive books, market makers, banks, or ETF issuers. "
                               "Lower the relevance threshold or add more coverage tickers to widen the net.")
                        ui.label(msg).style(f"color:{COLORS['text_muted']};font-size:12px;")
                        # NB: no early return — the RIA bucket below must still render;
                        # "no institutional targets, but 6 RIAs own it" is a real answer.
                    # Deliberately NOT called "prospects found" — that collided with the
                    # "Prospects" card above and read like the two numbers should match.
                    # They're disjoint by construction: this list EXCLUDES everything
                    # already tracked or already in the prospect queue (known_fund_names),
                    # so these are candidates that are not in the database until ADDed.
                    if result["prospects"]:
                        ui.label(f"{len(result['prospects'])} new suggestion(s) — not in your database yet").classes("font-bold")
                        _fnote = (f" · {_filt} filtered out as passive / market-maker / index noise"
                                  if _filt else "")
                        ui.label("Already-tracked funds and prospects you've added are filtered out of this list. "
                                 f"Click ADD to move one into the Prospects count on the cards above.{_fnote}").style(
                            f"color:{COLORS['text_muted']};font-size:11px;")
                    for p in result["prospects"][:25]:
                        with ui.row().classes("w-full items-start justify-between").style(
                                f"border-bottom:1px solid {COLORS['border']};padding:6px 0;"):
                            with ui.column().classes("flex-1"):
                                ui.label(f"{pretty_name(p['fund'])} — via {p['source_ticker']} ({p['source_name']})").classes("font-bold").style(
                                    f"color:{COLORS['text_heading']};font-size:13px;")
                                ui.label(p["talking_point"]).style(f"color:{COLORS['text_muted']};font-size:11px;")
                                # size_known=False means this holder came from the EDGAR full-text-search
                                # path (sec_filings._search_holders_for_ticker) — confirmed to hold a
                                # position, but exact share/dollar size wasn't fetched (see that
                                # function's docstring). Showing "1 shares · $0 reported" in that case
                                # would be misleadingly precise-looking for a value we don't actually have.
                                size_line = (f"{p['shares']:,} shares · ${p['value']:,} reported · relevance {p['relevance']}/100"
                                             if p.get("size_known", True)
                                             else f"confirmed holder (position size not available) · relevance {p['relevance']}/100")
                                ui.label(size_line).style(f"color:{COLORS['text_muted']};font-size:11px;")

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

                            ui.button("Add", on_click=add_this).props("flat dense")

                    # ── RIA / wealth bucket ──────────────────────────────────
                    # These own the stock but aren't institutional NDR targets —
                    # kept out of the list above, yet visible here (only ones with
                    # a real position) since who owns adjacent names through the
                    # advisory channel is still worth knowing.
                    _rias = result.get("ria_holders") or []
                    if _rias:
                        with ui.expansion(f"RIA / wealth managers holding these names ({len(_rias)})",
                                          icon="account_balance_wallet", value=False).classes("w-full").style(
                                f"border:1px solid {COLORS['border']};border-radius:8px;margin-top:10px;"):
                            ui.label("Real positions, but held through client accounts — there's no portfolio "
                                     "manager to pitch, so these aren't NDR targets. Video-call tier: an "
                                     "assistant can set these up, no management travel needed. Add one and the "
                                     "NDR scheduler defaults it to a video call. Ranked by position size.").style(
                                f"color:{COLORS['text_muted']};font-size:11px;")
                            for r in _rias[:25]:
                                with ui.row().classes("w-full items-center justify-between").style(
                                        f"border-bottom:1px solid {COLORS['border']};padding:5px 0;"):
                                    with ui.column().classes("gap-0 flex-1"):
                                        ui.label(r["fund"]).style(
                                            f"color:{COLORS['text_body']};font-size:12px;font-weight:600;")
                                        ui.label(f"{r['shares']:,} shares of {r['source_ticker']} "
                                                 f"({r['source_name']})").style(
                                            f"color:{COLORS['text_muted']};font-size:11px;")

                                    def add_ria(r=r):
                                        plist = _load_json("prospects.json", [])
                                        if any(x["fund"] == r["fund"] for x in plist):
                                            ui.notify(f"{r['fund']} is already in the prospect queue.", type="warning")
                                            return
                                        plist.append({
                                            "fund": r["fund"], "metro": "—", "style": "RIA / wealth manager",
                                            "score": r["relevance"],
                                            # Low-touch tier: video call an assistant schedules, not
                                            # management travel. The NDR scheduler reads is_ria() and
                                            # defaults these to a video format for the same reason.
                                            "touch": "video-call",
                                            "outreach": "Video call — assistant can schedule",
                                            "notes": f"RIA/wealth manager — holds {r['shares']:,} shares of "
                                                     f"{r['source_ticker']} ({r['source_name']}). Video-call "
                                                     f"tier: no PM to pitch, so an assistant can set up a call.",
                                            "added": datetime.now().strftime("%Y-%m-%d"),
                                            "source": f"Coverage Network (RIA) — {r['source_ticker']}",
                                        })
                                        _save_json("prospects.json", plist)
                                        ui.notify(f"{r['fund']} added to prospect queue.")
                                        _refresh()

                                    ui.button("Add", on_click=add_ria).props("flat dense")

            ui.button("Auto-Generate Prospect List", on_click=run_auto_prospecting).props("color=primary dense")
            run_auto_prospecting()

    ui.markdown("---")
    with ui.expansion("NOBO Cross-Reference", value=False).classes("w-full"):
        ui.label("Request from the transfer agent (e.g. Computershare) quarterly — Excel or CSV with holder name "
                  "and shares. Compares a list of names (the prospect queue, tracked institutions, the call "
                  "listener log, the IR website visitor log, or a pasted list) against this client's actual NOBO "
                  "shareholder file — matches are already-identified shareholders; everyone else is a real, "
                  "unconfirmed prospect.").style(f"color:{COLORS['text_muted']};font-size:12px;")

        nobo_status = ui.label("").style(f"color:{COLORS['text_muted']};font-size:12px;")

        def refresh_nobo_status():
            cur = prospecting.get_nobo_list(client_id)
            if cur.get("rows"):
                nobo_status.text = f"{cur['source_label']} — {len(cur['rows'])} holders on file (loaded {cur['_fetched_at'][:10]})"
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
                ui.notify(f"NOBO list updated — {len(parsed)} holders.")
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
                        ui.label("Identified shareholders").classes("font-bold").style("color:#15803D;font-size:12px;")
                        if matched:
                            for nm, mn, sh in matched:
                                ui.label(f"{nm} → {mn} — {sh:,} shares").style(f"color:{COLORS['text_body']};font-size:11px;")
                        else:
                            ui.label("None matched.").style(f"color:{COLORS['text_muted']};font-size:11px;")
                    with ui.column().classes("flex-1").style(f"background:{COLORS['surface_hover_bg']};border-radius:8px;padding:8px;"):
                        ui.label("Not on the NOBO file (genuine prospects)").classes("font-bold").style(
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
    ui.label("Peer Cross-Targeting — Find Institutions Owning Peers But Not This Client").classes("font-bold")
    peers = _load_peer_universe()

    with ui.expansion("Manage Peer Universe — Add or Remove Tickers", value=False).classes("w-full"):
        ui.label(f"Custom peer group saved to peer_universe.csv · Persists across restarts · {len(peers)} peers currently tracked").style(
            f"color:{COLORS['text_muted']};font-size:12px;")

        manage_list = ui.column().classes("w-full")

        def render_manage_list():
            manage_list.clear()
            current = _load_peer_universe()
            with manage_list:
                for idx, p in enumerate(current):
                    with ui.row().classes("w-full items-center justify-between").style(f"border-bottom:1px solid {COLORS['border']};padding:4px 0;"):
                        ev = f"{p['ev_rev']}x" if p.get("ev_rev") else "no EV/Rev on file"
                        ui.label(f"{p['ticker']} — {p['name']} · {p.get('sector','—')} · {ev}").style(f"color:{COLORS['text_body']};font-size:13px;")

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
                        ui.button("", on_click=do_delete).props("flat dense")

        render_manage_list()
        ui.label("Tier: \"core\" = closest-size direct comp (full Fit Score points, +5 conviction bonus) · "
                 "\"close\" = real but less-comparable peer (default) · \"large\" = mega-cap/weak-signal peer. "
                 "Weight scales Peer Conviction — higher for peers closest to this client's own size.").style(
            f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")
        ui.markdown("---")

        ui.label("Add a new peer ticker:").classes("font-bold").style("font-size:13px;")
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
            ui.notify(f"{tkr} — {nm} added and saved" + (f" with EV/Rev {ev_val}x." if ev_val else " — no EV/Rev yet, flagged as needing research."))
            new_ticker.value, new_name.value, new_sector.value, new_ev.value = "", "", "", ""
            new_tier.value, new_weight.value = "close", 1.0
            render_manage_list()
            _refresh()

        ui.button("Add", on_click=add_peer).props("dense")

        missing_ev = [p["ticker"] for p in peers if not p.get("ev_rev")]
        if missing_ev:
            ui.label(f"No EV/Revenue multiple on file for: {', '.join(missing_ev)} — these won't get a specific "
                     f"valuation comparison in outreach drafts until a multiple is added here.").style(
                f"color:{COLORS['text_muted']};font-size:11px;")

        ui.markdown("---")
        ui.label("Quick-add common fintech peers:").style(f"color:{COLORS['text_muted']};font-size:12px;")
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
                    ui.label(f"{qt}").style(f"color:{COLORS['text_muted']};font-size:12px;")
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
        _freshness_bits.append(f"Live SEC 13F data: {', '.join(_live_tickers)}")
    if _seed_tickers:
        _freshness_bits.append(f"Seed data only (not yet 13F-refreshed): {', '.join(_seed_tickers)}")
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
                    ui.label(f"{t} — {info['name']} · {info.get('sector','—')}").style(f"color:{COLORS['text_muted']};font-size:12px;")

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
                # Same = confirmed-by-real-13F-filing marker as the
                # institution card's "Peers held" line — kept consistent so
                # the same overlap doesn't look "more real" in one place
                # than the other.
                ct_src = ct.get("Peer_Holdings_Source", {})
                overlap_labels = [p + (" " if ct_src.get(p) == "live" else "") for p in overlap]
                score = ct["Engagement_Score"]
                score_clr = "#15803D" if score >= 80 else "#B45309" if score >= 50 else "#94A3B8"
                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(f"{ct['Fund']} — {ct['Type']} · AUM {ct['AUM']}").classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                        ui.label(f"Score: {score}").style(f"color:{score_clr};font-weight:bold;")
                    ui.label(f"Owns: {', '.join(overlap_labels)} · IR visits (30d): {ct['IR_Visits_30d']} · "
                             f"Q1 call: {'Yes' if ct['Call_Listener'] else 'No'} · Does NOT own this client").style(
                        f"color:{COLORS['text_muted']};font-size:12px;")
            if from_click:
                ui.notify(f"Cross-targeting run — {len(cross_targets)} institution(s) found.", type="positive")

    ui.button("Run cross-targeting", on_click=lambda: run_cross_targeting(from_click=True)).props("color=primary dense")
    run_cross_targeting()

    ui.markdown("---")
    ui.label("Fit Score Ranking — All Confirmed Peer Holders (Live 13F)").classes("font-bold")
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
    ).style(f"color:{COLORS['text_muted']};font-size:12px;")

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
            tier_clrs = {"P1": "#15803D", "P2": "#3B8A5C", "P3": "#B45309", "P4": "#94A3B8"}
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
                    ui.notify(f"{r['fund']} added to prospect queue.")

                with ui.card().classes("w-full").style(f"background:{COLORS['surface_hover_bg']};"):
                    with ui.row().classes("w-full justify-between items-center"):
                        ui.label(r["fund"]).classes("font-bold").style(f"color:{COLORS['text_heading']};font-size:13px;")
                        with ui.row().classes("items-center gap-2"):
                            ui.label(f"{r['tier_label']} · {r['composite']}/100").style(f"color:{tier_clr};font-weight:bold;font-size:13px;")
                            ui.button("Add", on_click=add_scored_prospect).props("flat dense")
                    ui.label(f"Holds: {', '.join(r['peers_held'])}" +
                             (" · NEW buyer this quarter" if r["newbuyer_pts"] else "")).style(
                        f"color:{COLORS['text_muted']};font-size:12px;")
                    with ui.row().classes("w-full gap-2").style("margin-top:2px;flex-wrap:wrap;"):
                        for label, val, maxv in [
                            ("Conviction", r["conviction"], 30), ("New-buyer", r["newbuyer_pts"], 20),
                            ("Fit", r["fit"], 15), ("Turnover", r["turnover_pts"], 15),
                            ("Purch. power", r["pp_pts"], 10), ("Contact", r["contact_pts"], 10),
                        ]:
                            ui.label(f"{label} {val}/{maxv}").style(
                                f"color:{COLORS['text_muted']};font-size:11px;background:{COLORS['surface_bg']};"
                                f"padding:1px 6px;border-radius:6px;")
                    ui.label(f"Turnover: {r['turnover_class']} ({r['turnover_why']}) · "
                              f"Purchasing power: {r['pp_class']} ({r['pp_why']}) · "
                              f"Contactability: {r['contact_class']} ({r['contact_why']})").style(
                        f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;margin-top:2px;")
            if from_click:
                ui.notify(f"Fit Score ranking run — {len(scored)} institution(s) scored.", type="positive")

    ui.button("Rank by Fit Score", on_click=lambda: run_fit_score_ranking(from_click=True)).props("color=primary dense")

    with ui.expansion("Fit Score Weights — Re-weight the Components", value=False).classes("w-full"):
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
            ui.notify("Weights saved — re-run Fit Score ranking to see the effect.", type="positive")

        ui.button("Save weights", on_click=save_weight_changes).props("dense")

        ui.markdown("---")
        ui.label("Which score signals are converting? Re-weight the score:").classes("font-bold").style("font-size:13px;")
        reweight_area = ui.column().classes("w-full")

        def run_reweight_suggestion():
            reweight_area.clear()
            result = fit_score.suggest_reweight(get_active_client_id())
            with reweight_area:
                if result["mode"] == "insufficient":
                    ui.label(result["message"]).style(f"color:{COLORS['text_muted']};font-size:12px;")
                    return
                ui.label(f"From {result['n_pos']} positive (met/owns) and {result['n_neg']} pass outcomes:").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")
                for c in result["components"]:
                    move_str = f"+{c['move']}" if c["move"] > 0 else str(c["move"])
                    move_clr = "#15803D" if c["move"] > 0 else "#B91C1C" if c["move"] < 0 else COLORS["text_muted"]
                    ui.label(f"{c['label']}: current {c['cur']} → suggested {c['suggested']} ({move_str}) · "
                              f"lift {c['lift']} (avg {c['mean_pos']} converters vs {c['mean_neg']} passes)").style(
                        f"color:{move_clr};font-size:12px;")

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
    ui.label("SEC Intelligence").classes("text-lg font-bold")
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
                f"border-radius:6px;padding:8px 12px;margin-top:4px;"
            ):
                ui.label(
                    f"13F refresh failed for all {len(_13f_errors)} tracked ticker(s) — the SEC bulk "
                    f"download/parse itself errored before any institutional-holder data could be saved. "
                    f"This is not \"no data exists\"; it's a failed fetch. Error: {_sample_err}"
                ).style(f"color:{COLORS['text_body']};font-size:12px;")

    # At-a-glance summary of what's cached across the tracked universe.
    _sec_tickers = sec_filings.tracked_tickers()
    _sec_13d = sum(len(sec_filings.get_cached_13d_13g(t, refresh_if_stale=False).get("filings", []))
                   for t, _n in _sec_tickers)
    _sec_hold = sum(len(sec_filings.get_cached_13f_holders(t).get("holders", []))
                    for t, _n in _sec_tickers)
    with ui.row().classes("w-full gap-3").style("margin-top:8px;"):
        _hub_metric("Tickers tracked", len(_sec_tickers), "Client + peer universe")
        _hub_metric("13D/13G on file", _sec_13d, "Ownership-stake filings")
        _hub_metric("Institutional holders", _sec_hold, "From latest 13F")

    # Data-provenance rollup — how big the tracked universe is and where every
    # name came from. This is the honest, concrete answer to "why isn't the
    # database bigger?": it grows from authoritative sources, each tagged.
    _cid = get_active_client_id()
    _merged = _merge_sec_universe([dict(i) for i in get_seed_buyside_institutions(_cid)], _cid)
    from collections import Counter as _Counter
    _by_src = _Counter(i.get("Source", "Seed (demo)") for i in _merged)
    try:
        _nobo_inst = sum(1 for h in nobo_engine.get_active_pulls(_cid)["current"]["holders"]
                         if h.get("type") == "Institutional")
    except Exception:
        _nobo_inst = 0
    ui.label("Universe by data source").classes("font-bold").style("margin-top:12px;")
    ui.label(f"{len(_merged)} distinct names in the tracked universe · plus {_nobo_inst} institutional NOBO "
             "holders (Market Intelligence → NOBO). Hand-typed seed today; refresh below to grow the real "
             "SEC-sourced names live from EDGAR.").style(f"color:{COLORS['text_muted']};font-size:12px;")
    with ui.row().classes("w-full gap-2 flex-wrap").style("margin-top:4px;"):
        for _src, _n in _by_src.most_common():
            ui.label(f"{_src}: {_n}").style(
                f"background:{_source_color(_src)};color:#fff;border-radius:6px;padding:2px 10px;"
                "font-size:12px;font-weight:600;")

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
                        ui.label(f"13D/13G fetch error: {d13['_error']}").style(f"color:{COLORS['warning']};font-size:12px;")
                    if not filings:
                        ui.label("No 13D/13G filings cached yet for this ticker.").style(f"color:{COLORS['text_muted']};font-size:12px;")
                    else:
                        for f in filings[:10]:
                            ui.label(f"{f['date']} · {f['form']} · {f['title']}").style(f"color:{COLORS['text_body']};font-size:12px;")
                            if f.get("link"):
                                ui.link("View on EDGAR ↗", f["link"], new_tab=True).style("font-size:12px;")

                    ui.markdown("---")
                    if f13.get("_error") and f13["_error"] != "not yet fetched":
                        ui.label(f"13F fetch error: {f13['_error']}").style(f"color:{COLORS['warning']};font-size:12px;")
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

    async def refresh_universe():
        # One-click: pull COMPLETE 13F holders (bulk structured dataset,
        # filtered by CUSIP — exact shares, every holder) for USIO and every
        # peer, plus 13D/13G, then report how many real names populate the
        # universe by source. This is the "make it bigger, accurately" action.
        ui.notify("Refreshing from SEC EDGAR — downloading the ~100MB quarterly 13F bulk dataset and pulling "
                  "13D/13G. This is the complete, by-CUSIP holder list; it takes 1–3 minutes.", type="warning")
        try:
            await asyncio.to_thread(sec_filings.refresh_13f_bulk_all, sec_filings.tracked_tickers())
            await asyncio.to_thread(sec_filings.refresh_all, False, True)
            recs = _sec_universe_records(get_active_client_id())
            bs = _Counter(r["Source"] for r in recs)
            summary = ", ".join(f"{n} {s}" for s, n in bs.most_common()) or "no new names this quarter"
            ui.notify(f"SEC EDGAR refresh complete — {len(recs)} real names now in your universe ({summary}). "
                      "Reopen Buy-Side Intelligence to see them tagged by source.", type="positive")
        except Exception as e:
            ui.notify(f"Refresh failed: {e}", type="negative")
        render_sec_list()

    # Data pulls (13F / 13D-G / full universe) are triggered only from
    # Settings → Data Sources now — one deliberate place for an expensive SEC
    # refresh, so opening a tab never kicks one off. This tab shows the cached
    # result; reopen it after a pull to see fresh holders. (The refresh_* handlers
    # above are unused here — the live controls live in
    # settings_page._render_data_sources.)
    ui.markdown("---")
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            f"border-left:4px solid {COLORS['accent']};"):
        ui.label("Data pulls live in Settings").classes("font-bold").style(
            f"color:{COLORS['text_heading']};font-size:13px;")
        ui.label("Refreshing SEC 13F / 13D-G data hits the network and can take minutes, so it's kicked off only "
                 "from Settings → Data Sources — never by navigating here.").style(
            f"color:{COLORS['text_secondary']};font-size:12px;")
        ui.button("Open Settings → Data Sources", icon="settings",
                  on_click=lambda: nav.go_to("Settings", "Data Sources")).props(
            "flat dense color=primary").style("margin-top:4px;")

    ui.markdown("---")
    ui.label(
        "If a ticker fails to resolve to a SEC CIK (rare — recent IPOs, ADRs, or a ticker change), add a manual "
        "override in core/sec_filings.py's MANUAL_CIK_OVERRIDES dict."
    ).style(f"color:{COLORS['text_muted']};font-size:11px;")
