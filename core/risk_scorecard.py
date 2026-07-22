"""
core/risk_scorecard.py — computes Markets' IR Risk Dashboard content (the
"Actionable IR signals" list and the 6-category / 24-indicator risk grid)
from real data wherever a real data source exists in this app, marking an
indicator GRAY / "Not Tracked" wherever it doesn't.

This replaces data/seed/consensus_estimates.py's risk_signals/
risk_categories dicts as the primary source. Those started as a faithful
port of app.py's own hardcoded content (itself typed-in literals, not
computed from anything, despite the UI's "auto-updates when models are
ingested" caption). By the time this module was written, the app had
gained several real data sources that didn't exist when that scorecard was
first built: core.market_data (live-ish price/volume), core.sec_filings
(13D/13G ownership-stake filings), the Reg FD log (reports_page.py), the
Script Generation stage state (earnings_page.py), the Consensus Tracker
log (earnings_page.py), and — most recently — core.transcripts
(AI-summarized earnings call transcripts, ingested by hand since ChorusCall
has no public API; see that module's docstring), which backs Q&A Risk
Topics below once a transcript has been ingested and summarized, and (as of
2026-07-12) log_ndr_objection() / the ndr_objections.json log it writes to,
fed by page_modules_nicegui/investors_page.py's Post-NDR Debrief form —
backs KPI Understanding / Investor Objection Trend below once at least one
debrief has logged a real objection. Every indicator below that can be
grounded in one of those now is; the rest — short interest, ESG/governance
monitoring, activist screening, float/ADV, a full cap table — still have no
real source anywhere in this app, so they stay GRAY. That's a deliberate "we
don't have this," not a placeholder waiting for a guess. (Insider Form 4 filings
USED to be on that GRAY list; they're now real via core.insider_feed / SEC
EDGAR, so Insider Selling Optics and the actionable insider card are computed.)

The static, purely-informational items in data/seed/consensus_estimates.py's
risk_signals list (the two "blind spot" gray cards and the NY Metro NDR
prompt) are still pulled from there rather than reinvented here — they're
already honest about being untracked, and NDR-trip readiness isn't wired
into this module yet either.
"""

from datetime import datetime, timedelta

from config.client_config import CA, CT, get_active_client_id
from core import db, market_data


def _consensus_pt_avg(period="Q2 2026E"):
    """Average price target across currently-active covering analysts —
    shared by both compute_scorecard() and compute_actionable_signals() so
    the "138% upside" style figure is computed once, consistently, the
    same way page_modules_nicegui/today_page.py computes its own."""
    from core.consensus import get_consensus
    seed = get_consensus(get_active_client_id())
    ests = seed.get("period_estimates", {}).get(period, {})
    covering_firms = {a["firm"] for a in CA() if a.get("covering", True)}
    pts = [ests[f]["Price Target"] for f in ests if f in covering_firms and ests.get(f, {}).get("Price Target") is not None]
    return sum(pts) / len(pts) if pts else None


def _parse_filing_date(f):
    for key in ("filing_date", "date", "updated"):
        v = f.get(key) if isinstance(f, dict) else None
        if v:
            try:
                return datetime.fromisoformat(str(v)[:19])
            except Exception:
                continue
    return None


# ─────────────────────────────────────────────────────────────────────────
# 24-indicator grid, one function per category
# ─────────────────────────────────────────────────────────────────────────
def _market_signals():
    ticker = CT("ticker")
    snap = market_data.get_snapshot(ticker)
    items = []

    if snap and snap.get("pct_change") is not None:
        chg = snap["pct_change"]
        status = "GREEN" if chg >= 3 else "YELLOW" if chg >= 0 else "ORANGE" if chg >= -3 else "RED"
        as_of = (snap.get("as_of") or "")[:16].replace("T", " ")
        items.append(("Stock Performance", status,
                       f"{chg:+.1f}% as of {as_of} — {'a real move' if abs(chg) >= 3 else 'a modest, single-session move'}, not yet a multi-day trend."))
    else:
        items.append(("Stock Performance", "GRAY", "Market data not yet fetched for this ticker."))

    sector_snap = market_data.get_snapshot("FINX")  # payments-sector ETF as a rough sector proxy
    if snap and snap.get("pct_change") is not None and sector_snap and sector_snap.get("pct_change") is not None:
        rel = snap["pct_change"] - sector_snap["pct_change"]
        status = "GREEN" if rel > 0 else "YELLOW" if rel > -2 else "ORANGE"
        items.append(("Relative Performance", status,
                       f"{ticker} {snap['pct_change']:+.1f}% vs FINX {sector_snap['pct_change']:+.1f}% same session — "
                       f"{'outperforming' if rel > 0 else 'underperforming'} sector by {abs(rel):.1f} point(s)."))
    else:
        items.append(("Relative Performance", "GRAY", "Needs both a stock and FINX sector-ETF snapshot — not yet fully fetched."))

    items.append(("Volatility", "GRAY", "Not tracked — no historical volatility series in this app."))
    items.append(("Short Interest", "GRAY", "Not tracked — no short-interest data source exists here."))
    return items


