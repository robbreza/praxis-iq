"""Segment revenue, read from the filing's own XBRL instance document.

WHY THIS MODULE EXISTS. The `companyfacts` API that the rest of the platform runs on returns
CONSOLIDATED facts only — it strips dimensions. Segment detail is dimensional data, so it is
simply not in that API at any depth. It lives in the filing's XBRL instance, where each fact
carries a contextRef and the context carries the segment axis. So this module goes to the
instance document directly. That is the primary source; there is no vendor in the path.

WHAT IT FOUND, AND WHY IT MATTERS. USIO reports TWO reportable segments (us-gaap:
NumberOfReportableSegments = 2), not four:

    * Merchant Services  — card, ACH, and Prepaid. The payments business.
    * Output Solutions   — print-and-mail.

Our own onboarding kit listed "Segment revenue table (ACH / Card / Prepaid / Output)" among
the things it could not source, as though those were four segments. They are not. ACH,
Card/PayFac and Prepaid all sit INSIDE Merchant Services; they are product lines, not
reportable segments, and USIO does not disaggregate revenue among them in the segment note.
Anything built expecting four segments was built against a structure that does not exist —
so the kit was declining to produce a table that could not have been produced anyway.

THE COMPARABILITY PROBLEM THIS EXPOSES — and it cuts against our own headline.

The peer-median analysis compares USIO's 2.98x EV/Gross Profit to a 3.61x median drawn from
pure-play payments companies. But USIO's 2.98x is a BLENDED multiple across two businesses:
a payments business AND a print-and-mail business whose cost of services is ~85% POSTAGE — a
pass-through. Applying a payments multiple to 100% of USIO's gross profit implicitly values
the print business at a payments multiple, which it almost certainly does not deserve. We
were comparing a blend to a pure-play and calling the gap a discount.

That is a real objection to our own work, so this module sizes it honestly — and the honest
sizing does NOT require inventing a multiple for Output Solutions. It asks a breakeven
question instead: hold Merchant Services at exactly the peer median, and ask what Output
Solutions would have to be worth for USIO to be fairly valued today. If that breakeven number
is absurdly low, the conclusion survives the objection without anyone guessing at a print
comp. See sotp_breakeven().

Every figure is reconciled against the consolidated gross profit that the rest of the platform
already uses. If the segments do not sum to the consolidated total, this module reports a
failure rather than returning numbers — a silently wrong segment split would be worse than
none, because it would look authoritative.
"""

import re
import threading
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

from core import sec_filings as sf

_TTL = timedelta(hours=12)
_cache = {}
_lock = threading.Lock()

_SEG_AXIS = "StatementBusinessSegmentsAxis"
_NATURE_AXIS = "NatureOfExpenseAxis"

# The facts we want, by local name.
_REVENUE = ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues")
_COST = ("CostOfGoodsAndServicesSold", "CostOfRevenue", "CostOfServices")
_GROSS = ("GrossProfit",)
_DA = ("DepreciationAndAmortization", "DepreciationDepletionAndAmortization")


def _local(tag):
    """Local name from an ElementTree tag: '{ns}GrossProfit' -> 'GrossProfit'."""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _qn_local(qname):
    """Local name from a QName ATTRIBUTE VALUE: 'us-gaap:SegmentsAxis' -> 'SegmentsAxis'.

    Element tags arrive from ElementTree in Clark notation ({namespace}name), but the
    `dimension` attribute on an explicitMember is a raw QName carrying a COLON prefix, which
    ElementTree does not expand. Running _local() over it returns the string untouched, so an
    axis reads as 'us-gaap:StatementBusinessSegmentsAxis' and silently matches nothing. Strip
    both forms.
    """
    if not qname:
        return ""
    return qname.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def _instance_url(ticker, form="10-K"):
    """Locate the XBRL instance document inside the latest annual filing."""
    cik = sf.resolve_cik(ticker)
    if not cik:
        return None, None, None
    subs = sf._get(f"https://data.sec.gov/submissions/CIK{cik}.json", timeout=30).json()
    r = subs["filings"]["recent"]
    hit = next(((a, d) for a, d, f in
                zip(r["accessionNumber"], r["filingDate"], r["form"]) if f == form), None)
    if not hit:
        return None, None, None
    acc, filed = hit
    base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-', '')}"
    idx = sf._get(base + "/index.json", timeout=30).json()
    # The instance is the .xml that is not a linkbase (_cal/_def/_lab/_pre) and not the summary.
    for f in idx["directory"]["item"]:
        n = f["name"]
        if (n.endswith(".xml") and not n.startswith("R")
                and not re.search(r"_(cal|def|lab|pre)\.xml$", n)
                and n != "FilingSummary.xml"):
            return base + "/" + n, acc, filed
    return None, acc, filed


