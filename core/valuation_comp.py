"""
core/valuation_comp.py — the valuation comp table, and the number it exists to produce:
what USIO is worth if the market applied its peers' own multiple to USIO's own gross profit.

WHY EV/GROSS PROFIT IS THE SPINE OF THIS TABLE
Because it is the one multiple in the table that survives this peer set's accounting.
USIO reports revenue GROSS as a principal (10-K filed 2026-03-18, verified in
core.forensics), booking interchange it never keeps. Peers vary — some gross, some
net, several mixed per-contract under ASC 606. That makes EV/Revenue and gross margin
non-comparable across these names. EV/Gross Profit is immune, and the algebra is why:

    EV/GP = (EV / Revenue) / (GrossProfit / Revenue) = EV / GrossProfit

Revenue cancels. Whatever presentation basis a filer chose, it inflates revenue and
cost of revenue equally, leaves gross profit untouched, and drops out of the ratio.
So EV/Revenue and gross margin are carried in this table as CONTEXT and are explicitly
marked non-comparable; EV/Gross Profit is what the implied value is computed from, and
it is the only multiple this module will rank on.

WHAT THIS MODULE WILL NOT DO
Report a median EV/EBITDA for USIO. USIO's EBITDA is negative, so the multiple is a
meaningless negative number (~-292x) that would look like a data error in a board
packet and could be mistaken for a valuation. It is surfaced as "n/m", never averaged.

Medians are PRIMARY peers only. The reference large caps (FI/GPN/TOST) set the industry
bar but are not valuation comps — you do not apply a $100B processor's multiple to a
micro cap.
"""

import statistics

from config.client_config import CT
from core import benchmarking_engine

# forensics statuses whose gross profit came from the filer's own annual report.
# Anything else does not enter this table's EV/Gross Profit at all.
_FILING_OK = ("ok", "derived", "ok_mda")


def _median(vals):
    v = [x for x in vals if x is not None]
    return statistics.median(v) if v else None


def _row(r, forensic=None):
    """One comp-table row.

    EV/Gross Profit is computed as EV ÷ the filer's OWN gross profit — one market
    input, one filing input, and no vendor margin in between. The engine's `ev_gp`
    (EV/Rev ÷ vendor gross margin) is deliberately NOT used: it silently inherited
    Yahoo's margin, which for FOUR read 35.1% against a filed 32.4%, and for CASS
    invented 47.6% for a company whose 10-K never uses the phrase "gross profit".

    Where the filer reports no gross profit at all (CASS, GDOT — both banks), EV/GP
    is None. The metric does not exist for them; that is a fact about the business,
    not a data gap, and they drop out of the median on those grounds.
    """
    ev, mc = r.get("enterprise_value"), r.get("market_cap")
    fx = forensic or {}
    gp = fx.get("gross_profit") if fx.get("status") in _FILING_OK else None
    ev_gp = (ev / gp) if (ev and gp and ev > 0) else None
    return {
        "ticker": r["ticker"], "name": r.get("name") or "", "is_client": r.get("is_client", False),
        "tier": r.get("tier", "primary"), "segment": r.get("segment", ""),
        "closest_analog": r.get("closest_analog", False),
        "market_cap": mc, "enterprise_value": ev,
        "net_debt": (ev - mc) if (ev is not None and mc is not None) else None,
        "ev_rev": r.get("ev_rev"), "ev_gp": ev_gp,
        "gross_margin": (fx.get("gross_margin") * 100) if fx.get("gross_margin") is not None else None,
        "gm_source": "filing" if gp else (r.get("gm_source") or "—"),
        "vendor_gross_margin": r.get("gross_margin"),
        "rev_growth": r.get("rev_growth"),
        "gross_profit": gp, "gp_period": fx.get("period"),
        "revenue": fx.get("revenue"),
        "ev_excluded": r.get("ev_excluded", False),
        "gm_basis": fx.get("status"), "gm_detail": fx.get("detail"),
        # Carried through so the table can show whether the EV is rebuilt at the live
        # price or fell back to the one cached with the fundamentals (up to 24h old).
        "ev_is_live": r.get("ev_is_live"),
        "shares_outstanding": r.get("shares_outstanding"),
    }


