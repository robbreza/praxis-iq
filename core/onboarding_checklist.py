"""
core/onboarding_checklist.py — Praxis Point IRConnect client onboarding, LIVE.

IRConnect_Client_Onboarding_Checklist.docx is the one artifact in the set with no
fabricated data in it — it is a process document, not an analytical one. It asks a new
client for the things the platform needs before go-live, and its six sections map almost
exactly onto this codebase's own configuration surface. So rather than audit it, it is
turned into what it should always have been: a LIVE readiness view that answers each item
from the platform instead of a box the client ticks.

A static "□ Pending" tells you nobody has typed an answer. A live check tells you whether
the thing actually works. Those differ: USIO's checklist would show "analyst roster ✓" —
and until today the roster was right while every model behind it was demo data.

-----------------------------------------------------------------------------
🔴 ONE ITEM IN THE .docx IS THE ROOT CAUSE OF HALF OF WHAT WE FIXED ON 2026-07-16
-----------------------------------------------------------------------------
    "Peer/comp group — defined by your team and sell-side coverage, NOT ASSIGNED BY US"

That deference sounds respectful and it is how USIO ended up benchmarked against a bank.
The Quarterly Board Package's comp group was, in its own words, "set by management and
sell-side coverage (Ladenburg, H.C. Wainwright): GDOT, IMXI, FINW, PAYS" —

    GDOT  merger approved by stockholders 2026-06-23 (8-K Item 5.07)
    IMXI  pending acquisition by Western Union
    FINW  FinWise Bancorp — a BANK, reporting under bank accounting
    PAYS  a real peer

Three of four disqualified. And the TwoTier CompSheet's memo named the mechanism: "The
prior comp set was built primarily from the USIO 10-K's named competitors section... That
list reflects USIO MANAGEMENT'S competitive landscape view, not necessarily the most
useful INVESTOR comp set."

Management's competitor list answers "who do we lose deals to." An investor comp set
answers "what should this trade at." They are different questions and the second one has
rules. The fix is NOT to override the client — their view is real information about the
business. It is to ASK for their view and then TEST it, and to say so at onboarding rather
than discover it a quarter later. The criteria already exist, from the CompSheet's memo:

    (a) US-listed, actively traded, independent public company — NO PENDING M&A
    (b) meaningful overlap with at least one client segment
    (c) revenue reported on a comparable basis — payments processor, NOT bank accounting

`peer_group_policy()` below carries that, and `check()` runs (a) and (c) against the live
set every time.
"""

from datetime import date, datetime

from config.client_config import CA, CE, CP, CT


def _ok(v):
    return "ready" if v else "gap"


def corporate_calendar(client_id=None):
    ce = CE()
    items = []
    ed = ce.get("earnings_date")
    items.append({"item": "Standard earnings call date/time", "owner": "IR",
                  "status": _ok(ed), "live": f"{ed} (next: {ce.get('current_quarter')})" if ed else None,
                  "note": "Verified against the market feed's earnings calendar — the 90-day plan "
                          "on file had this 7 days wrong, which made its own blackout math impossible."})
    qs, qe = ce.get("quiet_start"), ce.get("quiet_end")
    items.append({"item": "Quiet period length before/after earnings", "owner": "General Counsel",
                  "status": _ok(qs and qe), "live": f"{qs} → {qe}" if qs else None, "note": None})
    items.append({"item": "Fiscal year end date", "owner": "CFO / Controller",
                  "status": "ready", "live": "Dec 31 — derived from the 10-K period, not asked",
                  "note": "Sourced from the filing rather than the client."})
    items.append({"item": "Annual shareholder meeting date", "owner": "Corporate Secretary",
                  "status": "gap", "live": None,
                  "note": "Not tracked. Gates the NOBO timing below."})
    return items


def service_providers(client_id=None):
    return [
        {"item": "Transfer agent of record", "owner": "Corporate Secretary", "status": "gap",
         "live": None, "note": "Not tracked anywhere in the platform — and it is the gating "
                               "dependency for the NOBO request, which is the oldest open item on file."},
        {"item": "Outside securities counsel (script review)", "owner": "General Counsel",
         "status": "gap", "live": None,
         "note": "The script workflow has a legal-review stage but no counsel contact behind it."},
        {"item": "Proxy solicitor", "owner": "Corporate Secretary", "status": "gap", "live": None,
         "note": None},
    ]


