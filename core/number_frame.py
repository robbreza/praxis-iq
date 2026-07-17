"""
core/number_frame.py — what an analyst question actually IS, and what answer it demands.

THE MODEL (from the IR lead, and it is the first frame that explains the whole corpus):

    "Almost every question references a number in the financial statements or
     prepared remarks, and then needs to be judged — is the number the analyst is
     questioning a good number? If it's good, a certain type of response is
     expected; if the number is negative, a certain type of response is expected.
     And it's this they seek or want to know."

So an analyst question is not free-form. It is:

    1. ANCHOR    — a number from the statements or the script.
    2. VALENCE   — the analyst has ALREADY judged that number good or bad. They
                   are not asking you to tell them which it is.
    3. DEMAND    — the valence determines the response the number obliges:
                     GOOD number → prove it REPEATS. ("Is this run-rate, or a
                       one-timer I have to strip out of my model?")
                     BAD number  → prove you CONTROL it, and say WHEN it reverses.
                       ("Is this yours to fix, and by which quarter?")
                     CLAIM/GUIDE → prove it's BACKED. ("What's actually signed?")
    4. TEST      — did management deliver the demanded element?

    A PRESS is the MISMATCH: management answered, but omitted what the valence
    obliged. Not evasion — often a perfectly good answer to a question nobody
    asked.

WHY THIS BEATS EVERYTHING TRIED BEFORE:
  * marker regex ("follow-up") — the word is turn-taking etiquette as often as
    dissatisfaction. Swung 6%→42% across three tweaks. Measures nothing.
  * lexical/IDF continuity — a press REPHRASES by design ("pipeline of
    opportunities" → "levers to push the pace of adoption"), so overlap on the
    five real presses was 0.02–0.08. Structurally wrong instrument.
  * bare semantic "same topic?" — better, but says only THAT they pressed, never
    WHAT was owed. Unauditable.
This frame is falsifiable and inspectable: it names the anchor, the valence, the
demand and the omission, so an IR lead can check the reasoning in seconds rather
than trusting a score. That's the difference between a metric and an argument.

VALIDATED-BY-CONSTRUCTION on our five hand-read presses — all five fit, and both
demands collapse into the same underlying question analysts have been asking USIO
for two years: "is your revenue PREDICTABLE, or does it depend on things you
don't control?"

STATUS: no accuracy figure is claimed. The prior validation attempt was circular
(scored against the regex it replaced). Establishing a real error rate needs
exchanges labelled by a human who is not the author of this module.
"""

import re

DEMANDS = {
    "GOOD": ("REPEATABILITY",
             "The analyst thinks this number is good and is testing whether it RECURS. What is "
             "owed: is it run-rate or one-time, and what makes it repeat? An answer that only "
             "celebrates the number does not discharge this."),
    "BAD": ("CONTROL_AND_TIMING",
            "The analyst thinks this number is bad and is testing whether YOU control it and WHEN "
            "it reverses. What is owed: the mechanism, whether it's yours to fix, and a date or "
            "quarter. An answer that explains the cause but gives no path or timing does not "
            "discharge this."),
    "CLAIM": ("BACKING",
              "The analyst is testing a forward claim or guide. What is owed: what is already "
              "signed/contracted/booked versus assumed, and the schedule. An answer that restates "
              "confidence does not discharge this."),
}

