"""The Q2 FY26 call script — built around the two promises management can prove.

THE SITUATION, STATED HONESTLY. USIO has a credibility deficit and it is earned. On the Q2
2025 call management lowered FY2025 revenue guidance to 5%-12% because of "delayed
implementations at two large national accounts". FY2025 landed at **+3.0%** — below the floor
of the LOWERED range. A cut, then a miss through the cut.

So the street has been trained on a pattern: big accounts -> "on track" -> delay -> cut -> miss.
They now take the one number with a track record of being defended (the guidance range) and
discount every forward-looking statement to zero. That is not laziness — it is a rational prior,
and it is why management gave enough on the Q1 2026 call to build an entire P&L (a revenue
range, a cost line they committed to hold, a margin they said had bottomed) and nobody built
the bridge. The inputs come from a source the street has already marked down once.

YOU CANNOT FIX THAT BY SAYING THE CATALYST LOUDER. The $1 billion voucher program gets
discounted for exactly the same reason the national accounts did. What changes a prior is a
specific, near-term, falsifiable claim that LANDS. Management made precisely two:

    1. "I feel that we've hit the bottom on the gross margins this quarter, and we should be
       able to get back to 23%-25% in the short term."          (Hoch, Q1 2026 call)
    2. "Cash SG&A for the rest of the year, roughly flattish."  (confirmed: "That's correct")

Both are checkable on one line of the Q2 release each. That is the entire opportunity. This
script is built around them and nothing else leads.

THE TRAP THIS SCRIPT EXISTS TO AVOID. Q2 FY26 will hand management a +27.6% revenue headline
if the quarter merely repeats Q1. That number is the BASE, not the business: Q2 FY25 was the
weakest quarter of FY2025 (-5.2% vs its own FY average), hit by "the loss of a meaningful
customer in our Payfac business", legacy attrition and prepaid losses. Meanwhile Q2 FY25 carried
the STRONGEST gross profit in the two-year series ($5,140,069 at a 25.8% margin), because the
revenue that went missing was low-margin. So gross profit comps against the hardest quarter in
two years and prints ~FLAT on a quarter where revenue prints +27%.

Leading with that revenue number is the worst available move for THIS company: the most
flattering figure, produced by a base effect, from a management team the street has already
marked down once. The sell-side unpicks it within the hour, and the credibility hole gets
deeper. See core/comp_quality.py.

THE ASSET NOBODY HAS MODELLED. Q2 ends 6/30, so the reported quarter contains ZERO float from
the voucher program. But Texas TEFA funded 2026-07-01 and the Q2 call is in early August — so
by the call management is roughly five weeks into Q3 with REAL BALANCES ALREADY IN THE BANK.

That is the single most valuable thing they have, and it is valuable precisely BECAUSE of the
credibility problem: it is not a forecast. It is an observed fact about the present. "We've been
told as much as $1 billion" is a forward-looking statement the street discounts to zero. "As of
[date], program balances on our platform are $X" is a number they can put in a model today and
defend to their own committee. Analysts want to be right more than they want to be optimistic —
give them something defensible and they will use it; give them a hope and they will strip it out.

REG FD — THIS IS NOT OPTIONAL. Any float figure must be delivered ON THE CALL or in the release,
to everyone at once. It must never go to one analyst, one investor, or one meeting first. The
whole point is public disclosure of an observed fact; selective disclosure of the same fact is a
violation and would turn the best asset on this call into a liability.

WHERE 2027 GETS MADE, AND WHY IT IS NOT IN THIS SCRIPT AS A NUMBER. A full year of program float
plus flat opex is what re-rates the stock, because at ~$20M of gross profit against ~$20M of
opex, USIO sits exactly at the operating-leverage crossover — small gross profit moves are
enormous EPS moves (a 2pp gross margin difference is 4.2x the EPS; see core/mgmt_model.py).
Management should NOT put a 2027 number on this call. They have not earned the right to be
believed about 2027 yet, and a projection would be marked down like every other projection. Give
the street the observed inputs — balances, dwell, margin — and let THEM build 2027. An analyst's
own model is the only model that re-rates a stock, because it is the only one they will defend.
"""