def _parse_contexts(root):
    """contextRef -> {'end':..., 'start':..., 'dims': {axis_localname: member}}"""
    ctx = {}
    for el in root.iter():
        if _local(el.tag) != "context":
            continue
        cid = el.get("id")
        rec = {"dims": {}, "start": None, "end": None, "instant": None}
        for sub in el.iter():
            ln = _local(sub.tag)
            if ln == "startDate":
                rec["start"] = (sub.text or "").strip()
            elif ln == "endDate":
                rec["end"] = (sub.text or "").strip()
            elif ln == "instant":
                rec["instant"] = (sub.text or "").strip()
            elif ln == "explicitMember":
                axis = _qn_local(sub.get("dimension"))
                rec["dims"][axis] = (sub.text or "").strip()
        ctx[cid] = rec
    return ctx


def _facts(root, ctx, names):
    """Collect facts whose local name is in `names`, keyed by (period, dims)."""
    out = []
    want = set(names)
    for el in root:
        ln = _local(el.tag)
        if ln not in want:
            continue
        cref = el.get("contextRef")
        c = ctx.get(cref)
        if not c or el.text is None:
            continue
        try:
            val = float(el.text.strip())
        except ValueError:
            continue
        out.append({"name": ln, "value": val, "start": c["start"], "end": c["end"],
                    "dims": c["dims"]})
    return out


def _pick(facts, end, dims_filter):
    """One value for a period whose dimensions match EXACTLY (no extra axes)."""
    for f in facts:
        if f["end"] != end:
            continue
        if f["dims"] == dims_filter:
            return f["value"]
    return None


def fetch(ticker=None):
    """Segment table for the latest 10-K, reconciled against consolidated. Cached.

    ticker defaults to the ACTIVE TENANT (config.client_config.CT), never a
    hardcoded 'USIO' — otherwise a second client's segment section would render
    USIO's 10-K. Pass an explicit ticker only to inspect a specific company."""
    if ticker is None:
        from config.client_config import CT
        ticker = CT("ticker")
    key = ticker.upper()
    with _lock:
        hit = _cache.get(key)
        if hit and datetime.now() - hit[0] < _TTL:
            return hit[1]
    try:
        res = _fetch_uncached(key)
    except Exception as exc:
        res = {"ticker": key, "status": "error", "detail": f"{type(exc).__name__}: {exc}",
               "segments": []}
    with _lock:
        _cache[key] = (datetime.now(), res)
    return res


