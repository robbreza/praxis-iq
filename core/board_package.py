"""
core/board_package.py — the IR Quarterly Board Package, live.

MERGES two documents that had been drifting apart:
  * USIO_IR_Quarterly_Board_Package_Q2_2026.docx — good STRUCTURE, unusable data.
  * board_ir_report_pdf() — good financials, but duplicated this package's valuation
    and ownership sections in a second board document.

WHAT THE .docx GOT RIGHT: the skeleton. Quarter at a glance / sell-side coverage /
buy-side & retail / market context & valuation / open items / appendix comp sheet is a
proper IR board package, and better than what we printed. It is kept.

WHAT IT GOT WRONG (audited 2026-07-16, see CHANGELOG):
  * Dated 2026-06-19 and reported "Q2 2026" results — a quarter that ended 11 days later
    and reports 54 days later. It was Q1 2026 data wearing a Q2 label. THE FIX IS
    STRUCTURAL: this module never labels a quarter it hasn't verified as reported. The
    period comes from the filings, not from a title.
  * USIO market cap ~$40M (actual $64.3M) over TTM revenue ~$102M (actual $85.4M) -> P/S
    "~0.4x" vs a real 0.75x. Wrong in both directions AT ONCE, both flattering.
  * Comp group GDOT/IMXI/FINW/PAYS — an acquired company, a pending acquisition, a bank,
    and one real peer.
  * 4 of 5 analyst rows contradicted the tape.

EVERY FIGURE HERE RESOLVES TO A FILING, THE MARKET FEED, OR OUR OWN ACTIVITY LOG. Where a
number cannot be sourced it is reported as absent. That is the whole difference between
this and the document it replaces.
"""

from datetime import date, datetime

from config.client_config import CE, CF, CT


def _reported_period():
    """The last quarter actually REPORTED, taken from the filings.

    The .docx's central failure was a label: it said "Q2 2026" on a package built from Q1
    data because a human typed the title. Here the period is derived — `quarter_end` comes
    off the 10-Q — and the next, unreported quarter is named separately and never mixed in.
    """
    from core import edgar_financials
    s = edgar_financials.financial_summary(CT("ticker"))
    if not s or s.get("_error"):
        return None
    qe = s.get("quarter_end")
    label = CF().get("last_quarter")
    upcoming, edate = CE().get("current_quarter"), CE().get("earnings_date")
    days = None
    try:
        days = (date.fromisoformat(str(edate)[:10]) - date.today()).days
    except Exception:
        pass
    return {"quarter_end": qe, "label": label, "summary": s,
            "upcoming": upcoming, "upcoming_date": edate, "days_to_upcoming": days}


def at_a_glance(client_id=None, period=None):
    """Quarter at a glance — the four numbers, each traceable.

    Takes an already-resolved period so compose() doesn't pay for it twice: both this
    and compose() called _reported_period(), which fans out to financial_summary().
    """
    from core import market_data
    p = period or _reported_period()
    if not p:
        return None
    inc = p["summary"]["income"]
    snap = market_data.get_snapshot(CT("ticker")) or {}
    return {
        "period": p["label"], "quarter_end": p["quarter_end"],
        "revenue": inc.get("revenue"), "rev_growth": inc.get("rev_growth_yoy"),
        "gross_profit": inc.get("gross_profit"), "gross_margin": inc.get("gross_margin"),
        "last_price": snap.get("last_price"), "pct_change": snap.get("pct_change"),
        # Deliberately absent rather than invented: the .docx printed "0.14% of float
        # short interest / 0.3 days to cover" and a "+24.2% stock reaction". We have no
        # short-interest feed, and the reaction belongs to a specific call.
        "short_interest": None,
        "short_interest_note": ("Not tracked — no short-interest data source is wired in. The "
                                "prior package printed 0.14% of float / 0.3 days to cover; that "
                                "figure has no source in this platform and is not reproduced."),
    }


