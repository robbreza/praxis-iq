"""core/contact_currency.py — Phase-2b firm CURRENCY via EDGAR 13F (§04, the "who moved" axis).

Email-scrubbing (Phase 2a) proves a domain accepts mail; it says nothing about whether the
firm still exists. This resolves a firm NAME -> SEC CIK from EDGAR's cik-lookup dump, then
reads the filer's recent 13F-HR history:

  active_filer     filed a 13F-HR within _ACTIVE_MONTHS -> a live institution today
  inactive_filer   resolved to a CIK but no recent 13F  -> may have wound down / merged
  no_13f           resolved, but never a 13F filer      -> a small RIA / non-13F shop (neutral)
  unresolved       name didn't match EDGAR exactly      -> informal name OR truly absent (neutral-)

Free + authoritative. This is the firm-liveness foundation; matching a specific PERSON to the
firm's CURRENT 13F signatory (contacts.signatory_from_13f) is the v2 person-currency step.

NORMALIZATION: NOT fund_lineup._norm — that collapses a manager to its distinctive family token
("1492 Capital Management" -> "1492"), which is right for fund-trust matching but would resolve
firms to the wrong CIK here. We keep the real firm name, dropping only parentheticals and legal
suffixes, and only accept a resolution that is UNAMBIGUOUS (or disambiguated by 'which one files
13F') — a wrong CIK is worse than an unresolved one.
"""
import re
import time
from datetime import datetime, timedelta

from core import db, sec_filings as sf

_ACTIVE_MONTHS = 18   # a live 13F filer reports quarterly; >18mo silent => not currently active
_LEGAL = {"llc", "inc", "incorporated", "lp", "llp", "ltd", "limited", "corp", "corporation",
          "co", "company", "plc", "sa", "ag", "gmbh", "lllp", "na", "nv", "srl", "spa", "the"}
# safe, unambiguous abbreviation expansions so "…Capital Mgmt" matches EDGAR's "…MANAGEMENT"
_ABBREV = {"mgmt": "management", "mgt": "management", "mngt": "management", "mngmt": "management",
           "assoc": "associates", "assocs": "associates", "ptnrs": "partners", "ptrs": "partners",
           "intl": "international", "advisers": "advisors", "grp": "group"}


def _firm_norm(name):
    s = re.sub(r"\(.*?\)", " ", name or "")           # drop "(U.S.)", "(Asset Management)", ...
    s = re.sub(r"[^a-z0-9 ]", " ", s.lower())
    toks = [_ABBREV.get(t, t) for t in s.split() if t and t not in _LEGAL]
    return " ".join(toks)


def _build_cik_index(target_norms):
    """One streaming pass over EDGAR's cik-lookup-data.txt (~40MB), keeping only EXACT-norm
    matches for the firm names we care about — memory-light. Returns {norm: [cik,...]}."""
    try:
        txt = sf._get("https://www.sec.gov/Archives/edgar/cik-lookup-data.txt", timeout=120).text
    except Exception:
        return {}
    idx = {}
    for line in txt.splitlines():
        m = re.match(r"^(.*):(\d+):\s*$", line)        # "HEARTLAND GROUP INC:0000809586:"
        if not m:
            continue
        nk = _firm_norm(m.group(1))
        if nk in target_norms:
            cik = int(m.group(2))
            idx.setdefault(nk, [])
            if cik not in idx[nk]:
                idx[nk].append(cik)
    return idx


def firm_currency(cik):
    """(status, last_13f_date) for a CIK via its 13F-HR history."""
    fils = sf.filer_13f_filings(cik, limit=1)
    if not fils:
        return "no_13f", None
    last = fils[0].get("date")
    try:
        d = datetime.strptime(str(last), "%Y-%m-%d")
        active = (datetime.now() - d) <= timedelta(days=_ACTIVE_MONTHS * 30)
    except Exception:
        active = True
    return ("active_filer" if active else "inactive_filer"), last


