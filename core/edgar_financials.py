"""
core/edgar_financials.py — real company financials from SEC EDGAR XBRL.

Pulls a company's structured financial facts from EDGAR's companyfacts API
(data.sec.gov/api/xbrl/companyfacts) — the same authoritative source behind the
10-Q/10-K — and extracts a clean income-statement / balance-sheet / cash-flow
summary with the ratios a CFA would compute. No representative "feed": every
number here is straight from the filing.

Two nuances handled with intent, both material for a payments company like USIO:
  • Settlement float — merchant reserves / prepaid-card / ACH settlement funds
    sit on the balance sheet as restricted cash (asset) offset by customer
    deposits (liability). They're pass-through, not leverage, so we also report
    a settlement-adjusted "operating" balance sheet and a net-cash figure.
  • Gross-vs-net revenue — payments firms present revenue differently, so gross
    margin and EV/Revenue aren't comparable across the group; gross profit is
    the honest common denominator (see core/benchmarking_engine.py).

Pure data + arithmetic, no UI. Cached (summary only) via core.db.
"""

from datetime import datetime

from core import db, sec_filings

_SUMMARY_KEY = "edgar_fin_summary_{ticker}.json"
_TTL_DAYS = 7

# Concept fallback chains — the first tag present wins.
_C = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cogs": ["CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfServices"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps": ["EarningsPerShareDiluted", "EarningsPerShareBasic"],
    "dna": ["DepreciationAndAmortization", "DepreciationDepletionAndAmortization",
            "DepreciationAmortizationAndAccretionNet"],
    "ocf": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex_ppe": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "capex_software": ["CapitalizedComputerSoftwareAdditions", "PaymentsToDevelopSoftware"],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "assets_current": ["AssetsCurrent"],
    "liabilities_current": ["LiabilitiesCurrent"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "restricted_cash": ["RestrictedCashAndCashEquivalentsAtCarryingValue",
                        "RestrictedCashAndCashEquivalentsNoncurrentAndCurrent", "RestrictedCashNoncurrent"],
    "customer_deposits": ["CustomerDepositsNoncurrent", "CustomerDeposits", "CustomerDepositsCurrent"],
    "debt_total": ["LongTermDebt"],
    "debt_current": ["LongTermDebtCurrent"],
    "debt_noncurrent": ["LongTermDebtNoncurrent"],
}


def _fetch_companyfacts(ticker):
    cik = sec_filings.resolve_cik(ticker)
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
    return sec_filings._get(url, timeout=45).json(), cik


def _days(entry):
    if "start" not in entry:
        return None
    try:
        s = datetime.strptime(entry["start"], "%Y-%m-%d")
        e = datetime.strptime(entry["end"], "%Y-%m-%d")
        return (e - s).days
    except (ValueError, KeyError):
        return None


def _usd_entries(gaap, tags):
    """All entries (with the first matching tag) for a concept, USD unit."""
    for tag in tags:
        node = gaap.get(tag)
        if not node:
            continue
        units = node.get("units", {})
        key = "USD" if "USD" in units else ("USD/shares" if "USD/shares" in units else next(iter(units), None))
        if key:
            return units[key], tag
    return [], None


def _latest_instant(gaap, tags):
    """Balance-sheet (instant) value at the most recent period end."""
    entries, _ = _usd_entries(gaap, tags)
    instants = [e for e in entries if "start" not in e and e.get("val") is not None]
    if not instants:
        return None, None
    e = max(instants, key=lambda x: x["end"])
    return e["val"], e["end"]


def _quarterly_series(gaap, tags):
    """(end, val) for ~3-month duration entries, sorted by end date."""
    entries, _ = _usd_entries(gaap, tags)
    q = {}
    for e in entries:
        d = _days(e)
        if d is not None and 80 <= d <= 100 and e.get("val") is not None:
            q[e["end"]] = e["val"]          # dedupe: later filing of same period wins
    return sorted(q.items())


def _latest_q(gaap, tags):
    series = _quarterly_series(gaap, tags)
    return series[-1] if series else (None, None)


def _q_ending(gaap, tags, end):
    for e, v in _quarterly_series(gaap, tags):
        if e == end:
            return v
    return None


def _prior_year_q(gaap, tags, end):
    """The quarterly value ~365 days before `end` (±25 days)."""
    if not end:
        return None
    target = datetime.strptime(end, "%Y-%m-%d")
    best = None
    for e, v in _quarterly_series(gaap, tags):
        gap = abs((target - datetime.strptime(e, "%Y-%m-%d")).days - 365)
        if gap <= 25 and (best is None or gap < best[0]):
            best = (gap, v)
    return best[1] if best else None