def _ownership_liquidity():
    items = [
        ("Top Holder Concentration", "GRAY", "Not fully tracked — only a curated set of institutions on file, not a complete cap table."),
        ("Float Liquidity", "GRAY", "Not tracked — no shares-outstanding/float or ADV data in this app."),
    ]

    try:
        from core import sec_filings
        ticker = CT("ticker")
        cached = sec_filings.get_cached_13d_13g(ticker, refresh_if_stale=False) or {}
        filings = cached.get("filings", []) if isinstance(cached, dict) else (cached or [])
        cutoff = datetime.now() - timedelta(days=45)
        recent = [f for f in filings if _parse_filing_date(f) and _parse_filing_date(f) >= cutoff]
        if filings:
            status = "GREEN" if recent else "YELLOW"
            reason = (f"{len(recent)} 13D/13G filing(s) in the last 45 days (of {len(filings)} on file) — "
                      f"{'active recent ownership-stake activity' if recent else 'on file, but nothing in the last 45 days'}.")
        else:
            status, reason = "GRAY", "No 13D/13G filings cached yet — see Investors → SEC Intelligence."
        items.append(("New Institutional Buying", status, reason))
    except Exception as e:
        items.append(("New Institutional Buying", "GRAY", f"13D/13G data unavailable ({e})."))

    items.append(("Retail / Momentum Risk", "GRAY", "Not tracked — no NOBO / retail-ownership data source in this app."))
    return items


def get_revision_momentum(period="Q2 2026E"):
    """8-quarter PT-revision summary — same first-vs-last-PT drift math as
    markets_page.py's PT Drift Tracker "Analyst PT direction" table.

    Extracted to its own function (rather than left inline in
    _estimate_guidance_risk) so it has exactly one caller-agnostic result
    that both the IR Risk Dashboard's "Revision Momentum" scorecard tile
    AND core/board_slides.py's Export-as-Board-Slide feature read from —
    computed once, here, so the two surfaces never say two different things
    about the same 8-quarter history.

    Returns {"status": "GREEN"|"YELLOW"|"RED"|"GRAY", "headline": str,
    "detail": str, "full": str} — "headline"+"detail" are sized for a slide
    stat callout (short label + sub-caption), "full" is the single-sentence
    form the scorecard tile displays.
    """
    from core.consensus import get_consensus
    seed = get_consensus(get_active_client_id())
    pt_hist = seed.get("pt_history", {})
    labels = pt_hist.get("labels", [])
    by_firm = pt_hist.get("by_firm", {})

    if not by_firm:
        msg = "No PT history on file yet — see Markets → PT Drift Tracker."
        return {"status": "GRAY", "headline": "Not tracked", "detail": msg, "full": msg}

    raising, cutting = [], []
    for firm, pts in by_firm.items():
        # firm series are aligned to a shared date axis, so a firm's last slot is None unless it
        # revised on the very last date — use the firm's own valid points, not pts[-1].
        valid = [(labels[i], p) for i, p in enumerate(pts) if p is not None and i < len(labels)]
        if len(valid) < 2:
            continue
        chg_pct = round((valid[-1][1] - valid[0][1]) / valid[0][1] * 100, 1) if valid[0][1] else 0
        if chg_pct > 0:
            raising.append((firm, chg_pct))
        elif chg_pct < 0:
            cutting.append((firm, chg_pct))

    span = f"{labels[0]}–{labels[-1]}" if labels else ""
    moves = raising + cutting
    if not moves:
        msg = "No net PT revisions across the tracked history — every covering desk is flat."
        return {"status": "YELLOW", "headline": "No net revisions", "detail": "Every covering desk flat.", "full": msg}

    n = len(moves)
    status = "GREEN" if raising and not cutting else "RED" if cutting and not raising else "YELLOW"
    direction = "upward" if raising and not cutting else "downward" if cutting and not raising else "mixed"
    headline = f"{n} {direction} revision{'s' if n != 1 else ''}"
    move_list = ", ".join(f"{f} {c:+.1f}%" for f, c in moves)
    return {
        "status": status,
        "headline": headline,
        "detail": f"{move_list}, the rest flat.",
        "full": f"{headline} across the tracked PT history{f' ({span})' if span else ''} ({move_list}) — the rest flat.",
    }


