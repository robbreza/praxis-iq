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
import json
import re
import urllib.request
from datetime import timedelta

from core import fund_lineup as _fl
from core import sec_filings as sf
from core.security import get_anthropic_api_key

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


# ── LLM fallback (for prospectus formats the rule-first patterns don't cover) ──────────────────
def _pm_window(text, size=14000):
    """Bound the prospectus to the region that names PMs, so the LLM reads a few KB, not 500.
    Prefers the consolidated 'Management of the Fund(s)' section (names the whole complex's PMs
    with bios — best for large families); else centres on the first 'portfolio manager' mention
    with person-name context; else the first mention / doc head."""
    def _win(pos):
        start = max(0, pos - 300)
        return text[start:start + size]
    # 1. the real 'Management of the Fund(s)' section — one that names people, not the TOC line.
    for m in re.finditer(r"[Mm]anagement of the [Ff]unds?\b", text):
        seg = text[m.start():m.start() + 900]
        if re.search(r"has (?:served|managed)|portfolio manager", seg, re.I) and re.search(r"[A-Z][a-z]+ [A-Z]\.?", seg):
            return _win(m.start())
    # 2. the first name-bearing 'portfolio manager' mention.
    for m in re.finditer(r"[Pp]ortfolio [Mm]anager", text):
        if re.search(r"has (?:served|managed|co-managed)|managed by|consists of|responsible for",
                     text[m.start():m.start() + 300], re.I):
            return _win(m.start())
    m = re.search(r"[Pp]ortfolio [Mm]anager", text)
    return _win(m.start()) if m else text[:size]


def _looks_like_person(name):
    """Guard on LLM output — a clean 2–4-token human name, no entity/fund words. The LLM can't
    smuggle a fund or firm name through as a portfolio manager."""
    toks = (name or "").split()
    if not (2 <= len(toks) <= 4):
        return False
    if any(t.strip(".-'").lower() in _NONNAME for t in toks):
        return False
    return all(t[:1].isupper() and re.fullmatch(r"[A-Za-z.\-']+", t) for t in toks)


def _claude(prompt, max_tokens=1024):
    """Raw Messages-API call (same pattern as core.email_classifier). Returns text or None on any
    failure — no key, no network, non-2xx, malformed. Isolated so tests monkeypatch it directly."""
    api_key = get_anthropic_api_key()
    if not api_key:
        return None
    try:
        payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages", data=payload,
            headers={"Content-Type": "application/json", "x-api-key": api_key,
                     "anthropic-version": "2023-06-01"}, method="POST")
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read())["content"][0]["text"].strip()
    except Exception as e:
        print(f"[fund_managers] Claude call failed: {e}")
        return None


_LLM_PROMPT = (
    "You are extracting portfolio managers from a mutual-fund prospectus excerpt.\n"
    "Return ONLY a JSON array: [{\"name\": \"First [Middle] Last\", \"title\": \"...\"}].\n"
    "Rules:\n"
    "- Include ONLY individuals explicitly named as a portfolio manager or co-portfolio manager of a fund.\n"
    "- Use the person's real full name as written; drop nickname parentheticals and designations (CFA, CPA).\n"
    "- title = their stated title (e.g. 'Vice President and Portfolio Manager'); if none is stated, use 'Portfolio Manager'.\n"
    "- Do NOT include fund names, firm names, trusts, or anyone who is not a portfolio manager.\n"
    "- If no portfolio managers are named, return [].\n\n"
    "Excerpt:\n")


