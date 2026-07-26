"""Ingest Canadian roster JSON {firm:{domain,people}} -> house CRM (dedup-safe, side-aware).
Usage: python ingest_ca.py <json_file>"""
import sys, json, html
from core.security import load_environment; load_environment()
from core import roster

# firm -> (cik | None, city, side). CIK None = resolve later via the currency batch.
CA_META = {
 "RBC Global Asset Management Inc.": (None, "Toronto", "buy"),
 "TD Asset Management Inc.": ("1056053", "Toronto", "buy"),
 "Manulife Investment Management": ("928047", "Toronto", "buy"),
 "1832 Asset Management L.P.": (None, "Toronto", "buy"),
 "CI Global Asset Management": ("1163648", "Toronto", "buy"),
 "Burgundy Asset Management Ltd.": ("1315868", "Toronto", "buy"),
 "Picton Mahoney Asset Management": (None, "Toronto", "buy"),
}
data = json.load(open(sys.argv[1], encoding="utf-8"))
for firm, payload in data.items():
    meta = CA_META.get(firm)
    if not meta:
        print(f"!! no meta for {firm!r} — skipped"); continue
    cik, city, side = meta
    domain = payload.get("domain")
    people = [{"name": html.unescape(p.get("name", "")), "title": html.unescape(p.get("title") or "")}
              for p in (payload.get("people") or [])]
    if not people:
        print(f"{firm[:34]:34s} | (none)"); continue
    res = roster.add_people(firm=firm, firm_cik=cik, city=city, domain=domain, side=side,
                            firm_currency="active_filer" if cik else None,
                            source_note=f"{firm} team page (Canada), Jul 2026", people=people)
    print(f"{firm[:34]:34s} | dom={domain or '-':20s} side={side} | {len(people):2d} -> +{res['added']} new, {res['merged']} merged | {res['by_role']}")
