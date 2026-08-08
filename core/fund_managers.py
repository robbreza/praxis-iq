"""core/fund_managers.py — extract a fund complex's PORTFOLIO MANAGERS from its prospectus.

The 13F gives one signatory per firm (usually an ops/compliance officer); the people who actually
run the money — portfolio managers — are named in each '40-Act fund's prospectus (485BPOS / 497),
in the summary "Portfolio Managers" block and the "Management of the Fund(s)" section. This pulls
those names + titles so core/roster.add_people can land them as classified, CIK-linked house
contacts under the same account as everything else.

Free + authoritative (SEC EDGAR). Works for '40-Act fund complexes; hedge funds / SMAs have no
prospectus and need the website/ADV path. Rule-first extraction (the common prospectus phrasings);
never guesses a name — an unparseable prospectus returns []. Reuses core/fund_lineup's global cache
+ core/sec_filings' throttled fetcher.
"""
import re
from datetime import timedelta

from core import fund_lineup as _fl
from core import sec_filings as sf

_PM_KEY = "sec_fund_pms_"          # per-registrant-CIK, GLOBAL scope (via fund_lineup._gload/_gsave)
_PM_TTL = timedelta(days=30)
_PROSPECTUS_FORMS = ("485BPOS", "497", "485APOS")

# Anchor phrases that introduce the portfolio-manager roster for a fund. Each captures the run of
# names up to the sentence end. Prospectuses reuse a handful of stock phrasings; these cover the
# common ones (team-of-professionals, primarily-responsible, co-managed/managed-by).
# The captured name-run ends at the sentence boundary or the "has served/managed" clause. Note the
# terminator is `\s\.` (space-then-period): in the tag-stripped/whitespace-collapsed text a real
# sentence period carries a leading space ("McGlone . Mr"), while a middle-initial period is tight
# ("Colin P. McWey") — so this stops at the end of the list, not inside a name.
_END = r"(?:\s\.|\s+(?:who )?ha(?:s|ve) (?:served|managed|co-managed)|\s+(?:is|are)\s)"
_LIST_ANCHORS = (
    r"team of investment professionals[^.]*?consists of (.+?)" + _END,
    r"portfolio managers?[^.]*?primarily responsible for the day-to-day management[^.]*?(?:are|is) (.+?)" + _END,
    r"day-to-day management of the funds?[^.]*?(?:are|is) (.+?)" + _END,
    r"funds?[^.]{0,40}?(?:are|is) (?:jointly and primarily )?(?:co-)?managed by (?:a team[^.]*?(?:consisting of|of) )?(.+?)" + _END,
)
_DESIG = {"cfa", "cpa", "caia", "cfp", "phd", "mba", "jr", "sr", "ii", "iii", "iv", "esq"}
_HONORIFIC = {"mr", "ms", "mrs", "dr", "messrs"}
# Words that mean a fragment is NOT a person name (a fund/entity, or a sentence ran into the
# capture). Conservative on purpose — better to drop a real name than to emit a fund as a person.
_NONNAME = {"fund", "funds", "trust", "group", "company", "co", "llc", "lp", "inc", "incorporated",
            "advisors", "adviser", "advisers", "management", "capital", "partners", "associates",
            "the", "while", "since", "each", "team", "portfolio", "value", "growth", "income",
            "equity", "and", "of", "who", "has", "have", "is", "are", "a", "an", "series"}


def _clean_name(raw):
    """One split fragment → clean 'First [Middle] Last', or None. Conservative: drops nickname
    parentheticals, designations (CFA…) and honorifics, and REJECTS anything that doesn't look
    like a plain 2–3-token human name (an entity word, a run-on into the next sentence, or a
    fund name → None). Under-extract rather than emit a wrong name."""
    s = re.sub(r"\([^)]*\)", " ", raw)                 # nickname parentheticals
    s = re.sub(r"[^A-Za-z.\-' ]", " ", s)
    toks = [t for t in s.split() if t]
    if toks and toks[0].strip(".").lower() in _HONORIFIC:
        toks = toks[1:]
    keep = []
    for t in toks:
        low = t.strip(".-'").lower()
        if low in _DESIG:
            continue
        if low in _NONNAME:                             # hit an entity/stop word -> stop the name
            break
        if not t[:1].isupper():                         # a lowercase token ends a name run
            break
        keep.append(t)
    # a person name is First [Middle] Last — 2 or 3 tokens, first & last multi-char (not initials)
    if not (2 <= len(keep) <= 3):
        return None
    if len(keep[0].strip(".")) < 2 or len(keep[-1].strip(".-")) < 2:
        return None
    return " ".join(keep)


def _dedupe(names):
    """Merge nickname/format variants of the SAME person. Key = (surname, middle-initial) when a
    middle initial is present (keeps two same-surname people with different middles apart, e.g. a
    father/son PM pair), else (surname, first name). Keeps the most formal first name."""
    out, by_key = [], {}
    for nm in names:
        parts = nm.split()
        surname = parts[-1].strip(".-").lower()
        if len(parts) == 3 and len(parts[1].strip(".")) <= 2:
            key = (surname, parts[1][:1].lower())       # middle initial
        else:
            key = (surname, parts[0].lower())
        if key not in by_key:
            by_key[key] = len(out)
            out.append(nm)
        elif len(parts[0]) > len(out[by_key[key]].split()[0]):
            out[by_key[key]] = nm                        # prefer the longer (formal) first name
    return out