def _parse_llm_array(raw):
    """Fence-tolerant parse of the model's JSON array into validated [{'name','title'}]."""
    if not raw:
        return []
    text = raw.strip()
    fence = re.search(r"```(?:json)?\s*(\[.*\])\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        arr = re.search(r"\[.*\]", text, re.DOTALL)
        if arr:
            text = arr.group(0)
    try:
        rows = json.loads(text)
    except Exception:
        return []
    out, seen = [], set()
    for r in rows if isinstance(rows, list) else []:
        nm = _clean_name((r or {}).get("name", "")) or (r or {}).get("name", "").strip()
        if not nm or not _looks_like_person(nm) or nm.lower() in seen:
            continue
        seen.add(nm.lower())
        title = ((r or {}).get("title") or "").strip() or "Portfolio Manager"
        out.append({"name": nm, "title": title[:80]})
    return out


def _llm_extract(text):
    """Rule-first found nothing — ask the model to read the PM section. Two guards keep the model
    honest: `_looks_like_person` (no fund/firm names) and — critically — the returned name's first
    AND last token must actually APPEAR in the source excerpt, so the model can't invent a
    plausible-sounding PM that isn't in the document (the app's never-guess rule)."""
    window = _pm_window(text)
    rows = _dedupe_rows(_parse_llm_array(_claude(_LLM_PROMPT + window)))
    grounded = []
    for r in rows:
        toks = r["name"].split()
        first, last = toks[0].strip(".-'"), toks[-1].strip(".-'")
        # the first + last name must appear CONTIGUOUSLY in the source (optionally with a middle
        # token between) — scattered tokens don't count, so a hallucinated name can't pass.
        if len(first) >= 2 and len(last) >= 2 and re.search(
                re.escape(first) + r"(?:\s+\w+\.?)?\s+" + re.escape(last), window, re.I):
            grounded.append(r)
    return grounded


def _dedupe_rows(rows):
    """Dedupe [{'name',...}] using the same person-key logic as the rule path."""
    names = _dedupe([r["name"] for r in rows])
    by_name = {r["name"]: r for r in rows}
    return [by_name[n] for n in names if n in by_name]


def portfolio_managers(cik, force=False, use_llm=True):
    """The portfolio managers named in a fund registrant's prospectus: [{'name','title'}].
    Rule-first (free, deterministic); falls back to the LLM only when the rules find nothing and a
    key is configured. Cached 30 days (global). [] if no prospectus or none could be parsed."""
    cik = int(cik)
    ck = f"{_PM_KEY}{cik}"
    cached = _fl._gload(ck)
    if cached and not force and not sf._is_stale(cached.get("_fetched_at"), _PM_TTL):
        return cached.get("managers", [])
    text, acc = _prospectus_text(cik)
    if not text:
        return []
    managers = parse_managers(text)                     # rule-first: free + deterministic
    source = "rules"
    if not managers and use_llm:                        # tail: formats the patterns don't cover
        managers = _llm_extract(text)
        source = "llm"
    if managers:                                        # only cache a positive result
        try:
            _fl._gsave(ck, {"managers": managers, "accession": acc, "source": source,
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


def eligible_firms():
    """Firms in the fund-lineup crosswalk that resolve to a USABLE fund registrant (confirmed or
    high-confidence, non-rejected CIK) — the roster targets. [{'firm','cik'}], deduped by CIK so a
    firm isn't fetched twice. This is what the whole-book roster (and its UI progress) iterates."""
    out, seen = [], set()
    for e in _fl.crosswalk_entries():
        if e.get("rejected"):
            continue
        cik = e.get("cik")
        if not cik or int(cik) in seen:
            continue
        if not (e.get("confirmed") or e.get("confidence") in ("high", "manual")):
            continue
        seen.add(int(cik))
        out.append({"firm": e.get("manager") or e.get("registrant") or "", "cik": int(cik)})
    return out


def roster_pms_for_book(cid=None, limit=None):
    """Roster PMs for every eligible fund-family firm. One deliberate enrichment pass — each
    registrant is a cached prospectus fetch (+ a possible LLM call for hard formats). Returns
    per-firm summaries. The Console/House-Contacts button iterates eligible_firms() itself so it
    can show live progress; this stays the headless one-shot."""
    firms = eligible_firms()
    if limit:
        firms = firms[:limit]
    return [roster_pms_for_firm(f["firm"], f["cik"]) for f in firms]
