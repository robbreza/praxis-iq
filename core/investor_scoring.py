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
def score_institutions(institutions, mode, q2_listeners, meeting_log=None):
    meeting_log = meeting_log or []
    for inst in institutions:
        interaction_pts = compute_interaction_score(get_fund_meetings(meeting_log, inst["Fund"]))
        if mode == "pre":
            call_pts = round(inst["Call_Score"] * 30 / 40)
            peer_pts = round(inst["Peer_Score"] * 25 / 35)
            visit_pts = round(inst["Visit_Score"] * 20 / 25)
            inst["Score_Label"] = "Engagement"
            inst["Score_Breakdown"] = [
                ("Earnings Call Listener", call_pts, 30),
                ("Peer Ownership", peer_pts, 25),
                ("IR Site Visits", visit_pts, 20),
                ("Meeting Interactions", interaction_pts, INTERACTION_SCORE_MAX),
            ]
        else:
            q2_listened = inst["Fund"] in q2_listeners if q2_listeners else inst["Call_Listener"]
            q2_call_pts = round((40 if q2_listened else 0) * 30 / 40)
            if not inst["USIO_Holder"] and inst["Peer_Holdings"]:
                catalyst_raw = 35
            elif not inst["USIO_Holder"]:
                catalyst_raw = 20
            elif inst["QoQ_Change"] > 0:
                catalyst_raw = 25
            else:
                catalyst_raw = 10
            catalyst_pts = round(catalyst_raw * 25 / 35)
            visit_pts = round(min(25, inst["IR_Visits_30d"] * 8) * 20 / 25)
            inst["Score_Label"] = "Prospect"
            inst["Score_Breakdown"] = [
                ("Q2 Call Listener", q2_call_pts, 30),
                ("Catalyst Fit", catalyst_pts, 25),
                ("New IR Activity", visit_pts, 20),
                ("Meeting Interactions", interaction_pts, INTERACTION_SCORE_MAX),
            ]
        inst["Engagement_Score"] = min(100, sum(pts for _, pts, _ in inst["Score_Breakdown"]))
        inst["Interaction_Score"] = interaction_pts
        # Digital_Intent_Score is a separate, unrelated metric (call-listener +
        # visit signal only) — keeps using the ORIGINAL 40/25 scale it was
        # always defined against, unaffected by the Engagement_Score rebalance.
        listener_c, visit_c = inst["Call_Score"], inst["Visit_Score"]
        inst["Digital_Intent_Score"] = min(100, round((listener_c / 40) * 60 + (visit_c / 25) * 40))
    institutions.sort(key=lambda x: x["Engagement_Score"], reverse=True)
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
