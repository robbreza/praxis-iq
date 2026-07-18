"""
core/benchmarking_engine.py — live peer benchmarking analysis (pure compute).

Replaces the single static "gross margin" image the Peer Benchmarking Report
used to show (data/seed/report_images.py had only PBR_P1). Every figure here is
computed from data the platform already tracks: the peer universe (CP(), with
EV/Revenue), USIO's financials (CF()), the live price (market_data), the forward
guidance revenue (consensus/guidance_engine), and per-peer gross-margin/growth
(data/seed/peer_fundamentals.py). No UI — reports_page renders what this returns.

The analysis ranks on EV/GROSS PROFIT and nothing else, because it is the only
multiple this peer set's accounting doesn't distort. USIO reports revenue GROSS as
a principal (10-K filed 2026-03-18) — interchange it never keeps sits in both
revenue and cost of services. Peers vary; several make a per-contract ASC 606
principal/agent judgment. So:

  * EV/Gross Profit  — comparable. Revenue cancels: EV/GP = (EV/Rev) ÷ (GP/Rev).
                       Computed here as EV ÷ the filer's OWN gross profit.
  * EV/Revenue       — NOT comparable across these names. Kept as context only.
  * gross margin     — NOT comparable. Each firm's own figure is a fact and is
                       shown; median_gm is deliberately None (see build_benchmark).

Gross profit comes from core.forensics — filing-sourced, period-aligned, reads 20-F
as well as 10-K, and picks up GAAP gross profit disclosed only in MD&A (FOUR). There
is no vendor fallback for it. data/seed/peer_fundamentals.py still backs EV/Revenue
and growth as a last resort; it no longer touches margin.
"""

import statistics
import threading
from datetime import datetime, timedelta

from config.client_config import CF, CT, CP


def _live_price():
    from core import market_data
    snap = market_data.get_snapshot(CT("ticker"))
    if snap and snap.get("last_price") is not None:
        return snap["last_price"]
    return CT("last_price", 0) or 0


def _fy_revenue():
    """Forward FY revenue for the reporting year — the guidance number written
    through to period_guidance, so EV/Revenue reflects the guidance decision.
    Falls back to annualizing the last reported quarter if none is on record."""
    from core import consensus, guidance_engine
    fy_label = guidance_engine.reporting_fy_label()
    try:
        pg = consensus.get_consensus(None).get("period_guidance", {})
        rev = pg.get(fy_label, {}).get("Revenue Est ($M)")
        if rev:
            return float(rev), fy_label
    except Exception:
        pass
    return round(CF().get("last_rev", 0) * 4, 1), fy_label


def _usio_ev_rev(fy_rev):
    fin = CF()
    price = _live_price()
    shares = fin.get("shares_out_m", 0) or 0
    cash = fin.get("cash_m", 0) or 0
    debt = fin.get("debt_m", 0) or 0
    mktcap = price * shares
    ev = mktcap - cash + debt
    ev_rev = (ev / fy_rev) if fy_rev else None
    detail = {"price": price, "shares_m": shares, "mktcap": round(mktcap, 1),
              "cash": cash, "debt": debt, "ev": round(ev, 1), "fy_rev": fy_rev}
    return (round(ev_rev, 2) if ev_rev is not None else None), detail


def _efficiency(ev_gp):
    """Gross profit as a % of enterprise value — how much gross profit you buy per
    dollar of EV. Higher is cheaper.

    Derived FROM ev_gp (it is just its reciprocal) so the two can never disagree.
    It used to be computed independently as gross_margin ÷ EV/Revenue. That is the
    same thing algebraically — (GP/Rev) ÷ (EV/Rev) = GP/EV — but ONLY if both share
    the same revenue. They stopped doing so the moment gross margin came from the
    filing and EV/Revenue from Yahoo: the revenues no longer cancelled, and the two
    metrics drifted apart (FOUR by a full point). One number, one definition.
    """
    return round(100.0 / ev_gp, 1) if ev_gp else None


# forensics statuses whose gross profit came from the filer's own annual report.
_FILING_OK = ("ok", "derived", "ok_mda")


def _ev_gp(ev, gross_profit):
    """EV/Gross Profit — the one comp metric this peer set's accounting doesn't
    distort, computed as EV ÷ the filer's OWN gross profit.

    IT USED TO BE (EV/Rev) ÷ gross margin, which is algebraically identical BUT
    inherited whatever the gross margin's source was. That let a vendor number in
    through the back door and it was not harmless:

      * FOUR — Yahoo said 35.1%; the 10-K says 32.4%. EV/GP read 5.9x, not 6.9x.
      * CASS — Yahoo said 47.6% for a company whose 10-K uses the phrase "gross
        profit" ZERO times. It is a bank. The multiple was pure fiction, and it sat
        immediately above USIO, dragging the peer median UP and the "discount" with it.

    Now: EV is the only market input, gross profit must come from a filing, and a
    company with no gross profit line has no EV/GP. None is the correct answer for a
    metric that does not exist — not a reason to reach for a substitute.
    """
    return round(ev / gross_profit, 1) if (ev and gross_profit and ev > 0) else None


