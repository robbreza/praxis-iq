"""core/contact_classifier.py — rule-first labeling for the contact pipeline (§02).

Cheap, deterministic signals do the work; an LLM tail (not invoked here) is for the
ambiguous remainder only. Pure functions — no DB, no network. Given a job-function
string, firm name, and location, it returns the roles (multi-valued + a primary),
seniority / decision-weight, firm type, and country the design taxonomy defines.

Roles are SIDE-aware: the same word ("Analyst") means a buy-side analyst on a buyside
list and a sell-side analyst on a coverage list, so the caller passes `side` — usually
inferred once from the source (a "Buyside Call List" makes every row buy-side by
construction, which is what carries the 67% of real rows that have no title at all).
"""
import re

# ── canonical role tokens ───────────────────────────────────────────────────
ROLE_PM = "buy_side_pm"
ROLE_SECTOR_PM = "buy_side_sector_pm"
ROLE_BS_SECTOR_ANALYST = "bs_sector_analyst"
ROLE_BS_GENERALIST = "bs_generalist"
ROLE_BS_ANALYST = "bs_analyst"              # buy-side analyst, sector unspecified
ROLE_CIO = "cio"
ROLE_DOR = "director_of_research"
ROLE_ASSOC_PM = "associate_pm"
ROLE_SS_ANALYST = "ss_analyst"
ROLE_SS_SECTOR_ANALYST = "ss_sector_analyst"
ROLE_SS_ASSOC = "ss_associate"
ROLE_SS_SALES = "ss_sales"
ROLE_TRADER = "trader"
ROLE_STRATEGIST = "strategist_macro"
ROLE_ALLOCATOR = "asset_allocator"
ROLE_ESG = "esg_governance"
ROLE_PRINCIPAL = "principal_csuite"
ROLE_RIA = "ria_advisor"
ROLE_FAMILY = "family_office"
ROLE_CONSULTANT = "consultant"
ROLE_BANKER = "banker"
ROLE_MEDIA = "media"
ROLE_OTHER = "ir_other"
# source-labeled but no title given — preserves side so the row stays queryable
ROLE_BS_UNSPEC = "bs_unspecified"
ROLE_SS_UNSPEC = "ss_unspecified"

_SPLIT = re.compile(r"[,/;]|\band\b|&|\+")


def _tokens(job_function):
    if not job_function:
        return []
    return [p.strip().lower() for p in _SPLIT.split(str(job_function)) if p.strip()]


def _map_token(t, side):
    has = lambda *ks: any(k in t for k in ks)
    if has("chief investment officer") or t == "cio":
        return ROLE_CIO
    if has("director of research", "head of research", "research director"):
        return ROLE_DOR
    if has("associate portfolio manager", "associate pm", "assistant portfolio manager"):
        return ROLE_ASSOC_PM
    if has("portfolio manager") or t == "pm" or t == "pm/analyst":
        return ROLE_SECTOR_PM if has("sector") else ROLE_PM
    if (has("chief executive", "ceo", "chairman", "founder", "founding", "managing partner",
            "managing member", "owner", "principal")
            or (has("president") and not has("vice president"))):
        return ROLE_PRINCIPAL
    if has("corporate access", "corp access", "sales"):
        return ROLE_SS_SALES
    if has("strateg", "econom"):
        return ROLE_STRATEGIST
    if has("asset alloc", "allocator", "allocation"):
        return ROLE_ALLOCATOR
    if has("governance", "proxy", "stewardship", "esg", "sustainab", "responsible invest"):
        return ROLE_ESG
    if has("head of trading", "trader", "trading", "dealing"):
        return ROLE_TRADER
    if has("analyst", "research"):
        if side == "sell":
            return ROLE_SS_SECTOR_ANALYST if has("sector") else ROLE_SS_ANALYST
        if has("sector"):
            return ROLE_BS_SECTOR_ANALYST
        if has("generalist"):
            return ROLE_BS_GENERALIST
        return ROLE_BS_ANALYST
    if has("associate", "junior"):
        return ROLE_SS_ASSOC if side == "sell" else ROLE_ASSOC_PM
    if has("banker", "investment banking"):
        return ROLE_BANKER
    if has("journalist", "reporter", "editor", "media", "press", "correspondent"):
        return ROLE_MEDIA
    if has("investor relations", "ir "):
        return ROLE_OTHER
    return None


# The FUNCTIONAL investment role wins the primary — "Portfolio Manager, Principal" is a PM,
# "Executive VP, Portfolio Manager" is a PM. CIO stays top (it's the investment lead); bare
# ownership/board rank (Principal/CEO/Chairman) is primary only when no function is stated.
_PRIMARY_PRIORITY = [ROLE_CIO, ROLE_DOR, ROLE_SECTOR_PM, ROLE_PM, ROLE_ASSOC_PM,
                     ROLE_ALLOCATOR, ROLE_STRATEGIST, ROLE_ESG, ROLE_SS_SALES,
                     ROLE_BS_SECTOR_ANALYST, ROLE_SS_SECTOR_ANALYST, ROLE_BS_GENERALIST,
                     ROLE_BS_ANALYST, ROLE_SS_ANALYST, ROLE_TRADER, ROLE_SS_ASSOC,
                     ROLE_BANKER, ROLE_PRINCIPAL, ROLE_MEDIA, ROLE_OTHER]