def implied_value(usio_row, median_gp):
    """The money question: apply the peer median EV/Gross Profit to USIO's OWN gross
    profit, and see what the equity is worth.

    Works off EV so the capital structure is handled honestly, then bridges back to
    equity through net debt. USIO carries net cash, so the equity upside is slightly
    WIDER than the EV upside — dropping that bridge would understate it, and inventing
    a share count to quote a price target would add a number we don't need: the
    percentage is the claim.
    """
    ev, mc = usio_row["enterprise_value"], usio_row["market_cap"]
    gp, cur = usio_row["gross_profit"], usio_row["ev_gp"]
    if not (ev and mc and gp and cur and median_gp):
        return None
    implied_ev = gp * median_gp
    net_debt = ev - mc
    implied_equity = implied_ev - net_debt
    return {
        "current_ev": ev, "current_equity": mc, "net_debt": net_debt,
        "gross_profit": gp, "current_multiple": cur, "peer_median_multiple": median_gp,
        "implied_ev": implied_ev, "implied_equity": implied_equity,
        "upside_pct": (implied_equity / mc - 1) * 100,
        "rerate_needed": median_gp - cur,
    }


def sensitivity(usio, primary):
    """How much of the discount would survive if a non-filing-backed peer set the median.

    HISTORY, KEPT BECAUSE IT IS THE POINT: this used to fire. When peer gross margins
    came from Yahoo, CASS (5.8x) and FOUR (5.9x) sat immediately above USIO with
    vendor-constructed margins, and the implied upside swung +4% to +45% on whether
    they were allowed into the median. That range was the honest answer AT THE TIME —
    and it was the thing that made going to the filings worth doing.

    Reading the filings resolved it rather than hedging it:
      * FOUR discloses GAAP gross profit in its MD&A ($1,354M FY2025 -> 32.4%, vs
        Yahoo's 35.1%). It is filing-backed and stays in.
      * CASS's 10-K uses the phrase "gross profit" ZERO times — it is a bank. The
        metric does not exist, so it leaves the median on those grounds, not on ours.

    So every peer in the median is now filing-backed, `unbacked` is empty, and this
    returns None. It stays wired in as a live tripwire: if a future peer's gross
    profit ever falls back to a vendor number, the range reappears in the headline
    automatically instead of a point estimate quietly absorbing it.
    """
    have = [p for p in primary if p["ev_gp"] is not None]
    backed = [p for p in have if p["gm_basis"] in _FILING_OK]
    unbacked = [p for p in have if p["gm_basis"] not in _FILING_OK]
    if not backed or not unbacked:
        return None
    m_all, m_backed = _median([p["ev_gp"] for p in have]), _median([p["ev_gp"] for p in backed])
    i_all, i_backed = implied_value(usio, m_all), implied_value(usio, m_backed)
    if not (i_all and i_backed):
        return None
    return {
        "median_all": m_all, "n_all": len(have),
        "median_backed": m_backed, "n_backed": len(backed),
        "backed": [p["ticker"] for p in sorted(backed, key=lambda r: r["ev_gp"])],
        "unbacked": [{"ticker": p["ticker"], "ev_gp": p["ev_gp"], "gross_margin": p["gross_margin"],
                      "gm_basis": p["gm_basis"]} for p in sorted(unbacked, key=lambda r: r["ev_gp"])],
        "upside_all": i_all["upside_pct"], "upside_backed": i_backed["upside_pct"],
        "implied_equity_all": i_all["implied_equity"],
        "implied_equity_backed": i_backed["implied_equity"],
        "robust": abs(i_all["upside_pct"] - i_backed["upside_pct"]) < 15,
        "note": (
            f"EV/Gross Profit = (EV/Revenue) ÷ gross margin, so each peer's multiple inherits its "
            f"margin's provenance. {' and '.join(p['ticker'] for p in unbacked)} take their gross "
            f"margin from market data, not a filing — and they are the two peers sitting immediately "
            f"above {CT('ticker')}. Restricting the median to the {len(backed)} filing-backed peers "
            f"({', '.join(p['ticker'] for p in sorted(backed, key=lambda r: r['ev_gp']))}) moves it "
            f"from {m_all:.2f}x to {m_backed:.2f}x and the implied upside from "
            f"{i_all['upside_pct']:+.0f}% to {i_backed['upside_pct']:+.0f}%. The discount is real "
            f"either way, but its SIZE is not robust — treat it as a range, not a point."),
    }


