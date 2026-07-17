"""
core/morning_after.py — the morning-after call critique, at buy-side standard.

WHAT THIS ANSWERS, in the order an IR lead actually asks it:
  1. What did the tape do?            — close→next open (executable prints only)
  2. What did we say?                 — prepared remarks, with real delivery timing
  3. What did they ask ANYWAY?        — Q&A topics we failed to pre-empt
  4. What carried over?               — topics that recurred from last quarter
  5. So what do we fix next quarter?  — the actionable list

THE KEY INSIGHT: the prepared remarks in the transcript ARE the script as
delivered. So pre-emption is measurable directly — no separate script file
needed, and no reliance on anyone having archived the right draft. For each
topic an analyst raised in Q&A, we ask whether the prepared remarks had already
addressed it. That ratio is the pre-empt score the old static scorecard quoted
("8/12") but never computed.

TIMING is real, not estimated: these transcripts carry per-speaker timestamps,
so section durations are measured off the tape rather than inferred from word
counts at an assumed speaking rate.

STANDARD (from USIO INVESTMENT CASE.docx, the reference the IR lead set): a
critique is only useful if it names the investor hesitation, says whether the
call resolved it, separates the headline from what the buy-side actually models,
gives the MECHANICAL why, and cites its evidence. The deterministic facts below
are assembled here; narrative() hands those facts (and only those facts) to the
model to write in that register — it is never asked to supply a number.
"""

import re
from datetime import datetime

from config.client_config import get_active_client_id
from core import db

# The prepared/Q&A seam. Wording varies by transcription vendor, so several
# phrasings are matched — but each must be UNAMBIGUOUS. Note the trap: the
# operator's opening boilerplate ("After today's presentation, there will be an
# opportunity to ask questions") appears ~2k chars in, and a loose pattern that
# matched it would split the call near the top, tagging the prepared remarks as
# Q&A and wrecking both the timing and the pre-empt analysis. So no pattern here
# may match a mere mention of questions — only an explicit handover.
_QA_BOUNDARY = re.compile(
    r"(open the (?:call|floor|line)s? (?:up )?(?:to|for) questions"
    r"|(?:begin|conduct|start)(?:ing)?\s+(?:the|that|our)\s+question[- ]and[- ]answer"
    r"|turn (?:the )?call back (?:over )?to the operator"
    r"|first question\s+(?:today\s+)?comes from"
    r"|we(?:'ll| will) now (?:begin|take) (?:the )?questions)", re.I)

# "Speaker/role line\n00:MM:SS" — a turn header. The line before the timestamp is
# the ROLE ("SVP of Investor Relations at Usio"), which is what we want: timing by
# role is the IR question, not timing by person.
#
# The char class must allow commas and digits. Without commas, "Founder, Chairman,
# and CEO at Usio" silently failed to match — dropping the CEO's turns entirely
# and, worse, SILENTLY INFLATING the preceding speaker, because a turn's duration
# runs to the next MATCHED turn. Any unmatched turn is absorbed into its
# predecessor rather than lost, so the error masquerades as a plausible number.
_TURN = re.compile(r"^(?P<spk>[A-Z][A-Za-z0-9 .,'&()/\-]{2,90})\n(?P<ts>\d{2}:\d{2}:\d{2})\s*$", re.M)

_STOP = {"the", "and", "for", "with", "that", "this", "from", "into", "over", "under",
         "growth", "revenue", "impact", "outlook", "timeline", "rates", "specificity",
         "drivers", "recovery", "penetration", "attrition", "portfolio", "risk"}

# ── Reading the Q&A as an arena, not a scorecard ────────────────────────────
# Sell-side analysts MUST ask something: they need to be on record having engaged
# with the call or their opinion carries no weight. So a question is not, by
# itself, evidence that the script failed. Most questions are one of:
#   * fishing for INCREMENTAL colour — the trend, the cadence, the forward read.
#     You cannot pre-empt a request for more than you said; that's the job.
#   * positioning — a big-picture question to sound smart, which management may
#     legitimately wave off.
# What actually indicts a script is narrower and needs EVIDENCE:
#   * management could not answer ("we don't have the dollars") — that tells the
#     buy-side the company isn't modelling its own forward revenue;
#   * management conceded something material that the script had framed as
#     upside (implementation delays "outside our control");
#   * the topic RECURS quarter after quarter — the language never landed;
#   * analysts pressed repeatedly / from several angles.
# Everything else is the arena working as designed.
_CONCESSION = re.compile(
    r"\b(conced|acknowledg|admit|could not|couldn't|unable|did ?n[o']t (?:quantify|provide|answer|have)|"
    r"no (?:specific )?(?:answer|figure|number)|don'?t have the|not (?:able|prepared) to|"
    r"declined|vague|deflect|non-?committal|stated 'we)", re.I)