def classify_roles(job_function, side="buy"):
    """Return (roles:list[str], primary:str|None). `side` in {'buy','sell','unknown'}.
    Empty title but a known side yields a side-placeholder role so the row's buy/sell
    nature survives (this is how the source label carries the untitled majority)."""
    roles = []
    for t in _tokens(job_function):
        r = _map_token(t, side)
        if r and r not in roles:
            roles.append(r)
    if not roles:
        placeholder = {"buy": ROLE_BS_UNSPEC, "sell": ROLE_SS_UNSPEC}.get(side)
        return ([placeholder], placeholder) if placeholder else ([], None)
    primary = next((r for r in _PRIMARY_PRIORITY if r in roles), roles[0])
    return roles, primary


# ── seniority / decision-weight ─────────────────────────────────────────────
_PRINCIPAL = {ROLE_CIO, ROLE_PRINCIPAL}
_DECISION = {ROLE_PM, ROLE_SECTOR_PM, ROLE_DOR}
_JUNIOR = {ROLE_ASSOC_PM, ROLE_SS_ASSOC}
_INFLUENCER = {ROLE_BS_ANALYST, ROLE_BS_SECTOR_ANALYST, ROLE_BS_GENERALIST, ROLE_SS_ANALYST,
               ROLE_SS_SECTOR_ANALYST, ROLE_STRATEGIST, ROLE_ALLOCATOR, ROLE_ESG, ROLE_TRADER,
               ROLE_SS_SALES, ROLE_BANKER}


def seniority_for(roles):
    """Decision-weight from the role set — separate from function (§02, Axis B)."""
    s = set(roles or [])
    if s & _PRINCIPAL:
        return "principal"
    if s & _DECISION:
        return "decision_maker"
    if (s & _JUNIOR) and not (s & _INFLUENCER):
        return "junior"
    if s & _INFLUENCER:
        return "influencer"
    return "unknown"


# ── firm type (from the institution name) ───────────────────────────────────
def firm_type_for(institution, email_domain=None):
    n = (institution or "").lower()
    has = lambda *ks: any(k in n for k in ks)
    if has("retirement", "pension", "endowment", "foundation", "sovereign",
           "superannuation", "provident", "common fund", "trust for"):
        return "asset_owner"
    if has("family office") or n.strip().endswith("family office"):
        return "family_office"
    if has("outsourced cio", "ocio", "outsourced investment"):
        return "ocio"
    if has("mercer", "callan", "wilshire", "meketa", "nepc", "cambridge associates",
           "verus", "russell investments consulting", "consult"):
        return "consultant"
    if has("wealth", "advisors", "advisers", "advisory", "financial advisor"):
        return "ria"
    if has("securities", "brokerage", "capital markets", "broker-dealer", "broker dealer"):
        return "broker_dealer"
    if has("insurance", "assurance", "life insurance", "reinsurance"):
        return "insurance"
    if has("bank ", "bancorp", "banque") or n.strip().endswith("bank"):
        return "bank"
    return "asset_manager"   # capital / management / partners / LP / investment / asset — the default


# ── jurisdiction ────────────────────────────────────────────────────────────
_CA = {"ontario", "quebec", "québec", "british columbia", "alberta", "manitoba",
       "saskatchewan", "nova scotia", "new brunswick", "newfoundland",
       "newfoundland and labrador", "prince edward island", "yukon",
       "northwest territories", "nunavut",
       "on", "qc", "bc", "ab", "mb", "sk", "ns", "nb", "nl", "pe", "yt", "nt", "nu"}
_AU = {"new south wales", "victoria", "queensland", "western australia", "south australia",
       "tasmania", "australian capital territory", "northern territory",
       "nsw", "vic", "qld", "wa", "sa", "tas", "act"}
_US = {"alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
       "delaware", "florida", "georgia", "hawaii", "idaho", "illinois", "indiana", "iowa",
       "kansas", "kentucky", "louisiana", "maine", "maryland", "massachusetts", "michigan",
       "minnesota", "mississippi", "missouri", "montana", "nebraska", "nevada",
       "new hampshire", "new jersey", "new mexico", "new york", "north carolina",
       "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
       "south carolina", "south dakota", "tennessee", "texas", "utah", "vermont",
       "virginia", "washington", "west virginia", "wisconsin", "wyoming",
       "district of columbia", "dc", "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl",
       "ga", "hi", "id", "il", "in", "ia", "ks", "ky", "la", "me", "md", "ma", "mi", "mn",
       "ms", "mo", "mt", "ne", "nv", "nh", "nj", "nm", "ny", "nc", "nd", "oh", "ok", "or",
       "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt", "va", "wa", "wv", "wi", "wy"}


def country_for(region, email=None):
    """Country from state/province, then email TLD as a fallback. Decides which
    registration validators apply in Phase 2 (US→EDGAR/FINRA; CA→CSA; UK→FCA; AU→ASIC)."""
    s = (region or "").strip().lower()
    if s in _CA:
        return "Canada"
    if s in _AU:
        return "Australia"
    if s in _US:
        return "US"
    dom = (email or "").rsplit("@", 1)[-1].lower() if email and "@" in (email or "") else ""
    if dom.endswith(".ca"):
        return "Canada"
    if dom.endswith(".co.uk") or dom.endswith(".uk"):
        return "UK"
    if dom.endswith(".com.au") or dom.endswith(".au"):
        return "Australia"
    if dom.endswith((".com", ".net", ".org", ".us")):
        return "US"       # US-centric default when a corporate gTLD is all we have
    return None            # genuinely unknown — leave for Phase-2 resolution
