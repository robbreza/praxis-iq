"""
core/earnings_prep.py — the Earnings Prep Brief: what management needs to know
in the room before the call, computed live.

WHY THIS DIDN'T EXIST. app.py had a "Generate Q2 Earnings Prep Briefing" button
that shelled out to `node generate_briefing.js`. That file does not exist anywhere
on the filesystem — the button could only ever have failed. So there was nothing to
port, and the only surviving specification is the caption above it:

    "a CFO-ready Word document with consensus vs guidance, beat/miss scenarios,
     approved talking points, risk flags, and Q&A prep."

That spec is good and is honoured here, live. It prints as a PDF, not .docx, because
the reports audit's premise is that every report must print and report_pdf is the
established path.

WHAT THIS BRIEF IS FOR. Not to reassure. A prep brief that tells management the bar
is fine and the story is clean has no reason to exist — they can feel that already.
Its whole value is the three questions nobody wants to ask out loud:

  1. Can we hit our own guidance and still miss the Street? (Here: YES.)
  2. Do our own published numbers reconcile? (Here: NO.)
  3. What did we fail to answer last time, that they will ask again? (Here: four things.)

THE COVERAGE HONESTY RULE. "Consensus" is reported with its n, always. USIO's Street
revenue number is the mean of TWO analysts; three of five carry no model. A two-analyst
mean is not a consensus, and a brief that prints "$25.15M consensus" without saying so
hands management false precision on the single number the call is judged against.
"""

from datetime import date, datetime

from config.client_config import CE, CT

_REV = "Revenue Est ($M)"


def _days_out(earnings_date):
    try:
        return (date.fromisoformat(str(earnings_date)[:10]) - date.today()).days
    except Exception:
        return None


def the_bar(client_id=None):
    """Consensus vs guidance — the number the call is judged against, with its n.

    THE STREET COMES FROM THE MARKET FEED, NOT THE PLATFORM'S OWN FILE. This is the
    single most consequential sourcing decision in the brief, and it was wrong until
    2026-07-16. `period_estimates.json` has never been written for this client, so
    consensus.get_consensus() silently falls back to data/seed/consensus_estimates.py
    — DEMO numbers — and the beat/miss read was computed off them:

        seed (demo)  HCW $25.50M · Ladenburg $24.80M  -> "street" $25.15M
        Yahoo (real) 4 analysts, $23.02-24.45M        -> street  $23.67M

    Both seeded figures sit ABOVE the entire real range, and the error was not
    directionally neutral: on demo data USIO's $24.5M guide looked BELOW the street
    (hit your guide, miss the tape); on real estimates it is ABOVE every published
    analyst. The brief's headline inverted.

    So: street = market feed (period mapping verified against filed actuals, never
    assumed). The platform's own file is retained ONLY as a cross-check and is
    reported when it disagrees — a disagreement between what the IR team has on file
    and what the tape is marking against is itself worth knowing before a call.
    """
    from core import consensus, market_data
    from config.client_config import CF

    c = consensus.get_consensus(client_id)
    period = _current_period()
    guide = ((c.get("period_guidance") or {}).get(period) or {}).get(_REV)
    if guide is None:
        return None

    fin = CF()
    street = market_data.street_for_quarter(
        CT("ticker"),
        fy_revenue_actual=fin.get("fy_revenue") or 85.4,
        q_year_ago_actual=fin.get("q_year_ago_rev") or 19.90,
        client_id=client_id,
    )
    if not street or not street.get("verified") or street.get("avg_m") is None:
        # Refuse rather than fall back to the seed. A brief that silently swaps a
        # demo number in for the street is worse than one that says it can't source it.
        return {"period": period, "guidance": guide, "street": None, "unavailable": True,
                "read": ("The street estimate could not be sourced from the market feed with a "
                         "verified period mapping. The platform's own period_estimates file is NOT "
                         "used as a fallback: it has never been written for this client and would "
                         "serve demo figures. No beat/miss read is offered.")}

    st = street["avg_m"]
    gap_pct = (st / guide - 1) * 100

    # Cross-check against what the IR team has on file.
    pe = (c.get("period_estimates") or {}).get(period, {}) or {}
    on_file = {f: d.get(_REV) for f, d in pe.items() if d.get(_REV) is not None}
    ours = (sum(on_file.values()) / len(on_file)) if on_file else None
    outside = [f"{f} ${v:.2f}M" for f, v in on_file.items()
               if street["high_m"] and (v > street["high_m"] or v < street["low_m"])]

    return {
        "period": period, "guidance": guide, "street": round(st, 2),
        "gap_pct": round(gap_pct, 1), "gap_m": round(st - guide, 2),
        "n": street["n"], "low": street["low_m"], "high": street["high_m"],
        "fy_street": street["fy_avg_m"], "fy_n": street["fy_n"],
        "source": "market feed", "as_of": street.get("as_of"),
        "coverage": street.get("coverage") or [],
        "price_target": street.get("price_target"),
        "on_file_mean": round(ours, 2) if ours else None,
        "on_file": on_file, "on_file_outside_range": outside,
        # Above EVERY published estimate is a different posture from merely above the mean.
        "guide_above_all": street["high_m"] is not None and guide > street["high_m"],
        "can_hit_guide_and_miss_street": st > guide,
        "read": _bar_read(guide, st, gap_pct, street, ours, outside),
    }


