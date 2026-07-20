"""
core/investor_scoring.py — the shared buy-side institution scoring engine
and meeting log, used by BOTH page_modules_nicegui/investors_page.py (the
full Buy-Side Intelligence tab) and page_modules_nicegui/today_page.py (the
"Investor Pipeline — Strongest Signal" widget on the front page).

Why this exists as its own module: today_page.py's pipeline widget used to
be a hardcoded, static list of five funds with literal scores typed into
the page ("6 site visits · Hot lead") — a second, disconnected copy of
institutions that are ALREADY tracked and scored for real over in Investor
Targeting. That meant the two pages could show different numbers for the
same fund, and nothing you did on the Today card (like emailing a contact)
was ever recorded anywhere or reflected back on that fund's real record.
Pulling the scoring model and the meeting log out to a shared, page-agnostic
module fixes both: one real score per fund, one real interaction ledger,
and any page that logs an interaction (Today's quick-email flow, or the
full Meeting Log dialog in Investor Targeting) is writing to the same place
the other page reads from.

Scoring model: 100 points across four pillars — Earnings Call Listener /
Peer Ownership / IR Site Visits (each pulled from data/seed/
buyside_institutions.py or, in "post" mode, from live Q2-call-listener and
ownership-change signals), plus Meeting Interactions (0-25, derived from
every logged meeting_log entry's Outcome via OUTCOME_POINTS — see
compute_interaction_score). Meeting Interactions is the only pillar that
changes purely from something a person logged, rather than from seed/feed
data, which is what makes emailing someone from either page a real,
score-moving action instead of a no-op.
"""

from datetime import datetime

from core import db

# ─────────────────────────────────────────────────────────────────────────
# Meeting log — the interaction ledger. Any logged interaction (a full
# Meeting Log entry from Investor Targeting, or a quick "email sent" from
# Today's pipeline widget) is one row here, keyed by Fund.
# ─────────────────────────────────────────────────────────────────────────
def load_meeting_log():
    records = db.load_json("meeting_log.csv", default=None)
    if records is not None:
        return records
    return [
        {"Fund": "Perkins Investment Management", "Date": "2026-06-10", "Type": "1x1 — Investor Conference",
         "Attendees": "Michael Perkins (PM), USIO CFO",
         "Notes": "Discussed Q1 beat, PayFac pipeline. Positive tone. PM asked about FY2027 guidance.",
         "Outcome": "Positive — follow up with Q2 preview deck", "Source": "Manual"},
        {"Fund": "Ancora Advisors", "Date": "2026-05-28", "Type": "Intro call",
         "Attendees": "Frederick DiSanto, IR",
         "Notes": "First contact post-Q1 earnings. Owns GDOT. Interested in ACH growth story.",
         "Outcome": "Warm — send earnings prep when available", "Source": "Manual"},
    ]


def save_meeting_log(records):
    db.save_json("meeting_log.csv", records)


def get_fund_meetings(records, fund_name):
    return sorted([m for m in records if m.get("Fund") == fund_name], key=lambda x: x.get("Date", ""), reverse=True)


# ─────────────────────────────────────────────────────────────────────────
# Interaction Score — the 4th scoring pillar. Every logged meeting's
# Outcome moves a fund's real Engagement_Score, because it's derived fresh
# from the persisted meeting_log on every render — same "recompute from
# persisted source data" pattern the Call/Peer/Visit pillars already use.
# ─────────────────────────────────────────────────────────────────────────
OUTCOME_POINTS = {
    "CFO follow-up required": 10,   # strongest buying-intent / escalation signal
    "Positive — follow up":    8,
    "Warm — send materials":   5,
    "Neutral — maintain":      2,
    "No clear signal":         0,   # also what a bare "email sent, no reply yet" logs as
    "Flag — possible exit":  -10,   # possible pre-exit diligence — actively penalized
}
INTERACTION_SCORE_MAX = 25


def compute_interaction_score(fund_meetings):
    """Sum of OUTCOME_POINTS across every logged meeting for this fund,
    clamped to [0, INTERACTION_SCORE_MAX]. A fund with no meetings logged
    yet scores 0 here (neutral — this pillar simply hasn't got data yet,
    same as Call/Peer/Visit start from whatever the seed/live feed says)."""
    if not fund_meetings:
        return 0
    total = sum(OUTCOME_POINTS.get(m.get("Outcome", ""), 0) for m in fund_meetings)
    return max(0, min(INTERACTION_SCORE_MAX, total))