def _estimate_guidance_risk(period="Q2 2026E"):
    from core.consensus import get_consensus
    seed = get_consensus(get_active_client_id())
    items = []

    g = seed.get("period_guidance", {}).get(period, {})
    ests = seed.get("period_estimates", {}).get(period, {})
    ingested = {f: v for f, v in ests.items() if v.get("Rating") is not None}
    rev_vals = [v["Revenue Est ($M)"] for v in ingested.values() if v.get("Revenue Est ($M)") is not None]
    con_rev = sum(rev_vals) / len(rev_vals) if rev_vals else None
    if con_rev and g.get("Revenue Est ($M)"):
        gap_pct = (con_rev - g["Revenue Est ($M)"]) / g["Revenue Est ($M)"] * 100
        status = "GREEN" if abs(gap_pct) <= 1 else "YELLOW" if abs(gap_pct) <= 3 else "ORANGE" if abs(gap_pct) <= 6 else "RED"
        items.append(("Consensus Revenue", status, f"Street ${con_rev:.1f}M vs guidance midpoint ${g['Revenue Est ($M)']:.1f}M — {gap_pct:+.1f}% gap."))
    else:
        items.append(("Consensus Revenue", "GRAY", "No ingested analyst estimates for this period yet."))

    # COUNT MODELS, NOT STATUS. This used to count analysts whose status == "active"
    # and call the result "covering analysts' models" — but an analyst being active
    # means they publish research, NOT that we hold their spreadsheet. Verified
    # 2026-07-16: 2 analysts are active and we have 0 of their models, so the old
    # logic reported "2 of 5 models" while the true figure was zero.
    total = len(CA())
    covering = sum(1 for a in CA() if a.get("covering", True))
    with_model = sum(1 for v in ests.values() if v.get("Revenue Est ($M)") is not None)
    cov = with_model / total if total else 0
    status = "GREEN" if cov >= 0.8 else "YELLOW" if cov >= 0.5 else "ORANGE" if cov > 0 else "RED"
    if with_model:
        items.append(("EBITDA / EPS Risk", status,
                      f"Consensus built on {with_model} of {total} analysts' models "
                      f"({'broad' if cov >= 0.8 else 'thin'} coverage)."))
    else:
        items.append(("EBITDA / EPS Risk", "RED",
                      f"NO analyst models on file — {covering} of {total} analysts actively cover "
                      f"{CT('ticker')}, but not one of their models has been ingested. Any 'consensus' "
                      f"computed here would be from the market feed's aggregate, not from models we hold."))

    surprises = db.load_json("earnings_surprise_log.json", [])
    if surprises:
        last = surprises[-1]
        gve = last.get("guidance_vs_embedded", "—")
        status = {"Beat": "GREEN", "Above": "GREEN", "In-line": "YELLOW", "Below": "ORANGE"}.get(gve, "GRAY")
        items.append(("Guidance Credibility", status, f"Last logged quarter ({last.get('quarter','—')}): guidance {gve} vs embedded expectation."))
    else:
        items.append(("Guidance Credibility", "GRAY", "No quarters logged yet in the Consensus Tracker (Earnings page)."))

    # Was GRAY/"not built yet" — but the 8-quarter PT-history log this needs
    # (pt_history.by_firm) already exists in the same seed data and is
    # actively used by markets_page.py's PT Drift Tracker chart (see
    # _render_pt_drift). Computation now lives in get_revision_momentum()
    # above so this tile and core/board_slides.py's board-slide export both
    # read the exact same 8-quarter drift result.
    rm = get_revision_momentum(period)
    items.append(("Revision Momentum", rm["status"], rm["full"]))
    return items