def _resolve_company(ticker, name, curated, is_client=False):
    """Resolve one company's comp metrics with source provenance:
      gross margin / gross profit — FILING ONLY (core.forensics). No market or
        curated fallback: a vendor's constructed margin is not a reported one, and
        pretending otherwise is what put false findings into a board PDF. A filer
        with no gross profit line (CASS, GDOT — banks) gets None and drops out of
        every margin-based comparison.
      revenue growth — filing > market > curated
      EV/Revenue — market (Yahoo, one consistent trailing basis). A name whose
        EV is non-positive — a bank whose cash holds customer deposits, or a
        net-cash name — is flagged ev_excluded and dropped from the EV comps
        (it isn't EV-comparable); curated is used only if Yahoo has nothing."""
    from core import edgar_financials, forensics, market_data
    # Revenue growth still comes from the filing > market chain: growth is growth, and
    # it carries none of the gross-vs-net comparability problem that gross margin does.
    fs = edgar_financials.financial_summary(ticker)
    fi = fs.get("income", {}) if (fs and not fs.get("_error")) else {}
    yf = market_data.get_fundamentals(ticker) or {}

    # GROSS MARGIN / GROSS PROFIT: FILING ONLY. No market fallback, no curated
    # estimate. There used to be a filing > market > curated chain here and it was
    # the single most damaging line in this module — it silently substituted a
    # vendor's constructed margin whenever EDGAR came up short, and every downstream
    # consumer (EV/GP, the median, the discount, the board PDF, the IR plan) treated
    # the result as filing-grade. forensics.filing_margin() is period-aligned, reads
    # 20-F as well as 10-K, and picks up GAAP gross profit disclosed only in MD&A.
    fx = forensics.filing_margin(ticker)
    if fx["status"] in _FILING_OK:
        gm, gm_src, gp = fx["gross_margin"] * 100, "filing", fx["gross_profit"]
    else:
        # No gross profit in the filings — say so. CASS and GDOT are banks and have
        # no such line at all; a vendor figure for them is constructed, not reported.
        gm, gm_src, gp = None, fx["status"], None

    if fi.get("rev_growth_yoy") is not None:
        growth, gr_src = fi["rev_growth_yoy"], "filing"
    elif yf.get("rev_growth") is not None:
        growth, gr_src = yf["rev_growth"], "market"
    else:
        growth, gr_src = curated.get("rev_growth"), "est"

    ev_excluded = False
    if yf.get("ev_rev") is not None and not yf.get("ev_positive"):
        ev_rev, ev_src, ev_excluded = None, "excluded", True
    elif yf.get("ev_positive"):
        ev_rev, ev_src = yf["ev_rev"], "market"
    else:
        ev_rev, ev_src = curated.get("ev_rev"), "est"

    # EV AT THE LIVE PRICE, not the one cached with the fundamentals.
    # get_fundamentals caches 24h; the price snapshot caches 60 minutes. Reading
    # yf["enterprise_value"] served an EV computed at whatever the price was when the
    # fundamentals were last fetched — measured 7.8% stale on 2026-07-16 with USIO down
    # 7.5% on the day. EV is the numerator of every multiple in this module, so that
    # error propagated into EV/GP, the peer median, the discount and the implied value.
    # live_ev() rebuilds it as (live price x cached shares) + cached net debt.
    live = market_data.live_ev(ticker)
    ev = live["enterprise_value"] if live else yf.get("enterprise_value")
    mcap = live["market_cap"] if live else yf.get("market_cap")
    return {
        "ticker": ticker, "name": name, "is_client": is_client,
        "shares_outstanding": (live or {}).get("shares_outstanding") or yf.get("shares_outstanding"),
        "ev_is_live": bool(live),
        "ev_rev": ev_rev,
        "gross_margin": round(gm, 1) if gm is not None else None,
        "gross_profit": gp, "gp_period": fx.get("period"),
        "gm_detail": fx.get("detail"),
        "rev_growth": round(growth, 1) if growth is not None else None,
        "ev_gp": _ev_gp(ev, gp),
        "efficiency": _efficiency(_ev_gp(ev, gp)),
        "gm_source": gm_src, "growth_source": gr_src, "ev_source": ev_src,
        "ev_excluded": ev_excluded,
        "market_cap": mcap, "enterprise_value": ev,
    }


