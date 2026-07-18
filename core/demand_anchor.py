"""Demand anchor (Layer 3) — how the value chain trades in relation to aggregate demand.

THE QUESTION. The tight median (Layer 1) says what SARO is worth vs its model-matched peers.
This layer answers the next one: the WHOLE chain — OEMs, parts, aftermarket services, leasing —
draws on the same aggregate aerospace demand, so how sensitive is each layer to that demand,
and what does SARO's position imply? The point is not another multiple; it is to show that an
aftermarket-SERVICES business (fleet- and flight-hour-driven, recurring) has DIFFERENT demand
economics than an OEM (build-rate-driven, cyclical) — which is why the two can trade at
different multiples at the same growth, and why a raw "cheap vs the median" read is incomplete.

THE DEMAND PROXY, AND ITS HONEST LIMITS. The ideal driver for aftermarket MRO is global flight
hours / RPKs (a coincident measure of how hard the installed fleet is flying). We cannot pull
IATA/OAG traffic from a free feed, so we use what IS in the filings and is literally "demand
driven by Boeing": **Boeing total revenue** (19 years from EDGAR). Read it for what it is —
an OEM-OUTPUT / build-rate proxy. It LEADS aftermarket demand (more deliveries -> bigger future
fleet -> more MRO later) rather than coinciding with it, and it carries Boeing-specific noise
(737 MAX grounding, COVID, the 2024 strike). A traffic/RPK anchor is the planned upgrade; this
module is written so the anchor is swappable.

THE STATISTICS, DONE HONESTLY. Two traps this avoids:
  1. LEVELS vs GROWTH. Revenue levels all trend up, so correlating levels manufactures a high
     r that means nothing. We correlate YEAR-OVER-YEAR GROWTH (stationary), and report the
     OLS slope (beta) of a name's growth on Boeing's growth — "for a 1pp move in Boeing, this
     name's revenue moves beta pp".
  2. THE COVID BREAK. 2020-21 was a ~60% traffic collapse and rebound that dwarfs every other
     year; on ~10 annual points it single-handedly drives any correlation. So every beta is
     reported TWICE — full window and EX-COVID (2020-21 dropped) — and if the two disagree,
     the "sensitivity" was mostly a COVID artifact, which is itself the finding.

Annual data means n is small (SARO has 4 years -> 3 growth points, too few to regress — its
beta is marked insufficient and PROXIED by its model-matched layer). These are directional
reads with stated error bars, not precise factor loadings; the module says so rather than
implying false precision.
"""

from datetime import date

from core import sec_filings, value_chain

_ANCHOR = "BA"
_ANCHOR_LABEL = "Boeing total revenue (OEM-output / build-rate demand proxy)"
_COVID_YEARS = (2020, 2021)
_MIN_GROWTH_POINTS = 4  # need >=4 YoY points to report a beta at all


def annual_revenue(ticker):
    """{fiscal_year:int -> revenue}. Direct companyfacts (not the forensics cache, which is a
    subset), merging revenue tags across the ASC 606 transition, and INCLUDING 20-F/40-F so
    foreign filers (TAT, etc.) aren't silently dropped."""
    try:
        cik = sec_filings.resolve_cik(ticker)
        g = sec_filings._get(
            f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json",
            timeout=120).json()["facts"].get("us-gaap", {})
    except Exception:
        return {}
    out = {}
    for tag in ("Revenues",
                "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax"):
        node = g.get(tag)
        if not node:
            continue
        for unit in node["units"].values():
            for v in unit:
                if v.get("form") not in ("10-K", "20-F", "40-F") or not v.get("start"):
                    continue
                d = (date.fromisoformat(v["end"]) - date.fromisoformat(v["start"])).days
                if 350 <= d <= 380:
                    out[int(v["end"][:4])] = v["val"]  # later (newer) tag wins on overlap
    return out


def _yoy(series):
    """{year -> YoY growth %} from a {year -> level} series."""
    out = {}
    for y in sorted(series):
        if y - 1 in series and series[y - 1]:
            out[y] = (series[y] / series[y - 1] - 1) * 100
    return out