NDR_OBJECTIONS_KEY = "ndr_objections.json"


def log_ndr_objection(trip_name, objection="", narrative_gap=""):
    """Called from page_modules_nicegui/investors_page.py's Post-NDR Debrief
    form whenever a debrief records a key objection and/or narrative gap —
    this is the real data source _investor_narrative_risk() below was
    written to wait for (see this module's docstring: 'NDR-debrief
    objection logging... still have no real source anywhere in this app').
    Appends rather than overwrites, so KPI Understanding / Investor
    Objection Trend below can look at the log's history, not just the
    latest debrief. No-ops (doesn't append an empty entry) if both fields
    are blank — a debrief with nothing to log shouldn't pollute the trend
    with a hollow row."""
    objection = (objection or "").strip()
    narrative_gap = (narrative_gap or "").strip()
    if not objection and not narrative_gap:
        return
    log = db.load_json(NDR_OBJECTIONS_KEY, default=[])
    log.append({
        "trip": trip_name, "objection": objection, "narrative_gap": narrative_gap,
        "logged_at": datetime.now().isoformat(),
    })
    db.save_json(NDR_OBJECTIONS_KEY, log)


def _investor_narrative_risk(period="Q2 2026E"):
    items = [("Equity Story Clarity", "GRAY", "Subjective — no quantified source in this app.")]

    objections = db.load_json(NDR_OBJECTIONS_KEY, default=[])
    if objections:
        recent = objections[-5:]
        with_gap = sum(1 for o in recent if o.get("narrative_gap"))
        # YELLOW, not a fabricated GREEN/RED classification — this is real
        # logged data (an actual objection exists), but whether that's good
        # or bad news needs a human read, not a guessed sentiment score.
        # Same "honest signal over invented precision" approach as
        # core/fit_score.py's heuristic classes.
        items.append(("KPI Understanding", "YELLOW",
                       f"{len(objections)} objection(s) logged from NDR debriefs — most recent from \"{objections[-1]['trip']}\": "
                       f"\"{objections[-1]['objection'] or objections[-1]['narrative_gap']}\". Review in NDR Planner → Post-NDR Debrief."))
        items.append(("Investor Objection Trend", "YELLOW",
                       f"{with_gap} of the last {len(recent)} debrief(s) logged a narrative gap (a question the script doesn't "
                       f"currently answer) — feed these into the next Script Generation cycle's Q&A prep."))
    else:
        items.append(("KPI Understanding", "GRAY", "Not tracked — no logged investor objections on file yet."))
        items.append(("Investor Objection Trend", "GRAY", "Not tracked — same reason; populates once NDR debriefs start logging real objections."))

    # Alignment is only computable for analysts whose published PT we hold (pt on file);
    # the rest cover the name but we have no target to check Buy-rating/above-price against.
    with_pt = [a for a in CA() if a.get("pt") is not None]
    snap = market_data.get_snapshot(CT("ticker"))
    from core.consensus import get_consensus
    seed = get_consensus(get_active_client_id())
    ests = seed.get("period_estimates", {}).get(period, {})
    if with_pt and snap and snap.get("last_price"):
        # Prefer a logged model's Rating; fall back to the analyst's published rating on the registry.
        buy_count = sum(1 for a in with_pt if (ests.get(a["firm"], {}).get("Rating") or a.get("rating")) == "Buy")
        above_count = sum(1 for a in with_pt if a.get("pt") and a["pt"] > snap["last_price"])
        aligned = min(buy_count, above_count)
        status = "GREEN" if aligned == len(with_pt) else "YELLOW" if aligned > 0 else "ORANGE"
        items.append(("Analyst Message Alignment", status,
                       f"{buy_count}/{len(with_pt)} analyst(s) with a logged PT are Buy-rated, {above_count}/{len(with_pt)} with PT above last trade (${snap['last_price']:.2f})."))
    else:
        items.append(("Analyst Message Alignment", "GRAY", "Needs analyst ratings/PTs on file and a market snapshot."))
    return items


