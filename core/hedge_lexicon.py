"""
core/hedge_lexicon.py — a hedge list built from OUR OWN calls, labelled by
whether the answer actually resolved the analyst's concern.

THE IDEA (from the IR lead, and it is the whole design):

    "We often ask questions to understand what it's NOT — which is a concern
     that could make a violent reaction to the stock."

An analyst question is usually a hypothesis test for a NEGATIVE. "Is X
happening?" means "I need to rule out X, because if X is true my model breaks."
A direct answer eliminates X. A *variation* — indirect, approximate, adjacent —
fails to eliminate it, and the analyst must now price the possibility. That
pricing is the violent reaction. So the thing worth measuring is not sentiment,
and not even hedging per se: it is **did the answer eliminate the concern.**

WHY NOT JUST USE LOUGHRAN-McDONALD: (a) it's licence-restricted for commercial
use; (b) it was validated on 10-K filings, not spoken answers; (c) most
importantly it is outcome-blind — it counts "approximately" the same whether the
analyst walked away satisfied or asked again three times. Our transcripts carry
the outcome, so we can do better on our own narrow question.

THE GROUND TRUTH IS THE ANALYST'S OWN REACTION. After management answers, the
analyst either:
  * signals closure — "that's a great answer", "that's helpful", "got it" — the
    concern is eliminated; or
  * re-asks / presses — "just specifically on…", "so to be clear…", "but what
    I'm trying to get at…" — the answer did not eliminate it.
That's a label produced by the person whose opinion actually moves the stock,
not by a dictionary.

METHOD: split the Q&A into exchanges (analyst question → management answer(s) →
analyst reaction), label each RESOLVED / UNRESOLVED from the reaction, then find
the terms over-represented in UNRESOLVED answers. Those are OUR hedge words —
the language that, in our calls, has historically failed to put a concern to bed.

HONEST LIMITS — read before quoting any of this:
  * Six calls is a small sample. Terms below are indicative, not established;
    the log-ratio is descriptive, not a significance test, and no p-value is
    implied. The list gets meaningful as calls accumulate.
  * It is OUR list: tied to how OUR management speaks. That is a feature for
    tracking us over time and a defect for comparing us with peers — cross-firm
    comparison needs a common instrument (that's what LM would buy).
  * "Moved on" is treated as weakly resolved, but an analyst can also give up.
    We can't tell those apart from text, and we don't pretend to.
"""

import math
import re
from collections import Counter

# Transcription vendors differ on contractions and it silently breaks matching.
# Motley Fool's style EXPANDS them ("that is helpful", "you do not provide", "let
# us say"); the vendor behind our USIO transcripts PRESERVES them ("that's",
# "don't"). Patterns tuned on one corpus therefore miss the other entirely — in
# testing, both of RPAY's "presses" were really closures ("Thanks for that",
# "That is helpful") that simply didn't match, which would have produced a
# headline finding ("RPAY analysts press 4x more than USIO's") that was purely an
# artifact of house style. Normalising first is what makes a cross-vendor
# comparison mean anything.
_CONTRACT = [
    (r"\bthat is\b", "that's"), (r"\bit is\b", "it's"), (r"\bwe are\b", "we're"),
    (r"\byou are\b", "you're"), (r"\bthey are\b", "they're"), (r"\bi am\b", "i'm"),
    (r"\bdo not\b", "don't"), (r"\bdoes not\b", "doesn't"), (r"\bdid not\b", "didn't"),
    (r"\bcan not\b", "can't"), (r"\bcannot\b", "can't"), (r"\bwill not\b", "won't"),
    (r"\bwould not\b", "wouldn't"), (r"\bis not\b", "isn't"), (r"\bare not\b", "aren't"),
    (r"\bwe have\b", "we've"), (r"\bi have\b", "i've"), (r"\bthere is\b", "there's"),
    (r"\bwhat is\b", "what's"), (r"\blet us\b", "let's"), (r"\bwe will\b", "we'll"),
    (r"\byou will\b", "you'll"), (r"\bi will\b", "i'll"),
]
_SMART = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def normalize(text):
    """Fold transcription-house style so patterns match across vendors."""
    t = (text or "").translate(_SMART).lower()
    for pat, rep in _CONTRACT:
        t = re.sub(pat, rep, t)
    return t


# Analyst signals the concern IS eliminated. Run against normalize()d text.
_CLOSURE = re.compile(
    r"\b(great answer|good answer|that's (helpful|great|clear|fair|what i (wanted|needed))|"
    r"very helpful|that helps|helpful|makes sense|got it|understood|perfect|excellent|"
    r"fair enough|appreciate (it|that|the colou?r)|"
    r"thanks?( you)?[,.]?\s*(for (that|those|the)|that|those)|congrat)", re.I)

# Analyst signals it is NOT eliminated — pressing, narrowing, re-asking.
_PRESS = re.compile(
    r"\b(just (specifically|to (be clear|clarify|follow up))|to be clear|to clarify|"
    r"so (are you saying|you'?re saying|if i)|what i'?m (trying|getting) at|"
    r"i'?m trying to (understand|get|figure)|but (what|how|is|are|if)|"
    r"can you (be more specific|quantify|put a number)|any (way to|sense of)|"
    r"how should (we|i) (think|model)|follow(ing)?[- ]up|one more on|back to)", re.I)