_PRESSURE = re.compile(
    r"\b(pressed|repeatedly|multiple times|again|twice|three times|two angles|several angles|"
    r"challeng|demand|push(?:ed|ing) back|follow(?:ed)?[- ]up)", re.I)
_RITUAL = re.compile(
    r"\b(macro|macro-?economic|economy|economic (?:slowdown|headwind|conditions)|job report|"
    r"interest rate environment|industry (?:trend|dynamic)|secular|big picture|"
    r"competitive landscape|tariff|election)", re.I)
_INCREMENTAL = re.compile(
    r"\b(elaborate|more (?:colour|color|detail|specific)|what gives (?:you )?confidence|"
    r"cadence|trajectory|going forward|trend|how should we (?:think|model)|quantif|"
    r"break ?out|timeline|when (?:do|will)|outlook)", re.I)


def _secs(ts):
    h, m, s = (int(x) for x in ts.split(":"))
    return h * 3600 + m * 60 + s


def normalize_role(label):
    """Collapse a transcript's speaker label to a stable IR role.

    Necessary for ANY cross-quarter comparison: the vendor relabels the same
    person every quarter — "Founder, Chairman, and CEO at Usio", "Chairman and
    CEO at Usio", "Founder, Chairman, CEO and President at Usio" are one man, and
    left raw they fragment into three separate rows that can't be trended. Some
    transcripts don't name speakers at all ("Speaker 5"), which is a real gap and
    is reported as Unknown rather than guessed at.
    """
    s = (label or "").lower()
    if s.startswith("operator"):
        return "Operator"
    if re.match(r"^speaker\s*\d+$", s.strip()):
        return "Unknown speaker"
    if "investor relations" in s:
        return "IR"
    if "chief executive" in s or re.search(r"\bceo\b", s):
        return "CEO"
    if ("chief revenue" in s or re.search(r"\bcro\b", s) or "payment acceptance" in s):
        return "CRO"
    if ("chief financial" in s or re.search(r"\bcfo\b", s)
            or "accounting officer" in s or "chief accounting" in s):
        return "CFO/CAO"
    if "analyst" in s or " at " in s:
        return "Analyst"
    return label or "Unknown"


def split_prepared_qa(text):
    """(prepared_remarks, qa, boundary_char). Falls back to (all, '', None) when
    no seam is found — better to treat everything as prepared than to silently
    mis-attribute Q&A."""
    m = _QA_BOUNDARY.search(text or "")
    if not m:
        return text or "", "", None
    return text[:m.end()], text[m.end():], m.end()


# A turn header in this format is: "Name\nName\nRole/Title\nHH:MM:SS". _TURN
# anchors on the TITLE line, so a turn's body runs up to the NEXT speaker's NAME
# lines and swallows them — every turn's text ended with the next speaker's name
# ("…Such as? Louis Hoch"). That inflates word counts slightly and poisons any
# term-overlap work, where "louis"/"hoch" showed up as the top shared terms
# between a question and its follow-up.
_TRAILING_NAME = re.compile(r"(?:\n[A-Z][A-Za-z.'\-]+(?: [A-Z][A-Za-z.'\-]+){0,3})+\s*$")


def _clean_body(s):
    """Drop the next speaker's name lines from the end of a turn body."""
    return _TRAILING_NAME.sub("", s or "").strip()


def speaker_timeline(text):
    """[{speaker, start_s, end_s, dur_s, words, section}] from the transcript's
    own timestamps — measured delivery, not a words÷wpm estimate."""
    turns = list(_TURN.finditer(text or ""))
    if not turns:
        return []
    _, _, boundary = split_prepared_qa(text)
    out = []
    for i, m in enumerate(turns):
        body_start = m.end()
        body_end = turns[i + 1].start() if i + 1 < len(turns) else len(text)
        start = _secs(m.group("ts"))
        end = _secs(turns[i + 1].group("ts")) if i + 1 < len(turns) else None
        out.append({
            "speaker": m.group("spk").strip(),
            "start_s": start,
            "end_s": end,
            "dur_s": (end - start) if end is not None else None,
            "words": len(_clean_body(text[body_start:body_end]).split()),
            "section": "qa" if (boundary and m.start() >= boundary) else "prepared",
        })
    return out