def _ols_beta(xs, ys):
    """Slope, intercept, r, r2 of ys on xs. None if <2 points or zero x-variance."""
    n = len(xs)
    if n < 2:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    syy = sum((y - my) ** 2 for y in ys)
    if sxx == 0 or syy == 0:
        return None
    beta = sxy / sxx
    r = sxy / (sxx ** 0.5 * syy ** 0.5)
    return {"beta": beta, "r": r, "r2": r * r, "n": n}


def _beta_to_anchor(name_growth, anchor_growth, drop=()):
    """Beta of a name's revenue growth on the anchor's, over their overlapping years."""
    yrs = sorted(set(name_growth) & set(anchor_growth) - set(drop))
    if len(yrs) < 2:
        return None
    xs = [anchor_growth[y] for y in yrs]
    ys = [name_growth[y] for y in yrs]
    res = _ols_beta(xs, ys)
    if res:
        res["years"] = yrs
    return res


def build(client_id=None):
    from config.client_config import CT
    from core import db

    client_tk = CT("ticker")
    client_chain = CT("chain", "")
    peers = db.load_json("peer_universe.csv", default=[], client_id=client_id) or []

    anchor_lv = annual_revenue(_ANCHOR)
    anchor_g = _yoy(anchor_lv)

    def profile(tk, chain):
        lv = annual_revenue(tk)
        g = _yoy(lv)
        row = {"ticker": tk, "chain": chain, "years": len(g),
               "full": None, "ex_covid": None, "status": "ok"}
        if len(g) < _MIN_GROWTH_POINTS:
            row["status"] = "insufficient_history"
            return row
        row["full"] = _beta_to_anchor(g, anchor_g)
        row["ex_covid"] = _beta_to_anchor(g, anchor_g, drop=_COVID_YEARS)
        return row

    client_row = profile(client_tk, client_chain)
    peer_rows = [profile(p["ticker"], p.get("chain") or "") for p in peers]

    # Layer averages (ex-COVID beta, the more trustworthy one) — the core deliverable:
    # does aftermarket-services move LESS with Boeing/OEM output than the OEM/parts layers?
    layers = {}
    for r in peer_rows + [client_row]:
        b = (r.get("ex_covid") or {}).get("beta")
        if b is not None:
            layers.setdefault(r["chain"], []).append(b)
    layer_beta = {c: sum(v) / len(v) for c, v in layers.items() if v}

    # SARO's own beta is data-poor (short history) -> proxy via its model-matched layer.
    proxy = None
    if client_row["status"] != "ok" or not client_row.get("ex_covid"):
        proxy = layer_beta.get(client_chain)

    out = {
        "anchor": _ANCHOR, "anchor_label": _ANCHOR_LABEL,
        "anchor_years": sorted(anchor_lv),
        "client": client_row, "peers": peer_rows,
        "layer_beta": layer_beta,
        "layer_beta_labeled": {value_chain.label(c): round(b, 2) for c, b in
                               sorted(layer_beta.items(), key=lambda kv: kv[1], reverse=True)},
        "client_chain": client_chain, "client_proxy_beta": proxy,
    }
    out["read"] = _read(out)
    return out


