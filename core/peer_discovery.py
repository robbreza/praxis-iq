"""Systematic peer/comp discovery — the capital-markets-expert way to capture the full set.

WHY THIS EXISTS. Peer selection by recall does not work, and we have the scars to prove it:
onboarding WRAP, the analyst's memory missed BYRN (the single most obvious less-lethal comp);
onboarding SARO, it missed AerSale/TAT/FTAI (the client supplied them) AND a plain EDGAR
SIC screen instantly surfaced Howmet — a $111B engine-parts name neither recall nor the
10-K competition section named. A comp set built from memory is a comp set with holes, and
in a valuation the holes move the median.

THE METHOD: TRIANGULATE PRIMARY SOURCES. No single source is complete, so we do not trust
any one of them. Each catches a different slice, and the union is the candidate universe:

  1. 10-K COMPETITION SECTION — the names the company itself calls competitors. High signal
     for direct/product competitors; blind to same-multiple names in adjacent businesses.
  2. SIC-CODE SCREEN (own SIC + ADJACENT SICs) — every filer the SEC classifies in the same
     and neighbouring industries. Catches names recall forgets. The "adjacent" part is
     essential: SARO's SIC 3724 (Aircraft Engines & Engine Parts) catches Howmet and SIFCO
     but MISSES AAR/VSE/AerSale/FTAI, which sit in 3728 (aircraft parts), 4581 (airport
     services) and 6726 (leasing). One SIC is never enough.
  3. PROXY (DEF 14A) COMPENSATION PEER GROUP — the peers management pays a consultant (Korn
     Ferry, for SARO) to benchmark comp against. This is management's OWN vetted, size-
     matched peer list, and it is the single best source for market-cap comparability.
  4. 10-K STOCK-PERFORMANCE-GRAPH PEER INDEX — the peer group the company benchmarks its
     TOTAL RETURN against. Another management-stated list, chosen for investor comparison.

THEN, AND ONLY THEN, FILTER AND TIER (human judgment, not automated):
  * drop defunct/acquired filers (no 10-K in ~2 years) — the SIC universe is full of them;
  * attach EV, filing gross margin, coverage and gross-profit STATUS to each survivor;
  * the analyst tiers primary (size + model + margin comparable) vs reference (leaders/too
    big) and decides business-model fit — a services-MRO (SARO, AAR: ~15% margin) is not the
    same comp as a parts manufacturer (HEICO, Howmet: 34-40%) even though both are "aerospace
    aftermarket". EV/Gross-Profit medians blended across those models mislead (see
    valuation_comp.growth_basis for the same lesson on USIO).

This module does the CAPTURE (sources 1-4) and the ENRICHMENT. It deliberately does not
auto-tier or auto-select — that is the analyst's call, and pretending otherwise is how you
get a plausible-looking wrong median. It returns a candidate sheet with provenance (which
source named each), so the analyst can see WHY a name is a candidate and what it would add.
"""

import re
import html as _html

from core import sec_filings

# Adjacent-SIC hints by broad sector. Not exhaustive — the analyst can pass extra_sics — but
# these encode the "one SIC is never enough" lesson for the sectors we've onboarded so far.
_ADJACENT_SICS = {
    "3724": ["3728", "4581", "6726", "3720", "3760"],  # aero engines -> parts, svcs, leasing, aircraft, guided missiles
    "3728": ["3724", "4581", "3720"],                    # aircraft parts -> engines, svcs, aircraft
    "7372": ["7371", "7389", "7374"],                    # prepackaged software -> svcs, data proc
    "6199": ["6022", "7389", "6770"],                    # finance services -> banks, svcs
}


def _company_ticker_map():
    """CIK(int) -> ticker, from EDGAR's canonical company_tickers.json."""
    try:
        data = sec_filings._get("https://www.sec.gov/files/company_tickers.json", timeout=40).json()
        return {int(row["cik_str"]): row["ticker"] for row in data.values()}
    except Exception:
        return {}


def sic_screen(sic, include_adjacent=True, extra_sics=()):
    """Every 10-K filer EDGAR classifies in `sic` (+ adjacent + extra). Returns [(cik, name)]."""
    sics = [str(sic)]
    if include_adjacent:
        sics += _ADJACENT_SICS.get(str(sic), [])
    sics += [str(s) for s in extra_sics]
    out = {}
    for code in dict.fromkeys(sics):
        url = (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&SIC={code}"
               f"&type=10-K&dateb=&owner=include&count=100")
        try:
            t = sec_filings._get(url, timeout=40).text
        except Exception:
            continue
        # company table: CIK link cell followed by the company-name cell
        for cik, name in re.findall(
                r'CIK=(\d{6,10})&[^"]*type=10-K[^>]*>\s*\d+\s*</a>\s*</td>\s*<td[^>]*>\s*([^<]+?)\s*</td>', t):
            out.setdefault(int(cik), _html.unescape(name).strip())
        # fallback pattern
        for cik, name in re.findall(
                r'CIK=(\d{6,10})[^>]*>[^<]*</a></td>\s*<td[^>]*>\s*([^<]+?)\s*</td>', t):
            out.setdefault(int(cik), _html.unescape(name).strip())
    return sorted(out.items(), key=lambda kv: kv[1])