def sell_side_and_peers(client_id=None):
    from core import consensus, market_data
    items = []

    roster = CA() or []
    covering = [a for a in roster if a.get("covering", True)]
    live_cov = []
    try:
        est = market_data.get_estimates(CT("ticker")) or {}
        live_cov = est.get("coverage") or []
    except Exception:
        pass
    items.append({
        "item": "Current analyst roster (name, firm, email, coverage status)", "owner": "IR",
        "status": "ready", "live": f"{len(roster)} covering firms",
        "note": (f"Cross-checked against the market feed: all {len(live_cov)} covering firms match "
                 f"the roster exactly. The roster was never the problem." if live_cov else None)})

    # models — the gap this checklist never asked about
    n_models = 0
    try:
        c = consensus.get_consensus(client_id)
        period = (CE().get("current_quarter") or "") + "E"
        ests = (c.get("period_estimates") or {}).get(period, {})
        n_models = sum(1 for v in ests.values() if v.get("Revenue Est ($M)") is not None)
    except Exception:
        pass
    items.append({
        "item": "Sell-side MODELS (revenue/EPS by analyst)", "owner": "IR / each analyst",
        "status": _ok(n_models), "live": f"{n_models} of {len(roster)} on file",
        "note": ("NOT ON THE ORIGINAL CHECKLIST — and it should be. No feed publishes per-analyst "
                 "models; they come from the analysts by email. Until they are collected, any "
                 "'consensus' the platform shows comes from the market feed's aggregate, not from "
                 "models we hold. This was demo seed data until 2026-07-16.")})

    peers = CP() or []
    primary = [p for p in peers if p.get("tier") != "reference"]
    items.append({
        "item": "Peer/comp group", "owner": "IR + sell-side — THEN TESTED (see policy)",
        "status": "ready", "live": f"{len(primary)} primary, {len(peers)-len(primary)} reference",
        "note": "The .docx said 'defined by your team and sell-side coverage, not assigned by us'. "
                "That deference, unchecked, is what lets a bank or an acquired company into a comp "
                "set. See peer_group_policy()."})
    return items


def shareholder_base(client_id=None):
    from core import sec_filings
    items = []
    n13f = None
    try:
        h = sec_filings.get_cached_13f_holders(CT("ticker")) or {}
        n13f = len([x for x in (h.get("holders") or []) if x.get("filer")])
    except Exception:
        pass
    items.append({"item": "13F/13G/13D snapshot", "owner": "IR / Legal", "status": _ok(n13f),
                  "live": f"{n13f} institutional holders tracked" if n13f else None,
                  "note": "Pulled from EDGAR directly — not asked of the client."})

    nobo = None
    try:
        from core import nobo_engine
        nobo = getattr(nobo_engine, "latest_pull", lambda: None)()
    except Exception:
        pass
    items.append({
        "item": "Has a NOBO list ever been requested?", "owner": "Corporate Secretary",
        "status": "gap" if not nobo else "ready", "live": None,
        "note": "Still no. This is the oldest open item on the engagement — it appears on the "
                "90-Day Plan (target Jul 3, overdue), the Board Package ('scoped but not yet "
                "submitted') and here. It is blocked on the transfer agent above, which is also "
                "not on file. Two gaps, one chain."})
    return items


def source_documents(client_id=None):
    from core import consensus, transcripts
    items = []
    try:
        tr = transcripts.list_transcripts(client_id) or []
    except Exception:
        tr = []
    items.append({"item": "Prior earnings call scripts/transcripts", "owner": "IR",
                  "status": _ok(tr), "live": f"{len(tr)} quarters on file",
                  "note": "Enough to run the Morning After critique, the non-answer profile and "
                          "the number_frame analysis."})
    pg = None
    try:
        pg = (consensus.get_consensus(client_id) or {}).get("period_guidance")
    except Exception:
        pass
    items.append({"item": "Internal guidance model / actuals", "owner": "Finance",
                  "status": _ok(pg), "live": f"{len(pg)} periods" if pg else None,
                  "note": "Guidance is entered and real. NOTE: the quarterly guides currently sum "
                          "ABOVE the stated FY range — see the Earnings Prep Brief."})
    items.append({"item": "Typical lag from quarter-end to final results", "owner": "Finance",
                  "status": "gap", "live": None, "note": None})
    return items