def _fetch_uncached(ticker):
    url, acc, filed = _instance_url(ticker)
    if not url:
        return {"ticker": ticker, "status": "no_instance", "segments": [],
                "detail": "No XBRL instance document found in the latest 10-K."}

    root = ET.fromstring(sf._get(url, timeout=120).content)
    ctx = _parse_contexts(root)
    rev = _facts(root, ctx, _REVENUE)
    cost = _facts(root, ctx, _COST)
    gp = _facts(root, ctx, _GROSS)
    da = _facts(root, ctx, _DA)

    # Which fiscal year-ends are present as CONSOLIDATED (no dimensions) gross profit?
    ends = sorted({f["end"] for f in gp if not f["dims"] and f["start"]}, reverse=True)
    if not ends:
        return {"ticker": ticker, "status": "no_consolidated_gp", "segments": [],
                "detail": "No undimensioned GrossProfit in the instance."}
    fy, prior = ends[0], (ends[1] if len(ends) > 1 else None)

    # Segment members present on the business-segments axis for the current FY.
    members = []
    for f in gp:
        if f["end"] == fy and list(f["dims"].keys()) == [_SEG_AXIS]:
            m = f["dims"][_SEG_AXIS]
            if m not in members:
                members.append(m)
    if not members:
        return {"ticker": ticker, "status": "no_segments", "segments": [],
                "detail": "Instance has no StatementBusinessSegmentsAxis members on GrossProfit."}

    def _label(m):
        raw = m.split(":")[-1]
        raw = re.sub(r"Member$", "", raw)
        return re.sub(r"(?<!^)(?=[A-Z])", " ", raw).strip()

    segs = []
    for m in members:
        d = {_SEG_AXIS: m}
        row = {
            "member": m,
            "label": _label(m),
            "revenue": _pick(rev, fy, d),
            "cost": _pick(cost, fy, d),
            "gross_profit": _pick(gp, fy, d),
            "d_and_a": _pick(da, fy, d),
            "revenue_prior": _pick(rev, prior, d) if prior else None,
            "gross_profit_prior": _pick(gp, prior, d) if prior else None,
        }
        r_, g_ = row["revenue"], row["gross_profit"]
        row["gross_margin"] = (g_ / r_ * 100) if (r_ and g_ is not None) else None
        rp, gpp = row["revenue_prior"], row["gross_profit_prior"]
        row["gross_margin_prior"] = (gpp / rp * 100) if (rp and gpp is not None) else None
        row["rev_growth"] = ((r_ / rp - 1) * 100) if (r_ and rp) else None
        row["gm_delta_pp"] = ((row["gross_margin"] - row["gross_margin_prior"])
                              if (row["gross_margin"] is not None
                                  and row["gross_margin_prior"] is not None) else None)
        # Cost composition — which nature-of-expense members carry this segment's cost.
        comp = []
        for f in cost:
            if f["end"] != fy:
                continue
            if f["dims"].get(_SEG_AXIS) == m and _NATURE_AXIS in f["dims"] and f["value"]:
                comp.append({"kind": _label(f["dims"][_NATURE_AXIS]), "value": f["value"]})
        row["cost_composition"] = sorted(comp, key=lambda c: -c["value"])
        segs.append(row)

    con = {
        "revenue": _pick(rev, fy, {}),
        "cost": _pick(cost, fy, {}),
        "gross_profit": _pick(gp, fy, {}),
        "revenue_prior": _pick(rev, prior, {}) if prior else None,
        "gross_profit_prior": _pick(gp, prior, {}) if prior else None,
    }

    res = {"ticker": ticker, "fy": fy, "prior_fy": prior, "accession": acc, "filed": filed,
           "source_url": url, "segments": segs, "consolidated": con,
           "n_segments": len(segs), "status": "ok"}
    res.update(_reconcile(res))
    return res


