"""
core/topic_continuity.py — is the analyst's follow-up about the SAME subject?

WHY THIS EXISTS. The press detector in core/hedge_lexicon.py keyed off phrases
like "just a quick follow-up", and that word is ambiguous in analyst speech:

    RPAY : "Got it. That makes a ton of sense. And then just a quick follow-up
            for me. On [new subject]…"                        → a NEW question
    USIO : "It's helpful. It's a bit of a follow-up. Do you have levers to push
            the pace of adoption, or is that outside your control?"
                                                              → a REAL press

Identical wording, opposite meaning. Marker-based detection scored RPAY at 26%
vs USIO's 6% — an artifact that would have read as "analysts go easier on our
peer". The discriminator is not vocabulary, it's SUBJECT: did the reaction stay
on the topic the analyst originally raised?

THE CONSTRUCT, restated so it can be measured:
    A PRESS = the reaction asks something AND is about the same subject as the
    original question. Politeness is irrelevant; so is the word "follow-up".

METHOD. IDF-weighted cosine over content terms of question vs reaction. IDF is
learned from the corpus of Q&A turns supplied, so terms that are distinctive in
THIS domain ("payfac", "adoption", "onboarded") carry weight while boilerplate
("quarter", "growth", "think") carries little. Deterministic, no dependency, and
inspectable — you can always see which shared terms drove a score.

HONEST LIMITS:
  * Lexical overlap is a proxy for subject. An analyst who re-asks in entirely
    different words ("so is that within your gift?") scores low and is missed.
  * The threshold is calibrated on a handful of hand-read exchanges. It is a
    working cut-off, not a validated constant — the module reports its own
    accuracy on that set rather than asserting correctness.
  * Short reactions have unstable scores; below _MIN_TERMS we abstain rather
    than guess.
"""

import math
import re
from collections import Counter

_WORD = re.compile(r"[a-z][a-z'\-]{2,}")
_MIN_TERMS = 3          # below this a reaction is too short to score honestly

# Conversational scaffolding carries no subject. Deliberately NOT a sentiment or
# hedging list — purely words that say nothing about WHAT is being discussed.
_STOP = set("""a about actually add afternoon again all also am an and another any anything are
around as ask asked at back be because been being bit both but by call can could day did do does
doing done down each even ever every first for from get gets getting give given go going good got
great guys had has have having hear help here hey hi how i if in into is it its just kind know last
let like little long look looking lot lots make makes many maybe me mean means might more morning
most much my need next nice no not now number obviously of off ok okay on once one only or other our
out over people per pretty put question questions quick quite really right said same say says see
seeing seen sense should side since so some something sorry sort still such sure take taking talk
talking than thank thanks that the their them then there these they thing things think this those
thought three through time to today two up us use used very want was way we well were what when
where whether which while who why will with within would year years yeah yes yet you your""".split())


def terms(text):
    return {w for w in _WORD.findall((text or "").lower()) if w not in _STOP}


def build_idf(documents):
    """{term: idf} learned from the supplied Q&A turns. Domain-specific by
    construction: 'payfac' is distinctive here, 'growth' is not."""
    n = max(len(documents), 1)
    df = Counter()
    for d in documents:
        df.update(terms(d))
    return {t: math.log((n + 1) / (c + 1)) + 1.0 for t, c in df.items()}


def continuity(question, reaction, idf):
    """0–1 subject overlap between a question and the analyst's reaction, plus
    the shared terms that drove it. None when the reaction is too short to score.
    """
    q, r = terms(question), terms(reaction)
    if len(r) < _MIN_TERMS or not q:
        return None, []
    default = math.log(2.0) + 1.0        # unseen term ⇒ treat as distinctive
    shared = q & r
    num = sum(idf.get(t, default) for t in shared)
    dq = math.sqrt(sum(idf.get(t, default) ** 2 for t in q))
    dr = math.sqrt(sum(idf.get(t, default) ** 2 for t in r))
    if not dq or not dr:
        return None, []
    # Cosine-style, but numerator uses linear IDF so a single rare shared term
    # ("adoption") moves the score the way a reader would.
    score = num / (dq * dr) if (dq and dr) else 0.0
    ranked = sorted(shared, key=lambda t: -idf.get(t, default))
    return round(min(score, 1.0), 3), ranked[:6]