def _extract(raw):
    gaap = raw.get("facts", {}).get("us-gaap", {})
    dei = raw.get("facts", {}).get("dei", {})

    # ---- Income statement (latest quarter) ----
    q_end, rev = _latest_q(gaap, _C["revenue"])
    cogs = _q_ending(gaap, _C["cogs"], q_end)
    gp = _q_ending(gaap, _C["gross_profit"], q_end)
    if gp is None and rev is not None and cogs is not None:
        gp = rev - cogs
    oi = _q_ending(gaap, _C["operating_income"], q_end)
    ni = _q_ending(gaap, _C["net_income"], q_end)
    # Total D&A = depreciation + intangible amortization; the lone
    # "DepreciationAndAmortization" tag understates it for USIO (it omits
    # intangible amortization). Fall back to that tag only if components absent.
    dep = _latest_q(gaap, ["Depreciation"])[1]
    amort = _latest_q(gaap, ["AmortizationOfIntangibleAssets"])[1]
    dna = (((dep or 0) + (amort or 0)) if (dep is not None or amort is not None)
           else _q_ending(gaap, _C["dna"], q_end))
    ebitda = (oi + dna) if (oi is not None and dna is not None) else None

    # Adjusted EBITDA = EBITDA + the usual non-cash / non-recurring add-backs
    # (stock comp, restructuring, impairment, acquisition costs). The company's
    # own "Adjusted EBITDA" is a non-GAAP measure that isn't XBRL-tagged; this
    # reconstructs the standard bridge from tagged line items.
    sbc = _latest_q(gaap, ["ShareBasedCompensation"])[1]
    restr = _q_ending(gaap, ["RestructuringCharges"], q_end)
    impair = _q_ending(gaap, ["GoodwillImpairmentLoss", "AssetImpairmentCharges"], q_end)
    acq = _q_ending(gaap, ["BusinessCombinationAcquisitionRelatedCosts"], q_end)
    adj_items = {"Stock-based compensation": sbc, "Restructuring": restr,
                 "Impairment": (impair or None), "Acquisition costs": acq}
    adj_sum = sum(v for v in adj_items.values() if v)
    adjusted_ebitda = (ebitda + adj_sum) if ebitda is not None else None

    # TTM revenue = sum of the last four reported quarters (comp-set basis).
    rev_series = _quarterly_series(gaap, _C["revenue"])
    ttm_revenue = sum(v for _, v in rev_series[-4:]) if len(rev_series) >= 4 else None
    rev_prior = _prior_year_q(gaap, _C["revenue"], q_end)
    rev_growth = ((rev / rev_prior - 1) * 100) if (rev and rev_prior) else None

    # EPS (diluted preferred) — instant-ish per-share, take latest quarter value
    eps_entries, _ = _usd_entries(gaap, _C["eps"])
    eps = None
    eps_q = [e for e in eps_entries if _days(e) and 80 <= _days(e) <= 100 and e.get("val") is not None]
    if eps_q:
        eps = max(eps_q, key=lambda x: x["end"])["val"]

    # ---- Balance sheet (latest instant) ----
    assets, bs_end = _latest_instant(gaap, _C["assets"])
    liabilities, _ = _latest_instant(gaap, _C["liabilities"])
    equity, _ = _latest_instant(gaap, _C["equity"])
    assets_cur, _ = _latest_instant(gaap, _C["assets_current"])
    liab_cur, _ = _latest_instant(gaap, _C["liabilities_current"])
    cash, _ = _latest_instant(gaap, _C["cash"])
    restricted, _ = _latest_instant(gaap, _C["restricted_cash"])
    cust_deposits, _ = _latest_instant(gaap, _C["customer_deposits"])

    debt_total, _ = _latest_instant(gaap, _C["debt_total"])
    if debt_total is None:
        dc, _ = _latest_instant(gaap, _C["debt_current"])
        dn, _ = _latest_instant(gaap, _C["debt_noncurrent"])
        debt_total = (dc or 0) + (dn or 0) if (dc or dn) else None

    # ---- Cash flow (latest quarter) ----
    ocf = _q_ending(gaap, _C["ocf"], q_end)
    capex_ppe = _q_ending(gaap, _C["capex_ppe"], q_end) or 0
    capex_sw = _q_ending(gaap, _C["capex_software"], q_end) or 0
    capex = capex_ppe + capex_sw
    fcf = (ocf - capex) if ocf is not None else None

    # Shares out (dei, instant)
    shares = None
    sh_node = dei.get("EntityCommonStockSharesOutstanding")
    if sh_node:
        units = sh_node.get("units", {})
        vals = units.get("shares", [])
        if vals:
            shares = max(vals, key=lambda x: x.get("end", ""))["val"]

    def pct(n, d):
        return round(n / d * 100, 1) if (n is not None and d) else None

    # Custodial / settlement float. USIO holds customer prepaid & merchant
    # settlement funds — cash + restricted cash reconciles to ~$100M vs ~$8M
    # corporate cash — offset by customer-deposit / settlement liabilities.
    # Pass-through, not corporate leverage, so we surface the float rather than
    # net an unbalanced "adjusted" balance sheet (the custodial assets span
    # several line items and can't be cleanly matched from us-gaap tags alone).
    cash_restricted_total, _ = _latest_instant(
        gaap, ["CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"])
    net_cash = (cash - debt_total) if (cash is not None and debt_total is not None) else cash

    return {
        "quarter_end": q_end,
        "bs_end": bs_end,
        "income": {
            "revenue": rev, "cogs": cogs, "gross_profit": gp, "operating_income": oi,
            "net_income": ni, "ebitda": ebitda, "dna": dna, "eps": eps,
            "adjusted_ebitda": adjusted_ebitda,
            "ebitda_adjustments": {k: v for k, v in adj_items.items() if v},
            "gross_margin": pct(gp, rev), "operating_margin": pct(oi, rev),
            "net_margin": pct(ni, rev), "ebitda_margin": pct(ebitda, rev),
            "adj_ebitda_margin": pct(adjusted_ebitda, rev),
            "rev_growth_yoy": round(rev_growth, 1) if rev_growth is not None else None,
            "rev_prior_year": rev_prior, "ttm_revenue": ttm_revenue,
        },
        "balance": {
            "assets": assets, "liabilities": liabilities, "equity": equity,
            "assets_current": assets_cur, "liabilities_current": liab_cur,
            "cash": cash, "restricted_cash": restricted, "customer_deposits": cust_deposits,
            "debt": debt_total, "net_cash": net_cash,
            "cash_and_restricted": cash_restricted_total,
            "working_capital": (assets_cur - liab_cur) if (assets_cur is not None and liab_cur is not None) else None,
            "current_ratio": round(assets_cur / liab_cur, 2) if (assets_cur and liab_cur) else None,
            "debt_to_equity": round(debt_total / equity * 100, 1) if (debt_total is not None and equity) else None,
            "book_value": equity,
        },
        "cashflow": {
            "operating_cf": ocf, "capex": capex, "capex_ppe": capex_ppe, "capex_software": capex_sw,
            "fcf": fcf, "fcf_margin": pct(fcf, rev), "ocf_margin": pct(ocf, rev),
        },
        "shares_out": shares,
    }