def excluded_impact(usio, primary, client_id=None):
    """Peers OUT of the median ENTIRELY — and what including them would do.

    THE GAP THIS CLOSES. sensitivity() above only inspects peers that HAVE an ev_gp. A
    peer excluded outright has ev_gp = None, so it never enters `have` and the function
    is structurally blind to it. That blindness had a price: on 2026-07-16 IIIV and PRTH
    were both excluded as `stale`, sensitivity() returned None — reporting the answer as
    ROBUST — while including them would have moved the median 3.13x -> 3.74x and the
    implied read from **-3% to +16%**. The single largest open question on the page was
    invisible to the function whose entire job is finding open questions.

    Two kinds of exclusion, and they are not the same:

      * STALE — the filer HAS a gross profit, it is just old (IIIV last tagged FY2023).
        A real number exists, so the impact CAN be sized. Sizing it is a hypothetical and
        is labelled as one: it asks "if that stale margin still held, where would the
        median be?" — which is the question that tells you whether reading the current
        10-K is worth an hour.
      * NO GROSS PROFIT LINE — the filer reports none at all (CASS, GDOT: banks). No
        figure exists, at any vintage, so the impact CANNOT be sized and saying "we don't
        know" is the only honest output. Do not let a vendor number in through this door;
        that is the error this module exists to prevent.

    Returns None when nothing is excluded — the common, healthy case.
    """
    from core import forensics
    out_rows = [p for p in primary if p.get("ev_gp") is None]
    if not out_rows:
        return None
    inside = [p for p in primary if p.get("ev_gp") is not None]
    base_med = _median([p["ev_gp"] for p in inside])
    base_imp = implied_value(usio, base_med) if base_med else None

    sizable, unsizable = [], []
    for p in out_rows:
        f = forensics.filing_margin(p["ticker"])
        ev, gp = p.get("enterprise_value"), f.get("gross_profit")
        if f.get("status") == "stale" and ev and gp and ev > 0:
            sizable.append({
                "ticker": p["ticker"], "reason": "stale",
                "hypothetical_ev_gp": ev / gp,
                "vintage": f.get("period"), "gross_margin": (f.get("gross_margin") or 0) * 100,
                "detail": f.get("detail"),
            })
        else:
            unsizable.append({
                "ticker": p["ticker"], "reason": f.get("status"),
                "detail": f.get("detail"),
            })

    res = {"excluded": [p["ticker"] for p in out_rows], "sizable": sizable,
           "unsizable": unsizable, "base_median": base_med, "n_inside": len(inside)}

    if sizable and base_imp:
        with_them = _median([p["ev_gp"] for p in inside] + [s["hypothetical_ev_gp"] for s in sizable])
        imp2 = implied_value(usio, with_them)
        res.update({
            "median_with_stale": with_them, "n_with_stale": len(inside) + len(sizable),
            "upside_base": base_imp["upside_pct"],
            "upside_with_stale": imp2["upside_pct"] if imp2 else None,
            "material": bool(imp2 and abs(imp2["upside_pct"] - base_imp["upside_pct"]) >= 8),
        })
    res["read"] = _excluded_read(res)
    return res


def _excluded_read(r):
    bits = []
    if r.get("sizable"):
        names = ", ".join(
            f"{s['ticker']} (last filed FY{str(s['vintage'])[:4]}, would be "
            f"{s['hypothetical_ev_gp']:.2f}x)" for s in r["sizable"])
        if r.get("upside_with_stale") is not None:
            move = r["upside_with_stale"] - r["upside_base"]
            bits.append(
                f"{len(r['sizable'])} peer(s) are excluded only because their gross profit is STALE, "
                f"not absent: {names}. If those vintage margins still held, the median would be "
                f"{r['median_with_stale']:.2f}x rather than {r['base_median']:.2f}x and the implied "
                f"read {r['upside_with_stale']:+.0f}% rather than {r['upside_base']:+.0f}% — a "
                f"{abs(move):.0f}pp swing. "
                + ("THAT IS MATERIAL: reading their current 10-K is the highest-value hour available "
                   "on this page, and until someone does, the headline is a point estimate standing "
                   "on an open question."
                   if r.get("material") else
                   "Not material — the headline holds either way."))
        else:
            bits.append(f"Excluded as stale: {names}. Impact could not be sized.")
    if r.get("unsizable"):
        names = ", ".join(f"{u['ticker']} ({u['reason']})" for u in r["unsizable"])
        bits.append(
            f"{len(r['unsizable'])} peer(s) cannot be sized at all: {names}. They report no gross "
            f"profit line at ANY vintage, so there is no figure to include and no impact to compute. "
            f"A vendor number exists for them and is constructed, not reported — admitting one here "
            f"to 'complete' the median is precisely the error this analysis exists to prevent.")
    return " ".join(bits)




