"""The Q2 FY26 script for the case management does not want to plan for: gross margin ~20%.

WHY THIS EXISTS. The base script (core/q2_script.py) is built on management's claim that Q1 was
the gross margin bottom and 23%-25% returns "in the short term". If Q2 prints ~20% again, that
script does not degrade — it INVERTS. Every section that was an asset becomes a liability, and
the instinct in the room will be to reach for the revenue headline, which is the single worst
move available. A call script written only for the good outcome is not a script; it is a hope.

WHAT A 20% PRINT ACTUALLY MEANS, AND IT IS WORSE THAN A MISSED TARGET:

    at 20.2% GM on GUIDED revenue (+11%)  ->  operating income -$497,725, EPS -$0.014

USIO does not clear its own cost base. And that reaches a SECOND commitment: "profitable and
EBITDA positive" was **GUIDED** (Sine read the list back; Hoch: "That's correct"), not a target
like the margin. At 20.2%, EBITDA is ~$405K — technically positive, functionally noise, and GAAP
profitability is gone. So the call is not "we missed a margin goal." It is "a guided commitment
is now at risk," and it must be handled as the larger thing it is.

THE CREDIBILITY ARITHMETIC. This would be the second broken forward statement in about eighteen
months. FY2025 guidance was cut to 5%-12% on "delayed implementations at two large national
accounts" and then landed at +3.0% — below the floor of the cut. Add a failed margin-bottom call
and management is roughly 0-for-2 on checkable forward claims. The street's discount on this
issuer's word stops being a prior and becomes a track record.

THE ONE RULE THAT GOVERNS THIS ENTIRE CALL: **STOP MAKING FORWARD CLAIMS.**

Every instinct in the room will push the other way — "we'll get there next quarter", "the mix
shift is coming", "H2 is when it lands". Do not. A third forward claim from a source now 0-for-2
costs more than it buys: it is not believed, it hands the next call another failure to explain,
and it signals that management has not registered why the first two failed. The company's only
remaining currency is OBSERVED FACT — things that already happened, with dates on them. Spend
only that.

This is the least comfortable advice in this platform and it is the highest-conviction. A
management team that says "here is what happened, here is what we do not yet know, we will not
project until we have earned it" is more investable after a miss than one that re-promises. The
re-promise is what turns a bad quarter into a de-rating.
"""

from datetime import date

# Modelled on GUIDED revenue (+11%), Q1 cash SG&A held flat — i.e. management delivers on
# everything EXCEPT the margin. See core/mgmt_model.guidance_case(11.0, 20.2, "q1_run_rate").
AT_20 = {"gross_margin": 20.2, "operating_income": -497_725, "eps": -0.014,
         "ebitda": 405_255, "gross_profit": 19_146_959}


