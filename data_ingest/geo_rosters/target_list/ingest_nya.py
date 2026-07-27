"""Ingest NY-A verified firms + rosters (target-list build-out, Jul 2026). CIK None -> resolved later.
Verified-but-no-roster firms (1798 Global, Brompton Cross, Camelot) skipped (no people). Rejected
(Bascom Hill, Catapult, Colonial Fund, First York) absent. Corrected cities: Alpine=NJ, Chilton/Empire=CT."""
import html, re
from core.security import load_environment; load_environment()
from core import roster

_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","frm","jd","mba","ii","iii","iv"}
def clean(name):
    parts=[p.strip() for p in name.split(",")]
    kept=[parts[0]]+[p for p in parts[1:] if p.lower().strip(". ") not in _CREDS]
    return ", ".join([k for k in kept if k]).strip(" ,")

E=[
 ("ACT II Global","New York, NY",None,[("Dennis Leibowitz","Founder & Managing General Partner (CIO)")]),
 ("Alpine Associates","Englewood Cliffs, NJ","alpineassociatesmanagement.com",[
   ("Robert E. Zoellner, Jr.","CEO & CIO"),("Brad Cohen","Portfolio Manager & Senior Research Analyst"),
   ("Colton Zoellner","Deputy Portfolio Manager & Trader"),("Henry J. Cauceglia","Director of Research & Head of IR"),
   ("Judey A. Delgado","Senior Research Analyst")]),
 ("A.R.T. Advisors","New York, NY",None,[("Aaron M. Sosnick","Founder & Chairman")]),
 ("Balyasny Asset Management","New York, NY","bamfunds.com",[
   ("Dmitry Balyasny","Managing Partner & CIO"),("Taylor O'Malley","Co-Founding Partner & Chairman"),
   ("Scott Schroeder","Co-Founding Partner"),("Kevin Russell","Global Head of Multi-Asset Arbitrage"),
   ("Bill Wappler","Partner & Global Director of Research"),("Alex Lurye","Partner & Chief Risk Officer")]),
 ("Baron Capital","New York, NY","baroncapitalgroup.com",[
   ("Ron Baron","Founder, CEO & Portfolio Manager"),("David Baron","Co-President & Portfolio Manager"),
   ("Michael Baron","Co-President & Portfolio Manager"),("Cliff Greenberg","Co-CIO, SVP & Portfolio Manager"),
   ("Andrew Peck","Co-CIO, SVP & Portfolio Manager"),("Michael Lippert","VP, Portfolio Manager & Head of Technology Research"),
   ("Alex Umansky","VP & Portfolio Manager")]),
 ("Boothbay Fund Management","New York, NY","bbaymgmt.com",[("Ari Glass","Founder, CEO & CIO")]),
 ("Cadian Capital","New York, NY",None,[("Eric Bannasch","Founder, CEO & Portfolio Manager")]),
 ("Catalyst Capital Advisors","Rye, NY","catalystmf.com",[
   ("David Miller","Senior Portfolio Manager & Co-Founder"),("Jerry Szilagyi","CEO & Co-Founder")]),
 ("Caxton Associates","New York, NY","caxton.com",[("Andrew Law","Chairman & CEO (CIO)")]),
 ("Chilton Investment Company","Stamford, CT",None,[
   ("Richard L. Chilton, Jr.","Founder, Chairman & CEO"),("Jennifer L. Foster","Co-CIO – Equities"),
   ("Nicholas Frelinghuysen","Co-CIO – Equities"),("Wiley Wilson","Portfolio Manager – Equities")]),
 ("ClearBridge Investments","New York, NY","clearbridge.com",[
   ("Terrence Murphy","CEO"),("Scott Glasser","CIO, Managing Director & Portfolio Manager"),
   ("Aram Green","Managing Director & Portfolio Manager"),("Margaret Vitrano","Portfolio Manager"),
   ("Peter Bourbeau","Portfolio Manager"),("Sam Peters","Portfolio Manager (Value Strategy)")]),
 ("Coatue Management","New York, NY","coatue.com",[
   ("Philippe Laffont","Founder & Portfolio Manager"),("Thomas Laffont","Co-Founder & CIO of Privates")]),
 ("Cobalt Capital","New York, NY",None,[("Wayne Cooperman","President (Founder & Portfolio Manager)")]),
 ("Cramer Rosenthal McGlynn","New York, NY","crmllc.com",[
   ("Brian M. Harvey","Co-CEO, CIO & Managing Member"),("Kevin M. Chin","Portfolio Manager"),
   ("Robert Maina","Portfolio Manager"),("Mimi B. Morris","Portfolio Manager"),
   ("Jeffrey Yanover","Portfolio Manager"),("Andrew Shinn","Research Analyst"),("Tristan R. Newkirk","Research Analyst")]),
 ("Nuveen","New York, NY","nuveen.com",[("Saira Malik","Head of Nuveen Equities and Fixed Income, CIO")]),
 ("D.E. Shaw","New York, NY","deshaw.com",[
   ("Anne Dinning","Managing Director; Chair of the Executive Committee"),
   ("David E. Shaw","Founder and Chief Scientist"),("Eddie Fishman","COO; Executive Committee"),
   ("Max Stone","Executive Committee"),("Alexis Halaby","Head of Investor Relations; Executive Committee")]),
 ("Edgewood Management","New York, NY","edgewood.com",[
   ("Alan Breed","Co-President & Portfolio Manager"),("Larry Creel","Co-President & Portfolio Manager"),
   ("Kevin Seth","Partner & Portfolio Manager"),("Scott Edwardson","Partner & Portfolio Manager"),
   ("Will Broadbent","Partner & Portfolio Manager")]),
 ("Empire Capital Management","Westport, CT",None,[
   ("Scott A. Fine","Co-Founder and Managing Member"),("Peter J. Richards","Co-Founder and Managing Member")]),
 ("Epoch Investment Partners","New York, NY","eipny.com",[
   ("William W. Priest","Managing Director, CIO & Portfolio Manager"),
   ("Michael A. Welhoelter","Managing Director, Co-CIO, Head of Quantitative Research & Risk"),
   ("Steven D. Bleiberg","Managing Director, Portfolio Manager"),
   ("Kera Van Valen","Managing Director, Portfolio Manager & Research Analyst"),
   ("David J. Siino","Managing Director, Portfolio Manager & Senior Research Analyst")]),
 ("Federated Hermes (Global Equities)","New York, NY","federatedhermes.com",[
   ("Stephen Auth","CIO, Global Equities (retiring)"),
   ("Steve Chiavarone","Deputy CIO Global Equities / Head of Multi-Asset (CIO Global Equities 9/1/2026)")]),
]
tot=0
for firm,city,domain,people in E:
    ppl=[{"name":clean(html.unescape(n)),"title":html.unescape(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} (target-list verify, Jul 2026)", people=ppl)
    tot+=res["added"]
    print(f"{firm[:32]:32s} | {city[:18]:18s} | +{res['added']} new, {res['merged']} merged")
print(f"\nNY-A: +{tot} new across {len(E)} firms")