def _event_communication_risk():
    items = []

    ss = db.load_json("script_workflow_state.json", None)
    if ss and ss.get("stages"):
        stages = ss["stages"]
        complete = sum(1 for s in stages.values() if s.get("status") == "complete")
        pct = complete / len(stages) * 100 if stages else 0
        status = "GREEN" if pct >= 80 else "YELLOW" if pct >= 40 else "ORANGE" if pct > 0 else "RED"
        items.append(("Earnings Prep", status, f"Script Generation {pct:.0f}% through its 5 stages ({complete}/{len(stages)} complete)."))
    else:
        items.append(("Earnings Prep", "GRAY", "Script Generation hasn't been started yet (Earnings page)."))

    items.append(("Conference Readiness", "GRAY", "Not computed here — see Calendar for confirmed events; no structured readiness field wired in yet."))

    regfd = db.load_json("regfd_log.json", [])
    if regfd:
        open_high = sum(1 for e in regfd if e.get("risk") == "HIGH" and not e.get("reviewed"))
        open_8k = sum(1 for e in regfd if e.get("8k_flag") and not e.get("8k_resolved"))
        total_open = open_high + open_8k
        status = "GREEN" if total_open == 0 else "YELLOW" if total_open <= 1 else "ORANGE" if total_open <= 3 else "RED"
        items.append(("Disclosure Risk", status,
                       f"{total_open} open Reg FD item(s) — {open_high} unreviewed HIGH-risk, {open_8k} unresolved 8-K flag(s). See Reports → Reg FD."))
    else:
        items.append(("Disclosure Risk", "GRAY", "No Reg FD log entries yet (Reports → Reg FD)."))

    items.append(_qa_risk_topics_item())
    return items


def _qa_risk_topics_item():
    """Sourced from core.transcripts — an AI pass over the most recently
    ingested earnings call transcript that flags Q&A exchanges reading as
    analyst pushback/skepticism (see transcripts.py's summarize_transcript
    prompt). Stays GRAY if no transcript has been ingested yet, or one has
    been ingested but not yet summarized — this never guesses at Q&A
    content that wasn't actually captured."""
    try:
        from core import transcripts
        from config.client_config import CE
        quarter = CE().get("current_quarter") or None
        record = None
        if quarter:
            record = transcripts.get_transcript(quarter)
        if not record:
            # Fall back to the most recently ingested transcript (e.g. the
            # prior quarter's call, if the current quarter hasn't happened
            # yet) rather than assuming nothing exists at all.
            all_t = transcripts.list_transcripts()
            record = transcripts.get_transcript(all_t[0]["quarter"]) if all_t else None
        if not record:
            return ("Q&A Risk Topics", "GRAY", "No earnings call transcript ingested yet — see Earnings → Call Transcripts.")
        topics = record.get("qa_risk_topics")
        if topics is None:
            return ("Q&A Risk Topics", "GRAY",
                     f"Transcript on file for {record['quarter']}, but AI summary hasn't been run yet — "
                     f"see Earnings → Call Transcripts.")
        if not topics:
            return ("Q&A Risk Topics", "GREEN", f"{record['quarter']} call: no analyst pushback/skepticism flagged by AI review.")
        high = sum(1 for t in topics if t.get("severity") == "HIGH")
        med = sum(1 for t in topics if t.get("severity") == "MEDIUM")
        status = "RED" if high >= 2 else "ORANGE" if high == 1 else "YELLOW" if med else "GREEN"
        names = ", ".join(t.get("topic", "?") for t in topics[:3])
        return ("Q&A Risk Topics", status,
                 f"{record['quarter']} call: {len(topics)} flagged topic(s) — {names}{'...' if len(topics) > 3 else ''}.")
    except Exception as e:
        return ("Q&A Risk Topics", "GRAY", f"Transcript data unavailable ({e}).")