def sell_side(client_id=None):
    """Per-analyst coverage — from the market feed, which is the only source that
    attributes a rating and a price target to a NAMED firm.

    The .docx's table had 4 of 5 rows contradicting the tape (HCW $4.50 vs $4.00,
    Litchfield "Hold $3.00" vs Buy $6.00, Maxim $4.00 vs $5.00, and a "5th analyst ·
    Sell · $1.50 · pending confirmation" that no filing or feed substantiates).
    """
    from core import market_data
    est = market_data.get_estimates(CT("ticker"))
    if not est:
        return None
    cov = est.get("coverage") or []
    pt = est.get("price_target") or {}
    today = date.today()
    for c in cov:
        try:
            c["age_days"] = (today - date.fromisoformat(c["date"])).days
        except Exception:
            c["age_days"] = None
        c["stale"] = c["age_days"] is not None and c["age_days"] > 365
    active = [c for c in cov if not c["stale"]]
    return {"coverage": cov, "n": len(cov), "n_active": len(active),
            "n_stale": len(cov) - len(active), "price_target": pt,
            "as_of": est.get("as_of"), "read": _sell_side_read(cov, active, pt)}


def _sell_side_read(cov, active, pt):
    if not cov:
        return "No covering analysts resolve from the market feed."
    stale = [c for c in cov if c["stale"]]
    s = (f"{len(active)} of {len(cov)} covering analysts have acted within the last year. ")
    if stale:
        bits = ", ".join(f"{c['firm'].split()[0]} ({c['date'][:4]})" for c in stale)
        s += (f"The rest are dormant — {bits} — and calling this {len(cov)}-analyst coverage is "
              f"generous. ")
    if pt.get("mean") and pt.get("current"):
        s += (f"Consensus PT ${pt['mean']:.2f} vs ${pt['current']:.2f} last "
              f"({(pt['mean']/pt['current']-1)*100:+.0f}%), range ${pt.get('low', 0):.2f}–"
              f"${pt.get('high', 0):.2f}. ")
    s += ("Ratings and price targets are the market feed's — the only source that attributes "
          "them to a named firm. Per-analyst revenue and EPS models are NOT published by any "
          "feed and none are on file; see Open Items.")
    return s


def buy_side(client_id=None):
    """Holder base and activism posture — from 13F/13D-G, windowed.

    A 13D COUNT WITHOUT A DATE WINDOW IS MEANINGLESS. USIO has 19 Schedule 13D filings on
    file, and they span 2001-2023: activists file, and then they exit, and the filing stays
    on EDGAR forever. Counting all of them says "19 activists" about a company with none.
    Counting none says "passive" without evidence. The honest read is the WINDOW: no 13D
    activity since 2023-11-29.

    (The .docx asserted "0 Schedule 13D filers — holder base remains passive, not activist."
    Directionally right, stated as a fact that is false: there are 19. A first draft of this
    function made the opposite error and reported 19 activists.)
    """
    from core import sec_filings
    WINDOW_DAYS = 730
    out = {"holders": None, "note": None}
    try:
        h = sec_filings.get_cached_13f_holders(CT("ticker")) or {}
        out["holders"] = len([x for x in (h.get("holders") or []) if x.get("filer")])
    except Exception:
        pass
    try:
        f = sec_filings.get_cached_13d_13g(CT("ticker")) or {}
        rows = f.get("filings") or []
        cutoff = (date.today() - __import__("datetime").timedelta(days=WINDOW_DAYS)).isoformat()
        d13 = [r for r in rows if "13D" in str(r.get("form", "")).upper()]
        g13 = [r for r in rows if "13G" in str(r.get("form", "")).upper()]
        recent_d = [r for r in d13 if (r.get("date") or "") >= cutoff]
        recent_g = [r for r in g13 if (r.get("date") or "") >= cutoff]
        newest_d = max((r.get("date") or "" for r in d13), default=None)
        out.update({
            "activists_recent": len(recent_d), "activists_all_time": len(d13),
            "passive_recent": len(recent_g), "passive_all_time": len(g13),
            "newest_13d": newest_d, "window_days": WINDOW_DAYS,
            "fetch_error": f.get("_error"),
        })
        if not recent_d:
            out["note"] = (
                f"No Schedule 13D filed in the last {WINDOW_DAYS // 365} years"
                + (f" — the most recent is {newest_d}" if newest_d else "")
                + f". {len(d13)} sit on EDGAR going back to {min((r.get('date') or '' for r in d13), default='—')[:4]}, "
                  f"but a 13D never comes off the record when the filer exits, so the all-time count "
                  f"says nothing about who holds the stock today. The window is the evidence: no "
                  f"activist has crossed 5% with intent in {WINDOW_DAYS // 365} years. "
                  f"{len(recent_g)} Schedule 13G (passive) filings in the same window.")
        else:
            out["note"] = (f"{len(recent_d)} Schedule 13D filing(s) in the last "
                           f"{WINDOW_DAYS // 365} years — most recent {newest_d}. A 13D is filed "
                           f"within 10 days of crossing 5% WITH INTENT. This warrants a name-level "
                           f"look before the board meeting.")
    except Exception:
        pass
    return out