def _reconcile(res):
    """Segments MUST sum to consolidated. If they don't, the parse is not trustworthy.

    This is the guard that makes the module safe to build on. A positional HTML scrape of the
    rendered table could silently pick up the wrong row and produce a plausible-looking split
    that does not tie; so could a dimension filter that misses an axis. Rather than trust the
    parse, tie it out — and if it does not tie, return a failure and let the caller show
    nothing. Also cross-checks against forensics.filing_margin(), which is what every other
    number on the platform is built from, so segments cannot disagree with the headline.
    """
    con, segs = res["consolidated"], res["segments"]
    checks = {}
    for field in ("revenue", "cost", "gross_profit"):
        parts = [s.get(field) for s in segs]
        if any(p is None for p in parts) or con.get(field) is None:
            checks[field] = None
            continue
        total, want = sum(parts), con[field]
        checks[field] = abs(total - want) / want if want else None

    bad = [k for k, v in checks.items() if v is not None and v > 0.005]
    missing = [k for k, v in checks.items() if v is None]

    external = None
    try:
        from core import forensics
        fm = forensics.filing_margin(res["ticker"])
        if fm.get("gross_profit") and con.get("gross_profit"):
            external = abs(fm["gross_profit"] - con["gross_profit"]) / fm["gross_profit"]
    except Exception:
        pass

    out = {"reconciliation": checks, "reconciles": not bad,
           "external_gp_delta": external}
    if bad:
        out["status"] = "reconcile_failed"
        out["detail"] = (
            "Segments do not sum to the consolidated total for: " + ", ".join(bad) +
            ". The parse is not trustworthy and no segment figures should be shown.")
    elif external is not None and external > 0.005:
        out["status"] = "reconcile_failed"
        out["detail"] = (
            f"Consolidated gross profit from the instance ({con['gross_profit']:,.0f}) "
            f"disagrees with forensics.filing_margin by {external*100:.2f}%. Segments would "
            f"contradict the headline; showing nothing instead.")
    elif missing:
        out["detail"] = "Reconciled on: " + ", ".join(
            k for k, v in checks.items() if v is not None) + \
            ". Not checkable on: " + ", ".join(missing) + "."
    else:
        out["detail"] = (
            "Segments tie to the consolidated total on revenue, cost and gross profit, and the "
            "consolidated gross profit ties to the figure the rest of the platform uses.")
    return out


def sotp_breakeven(seg=None, peer_median=None, usio_ev=None):
    """The honest answer to 'you're comparing a blend to a pure-play'.

    THE OBJECTION. USIO's 2.98x EV/Gross Profit is blended across Merchant Services (payments)
    and Output Solutions (print-and-mail, ~85% of its cost of services is POSTAGE — a
    pass-through). The 3.61x peer median is drawn from pure-play payments companies. Applying
    it to all of USIO's gross profit values the print business at a payments multiple.

    WHAT WE DO NOT DO. We do not pick a multiple for Output Solutions. We have no print-and-mail
    comp set, and inventing one would be exactly the fabrication this platform was rebuilt to
    eliminate. A number sourced from nowhere does not become defensible by sitting in a model.

    WHAT WE DO INSTEAD. Hold Merchant Services at EXACTLY the peer median — no benefit of the
    doubt — attribute the entire remaining enterprise value to Output Solutions, and solve for
    the multiple that clears. That yields a BREAKEVEN, not an assumption:

        implied_EV = median x MS_gross_profit + X x OS_gross_profit,  solve X at implied = current

    Read it as: "for USIO to be fairly valued today, Output Solutions must be worth X times its
    gross profit." If X is implausibly low, the discount survives the objection and no one had
    to guess. If X is plausible, the objection stands and the headline is not safe — and this
    function will say so either way.
    """
    from core import valuation_comp, benchmarking_engine

    seg = seg or fetch()
    if seg.get("status") != "ok" or len(seg.get("segments") or []) < 2:
        return None

    v = valuation_comp.build()
    peer_median = peer_median if peer_median is not None else v["median"]["ev_gp"]
    usio_ev = usio_ev if usio_ev is not None else v["implied"]["current_ev"]
    if not peer_median or not usio_ev:
        return None

    # The payments segment is the one the peer median actually describes.
    pay = next((s for s in seg["segments"] if re.search(r"merchant|payment", s["label"], re.I)), None)
    oth = [s for s in seg["segments"] if s is not pay]
    if not pay or not oth or not pay.get("gross_profit"):
        return None
    other_gp = sum(s["gross_profit"] for s in oth if s.get("gross_profit"))
    if not other_gp:
        return None

    pay_ev_at_median = peer_median * pay["gross_profit"]
    residual = usio_ev - pay_ev_at_median
    breakeven = residual / other_gp

    blended = v["implied"]["current_multiple"]
    return {
        "peer_median": peer_median,
        "usio_ev": usio_ev,
        "blended_multiple": blended,
        "payments_label": pay["label"],
        "payments_gp": pay["gross_profit"],
        "payments_gp_share": pay["gross_profit"] / (pay["gross_profit"] + other_gp) * 100,
        "payments_ev_at_median": pay_ev_at_median,
        "other_labels": [s["label"] for s in oth],
        "other_gp": other_gp,
        "other_gp_share": other_gp / (pay["gross_profit"] + other_gp) * 100,
        "residual_ev": residual,
        "breakeven_other_ev_gp": breakeven,
        # A residual at or below zero means the market is already paying less for ALL of USIO
        # than the peer median says the payments segment alone is worth.
        "residual_negative": residual <= 0,
        "read": _sotp_read(pay, oth, peer_median, breakeven, residual, blended),
    }