def section_timing(text):
    """Minutes on the clock per speaker in the PREPARED remarks, plus totals.
    This is what answers 'did the business review run long?' with the tape
    rather than an estimate."""
    tl = speaker_timeline(text)
    if not tl:
        return None
    prepared = [t for t in tl if t["section"] == "prepared" and t["dur_s"]]
    by_spk = {}
    for t in prepared:
        role = normalize_role(t["speaker"])
        d = by_spk.setdefault(role, {"speaker": role, "raw": set(), "seconds": 0, "words": 0, "turns": 0})
        d["raw"].add(t["speaker"])
        d["seconds"] += t["dur_s"]
        d["words"] += t["words"]
        d["turns"] += 1
    for d in by_spk.values():
        d["minutes"] = round(d["seconds"] / 60.0, 1)
        d["wpm"] = round(d["words"] / (d["seconds"] / 60.0)) if d["seconds"] else None
        d["raw"] = sorted(d["raw"])   # keep the source labels for traceability
    qa = [t for t in tl if t["section"] == "qa" and t["dur_s"]]
    # Prepared-remarks time means MANAGEMENT delivering the script. The Operator
    # is logistics, and must be excluded for a second reason: the operator turn
    # that hands over to Q&A STRADDLES the seam — it starts in the prepared
    # section but runs to the first analyst, so counting it added 9.0 minutes of
    # queue instructions to Q2 2025's "prepared remarks" and made the shortest
    # call on record (10.9 min) look like the longest (19.9). A turn is tagged by
    # where it starts; the operator is the only speaker who reliably straddles.
    def _mgmt(rows):
        return [t for t in rows if normalize_role(t["speaker"]) != "Operator"]
    prep_s = sum(t["dur_s"] for t in _mgmt(prepared))
    qa_s = sum(t["dur_s"] for t in _mgmt(qa))
    op_s = sum(t["dur_s"] for t in prepared + qa if normalize_role(t["speaker"]) == "Operator")
    speakers = sorted((d for d in by_spk.values() if d["speaker"] != "Operator"),
                      key=lambda d: -d["seconds"])
    # Is this transcript's labelling good enough to trust the minutes?
    # Two tells, both real and both seen in this corpus (Q2 2025):
    #   * anonymous speakers ("Speaker 5") — nothing can be attributed to a role;
    #   * the operator holding a big share of the clock — analyst/management turns
    #     are being mislabelled as Operator, so every duration is suspect.
    # The tape and the Q&A topics stay valid in that case (they come from the text
    # and the market, not the labels) — only timing is withheld.
    total_s = prep_s + qa_s + op_s
    warnings = []
    if any(d["speaker"] == "Unknown speaker" for d in by_spk.values()):
        warnings.append("speakers are anonymous in this transcript — no role attribution")
    if total_s and op_s / total_s > 0.20:
        warnings.append(f"operator holds {op_s/total_s*100:.0f}% of the clock — turns look mislabelled")
    return {
        "by_speaker": speakers,
        "prepared_minutes": round(prep_s / 60.0, 1),
        "qa_minutes": round(qa_s / 60.0, 1),
        "operator_minutes": round(op_s / 60.0, 1),
        "total_minutes": round((prep_s + qa_s) / 60.0, 1),
        "reliable": not warnings,
        "warnings": warnings,
    }


def _topic_terms(topic):
    words = [w for w in re.findall(r"[A-Za-z]{4,}", (topic or "").lower()) if w not in _STOP]
    return words[:4]


