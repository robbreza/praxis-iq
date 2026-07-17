"""
core/non_answers.py — detect managers NOT answering analyst questions.

METHOD IS NOT OURS. This implements the published classifier from:

    Gow, I. D., Larcker, D. F., & Zakolyukina, A. A. (2021).
    "Non-Answers During Conference Calls."
    Journal of Accounting Research, 59(4), 1349–1384.
    Working paper: https://www.gsb.stanford.edu/faculty-research/working-papers/
                   non-answers-during-conference-calls
    SSRN: https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3310360

Why borrow rather than invent: they hand-tagged a sample of question/answer
pairs, built regexes against a training split, and reported honest out-of-sample
performance — **78.87% true-positive rate, 89.20% accuracy** (in-sample 81.82% /
90.90%, so barely overfit). Our own `_CONCESSION` regex in core/morning_after.py
was an unvalidated guess at the same thing. This replaces guesswork with an
instrument that has a known error rate.

THEIR TAXONOMY (better than our binary "conceded"):
  * REFUSE    — won't answer. "I am not at liberty to give you much more detail."
                Base rate 8.2% of responses (~2.65 per call).
  * UNABLE    — can't answer. "I don't have it in the room." "I do not know."
                Base rate 3.6% (~1.26 per call).
  * AFTERCALL — deflect to offline. "Let's take that after the call."
                Base rate 0.2% (~0.05 per call). Rare, because Reg FD makes
                "call me later" a selective-disclosure problem.

THE BENCHMARK — the reason this matters for IR:
  ~11% of analyst questions elicit a non-answer, stable over time and across
  industries (25th pct ≈7%, 75th ≈14%; lowest materials/energy 9%, highest
  telecom/health care 13%). Average 34.67 responses per call. So a non-answer
  rate is only meaningful against that norm: 11% is NORMAL, not a failure. This
  finally gives the critique a defensible yardstick instead of an opinion.

Regexes and dictionaries below are transcribed from the paper's Tables A.1/A.2.
`_DISC_NOUN` is truncated in the published table (the PDF cuts off mid-list); the
missing tail is noted where it bites, and the effect is a slightly conservative
REFUSE detector — it under-flags rather than over-flags, which is the right way
to be wrong here.
"""

import re

# ── Table A.2 dictionaries (transcribed) ────────────────────────────────────
_WORD_CHAR = r"[\w’',&@#$%_\-\(\)\[\]]"

_DISC_VERB_NO_NOUN = (
    r"(be\b\s?([\w’,&@#$%_\-\(\)\[\]]+\s){0,1}specific|announce|announced|announcing|answer|answered|"
    r"answering|breakdown|breakout|break out|breaking out|broken out|break that out|break it out|"
    r"break those out|breaking that out|breaking it out|breaking those out|broken that out|"
    r"broken it out|broken those out|comment|commented|commenting|disclose|disclosed|disclosing|"
    r"discuss|discussed|discussing|divulge|divulged|divulging|elaborate|elaborated|elaborating|"
    r"estimate|estimated|estimating|forecast|forecasted|forecasting|guide|guided|guiding|predict|"
    r"predicted|predicting|report|reported|reporting|reveal|revealed|revealing|speculate|speculated|"
    r"speculating|say about|say anything|say more|say any more|say much more|say too much|said about|"
    r"said anything|said more|said any more|said much more|said too much|talk about|talked about)")

_DISC_VERB_NOUN = (
    r"(address|addressed|addressing|explain|explanation|get into|get|getting|give|given|giving|"
    r"go into|going into|got into|gotten into|mention|mentioned|mentioning|on record|present|"
    r"presented|presenting|provide|provided|providing|quantified|quantify|quantifying|release|"
    r"released|releasing|speak|speaking|specified|specify|specifying|spoke|supplied|supply|"
    r"supplying|talk|talked|talking|tell|told|update|updated|updating)")

_DEFERRAL = (r"(difficult|impossible|infeasible|hard|decline|refuse|refrain|unable|never|"
             r"all I can|all we can|all I will|all we will|about all)")