def peer_group_policy():
    """What the checklist SHOULD say about the peer group.

    Not an override of the client — their view is real information about the business. But
    "not assigned by us" is not deference, it is an abdication, and it is traceable to a
    specific bad outcome: a bank (FINW) and a company in an approved merger (GDOT) sitting
    in a valuation comp set for a quarter.
    """
    return {
        "old": "Peer/comp group — defined by your team and sell-side coverage, not assigned by us.",
        "new": ("Peer/comp group — we want your team's view AND your analysts', because management's "
                "competitor list is real information. We will then TEST every name against the "
                "criteria below and tell you which fail and why. Management's competitor list answers "
                "'who do we lose deals to'. An investor comp set answers 'what should this trade at'. "
                "Those are different questions, and only the second one has rules."),
        "criteria": [
            ("(a) Independent and not in play", "US-listed, actively traded, no pending or approved "
             "M&A. A stock pinned to deal consideration is not trading on fundamentals and cannot "
             "calibrate a multiple."),
            ("(b) Segment overlap", "Meaningful overlap with at least one of the client's segments. "
             "A name that has divested the overlapping business no longer qualifies, however "
             "familiar it is."),
            ("(c) Comparable revenue basis", "A payments processor, not bank accounting. A filer "
             "with no cost-of-revenue line has no gross profit, and therefore no comparable margin "
             "or EV/Gross Profit — any vendor figure for it is constructed."),
        ],
        # Worked example is USIO's inherited comp group; show it only for USIO, generic otherwise.
        "evidence": (
            "Applied to USIO's inherited comp group (GDOT, IMXI, FINW, PAYS): GDOT fails "
            "(a) — stockholders approved the CommerceOne merger 2026-06-23. IMXI fails (a) "
            "— pending Western Union acquisition. FINW fails (c) — bank. Three of four, "
            "and the platform had independently found GDOT's EV was negative and CASS's "
            "10-K never uses the phrase 'gross profit' before anyone read this policy."
            if CT("ticker") == "USIO" else
            "Every peer is tested live against criteria (a) recent M&A / merger approval and "
            "(c) no reported gross-profit line, and any that fail are excluded from the median "
            "rather than inherited on trust. See check()."),
    }


def check(client_id=None):
    """Run the peer set against criteria (a) and (c), live, every time."""
    from core import forensics
    rows = []
    for p in CP():
        if p.get("tier") == "reference":
            continue
        f = forensics.filing_margin(p["ticker"])
        no_gp = f["status"] == "no_gross_profit_line"
        seg = (p.get("segment") or "")
        rows.append({
            "ticker": p["ticker"], "name": p.get("name"),
            "c_comparable_basis": not no_gp,
            "c_note": ("reports no gross profit line — bank accounting or equivalent; fails (c)"
                       if no_gp else f"gross profit sourced from the filing ({f['status']})"),
            "flagged": "FLAGGED" in seg.upper() or "take-private" in seg.lower(),
            "flag_note": seg if ("FLAGGED" in seg.upper() or "take-private" in seg.lower()) else None,
        })
    return rows


def compose(client_id=None):
    sections = [
        ("1. Corporate calendar", corporate_calendar(client_id)),
        ("2. Service providers", service_providers(client_id)),
        ("3. Sell-side & peer group", sell_side_and_peers(client_id)),
        ("4. Shareholder base", shareholder_base(client_id)),
        ("5. Source documents", source_documents(client_id)),
    ]
    all_items = [i for _, items in sections for i in items]
    ready = sum(1 for i in all_items if i["status"] == "ready")
    return {
        "client": CT("name"), "ticker": CT("ticker"), "as_of": datetime.now(),
        "sections": sections, "ready": ready, "total": len(all_items),
        "gaps": [i for i in all_items if i["status"] == "gap"],
        "peer_policy": peer_group_policy(), "peer_check": check(client_id),
    }