def _insider_selling_item():
    """Insider Selling Optics — now REAL, from core.insider_feed (SEC EDGAR Form
    4). GRAY only if no filings have been pulled for this client yet, not because
    the capability is missing."""
    try:
        from core import insider_feed
        itx = insider_feed.recent(limit=60)
        if not itx:
            return ("Insider Selling Optics", "GRAY",
                    "Form 4 monitoring is wired in (SEC EDGAR) — no filings pulled for this client yet; run a refresh.")
        nm = insider_feed.net_open_market()
        b, s = nm.get("buy_shares") or 0, nm.get("sell_shares") or 0
        if not (b or s):
            return ("Insider Selling Optics", "GREEN",
                    f"{len(itx)} recent Form 4(s) tracked — all routine grants/exercises, no open-market selling.")
        if (nm.get("net_shares") or 0) >= 0:
            return ("Insider Selling Optics", "GREEN",
                    f"Net open-market buying ({b:,.0f} bought vs {s:,.0f} sold) — a positive optic.")
        return ("Insider Selling Optics", "YELLOW",
                f"Net open-market selling ({s:,.0f} sold vs {b:,.0f} bought) — anticipate questions; "
                f"confirm any planned/10b5-1 sales.")
    except Exception as e:
        return ("Insider Selling Optics", "GRAY", f"Insider (Form 4) data unavailable ({e}).")


def _governance_reputation_risk():
    return [
        _insider_selling_item(),
        ("Activism Vulnerability", "GRAY", "Not tracked — no activist-screening data source in this app."),
        ("Management Credibility", "GRAY", "Not tracked — no quantified source for this in this app."),
        ("ESG / Governance Noise", "GRAY", "Not tracked — no ESG/governance monitoring in this app."),
    ]


def compute_scorecard(period="Q2 2026E"):
    """Returns the same {category_name: [(label, status, reason), ...]}
    shape markets_page.py has always used, so its existing overall-score
    math and rendering code don't need to change — only where this dict
    comes from does (previously data/seed/consensus_estimates.py's static
    risk_categories, now this function)."""
    return {
        "1. Market Signals": _market_signals(),
        "2. Ownership / Liquidity": _ownership_liquidity(),
        "3. Estimate / Guidance Risk": _estimate_guidance_risk(period),
        "4. Investor Narrative Risk": _investor_narrative_risk(period),
        "5. Event / Communication Risk": _event_communication_risk(),
        "6. Governance / Reputation Risk": _governance_reputation_risk(),
    }


# ─────────────────────────────────────────────────────────────────────────
# "Actionable IR signals" list
# ─────────────────────────────────────────────────────────────────────────
def _model_request_email(inactive, to):
    """Build a ready-to-send model-request email (recipients + subject + body,
    raw — the UI URL-encodes it into a mailto link) for the analysts with no
    model on file, so the IR lead can email them directly from the risk-signal
    dialog instead of being pointed off to another surface."""
    from config.client_config import CE, CI
    ce, ir = CE(), CI()
    quarter = ce.get("current_quarter", "the upcoming quarter")
    edate = ce.get("earnings_date", "")
    name, ticker = CT("name"), CT("ticker")
    ir_name = ir.get("name", "")
    ir_title = ir.get("title", "Investor Relations")
    first_names = ", ".join(a["name"].split()[0] for a in inactive)
    subject = f"{ticker} — Estimates / model request ahead of {quarter} earnings"
    body = (
        f"Hi {first_names},\n\n"
        f"Ahead of our {quarter} earnings" + (f" on {edate}" if edate else "") + ", I want to make sure you "
        f"have everything you need to publish an updated model on {name} ({ticker}) — we'd value having your "
        f"estimates reflected in consensus.\n\n"
        f"I'm happy to walk through our latest disclosures or set up a brief call, whatever is most useful. "
        f"Just let me know.\n\n"
        f"Best regards,\n{ir_name}\n{ir_title}\n{name} ({ticker})"
    )
    return {"to": to, "subject": subject, "body": body}