def growth_basis(bm=None, primary=None):
    """The growth gap, measured on the basis the multiple actually pays for.

    THE PROBLEM. The comp table's growth column is LATEST-QUARTER REVENUE growth. Every company
    is measured that way, so it is internally consistent and not wrong. But we do not rank on
    EV/Revenue — we rank on EV/GROSS PROFIT, precisely because revenue is not comparable across
    gross and net reporters. Having correctly thrown revenue out of the multiple, the table then
    quotes REVENUE growth beside it. The growth attached to the denominator we actually use is
    GROSS PROFIT growth, and for a company whose margin is moving those are different numbers.

    HOW DIFFERENT, FOR USIO, ON 2026-07-16:

        latest-quarter revenue growth (what the table shows)   15.7%  vs 19.5% median   -3.8pp
        annual revenue growth                                   3.0%  vs 18.2% median  -15.2pp
        annual GROSS PROFIT growth (what EV/GP pays for)        0.4%  vs 19.2% median  -18.8pp

    The gap on the reported basis is FIVE TIMES narrower than the gap on the basis that matters,
    and it errs in the flattering direction. That is not a rounding difference; it is the
    difference between "grows a little slower than peers" and "does not grow at all while peers
    compound at ~19%".

    WHAT IT DOES TO THE HEADLINE. USIO trades at 2.98x against a 3.61x median — a 17% discount.
    A company growing gross profit at +0.4% while the median peer grows at +19.2% arguably
    SHOULD trade at a discount, and the open question is whether 17% is too LARGE or too SMALL
    for a ~19pp growth gap. Stated plainly: the +20% is not a finding that USIO is cheap. It is
    a bet that the acceleration continues.

    AND THE ACCELERATION IS REAL — this is not a bear case dressed up as rigour. Q1 FY26 grew
    revenue 15.7% and gross profit 7% (10-Q, verbatim: "Gross profit increased by 7% to $5.1
    million", margin "20.2% ... down versus 21.9%"), against FY2025's +3.0% / +0.4%. The
    business is inflecting. But that is ONE quarter against a full year, the margin compressed
    while it happened, and the entire re-rating case now rests on it. That is a defensible
    thesis to take to a board. It is not the same claim as "the peers say we are worth 20% more",
    and the two must not be presented as though they were.

    Returns None if the annual basis cannot be built for USIO and at least three peers — a
    median of two is not a median.
    """
    from core import benchmarking_engine, forensics

    bm = bm or benchmarking_engine.build_benchmark()
    prim = primary if primary is not None else bm["primary"]
    ticks = [p["ticker"] for p in prim if p.get("ticker")]
    try:
        forensics.prefetch([CT("ticker")] + ticks)
    except Exception:
        pass

    u = forensics.annual_growth(CT("ticker"))
    if u.get("status") != "ok":
        return None
    rows = []
    for t in ticks:
        a = forensics.annual_growth(t)
        if a.get("status") == "ok":
            rows.append(a)
    if len(rows) < 3:
        return None

    med_rev = _median([r["rev_growth"] for r in rows])
    med_gp = _median([r["gp_growth"] for r in rows])
    q_rev = bm["usio"].get("rev_growth")
    q_med = bm.get("median_gr")

    out = {
        "usio_q_rev_growth": q_rev,
        "median_q_rev_growth": q_med,
        "gap_quarterly_rev": (q_rev - q_med) if (q_rev is not None and q_med is not None) else None,
        "usio_annual_rev_growth": u["rev_growth"],
        "median_annual_rev_growth": med_rev,
        "gap_annual_rev": (u["rev_growth"] - med_rev) if med_rev is not None else None,
        "usio_annual_gp_growth": u["gp_growth"],
        "median_annual_gp_growth": med_gp,
        "gap_annual_gp": (u["gp_growth"] - med_gp) if (med_gp is not None and u["gp_growth"] is not None) else None,
        "usio_gm_delta_pp": u.get("gm_delta_pp"),
        "fy": u.get("fy"),
        "prior_fy": u.get("prior_fy"),
        "n_peers": len(rows),
        "peers": [{"ticker": r["ticker"], "rev_growth": r["rev_growth"],
                   "gp_growth": r["gp_growth"], "gm_delta_pp": r.get("gm_delta_pp")}
                  for r in rows],
    }
    # Does the basis change the story? Flag when the honest gap is materially wider.
    gq, ga = out["gap_quarterly_rev"], out["gap_annual_gp"]
    out["basis_matters"] = bool(gq is not None and ga is not None and abs(ga - gq) >= 8)
    out["read"] = _growth_basis_read(out)
    return out