def sections():
    return [
        {"n": 1, "title": "Open on the miss. Before anything good. No exceptions.",
         "say": ("First words of the prepared remarks: we said 23%-25% in the short term, we "
                 "printed X%, we were wrong about the timing. Then the mechanical reason — which "
                 "revenue mix did not shift, and by how much. Numbers, not adjectives."),
         "why": ("The one thing worse than missing the call is being seen to bury it. This "
                 "management team already has a cut-then-miss on the record; if the margin miss "
                 "arrives after two paragraphs of records and momentum, the read is not "
                 "'disappointing quarter' — it is 'they are managing us'. That read is very "
                 "expensive and very hard to reverse."),
         "do_not": ("Do not open with revenue records, transaction records, or Output growth. Do "
                    "not let the word 'record' appear before the word 'margin'.")},

        {"n": 2, "title": "Do NOT re-promise the recovery",
         "say": ("State what you know and what you do not. 'We are not going to put a timeline "
                 "on the margin recovery on this call' is a COMPLETE and acceptable answer, and "
                 "a stronger one than a date."),
         "why": ("This would be the second failed forward claim in eighteen months — 0-for-2. A "
                 "third is not believed, and it hands the Q3 call another failure to explain. "
                 "Refusing to project is the only move that signals you understand why the "
                 "first two failed. It reads as discipline, not weakness, and it is the "
                 "beginning of the credibility rebuild rather than another withdrawal from it."),
         "do_not": ("Do NOT say 'we expect to get there in Q3/Q4/H2'. Do not restate 23%-25% "
                    "with a new date attached. Do not say 'we still believe'.")},

        {"n": 3, "title": "The revenue headline is now radioactive",
         "say": ("Give the revenue number plainly, in its place, with the base effect attached "
                 "IN THE SAME BREATH: last year's Q2 was the weakest quarter of the year and "
                 "carried a specific PayFac customer loss. Then the two-year stack. Then move on."),
         "why": ("If the quarter repeats Q1, revenue prints ~+27% while gross profit prints "
                 "roughly flat. Leading with +27% on the same call where you missed the margin "
                 "call is the single worst available move: it is the most flattering number, "
                 "manufactured by a base effect, presented by a team that just missed its one "
                 "checkable promise. It converts a bad quarter into a credibility event."),
         "do_not": "Do not use the words 'record revenue' anywhere in the prepared remarks."},

        {"n": 4, "title": "Cash SG&A — the promise that probably DID land",
         "say": ("If cash SG&A held flat, say so with the dollars. This is now the only kept "
                 "commitment on the call and it should be stated as a fact, once, without "
                 "leaning on it."),
         "why": ("Cost is the lever management controls; delivering on it while missing the mix "
                 "is the difference between 'this team cannot execute' and 'this team executed "
                 "what it controls and misjudged what it does not'. That distinction is worth "
                 "real multiple, and it is the only good news that is fully earned."),
         "do_not": ("Do not use it as a pivot away from the margin. It is a fact, not a "
                    "consolation prize, and framing it as an offset makes it read as one.")},

        {"n": 5, "title": "The float is now the ONLY unspent asset — spend it as fact",
         "say": ("The voucher program funded July 1; the call is ~5 weeks into Q3. Give the "
                 "OBSERVED figures: balances on platform as of a stated date, loads processed, "
                 "accounts live. Then stop. State the economics (interest on balances carries "
                 "~100% margin, no incremental cost of services) as arithmetic, not as a promise."),
         "why": ("This is the only thing on the call that is not a forward-looking statement, "
                 "which is precisely why it survives a credibility failure elsewhere. An "
                 "observed balance with a date on it is something an analyst can model today. "
                 "After a missed margin call it is the ONLY thing that will be believed — and if "
                 "it is not said out loud, it does not exist to anyone, because nothing in the "
                 "reported quarter contains it."),
         "do_not": ("Reg FD — on the call or in the release, everyone at once, never a meeting "
                    "first. And do NOT reach for '$1 billion' to change the subject. Quoting the "
                    "big number without management's own hedges ('we've been told', 'as much "
                    "as', 'we're not sure how... if it all goes on cards'), on the day you "
                    "missed a forward call, is how the THIRD credibility hole gets dug. The "
                    "observed number is worth more than the headline precisely today.")},

        {"n": 6, "title": "Show the mechanism with observed data, not projections",
         "say": ("PINless -> RTP is measurable and already happened: RTP went from ~2,000 "
                 "transactions in January to 200,000+ in the latest month, and it is pulling "
                 "from PINless rather than ACH. Give transaction counts and mix percentages. "
                 "Let the direction speak without attaching a margin forecast to it."),
         "why": ("This is the difference between an explanation and an excuse. An excuse says "
                 "'mix will improve'. An explanation says 'here is the mix, measured, moving in "
                 "this direction, at this rate — draw your own conclusion'. The second survives "
                 "a credibility failure because it asks to be checked rather than believed."),
         "do_not": "Do not convert the transaction trend into a margin projection. That is a re-promise."},

        {"n": 7, "title": "Q&A — the questions you will actually get",
         "say": ("(a) 'You said Q1 was the bottom. What changed?' — Answer the question asked. "
                 "The honest answer may be 'we misjudged how fast PINless would grow relative "
                 "to the RTP shift'. Say that. "
                 "(b) 'Is the 10-12% revenue guidance still good?' — This is the real question, "
                 "because at 20% margin the GUIDED 'profitable and EBITDA positive' is at risk. "
                 "Have the answer decided BEFORE the call, with the board. "
                 "(c) 'When does margin recover?' — 'We're not putting a date on it today.' "
                 "(d) 'Is the $1B still happening?' — Observed number, then the hedges. Never "
                 "the reverse."),
         "why": ("(b) is the one that decides the stock, and it is the one most likely to be "
                 "answered badly in the moment. At 20.2% on guided revenue, operating income is "
                 "NEGATIVE and EBITDA is ~$405K — 'profitable and EBITDA positive' was GUIDED, "
                 "not targeted. If that commitment is now at risk, the decision to reaffirm, "
                 "qualify or withdraw it is a BOARD decision made in advance, not a CEO "
                 "improvisation under questioning. Improvising it is how a bad quarter becomes a "
                 "bad year."),
         "do_not": ("Do not reaffirm full-year guidance reflexively because it is the "
                    "comfortable answer in the room. That is exactly how FY2025's 5%-12% "
                    "happened — and then missed.")},
    ]


def build():
    return {"as_of": date.today().isoformat(), "quarter": "Q2 FY2026",
            "scenario": "gross margin ~20% — no recovery", "at_20": AT_20,
            "sections": sections(), "read": _read()}


def _read():
    return (
        "IF Q2 PRINTS ~20%, THIS IS NOT A MISSED TARGET — IT IS A SECOND COMMITMENT AT RISK. At "
        "20.2% on GUIDED revenue (+11%) with cash SG&A held flat, FY2026 operating income is "
        "-$498K and EPS is -$0.014: USIO does not clear its own cost base. And 'profitable and "
        "EBITDA positive' was GUIDED, not targeted — EBITDA at ~$405K is functionally noise. "
        "Whether to reaffirm, qualify or withdraw that guidance is a BOARD decision to be taken "
        "BEFORE the call, not improvised in Q&A. "
        "THE ONE RULE: STOP MAKING FORWARD CLAIMS. This would be the second broken forward "
        "statement in eighteen months — a cut to 5%-12% that then printed +3.0%, and now a failed "
        "margin-bottom call. Roughly 0-for-2. A third claim is not believed, hands the Q3 call "
        "another failure to explain, and signals management has not registered why the first two "
        "failed. 'We are not putting a timeline on the margin recovery today' is a complete "
        "answer and a stronger one than a date. "
        "OPEN ON THE MISS, BEFORE ANYTHING GOOD — the word 'record' must not appear before the "
        "word 'margin'. The ~+27% revenue headline is radioactive on this call: it is "
        "base-manufactured, it is the most flattering number available, and leading with it on "
        "the day you missed your one checkable promise converts a bad quarter into a de-rating. "
        "SPEND THE ONLY CURRENCY LEFT: observed fact. Cash SG&A, if it held. Measured PINless->RTP "
        "mix (2,000 -> 200,000+ transactions), with no margin forecast attached. And the float — "
        "balances on platform as of a stated date, because the program funded July 1 and it is "
        "the only item on this call that is not a forward-looking statement. That is exactly why "
        "it survives when nothing else does."
    )