from datetime import date

CREDIBILITY = {
    "fy25_guidance_lowered_to": "5%-12%",
    "fy25_actual": 2.97,
    "why_lowered": "delayed implementations at two large national accounts",
    "source": "Q2 2025 call; FY2025 10-K",
}

PROMISES = [
    {"claim": "Gross margin bottomed in Q1; back to 23%-25% in the short term",
     "quote": ("I feel that we've hit the bottom on the gross margins this quarter, and, you "
               "know, we should be able to get back to 23%-25% in the short term."),
     "who": "Louis Hoch", "call": "Q1 2026", "checkable_on": "one line of the Q2 release",
     "q1_actual": 20.2},
    {"claim": "Cash SG&A roughly flattish for the rest of the year",
     "quote": "Cash SG&A for the rest of the year, roughly flattish. — confirmed: \"That's correct\"",
     "who": "Barry Sine / Louis Hoch", "call": "Q1 2026",
     "checkable_on": "one line of the Q2 release", "q1_actual": 4_356_142},
]


def sections():
    """The script, in order. Order IS the argument — what leads is what gets quoted."""
    return [
        {
            "n": 1, "title": "Open on the promise you kept — gross margin",
            "say": ("Lead with the gross margin against the 23%-25% commitment made last "
                    "quarter. Name the number, name the commitment, and say whether it was met. "
                    "If it was met: this is the first forward claim to land in over a year and "
                    "it should be stated as such, plainly, without a victory lap. If it was "
                    "missed: say so FIRST, before anything good, and explain the mix."),
            "why": ("The street's prior is that USIO's forward statements do not land — a cut "
                    "to 5%-12% and then a 3.0% print. Nothing else on this call buys anything "
                    "back. Every other message is worth more after this one and worth nothing "
                    "before it."),
            "do_not": "Do not open with revenue. See section 3.",
        },
        {
            "n": 2, "title": "Then the second promise — cash SG&A flat",
            "say": ("Cash SG&A against the 'roughly flattish' commitment. State the dollars, not "
                    "a percentage. Then make the leverage explicit ONCE: gross profit is roughly "
                    "the size of opex, so incremental gross profit reaches the bottom line "
                    "almost intact."),
            "why": ("Two kept promises is a pattern; one is an event. Cost is the lever "
                    "management controls, which is exactly why the street gives credit for it "
                    "— margin expansion is self-help and it is credible in a way that a "
                    "pipeline is not."),
            "do_not": ("Do not project an EPS number off the leverage. Show the mechanism and "
                       "stop. They will do the arithmetic and believe their own answer."),
        },
        {
            "n": 3, "title": "Handle the revenue comp BEFORE anyone asks",
            "say": ("State the base effect in the prepared remarks. Q2 last year was the "
                    "weakest quarter of FY2025 and it was hit by a specific PayFac customer "
                    "loss and prepaid attrition — so the YoY revenue rate flatters. Give the "
                    "two-year stack and the comparison against last year's AVERAGE quarter, and "
                    "give them before the Q&A."),
            "why": ("The sell-side computes this within an hour of the release. Being handed it "
                    "in Q&A, from a company with a cut-then-miss history, reads as either not "
                    "knowing your own numbers or hoping nobody checked. Volunteering it is the "
                    "single cheapest credibility purchase on the call."),
            "do_not": ("Do NOT lead with the YoY revenue growth rate. It is the most flattering "
                       "number available and the least defensible one."),
        },
        {
            "n": 4, "title": "The float — report the PRESENT, do not forecast the future",
            "say": ("The voucher program funded July 1. The Q2 call is roughly five weeks into "
                    "Q3, so give the OBSERVED figure: balances on platform as of a stated date, "
                    "loads processed to date, accounts live. Facts with a date on them. Then "
                    "state the economics plainly — interest on balances carries ~100% margin and "
                    "requires no incremental cost of services."),
            "why": ("This is the whole call. 'We've been told as much as $1 billion' is a "
                    "forward-looking statement and this street discounts those to zero — they "
                    "have been trained to. 'As of August 1, balances are $X' is an observed "
                    "fact they can model today and defend to their own committee. It converts "
                    "the catalyst from a hope into an input. Nothing in the reported quarter "
                    "contains it, so if it is not said out loud it does not exist to anyone."),
            "do_not": ("Never give this to one analyst, one investor, or one meeting first — "
                       "Reg FD. On the call, in the release, everyone at once. And do not "
                       "repeat '$1 billion' as though it were contracted: management's own "
                       "hedges were 'we've been told', 'as much as', 'we're not sure how... if "
                       "it all goes on cards'. Quoting the big number without the hedges is how "
                       "the NEXT credibility hole gets dug."),
        },
        {
            "n": 5, "title": "2027 — give the inputs, withhold the number",
            "say": ("Frame the shape, not the size: a full year of program balances against a "
                    "flat cost base. Give the drivers they need — how balances behave, what "
                    "dwell looks like, where margin settles. Then stop."),
            "why": ("A 2027 projection from this management team gets marked down like every "
                    "other projection, because the prior is earned and one good quarter does "
                    "not clear it. But an analyst's OWN 2027 model is the thing that re-rates "
                    "the stock — it is the only one they will defend in print. Analysts want to "
                    "be right more than they want to be optimistic. Hand them defensible "
                    "inputs and they will build the number themselves, and then they will own "
                    "it."),
            "do_not": ("Do not guide 2027 on this call. Do not put the $1B in a slide with an "
                       "EPS number next to it."),
        },
        {
            "n": 6, "title": "Q&A — the three you will get",
            "say": ("(a) 'Isn't the revenue growth just an easy comp?' — Yes, and you said so in "
                    "the prepared remarks. Point back. "
                    "(b) 'Gross margin is still below 23%' (if it is) — Do not re-litigate the "
                    "mix. Say what changed, what didn't, and when it does. "
                    "(c) 'How much of the $1B is real?' — Answer with the observed number and "
                    "the hedges, in that order. Never the other way round."),
            "why": ("Every one of these is predictable, and being visibly ready for the hostile "
                    "version of a question is itself a credibility signal to a room that has "
                    "been burned."),
            "do_not": "Do not answer (c) with an annualised projection.",
        },
    ]