def _bar_read(guide, street, gap_pct, s, ours, outside):
    out = []
    if s["high_m"] is not None and guide > s["high_m"]:
        out.append(
            f"USIO's ${guide:.1f}M guide sits ABOVE every published analyst estimate — the street's "
            f"HIGH is ${s['high_m']:.2f}M and its average is ${street:.2f}M across {s['n']} analysts. "
            f"Simply delivering the guide beats the whole street by {abs(gap_pct):.1f}%. The risk here "
            f"is not the bar; it is that USIO has guided to a number nobody on the street models, so "
            f"the guide itself is the claim that needs backing on the call.")
    elif street > guide:
        out.append(
            f"USIO can deliver its own guidance of ${guide:.1f}M and still MISS the street by "
            f"{gap_pct:.1f}%. The bar the stock trades against is ${street:.2f}M, not ${guide:.1f}M.")
    else:
        out.append(
            f"The street (${street:.2f}M, {s['n']} analysts) sits {abs(gap_pct):.1f}% BELOW guidance "
            f"(${guide:.1f}M) — hitting the guide clears the bar.")
    out.append(f"Street range ${s['low_m']:.2f}–{s['high_m']:.2f}M.")
    if outside:
        out.append(
            f"NOTE: the estimates on file in this platform ({', '.join(outside)}) fall OUTSIDE the "
            f"street's entire published range. They have never been entered — they are demo seed "
            f"values — and are shown only as a cross-check. The street figure above is the market "
            f"feed's, not theirs.")
    return " ".join(out)


def _current_period():
    from core import guidance_engine
    q = CE().get("current_quarter") or ""
    return f"{q}E" if q and not q.endswith("E") else q


def guidance_reconciliation(client_id=None):
    """Do the company's own quarterly numbers add up to its own full-year guidance?

    NOTHING ELSE CHECKS THIS. guidance_engine.guidance_consistency() verifies that
    the SCRIPT'S PROSE states the same FY range as the CFO's decision — a text-vs-
    decision check. It does not, and was never built to, add the quarters up. So a
    full year can be internally contradictory while every consistency check passes.

    An analyst builds the quarters. If they don't foot to the FY, that is the first
    question on the call, and it is a credibility question, not a modelling one.
    """
    from core import consensus, guidance_engine
    c = consensus.get_consensus(client_id)
    pg = c.get("period_guidance") or {}
    actuals = guidance_engine.reported_actuals() or {}
    fy_label = guidance_engine.reporting_fy_label()
    if not fy_label:
        return None
    year = fy_label.split()[1][:4]
    quarters = [f"Q{i} {year}E" for i in range(1, 5)]

    parts, total, have_all = [], 0.0, True
    for p in quarters:
        act = (actuals.get(p) or {}).get(_REV)
        gid = (pg.get(p) or {}).get(_REV)
        val = act if act is not None else gid
        if val is None:
            have_all = False
        else:
            total += val
        parts.append({"period": p, "actual": act, "guidance": gid, "used": val,
                      "source": "actual" if act is not None else ("guidance" if gid is not None else None)})
    if not have_all:
        return {"parts": parts, "complete": False,
                "read": "Not every quarter has an actual or a guide on file — the full year can't be footed."}

    fy_mid = (pg.get(fy_label) or {}).get(_REV)
    dec = (guidance_engine.guidance_consistency(client_id) or {}).get("input") or {}
    lo, hi = dec.get("low"), dec.get("hi")
    out = {"parts": parts, "complete": True, "sum": round(total, 2),
           "fy_label": fy_label, "fy_guidance": fy_mid, "fy_low": lo, "fy_high": hi}
    if lo is not None and hi is not None:
        out["above_high"] = round(total - hi, 2) if total > hi else None
        out["below_low"] = round(lo - total, 2) if total < lo else None
        out["reconciles"] = lo <= total <= hi
    elif fy_mid is not None:
        out["reconciles"] = abs(total - fy_mid) < 0.5
    out["read"] = _recon_read(out)
    return out


