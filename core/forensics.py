"""
core/forensics.py — Footnote Forensics, from PRIMARY SOURCES ONLY.

WHAT THIS ANSWERS: can USIO's gross margin be compared to its peers' at all?
The answer, on verified evidence, is mostly NO — and knowing exactly why is worth
more than a comparison that looks precise and is wrong.

-----------------------------------------------------------------------------
HISTORY — READ THIS BEFORE ADDING A "CONVENIENT" NUMBER TO THIS MODULE
-----------------------------------------------------------------------------
This module was twice built on secondary data and twice produced false findings
that reached a generated board PDF:

  1. Built off a June 2026 workbook's frozen margins -> claimed "USIO BEATS FOUR
     after adjustment." Live filings disproved it (USIO 20.2% vs FOUR adj 24.8%).
  2. Rebuilt with live margins but the workbook's accounting policy -> claimed
     "USIO is clean on 3/3 distortions; USIO is a net reporter." USIO's own 10-K
     says the exact opposite.

Root cause both times: a source that ASSERTED rather than one that FILED. The
workbook's verbatim "10-K p.58 / p.38 / p.94" quotes are fabricated — none appear
in the respective 10-Ks (see data/seed/quarantine/peer_forensics_QUARANTINED.py).

RULE, ENFORCED BY THIS MODULE: every fact here resolves to an SEC filing this code
fetched itself, or it is reported as UNKNOWN. There is no seed file. There is no
fallback estimate. `None` is a valid, honest answer and must be rendered as one.

-----------------------------------------------------------------------------
THE VERIFIED FINDING — WHICH INVERTS THE WORKBOOK
-----------------------------------------------------------------------------
USIO reports revenue GROSS, as a principal (10-K filed 2026-03-18):

    "The Company complies with ASC 606-10 and reports revenues at gross as a
     principal versus net as an agent."
    "Revenues derived from electronic processing of credit, debit, and prepaid
     card transactions ... are reported gross of amounts paid to sponsor banks as
     well as interchange and assessments paid to credit card associations."

So USIO's ~23% gross margin is depressed by USIO's OWN gross presentation — the
very mechanism the workbook attributed only to peers. "USIO looks cheap because
peers report gross" is backwards.

And USIO discloses NO interchange dollar amount, so its net-basis margin cannot be
computed from public filings — not by us, not by any analyst. That is USIO's own
disclosure gap, and it is the single most consequential one on the sheet.

CONSEQUENCE: reported gross margin is not a comparable metric across this peer set.
GROSS PROFIT is, because interchange is a pass-through that lands in both revenue
and cost of revenue, leaving gross profit unchanged and only the RATIO distorted.
That is exactly why the benchmarking report ranks on EV/Gross Profit — the engine
was right; the workbook was wrong.
"""

import threading
from datetime import date, datetime, timedelta

from config.client_config import CP, CT
from core import edgar_financials, sec_filings

# ─────────────────────────────────────────────────────────────────────────────
# Per-process cache of the raw us-gaap facts.
#
# WHY THIS EXISTS: companyfacts is a multi-MB JSON per filer, and this module's
# entry points each need the same one — filing_margin(), sbc(), sbc_profile()
# (which re-reads filing_margin), and benchmarking_engine._resolve_company()
# (which calls filing_margin for every company in the comp set). Unmemoized, ONE
# render of the Peer & Market tab fired **33 HTTP fetches and took 23 seconds**,
# which reads as a hung page and risks SEC's fair-access limits.
#
# TTL is hours because the underlying data is annual-report facts: they change
# when a company FILES, not intraday. In-process rather than in Postgres on
# purpose — these payloads are megabytes each and do not belong in the DB cache.
# Locked because NiceGUI renders concurrently and two tabs opening at once must
# not both pay the fetch.
_FACTS_TTL = timedelta(hours=6)
_facts_cache = {}
_facts_lock = threading.Lock()


def _facts(ticker):
    """us-gaap facts dict for a ticker, or None. Memoized (see _FACTS_TTL).

    Negative results are cached too: a filer with no CIK or a failed fetch should
    cost one attempt per TTL, not one per call.
    """
    now = datetime.now()
    with _facts_lock:
        hit = _facts_cache.get(ticker)
        if hit and now - hit[0] < _FACTS_TTL:
            return hit[1]
    try:
        raw, _ = edgar_financials._fetch_companyfacts(ticker)
        gaap = raw["facts"]["us-gaap"]
    except Exception:
        gaap = None
    with _facts_lock:
        _facts_cache[ticker] = (now, gaap)
    return gaap


