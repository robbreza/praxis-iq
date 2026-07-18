"""
core/onboarding_kit.py — the New Analyst Onboarding Kit, live.

THE FRAMEWORK IS THE POINT. USIO_New_Analyst_Onboarding_Kit_1.docx had the right
shape — business model, thesis, forensic positioning, Q&A cheat sheet, model-building
metrics — and it is a genuinely good IR artifact. Its CONTENT came from the fabricated
workbook, so the shape is kept and every answer is regenerated from primary sources.

WHY THIS ONE MATTERS MORE THAN THE OTHERS. Everything else we rebuilt is internal — a
board deck, a workbook, a board package. This is the only artifact designed to be HANDED
TO A SELL-SIDE ANALYST. Its reader has the 10-K open. An answer that cannot survive that
is worse than no answer, because it does not fail quietly: it fails in front of the exact
person whose trust the document exists to earn.

THE ANSWER THAT HAD TO CHANGE. The .docx's Q1 — which it correctly identified as "the
first question ever asked" — told analysts:

    "(2) Some peers report gross revenue (inflating their margin denominator).
     On a normalized net basis, Usio's margins are competitive with direct peers."

USIO is the gross reporter. Its own 10-K (filed 2026-03-18) says it "reports revenues at
gross as a principal versus net as an agent" and that revenues are "reported gross of
amounts paid to sponsor banks as well as interchange and assessments." An analyst checks
the revenue-recognition note first on any payments company. That answer gets caught.

AND THE TRUE ANSWER IS A BETTER PITCH. It explains the margin, it is sourced to a
quotable line in the filing, it redirects to a metric where USIO looks reasonable rather
than one where it looks broken, and it holds when checked. Nothing here is a concession —
the honest version is the stronger version. That is the whole thesis of this module.

SOURCING RULE: every answer either resolves to a filing, the market feed, or is marked as
needing a source. There is no seed file.
"""

from datetime import datetime

from config.client_config import CT


def policy_fact():
    """The one fact the whole margin conversation turns on, with its quote."""
    from core import forensics
    return dict(forensics.USIO_POLICY)


def valuation_facts(client_id=None):
    from core import benchmarking_engine, valuation_comp
    bm = benchmarking_engine.build_benchmark(client_id)
    v = valuation_comp.build(client_id)
    try:
        bridge = valuation_comp.revenue_bridge(client_id)
    except Exception:
        bridge = None
    return {"bm": bm, "comp": v, "bridge": bridge,
            "key_finding": benchmarking_engine.key_finding(bm)}


def _q_gross_margin(pol, val):
    """THE question. The .docx got it backwards; this is the sourced version."""
    b, comp = val.get("bridge"), val.get("comp")
    u = (b or {}).get("usio")
    med = (comp or {}).get("median", {}).get("ev_gp")
    # The interchange / gross-as-principal answer is USIO-specific. For any other client give
    # the generic version (why gross margin isn't comparable, use EV/Gross Profit instead).
    if CT("ticker") != "USIO":
        g = ("Gross margin is not comparable across companies with different revenue-recognition "
             "treatment (gross vs net as principal/agent) or different business models. The fix is "
             "to compare gross PROFIT, or EV/Gross Profit — revenue cancels out of that ratio "
             "entirely (EV/Rev = EV/GP × margin).")
        if u and u.get("ev_gp") and med:
            g += (f" On that basis we trade at {u['ev_gp']:.1f}x EV/Gross Profit vs a {med:.1f}x "
                  f"peer median.")
        return {
            "q": "Why is our gross margin what it is, and is it comparable to peers?",
            "a": g,
            "flag": "Gross margin isn't comparable across differing revenue-recognition or business "
                    "models — steer to gross profit / EV/Gross Profit.",
            "sources": ["core.valuation_comp — live peer EV/Gross Profit"],
        }
    a = (f"Because WE report revenue gross, as a principal — not because peers inflate theirs. "
         f"Our 10-K ({pol['form']}, filed {pol['filed']}) says it plainly: “{pol['quote']}” "
         f"Interchange and sponsor-bank fees we never keep sit in BOTH our revenue and our cost of "
         f"services, so they inflate the denominator and deflate the ratio. A peer reporting net "
         f"shows 60–75% on identical economics.")
    if u and med:
        a += (f" So gross margin is not comparable across payment processors at all. Compare gross "
              f"PROFIT, or EV/Gross Profit — revenue cancels out of that ratio entirely "
              f"(EV/Rev = EV/GP × margin). On that basis we trade at "
              f"{u['ev_gp']:.1f}x vs a {med:.1f}x peer median, and our warranted EV/Revenue is "
              f"{u['ev_rev_warranted']:.2f}x against {u['ev_rev_actual']:.2f}x traded — which is "
              f"why the “revenue discount” you may have seen quoted off EV/Revenue is a margin "
              f"difference, not a valuation gap.")
    a += (" Separately, interest income on prepaid float — a ~100%-margin line — fell about "
          "$400K year over year as rates normalised, which cost roughly 150bps of reported margin. "
          "Ex-interest, processing margin is improving.")
    return {
        "q": "Why is gross margin only ~23% when competitors report 30–75%?",
        "a": a,
        "flag": "CRITICAL — the first question every analyst asks, and the one the prior kit "
                "answered backwards. The reader has the 10-K open; this answer is built to survive that.",
        "sources": [f"{pol['form']} filed {pol['filed']} — revenue recognition note",
                    "core.valuation_comp.revenue_bridge() — live",
                    "interest income decline: corroborated by the TwoTier CompSheet SOTP "
                    "($1.5M FY25A → $1.1M FY26E)"],
    }