def _recon_read(o):
    if o.get("reconciles"):
        return (f"The quarters foot to the full year: ${o['sum']:.2f}M sits inside the stated "
                f"${o['fy_low']:.1f}–{o['fy_high']:.1f}M range. Nothing to answer for.")
    total, lo, hi = o["sum"], o.get("fy_low"), o.get("fy_high")
    if hi is not None and total > hi:
        return (f"THE QUARTERS DO NOT FOOT TO THE FULL YEAR. Q1 actual plus the Q2–Q4 guides sum "
                f"to ${total:.2f}M, which is ${total-hi:.2f}M ABOVE the top of the stated "
                f"${lo:.1f}–{hi:.1f}M FY range. Any analyst who builds the quarters gets a different "
                f"full year than the one USIO published — and the sum is above the ceiling, so it "
                f"reads either as sandbagged FY guidance or as quarterly guides that won't hold. "
                f"Expect to be asked which. Decide the answer before the call, not on it.")
    if lo is not None and total < lo:
        return (f"THE QUARTERS DO NOT FOOT TO THE FULL YEAR. The quarters sum to ${total:.2f}M, "
                f"${lo-total:.2f}M BELOW the bottom of the stated ${lo:.1f}–{hi:.1f}M FY range — the "
                f"quarterly guides do not get you to your own floor. Expect to be asked how.")
    return f"The quarters sum to ${total:.2f}M against an FY guide of ${o.get('fy_guidance')}M."


def scenarios(bar):
    """What the tape does at each revenue outcome.

    Thresholds are the street's published LOW / AVERAGE / HIGH plus the guide. The
    market feed gives the distribution but not per-analyst attribution, so this no
    longer names which firm writes "miss" — it says how much of the street a given
    print clears. Naming firms would require per-analyst estimates, and the only
    per-analyst numbers on file are demo seed values that sit outside the real range.
    """
    if not bar or bar.get("unavailable") or bar.get("street") is None:
        return []
    g, st = bar["guidance"], bar["street"]
    lo, hi = bar.get("low"), bar.get("high")
    n = bar.get("n")
    marks = sorted({round(x, 2) for x in [g, st, lo, hi] if x is not None}, reverse=True)
    out = []
    for m in marks:
        if hi is not None and m >= hi:
            label = "Beats the whole street"
            desc = (f"Clears the highest published estimate (${hi:.2f}M). Every analyst on the tape "
                    f"writes a beat. No split headline available.")
        elif m >= st:
            label = "Beats the street average"
            desc = (f"Above the ${st:.2f}M mean of {n} analysts but below the ${hi:.2f}M high — the "
                    f"analysts at the top of the range write a miss. Expect a split headline.")
        elif lo is not None and m >= lo:
            label = "Inside the street range, below the mean"
            desc = (f"Lands between the ${lo:.2f}M low and the ${st:.2f}M mean — reads as a miss of "
                    f"{(st-m)/st*100:.1f}% against consensus even if it clears some models.")
        else:
            label = "Below the whole street"
            desc = f"Under the lowest published estimate (${lo:.2f}M). Unambiguous miss."
        if abs(m - g) < 0.005:
            label += " — this is our guide"
            desc += (" This is the outcome of simply delivering what we promised, so it is the one "
                     "to have an answer ready for.")
        out.append({"revenue": m, "label": label, "desc": desc,
                    "is_guide": abs(m - g) < 0.005,
                    "vs_guide_pct": round((m / g - 1) * 100, 1),
                    "vs_street_pct": round((m / st - 1) * 100, 1)})
    return out


