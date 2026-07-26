"""core/roster.py — fill out a firm's PM/analyst ROSTER.

The 13F gives one signatory per firm; the buy-side people who actually make and influence the
decision (PMs, sector analysts, CIO, DoR) live on the firm's own team page. This ingests a list
of {name, title} pulled for a firm and lands them as classified house contacts, linked to the
firm's CIK so they sit under the same account as everything else. Being on the CURRENT team page
is itself a currency signal — these are present-day employees, unlike the 2021 lists.
"""
from datetime import datetime

from core import contacts, contact_classifier as cc


def add_people(firm, firm_cik=None, city=None, domain=None, people=None,
               source="firm_site", source_note="Firm website team page", firm_currency=None,
               side="buy", country=None):
    """people = [{'name':..., 'title':...}, ...]. Lands each as a classified contact under `firm`.
    DEDUPES against the firm's existing contacts: someone already in the book (e.g. from Rob's
    2021 lists) is ENRICHED in place (correct role from the current title + firm CIK link), not
    duplicated; genuinely new people get a CIK-keyed record. Returns a summary."""
    from core import db
    firm_key = contacts._norm(firm)
    fcik = str(firm_cik) if firm_cik else None

    conn = db.get_connection()
    try:
        cur = conn.cursor()
        pg = db.connection_is_postgres(conn)
        ph = "%s" if pg else "?"
        if fcik:
            cur.execute(f"SELECT contact_id FROM contacts WHERE firm_key={ph} OR cik={ph} OR firm_cik={ph}",
                        (firm_key, fcik, fcik))
        else:
            cur.execute(f"SELECT contact_id FROM contacts WHERE firm_key={ph}", (firm_key,))
        existing = {r[0] for r in cur.fetchall()}
    finally:
        conn.close()

    def _classify(cid, title):
        roles, primary = cc.classify_roles(title, side=side)
        contacts.update_classification(
            cid, roles=",".join(roles) or None, primary_role=primary, seniority=cc.seniority_for(roles),
            firm_type=cc.firm_type_for(firm, domain), market_cap_focus="micro,small",
            validation_status="probable", confidence=70, firm_cik=fcik, firm_currency=firm_currency,
            city=city, country=country, provenance=source_note)
        return primary

    added = merged = skipped = 0
    by_role = {}
    for p in (people or []):
        name = (p.get("name") or "").strip()
        title = (p.get("title") or "").strip() or None
        if not name or len(name.split()) < 2:
            skipped += 1
            continue
        manual_id = contacts.contact_id_for(None, name, firm)
        cik_id = contacts.contact_id_for(firm_cik, name, firm) if firm_cik else manual_id
        if manual_id in existing:                 # already in Rob's book -> enrich in place
            primary = _classify(manual_id, title)
            merged += 1
        elif cik_id in existing:
            primary = _classify(cik_id, title)
            merged += 1
        else:                                     # genuinely new roster member
            cid = contacts.upsert_contact(name=name, firm=firm, cik=fcik, title=title,
                                          domain=domain, source=source, source_ref=source_note)
            primary = _classify(cid, title)
            added += 1
        by_role[primary or "(unknown)"] = by_role.get(primary or "(unknown)", 0) + 1
    return {"firm": firm, "added": added, "merged": merged, "skipped": skipped,
            "by_role": by_role, "at": datetime.now().isoformat()}