def _resolve_firm(ciks, throttle):
    """Given the candidate CIKs for one firm norm, return (cik, status). A single candidate is
    taken as-is; multiple candidates are disambiguated toward whichever actually files 13F (the
    institutional entity we care about); if none files, it's ambiguous and we don't attribute."""
    if not ciks:
        return None, "unresolved"
    if len(ciks) == 1:
        status, _ = firm_currency(ciks[0])
        return ciks[0], status
    filer = None
    for cik in ciks[:5]:
        status, _ = firm_currency(cik)
        time.sleep(throttle)
        if status in ("active_filer", "inactive_filer"):
            return cik, status
        if filer is None:
            filer = cik
    return None, "ambiguous"   # several CIKs, none a 13F filer -> don't guess


def batch_currency(where="source='bulk_upload'", throttle=0.12, limit_firms=None):
    """Resolve every distinct firm in the matching contact set to a CIK, classify its 13F
    currency, and write firm_cik + firm_currency onto its contacts. Holds NO db connection
    across the throttled EDGAR phase. `where` is a TRUSTED literal."""
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT DISTINCT firm FROM contacts WHERE {where} AND firm IS NOT NULL")
        firms = [r[0] for r in cur.fetchall()]
    finally:
        conn.close()

    norm_of = {f: _firm_norm(f) for f in firms}
    target = set(n for n in norm_of.values() if n)
    if limit_firms:
        target = set(list(target)[:limit_firms])

    idx = _build_cik_index(target)               # one download, offline

    firm_status = {}                             # norm -> (cik|None, status)
    for nk in target:
        firm_status[nk] = _resolve_firm(idx.get(nk, []), throttle)
        time.sleep(throttle)

    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT contact_id, firm FROM contacts WHERE {where} AND firm IS NOT NULL")
        rows = cur.fetchall()
    finally:
        conn.close()

    updates, hist = [], {}
    for cid, firm in rows:
        cik, status = firm_status.get(norm_of.get(firm, ""), (None, "unresolved"))
        updates.append((cid, str(cik) if cik else None, status))
        hist[status] = hist.get(status, 0) + 1

    if updates:
        _write(updates)
    return {"distinct_firms": len(target),
            "resolved_ciks": sum(1 for v in firm_status.values() if v[0]),
            "contacts_updated": len(updates),
            "by_firm_currency": dict(sorted(hist.items(), key=lambda x: -x[1]))}


# ── Phase-2b v2: person-level currency via the CURRENT 13F signatory ─────────
def current_signatory(cik):
    """The firm's CURRENT 13F signing officer (name/title/phone) from its latest 13F-HR."""
    fils = sf.filer_13f_filings(cik, limit=1)
    if not fils or not fils[0].get("accession"):
        return None
    from core import contacts as _contacts
    sig = _contacts.signatory_from_13f(cik, fils[0]["accession"])
    if not sig or not sig.get("name"):
        return None
    return {**sig, "accession": fils[0]["accession"], "date": fils[0].get("date")}


def _name_tokens(n):
    return frozenset(t for t in re.sub(r"[^a-z ]", " ", (n or "").lower()).split() if len(t) > 1)


# full contacts-table column order for a bulk upsert of a signatory contact
_SIG_COLS = ["contact_id", "cik", "firm", "firm_key", "name", "title", "phone", "email",
             "email_status", "email_source", "email_checked_at", "domain", "source", "source_ref",
             "created_at", "updated_at", "roles", "primary_role", "seniority", "firm_type",
             "country", "region", "city", "market_cap_focus", "validation_status", "confidence",
             "provenance", "firm_cik", "firm_currency"]


