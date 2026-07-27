"""Ingest West Coast verified firms WITH rosters (target-list build-out). 'Cramer Rosenthal (West)'
skipped (duplicate of the NY firm already ingested). Rejected (defunct/wrong-type/unconfirmable)
excluded: Analytic, Big Basin, DB ATS, Harpoon, Ivory, Jafra, Montibus, Oliver Press, Owenoke,
Ozumo, Pacific Grove, Platte River, Preservation, PresPoint, QCM, Rainier, SFNT, Tech Oppty, Tribeca."""
import html
from core.security import load_environment; load_environment()
from core import roster
_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","frm","jd","mba","cia","ii","iii","iv"}
def clean(n):
    p=[x.strip() for x in n.split(",")]
    return ", ".join([p[0]]+[x for x in p[1:] if x.lower().strip(". ") not in _CREDS]).strip(" ,")
E=[
 ("Ascend Capital (Fairbairn Family Office)","San Francisco, CA",None,[("Malcolm P. Fairbairn","Founder & Chief Investment Officer")]),
 ("Crosslink Capital","San Francisco, CA","crosslinkcapital.com",[
   ("Michael Stark","Partner and Founder"),("David Silverman","Partner"),("Eric Chin","Partner and Alpha Founder"),
   ("Matt Bigge","Partner"),("Phil Boyer","Partner"),("Gabby Contro","Partner")]),
 ("Cutler Capital Management","Worcester, MA","cutlercapital.com",[
   ("Geoffrey Dancey","Managing Partner & Portfolio Manager"),("Melvin S. Cutler","Founder & Portfolio Manager"),
   ("Mitko Botev","Portfolio Manager & Analyst"),("Toni Molinari","Research Analyst")]),
 ("Falcon Point Capital","San Francisco, CA","fptcap.com",[
   ("James A. Bitzer","Senior Managing Director, Chief Investment Officer"),
   ("Michael J. Mahoney","Senior Managing Director, Portfolio Manager, CCO")]),
 ("First Pacific Advisors","Los Angeles, CA","fpa.com",[
   ("Steven Romick","Managing Partner, Portfolio Manager"),("Mark Landecker","Partner, Portfolio Manager"),
   ("Brian A. Selmo","Partner, Portfolio Manager"),("Abhijeet Patwardhan","Partner, Portfolio Manager")]),
 ("PIMCO","Newport Beach, CA","pimco.com",[
   ("Daniel J. Ivascyn","Group Chief Investment Officer"),("Erin Browne","Managing Director, Portfolio Manager")]),
 ("Provident Investment Management","Novi, MI","investprovident.com",[
   ("James Skubik","Chief Investment Officer, Senior Portfolio Manager"),("Dan Boyle","Chairman, Senior Portfolio Manager"),
   ("Miles Putnam","President, Senior Portfolio Manager"),("Scott Horsburgh","Senior Consultant")]),
 ("Rice Hall James & Associates","San Diego, CA","ricehalljames.com",[
   ("Daniel S. Sargen","CIO, PM/Analyst"),("Lou M. Holtz","CIO & PM/Analyst"),("Gary S. Rice","Portfolio Manager"),
   ("George I. Kruntchev","PM/Analyst"),("Reed M. Wirick","PM/Analyst"),("Timothy A. Todaro","PM/Analyst"),
   ("Yossi Lipsker","PM/Analyst")]),
 ("Tenzing Global Investors","San Francisco, CA",None,[
   ("Chetan Kapoor","Managing Member & Chief Investment Officer"),("Mark Simmons","CFO & CCO")]),
]
tot=0
for firm,city,domain,people in E:
    ppl=[{"name":clean(html.unescape(n)),"title":html.unescape(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} (target-list verify, Jul 2026)", people=ppl)
    tot+=res["added"]; print(f"{firm[:34]:34s} | {city[:16]:16s} | +{res['added']} new, {res['merged']} merged")
print(f"\nWEST COAST: +{tot} new across {len(E)} firms")
