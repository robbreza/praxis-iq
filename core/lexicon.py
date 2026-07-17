"""
core/lexicon.py — finance-specific word measures over the earnings script.

BACKED BY: Loughran, T. & McDonald, B. (2011), "When Is a Liability Not a
Liability? Textual Analysis, Dictionaries, and 10-Ks", Journal of Finance 66(1),
35–65. Master Dictionary (March 2026, 86,553 words) via Notre Dame's SRAF:
https://sraf.nd.edu/loughranmcdonald-master-dictionary/

⚠️ LICENSING — read vendor/loughran_mcdonald/NOTICE.md before using this.
The lists are free for ACADEMIC research; COMMERCIAL use requires a licence
(loughranmcdonald@gmail.com). Praxis Point IR is commercial. So this module is
GATED: it returns None unless settings.json declares `lm_license`. That is a
deliberate speed bump so the capability can be evaluated without anyone wiring
an unlicensed dictionary into a client deliverable by accident.

WHY A FINANCE-SPECIFIC LIST: general sentiment lexicons misread financial prose —
"liability", "cost", "tax", "capital", "vice" (as in vice-president) all read as
NEGATIVE to psychology-derived lists, when in filings they're neutral accounting
vocabulary. That mis-measurement is the entire reason this dictionary exists.

WHAT WE USE IT FOR: hedging. An earnings script's problem is rarely sentiment —
it's whether management committed to anything. Weak_Modal ("may", "possibly",
"appears") and Uncertainty ("approximately", "ambiguous") against Strong_Modal
("will", "clearly", "definitely") is a defensible instrument for that, replacing
hand-rolled guesses.

HONEST LIMITS:
  * Word counting is not comprehension. A high hedge rate on a genuinely
    uncertain quarter is correct behaviour, not a defect.
  * These lists were validated on 10-K filings, not spoken calls. Directionally
    useful; not a published benchmark for scripts. There is no "normal hedge
    rate" here the way there is an 11% non-answer rate — do not invent one.
"""

import csv
import os
import re

_CSV = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "vendor", "loughran_mcdonald", "lm_master.csv")
_CATS = ("Negative", "Positive", "Uncertainty", "Litigious",
         "Strong_Modal", "Weak_Modal", "Constraining", "Complexity")
_CACHE = {}
_WORD = re.compile(r"\b[A-Za-z][A-Za-z'\-]*\b")


def license_status():
    """'commercial' | 'academic' | None. Read from settings so it's an explicit,
    auditable decision rather than a code edit."""
    try:
        from core import db
        v = (db.load_json("settings.json", {}) or {}).get("lm_license")
        return v if v in ("commercial", "academic") else None
    except Exception:
        return None


def available():
    return bool(license_status()) and os.path.exists(_CSV)


def _load():
    """{word -> set(categories)}. Cached; ~86k rows, parsed once per process."""
    if _CACHE:
        return _CACHE
    if not os.path.exists(_CSV):
        return {}
    with open(_CSV, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            hits = set()
            for c in _CATS:
                try:
                    if int(float(row.get(c) or 0)):
                        hits.add(c)
                except (TypeError, ValueError):
                    continue
            if hits:
                _CACHE[row["Word"].strip().lower()] = hits
    return _CACHE


def measure(text):
    """Per-category word rates for a passage, or None when unlicensed/missing.

    Returns {words, counts{cat:n}, rates{cat:pct}, hedge_ratio, hedge_read,
    examples{cat:[…]}}. hedge_ratio = (Weak_Modal + Uncertainty) / Strong_Modal —
    how much the script qualifies versus how much it commits.
    """
    lic = license_status()
    if not lic:
        return None
    d = _load()
    if not d:
        return None
    words = [w.lower() for w in _WORD.findall(text or "")]
    if not words:
        return None
    counts = {c: 0 for c in _CATS}
    examples = {c: [] for c in _CATS}
    for w in words:
        for c in d.get(w, ()):
            counts[c] += 1
            if len(examples[c]) < 8 and w not in examples[c]:
                examples[c].append(w)
    n = len(words)
    rates = {c: round(counts[c] / n * 100, 2) for c in _CATS}
    weak = counts["Weak_Modal"] + counts["Uncertainty"]
    strong = counts["Strong_Modal"]
    ratio = round(weak / strong, 2) if strong else None
    if ratio is None:
        read = (f"{weak} hedging word(s) and NO strong-modal commitments — the script qualifies "
                "without ever committing." if weak else "No modal language either way.")
    elif ratio >= 3:
        read = (f"{ratio}x more hedging than commitment ({weak} qualifiers vs {strong} commitments). "
                "Analysts read that as management not backing its own numbers.")
    elif ratio >= 1.5:
        read = f"{ratio}x more hedging than commitment — leaning cautious."
    else:
        read = f"{ratio}x — commitment and hedging roughly balanced."
    return {"license": lic, "words": n, "counts": counts, "rates": rates,
            "hedge_ratio": ratio, "hedge_read": read, "examples": examples,
            "caveat": "Loughran-McDonald lists were validated on 10-K filings, not spoken calls. "
                      "Directional only — there is no published 'normal' hedge rate for scripts."}
