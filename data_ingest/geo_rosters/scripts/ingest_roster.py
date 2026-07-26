"""Ingest an agent's roster JSON ({firm: [{name,title}]}) into the house CRM via roster.add_people.
Usage: python ingest_roster.py <json_file>"""
import sys, json, html
from core.security import load_environment; load_environment()
from core import roster

FIRM_META = {
 "Mackenzie Financial Corp": ("919859", "mackenzieinvestments.com", "Toronto"),
 "Hillsdale Investment Management Inc.": ("1368465", "hillsdaleinv.com", "Toronto"),
 "Spartan Fund Management Inc.": ("1930346", "spartanfunds.ca", "Toronto"),
 "CIBC Asset Management Inc": ("1021926", "cibc.ca", "Toronto"),
 "PenderFund Capital Management Ltd.": ("1706164", "penderfund.com", "Vancouver"),
 "North Growth Management Ltd.": ("1745796", "northgrowth.com", "Vancouver"),
 "Peregrine Investment Management Inc": ("2053303", "peregrineinv.com", "Toronto"),
 "William Blair Investment Management, LLC": ("1644956", "williamblair.com", "Chicago"),
 "Granahan Investment Management, LLC": ("1026710", "granahan.com", "Waltham"),
 "Kennedy Capital Management LLC": ("884589", "kennedycapital.com", "St Louis"),
 "Punch & Associates Investment Management, Inc.": ("1238990", "punchinvest.com", "Edina"),
 "Ancora Advisors LLC": ("1446114", "ancora.net", "Cleveland"),
 "Royce & Associates LP": ("906304", "royceinvest.com", "New York"),
 "Fred Alger Management, LLC": ("3520", "alger.com", "New York"),
 "Lord, Abbett & Co. LLC": ("728100", "lordabbett.com", "Jersey City"),
 "Heartland Advisors Inc": ("937394", "heartlandadvisors.com", "Milwaukee"),
}

data = json.load(open(sys.argv[1], encoding="utf-8"))
for firm, people in data.items():
    meta = FIRM_META.get(firm)
    if not meta:
        print(f"!! no meta for {firm!r} — skipped ({len(people)} people)"); continue
    cik, domain, city = meta
    clean = [{"name": html.unescape(p.get("name", "")), "title": html.unescape(p.get("title") or "")}
             for p in people]
    res = roster.add_people(firm=firm, firm_cik=cik, city=city, domain=domain,
                            firm_currency="active_filer",
                            source_note=f"{firm} team page, Jul 2026", people=clean)
    print(f"{firm[:34]:34s} | web {len(people):2d} -> +{res['added']} new, {res['merged']} merged, {res['skipped']} skip | roles {res['by_role']}")