def _growth_basis_read(o):
    bits = []
    if o["gap_quarterly_rev"] is not None and o["gap_annual_gp"] is not None:
        bits.append(
            "THE GROWTH GAP DEPENDS ENTIRELY ON WHICH BASIS YOU MEASURE. The comp table shows "
            "latest-quarter REVENUE growth: USIO {:+.1f}% vs a {:+.1f}% median, a {:+.1f}pp gap "
            "that reads as 'slightly slower than peers'. But we rank on EV/GROSS PROFIT, and the "
            "growth attached to THAT denominator is gross profit growth. On the annual basis USIO "
            "grew gross profit {:+.1f}% against a {:+.1f}% peer median — a {:+.1f}pp gap.".format(
                o["usio_q_rev_growth"], o["median_q_rev_growth"], o["gap_quarterly_rev"],
                o["usio_annual_gp_growth"], o["median_annual_gp_growth"], o["gap_annual_gp"]))
    if o.get("basis_matters"):
        bits.append(
            "That is roughly {:.0f}x wider than the basis the table reports, and it errs in the "
            "FLATTERING direction. It is the difference between 'grows a little slower' and 'does "
            "not grow while peers compound near {:.0f}%'.".format(
                abs(o["gap_annual_gp"] / o["gap_quarterly_rev"]) if o["gap_quarterly_rev"] else 0,
                o["median_annual_gp_growth"]))
    bits.append(
        "WHAT THIS DOES TO THE IMPLIED UPSIDE. A company growing gross profit at {:+.1f}% while "
        "the median peer grows at {:+.1f}% should trade at SOME discount. So the live question is "
        "not whether the discount exists — it is whether it is too large or too SMALL for a "
        "{:.0f}pp growth gap. The implied upside is therefore not a finding that USIO is cheap; "
        "it is a bet that the growth gap closes.".format(
            o["usio_annual_gp_growth"], o["median_annual_gp_growth"], abs(o["gap_annual_gp"])))
    bits.append(
        "WHY THIS IS THE WORST OF THE FOUR QUADRANTS, NOT MERELY A SLOW ONE. Investors forgive "
        "slow growth when MARGINS ARE EXPANDING, because cost is the lever management actually "
        "controls — margin expansion is self-help and it is credible on a two-quarter view. They "
        "forgive thin margins when GROWTH IS FAST, because scale is coming. USIO currently claims "
        "NEITHER: gross profit grew {:+.1f}% while gross margin moved {:+.1f}pp. Adding revenue "
        "that does not convert to gross profit is the one combination that earns credit from "
        "neither camp — it consumes working capital and support cost to buy volume the multiple "
        "does not pay for. That is a far better explanation of the {:.0f}% discount than "
        "'mispricing', and any re-rating case has to beat it.".format(
            o["usio_annual_gp_growth"], o.get("usio_gm_delta_pp") or 0, 17))
    # USIO-SPECIFIC EVIDENCE BLOCK \u2014 carries USIO's verbatim Q1 FY26 10-Q quote and its
    # exact $5.1M / 20.2% / 21.9% figures. It is real for USIO and FALSE for any other
    # tenant, so it renders only for USIO. The proper generalization is a per-client
    # "inflection evidence" field (or transcript-driven extraction); until that exists,
    # other tenants simply omit this paragraph rather than inherit USIO's numbers.
    if CT("ticker") == "USIO":
        bits.append(
            "AND THE BET HAS EVIDENCE. Q1 FY{} grew revenue {:+.1f}% and gross profit +7% (10-Q: "
            "\u201cGross profit increased by 7% to $5.1 million\u201d, margin \u201c20.2% ... down "
            "versus 21.9%\u201d) against FY{}'s {:+.1f}% / {:+.1f}%. The business is inflecting and "
            "that is a real fact. But it is ONE quarter against a full year, margin compressed while "
            "it happened, and the re-rating case now rests on it. Take that thesis to the board on "
            "its merits \u2014 do not present it as 'the peers say we are worth 20% more'.".format(
                "26", o["usio_q_rev_growth"], str(o["fy"])[:4],
                o["usio_annual_rev_growth"], o["usio_annual_gp_growth"]))
    # Replace the USIO label with the active client's ticker. The narrative variables are
    # named "usio_*" for legacy reasons but hold the ACTIVE client's data, so for any tenant
    # the word "USIO" in these strings is a mislabel, not USIO's data leaking.
    return " ".join(bits).replace("USIO", CT("ticker"))