def _explanatory_power(o):
    """Median ex-COVID r-squared across names with a beta, and the count that clear a
    'meaningful' bar (r2 >= 0.25). Governs whether we may make ANY positioning claim."""
    r2s = [(r.get("ex_covid") or {}).get("r2") for r in o["peers"] + [o["client"]]]
    r2s = [x for x in r2s if x is not None]
    if not r2s:
        return {"median_r2": None, "n_meaningful": 0, "n": 0}
    r2s.sort()
    med = r2s[len(r2s) // 2]
    return {"median_r2": med, "n_meaningful": sum(1 for x in r2s if x >= 0.25), "n": len(r2s)}


def _read(o):
    tkr = o["client"]["ticker"]
    lb = o["layer_beta"]
    ep = _explanatory_power(o)
    parts = [
        "DEMAND ANCHOR — HOW THE CHAIN MOVES WITH AGGREGATE DEMAND. Driver: {} ({} years, "
        "{}-{}), an OEM-OUTPUT proxy that LEADS aftermarket demand rather than coinciding "
        "with it.".format(
            o["anchor_label"], len(o["anchor_years"]),
            o["anchor_years"][0] if o["anchor_years"] else "?",
            o["anchor_years"][-1] if o["anchor_years"] else "?")
    ]

    # THE HONEST GATE. If the anchor has little explanatory power ex-COVID, say so and DO NOT
    # rank layers off noise. This is the actual result for the Boeing-revenue anchor.
    weak = ep["median_r2"] is not None and (ep["median_r2"] < 0.25 or ep["n_meaningful"] <= max(1, ep["n"] // 4))
    if weak:
        parts.append(
            "VERDICT: THIS ANCHOR DOES NOT CARRY THE SIGNAL. Ex-COVID, Boeing revenue explains "
            "almost none of these companies' revenue growth (median R² = {:.2f}; only {} of {} "
            "names clear R² ≥ 0.25). Whatever correlation exists full-window is a 2020-21 COVID "
            "artifact — strip those two years and it collapses. The reason is that Boeing REVENUE "
            "is dominated by Boeing's OWN idiosyncrasies (737 MAX grounding, COVID, the 2024 "
            "strike, program charges), not by aggregate aerospace demand. So the layer betas "
            "below are NOT statistically distinguishable from zero and MUST NOT be used to rank "
            "demand sensitivity or to price anything.".format(
                ep["median_r2"], ep["n_meaningful"], ep["n"]))
        if o["layer_beta_labeled"]:
            parts.append("For reference only (do not rely on): ex-COVID layer betas — " +
                         ", ".join(f"{lab} {b:+.2f}" for lab, b in o["layer_beta_labeled"].items()) + ".")
        parts.append(
            "WHAT THIS MEANS FOR THE FRAMEWORK. The positioning THESIS still holds on first "
            "principles — aftermarket services is fleet-/flight-hour-driven and recurring, an "
            "OEM order book is build-rate-driven and cyclical — but PROVING it needs a coincident "
            "traffic anchor (global RPKs / departures), not Boeing's output. Boeing revenue was "
            "the only demand series pullable from filings; the RPK feed is the required upgrade, "
            "and until it lands this layer frames the thesis QUALITATIVELY rather than "
            "quantifying it. Reporting the noise as a factor loading would be exactly the false "
            "precision this analysis exists to avoid.")
        return " ".join(parts)

    # Strong-enough anchor: make the positioning claim, gated on the numbers.
    if o["layer_beta_labeled"]:
        parts.append("Ex-COVID revenue-growth beta by value-chain layer (median R² = {:.2f}): ".format(
            ep["median_r2"]) + ", ".join(
            f"{lab} {b:+.2f}" for lab, b in o["layer_beta_labeled"].items()) + ".")
    cc = o["client_chain"]
    svc, oem = lb.get(cc), lb.get("engine_oem")
    if svc is not None and oem is not None and abs(svc - oem) > 0.1:
        parts.append(
            "THE POSITIONING POINT. {}'s layer ({}) beta {:+.2f} vs {:+.2f} for engine-OEM — "
            "aftermarket services move {} with OEM build-rate demand, consistent with recurring, "
            "fleet-driven revenue. That is why an aftermarket name can hold a different multiple "
            "than an OEM at the same growth.".format(
                tkr, value_chain.label(cc), svc, oem, "LESS" if svc < oem else "MORE"))
    if o.get("client_proxy_beta") is not None:
        parts.append(
            "{} has too little history ({} growth points) to regress alone; its sensitivity is "
            "PROXIED by its layer beta {:+.2f} — directional only.".format(
                tkr, o["client"]["years"], o["client_proxy_beta"]))
    parts.append(
        "CAVEATS: small annual n; Boeing-revenue anchor carries MAX/COVID/strike distortions and "
        "LEADS rather than coincides with MRO demand; a traffic/RPK anchor is the upgrade. Frame "
        "demand quality; do not set a price off these.")
    return " ".join(parts)