_STOP = set("""a an the and or but if of to in on at by for with from as is are was were be been being
have has had do does did will would can could should may might must shall we you they it he she i our
your their its his her that this these those there here what when where which who whom how why not no
yes so than then them us me my mine ours yours theirs about into over under again more most some any
all each very just really quite kind sort like well okay ok now going go got get really lot lots thing
things going know think see say said says look looking come came bit much many little few also too
only even still back up down out off over such own same other another next last first second one two
three per year quarter years quarters""".split())

_WORD = re.compile(r"[a-z][a-z'\-]{2,}")


def _tokens(text):
    return [w for w in _WORD.findall((text or "").lower()) if w not in _STOP]


def build_exchanges(text, turns, boundary, normalize_role):
    from core.morning_after import _clean_body as ma_clean
    """[{question, answers[], reaction, resolved}] for one call's Q&A.

    An exchange = one analyst question, every management turn answering it, and
    the analyst's next utterance (the reaction). Labelled from that reaction.
    """
    seq = []
    for i, m in enumerate(turns):
        if boundary is None or m.start() < boundary:
            continue
        end = turns[i + 1].start() if i + 1 < len(turns) else len(text)
        seq.append({"role": normalize_role(m.group("spk")),
                    "text": " ".join(ma_clean(text[m.end():end]).split())})

    exchanges, i = [], 0
    while i < len(seq):
        if seq[i]["role"] != "Analyst":
            i += 1
            continue
        q = seq[i]
        answers, j = [], i + 1
        while j < len(seq) and seq[j]["role"] not in ("Analyst", "Operator"):
            answers.append(seq[j]["text"])
            j += 1
        reaction = seq[j]["text"] if (j < len(seq) and seq[j]["role"] == "Analyst") else ""
        if answers:
            nreact = normalize(reaction)          # fold vendor house style first
            closure = bool(_CLOSURE.search(nreact))
            press = bool(_PRESS.search(nreact))
            # PRESS WINS over politeness. Analysts are courteous by reflex — "It's
            # helpful. It's a bit of a follow-up. Do you have levers, or is that
            # outside your control?" opens with closure language and is still the
            # most important press in this corpus. Letting closure win scored it
            # resolved. The discriminator is that a genuine new topic ("Thanks for
            # that. And then could you remind us on Consumer?") does NOT trip
            # _PRESS, whereas an explicit same-topic continuation ("follow-up",
            # "just specifically", "to be clear", "back to") does. So "helpful"
            # buys nothing if they immediately ask again.
            resolved = (not press) and (closure or not reaction.strip().endswith("?"))
            exchanges.append({"question": q["text"], "answers": answers,
                              "reaction": reaction, "resolved": resolved,
                              "closure": closure, "press": press})
        i = j if j > i else i + 1
    return exchanges


def build(transcript_texts, min_count=3, top=40):
    """Derive the hedge list. `transcript_texts` = [full_text, …].

    Returns {exchanges, resolved, unresolved, terms:[{term, unresolved_rate,
    resolved_rate, log_ratio, n}], caveat}.
    """
    from core import morning_after as ma

    all_ex = []
    for text in transcript_texts:
        _p, _q, b = ma.split_prepared_qa(text or "")
        if b is None:
            continue
        turns = list(ma._TURN.finditer(text))
        all_ex += build_exchanges(text, turns, b, ma.normalize_role)

    unres = [e for e in all_ex if not e["resolved"]]
    res = [e for e in all_ex if e["resolved"]]
    cu = Counter()
    cr = Counter()
    for e in unres:
        cu.update(set(_tokens(" ".join(e["answers"]))))
    for e in res:
        cr.update(set(_tokens(" ".join(e["answers"]))))

    nu, nr = max(len(unres), 1), max(len(res), 1)
    rows = []
    for term, n in cu.items():
        if n < min_count:
            continue
        pu = n / nu
        pr = cr.get(term, 0) / nr
        # +0.5 smoothing: a term absent from resolved answers must not divide by
        # zero into a fake infinity.
        lr = math.log((pu + 0.5 / nu) / (pr + 0.5 / nr))
        rows.append({"term": term, "n_unresolved": n, "n_resolved": cr.get(term, 0),
                     "unresolved_rate": round(pu, 3), "resolved_rate": round(pr, 3),
                     "log_ratio": round(lr, 2)})
    rows.sort(key=lambda r: -r["log_ratio"])
    return {
        "exchanges": len(all_ex), "resolved": len(res), "unresolved": len(unres),
        "terms": rows[:top],
        "caveat": (f"Derived from {len(all_ex)} Q&A exchanges across our own calls "
                   f"({len(unres)} unresolved / {len(res)} resolved). Log-ratio is DESCRIPTIVE — "
                   "with a sample this small it is not a significance test and no p-value is implied. "
                   "It is also OUR list: good for tracking us over time, not for comparing to peers."),
    }