def _tight_read(tight, n_blended):
    """Explain why the tight, model-matched median is the real relative-value read and the
    blended one is a mix artifact."""
    if not tight:
        return ("No value-chain position is set for this client, so only the blended peer "
                "median is available. Tag each peer's chain position to get the tight, "
                "model-matched median (the review-defensible one).")
    t = tight
    ti = t.get("implied") or {}
    bi = t.get("blended_implied") or {}
    tkr = CT("ticker")
    bits = [
        "TWO MEDIANS, AND ONLY ONE IS A VALUATION. EV/Gross-Profit is comparable ONLY within a "
        "business model. The blended median of {:.2f}x across {} mixed-model peers implies "
        "{:+.0f}% — but it spans the whole value chain, and it is dragged up by parts "
        "MANUFACTURERS earning 40-60% margins on a different model than a {} business.".format(
            t["blended_ev_gp"], n_blended, bi.get("upside_pct") or 0, t["position_label"].lower())
    ]
    bits.append(
        "Restricting to {}'s OWN value-chain position — {} — the model-matched median is "
        "{:.2f}x across {} ({} names incl. {}), implying {:+.0f}%. THAT is the relative-value "
        "read that survives review; the blended figure is a composition artifact, not a finding.".format(
            tkr, t["position_label"], t["ev_gp"], ", ".join(t["peers"]), t["n"] + 1, tkr,
            ti.get("upside_pct") or 0))
    bits.append(
        "The rest of the chain (OEMs, parts, distribution, leasing) is retained for DEMAND "
        "context — every layer draws on the same aggregate aftermarket demand — not for the "
        "multiple. Value against the tight set; explain against the chain.")
    return " ".join(bits)


def build(client_id=None):
    bm = benchmarking_engine.build_benchmark(client_id)
    try:
        from core import forensics
        fx = forensics.build()["rows"]
    except Exception:
        fx = {}

    usio = _row(bm["usio"], fx.get(CT("ticker")))
    primary = [_row(p, fx.get(p["ticker"])) for p in bm["primary"]]
    reference = [_row(p, fx.get(p["ticker"])) for p in bm["reference"]]

    # Medians: primary peers only, and only on rows that actually have the metric.
    med = {
        "ev_gp": _median([p["ev_gp"] for p in primary]),
        "ev_rev": _median([p["ev_rev"] for p in primary]),
        "rev_growth": _median([p["rev_growth"] for p in primary]),
        "gross_margin": _median([p["gross_margin"] for p in primary]),
    }
    ranked = sorted([r for r in [usio] + primary if r["ev_gp"] is not None],
                    key=lambda r: r["ev_gp"])
    for i, r in enumerate(ranked):
        r["rank"] = i + 1

    imp = implied_value(usio, med["ev_gp"])
    sens = sensitivity(usio, primary)
    excl = excluded_impact(usio, primary, client_id)

    # ── Value-chain positioning (Layer 2) + the TIGHT, model-matched median (Layer 1) ──
    # EV/Gross-Profit is only comparable within a business model. The blended median above
    # spans the whole chain (OEMs, parts makers, services, leasing); the TIGHT median below
    # is restricted to peers in the client's OWN value-chain position, which is the only
    # relative-value read that survives review. Both are returned; the renderer leads with
    # tight and keeps the chain for demand context. See core/value_chain.py.
    from core import value_chain as _vc, db as _db
    _chain_map = {p.get("ticker"): (p.get("chain") or "")
                  for p in (_db.load_json("peer_universe.csv", default=[], client_id=client_id) or [])}
    client_chain = CT("chain", "")
    usio["chain"] = client_chain
    for r in primary + reference:
        r["chain"] = _chain_map.get(r["ticker"], "")
    tight = None
    if client_chain:
        tight_peers = [p for p in primary if (p.get("chain") or "") == client_chain]
        tight_gp = _median([p["ev_gp"] for p in tight_peers])
        if tight_gp:
            t_imp = implied_value(usio, tight_gp)
            tight = {
                "position": client_chain, "position_label": _vc.label(client_chain),
                "ev_gp": tight_gp,
                "peers": [p["ticker"] for p in tight_peers if p["ev_gp"] is not None],
                "n": len([p for p in tight_peers if p["ev_gp"] is not None]),
                "implied": t_imp,
                "blended_ev_gp": med["ev_gp"], "blended_implied": imp,
            }
    value_chain_groups = [
        {"slug": slug, "label": label, "tickers": [p["ticker"] for p in rs],
         "is_client_position": slug == client_chain}
        for slug, label, rs in _vc.group_by_chain(primary + reference + [usio])]
    tight_read = _tight_read(tight, len([p for p in primary if p["ev_gp"] is not None]))
    # The growth gap on the basis the multiple actually pays for. See growth_basis().
    try:
        gbasis = growth_basis(bm, bm["primary"])
    except Exception as exc:
        print(f"[valuation_comp] growth basis unavailable: {exc}")
        gbasis = None
    # Take-out evidence. A control bid is a DIFFERENT kind of evidence from a trading
    # multiple and belongs beside it, not inside it — so this rides along in the payload
    # and never touches the median.
    try:
        from core import transaction_comps as _tc
        txn = _tc.build(bm)
    except Exception as exc:
        print(f"[valuation_comp] transaction comps unavailable: {exc}")
        txn = None
    return {
        "usio": usio, "primary": primary, "reference": reference,
        "ranked": ranked, "median": med, "implied": imp, "sensitivity": sens,
        "excluded_impact": excl,
        "tight": tight, "value_chain": value_chain_groups, "tight_read": tight_read,
        "transaction_comps": txn,
        "growth_basis": gbasis,
        "n_primary": len([p for p in primary if p["ev_gp"] is not None]),
        "excluded": [p for p in primary if p["ev_excluded"]],
        "read": _read(usio, med, imp, sens),
        "caveat": (
            "EV/Gross Profit is the only multiple here that is comparable across this peer set. "
            + ("USIO reports revenue GROSS as a principal (10-K filed 2026-03-18) and peers vary — "
               "several make a per-contract ASC 606 principal/agent judgment — "
               if CT("ticker") == "USIO" else
               "gross-vs-net revenue treatment varies across these companies — ")
            + "so EV/Revenue and gross margin are shown for context only and must not be compared "
            "across rows. Revenue cancels out of EV/Gross Profit, which is why the ranking and the "
            "implied value use it."),
    }