def clear_cache():
    """Drop the facts cache — for tests, and for a forced refresh after a filing."""
    with _facts_lock:
        _facts_cache.clear()

# Revenue and cost tags, in preference order. GrossProfit is preferred over a
# revenue-minus-cost derivation so we report what the company reported.
_REV = ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"]
# Cost-of-revenue tags, in preference order. The last entry EXCLUDES D&A, so a margin
# derived from it is a gross profit BEFORE depreciation and is therefore slightly
# flattering — it is last for that reason, and filing_margin() flags any row that
# lands on it. It is not optional though: it is the only current cost line several
# filers tag (FOUR, PRTH), and without it they look like they report no cost of
# revenue at all and get silently replaced by a vendor's number.
_COST = ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfServices", "CostOfGoodsSold",
         "CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"]
_COST_EXCLUDES_DA = {"CostOfGoodsAndServiceExcludingDepreciationDepletionAndAmortization"}

# USIO's revenue-recognition policy, quoted from the 10-K this code fetched.
# Held here (not in a seed) because it is the one policy fact the whole analysis
# turns on, and it must travel with the citation that proves it.
USIO_POLICY = {
    "basis": "GROSS (principal)",
    "quote": ("The Company complies with ASC 606-10 and reports revenues at gross as a "
              "principal versus net as an agent."),
    "quote2": ("Revenues derived from electronic processing of credit, debit, and prepaid card "
               "transactions that are authorized and captured through third-party networks are "
               "reported gross of amounts paid to sponsor banks as well as interchange and "
               "assessments paid to credit card associations."),
    "form": "10-K", "filed": "2026-03-18",
    "verified": "2026-07-16 — fetched from EDGAR and string-matched by core.forensics",
}


# ─────────────────────────────────────────────────────────────────────────────
# GAAP gross profit disclosed in the 10-K but NOT tagged in XBRL.
#
# Shift4 (FOUR) stopped tagging GrossProfit after FY2021 because it stopped
# presenting the subtotal on the face of the income statement. It still discloses
# it — in an MD&A reconciliation table — and its own footnote says so:
#
#   "Although gross profit is not presented on the Consolidated Statements of
#    Operations, it represents the most comparable metric calculated under
#    U.S. GAAP to non-GAAP gross revenues less network fees."
#
# So this is a GAAP figure from the primary source, not an estimate. Without it
# FOUR looks like it has no current gross margin and gets silently replaced by a
# vendor's number (Yahoo says 35.1%; the filing says 32.4%).
#
# THIS IS HAND-CARRIED DATA, WHICH IS EXACTLY WHAT BURNED THIS MODULE TWICE. The
# difference is the guard: `check` must reconcile against XBRL on every run. If
# FOUR files a new 10-K, its FY revenue moves, the check fails, and the fact is
# reported STALE instead of being quietly applied to the wrong year. A hand-carried
# fact without an expiry is a time bomb; this one has one.
_MDA_GROSS_PROFIT = {
    "FOUR": {
        "fy": "2025-12-31", "gross_profit": 1354e6,
        # Reconciles on the face of the table: 4180 − 2199 network fees − 553 other
        # costs of sales − 74 depreciation of equipment under lease = 1354.
        "check": {"revenue": 4180e6},
        "network_fees": 2199e6,  # FOUR discloses its interchange. USIO does not.
        "source": "10-K filed 2026-02-27, MD&A reconciliation table",
        "quote": ("Although gross profit is not presented on the Consolidated Statements of "
                  "Operations, it represents the most comparable metric calculated under U.S. "
                  "GAAP to non-GAAP gross revenues less network fees."),
    },
}


# Annual-report forms. 20-F/40-F matter: Paysafe (PSFE) is a foreign private issuer
# and files 20-F + 6-K, never a 10-K. An earlier cut of this module filtered on
# form == "10-K" and therefore reported "PSFE does not report a gross profit line"
# — false. It reports one; we just weren't looking at the form it files on.
_ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}

# Reported gross profit tag, for the annual growth basis.
_GROSS = ["GrossProfit"]


def _fy_facts(gaap, tags):
    """{period_end: (value, tag)} for ~annual durations on an annual-report form."""
    out = {}
    for t in tags:
        node = gaap.get(t)
        if not node:
            continue
        for unit in node["units"].values():
            for v in unit:
                if not v.get("start") or v.get("form") not in _ANNUAL_FORMS:
                    continue
                days = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
                if 350 <= days <= 380:
                    out.setdefault(v["end"], (v["val"], t))
    return out