def _find_evidence(hay, terms, width=150):
    """First passage in `hay` mentioning the topic's distinctive terms. Requires
    at least half the terms so a single generic word ('margin') can't score a
    topic as pre-empted."""
    if not terms:
        return None
    low = hay.lower()
    need = max(1, len(terms) // 2)
    best = None
    for m in re.finditer(re.escape(terms[0]), low):
        window = low[max(0, m.start() - 400): m.start() + 400]
        hits = sum(1 for t in terms if t in window)
        if hits >= need:
            s = max(0, m.start() - width // 2)
            best = "…" + " ".join(hay[s:m.start() + width].split()) + "…"
            break
    return best


def preempt_analysis(quarter, client_id=None, recurring_topics=None):
    """What the Q&A actually EXPOSED — not "how many questions did we fail to stop".

    Two wrong versions preceded this one, both worth remembering:
      1. "Was the topic mentioned in prepared remarks?" — flattering nonsense.
         Every topic here came FROM the Q&A, so all of them were asked; counting
         mentions scored a bad call as "80% pre-empted".
      2. "Mentioned but asked anyway ⇒ the language failed." — too harsh, and
         wrong about how a call works. Sell-side analysts MUST ask something to
         be on record engaging; most questions are fishing for incremental colour
         (the trend, the cadence, the forward read) or positioning to sound
         smart. You cannot pre-empt a request for more than you said. Treating
         every question as a script defect turns the critique into scolding and
         buries the two or three findings that matter.

    So a question is only held against the script when there is EVIDENCE:
      * material_gap — management couldn't answer / conceded something the script
        framed as upside, OR the topic recurs quarter to quarter, OR it was never
        addressed and is HIGH severity. These cost real money.
      * unaddressed  — not covered, but they'd likely have asked regardless.
      * probing      — covered; they wanted MORE. An opportunity to own the
                       narrative next quarter, not a failure.
      * ritual       — big-picture/macro question. The arena working as designed.
        No action.

    `recurring_topics` (from compute_qa_preemption_delta) escalates repeat
    offenders. Returns {of, material_gaps, unaddressed, probing, ritual, topics}
    or None when the quarter isn't summarized.
    """
    from core import transcripts
    cid = client_id or get_active_client_id()
    t = transcripts.get_transcript(quarter, client_id=cid)
    if not t or not t.get("qa_risk_topics"):
        return None
    prepared, _qa, boundary = split_prepared_qa(t.get("full_text") or "")
    if boundary is None:
        # No seam found ⇒ `prepared` is the WHOLE transcript, Q&A included. Every
        # topic would then trivially "appear" in the prepared remarks (the
        # analyst said it out loud there) and score as addressed-but-ineffective,
        # hiding real blind spots behind a confident-looking result. Refuse
        # rather than mislead.
        return {"of": len(t["qa_risk_topics"]), "material_gaps": None, "unaddressed": None,
                "probing": None, "ritual": None,
                "topics": [], "error": "Q&A boundary not found — pre-emption not measurable "
                                       "for this transcript's format."}
    recurring = {(a.get("q1_finding") or "").lower() for a in (recurring_topics or [])}
    topics = []
    for x in t["qa_risk_topics"]:
        terms = _topic_terms(x.get("topic"))
        ev = _find_evidence(prepared, terms)
        why = x.get("why") or ""
        sev = x.get("severity", "MEDIUM")
        conceded = bool(_CONCESSION.search(why))
        pressed = bool(_PRESSURE.search(why))
        recurs = any((x.get("topic") or "").lower() in r for r in recurring)

        # Order matters: evidence of a real problem outranks the mere fact that a
        # question was asked.
        # A concession only indicts the script when the topic itself carries
        # weight. A soft answer on a LOW-severity aside is the arena, not a gap —
        # flagging it as material dilutes the two or three findings that matter,
        # which is the fastest way to get a critique ignored.
        if conceded and sev != "LOW":
            verdict, read = "material_gap", (
                "Management could not answer, or conceded something the script framed as upside. "
                "This is the one that costs you — it tells the buy-side you don't have the number.")
        elif recurs:
            verdict, read = "material_gap", (
                "Recurs from last quarter — the language still isn't landing. Rewrite it, don't repeat it.")
        elif not ev and sev == "HIGH":
            verdict, read = "material_gap", (
                "Never addressed, and material. A genuine blind spot.")
        elif not ev:
            verdict, read = "unaddressed", (
                "Not in the prepared remarks. Worth covering next time, but they'd likely have asked anyway.")
        elif _RITUAL.search(why) and not pressed:
            verdict, read = "ritual", (
                "Big-picture question. Analysts have to be on record engaging with the call — this is "
                "positioning, not a gap in your script. No action.")
        elif _INCREMENTAL.search(why):
            verdict, read = "probing", (
                "You covered it; they wanted MORE — the trend, the cadence, the forward read. You can't "
                "pre-empt a request for incremental colour. Opportunity, not failure: give them the "
                "interpretation next quarter and you own the narrative.")
        else:
            verdict, read = "probing", (
                "Covered in the script; the question sought further detail. Normal Q&A.")

        topics.append({
            "topic": x.get("topic"), "severity": sev, "why": why,
            "addressed_in_prepared": bool(ev),
            "conceded": conceded, "pressed": pressed, "recurs": recurs,
            "verdict": verdict, "read": read, "evidence": ev, "terms": terms,
        })

    def _n(v):
        return sum(1 for x in topics if x["verdict"] == v)
    return {"of": len(topics),
            "material_gaps": _n("material_gap"), "unaddressed": _n("unaddressed"),
            "probing": _n("probing"), "ritual": _n("ritual"),
            "topics": topics}


def non_answer_profile(text):
    """Run the published Gow/Larcker/Zakolyukina (2021) non-answer classifier over
    this call's Q&A. Reports against their ~11% base rate, so the number means
    something instead of being an opinion.

    When the transcript's labels are unreliable, every Q&A turn is scanned rather
    than filtering to management — filtering on junk labels produced a confident
    0% for Q2 2025 while hiding a real "We don't have the dollars" (mis-attributed
    to the Operator). A false clean bill of health is worse than a caveated one.
    """
    from core import non_answers
    prepared, qa, boundary = split_prepared_qa(text or "")
    if boundary is None:
        return None
    tim = section_timing(text) or {}
    reliable = bool(tim.get("reliable", True))
    turns = list(_TURN.finditer(text))
    bodies = []
    for i, m in enumerate(turns):
        if m.start() < boundary:
            continue
        role = normalize_role(m.group("spk"))
        if reliable and role in ("Analyst", "Operator"):
            continue
        end = turns[i + 1].start() if i + 1 < len(turns) else len(text)
        bodies.append({"speaker": role, "text": _clean_body(text[m.end():end])})
    if not bodies:
        return None
    return non_answers.analyze_call(qa, bodies, labels_reliable=reliable)


def frame_qa(quarter, client_id=None, force=False):
    """Run core.number_frame over every Q&A exchange in a call: what number did
    the analyst anchor on, what did its valence oblige, and did management
    deliver it.

    CACHED in db — each exchange costs an LLM call (a call carries 15–25), so
    this is a deliberate action with a stored result, never something a page
    render triggers. Same contract as transcripts.summarize_transcript().

    Returns {quarter, generated, numeric_questions, mismatches, by_demand,
    frames:[…]} or None.
    """
    from core import hedge_lexicon, number_frame, transcripts
    cid = client_id or get_active_client_id()
    key = f"qa_frames_{quarter.replace(' ', '_')}.json"
    if not force:
        cached = db.load_json(key, None, client_id=cid)
        if cached:
            return cached

    rec = transcripts.get_transcript(quarter, client_id=cid)
    if not rec:
        return None
    text = rec.get("full_text") or ""
    _p, _q, b = split_prepared_qa(text)
    if b is None:
        return None
    exchanges = hedge_lexicon.build_exchanges(text, list(_TURN.finditer(text)), b, normalize_role)

    frames = []
    skipped = 0
    for e in exchanges:
        answer = " ".join(e["answers"])
        # An answer this short isn't an answer — it's "That's correct.", or a
        # transcript with an audio gap. Framing it produces a confident "omitted:
        # no management answer provided", which blames management for OUR
        # extraction (3 of Q1 2026's 7 unmet demands were exactly this). Abstain.
        if len(answer.strip()) < 120:
            skipped += 1
            continue
        f = number_frame.analyse(e["question"], answer, e.get("reaction", ""))
        if not f:
            continue
        # Keep the evidence attached so a verdict can be checked against the
        # transcript rather than trusted.
        f["question"] = e["question"][:600]
        f["answer"] = " ".join(e["answers"])[:600]
        f["reaction"] = (e.get("reaction") or "")[:300]
        frames.append(f)

    out = number_frame.summarise(frames)
    out.update({"quarter": quarter, "generated": datetime.now().isoformat(),
                "exchanges": len(exchanges), "skipped_short": skipped})
    db.save_json(key, out, client_id=cid)
    return out


def critique(quarter=None, client_id=None):
    """The full morning-after read for a delivered call. Deterministic facts
    only — narrative() turns these into buy-side prose."""
    from core import script_scorecard, transcripts
    cid = client_id or get_active_client_id()
    tr = transcripts.list_transcripts(cid) or []
    dated = sorted([t for t in tr if t.get("call_date")], key=lambda t: t["call_date"])
    if not dated:
        return None
    rec = next((t for t in dated if t.get("quarter") == quarter), dated[-1])
    quarter = rec["quarter"]
    full = transcripts.get_transcript(quarter, client_id=cid) or {}
    text = full.get("full_text") or ""

    prior = None
    idx = [t["quarter"] for t in dated].index(quarter)
    if idx > 0:
        prior = dated[idx - 1]["quarter"]

    carry = None
    if prior:
        try:
            carry = transcripts.compute_qa_preemption_delta(prior, quarter, client_id=cid)
        except Exception:
            carry = None

    recurring = [a for a in (carry or []) if a.get("priority") in ("CRITICAL", "IMPROVE")]
    return {
        "quarter": quarter,
        "call_date": rec.get("call_date"),
        "prior_quarter": prior,
        "reaction": script_scorecard.close_to_open_reaction(rec.get("call_date")),
        "timing": section_timing(text),
        "non_answers": non_answer_profile(text),
        # Cached only — never generated on render (an LLM call per exchange).
        "frames": db.load_json(f"qa_frames_{quarter.replace(' ', '_')}.json", None, client_id=cid),
        "preempt": preempt_analysis(quarter, cid, recurring_topics=recurring),
        "carryover": carry,
        "recurring": [a for a in (carry or []) if a.get("priority") in ("CRITICAL", "IMPROVE")],
        "held": [a for a in (carry or []) if a.get("priority") == "KEEP"],
    }


_NARRATIVE_RULES = (
    "You are writing the morning-after critique of an earnings call for the company's own IR lead. "
    "Audience: a CFA-level IR professional who was ON the call. Register: buy-side analyst, direct, "
    "unsentimental — you work for the shareholder, not the ego of the speaker.\n\n"
    "RULES:\n"
    "1. Use ONLY the facts supplied below. Do not introduce any number, percentage, date or claim "
    "that is not in them. If something isn't there, say it isn't known.\n"
    "1a. CITE EVERY NUMBER. Immediately after any figure you cite, put the verbatim sentence "
    "fragment it came from in quotes. If you cannot quote a source for a number, do not use the "
    "number — say what is unknown instead. Never combine two unrelated figures into a range: if the "
    "facts give you a revenue growth rate and a different growth rate, they are NOT a margin range, "
    "and inventing one that nobody guided to is the single worst thing you can do here.\n"
    "2. Name the investor hesitation, then say plainly whether this call resolved it.\n"
    "3. Separate the headline from what the buy-side actually models.\n"
    "4. Give the MECHANICAL why — the chain from a disclosure to a line in someone's model.\n"
    "5. UNDERSTAND THE Q&A AS AN ARENA, NOT A SCORECARD. Sell-side analysts are obliged to ask "
    "something — they must be on record engaging with the call or their opinion carries no weight. "
    "Most questions are fishing for INCREMENTAL colour (the trend, the cadence, the forward read) or "
    "positioning to sound smart. You cannot pre-empt a request for more than management said. So do "
    "NOT treat a question as proof the script failed, and do not scold management for being asked. "
    "Each topic is pre-classified for you: 'material_gap' (management couldn't answer, conceded "
    "something framed as upside, or it recurs — these cost real money, lead with them), "
    "'unaddressed' (not covered, but they'd have asked anyway), 'probing' (covered; they wanted more "
    "— an OPPORTUNITY to own the narrative next quarter, not a failure) and 'ritual' (big-picture "
    "question, no action). Respect those classifications. If there are no material gaps, say the "
    "call held and do not manufacture criticism.\n"
    "5a. The analysts' real problem is that their MODEL didn't tell them the answer — the answer "
    "isn't in the model, it's in how the data is interpreted going forward. The most valuable thing "
    "management can do is supply that interpretation before being asked.\n"
    "6. Be specific about what to change next quarter. No generic advice.\n"
    "7. No praise that isn't earned by a number in the facts.\n\n"
    "Structure: 'The tape' (what the market did and what that says), 'What landed', "
    "'What didn't land', 'Fix next quarter' (a short numbered list). 350-450 words, plain text."
)


_NUM = re.compile(r"(?<![\w.])(\$?\d[\d,]*(?:\.\d+)?%?)(?![\w])")


def _verify_numbers(prose, *corpora):
    """Flag numbers in the critique that appear NOWHERE in the supplied facts or
    the transcript. Returns the untraceable ones.

    WHY: telling the model "use only the supplied facts" is a request, not a
    control. This catches outright invention.

    WHAT IT CANNOT CATCH — read this before trusting it. It is a digit-presence
    check, so it only catches numbers with no source at all. It does NOT catch
    MISATTRIBUTION, which is the more common and more dangerous failure. Both of
    these got past it in testing, because every digit involved was real:
      * the transcript's card-revenue growth (23%) and ACH growth (25%) were
        welded into a "23-25% gross margin range" nobody ever guided to;
      * PINless Debit's ">50% growth" was recycled as a "50% interrogation claim".
    Right digits, wrong meaning, authoritative tone. The mitigation is the
    citation rule in _NARRATIVE_RULES (every number must carry the verbatim
    sentence it came from, so a reader can see when the quote doesn't support
    the claim) plus human review. Treat a clean result here as "nothing was
    invented", never as "every number means what it says".
    """
    hay = " ".join(c for c in corpora if c)
    hay_digits = re.sub(r"[,\s]", "", hay)
    bad = []
    for m in _NUM.finditer(prose or ""):
        tok = m.group(1)
        core = tok.strip("$%").replace(",", "")
        if not core or core in {"1", "2", "3", "4", "5"}:   # list numbering / trivial
            continue
        if core in hay_digits:
            continue
        s = max(0, m.start() - 55)
        bad.append({"value": tok, "context": "…" + " ".join(prose[s:m.end() + 55].split()) + "…"})
    return bad


def narrative(quarter=None, client_id=None, verify=True):
    """(text, was_ai, unverified) — the critique in buy-side register.

    The model gets ONLY the computed facts from critique(). Because that
    instruction is not enforceable, every number in the output is then verified
    against those facts plus the transcript; anything untraceable comes back in
    `unverified` for the caller to flag rather than being quietly published.
    Degrades to a deterministic summary when the model is unavailable.
    """
    c = critique(quarter, client_id)
    if not c:
        return None, False, []
    r, t, p = c.get("reaction"), c.get("timing"), c.get("preempt")

    facts = [f"Quarter: {c['quarter']} (call {c['call_date']}). Prior quarter: {c.get('prior_quarter')}."]
    if r:
        # Spell each measurement out and label it. A compact "…= -2.67%. Next
        # close -16.58%." got misread as "gapped down -16.58% at next open",
        # which inverts the story: a gap-down is a verdict at the bell, whereas
        # selling THROUGH the session is the market digesting. Both numbers were
        # real, so number-verification can't catch it — only unambiguous framing.
        drift = r["next_day_pct"] - r["pct"]
        facts.append(
            "TAPE — three DISTINCT measurements, do not conflate them "
            "(executable prints only; after-hours excluded, because on a micro-cap the AH tape is "
            "market-maker quotes that print but cannot be traded):\n"
            f"  (a) CALL-DAY CLOSE = ${r['close']:.2f}. The last executable price BEFORE the market "
            f"digested the call.\n"
            f"  (b) NEXT SESSION OPEN = ${r['next_open']:.2f}. The OVERNIGHT GAP versus (a) is "
            f"{r['pct']:+.2f}%. This is the market's first verdict.\n"
            f"  (c) NEXT SESSION CLOSE = ${r['next_close']:.2f}. Cumulative move versus (a) is "
            f"{r['next_day_pct']:+.2f}%, on volume of {r['next_volume']:,}.\n"
            f"  INTERPRETATION: the move from the open to the close was {drift:+.2f}pp. "
            + ("Most of the move happened AFTER the open — the market kept trading in one direction "
               "THROUGH the session as it digested the call and the transcript. That is a digestion "
               "pattern, NOT a gap."
               if abs(drift) > abs(r["pct"]) else
               "The bulk of the move was the overnight gap — the verdict was in at the bell."))
    if t:
        facts.append(f"TIMING measured from transcript timestamps: prepared remarks {t['prepared_minutes']} min, "
                     f"Q&A {t['qa_minutes']} min, total {t['total_minutes']} min. By speaker: "
                     + "; ".join(f"{s['speaker']} {s['minutes']} min ({s['wpm']} wpm)" for s in t["by_speaker"]))
    na = c.get("non_answers")
    if na:
        facts.append(
            f"NON-ANSWERS (Gow/Larcker/Zakolyukina 2021 classifier, JAR 59(4); 78.9% out-of-sample "
            f"true-positive rate): {na['non_answers']} of {na['responses']} manager responses were "
            f"non-answers = {na['rate']*100:.0f}%. Breakdown — refused {na['by_type']['REFUSE']}, "
            f"unable {na['by_type']['UNABLE']}, deferred-offline {na['by_type']['AFTERCALL']}. "
            f"BENCHMARK: the published base rate across all firms is ~11% of responses (25th pct 7%, "
            f"75th pct 14%), stable over time and across industries. So ~11% is NORMAL — do not treat a "
            f"rate at or below the norm as a failing; say so plainly. "
            + ("NOTE: this transcript mis-attributes speakers, so the RATE is indicative only — the "
               "flagged phrases are real but the denominator is not."
               if not na.get("labels_reliable") else ""))
        for f in na["flagged"]:
            facts.append(f"  - non-answer [{'+'.join(f['types'])}] by {f['speaker']}: "
                         f"\"{f['hits'][0]['phrase']}\" — context: {f['excerpt'][:170]}")
    fr = c.get("frames")
    if fr and fr.get("frames"):
        facts.append(
            f"WHAT THE Q&A DEMANDED ({fr.get('numeric_questions')} questions anchored on a number; "
            f"{fr.get('mismatches')} unmet). Model: the analyst has ALREADY judged the number; its "
            "valence sets what the answer owes — GOOD ⇒ prove it REPEATS, BAD ⇒ prove you CONTROL it "
            "and say WHEN, CLAIM/guide ⇒ prove it's BACKED (signed vs assumed). A mismatch is not "
            "evasion: it's a good answer to a question nobody asked. LEAD WITH THESE — an unmet "
            "demand is the most actionable thing on the call, and name the omission verbatim.")
        for x in fr["frames"]:
            if x.get("verdict") != "MISMATCH":
                continue
            facts.append(f"  - UNMET: anchor '{x.get('anchor')}' ({x.get('valence')} ⇒ owes "
                         f"{x.get('demand')}). Omitted: {x.get('missing')}. {x.get('why')}")
    if p:
        facts.append(f"Q&A TOPICS: {p['of']} topics drew analyst questions. {p['material_gaps']} material "
                     f"gap(s) (evidence: management couldn't answer, conceded something the script framed "
                     f"as upside, or the topic recurs). {p['unaddressed']} not addressed but they'd have "
                     f"asked anyway. {p['probing']} probing (covered; they wanted more — an opportunity, "
                     f"NOT a failure). {p['ritual']} ritual (on-record questions, no action).")
        for x in p["topics"]:
            facts.append(f"  - [{x['severity']}] {x['topic']} — {x['verdict']}. {x.get('why') or ''}"
                         + (f" Script said: {x['evidence']}" if x["evidence"] else ""))
    if c.get("held"):
        facts.append("HELD from last quarter (pre-emption worked, keep the language): "
                     + "; ".join((a.get("q1_finding") or "")[:90] for a in c["held"]))
    if c.get("recurring"):
        facts.append("RECURRING from last quarter (still not fixed): "
                     + "; ".join((a.get("q1_finding") or "")[:90] for a in c["recurring"]))

    facts_blob = "\n".join(facts)
    prompt = _NARRATIVE_RULES + "\n\nFACTS:\n" + facts_blob
    try:
        from core.transcripts import _call_claude
        out = _call_claude(prompt, max_tokens=1100)
        if out and out.strip():
            out = out.strip()
            unverified = []
            if verify:
                from core import transcripts
                t_rec = transcripts.get_transcript(c["quarter"], client_id=client_id) or {}
                unverified = _verify_numbers(out, facts_blob, t_rec.get("full_text"))
            return out, True, unverified
    except Exception as e:
        print(f"[morning_after] narrative model call failed: {e}")
    return _fallback_narrative(c), False, []


def _fallback_narrative(c):
    """Deterministic critique when the model is unavailable — facts, no prose."""
    r, t, p = c.get("reaction"), c.get("timing"), c.get("preempt")
    L = [f"MORNING-AFTER — {c['quarter']} (call {c['call_date']})", ""]
    if r:
        L.append(f"The tape: closed ${r['close']:.2f}, opened ${r['next_open']:.2f} ({r['pct']:+.2f}%); "
                 f"next close {r['next_day_pct']:+.2f}% on {r['next_volume']:,} shares. "
                 "Measured close-to-next-open; after-hours excluded (non-executable market-maker quotes).")
    if t:
        L.append(f"Delivery: prepared {t['prepared_minutes']} min, Q&A {t['qa_minutes']} min "
                 f"(total {t['total_minutes']} min).")
        for s in t["by_speaker"]:
            L.append(f"   {s['speaker']}: {s['minutes']} min, {s['wpm']} wpm")
    na = c.get("non_answers")
    if na:
        L.append("")
        L.append(f"Non-answers: {na['non_answers']}/{na['responses']} responses = {na['rate']*100:.0f}% "
                 f"(published norm ~11%). Refuse {na['by_type']['REFUSE']}, "
                 f"Unable {na['by_type']['UNABLE']}, Offline {na['by_type']['AFTERCALL']}.")
        for f in na["flagged"]:
            L.append(f"   [{'+'.join(f['types'])}] {f['speaker']}: \"{f['hits'][0]['phrase']}\"")
    if p and not p.get("error"):
        L.append("")
        L.append(f"{p['of']} topics drew questions — {p['material_gaps']} material gap(s), "
                 f"{p['unaddressed']} unaddressed, {p['probing']} probing, {p['ritual']} ritual.")
        for x in p["topics"]:
            L.append(f"   [{x['verdict'].upper()}] {x['severity']} — {x['topic']}: {x['read']}")
    return "\n".join(L)
