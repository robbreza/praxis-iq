"""Ingest NY-B verified firms WITH rosters. Madera (no roster) skipped. Rejected excluded (George
Weiss bankrupt, Pioneer Path->Citadel, Principled/Ridgecrest/Searock/Sursum/Thrax/TriOaks dormant,
QS Investors->Franklin, Teton->Gabelli, US Trust->BofA, Ziff split). Corrected cities: Jacobs Levy/
Palisade=NJ, Paloma/PAW/Tudor=CT, Nishkama=PR, Weiss=Boston."""
import html
from core.security import load_environment; load_environment()
from core import roster
_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","frm","jd","mba","ii","iii","iv"}
def clean(n):
    p=[x.strip() for x in n.split(",")]
    return ", ".join([p[0]]+[x for x in p[1:] if x.lower().strip(". ") not in _CREDS]).strip(" ,")
E=[
 ("Glenview Capital","New York, NY","glenview.com",[("Larry Robbins","Founder, CEO and Portfolio Manager")]),
 ("Highbridge Capital","New York, NY","highbridge.com",[("Mark Vanacore","Managing Director, Portfolio Manager (Energy, Equity Derivatives)")]),
 ("Voya Investment Management","New York, NY","voya.com",[("James Lydotes","Chief Investment Officer, Equities")]),
 ("Jacobs Levy Equity Management","Florham Park, NJ","jlem.com",[
   ("Bruce I. Jacobs","Principal, Co-Founder and Co-CIO"),("Kenneth N. Levy","Principal, Co-Founder and Co-CIO")]),
 ("Jennison Associates","New York, NY","jennison.com",[
   ("Blair A. Boyer","Managing Director, Co-Head of Large Cap Growth Equity, Portfolio Manager"),
   ("Natasha Kuhlkin","Managing Director, Co-Head of Growth Equity, Portfolio Manager"),
   ("Michael Del Balso","Managing Director, Large Cap Growth Portfolio Manager"),
   ("Jason M. Swiatek","Managing Director, Head of Small Cap Equity")]),
 ("J.P. Morgan Asset Management","New York, NY","jpmorgan.com",[("Hamilton Reiner","CIO of Core Equity and Head of U.S. Equity Derivatives")]),
 ("Levin Capital Strategies","New York, NY",None,[("John A. Levin","CEO & Senior Portfolio Manager")]),
 ("Long Oar Global Investors","New York, NY",None,[
   ("Colin Hall","Co-Founder / Portfolio Manager"),("James Davidson","Managing Member & CCO"),("Michael A. Cinque","CFO")]),
 ("MapleLane Capital","New York, NY",None,[("Leon Shaulov","Founder & Managing Partner"),("Robert S. Crespi","Managing Member / Partner")]),
 ("Newbrook Capital Advisors","New York, NY",None,[("Robert Boucai","Founder & CIO"),("Christopher Reed","CFO")]),
 ("Nishkama Capital","Dorado, PR","nishkama.com",[("Ravee Mehta","Founder & Portfolio Manager")]),
 ("BNY Investments","New York, NY","bny.com",[
   ("David France","Primary Portfolio Manager (index equity)"),("Todd Frysinger","Primary Portfolio Manager (index equity)"),
   ("Vlasta Sheremeta","Primary Portfolio Manager (index equity)"),("Michael Stoll","Primary Portfolio Manager (index equity)")]),
 ("Omega Family Office","New York, NY",None,[("Leon G. Cooperman","Chairman & CEO")]),
 ("Owl Creek Asset Management","New York, NY",None,[
   ("Jeffrey A. Altman","Founder & Chief Portfolio Manager"),("Daniel Krueger","Portfolio Manager"),("Daniel Sapadin","COO")]),
 ("Palisade Capital Management","Fort Lee, NJ","palisadecapital.com",[
   ("Alison Berman","Managing Partner, President & CEO"),("Dan Veru","Senior Partner & CIO")]),
 ("Paloma Partners","Greenwich, CT","paloma.com",[
   ("S. Donald Sussman","Founder & Chairman (CIO of flagship fund)"),("Ravi Singh","CEO"),("Mike DeAddio","COO")]),
 ("PAW Partners","Greenwich, CT","pawpartners.com",[("Peter A. Wright","General Partner, CIO & Senior Portfolio Manager")]),
 ("Phoenix Investment Adviser","New York, NY","phoenixinvadv.com",[("Jeffrey L. Peskind","Founder & CIO")]),
 ("Plural Investing","New York, NY","pluralinvesting.com",[("Chris Waller","Founder & Portfolio Manager")]),
 ("Spark Investment Management","New York, NY",None,[("Peter Laventhol","Managing Member & Majority Owner")]),
 ("Springbok Capital Management","New York, NY",None,[("Gavin Saitowitz","Founding Partner"),("Cisco Del Valle","Founding Partner")]),
 ("SRS Investment Management","New York, NY",None,[("Karthik Sarma","Founder & Managing Partner")]),
 ("Tiger Management","New York, NY",None,[("Alexander Robertson","President")]),
 ("TimesSquare Capital Management","New York, NY",None,[("Grant R. Babyak","CEO & Portfolio Manager")]),
 ("Trellus Management","New York, NY",None,[("Adam Usdan","Founder & Portfolio Manager")]),
 ("Tremblant Capital","New York, NY",None,[("Brett Barakett","Founder & CIO")]),
 ("Tudor Investment","Stamford, CT","tudor.com",[("Paul Tudor Jones II","Founder & CIO")]),
 ("UBS O'Connor","New York, NY",None,[
   ("Kevin Russell","CIO, UBS O'Connor"),("Bernard Ahkong","CIO, O'Connor Global Multi-Strategy Alpha")]),
 ("Weiss Asset Management","Boston, MA","weissasset.com",[("Andrew Weiss","Founder & CEO")]),
]
tot=0
for firm,city,domain,people in E:
    ppl=[{"name":clean(html.unescape(n)),"title":html.unescape(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} (target-list verify, Jul 2026)", people=ppl)
    tot+=res["added"]; print(f"{firm[:30]:30s} | {city[:16]:16s} | +{res['added']} new, {res['merged']} merged")
print(f"\nNY-B: +{tot} new across {len(E)} firms")