def _split_names(blob):
    """'A, B and C' / 'A and B' / 'A, B, and C' → [clean names]."""
    blob = re.split(r"\bwho (?:has|have)\b|\bhas served\b|\bhave served\b", blob, maxsplit=1)[0]
    parts = re.split(r",| and | & ", blob)
    out = []
    for p in parts:
        nm = _clean_name(p)
        if nm:
            out.append(nm)
    return out


def _title_for(name, text):
    """Best-effort title for a PM from the prospectus body ('Mr. Surname … is a <Title> …').
    Falls back to 'Portfolio Manager' — the role we already know from context."""
    surname = name.split()[-1].strip(".")
    m = re.search(
        rf"(?:Mr|Ms|Mrs|Dr)\.? (?:\w+\.? )*?{re.escape(surname)}\b[^.]*? is (?:a |an |the )?"
        r"([A-Z][A-Za-z ,&/-]+?)(?: with | of the | of [A-Z]| since |, and has |\.)", text)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip(" ,")
        # keep it to the leading role phrase
        title = re.split(r"\b(?:and a Director|and has|who)\b", title)[0].strip(" ,")
        if 3 <= len(title) <= 80:
            return title
    return "Portfolio Manager"


def _latest_prospectus(cik):
    """(accession, primary_document) of the registrant's most recent prospectus, or (None, None)."""
    try:
        sub = sf._get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", timeout=25).json()
    except Exception:
        return None, None
    rec = sub.get("filings", {}).get("recent", {})
    forms = rec.get("form", []) or []
    accs = rec.get("accessionNumber", []) or []
    docs = rec.get("primaryDocument", []) or []
    for f, a, d in zip(forms, accs, docs):
        if f in _PROSPECTUS_FORMS and d:
            return a, d
    return None, None


def _prospectus_text(cik):
    """Plain text of the latest prospectus document (tags stripped, whitespace collapsed), or None."""
    acc, doc = _latest_prospectus(cik)
    if not acc or not doc:
        return None, None
    accn = acc.replace("-", "")
    try:
        html = sf._get(f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{doc}", timeout=45).text
    except Exception:
        return None, acc
    return extract_text(html), acc


def extract_text(html):
    """HTML → collapsed plain text (pure, unit-testable)."""
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = re.sub(r"&#\d+;|&[a-zA-Z]+;", " ", text)     # numeric + named HTML entities (incl. the ;)
    return re.sub(r"\s+", " ", text).strip()


def parse_managers(text):
    """Pure extractor over prospectus plain text → [{'name','title'}], deduped, order-preserved.
    Gathers names across EVERY roster block (a complex names a team per fund), then titles each
    from the body. No network, no guessing."""
    if not text:
        return []
    names, seen = [], set()
    for pat in _LIST_ANCHORS:
        for m in re.finditer(pat, text, flags=re.I):
            for nm in _split_names(m.group(1)):
                k = nm.lower()
                if k not in seen:
                    seen.add(k)
                    names.append(nm)
    return [{"name": nm, "title": _title_for(nm, text)} for nm in _dedupe(names)]


def portfolio_managers(cik, force=False):
    """The portfolio managers named in a fund registrant's prospectus: [{'name','title'}].
    Cached 30 days (global). [] if the registrant has no prospectus or none could be parsed."""
    cik = int(cik)
    ck = f"{_PM_KEY}{cik}"
    cached = _fl._gload(ck)
    if cached and not force and not sf._is_stale(cached.get("_fetched_at"), _PM_TTL):
        return cached.get("managers", [])
    text, acc = _prospectus_text(cik)
    managers = parse_managers(text) if text else []
    if managers:                                        # only cache a positive result
        try:
            _fl._gsave(ck, {"managers": managers, "accession": acc,
                            "_fetched_at": _fl._iso_now()})
        except Exception:
            pass
    return managers


def roster_pms_for_firm(firm, cik, firm_currency=None):
    """Pull a fund complex's PMs from its prospectus and land them as classified, CIK-linked
    house contacts (core.roster dedupes against anyone already in the book). Returns a summary."""
    from core import roster
    pms = portfolio_managers(cik)
    if not pms:
        return {"firm": firm, "cik": int(cik), "found": 0, "added": 0, "enriched": 0}
    res = roster.add_people(firm, firm_cik=int(cik), people=pms, source="fund_prospectus_pm",
                            source_note="Fund prospectus — Portfolio Managers",
                            firm_currency=firm_currency) or {}
    return {"firm": firm, "cik": int(cik), "found": len(pms), **res}


def roster_pms_for_book(cid=None, limit=None):
    """Roster PMs for every firm in the fund-lineup crosswalk that resolves to a usable fund
    registrant (a confirmed or high-confidence, non-rejected CIK). One deliberate enrichment pass
    — each registrant is a cached prospectus fetch. Returns per-firm summaries."""
    out = []
    for e in _fl.crosswalk_entries():
        if e.get("rejected"):
            continue
        cik = e.get("cik")
        if not cik or not (e.get("confirmed") or e.get("confidence") in ("high", "manual")):
            continue
        out.append(roster_pms_for_firm(e.get("manager") or e.get("registrant") or "", cik))
        if limit and len(out) >= limit:
            break
    return out