# NOTE: the published Table A.2 truncates mid-list in the PDF. Transcribed as far
# as it goes; the tail (roughly "supplier…" onward) is absent, so REFUSE patterns
# that require a {DISC_NOUN} will miss a few nouns. Under-flagging beats
# over-flagging for an IR critique, so this is left honest rather than padded out
# with invented entries.
_DISC_NOUN = (
    r"(too much|much more|account|accounts|acquisition|acquisitions|activity|activities|amount|"
    r"amounts|analysis|answer|answers|anything|asset|assets|backlog|backlogs|balance|balances|"
    r"breakdown|budget|budgets|capital|cash|change|changes|comparison|comparisons|component|"
    r"components|condition|conditions|content|contract|contracts|cost|costs|coverage|credit|data|"
    r"deal|deals|debt|demand|demands|detail|details|development|developments|direction|directions|"
    r"distribution|dollar|dollars|earnings|equity|equities|estimate|estimates|expansion|expansions|"
    r"expectation|expectations|expense|expenses|exposure|fact|facts|factor|factors|fee|fees|figure|"
    r"figures|financing|forecast|forecasts|funding|growth|guidance|income|incomes|information|"
    r"interest|inventory|inventories|investment|investments|liquidity|loan|loans|loss|losses|"
    r"magnitude|magnitudes|management|margin|margins|marketing|metric|metrics|model|models|money|"
    r"name|names|needs|news|number|numbers|operations|option|options|order|orders|partner|partners|"
    r"percent|percentage|percentages|performance|plan|plans|point|points|policy|policies|portfolio|"
    r"portfolios|price|prices|pricing|profit|profits|profitability|progress|project|projects|"
    r"projection|projections|quality|quantification|quantity|quantities|range|ranges|rate|rates|"
    r"ratio|ratios|reason|reasons|reserve|reserves|result|results|revenue|revenues|risk|risks|sale|"
    r"sales|savings|share|shares|size|sizes|specific|specifics|specifically|spending|statement|"
    r"statements|statistic|statistics|strategy|supplier|suppliers)")

_G = {"WORD_CHAR": _WORD_CHAR, "DISC_VERB_NO_NOUN": _DISC_VERB_NO_NOUN,
      "DISC_VERB_NOUN": _DISC_VERB_NOUN, "DEFERRAL": _DEFERRAL, "DISC_NOUN": _DISC_NOUN}


def _c(p):
    return re.compile(p.format(**_G), re.I)


# ── Table A.1 patterns (transcribed) ────────────────────────────────────────
_REFUSE = [
    _c(r"\b{DISC_VERB_NOUN}\b\s?({WORD_CHAR}+\s){{0,2}}no\b\s?({WORD_CHAR}+\s){{0,2}}{DISC_NOUN}\b"),
    _c(r"\b{DISC_VERB_NO_NOUN}\b\s?({WORD_CHAR}+\s){{0,2}}no\b"),
    _c(r"(n(’|'|‘)t|\bnot|cannot|without)\b\s?({WORD_CHAR}+\s){{0,8}}{DISC_VERB_NO_NOUN}\b"),
    _c(r"(n(’|'|‘)t|\bnot|cannot|without)\b\s?({WORD_CHAR}+\s){{0,8}}{DISC_VERB_NOUN}\b\s?"
       r"({WORD_CHAR}+\s){{0,8}}{DISC_NOUN}\b"),
    _c(r"\b{DEFERRAL}\b\s?({WORD_CHAR}+\s){{0,8}}{DISC_VERB_NO_NOUN}\b"),
    _c(r"\b{DEFERRAL}\b\s?({WORD_CHAR}+\s){{0,8}}{DISC_VERB_NOUN}\b\s?({WORD_CHAR}+\s){{0,8}}{DISC_NOUN}\b"),
]
_UNABLE = [
    _c(r"\b(I|we)\b\s?({WORD_CHAR}+\s){{0,2}}((do(n(’|'|‘)t| not))|(can(’t|'t|not| not)))\b\s?"
       r"({WORD_CHAR}+\s){{0,2}}(know|recall|remember)\b"),
    _c(r"\b(I|we) have no idea\b"),
    _c(r"\b(I|we) do(n(’|'|‘)t| not)\b\s?({WORD_CHAR}+\s){{0,2}}(have (the|it|that|this|those))\b"),
    _c(r"(n(’|'|‘)t|\bnot|cannot|without)\b\s?({WORD_CHAR}+\s){{0,8}}(share|sharing|shared)\b\s?"
       r"({WORD_CHAR}+\s){{0,8}}(with)\b"),
]
_AFTERCALL = [_c(r"\b(off-line|offline|after the call|after call|another (time|day))\b")]