def filing_margin(ticker):
    """Period-ALIGNED gross margin straight from the company's own 10-K facts.

    Returns a dict that always states what it knows and what it doesn't. The
    alignment matters: an earlier cut of this analysis paired FOUR's FY2021 gross
    profit with its FY2025 revenue and produced a nonsense 6.7% margin. Gross
    profit and revenue must come from the SAME period or the number is fiction.
    """
    rec = {"ticker": ticker, "gross_margin": None, "period": None, "revenue": None,
           "gross_profit": None, "status": None, "detail": None}
    try:
        cik = sec_filings.resolve_cik(ticker)
    except Exception:
        cik = None
    if not cik:
        rec["status"] = "no_cik"
        rec["detail"] = ("No CIK resolves — absent from SEC's company_tickers.json AND not "
                         "resolvable via browse-EDGAR. We have no EDGAR data for it at all.")
        return rec
    gaap = _facts(ticker)
    if gaap is None:
        rec["status"] = "fetch_failed"
        rec["detail"] = "EDGAR companyfacts fetch failed or returned no us-gaap facts."
        return rec

    rev = _fy_facts(gaap, _REV)
    gp = _fy_facts(gaap, ["GrossProfit"])
    cost = _fy_facts(gaap, _COST)
    rec["latest_revenue_fy"] = max(rev) if rev else None

    # A GAAP gross profit disclosed in MD&A but untagged in XBRL — used ONLY if it
    # reconciles against this filer's current XBRL revenue. See _MDA_GROSS_PROFIT.
    mda = _MDA_GROSS_PROFIT.get(ticker)
    if mda and rev:
        latest = max(rev)
        xbrl_rev = rev[latest][0]
        expect = mda["check"]["revenue"]
        if latest == mda["fy"] and abs(xbrl_rev - expect) / expect < 0.005:
            rec.update({
                "gross_margin": mda["gross_profit"] / xbrl_rev, "period": latest,
                "revenue": xbrl_rev, "gross_profit": mda["gross_profit"],
                "tag": "10-K MD&A (GAAP, untagged in XBRL)", "derived": False,
                "network_fees": mda.get("network_fees"), "status": "ok_mda",
                "detail": (f"Discloses GAAP gross profit in MD&A but does not tag it in XBRL "
                           f"(stopped presenting the subtotal on the income statement). "
                           f"${mda['gross_profit']/1e6:,.0f}M on ${xbrl_rev/1e6:,.0f}M revenue, "
                           f"FY{latest[:4]}, per {mda['source']}. Reconciled against XBRL revenue "
                           f"on this run."),
            })
            return rec
        rec["status"] = "stale_mda"
        rec["detail"] = (
            f"Hand-carried MD&A gross profit is for FY{mda['fy'][:4]} on ${expect/1e6:,.0f}M revenue, "
            f"but the latest XBRL revenue is ${xbrl_rev/1e6:,.0f}M for FY{latest[:4]}. The filer has "
            f"moved on. REFUSING to apply a stale hand-carried figure — re-read the current 10-K's "
            f"MD&A table and update _MDA_GROSS_PROFIT.")
        return rec

    both = sorted(set(rev) & (set(gp) | set(cost)))
    if not both:
        rec["status"] = "no_gross_profit_line"
        rec["detail"] = ("Reports no gross profit and no cost-of-revenue line in XBRL "
                         "(no GrossProfit / CostOfRevenue / CostOfServices tag), and the 10-K "
                         "never uses the phrase. There is no gross margin to source — the metric "
                         "does not exist for this filer, so any vendor figure for it is constructed.")
        return rec

    end = both[-1]
    # A REPORTED GrossProfit is stronger evidence than one we derive by subtracting
    # a cost line whose composition we have not read. Both are usable; the
    # distinction is recorded and rendered rather than flattened away.
    if end in gp:
        gp_val, tag, derived = gp[end][0], gp[end][1], False
    else:
        gp_val, ctag = rev[end][0] - cost[end][0], cost[end][1]
        tag, derived = f"{rev[end][1]} − {ctag}", True
    rec.update({"gross_margin": gp_val / rev[end][0], "period": end, "revenue": rev[end][0],
                "gross_profit": gp_val, "tag": tag, "derived": derived})
    if rec["latest_revenue_fy"] and end < rec["latest_revenue_fy"]:
        rec["status"] = "stale"
        rec["detail"] = (f"Last tagged a gross profit line for FY{end[:4]}, but has reported revenue "
                         f"through FY{rec['latest_revenue_fy'][:4]}. The margin is {end[:4]}-vintage "
                         "and is NOT a current figure.")
    elif derived:
        rec["status"] = "derived"
        ex_da = ctag in _COST_EXCLUDES_DA
        rec["excludes_da"] = ex_da
        rec["detail"] = (f"Reports no GrossProfit line; margin DERIVED as revenue minus "
                         f"{ctag} for FY{end[:4]}. Usable, but it assumes that cost line is the "
                         f"full cost of revenue — we have not read its composition."
                         + (" NOTE: that cost line EXCLUDES depreciation & amortization, so this "
                            "margin is a gross profit BEFORE D&A and is flattering by however much "
                            "D&A belongs in cost of revenue. For reference, the same treatment on "
                            "FOUR reads 34.2% ex-D&A vs the 32.4% its 10-K actually reports."
                            if ex_da else ""))
    else:
        rec["status"] = "ok"
        rec["detail"] = f"Reported GrossProfit and revenue, both FY{end[:4]}, per {rev[end][1] and 'annual filing'}."
    return rec