# ─────────────────────────────────────────────────────────────────────────
# Scoring model — 30/25/20/25 = 100 (Call/Peer/Visit rebalanced from the
# original 40/35/25 to make room for the Meeting Interactions pillar
# without changing the 100-point scale every Tier 1/2/3 cutoff, filter,
# and export across the app already assumes).
# ─────────────────────────────────────────────────────────────────────────
def _pts(raw, out_of, scale):
    """Scale a component score, or None when the underlying signal doesn't exist.

    Returning None (rather than 0) is deliberate: the platform has no website-analytics or
    call-listener integration, so IR_Visits_30d / Call_Score / Visit_Score have NO source for a
    real 13F-derived institution. Coercing that absence to 0 would render as a confident "score 0"
    — a fabricated number wearing the costume of a measurement. A component with no input is
    omitted from the total and shown as "no data"."""
    if raw is None:
        return None
    return round(raw * out_of / scale)


_MATERIALITY_BY_BOOK_PCT = ((1.0, 20), (0.1, 14), (0.01, 6), (0.0, 1))


def _materiality_pts(book_pct):
    """Score (to 20) how much of the HOLDER'S OWN book this position represents.

    This replaces the "IR Site Visits" / "New IR Activity" pillar for real 13F institutions. That
    pillar needs website analytics the platform has no integration for, so it scored None for every
    real holder — 20 dead points out of 100. Book_Pct is measured, and it is the single best proxy
    for how much a holder actually cares: without it an index fund that added a handful of shares
    outranks a conviction holder who is actively selling, which is backwards for IR triage.

    None for a non-holder — materiality doesn't apply, so the pillar is omitted rather than zeroed.
    """
    if book_pct is None:
        return None
    for floor, pts in _MATERIALITY_BY_BOOK_PCT:
        if book_pct >= floor:
            return pts
    return 1


def _third_pillar(inst):
    """(label, points) for the 20-point third pillar: real position materiality when we have it,
    otherwise the original website-visits math for seed records."""
    if inst.get("Book_Pct") is not None:
        return "Position Materiality", _materiality_pts(inst["Book_Pct"])
    if inst.get("IR_Visits_30d") is not None:
        return "New IR Activity", _pts(min(25, inst["IR_Visits_30d"] * 8), 20, 25)
    if inst.get("Visit_Score") is not None:
        return "IR Site Visits", _pts(inst["Visit_Score"], 20, 25)
    return "Position Materiality", None


def score_institutions(institutions, mode, q2_listeners, meeting_log=None):
    """Score each institution from whatever real signals exist.

    Components with no source contribute nothing and are labelled; an institution with NO scorable
    component gets Engagement_Score None, not 0, so the UI can say "no data" instead of implying we
    measured engagement and found none."""
    meeting_log = meeting_log or []
    for inst in institutions:
        interaction_pts = compute_interaction_score(get_fund_meetings(meeting_log, inst["Fund"]))
        if mode == "pre":
            breakdown = [
                ("Earnings Call Listener", _pts(inst.get("Call_Score"), 30, 40), 30),
                ("Peer Ownership", _pts(inst.get("Peer_Score"), 25, 35), 25),
                (_third_pillar(inst)[0], _third_pillar(inst)[1], 20),
                ("Meeting Interactions", interaction_pts, INTERACTION_SCORE_MAX),
            ]
            inst["Score_Label"] = "Engagement"
        else:
            listener = inst.get("Call_Listener")
            if q2_listeners:
                q2_call_pts = round((40 if inst["Fund"] in q2_listeners else 0) * 30 / 40)
            else:
                q2_call_pts = None if listener is None else round((40 if listener else 0) * 30 / 40)

            # Catalyst fit needs to know whether they hold and, if so, the direction of travel.
            holder, qoq, peers = inst.get("USIO_Holder"), inst.get("QoQ_Change"), inst.get("Peer_Holdings")
            if holder is None:
                catalyst_raw = None
            elif not holder and peers:
                catalyst_raw = 35
            elif not holder:
                catalyst_raw = 20
            elif qoq is None:
                catalyst_raw = None          # holder, but no history pulled yet — don't guess
            elif qoq > 0:
                catalyst_raw = 25
            else:
                catalyst_raw = 10
            breakdown = [
                ("Q2 Call Listener", q2_call_pts, 30),
                ("Catalyst Fit", _pts(catalyst_raw, 25, 35), 25),
                (_third_pillar(inst)[0], _third_pillar(inst)[1], 20),
                ("Meeting Interactions", interaction_pts, INTERACTION_SCORE_MAX),
            ]
            inst["Score_Label"] = "Prospect"

        inst["Score_Breakdown"] = breakdown
        scored = [p for _, p, _ in breakdown if p is not None]
        inst["Engagement_Score"] = min(100, sum(scored)) if scored else None
        inst["Scored_Components"] = f"{len(scored)}/{len(breakdown)}"
        inst["Interaction_Score"] = interaction_pts

        # Digital intent is purely call-listener + site-visit signal. With no analytics
        # integration those are absent for real 13F institutions, so it stays None.
        listener_c, visit_c = inst.get("Call_Score"), inst.get("Visit_Score")
        inst["Digital_Intent_Score"] = (
            None if listener_c is None or visit_c is None
            else min(100, round((listener_c / 40) * 60 + (visit_c / 25) * 40)))

    # None sorts last — unscored institutions shouldn't outrank measured ones. Position value is
    # the tie-break: with only 2 of 4 components scorable (no web analytics / call-listener feed),
    # scores bunch tightly, and without this an index fund that added a few shares outranks a
    # conviction holder who is actively selling — the single most important call in the book.
    institutions.sort(key=lambda x: (x["Engagement_Score"] is not None, x["Engagement_Score"] or 0,
                                     x.get("Position_Value") or 0), reverse=True)
    return institutions