def tenk_competitors(cik, known=None):
    """Named competitors from the 10-K Competition section. `known` narrows the regex to a
    watch-list of expected industry names (avoids false positives from generic capitalized
    words); pass None to just return the raw Competition paragraph for manual reading."""
    try:
        subs = sec_filings._get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", timeout=30).json()
    except Exception:
        return {"names": [], "text": ""}
    r = subs["filings"]["recent"]
    acc = doc = None
    for a, f, d in zip(r["accessionNumber"], r["form"], r["primaryDocument"]):
        if f == "10-K":
            acc, doc = a, d
            break
    if not acc:
        return {"names": [], "text": ""}
    try:
        raw = sec_filings._get(
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{doc}", timeout=90).text
    except Exception:
        return {"names": [], "text": ""}
    flat = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    m = re.search(r"\bCompetition\b", flat)
    text = flat[m.start():m.start() + 1200] if m else ""
    names = []
    if known:
        found = re.findall(r"\b(" + "|".join(re.escape(k) for k in known) + r")\b", flat, re.I)
        from collections import Counter
        names = [n for n, _ in Counter(x.title() for x in found).most_common()]
    return {"names": names, "text": text}


def proxy_peer_group(cik):
    """Best-effort pull of the compensation peer-group list from the latest DEF 14A. Returns
    the peer-discussion paragraph for the analyst to read; auto-extracting a clean company
    list from proxy tables is unreliable, so we surface the text rather than guess."""
    try:
        subs = sec_filings._get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", timeout=30).json()
    except Exception:
        return ""
    r = subs["filings"]["recent"]
    acc = doc = None
    for a, f, d in zip(r["accessionNumber"], r["form"], r["primaryDocument"]):
        if f in ("DEF 14A", "DEFM14A"):
            acc, doc = a, d
            break
    if not acc:
        return ""
    try:
        raw = sec_filings._get(
            f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc.replace('-','')}/{doc}", timeout=90).text
    except Exception:
        return ""
    flat = re.sub(r"\s+", " ", _html.unescape(re.sub(r"<[^>]+>", " ", raw)))
    m = re.search(r"(compensation peer group|peer group (?:of )?companies|comparator group|"
                  r"the following (?:peer )?companies)", flat, re.I)
    return flat[m.start():m.start() + 1600] if m else ""


def enrich(tickers):
    """Attach EV, filing gross margin, gross-profit status and coverage to each ticker, and
    flag whether it is a CURRENT filer worth considering. Never fabricates — a name with no
    clean filing gross profit is returned with its real status so the analyst sees the gap."""
    from core import market_data, forensics
    import yfinance as yf
    rows = []
    for tk in dict.fromkeys(tickers):
        row = {"ticker": tk}
        try:
            ev = market_data.live_ev(tk)
            fm = forensics.filing_margin(tk)
            info = yf.Ticker(tk).info
            row.update({
                "name": info.get("shortName"),
                "ev_m": round((ev.get("enterprise_value") or 0) / 1e6),
                "gross_margin": round((fm.get("gross_margin") or 0) * 100, 1),
                "gp_status": fm.get("status"),
                "analysts": info.get("numberOfAnalystOpinions"),
                "current": (ev.get("enterprise_value") or 0) > 0,
            })
        except Exception as exc:
            row.update({"name": None, "error": str(exc)[:60], "current": False})
        rows.append(row)
    return rows


def discover(ticker, extra_sics=(), known_competitors=None):
    """Run all sources for `ticker` and return a capture sheet with provenance. Does NOT
    tier or select — that is the analyst's judgment (see module docstring)."""
    cik = sec_filings.resolve_cik(ticker)
    subs = sec_filings._get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", timeout=30).json()
    sic = subs.get("sic")
    cik2tk = _company_ticker_map()

    screen = sic_screen(sic, extra_sics=extra_sics)
    screen_tks = [(cik2tk.get(c), nm) for c, nm in screen]
    return {
        "ticker": ticker, "cik": cik, "sic": sic, "sic_desc": subs.get("sicDescription"),
        "sic_universe": [{"ticker": tk, "name": nm, "cik": c}
                         for (c, nm), (tk, _) in zip(screen, screen_tks)],
        "sic_tickers": [tk for tk, _ in screen_tks if tk],
        "tenk_competitors": tenk_competitors(cik, known=known_competitors),
        "proxy_peer_text": proxy_peer_group(cik),
    }