def batch_signatory(where="source='bulk_upload'", throttle=0.15, limit=None):
    """For every firm we resolved to a CIK, pull the CURRENT 13F signatory: (1) VERIFY any
    existing contact whose name matches the signatory (they ARE the current signing officer),
    and (2) UPSERT the signatory as a fresh, guaranteed-current contact. Returns a summary."""
    from datetime import datetime
    from core import contacts as _contacts, contact_classifier as _cc

    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute(f"SELECT DISTINCT firm, firm_cik, firm_currency FROM contacts WHERE {where} "
                    f"AND firm_cik IS NOT NULL AND firm_currency IN ('active_filer','inactive_filer')")
        firm_ciks = [(f, int(c), cy) for f, c, cy in cur.fetchall() if c]
        cur.execute(f"SELECT contact_id, firm, name FROM contacts WHERE {where} AND firm IS NOT NULL")
        existing = cur.fetchall()
    finally:
        conn.close()
    if limit:
        firm_ciks = firm_ciks[:limit]

    by_firm = {}
    for cid, firm, name in existing:
        by_firm.setdefault(firm, []).append((cid, _name_tokens(name)))

    verify, sig_rows = set(), {}
    now = datetime.now()
    for firm, cik, currency in firm_ciks:
        sig = current_signatory(cik)
        time.sleep(throttle * 2)
        if not sig:
            continue
        st = _name_tokens(sig["name"])
        for cid, toks in by_firm.get(firm, []):
            if toks and toks == st:
                verify.add(cid)
        ncid = _contacts.contact_id_for(cik, sig["name"], firm)
        roles, primary = _cc.classify_roles(sig.get("title"), side="buy")
        sig_rows[ncid] = (
            ncid, str(cik), firm, _contacts._norm(firm), sig["name"], sig.get("title"), sig.get("phone"),
            None, "unknown", None, None, None, "edgar_13f_current", sig["accession"], now, now,
            ",".join(roles) or None, primary, _cc.seniority_for(roles), _cc.firm_type_for(firm),
            None, None, None, None, "verified", 95,
            f"EDGAR 13F signatory as of {sig.get('date')}", str(cik), currency)

    _write_signatory(list(verify), list(sig_rows.values()))
    return {"firms_checked": len(firm_ciks), "signatories_found": len(sig_rows),
            "existing_verified": len(verify), "signatory_contacts_upserted": len(sig_rows)}


def _write_signatory(verify_cids, sig_rows):
    from core.security import get_database_url
    dsn = get_database_url()
    if not dsn:
        return   # signatory batch is Postgres-only (EDGAR seed job)
    import psycopg2
    from psycopg2.extras import execute_values
    conn = psycopg2.connect(dsn)
    try:
        cur = conn.cursor()
        if verify_cids:
            execute_values(
                cur,
                "UPDATE contacts AS c SET validation_status='verified', confidence=GREATEST(COALESCE(confidence,0),90), "
                "updated_at=now() FROM (VALUES %s) AS v(cid) WHERE c.contact_id = v.cid",
                [(x,) for x in verify_cids], page_size=500)
        if sig_rows:
            upd = [c for c in _SIG_COLS if c not in ("contact_id", "created_at", "email")]
            setc = ", ".join(f"{c} = EXCLUDED.{c}" for c in upd) + ", email = COALESCE(EXCLUDED.email, contacts.email)"
            execute_values(cur, f"INSERT INTO contacts ({', '.join(_SIG_COLS)}) VALUES %s "
                                f"ON CONFLICT (contact_id) DO UPDATE SET {setc}", sig_rows, page_size=400)
        conn.commit()
    finally:
        conn.close()


def _write(updates):
    from core.security import get_database_url
    dsn = get_database_url()
    if dsn:
        import psycopg2
        from psycopg2.extras import execute_values
        conn = psycopg2.connect(dsn)
        try:
            cur = conn.cursor()
            execute_values(
                cur,
                "UPDATE contacts AS c SET firm_cik = v.cik, firm_currency = v.cur, updated_at = now() "
                "FROM (VALUES %s) AS v(cid, cik, cur) WHERE c.contact_id = v.cid",
                updates, page_size=500)
            conn.commit()
        finally:
            conn.close()
    else:
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            now = datetime.now().isoformat()
            for cid, cik, status in updates:
                cur.execute("UPDATE contacts SET firm_cik=?, firm_currency=?, updated_at=? WHERE contact_id=?",
                            (cik, status, now, cid))
            conn.commit()
        finally:
            conn.close()