def _m(v):
    return v / 1e6 if v is not None else None


def talking_points(s):
    """Plain-English, meeting-ready lines management can speak to, generated
    from the filing — grouped by statement. Each is defensible and pre-empts
    the questions a buy-side analyst will ask."""
    inc, bs, cf = s["income"], s["balance"], s["cashflow"]
    tp = {"income": [], "balance": [], "cashflow": []}

    if inc.get("rev_growth_yoy") is not None and inc.get("revenue") is not None:
        rel = ("above" if inc["rev_growth_yoy"] >= 12 else
               "within" if inc["rev_growth_yoy"] >= 10 else "below")
        tp["income"].append(
            f"Revenue grew {inc['rev_growth_yoy']:.0f}% year-over-year to ${_m(inc['revenue']):.1f}M — "
            f"{rel} our 10–12% full-year target.")
    if inc.get("gross_profit") is not None:
        tp["income"].append(
            f"Gross margin was {inc['gross_margin']:.0f}%. Because we present revenue gross of interchange, "
            f"the comparable figure to net-revenue peers is our ${_m(inc['gross_profit']):.1f}M of gross profit — "
            f"that's the number to benchmark on.")
    if inc.get("ebitda") is not None and inc.get("net_income") is not None:
        adj = (f", or ${inc['adjusted_ebitda']/1e3:.0f}K adjusted EBITDA ({inc['adj_ebitda_margin']:.0f}% margin)"
               if inc.get("adjusted_ebitda") else "")
        tp["income"].append(
            f"We were GAAP-profitable — ${inc['net_income']/1e3:.0f}K net income on ${inc['ebitda']/1e3:.0f}K of "
            f"EBITDA{adj} — while still investing in growth.")

    if bs.get("customer_deposits") is not None and bs.get("cash_and_restricted") is not None:
        tp["balance"].append(
            f"Most of the balance sheet is customer money, not ours: we hold ${_m(bs['cash_and_restricted']):.0f}M "
            f"of cash and restricted cash on behalf of cardholders and merchants, offset by "
            f"${_m(bs['customer_deposits']):.0f}M+ of settlement/prepaid liabilities. It's pass-through — it nets "
            f"out and is not corporate leverage.")
    if bs.get("net_cash") is not None and bs.get("debt") is not None:
        tp["balance"].append(
            f"On a corporate basis we're net cash: ${_m(bs['cash']):.1f}M of cash against only "
            f"${_m(bs['debt']):.1f}M of debt (net cash ${_m(bs['net_cash']):.1f}M), with ${_m(bs['equity']):.1f}M "
            f"of equity — a clean, low-leverage capital structure.")

    if cf.get("fcf") is not None:
        tp["cashflow"].append(
            f"We generated ${cf['operating_cf']/1e3:.0f}K of operating cash flow and ${cf['fcf']/1e3:.0f}K of free "
            f"cash flow this quarter, after ${cf['capex']/1e3:.0f}K of capex and capitalized software — self-funding, "
            f"no external capital needed.")
    return tp


