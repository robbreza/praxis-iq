"""
core/textfmt.py — presentation-only text formatting.

Fund / holder names arrive from SEC EDGAR in screaming all-caps
("PERKINS CAPITAL MANAGEMENT INC"), which reads as unprofessional on a
client-facing surface. pretty_name() converts those to Title Case for DISPLAY
only — it never touches stored data or match keys (those stay upper so dedup /
lookups are unaffected). Names already in mixed case are returned untouched, so
a hand-curated "Lombard Odier Investment Managers" is never mangled.
"""
import re

# Initialisms / suffixes kept UPPER (don't Title-case these).
_KEEP_UPPER = {
    "LLC", "L.L.C.", "LP", "L.P.", "LLP", "PLC", "SA", "AG", "NV", "NA", "N.A.",
    "GP", "SE", "AB", "AS", "USA", "US", "UK", "UAE", "ETF", "REIT", "SPA", "S.A.",
    # well-known manager initialisms that look wrong Title-cased
    "FMR", "BNY", "UBS", "PNC", "TIAA", "CPP", "APG", "GIC", "BMO", "RBC", "TD",
    "LSV", "DZ", "KBC", "CIBC", "HSBC", "ING", "BNP", "LGT", "EFG",
}
# Period-insensitive form, so "L.P." (which loses its trailing dot to strip()) still
# matches "LP" — otherwise "Holdings L.P." Title-cased to a wrong "L.p.".
_KEEP_UPPER_NODOTS = {k.replace(".", "") for k in _KEEP_UPPER}
# Small connector words kept lower (unless they lead the name).
_KEEP_LOWER = {"of", "and", "the", "for", "de", "van", "der", "den", "del",
               "la", "le", "el", "di", "da", "du", "et", "und"}
_ROMAN_RE = re.compile(r"^[IVXLCDM]{1,6}$")
# camelCase brand names a plain Title-case would mangle (keyed by upper token).
_SPECIAL = {
    "JPMORGAN": "JPMorgan", "BLACKROCK": "BlackRock", "WISDOMTREE": "WisdomTree",
    "VANECK": "VanEck", "ISHARES": "iShares", "POWERSHARES": "PowerShares",
    "MFS": "MFS", "PGIM": "PGIM", "AQR": "AQR", "GQG": "GQG", "DNB": "DNB",
}
# Trailing EDGAR filer cruft — state-of-incorporation and entity-type tags EDGAR
# appends to the registered name that aren't part of it. They arrive delimited by
# either forward slashes ("CORP /DE/", "... /ADV", broker-dealer "... /BD") OR
# backslashes ("US BANCORP \DE\", trailing "DEUTSCHE BANK AG\"), sometimes several
# in a row ("... /GA/ /ADV"), and sometimes padded with long internal whitespace
# runs. _strip_edgar_cruft peels them all off (and collapses the whitespace) before
# formatting. The tag is 1-4 letters between slash/backslash delimiters; a real
# name never ends that way, and legit trailing words (>4 letters, or space after
# the delimiter) are left untouched.
_EDGAR_TAG_RE = re.compile(r"\s*[\\/][A-Za-z]{1,4}[\\/]?\s*$")
_TRAIL_DELIM_RE = re.compile(r"[\\/]+\s*$")
_WS_RE = re.compile(r"\s+")


def _strip_edgar_cruft(s):
    s = _WS_RE.sub(" ", str(s).strip())
    prev = None
    while prev != s:                              # peel repeated trailing tags: "/GA/ /ADV" → ""
        prev = s
        s = _TRAIL_DELIM_RE.sub("", s).strip()    # stray trailing "\" or "/" (e.g. "AG\")
        s = _EDGAR_TAG_RE.sub("", s).strip()      # "/DE/", "\DE\", "/BD", "/ADV"
    return s


def pretty_name(raw):
    """Title-case a screaming all-caps name for display; leave mixed-case as-is."""
    if not raw:
        return raw
    s = _strip_edgar_cruft(raw)
    letters = [c for c in s if c.isalpha()]
    # Only fix genuinely all-caps strings — respect anything already cased.
    if not letters or not all(c.isupper() for c in letters):
        return s

    tokens = re.split(r"(\s+|/|&|-)", s)   # keep separators in place
    out = []
    first_word_done = False
    for tok in tokens:
        if not tok or tok.isspace() or tok in ("/", "&", "-"):
            out.append(tok)
            continue
        core = tok.strip(".,()")
        up = core.upper()
        low = core.lower()
        if up in _SPECIAL:
            out.append(tok.replace(core, _SPECIAL[up]))
        elif up in _KEEP_UPPER or up.replace(".", "") in _KEEP_UPPER_NODOTS:
            out.append(tok)
        elif _ROMAN_RE.match(up) and up not in ("I",):   # III, IV, ... (not lone "I")
            out.append(tok.replace(core, up))
        elif low in _KEEP_LOWER and first_word_done:
            out.append(tok.lower())
        else:
            out.append(tok[:1].upper() + tok[1:].lower())
        first_word_done = True
    # No leading-cap fixup needed: first_word_done already prevents a leading
    # connector from being lowered, and forcing char[0] upper would break brand
    # names that legitimately start lowercase (iShares).
    return "".join(out)