def build():
    return {
        "as_of": date.today().isoformat(),
        "quarter": "Q2 FY2026",
        "credibility": CREDIBILITY,
        "promises": PROMISES,
        "sections": sections(),
        "read": _read(),
    }


def _read():
    return (
        "THE ONE THING: lead with gross margin against the 23%-25% commitment, and lead with "
        "cash SG&A against the 'flattish' commitment. Those are the only two forward claims "
        "management has made that are checkable on this release, and this street needs a "
        "forward claim to land before it will price any other one. FY2025 was a cut to 5%-12% "
        "followed by a 3.0% print; the discount on management's word is earned, and only a kept "
        "promise retires it. "
        "DO NOT LEAD WITH REVENUE. The base manufactures a ~+27% headline while gross profit "
        "prints roughly flat against the hardest comp in two years. It is the most flattering "
        "number on the release and the least defensible, and volunteering the base effect first "
        "is cheaper than being handed it in Q&A. "
        "THE ASSET: the program funded July 1 and the call is ~5 weeks into Q3, so management "
        "can report OBSERVED balances rather than forecast them. That is worth more than the "
        "$1 billion headline precisely because the street discounts forecasts from this issuer "
        "to zero — an observed number with a date on it is something an analyst can put in a "
        "model and defend. Say it on the call, to everyone at once, never in a meeting first. "
        "AND WITHHOLD 2027. A projection gets marked down; an analyst's own model is what "
        "re-rates the stock. Give them the inputs and let them own the number."
    )