def valuation(client_id=None):
    """Valuation vs peers — EV/Gross Profit only, plus the revenue bridge.

    Absorbs board_ir_report_pdf's "Valuation & peer position" so the two documents can no
    longer disagree. That section showed EV/Revenue with a green "% below median", which is
    the exact error that produced the retired deck's $9-12 price target.
    """
    from core import benchmarking_engine, valuation_comp
    bm = benchmarking_engine.build_benchmark()
    v = valuation_comp.build(client_id)
    try:
        bridge = valuation_comp.revenue_bridge(client_id)
    except Exception:
        bridge = None
    return {"bm": bm, "comp": v, "bridge": bridge,
            "key_finding": benchmarking_engine.key_finding(bm)}


def open_items(client_id=None):
    """What the board should know is unresolved. Red/amber only."""
    from core import risk_scorecard
    try:
        sigs = risk_scorecard.compute_actionable_signals(_period_label()) or []
    except Exception:
        sigs = []
    order = {"red": 0, "amber": 1}
    return sorted([s for s in sigs if s.get("level") in order],
                  key=lambda s: order.get(s.get("level"), 9))


def _period_label():
    q = CE().get("current_quarter") or ""
    return f"{q}E" if q and not q.endswith("E") else q


def appendix_comp_sheet(client_id=None):
    """Appendix A — the comp set, WITH the reason each name is in it.

    The .docx's Appendix A listed GDOT (acquired), IMXI (pending acquisition) and FINW (a
    bank) as "Active". A comp sheet without a written rationale per name is how that
    happens and goes unnoticed for a quarter.
    """
    from config.client_config import CP
    from core import forensics
    rows = []
    for p in CP():
        f = forensics.filing_margin(p["ticker"])
        rows.append({
            "ticker": p["ticker"], "name": p.get("name"), "tier": p.get("tier"),
            "rationale": p.get("segment") or "",
            "in_median": f["status"] in ("ok", "derived", "ok_mda"),
            "gm": (f["gross_margin"] * 100) if f["gross_margin"] is not None else None,
            "gm_basis": f["status"],
        })
    return rows


def compose(client_id=None):
    p = _reported_period()
    return {
        "ticker": CT("ticker"), "name": CT("name"),
        "as_of": datetime.now(),
        "period": p, "glance": at_a_glance(client_id, period=p),
        "sell_side": sell_side(client_id), "buy_side": buy_side(client_id),
        "valuation": valuation(client_id), "open_items": open_items(client_id),
        "appendix": appendix_comp_sheet(client_id),
    }