_RUBRIC = """You are analysing one earnings-call Q&A exchange, using a specific model of what an
analyst question IS.

An analyst question anchors on a NUMBER (from the financials or the prepared remarks). The analyst
has ALREADY judged that number — they are not asking you to tell them whether it is good. The
valence determines the response the number OBLIGES:

  GOOD number  -> the analyst is testing REPEATABILITY. Owed: is it run-rate or one-time, and what
                  makes it recur. Celebrating the number does NOT discharge this.
  BAD number   -> the analyst is testing CONTROL AND TIMING. Owed: the mechanism, whether it is
                  management's to fix, and WHEN it reverses. Explaining the cause without a path or
                  a date does NOT discharge this.
  CLAIM/GUIDE  -> the analyst is testing BACKING. Owed: what is already signed/booked vs assumed,
                  and the schedule. Restating confidence does NOT discharge this.

TWO THINGS ABOUT WHY ANALYSTS ASK, AND WHO IS LISTENING:

(A) COMPETITIVE FISHING. An analyst covers a UNIVERSE, not just this company. Some questions are
partly aimed at rivals they also cover — take-rates, per-customer economics, product mechanics,
win/loss detail, pricing. Management refusing THOSE is CORRECT, not a failure: the information has
proprietary cost. Mark such an unmet demand `competitive: true` and verdict WITHHELD, not MISMATCH.
Do not tell management to disclose something that arms a competitor. (This is not opinion: Gow,
Larcker & Zakolyukina 2021 find product-related questions are associated with non-answers, more so
when competition is intense — proprietary cost is the mechanism.)
BUT be strict about what actually qualifies. A company's OWN contracted backlog, signed-vs-assumed
split, margin path or implementation schedule is NOT competitively sensitive — firms disclose that
routinely. Claiming competitive sensitivity over one's own booked revenue is an excuse, not a
reason. If you can't name the rival advantage the disclosure would confer, it isn't competitive.

(B) THE PUBLIC CALL IS NOT WHERE THE REAL ANSWER LANDS. Most of the public Q&A is general knowledge
transfer; the analyst's real question gets answered in the CALLBACK after the call. So do NOT judge
whether the ANALYST ultimately got their answer — they usually do, privately, and you cannot see it.
Judge what THE MARKET heard, because the market is not on the callback. An unmet demand on the
public call leaves every other holder uncertain even if the analyst is satisfied an hour later —
and the tape prices what the market heard, not what the analyst learned.

HOW TO COMBINE (A) AND (B) — the analyst's reaction is EVIDENCE, but it is not the whole verdict,
because acceptance is ambiguous: an analyst may let it go publicly precisely because they will get
it on the callback. So use BOTH the reaction and whether the owed element was actually present:

  * Element PRESENT in the answer                       ⇒ DISCHARGED. Say so; don't manufacture fault.
  * Element ABSENT and the analyst RE-ASKED / sharpened
    it into an either/or / demanded the skipped number  ⇒ MISMATCH. Highest confidence: the demand
                                                          was live and went unmet in public.
  * Element ABSENT but the analyst ACCEPTED and moved on ⇒ DEFERRED. They very likely take it up on
                                                          the callback — but THE MARKET IS NOT ON THE
                                                          CALLBACK and never hears it. This is the
                                                          cheapest thing to fix: nobody pushed back,
                                                          so nobody in the room knows it's missing.
  * Element ABSENT and genuinely competitive             ⇒ WITHHELD. Correct behaviour; the cost is
                                                          that the market stays uncertain. Not a fault.

Do NOT score the answer against an ideal disclosure. If you mark everything MISMATCH you are
measuring your own expectations rather than the call — an earlier version of this rubric returned
9 unmet out of 9 on a call the market took +21%, which is how that error looks.

IMPORTANT: analysts must ask something to be on record, and say "just a quick follow-up" to mean
"my next question" — ignore wording, judge substance. Analysts also REPHRASE when they press, so
never require shared vocabulary. If there are no next words at all, assume they accepted.

Return STRICT JSON, no prose, no code fence:
{"anchor": "<the number/metric the question is about, verbatim if possible, else 'none'>",
 "valence": "GOOD"|"BAD"|"CLAIM"|"NONE",
 "demand": "REPEATABILITY"|"CONTROL_AND_TIMING"|"BACKING"|"NONE",
 "delivered": true|false,
 "missing": "<element omitted — fill this in even when DISCHARGED, as an opportunity — or ''>",
 "accepted_by_analyst": true|false,
 "competitive": true|false,
 "competitive_why": "<the rival advantage disclosure would confer, or '' if not competitive>",
 "verdict": "DISCHARGED"|"MISMATCH"|"DEFERRED"|"WITHHELD"|"NOT_NUMERIC",
 "why": "<one sentence an IR lead can check against the text, citing the analyst's reaction>"}"""


def analyse(question, answer, reaction=""):
    """Frame one exchange. Returns the dict above, or None if the judge fails.

    `reaction` is DECISIVE, not decorative: the analyst is the arbiter of whether
    the demand was met. Scoring the answer against an ideal disclosure instead
    returned 9 unmet demands out of 9 numeric questions on Q1 2026 — the
    best-received call on record (+21%) — which is the same tell as the marker
    regex flagging 42%: an instrument that fails everything is measuring the
    author's expectations, not the call. `missing` is still populated on a
    DISCHARGED verdict, as the opportunity it is.
    """
    import json
    try:
        from core.transcripts import _call_claude
        out = _call_claude(
            f"{_RUBRIC}\n\nQUESTION:\n{(question or '')[:1800]}\n\n"
            f"MANAGEMENT ANSWER:\n{(answer or '')[:2000]}\n\n"
            f"ANALYST'S NEXT WORDS (corroboration only):\n{(reaction or '(none)')[:600]}\n\nJSON:",
            max_tokens=380)
        if not out:
            return None
        m = re.search(r"\{.*\}", out, re.S)
        if not m:
            return None
        d = json.loads(m.group(0))
        d["demand_note"] = DEMANDS.get(d.get("valence"), ("", ""))[1]
        return d
    except Exception as e:
        print(f"[number_frame] judge failed: {e}")
        return None


def summarise(frames):
    """Roll a call's frames into the counts an IR lead acts on.

    The split that matters is MISMATCH vs DEFERRED vs WITHHELD, not "unmet":
      * mismatches — pressed and unmet. Fix first.
      * deferred   — unmet but nobody pushed back, because the analyst will get it
                     on the callback. THE MARKET NEVER HEARS IT. Cheapest to fix
                     precisely because no one in the room flagged it.
      * withheld   — competitively sensitive. Correct to refuse; the cost is
                     market uncertainty, and that's a trade, not a mistake.
    """
    real = [f for f in frames if f and f.get("verdict") != "NOT_NUMERIC"]
    def _v(v):
        return [f for f in real if f.get("verdict") == v]
    mis, defer, withheld = _v("MISMATCH"), _v("DEFERRED"), _v("WITHHELD")
    by_demand = {}
    for f in mis + defer:
        by_demand[f.get("demand", "NONE")] = by_demand.get(f.get("demand", "NONE"), 0) + 1
    return {"numeric_questions": len(real),
            "mismatches": len(mis), "deferred": len(defer), "withheld": len(withheld),
            "discharged": len(_v("DISCHARGED")),
            "market_uninformed": len(mis) + len(defer) + len(withheld),
            "by_demand": by_demand, "frames": frames}