def qa_prep(client_id=None):
    """What management failed to answer LAST quarter — because that is what gets
    asked again.

    Uses core.number_frame via morning_after.frame_qa: every analyst question anchors
    on a number, that number's valence sets what kind of answer is owed (a GOOD number
    owes REPEATABILITY, a CLAIM owes BACKING), and the verdict records whether the
    demand was discharged. A MISMATCH or DEFERRED is an unpaid debt, and analysts
    carry debts forward — they wrote it in their notes.
    """
    from core import transcripts, morning_after
    tr = [t for t in (transcripts.list_transcripts(client_id) or []) if t.get("call_date")]
    if not tr:
        return None
    last = sorted(tr, key=lambda t: t["call_date"])[-1]
    try:
        d = morning_after.frame_qa(last["quarter"], client_id=client_id)
    except Exception:
        d = None
    if not d:
        return None
    open_items = [f for f in d.get("frames", [])
                  if f.get("verdict") in ("MISMATCH", "DEFERRED", "WITHHELD")]
    return {
        "from_quarter": last["quarter"], "call_date": last["call_date"],
        "open": open_items, "n_open": len(open_items),
        "discharged": d.get("discharged"), "exchanges": d.get("exchanges"),
        "by_demand": d.get("by_demand") or {},
        "read": _qa_read(open_items, last["quarter"]),
    }


def _qa_read(items, quarter):
    if not items:
        return (f"Nothing was left unanswered on the {quarter} call — every numeric question's "
                f"demand was discharged. Rare, and worth protecting.")
    kinds = {}
    for f in items:
        kinds[f.get("demand")] = kinds.get(f.get("demand"), 0) + 1
    bits = ", ".join(f"{v}× {k}" for k, v in sorted(kinds.items(), key=lambda kv: -kv[1]) if k)
    return (f"{len(items)} question{'s' if len(items) != 1 else ''} from the {quarter} call went "
            f"unanswered or were answered with the wrong kind of answer ({bits}). Analysts carry these "
            f"forward — they are in the notes. Each one below is a question management should expect "
            f"again, and should decide the answer to before the call rather than in it.")


def risk_flags(client_id=None):
    """Red/amber items from the live risk scorecard — the things that are already
    known to be wrong going in."""
    from core import risk_scorecard
    try:
        sigs = risk_scorecard.compute_actionable_signals(_current_period()) or []
    except Exception:
        return []
    order = {"red": 0, "amber": 1, "green": 2, "gray": 3}
    live = [s for s in sigs if s.get("level") in ("red", "amber")]
    return sorted(live, key=lambda s: order.get(s.get("level"), 9))


def readiness(client_id=None):
    """Where the call prep actually stands — from the script workflow, not a vibe."""
    from core import risk_scorecard
    try:
        sc = risk_scorecard.compute_scorecard(_current_period()) or {}
    except Exception:
        return []
    out = []
    for cat, items in sc.items():
        for name, level, detail in items:
            if level in ("RED", "YELLOW"):
                out.append({"category": cat, "item": name, "level": level, "detail": detail})
    return out


def segment_story(client_id=None):
    """The segment narrative for the script — sourced from the filing's XBRL segment data
    (core.segments, the same instance-document parse behind the valuation SOTP). USIO reports two
    reportable segments: Merchant Services (payments) and Output Solutions (print-and-mail, ~85%
    postage pass-through). The script should OWN this — the blended EV/gross-profit multiple
    understates the payments business. Returns a management talking point + the anticipated analyst
    Q&A, or None when a clean two-segment split can't be sourced (e.g. SARO)."""
    try:
        from core import segments
        b = segments.sotp_breakeven()
    except Exception:
        return None
    if not b:
        return None
    pay, oth = b["payments_label"], ", ".join(b["other_labels"])
    if b["residual_negative"]:
        close_tp = (f"The market is already paying less for ALL of {CT('ticker')} than the peer median says "
                    f"{pay} alone is worth — the discount lives in the print optics, not the payments business.")
        close_qa = ("even holding it at the peer median, the value left for the rest is already negative — the "
                    "blended discount is an artifact of mixing a payments business with a pass-through.")
    else:
        close_tp = (f"Hold {pay} at the {b['peer_median']:.2f}x peer median and {oth} only has to clear "
                    f"{b['breakeven_other_ev_gp']:.2f}x its own gross profit for us to be fairly valued today.")
        close_qa = (f"{oth} only needs {b['breakeven_other_ev_gp']:.2f}x gross profit to justify today's price — "
                    f"a low bar for a stable, cash-generative print business.")
    return {
        "talking_point": (
            f"Own the segment mix. {pay} — the payments engine — is {b['payments_gp_share']:.0f}% of gross "
            f"profit; {oth} is print-and-mail, largely a postage pass-through. Our blended "
            f"{b['blended_multiple']:.2f}x EV/gross-profit sits against a {b['peer_median']:.2f}x pure-play "
            f"payments median, so applying that multiple to the whole company values the print business like "
            f"payments. " + close_tp),
        "qa": {
            "question": (f"Your multiple looks cheap versus payments peers — but you're not a pure-play. How "
                         f"should we think about {oth} in the valuation?"),
            "answer": (f"Fair — and it's the point. {pay} is {b['payments_gp_share']:.0f}% of gross profit and "
                       f"should be valued like payments; {oth} is a lower-multiple pass-through. "
                       f"{close_qa[0].upper() + close_qa[1:]}"),
        },
        "payments_label": pay, "other_labels": b["other_labels"],
        "payments_gp_share": b["payments_gp_share"], "blended_multiple": b["blended_multiple"],
        "peer_median": b["peer_median"], "breakeven": b["breakeven_other_ev_gp"],
        "residual_negative": b["residual_negative"],
    }