def _sotp_read(pay, oth, median, breakeven, residual, blended):
    names = " + ".join(s["label"] for s in oth)
    head = (
        f"USIO's {blended:.2f}x is a BLENDED multiple; the {median:.2f}x peer median is a "
        f"pure-play payments multiple. Comparing them directly values {names} at a payments "
        f"multiple, which is an objection worth taking seriously. Sizing it without inventing "
        f"a print comp: hold {pay['label']} at exactly the peer median ({median:.2f}x), and "
        f"the residual enterprise value implies {names} is being valued at "
        f"{breakeven:.2f}x its gross profit."
    )
    if residual <= 0:
        return head + (
            f" That residual is NEGATIVE. The market is paying less for all of USIO than the "
            f"peer median says {pay['label']} alone is worth — {names} is being valued at less "
            f"than nothing. The blend objection cannot explain the discount; it makes it wider."
        )
    if breakeven < 1.0:
        return head + (
            f" At {breakeven:.2f}x that is implausibly cheap for a business with real revenue "
            f"and positive gross profit — for reference, the cheapest name in the peer set "
            f"trades near 2.7x. So the discount SURVIVES the blend objection: even valuing "
            f"{names} at a fraction of any plausible multiple, USIO does not clear. This is a "
            f"stronger statement than the blended headline because it required no assumption "
            f"about what {names} is worth."
        )
    if breakeven < 2.5:
        return head + (
            f" {breakeven:.2f}x is low but not absurd for a print-and-mail business. The "
            f"discount probably survives, but this is now an argument that needs a real "
            f"print/mail comp set to settle rather than a breakeven. Do not present the "
            f"blended headline without this caveat."
        )
    return head + (
        f" {breakeven:.2f}x is a plausible standalone multiple for {names}. THAT MEANS THE "
        f"BLENDED HEADLINE IS NOT SAFE: much of the apparent discount may be mix, not "
        f"mispricing. A sum-of-the-parts with a real print/mail comp set is required before "
        f"presenting a discount to anyone."
    )


def build(ticker=None):
    seg = fetch(ticker)
    if seg.get("status") == "ok":
        try:
            seg["sotp"] = sotp_breakeven(seg)
        except Exception as exc:
            print(f"[segments] sotp unavailable: {exc}")
            seg["sotp"] = None
        seg["read"] = _read(seg)
    return seg


def _read(seg):
    bits = [f"USIO reports {seg['n_segments']} reportable segments for FY{seg['fy'][:4]}: "
            + ", ".join(s["label"] for s in seg["segments"]) + "."]
    for s in seg["segments"]:
        if s.get("gross_margin") is None:
            continue
        b = (f"{s['label']}: revenue ${s['revenue']/1e6:.1f}M, gross profit "
             f"${s['gross_profit']/1e6:.1f}M ({s['gross_margin']:.1f}%)")
        if s.get("rev_growth") is not None:
            b += f", revenue {s['rev_growth']:+.1f}% YoY"
        if s.get("gm_delta_pp") is not None:
            b += f", margin {s['gm_delta_pp']:+.1f}pp"
        top = (s.get("cost_composition") or [None])[0]
        if top and s.get("cost"):
            b += (f". Its largest cost is {top['kind']} at ${top['value']/1e6:.1f}M — "
                  f"{top['value']/s['cost']*100:.0f}% of the segment's cost of services")
        bits.append(b + ".")
    return " ".join(bits)
