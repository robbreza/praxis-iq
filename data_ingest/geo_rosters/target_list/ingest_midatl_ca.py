"""Ingest Mid-Atlantic/South + Canada verified firms WITH rosters. Dups already in DB skipped
(abrdn Inc., CI Global, 1832/Scotia, TD). Brown Investment Advisory -> merge into existing 'Brown
Advisory'. No-roster verified skipped (1838, Afton, AGF, Barometer, IGM, Polar). Rejected excluded."""
import html
from core.security import load_environment; load_environment()
from core import roster
_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","cim","frm","jd","mba","ii","iii","iv","jr","sr"}
def clean(n):
    p=[x.strip() for x in n.split(",")]
    return ", ".join([p[0]]+[x for x in p[1:] if x.lower().strip(". ") not in _CREDS]).strip(" ,")
E=[
 # US Mid-Atlantic/South
 ("Banbury Partners","Charlotte, NC",None,[
   ("Clay Baker Burleson","Managing Member"),("Edward Scott","Managing Member")]),
 ("BlueCrest Capital Management","London, UK","bluecrestcapital.com",[("Michael Platt","Founder & CEO")]),
 ("Brown Advisory","Baltimore, MD","brownadvisory.com",[("Michael D. Hankin","President & CEO")]),
 ("Chief Cornerstone Capital","Ambler, PA",None,[("Charles Purcell","Founder/CIO")]),
 ("Ewing Asset Management","Charlotte, NC",None,[
   ("Robert Allen Hewett","President/Chief Investment Officer"),("David W. Jackson","Principal")]),
 ("Masters Capital Management","Atlanta, GA","masterscapital.com",[("Michael W. Masters","Managing Member")]),
 ("Roundview Capital","Princeton, NJ","roundviewcapital.com",[
   ("Matthew D. Wallack","Chief Investment Officer"),("Stephen K. Shueh","Managing Partner"),
   ("Howard T. Alter","Managing Partner"),("Andrew S. Lieu","Partner"),("Nicholas A. Shelton","Principal")]),
 ("TFS Capital","West Chester, PA","tfscapital.com",[("Richard J. Gates","Member, Co-Portfolio Manager")]),
 ("Tower Bridge Advisors","West Conshohocken, PA","towerbridgeadvisors.com",[
   ("James M. Meyer","Chairman of the Board"),("Christopher E. Gildea","CEO, Senior Portfolio Manager"),
   ("Christopher M. Crooks","Chief Investment Officer, Senior Portfolio Manager"),
   ("Jeffrey Kachel","Principal, Portfolio Manager, CFO"),("Daniel P. Rodan","Senior Portfolio Manager"),
   ("Michael J. Adams","Senior Portfolio Manager"),("Shawn M. Gallagher","Senior Portfolio Manager"),
   ("Chad M. Imgrund","Sr. Research Analyst"),("Tom Blair","Qualified Plan Advisor, Portfolio Manager")]),
 # Canada
 ("BloombergSen Investment Partners","Toronto","bloombergsen.com",[
   ("Jonathan Bloomberg","Chief Executive Officer"),("Sanjay Sen","President and Chief Investment Officer"),
   ("Lawrence S. Bloomberg","Chairman of the Board of Directors"),("David Spencer","Vice President, Investor Relations")]),
 ("Delaney Capital Management","Toronto","delaneycapital.com",[("Kiki Delaney","Founder")]),
 ("Jarislowsky Fraser","Montreal","jflglobal.com",[
   ("Charles Nadim","Head of Research and Portfolio Manager, Canadian Equities"),
   ("Kelly Patrick","Head of Equities & Portfolio Manager, International and Global Equities"),
   ("Marc-Andre Gaudreau","VP & Senior Portfolio Manager, Specialized Credit; Head of JF Fixed Income"),
   ("Jeff Horbal","Lead, Consultant Relations & Senior Institutional Portfolio Manager")]),
 ("Pembroke Management","Montreal","pml.ca",[("Stephanie Pantaleo","Partner")]),
 ("Ridgewood Capital Asset Management","Toronto","ridgewoodcapital.ca",[
   ("John H. Simpson","Founding Partner and Managing Director"),("Paul W. Meyer","Founding Partner and Managing Director"),
   ("Mark J. Carpani","Partner and Senior Vice President, Fixed Income"),("James McAughey","Vice President, Equities"),
   ("Jennifer Zabanah","Vice President, Equities"),("Eddie Wong","Vice President, Fixed Income"),
   ("Robert Cruickshank","Vice President")]),
 ("Webb Asset Management","Sausalito, CA",None,[("Derek H. Webb","Founder & President")]),
]
tot=0
for firm,city,domain,people in E:
    country="Canada" if city in ("Toronto","Montreal") else ("UK" if "London" in city else "US")
    ppl=[{"name":clean(html.unescape(n)),"title":html.unescape(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country=country, source_note=f"{firm} (target-list verify, Jul 2026)", people=ppl)
    tot+=res["added"]; print(f"{firm[:32]:32s} | {city[:14]:14s} | +{res['added']} new, {res['merged']} merged")
print(f"\nMID-ATL/SOUTH + CANADA: +{tot} new across {len(E)} firms")