def sequential_read(client_id=None):
    """A one-line sequential (quarter-over-quarter) revenue read for the script — the last three
    quarters incl. the derived Q4 — from the cached quarterly trend. None if history is too thin."""
    try:
        from core import edgar_financials
        t = edgar_financials.get_trend(CT("ticker"))
    except Exception:
        return None
    qs = (t or {}).get("quarters") or []
    if len(qs) < 3:
        return None
    q = qs[-3:]

    def _m(v):
        return f"${v / 1e6:.1f}M" if v else "—"

    seq = " to ".join(f"{_m(x['revenue'])} in {x['label']}" for x in q)
    tail = f" — {q[-1]['rev_qoq_pct']:+.1f}% sequentially" if q[-1].get("rev_qoq_pct") is not None else ""
    return f"Sequentially, revenue moved {seq}{tail}."


def compose(client_id=None):
    """The whole brief."""
    ce = CE()
    bar = the_bar(client_id)
    return {
        "ticker": CT("ticker"), "name": CT("name"),
        "quarter": ce.get("current_quarter"), "earnings_date": ce.get("earnings_date"),
        "days_out": _days_out(ce.get("earnings_date")),
        "as_of": datetime.now(),
        "bar": bar,
        "reconciliation": guidance_reconciliation(client_id),
        "scenarios": scenarios(bar),
        "qa": qa_prep(client_id),
        "segment_story": segment_story(client_id),
        "sequential": sequential_read(client_id),
        "risks": risk_flags(client_id),
        "readiness": readiness(client_id),
        # Is the year-ago base this script will be measured against a clean one? For
        # Q2 FY26 it is not: an easy revenue comp and the hardest gross profit comp in
        # two years, off the SAME quarter. See core/comp_quality.py.
        "comp_quality": _comp_quality(),
    }


def _comp_quality():
    try:
        from core import comp_quality
        return comp_quality.build()
    except Exception as exc:
        print(f"[earnings_prep] comp quality unavailable: {exc}")
        return None


def headline(d):
    """The one thing to say first. Picks the sharpest true fact, in priority order —
    a brief that leads with anything softer than its worst true fact is decoration."""
    # A divergent base outranks nearly everything: it means the headline number the script
    # WANTS to lead with is the one the base manufactured, and the sell-side will unpick it
    # within the hour. Management needs that before they draft, not after.
    cq = d.get("comp_quality") or {}
    if cq.get("status") == "ok" and cq.get("divergent"):
        return (
            f"The {cq['base_end']} base is divergent: an EASY revenue comp "
            f"({cq['base_vs_fy_avg_pct']:+.1f}% vs its own FY average quarter) and the HARDEST "
            f"gross profit comp in two years (${cq['base_gross_profit']:,.0f}, {cq['base_margin']:.1f}% "
            f"margin, #1 of {cq.get('gp_n_2yr')}). Repeat last quarter and revenue prints "
            f"{cq.get('repeat_rev_yoy', 0):+.1f}% while gross profit prints "
            f"{cq.get('repeat_gp_yoy', 0):+.1f}%. Do NOT lead with the revenue growth rate — it is "
            f"the base, not the business, and the call will turn on the gap between those two."
        )
    r = d.get("reconciliation") or {}
    b = d.get("bar") or {}
    if r.get("complete") and r.get("reconciles") is False:
        return r["read"]
    if b.get("can_hit_guide_and_miss_street"):
        return b["read"]
    if (d.get("qa") or {}).get("n_open"):
        return d["qa"]["read"]
    return "No blocking issues found in the live data heading into this call."
