"""core/contact_ingest.py — the commit step of the contact pipeline (§03, stages 3-8).

Takes already-parsed rows (each a dict on the canonical field names) plus provenance,
side, and an allocation policy, then per row: normalize -> classify
(core.contact_classifier) -> resolve/dedupe (core.contacts.contact_id_for, deterministic)
-> upsert identity -> write the classification layer. Returns a summary with the
distributions so a load can be eyeballed.

`allocation` is recorded for now; the per-client `client_book` write lands in Phase 3.
For a trusted house-only seed (the operator's own lists) this commits directly; a
review-gate UI will wrap the same call for lower-trust / client uploads.

Canonical row fields (map arbitrary upload headers to these before calling):
  first_name, last_name, name, firm, title, email, phone, city, region, country,
  source_file, source_context, market_cap_focus
"""
from core import contacts, contact_classifier as cc


def _clean(v):
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _full_name(row):
    if _clean(row.get("name")):
        return _clean(row["name"])
    fn = _clean(row.get("first_name")) or ""
    ln = _clean(row.get("last_name")) or ""
    return (fn + " " + ln).strip() or None


def _domain(email):
    return email.rsplit("@", 1)[-1].lower() if email and "@" in email else None


def ingest_rows(rows, provenance, side="buy", allocation="house_only",
                default_market_cap=None, default_source="bulk_upload"):
    """Ingest an iterable of canonical-field dicts. Returns a summary dict.

    Per-row `market_cap_focus` (if present on the row) wins over `default_market_cap`
    — so a batch can carry a size band only where there's evidence for it."""
    made, skipped, updated = 0, 0, 0
    by_role, by_firm, by_country, by_sen = {}, {}, {}, {}

    def bump(d, k):
        d[k or "(none)"] = d.get(k or "(none)", 0) + 1

    for row in rows:
        name, firm = _full_name(row), _clean(row.get("firm"))
        if not name or not firm:
            skipped += 1
            continue
        email = _clean(row.get("email"))
        dom = _domain(email)
        title = _clean(row.get("title"))

        cid = contacts.upsert_contact(
            name=name, firm=firm, title=title, phone=_clean(row.get("phone")),
            email=email, domain=dom, source=default_source,
            source_ref=_clean(row.get("source_file")) or provenance,
        )
        if not cid:
            skipped += 1
            continue

        roles, primary = cc.classify_roles(title, side=side)
        seniority = cc.seniority_for(roles)
        firm_type = cc.firm_type_for(firm, dom)
        country = cc.country_for(_clean(row.get("region")) or _clean(row.get("country")), email)
        mcap = _clean(row.get("market_cap_focus")) or default_market_cap

        n = contacts.update_classification(
            cid,
            roles=",".join(roles) or None, primary_role=primary, seniority=seniority,
            firm_type=firm_type, country=country,
            region=_clean(row.get("region")), city=_clean(row.get("city")),
            market_cap_focus=mcap, validation_status="unknown",   # not scrubbed yet — Phase 2
            provenance=_clean(row.get("source_context")) or provenance,
        )
        made += 1
        updated += (1 if n else 0)
        bump(by_role, primary)
        bump(by_firm, firm_type)
        bump(by_country, country)
        bump(by_sen, seniority)

    return {
        "ingested": made, "skipped": skipped, "classified": updated,
        "allocation": allocation, "provenance": provenance,
        "by_primary_role": dict(sorted(by_role.items(), key=lambda x: -x[1])),
        "by_firm_type": dict(sorted(by_firm.items(), key=lambda x: -x[1])),
        "by_seniority": dict(sorted(by_sen.items(), key=lambda x: -x[1])),
        "by_country": dict(sorted(by_country.items(), key=lambda x: -x[1])),
    }