# Published base rates (Gow/Larcker/Zakolyukina 2021, Table 1 Panel A + Figures 1–2).
BENCHMARK = {
    "non_answer_rate": 0.11, "p25": 0.07, "p75": 0.14,
    "refuse_rate": 0.082, "unable_rate": 0.036, "aftercall_rate": 0.002,
    "avg_responses_per_call": 34.67, "avg_non_answers_per_call": 3.68,
    "sector_low": 0.09, "sector_high": 0.13,
    "classifier_tpr": 0.7887, "classifier_accuracy": 0.8920,
}


def classify_response(text):
    """(types, hits) for one manager response. types ⊆ {REFUSE, UNABLE, AFTERCALL}."""
    types, hits = set(), []
    for label, pats in (("REFUSE", _REFUSE), ("UNABLE", _UNABLE), ("AFTERCALL", _AFTERCALL)):
        for p in pats:
            m = p.search(text or "")
            if m:
                types.add(label)
                hits.append({"type": label, "phrase": " ".join(m.group(0).split())[:90]})
                break
    return types, hits


def analyze_call(qa_text, responses, labels_reliable=True):
    """Non-answer profile for one call.

    `responses` = the manager turns in the Q&A (analyst turns excluded — the
    measure is about what MANAGEMENT does with a question).

    `labels_reliable=False` when the transcript's speaker labels can't be
    trusted. This is not hypothetical: Q2 2025 attributes management's own
    "We don't have the dollars associated with those programs" to the OPERATOR.
    Filtering operator turns then returns a confident 0% non-answer rate for a
    call that contained a textbook UNABLE on the quarter's central question —
    a false clean bill of health, which is the worst possible failure for this
    metric. When labels are unreliable the caller should pass every Q&A turn and
    set this False; the rate is then reported as indicative only, because the
    denominator mixes analyst and manager turns.
    """
    flagged, per_type = [], {"REFUSE": 0, "UNABLE": 0, "AFTERCALL": 0}
    for r in responses:
        types, hits = classify_response(r.get("text", ""))
        if types:
            for t in types:
                per_type[t] += 1
            flagged.append({"speaker": r.get("speaker"), "types": sorted(types), "hits": hits,
                            "excerpt": " ".join((r.get("text") or "").split())[:220]})
    n = len(responses)
    rate = (len(flagged) / n) if n else 0.0
    b = BENCHMARK["non_answer_rate"]
    if not n:
        read = "No manager responses identified in the Q&A."
    elif rate > BENCHMARK["p75"]:
        read = (f"{rate*100:.0f}% of responses were non-answers — above the 75th percentile "
                f"({BENCHMARK['p75']*100:.0f}%) of the published sample. Analysts notice this.")
    elif rate < BENCHMARK["p25"]:
        read = (f"{rate*100:.0f}% — below the 25th percentile ({BENCHMARK['p25']*100:.0f}%). "
                "Unusually forthcoming.")
    else:
        read = (f"{rate*100:.0f}% vs an ~{b*100:.0f}% norm — normal. Non-answers are a routine part "
                "of a call; only an unusual rate, or a non-answer on the quarter's central issue, "
                "is a finding.")
    if not labels_reliable:
        read = (f"{len(flagged)} non-answer phrase(s) found, but this transcript's speaker labels are "
                "unreliable — management turns are mis-attributed, so the RATE is indicative only. "
                "The flagged phrases below are still real; the denominator isn't.")
    return {"responses": n, "non_answers": len(flagged), "rate": round(rate, 3),
            "by_type": per_type, "flagged": flagged, "labels_reliable": labels_reliable,
            "benchmark": b, "vs_benchmark_pp": round((rate - b) * 100, 1) if labels_reliable else None,
            "read": read}
