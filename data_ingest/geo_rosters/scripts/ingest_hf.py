"""Ingest hedge-fund roster JSON {firm: {domain, people:[{name,title}]}} -> house CRM.
Usage: python ingest_hf.py <json_file>"""
import sys, json, html
from core.security import load_environment; load_environment()
from core import roster, firm_book

# exact agent-key name -> (cik, city)
HF_META = {
 "Balyasny Asset Management L.P.": ("1218710", "Chicago"),
 "ExodusPoint Capital Management, LP": ("1736225", "New York"),
 "Alkeon Capital Management LLC": ("1230239", "New York"),
 "Holocene Advisors, LP": ("1700574", "New York"),
 "Alyeska Investment Group, L.P.": ("1453072", "Chicago"),
 "Stadium Capital Management LLC": ("1105087", "New Canaan"),
 "SQN Investors LP": ("1665887", "Menlo Park"),
 "One68 Global Capital, LLC": ("1755535", "New York"),
 "Gilder Gagnon Howe & Co LLC": ("902464", "New York"),
 "272 Capital LP": ("1841077", "Dallas"),
}
firms = firm_book.load_firms()
data = json.load(open(sys.argv[1], encoding="utf-8"))
for firm, payload in data.items():
    meta = HF_META.get(firm)
    if not meta:
        print(f"!! no meta for {firm!r} — skipped"); continue
    cik, city = meta
    if isinstance(payload, list):          # tolerate {firm: [people]} shape too
        domain, people = None, payload
    else:
        domain, people = payload.get("domain"), payload.get("people") or []
    currency = (firms.get(cik) or {}).get("currency") or "active_filer"
    clean = [{"name": html.unescape(p.get("name", "")), "title": html.unescape(p.get("title") or "")}
             for p in people]
    if not clean:
        print(f"{firm[:34]:34s} | (no public people found)"); continue
    res = roster.add_people(firm=firm, firm_cik=cik, city=city, domain=domain,
                            firm_currency=currency, source_note=f"{firm} — public sources, Jul 2026",
                            people=clean)
    print(f"{firm[:34]:34s} | dom={domain or '-':22s} | {len(clean):2d} found -> +{res['added']} new, {res['merged']} merged | {res['by_role']}")