# Per-process memo. build_benchmark() fans out to _resolve_company across the whole
# comp set — 9 companies x (companyfacts parse + forensics + live EV + several Neon
# round-trips). ONE render of the board package called it THREE times: board_package
# .valuation() calls it directly, valuation_comp.build() calls it again, and
# revenue_bridge() calls build() which calls it a third time. Same inputs, same answer,
# three times the latency.
#
# 45s TTL: long enough that a single render pays once, short enough that a price refresh
# or a peer-set edit is felt on the next interaction rather than the next restart.
_BM_TTL = timedelta(seconds=45)
_bm_memo = {}
_bm_lock = threading.Lock()


def clear_cache():
    """Drop the memo — call after editing the peer universe or forcing a refresh."""
    with _bm_lock:
        _bm_memo.clear()


def build_benchmark(client_id=None, force=False):
    if not force:
        with _bm_lock:
            hit = _bm_memo.get(client_id)
            if hit and datetime.now() - hit[0] < _BM_TTL:
                return hit[1]
    out = _build_benchmark_uncached(client_id)
    with _bm_lock:
        _bm_memo[client_id] = (datetime.now(), out)
    return out


def _build_benchmark_uncached(client_id=None):
    from core import forensics
    from data.seed.peer_fundamentals import get_peer_fundamentals
    fund = get_peer_fundamentals()

    # Warm every company's SEC facts in parallel before resolving them one by one.
    # _resolve_company -> filing_margin -> _facts is otherwise 9 sequential HTTP
    # round-trips (~4.7s of a ~10s cold render) waiting on one at a time.
    try:
        forensics.prefetch([CT("ticker")] + [p.get("ticker") for p in CP() if p.get("ticker")])
    except Exception as exc:
        print(f"[benchmark] prefetch skipped: {exc}")

    usio = _resolve_company(CT("ticker"), CT("name"), {}, is_client=True)
    peers = []
    for p in CP():
        r = _resolve_company(p.get("ticker"), p.get("name"), fund.get(p.get("ticker"), {}))
        r["tier"] = p.get("tier", "primary")
        r["segment"] = p.get("segment", "")
        r["closest_analog"] = bool(p.get("closest_analog"))
        peers.append(r)
    rows = [usio] + peers

    # The median is computed from PRIMARY peers only. The large-cap "reference"
    # names (FI / GPN / TOST) set the industry growth and margin bar but aren't
    # valuation comps — you don't apply a $100B processor's multiple to a micro-
    # cap — so they're shown separately and excluded from every median and rank.
    primary = [p for p in peers if p.get("tier") != "reference"]
    reference = [p for p in peers if p.get("tier") == "reference"]

    peer_ev = [p["ev_rev"] for p in primary if p["ev_rev"]]
    peer_gp = [p["ev_gp"] for p in primary if p["ev_gp"] is not None]
    peer_gm = [p["gross_margin"] for p in primary if p["gross_margin"] is not None]
    peer_gr = [p["rev_growth"] for p in primary if p["rev_growth"] is not None]
    median_ev = round(statistics.median(peer_ev), 2) if peer_ev else None
    median_gp = round(statistics.median(peer_gp), 1) if peer_gp else None
    # NO MEDIAN GROSS MARGIN. Deliberately None, and this is not an oversight.
    # Every margin here is now filing-sourced, but they are still measured on
    # DIFFERENT BASES: USIO and FOUR report revenue gross (interchange included),
    # RPAY/PSFE/others net or mixed per-contract under ASC 606. Taking the median of
    # 23.1% (gross) and 75.0% (net) produces a number that describes no company and
    # invites exactly the comparison this report exists to prevent. Each firm's own
    # margin is a fact and is still shown; the central tendency of the set is not.
    # Use median_gp — gross profit is presentation-invariant.
    median_gm = None
    median_gr = round(statistics.median(peer_gr), 1) if peer_gr else None
    discount = round((1 - usio["ev_rev"] / median_ev) * 100) if (usio["ev_rev"] and median_ev) else None
    discount_gp = round((1 - usio["ev_gp"] / median_gp) * 100) if (usio["ev_gp"] and median_gp) else None

    # Rank on EV/Gross Profit (cheapest first) within USIO + the primary comps.
    gp_ranked = sorted([r for r in ([usio] + primary) if r["ev_gp"] is not None], key=lambda r: r["ev_gp"])
    usio_gp_rank = next((i + 1 for i, r in enumerate(gp_ranked) if r["is_client"]), None)
    next_cheapest = next((r for r in gp_ranked if not r["is_client"]), None)
    excluded = [r for r in peers if r["ev_excluded"]]
    short = max([p for p in primary if p["ev_gp"] is not None], key=lambda r: r["ev_gp"], default=None)
    closest = next((p for p in peers if p.get("closest_analog")), None)

    return {
        "usio": usio, "peers": peers, "rows": rows,
        "primary": primary, "reference": reference, "closest": closest,
        "median_ev": median_ev, "median_gp": median_gp, "median_gm": median_gm, "median_gr": median_gr,
        "discount": discount, "discount_gp": discount_gp,
        "gp_ranked": gp_ranked, "usio_gp_rank": usio_gp_rank, "next_cheapest": next_cheapest,
        "excluded": excluded, "short": short,
    }