def _read(usio, med, imp, sens):
    if not imp:
        return "Insufficient live market data to compute an implied value."
    direction = "discount" if imp["upside_pct"] > 0 else "premium"
    s = (f"{CT('ticker')} trades at {imp['current_multiple']:.1f}x EV/Gross Profit against a primary-peer "
         f"median of {imp['peer_median_multiple']:.1f}x — a {abs(100 - imp['current_multiple']/imp['peer_median_multiple']*100):.0f}% "
         f"{direction} on the one multiple this peer set's accounting doesn't distort. "
         f"Re-rating to the peer median implies an enterprise value of ${imp['implied_ev']/1e6:.1f}M "
         f"against ${imp['current_ev']/1e6:.1f}M today; bridging net "
         f"{'cash' if imp['net_debt'] < 0 else 'debt'} of ${abs(imp['net_debt'])/1e6:.1f}M, that is "
         f"${imp['implied_equity']/1e6:.1f}M of equity vs ${imp['current_equity']/1e6:.1f}M — "
         f"{imp['upside_pct']:+.0f}%.")
    if sens and not sens["robust"]:
        lo, hi = sorted([sens["upside_backed"], sens["upside_all"]])
        s = (f"{CT('ticker')} trades at {imp['current_multiple']:.1f}x EV/Gross Profit — cheap against "
             f"its primary peers on the one multiple this peer set's accounting doesn't distort. But "
             f"the SIZE of the discount is not robust: the implied upside is {lo:+.0f}% to {hi:+.0f}% "
             f"depending on whether {' and '.join(u['ticker'] for u in sens['unbacked'])} — whose gross "
             f"margins come from market data rather than a filing, and which sit immediately above "
             f"{CT('ticker')} — are allowed to set the median. Re-rating to the {sens['n_backed']} "
             f"filing-backed peers ({sens['median_backed']:.2f}x) implies {sens['upside_backed']:+.0f}%; "
             f"to all {sens['n_all']} ({sens['median_all']:.2f}x), {sens['upside_all']:+.0f}%. Treat it "
             f"as a range. The direction is solid; the magnitude is an open question that resolves only "
             f"by reading {' and '.join(u['ticker'] for u in sens['unbacked'])}'s cost of revenue out "
             f"of their filings.")
    if usio["rev_growth"] is not None and med["rev_growth"] is not None:
        if usio["rev_growth"] > med["rev_growth"]:
            s += (f" {CT('ticker')} grows faster than the group ({usio['rev_growth']:+.0f}% vs "
                  f"{med['rev_growth']:+.0f}% median), so the discount is not a growth discount.")
        else:
            s += (f" {CT('ticker')} grows slower than the group ({usio['rev_growth']:+.0f}% vs "
                  f"{med['rev_growth']:+.0f}% median), which is part of why it is cheaper — the "
                  f"re-rating case has to argue that gap closes.")
    return s