def _guidance_gap_email(con_rev, guid_mid, gap_pct):
    """Street-vs-guidance gap → a note to the CFO to align on whether to walk
    analysts toward guidance or revisit the range before the print."""
    from config.client_config import CE, CI, get_client
    ce, ir = CE(), CI()
    cfo = get_client().get("executives", {}).get("CFO", {})
    quarter = ce.get("current_quarter", "the quarter")
    ticker = CT("ticker")
    first = cfo.get("name", "").split()[0] if cfo.get("name") else "there"
    subject = f"{ticker} — Street {gap_pct:+.1f}% vs our {quarter} guidance midpoint"
    body = (
        f"Hi {first},\n\n"
        f"Flagging ahead of {quarter}: Street revenue consensus is ${con_rev:.1f}M against our ${guid_mid:.1f}M "
        f"guidance midpoint ({gap_pct:+.1f}%). Hitting our own number would screen as a miss versus the Street.\n\n"
        f"Worth a quick discussion on whether we walk analysts toward guidance or revisit the range before the "
        f"print. Free to connect?\n\n"
        f"Best,\n{ir.get('name','')}\n{ir.get('title','Investor Relations')}"
    )
    return {"to": [cfo["email"]] if cfo.get("email") else [], "subject": subject, "body": body}


def _outreach_upside_email(pt_avg, last_price, upside_pct):
    """PT upside → a ready outreach note the IR lead sends to a target investor.
    No fixed recipient (they pick the investor), so `to` is left blank — the
    dialog opens a compose window with the subject and body pre-filled."""
    from config.client_config import CE, CI
    ce, ir = CE(), CI()
    name, ticker = CT("name"), CT("ticker")
    quarter = ce.get("current_quarter", "the upcoming quarter")
    subject = f"{ticker} — {upside_pct:+.0f}% upside to consensus PT into {quarter}"
    body = (
        f"Hi,\n\n"
        f"Wanted to put {name} ({ticker}) on your radar ahead of {quarter} earnings. The stock last traded "
        f"around ${last_price:.2f} versus a consensus price target of ${pt_avg:.2f} — roughly {upside_pct:+.0f}% "
        f"upside on the Street's own numbers.\n\n"
        f"Happy to set up time with management or share our latest materials if useful.\n\n"
        f"Best regards,\n{ir.get('name','')}\n{ir.get('title','Investor Relations')}\n{name} ({ticker})"
    )
    return {"to": [], "subject": subject, "body": body}