def get_fresh_scored_institutions(client_id=None):
    """The single source of truth for 'every tracked institution, scored,
    right now' — same mode-detection (pre/post earnings) and inputs
    investors_page.py's render_investors_page() uses, pulled out here so
    any other page (today_page.py) gets the identical numbers instead of
    a second, hand-maintained copy."""
    from config.client_config import CE, get_active_client_id
    from data.seed.buyside_institutions import get_seed_buyside_institutions

    cid = client_id or get_active_client_id()
    mode_state = db.load_json("buyside_mode.json", {})
    earnings_date_str = CE().get("earnings_date", "2026-08-12")
    earnings_date = datetime.strptime(earnings_date_str, "%Y-%m-%d").date()
    days_to_earnings = (earnings_date - datetime.now().date()).days
    auto_post = days_to_earnings < 0
    mode = mode_state.get("mode", "post" if auto_post else "pre")
    q2_listeners = set(mode_state.get("q2_listeners", []))

    meeting_log = load_meeting_log()
    institutions = score_institutions(get_seed_buyside_institutions(cid), mode, q2_listeners, meeting_log)
    return institutions, meeting_log


def days_since_last_contact(fund_name, meeting_log):
    """Days since the most recent meeting_log entry for this fund, or None
    if there isn't one. Shared by is_recently_contacted (the exclusion
    top_engagement_targets applies) and investors_page.py's Full Institution
    List, which shows a "contacted Nd ago" badge instead of excluding —
    both need the same underlying fact so the two pages' explanations of
    "why does the order/membership differ" stay consistent with each other."""
    cutoff = datetime.now().date()
    best = None
    for m in get_fund_meetings(meeting_log, fund_name):
        try:
            days_ago = (cutoff - datetime.strptime(m["Date"], "%Y-%m-%d").date()).days
        except (KeyError, ValueError):
            continue
        if days_ago >= 0 and (best is None or days_ago < best):
            best = days_ago
    return best


def is_recently_contacted(fund_name, meeting_log, exclude_recent_days=7):
    days = days_since_last_contact(fund_name, meeting_log)
    return days is not None and days <= exclude_recent_days


def top_engagement_targets(limit=5, client_id=None, exclude_recent_days=7):
    """Top-N tracked institutions by Engagement_Score, for the Today page's
    "Strongest Signal" widget — excludes any fund with a meeting_log entry
    logged in the last `exclude_recent_days` days, so a fund drops off the
    front page the moment you log an interaction with them (an email sent,
    a call, a meeting — anything) and only reappears once that window
    passes without a new one, or a fresh signal changes their underlying
    score. This is deliberately the SAME Engagement_Score investors_page.py
    ranks Tier 1/2/3 by, not a separate "strongest signal" formula — a fund
    that's a Tier 1 priority in Investor Targeting is the same fund that
    should show up here. investors_page.py's Full Institution List
    deliberately does NOT apply this same exclusion (it's meant to show
    every tracked fund, not just what's actionable today) — instead it
    shows a "contacted Nd ago" badge (see is_recently_contacted /
    days_since_last_contact above) so it's clear why a fund visible there
    might not appear in Today's shorter pipeline."""
    institutions, meeting_log = get_fresh_scored_institutions(client_id)
    eligible = [i for i in institutions if not is_recently_contacted(i["Fund"], meeting_log, exclude_recent_days)]
    return eligible[:limit]