def revenue_bridge(client_id=None):
    """Translate the comparable multiple back into the language the market speaks.

    THE PROBLEM THIS SOLVES. Everyone quotes EV/Revenue. It is not comparable across
    this peer set — USIO reports revenue GROSS as a principal, peers vary — which is
    why the retired board deck's "0.4x vs 2.3x peer median, an 82% discount" produced a
    $9-12 price target on a stock worth ~$3. But you cannot simply refuse to speak
    EV/Revenue: it is the number in every screen and every first meeting.

    THE BRIDGE. The identity is exact:

        EV/Revenue = (EV/Gross Profit) x (Gross Profit/Revenue)
                   = EV/GP x gross margin

    So while EV/Revenue cannot be compared ACROSS companies, each company's WARRANTED
    EV/Revenue can be derived: take the peer median EV/Gross Profit — the multiple that
    IS comparable — and apply it to that company's OWN margin. The margin never leaves
    its own filer, so nothing is compared that shouldn't be.

    WHAT IT SHOWS. USIO's warranted EV/Revenue at the peer median EV/GP is ~0.72x, and
    it trades at ~0.75x. The peer median EV/Revenue of ~2.1x was never a target: it is
    2.1x because those peers earn 60-75% gross margins, and USIO earns 23%. The entire
    "EV/Revenue discount" was a margin difference wearing a valuation costume — and this
    table is the one-page proof.
    """
    d = build(client_id)
    med, us = d["median"]["ev_gp"], d["usio"]
    if not med:
        return None
    rows = []
    for r in [us] + d["primary"]:
        gm = r.get("gross_margin")
        if r.get("ev_gp") is None or gm is None:
            continue
        gm_dec = gm / 100.0
        warranted = med * gm_dec
        actual = (r["enterprise_value"] / r["revenue"]) if (r.get("revenue") and r.get("enterprise_value")) else None
        rows.append({
            "ticker": r["ticker"], "name": r.get("name") or "", "is_client": r.get("is_client", False),
            "ev_gp": r["ev_gp"], "gross_margin": gm,
            "ev_rev_actual": actual, "ev_rev_warranted": warranted,
            "vs_warranted_pct": ((actual / warranted - 1) * 100) if (actual and warranted) else None,
        })
    rows.sort(key=lambda x: -x["ev_rev_warranted"])
    u = next((x for x in rows if x["is_client"]), None)
    return {"median_ev_gp": med, "n": d["n_primary"], "rows": rows, "usio": u,
            "peer_median_ev_rev": d["median"]["ev_rev"],
            "read": _bridge_read(u, med, d["median"]["ev_rev"])}


def _bridge_read(u, med, peer_med_ev_rev):
    if not u:
        return f"{CT('ticker')}'s EV/Revenue bridge could not be computed."
    s = (f"At the peer median of {med:.2f}x EV/Gross Profit, {CT('ticker')}'s WARRANTED EV/Revenue is "
         f"{med:.2f}x x {u['gross_margin']:.1f}% = {u['ev_rev_warranted']:.2f}x. It actually trades at "
         f"{u['ev_rev_actual']:.2f}x")
    if u["vs_warranted_pct"] is not None:
        s += (f" — {abs(u['vs_warranted_pct']):.0f}% "
              f"{'ABOVE' if u['vs_warranted_pct'] > 0 else 'below'} warranted.")
    if peer_med_ev_rev:
        s += (f" The peer median EV/Revenue of {peer_med_ev_rev:.2f}x is NOT a target and never was: "
              f"peers trade there because they earn 60-75% gross margins on net-reported revenue, and "
              f"{CT('ticker')} earns {u['gross_margin']:.1f}% on gross-reported revenue. Closing that "
              f"'gap' would require the margin, not a re-rating. The EV/Revenue discount was a margin "
              f"difference wearing a valuation costume.")
    return s