def key_finding(bm):
    """One-paragraph BLUF — leads with EV/Gross Profit (the payments-appropriate
    metric), with EV/Revenue as supporting colour."""
    u = bm["usio"]
    parts = []
    if bm.get("closest"):
        c = bm["closest"]
        parts.append(f"Closest operating analog: {c['ticker']} ({c['name']}) — its integrated card + ACH + "
                     f"document/billing mix is unusually close to {u['ticker']}'s. Benchmarked against a "
                     f"segmented peer set (integrated payments, billing/output, prepaid), not one generic "
                     f"payments median.")
    if bm["discount_gp"] is not None:
        rank = (f"the cheapest of {len(bm['gp_ranked'])}" if bm["usio_gp_rank"] == 1
                else f"#{bm['usio_gp_rank']} of {len(bm['gp_ranked'])}")
        nc = bm["next_cheapest"]
        vs = f" (next: {nc['ticker']} {nc['ev_gp']:.1f}x)" if nc else ""
        parts.append(
            f"{u['ticker']} trades at {u['ev_gp']:.1f}x EV/Gross Profit vs a peer median of "
            # A negative discount is a PREMIUM. Printing "a -3% discount" buries the sign
            # in a word that means the opposite, which is how an unfavourable read gets
            # skimmed as a favourable one.
            f"{bm['median_gp']:.1f}x — a {abs(bm['discount_gp']):.0f}% "
            f"{'discount' if bm['discount_gp'] > 0 else 'PREMIUM'} and {rank} in the group{vs}. "
            f"EV/Gross Profit is the only multiple this peer set's accounting doesn't distort: "
            + ("USIO reports revenue GROSS as a principal, so interchange it never keeps inflates "
               "its revenue and deflates its margin. "
               if u['ticker'] == 'USIO' else
               "gross-vs-net revenue treatment varies across these companies. ")
            + f"Revenue cancels out of EV/Gross Profit; it does not "
            f"cancel out of EV/Revenue, which is why {u['ticker']}'s {u['ev_rev']:.1f}x vs the "
            f"{bm['median_ev']:.1f}x median OVERSTATES how cheap it is and is not a usable comparison.")
    if u.get("rev_growth") is not None and bm["median_gr"] is not None:
        faster = u["rev_growth"] > bm["median_gr"]
        # The old text asserted "so the discount isn't a growth discount" on BOTH
        # branches — i.e. it drew the favourable conclusion even while reporting that
        # USIO grew slower. The conclusion has to follow the number, not precede it.
        parts.append(
            f"It grows {'faster' if faster else 'slower'} than the group "
            f"({u['rev_growth']:.0f}% vs {bm['median_gr']:.0f}% median)" +
            (" — so the discount isn't a growth discount." if faster else
             " — so part of the discount is a growth discount, and the re-rating case has to argue "
             "that gap closes."))
    if bm["short"]:
        parts.append(
            _pair_trade(bm, u))
    return " ".join(parts)


def _pair_trade(bm, u):
    """The pair-trade read.

    It used to hardcode LONG the client: `f"LONG {u['ticker']} / SHORT {short}"`,
    regardless of where the client actually ranked. That was only ever invisible
    because USIO happened to be near the cheapest. On the adopted two-tier peer set
    USIO ranks #4 of 6 — MQ, RPAY and PMTS are all cheaper — so "LONG USIO" would be
    asserting a trade the table on the same page contradicts. The long leg is the
    cheapest name on the ranking, whoever that is.
    """
    short = bm.get("short")
    ranked = [r for r in bm.get("gp_ranked", []) if r.get("ev_gp") is not None]
    if not short or not ranked:
        return ""
    cheap = ranked[0]
    if cheap["is_client"]:
        return (f"Pair-trade read: LONG {u['ticker']} / SHORT {short['ticker']} "
                f"({short['ticker']} {short['ev_gp']:.1f}x EV/Gross Profit, the priciest in the "
                f"group; {u['ticker']} the cheapest at {u['ev_gp']:.1f}x).")
    return (f"Pair-trade read: the cheapest name in the group is {cheap['ticker']} "
            f"({cheap['ev_gp']:.1f}x EV/Gross Profit), not {u['ticker']} ({u['ev_gp']:.1f}x) — "
            f"a long/short built off this table would be LONG {cheap['ticker']} / SHORT "
            f"{short['ticker']} ({short['ev_gp']:.1f}x) and would not involve {u['ticker']} at all. "
            f"That is the read a hedge fund gets from these comps.")