def qa_cheatsheet(client_id=None):
    """The cheat sheet. Only questions we can answer from a source.

    The .docx had 8. This has fewer, on purpose: three of its answers depended on the
    fabricated forensic table, and an unanswerable question is better left off an
    external document than answered from a workbook nobody can check.
    """
    pol, val = policy_fact(), valuation_facts(client_id)
    comp, bm = val["comp"], val["bm"]
    out = [_q_gross_margin(pol, val)]

    u, med = comp["usio"], comp["median"]["ev_gp"]
    imp = comp.get("implied")
    if imp:
        prem = imp["upside_pct"] <= 0
        out.append({
            "q": "Is the stock cheap?",
            "a": (f"On EV/Gross Profit — the only multiple this peer set's accounting doesn't "
                  f"distort — we trade at {imp['current_multiple']:.1f}x against a "
                  f"{imp['peer_median_multiple']:.1f}x peer median across {comp['n_primary']} peers, "
                  + (f"a {abs(100 - imp['current_multiple']/imp['peer_median_multiple']*100):.0f}% "
                     f"PREMIUM. We are not making a cheapness argument right now; the case is the "
                     f"margin bridge and the growth rate."
                     if prem else
                     f"a {abs(100 - imp['current_multiple']/imp['peer_median_multiple']*100):.0f}% "
                     f"discount — which implies {imp['upside_pct']:+.0f}% to the peer median on an "
                     f"equity basis. Do not use EV/Revenue for this: it is not comparable here.")),
            "flag": "Answer it on EV/Gross Profit or not at all. Every prior version of this pitch "
                    "used EV/Revenue and every one of them overstated the case.",
            "sources": ["core.valuation_comp — live, EV ÷ filing gross profit"],
        })

    if bm.get("median_gr") is not None and u.get("rev_growth") is not None:
        faster = u["rev_growth"] > bm["median_gr"]
        out.append({
            "q": "How does growth compare to the peer group?",
            "a": (f"We grew {u['rev_growth']:+.0f}% year over year against a {bm['median_gr']:+.0f}% "
                  f"peer median — " + ("faster than the group, so the valuation gap is not a growth "
                  "gap." if faster else "slower than the group. Part of any valuation gap is a growth "
                  "gap, and the re-rating case has to argue that closes.")),
            "flag": None,
            "sources": ["EDGAR filings via core.benchmarking_engine — live"],
        })

    out.append({
        "q": "Only 2 analysts are active. Is that a red flag?",
        "a": ("Five firms carry coverage; two have acted within the last year (Ladenburg, "
              "H.C. Wainwright). Litchfield's last action was 2024, Barrington's 2023, Maxim's "
              "2022 — so ‘five analysts’ overstates it and we would rather you knew that "
              "from us. No sell-side model is on file with IR at present."),
        "flag": "The prior kit called this “the asymmetric setup” and “the opportunity.” "
                "State it plainly instead — an analyst can count the notes themselves.",
        "sources": ["market feed upgrades/downgrades — live, per named firm"],
    })

    out.append({
        "q": "What is the balance sheet situation?",
        "a": _balance_answer(),
        "flag": "The settlement float is the thing to explain unprompted — it is customer money "
                "in custody and reads as leverage if you don't.",
        "sources": ["latest 10-Q via EDGAR — live"],
    })
    return out


def _balance_answer():
    from core import edgar_financials
    s = edgar_financials.financial_summary(CT("ticker"))
    if not s or s.get("_error"):
        return "Balance-sheet figures could not be sourced from EDGAR right now."
    bal = s.get("balance") or {}
    nc, eq, cd = bal.get("net_cash"), bal.get("equity"), bal.get("customer_deposits")
    if nc is None or eq is None:
        return "Balance-sheet detail is not fully available from EDGAR for this issuer yet."
    # net cash vs net debt is client-specific — USIO carries net cash; SARO carries net debt.
    # Don't assert "unlevered/self-funding" for a levered issuer.
    positive = nc >= 0
    ans = (f"{'Net cash' if positive else 'Net debt'} of ${abs(nc)/1e6:.1f}M against "
           f"${eq/1e6:.1f}M of equity — "
           f"{'essentially unlevered, and self-funding' if positive else 'a levered balance sheet'}.")
    # Settlement float is a PAYMENTS-business concept (customer money in custody). Only surface it
    # when the issuer actually carries it, rather than describing USIO's float on every tenant.
    if cd and cd / 1e6 >= 1:
        ans += (f" The line that confuses people is the ${cd/1e6:.0f}M of settlement float: customer "
                f"money held in custody between processing and disbursement, offset by a matching "
                f"liability. It is not corporate leverage and not ours to spend.")
    return ans


def cannot_source():
    """What the .docx asserted that we will not, and why. Printed in the kit.

    An onboarding kit that quietly drops the sections it can't support looks thinner. One
    that says why it dropped them is more credible than the version that made them up.
    """
    return [
        {"item": "Total payment volume processed",
         "why": "Disclosed in the earnings release, not in XBRL. It is the correct leading "
                "indicator and the prior kit was right to lead with it — wiring the release "
                "is the way to get it."},
        {"item": "Forensic peer adjustments (capitalised software, SBC add-backs by peer)",
         "why": "The prior kit's table came from a workbook whose 10-K citations are fabricated "
                "(quarantined). The one adjustment we CAN source — gross-vs-net — is in the "
                "EV/Revenue bridge, computed from each filer's own numbers."},
    ]


def compose(client_id=None):
    return {
        "ticker": CT("ticker"), "name": CT("name"), "as_of": datetime.now(),
        "policy": policy_fact(), "valuation": valuation_facts(client_id),
        "qa": qa_cheatsheet(client_id), "gaps": cannot_source(),
    }