def compute_actionable_signals(period="Q2 2026E"):
    from core.consensus import get_consensus
    seed = get_consensus(get_active_client_id())
    signals = []

    total = len(CA())
    # Same conflation as above: this counted INACTIVE analysts and called them "missing
    # models". Coverage status and model-on-file are different facts, and the fix
    # matters because an ACTIVE analyst with no model on file is the more actionable
    # gap — they publish, we just haven't collected it.
    ests_now = (get_consensus(get_active_client_id()).get("period_estimates", {}) or {}).get(period, {})
    no_model = [a for a in CA() if ests_now.get(a["firm"], {}).get("Revenue Est ($M)") is None]
    if no_model:
        names = ", ".join(a["name"].split()[-1] for a in no_model)
        _to = [a["email"] for a in no_model if a.get("email")]
        signals.append({
            "level": "red", "icon": "🔴",
            "title": f"{len(no_model)} of {total} analyst models missing — no consensus can be built from models we hold",
            "desc": f"{names} have no model on file — {len(no_model)} of {total}. No revenue or EPS "
                    f"consensus can be computed from models we hold, so any street figure shown in this "
                    f"platform comes from the market feed's aggregate, not from us. "
                    + (f"{len([a for a in no_model if a.get('covering', True)])} of them actively "
                       f"cover the stock and publish — those models are collectable today."
                       if any(a.get("covering", True) for a in no_model) else ""),
            "action": "Send model request emails to the analysts with no model on file",
            "email": _model_request_email(no_model, _to) if _to else None,
        })
    else:
        signals.append({
            "level": "green", "icon": "✅",
            "title": f"All {total} analyst models on file",
            "desc": "Full coverage — consensus reflects every covering analyst.",
            "action": "No action needed",
        })

    g = seed.get("period_guidance", {}).get(period, {})
    ests = seed.get("period_estimates", {}).get(period, {})
    ingested = {f: v for f, v in ests.items() if v.get("Rating") is not None}
    rev_vals = [v["Revenue Est ($M)"] for v in ingested.values() if v.get("Revenue Est ($M)") is not None]
    con_rev = sum(rev_vals) / len(rev_vals) if rev_vals else None
    if con_rev and g.get("Revenue Est ($M)"):
        gap_pct = (con_rev - g["Revenue Est ($M)"]) / g["Revenue Est ($M)"] * 100
        is_beat_risk = gap_pct > 1.5
        signals.append({
            "level": "amber" if is_beat_risk else "green", "icon": "⚠️" if is_beat_risk else "✅",
            "title": f"Street at ${con_rev:.1f}M vs your ${g['Revenue Est ($M)']:.1f}M guidance midpoint",
            "desc": f"Street revenue consensus is {gap_pct:+.1f}% {'above' if gap_pct > 0 else 'below'} guidance midpoint — "
                    f"{'hitting your own number would be a miss vs street' if is_beat_risk else 'in line with guidance'}.",
            "action": "Discuss with CFO: walk analysts toward guidance, or tighten guidance upward" if is_beat_risk else "In line — no action needed",
            "email": _guidance_gap_email(con_rev, g["Revenue Est ($M)"], gap_pct) if is_beat_risk else None,
        })

    pt_avg = _consensus_pt_avg(period)
    snap = market_data.get_snapshot(CT("ticker"))
    if pt_avg and snap and snap.get("last_price"):
        upside_pct = (pt_avg / snap["last_price"] - 1) * 100
        signals.append({
            "level": "green" if upside_pct >= 0 else "amber", "icon": "✅" if upside_pct >= 0 else "⚠️",
            "title": f"{upside_pct:+.0f}% {'upside' if upside_pct >= 0 else 'downside'} to consensus PT",
            "desc": f"Consensus PT of ${pt_avg:.2f} vs last trade of ${snap['last_price']:.2f}.",
            "action": "Lead with this in institutional outreach" if upside_pct > 50 else "Monitor",
            "email": _outreach_upside_email(pt_avg, snap["last_price"], upside_pct) if upside_pct > 50 else None,
        })

    # Insider activity (Form 4) — REAL now, from core.insider_feed (SEC EDGAR).
    # This is what retires the old "no insider-trading monitoring — blind spot"
    # seed card: we built the feed (it also backs the Today page's Insider
    # Activity section and the Investors insider feed), so the dashboard reports
    # the actual open-market buy/sell balance instead of claiming a blind spot.
    _ins = _insider_signal()
    if _ins:
        signals.append(_ins)

    # Static, documented gaps — no real data source exists in this app for the
    # REMAINING ones (short interest, activism screening); NDR-trip readiness
    # isn't wired into this computation yet either. Pulled from seed rather than
    # invented, same honesty policy as the GRAY items in the grid above. The
    # insider card is now dropped here (superseded by _insider_signal above).
    for s in seed.get("risk_signals", []):
        if "insider" in s.get("title", "").lower():
            continue
        if s.get("level") == "gray" or "NDR" in s.get("title", ""):
            signals.append(s)

    return signals


def _insider_signal():
    """A real actionable signal from the Form 4 feed (core.insider_feed), or None
    if the feed has no filings on file for this client yet (in which case we say
    nothing rather than claim a blind spot — the capability exists regardless)."""
    try:
        from core import insider_feed
        itx = insider_feed.recent(limit=60)
        if not itx:
            return None
        nm = insider_feed.net_open_market()
        b, s = nm.get("buy_shares") or 0, nm.get("sell_shares") or 0
        if not (b or s):
            return {
                "level": "green", "icon": "✅",
                "title": "Insider activity monitored — no open-market buys/sells to flag",
                "desc": f"{len(itx)} recent Form 4 filing(s) tracked from SEC EDGAR; all routine "
                        f"grants/exercises, no open-market trades.",
                "action": "No action — monitored on Today and the Investors insider feed.",
            }
        buying = (nm.get("net_shares") or 0) >= 0
        return {
            "level": "green" if buying else "amber",
            "icon": "✅" if buying else "⚠️",
            "title": f"Insider open-market activity — net {'buying' if buying else 'selling'} "
                     f"({b:,.0f} bought vs {s:,.0f} sold)",
            "desc": "Form 4 filings are monitored from SEC EDGAR. " + (
                "Net open-market buying is a positive signal to have ready for investor questions."
                if buying else
                "Net open-market selling — anticipate it and be ready to explain; unplanned selling "
                "can be misread by the market if it isn't framed."),
            "action": "Lead with insider buying in outreach" if buying
                      else "Confirm any planned/10b5-1 sales with CFO/GC and prepare an explanation",
        }
    except Exception:
        return None