_JUDGE = (
    "You are analysing an earnings-call Q&A exchange.\n\n"
    "An analyst asked a question. Management answered. The analyst then said something. Decide what "
    "that reaction IS.\n\n"
    "CRITICAL CONTEXT: sell-side analysts must ask something to be on record, and they routinely say "
    "'just a quick follow-up' to mean simply 'my next question' — that is turn-taking etiquette, NOT "
    "dissatisfaction. They are also polite by reflex ('helpful', 'got it') even when unsatisfied. So "
    "IGNORE the wording and judge the SUBJECT:\n\n"
    "  PRESS     — the reaction asks again about THE SAME UNDERLYING CONCERN as the original "
    "question, because the answer did not settle it. Analysts rephrase when they press — they attack "
    "the same concept from a new angle with different words, so do NOT require shared vocabulary. "
    "Classic tell: the analyst restates the concern as a sharper either/or, or asks for the specific "
    "number/mechanism the first answer skipped.\n"
    "  NEW_TOPIC — the reaction asks about a DIFFERENT subject. The first concern was settled (or "
    "dropped) and they have moved on.\n"
    "  CLOSED    — the reaction asks nothing: thanks, sign-off, acknowledgement only.\n\n"
    "Answer with exactly one word: PRESS, NEW_TOPIC, or CLOSED."
)


def classify_semantic(question, answer, reaction):
    """LLM judgement of what the reaction is. Returns the verdict or None.

    Needed because lexical overlap CANNOT detect a press: a press is a rephrasing
    by nature. Measured on our five hand-read presses, IDF-cosine scored
    0.024–0.081 — the analyst who moves from "pipeline of opportunities" to
    "levers to push the pace of adoption" shares no content words at all. Same
    concern, new angle, zero overlap. That's not a tuning problem, it's the wrong
    instrument for the construct.
    """
    if not (reaction or "").strip():
        return "CLOSED"
    try:
        from core.transcripts import _call_claude
        out = _call_claude(
            f"{_JUDGE}\n\nANALYST QUESTION:\n{(question or '')[:1500]}\n\n"
            f"MANAGEMENT ANSWER:\n{(answer or '')[:1500]}\n\n"
            f"ANALYST REACTION:\n{(reaction or '')[:1000]}\n\nOne word:", max_tokens=8)
        if not out:
            return None
        v = out.strip().upper()
        for k in ("NEW_TOPIC", "PRESS", "CLOSED"):
            if k in v:
                return k
    except Exception as e:
        print(f"[topic_continuity] judge failed: {e}")
    return None


def classify(question, reaction, idf, threshold=0.12):
    """Verdict for one exchange's reaction.

    Returns {verdict, score, shared, asks}. verdict ∈
      'press'     — asks AND stays on subject: the concern was not eliminated.
      'new_topic' — asks, but about something else: the analyst moved on.
      'closed'    — doesn't ask: the concern was eliminated (or they stopped).
      'abstain'   — too short to judge; we do not guess.
    """
    asks = bool(reaction) and ("?" in reaction)
    if not (reaction or "").strip():
        return {"verdict": "closed", "score": None, "shared": [], "asks": False}
    score, shared = continuity(question, reaction, idf)
    if not asks:
        return {"verdict": "closed", "score": score, "shared": shared, "asks": False}
    if score is None:
        return {"verdict": "abstain", "score": None, "shared": [], "asks": True}
    return {"verdict": "press" if score >= threshold else "new_topic",
            "score": score, "shared": shared, "asks": True}