_SBC_TAGS = ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"]


def sbc(ticker):
    """FY stock-based compensation from the filer's own XBRL. None if untagged."""
    gaap = _facts(ticker)
    if gaap is None:
        return None
    f = _fy_facts(gaap, _SBC_TAGS)
    return f[max(f)][0] if f else None


def sbc_profile():
    """SBC measured against GROSS PROFIT, not revenue — and the answer inverts the
    workbook, for the third time and from the same root cause.

    THE DENOMINATOR IS THE WHOLE ARGUMENT. The quarantined workbook measured SBC as a
    percent of REVENUE and concluded USIO was "clean — small in absolute terms, so the
    add-back represents little real dilution." Both halves are wrong:

      * Absolute dollars are not a test. $1.7M is small because USIO is small.
      * "% of revenue" is the WRONG basis for USIO specifically. USIO reports revenue
        GROSS, so its denominator is inflated by interchange it never keeps. That basis
        flatters USIO more than any other name in the set — the error is not neutral,
        it points one way.

    Gross profit is presentation-invariant (interchange lands in revenue and cost of
    revenue equally and cancels), so it is the only denominator that compares. On it:

        % of revenue      USIO 2.0% -> rank 4 of 6  (middle of the pack)
        % of gross profit USIO 8.9% -> rank 6 of 6  (HIGHEST in the group)

    So SBC is not a point in USIO's favour. It is the largest in the peer set relative
    to the gross profit the business actually generates. Peers only appear here if their
    gross profit is filing-sourced — CASS and GDOT are banks with no gross profit line,
    so they cannot be placed on this basis at all.
    """
    primary, _ = comp_set()
    rows = []
    for t in sorted(set(primary) | {CT("ticker")}):
        f = filing_margin(t)
        if f["status"] not in _USABLE:
            continue
        s, gp, rev = sbc(t), f.get("gross_profit"), f.get("revenue")
        if not (s and gp and rev):
            continue
        rows.append({"ticker": t, "sbc": s, "gross_profit": gp, "revenue": rev,
                     "pct_revenue": s / rev * 100, "pct_gross_profit": s / gp * 100,
                     "period": f["period"], "is_client": t == CT("ticker")})
    if not rows:
        return None
    by_gp = sorted(rows, key=lambda r: r["pct_gross_profit"])
    by_rev = sorted(rows, key=lambda r: r["pct_revenue"])
    for i, r in enumerate(by_gp):
        r["rank_gp"] = i + 1
    for i, r in enumerate(by_rev):
        r["rank_rev"] = i + 1
    us = next((r for r in rows if r["is_client"]), None)
    return {"rows": by_gp, "usio": us, "n": len(rows), "read": _sbc_read(us, by_gp, by_rev)}