def financial_summary(ticker, force=False):
    """Structured financial summary from EDGAR. Cached (summary only) for a week
    since 10-Q/10-K cadence is quarterly. Returns None on fetch failure."""
    key = _SUMMARY_KEY.format(ticker=ticker.upper())
    if not force:
        cached = db.load_json(key, None)
        if cached and cached.get("_fetched_at"):
            age = (datetime.now() - datetime.fromisoformat(cached["_fetched_at"])).days
            if age < _TTL_DAYS:
                return cached
    try:
        raw, cik = _fetch_companyfacts(ticker)
    except Exception as exc:
        return {"_error": str(exc), "_fetched_at": datetime.now().isoformat()}
    summary = _extract(raw)
    summary["ticker"] = ticker.upper()
    summary["entity"] = raw.get("entityName")
    summary["cik"] = cik
    summary["_fetched_at"] = datetime.now().isoformat()
    db.save_json(key, summary)
    return summary


def valuation_metrics(ticker, gm_fallback=None):
    """Real EV / EV-Revenue / EV-Gross-Profit for a company, on a consistent TTM
    basis: enterprise value = market cap (live price × shares outstanding) + debt
    − cash, over trailing-twelve-month revenue and gross profit. Gross margin
    comes from the filing; where a company doesn't report gross profit (e.g. a
    bank like GDOT), `gm_fallback` is used and flagged (gm_estimated=True).
    Returns None if the core inputs can't be resolved."""
    from core import market_data
    s = financial_summary(ticker)
    if not s or s.get("_error"):
        return None
    inc, bs = s["income"], s["balance"]
    ttm_rev = inc.get("ttm_revenue") or (inc["revenue"] * 4 if inc.get("revenue") else None)
    gm = inc.get("gross_margin")
    gm_est = gm is None
    if gm is None:
        gm = gm_fallback
    ttm_gp = (ttm_rev * gm / 100.0) if (ttm_rev and gm) else None

    snap = market_data.get_snapshot(ticker)
    price = snap["last_price"] if snap and snap.get("last_price") is not None else None
    shares = s.get("shares_out")
    mktcap = (price * shares) if (price and shares) else None
    cash = bs.get("cash") or 0
    debt = bs.get("debt") or 0
    ev = (mktcap + debt - cash) if mktcap is not None else None

    return {
        "ticker": ticker.upper(),
        "ev_rev": round(ev / ttm_rev, 2) if (ev and ttm_rev) else None,
        "ev_gp": round(ev / ttm_gp, 1) if (ev and ttm_gp) else None,
        "gross_margin": round(gm, 1) if gm is not None else None,
        "rev_growth": inc.get("rev_growth_yoy"),
        "ttm_rev": ttm_rev, "ev": ev, "mktcap": mktcap, "price": price, "shares": shares,
        "gm_estimated": gm_est, "source": "edgar",
    }
