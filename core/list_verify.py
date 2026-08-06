"""core/list_verify.py — import an outside list of firms and VERIFY each is real before trusting it.

Applies the platform's computed-not-guessed discipline to IMPORTED data — conference lists,
sell-side/broker lists, and AI-generated lists — which is exactly where fabrication and
staleness hide. For each firm name:
  1. VERIFY it's a real firm — look it up as a SEC 13F filer via EDGAR and attach the CIK;
     anything that can't be confirmed is FLAGGED for human review (the anti-hallucination gate).
  2. RECONCILE against the active client's universe — already a holder / prospect / in our
     contacts / brand new.
Callers then PROMOTE the verified-new rows into the curated_targets house book.

The only network dependency is verify_firm() (one throttled SEC EDGAR call per distinct name,
cached per process). Reconciliation is entirely local. See [[curated-targets-house-book]].
"""
import re

from core import sec_filings, web_flow

_verify_cache = {}


def _tokens(name):
    """Distinctive name tokens (generic words dropped), for matching. len>=3 to skip noise."""
    return {t for t in (web_flow._org_key(name) or ()) if len(t) >= 3}


def _query_name(name):
    """The bare firm name to search EDGAR with — drop a trailing ', LLC'/'(...)' etc."""
    return re.sub(r"[,(].*$", "", name or "").strip()


def verify_firm(name):
    """Is `name` a real firm? Look it up as a SEC 13F filer on EDGAR. Returns
    {name, is_real, cik, edgar_name}. is_real is True only when EDGAR has a 13F filer whose
    conformed name SHARES a distinctive token with the input (so a garbled/fake name that
    merely partial-matches an unrelated filer is not falsely confirmed). Cached per process."""
    name = (name or "").strip()
    if name in _verify_cache:
        return _verify_cache[name]
    result = {"name": name, "is_real": False, "cik": None, "edgar_name": None}
    q = _query_name(name)
    if q:
        try:
            resp = sec_filings._get(
                "https://www.sec.gov/cgi-bin/browse-edgar",
                params={"action": "getcompany", "company": q, "type": "13F",
                        "dateb": "", "owner": "include", "count": "10", "output": "atom"})
            names = re.findall(r"<conformed-name>(.*?)</conformed-name>", resp.text, re.I)
            ciks = re.findall(r"<cik>(.*?)</cik>", resp.text, re.I)
            want = _tokens(name)
            for i, en in enumerate(names):
                if _tokens(en) & want:                       # real filer sharing a distinctive token
                    result = {"name": name, "is_real": True,
                              "cik": (ciks[i].strip() if i < len(ciks) else (ciks[0].strip() if ciks else None)),
                              "edgar_name": en.strip()}
                    break
        except Exception:
            pass
    _verify_cache[name] = result
    return result


def client_universe(client_id=None):
    """{distinctive_token: {sources}} of the client's known firms — holders (target DB),
    peer-prospects, and 13F-sourced contacts — for local reconciliation."""
    from core import contacts, peer_prospects, targets
    idx = {}

    def add(names, src):
        for f in names:
            for t in _tokens(f or ""):
                idx.setdefault(t, set()).add(src)

    try:
        add([r.get("Fund", "") for r in (targets.targets_as_institutions(client_id) or [])], "holder")
    except Exception:
        pass
    try:
        add([r.get("filer", "") for r in (peer_prospects.all_candidates(client_id) or [])], "prospect")
    except Exception:
        pass
    try:
        add([c.get("firm", "") for c in (contacts.list_contacts(limit=100000) or [])], "contacts")
    except Exception:
        pass
    return idx


def reconcile(name, universe):
    """Where does `name` already sit in the client's universe? holder > prospect > contacts > new."""
    hits = set()
    for t in _tokens(name):
        hits |= universe.get(t, set())
    for label in ("holder", "prospect", "contacts"):
        if label in hits:
            return label
    return "new"


_STATUS_LABEL = {
    "holder": "Already a holder", "prospect": "Already a prospect",
    "contacts": "In our contacts", "new": "New to us",
}


def verify_and_reconcile(names, client_id=None):
    """Verify + reconcile a list of firm names. Returns a row per non-empty name:
    {name, is_real, cik, edgar_name, status, status_label}. Deduped (case-insensitive)."""
    universe = client_universe(client_id)
    out, seen = [], set()
    for raw in names:
        n = (raw or "").strip()
        if not n or n.lower() in seen:
            continue
        seen.add(n.lower())
        v = verify_firm(n)
        status = reconcile(n, universe)
        out.append({**v, "status": status, "status_label": _STATUS_LABEL[status]})
    return out


def promote(rows, client_id=None):
    """Promote verified-real rows into the client's curated_targets house book. Skips
    unverified rows (never promote something we couldn't confirm is real). Returns count added."""
    from core import curated_targets
    added = 0
    for r in rows:
        if not r.get("is_real"):
            continue
        cik = r.get("cik") or "—"
        if curated_targets.add(r["name"], rationale=f"Imported + SEC-verified (CIK {cik})",
                               scope="client", cid=client_id, added_by="import-verify"):
            added += 1
    return added