def _sbc_read(us, by_gp, by_rev):
    if not us:
        return "USIO's SBC or gross profit could not be sourced — no comparison made."
    n = len(by_gp)
    worst = us["rank_gp"] == n
    s = (f"USIO's SBC is ${us['sbc']/1e6:.1f}M (FY{us['period'][:4]}) — small in absolute dollars, "
         f"but absolute dollars are not the test. Measured against the gross profit the business "
         f"actually generates, it is {us['pct_gross_profit']:.1f}% — "
         f"{'the HIGHEST' if worst else f'rank {us['rank_gp']}'} of {n} in the peer set.")
    if us["rank_rev"] != us["rank_gp"]:
        s += (f" On the workbook's basis (% of revenue) it looks like {us['pct_revenue']:.1f}% and "
              f"rank {us['rank_rev']} of {n} — but that denominator is USIO's GROSS revenue, "
              f"inflated by interchange it never keeps, so it flatters USIO more than any peer here. "
              f"Gross profit is the only presentation-invariant denominator, and on it the 'lean SBC' "
              f"story does not survive.")
    return s


def comp_set():
    primary, reference = [], []
    for p in CP():
        (reference if p.get("tier") == "reference" else primary).append(p["ticker"])
    return primary, reference


def survey(tickers=None):
    """Every primary peer, with the honest status of its gross margin."""
    primary, _ = comp_set()
    tickers = tickers or sorted(set(primary) | {CT("ticker")})
    return {t: filing_margin(t) for t in tickers}


# Statuses whose margin is current and filing-sourced. "derived" qualifies: it is
# computed from the filer's own revenue and cost lines, just not from a reported
# GrossProfit subtotal.
_USABLE = ("ok", "derived", "ok_mda")


def comparable(rows):
    """Peers whose CURRENT gross margin is filing-sourced and period-aligned — the
    only ones that may enter a comparison at all."""
    return {t: r for t, r in rows.items() if r["status"] in _USABLE}


def build():
    """Everything the Footnote Forensics view needs — including, prominently, what
    it cannot tell you."""
    tk = CT("ticker")
    rows = survey()
    ok = comparable(rows)
    us = rows.get(tk) or {}

    reasons = {}
    for t, r in rows.items():
        if r["status"] not in _USABLE:
            reasons.setdefault(r["status"], []).append(t)

    peers_ok = {t: r for t, r in ok.items() if t != tk}
    primary, _ = comp_set()
    return {
        "ticker": tk,
        "policy": USIO_POLICY,
        "rows": rows,
        "usio": us,
        "comparable": ok,
        "peers_comparable": sorted(peers_ok),
        "excluded": reasons,
        "n_primary": len(primary),
        "pct_comparable": round(len(peers_ok) / len(primary) * 100) if primary else 0,
        "interchange_disclosed": False,  # verified: no dollar amount anywhere in the 10-K
        "sbc": sbc_profile(),
        "verdict": _verdict(us, peers_ok),
    }


def _verdict(us, peers_ok):
    """The finding, stated so it cannot be quoted out of context into a deck."""
    if not us.get("gross_margin"):
        return ("USIO's own gross margin could not be sourced from its filings — no comparison "
                "can be made.")
    lines = [
        f"USIO reports revenue GROSS, as a principal (10-K filed {USIO_POLICY['filed']}). Its "
        f"{us['gross_margin']*100:.1f}% gross margin (FY{us['period'][:4]}) is therefore depressed by "
        f"its OWN presentation: interchange and sponsor-bank fees it never keeps sit in both revenue "
        f"and cost of services.",
        "USIO discloses no interchange dollar amount, so its net-basis margin CANNOT be computed "
        "from public filings — by us or by any analyst. That is USIO's own disclosure gap and the "
        "most consequential one it has.",
    ]
    if peers_ok:
        bits = ", ".join(f"{t} {r['gross_margin']*100:.1f}%" for t, r in sorted(peers_ok.items()))
        lines.append(
            f"Peers with a current, filing-sourced gross margin: {bits}. These are NOT like-for-like "
            f"with USIO — each peer's own gross-vs-net treatment is a per-contract ASC 606 principal/"
            f"agent judgment we have not verified peer-by-peer, so the ratios are not comparable.")
    lines.append(
        "USE GROSS PROFIT, NOT GROSS MARGIN. Interchange is a pass-through: it inflates revenue and "
        "cost of revenue equally, leaving gross profit unchanged and only the ratio distorted. The "
        "benchmarking table's EV/Gross Profit ranking is the correct basis and is unaffected by any "
        "of this.")
    return " ".join(lines)


def prefetch(tickers):
    """Warm the facts memo for many tickers at once.

    A cold render of the comp set fetched 9 companyfacts JSONs SEQUENTIALLY — ~4.7s of
    the ~10s cold cost, spent waiting on one HTTP round-trip at a time while the CPU idled.
    They are independent, so fetch them together.

    Safe to parallelise ONLY because sec_filings._get() now paces globally across threads
    (see _throttle there). Before that, each thread slept on its own clock and four workers
    would have burst past SEC's ~10 req/s fair-access limit. The pool is deliberately small:
    the global limiter caps the rate anyway, so more workers buy nothing and only make a
    failure noisier.

    Returns nothing — this only populates the memo that _facts() reads. Any ticker that
    fails is simply left uncached and will be retried (and reported) by _facts() normally.
    """
    todo = []
    now = datetime.now()
    with _facts_lock:
        for t in tickers:
            hit = _facts_cache.get(t)
            if not (hit and now - hit[0] < _FACTS_TTL):
                todo.append(t)
    if len(todo) < 2:
        for t in todo:
            _facts(t)
        return
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(_facts, todo))


def annual_growth(ticker):
    """FY-over-FY growth on BOTH bases: revenue AND gross profit.

    WHY BOTH, AND WHY THIS EXISTS.

    The comp table's growth column is REVENUE growth on the latest quarter. Every company in
    the set is measured that way, so it is internally consistent — but it is not the growth
    the multiple is paying for. We rank on EV/GROSS PROFIT. For a gross reporter whose margin
    is moving, revenue growth and gross profit growth are different numbers, and only the
    second one is attached to the denominator we actually use.

    USIO Q1 FY26 is the case in point, straight from the 10-Q: revenue +16% to $25.5M, but
    "Gross profit increased by 7% to $5.1 million", with margin "20.2% ... down versus 21.9%".
    Revenue growth of 16% against gross profit growth of 7% is not a rounding difference — it
    is more than half the growth rate disappearing into mix. Quoting the 16% beside an
    EV/Gross Profit multiple invites a conclusion the denominator does not support.

    The annual basis matters for a second reason: the QUARTER is one observation. USIO's FY2025
    grew +3.0% while its latest quarter grew +15.7%. Both are true and neither is a typo — the
    business is genuinely accelerating — but a reader shown only the flattering one is being
    steered. Show both, label both, let the reader weigh them.

    Returns None where the company does not file two comparable annual periods; the caller
    must handle that rather than fill it in.
    """
    out = {"ticker": ticker, "fy": None, "prior_fy": None,
           "rev_growth": None, "gp_growth": None,
           "gross_margin": None, "gross_margin_prior": None, "gm_delta_pp": None,
           "status": None}
    try:
        gaap = _facts(ticker)
    except Exception as exc:
        out["status"] = f"error: {exc}"
        return out
    if not gaap:
        out["status"] = "no_facts"
        return out

    rev = _fy_facts(gaap, _REV)
    gp = _fy_facts(gaap, _GROSS)
    cost = _fy_facts(gaap, _COST)

    # Gross profit: reported if present, else derived from a cost line for the SAME period.
    def _gp_for(end):
        if end in gp:
            return gp[end][0], "reported"
        if end in rev and end in cost:
            return rev[end][0] - cost[end][0], "derived"
        return None, None

    ends = sorted(rev, reverse=True)
    if len(ends) < 2:
        out["status"] = "insufficient_annual_periods"
        return out

    fy = ends[0]
    # The prior period must be ~one year earlier, not merely the next one in the list —
    # a gap year would silently turn a 2-year change into a "growth rate".
    prior = None
    for e in ends[1:]:
        d = (date.fromisoformat(fy) - date.fromisoformat(e)).days
        if 330 <= d <= 400:
            prior = e
            break
    if not prior:
        out["status"] = "no_adjacent_prior_fy"
        return out

    out["fy"], out["prior_fy"] = fy, prior
    r0, r1 = rev[fy][0], rev[prior][0]
    if r1:
        out["rev_growth"] = (r0 / r1 - 1) * 100

    g0, b0 = _gp_for(fy)
    g1, b1 = _gp_for(prior)
    if g0 is not None and g1:
        out["gp_growth"] = (g0 / g1 - 1) * 100
        out["gp_basis"] = b0
    if g0 is not None and r0:
        out["gross_margin"] = g0 / r0 * 100
    if g1 is not None and r1:
        out["gross_margin_prior"] = g1 / r1 * 100
    if out["gross_margin"] is not None and out["gross_margin_prior"] is not None:
        out["gm_delta_pp"] = out["gross_margin"] - out["gross_margin_prior"]

    out["status"] = "ok" if out["rev_growth"] is not None else "no_revenue"
    return out

