"""Ingest Boston verified firms WITH rosters. Verified-no-roster skipped for re-verify (Brookside/
Bain Public Equity, John Hancock, LMCG, Pangaea, Putnam). Rejected excluded (Babson->Barings,
Independence/McStay defunct, Mellon Growth->BNY, Pioneer->Victory, Vinik/WPG/Whalerock-Boston/
Teton-Boston unverifiable/merged, Constitution=PE)."""
import html
from core.security import load_environment; load_environment()
from core import roster
_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","ctfa","cim","frm","jd","md","mba","ii","iii","iv","jr","sr"}
def clean(n):
    p=[x.strip() for x in n.split(",")]
    return ", ".join([p[0]]+[x for x in p[1:] if x.lower().strip(". ") not in _CREDS]).strip(" ,")
E=[
 ("Acadian Asset Management","Boston, MA","acadian-asset.com",[
   ("Brendan O. Bradley","Chief Investment Officer"),("Ryan Taliaferro","SVP, Director of Investment Strategies"),
   ("Owen Lamont","SVP, Portfolio Manager (Global Equity Research)"),("Javier Alcazar","SVP, Portfolio Manager (Global Equity Research)")]),
 ("Arrowstreet Capital","Boston, MA","arrowstreetcapital.com",[
   ("Bruce Clarke","Chairman (co-founder)"),("John Y. Campbell","Partner, Co-Head of Research (co-founder)"),
   ("Manolis Liodakis","Portfolio Manager")]),
 ("Barings","Charlotte, NC","barings.com",[("Mike Freno","Chairman & Chief Executive Officer")]),
 ("Frontier Capital Management","Boston, MA","frontiercap.com",[
   ("James A. Colgan","Partner | Portfolio Manager"),("Christopher J. Scarpa","Partner | Portfolio Manager"),
   ("Peter G. Kuechle","Partner | Portfolio Manager"),("Andrew B. Bennett","Partner | Portfolio Manager"),
   ("Jonathan M. Levin","Partner | Director of Research | Research Analyst"),("Rushan Jiang","Partner | Portfolio Manager"),
   ("Ravi Dabas","Partner | Portfolio Manager"),("Nathan A. Hayman","Partner | Portfolio Manager"),
   ("Kristin S. King","Partner | Portfolio Manager and Research Analyst"),("Emmanuel Franjul","Partner | Portfolio Manager"),
   ("Uri L. Nurko","Partner | Portfolio Manager and Research Analyst")]),
 ("Loring, Wolcott & Coolidge","Boston, MA","lwcotrust.com",[
   ("Thomas R. Appleton","Trustee"),("David Boit","Trustee"),("David Cuetos","Trustee"),("Wendy Holding","Trustee"),
   ("Nushin Kormi","Trustee"),("Amory L. Logan","Trustee"),("William B. Perkins","Trustee"),
   ("Gilbert M. Roddy","Trustee"),("Simran Su","Trustee")]),
 ("MFS Investment Management","Boston, MA","mfs.com",[
   ("Ted M. Maloney","Chief Executive Officer"),("Alison O'Neill","Chief Investment Officer"),
   ("David A. Falco","Co-CIO of Equity"),("Matthew Scholder","Co-CIO of Equity"),("Jeanine L. Thomson","Co-CIO of Equity"),
   ("Pilar Gomez-Bravo","Co-CIO of Fixed Income"),("Alexander M. Mackey","Co-CIO of Fixed Income")]),
 ("PanAgora Asset Management","Boston, MA","panagora.com",[
   ("Bryan D. Belton","President and Chief Executive Officer"),("George D. Mussalli","Global Chief Investment Officer"),
   ("Edward Qian","Chief Investment Officer, Multi Asset Investments"),("Jaime H. Lee","Managing Director, Head of Dynamic Equity Investments"),
   ("Richard Tan","Managing Director, Head of Stock Selector Equity Investments"),("Eric H. Sorensen","Vice Chair")]),
 ("RhumbLine Advisers","Boston, MA","rhumbline.com",[
   ("Alexander Ryer","Chief Investment Officer"),("Jeffrey Kusmierz","Senior Portfolio Manager"),
   ("Julie Carman Lee","Senior Portfolio Manager"),("Antonio Ballestas","Portfolio Manager"),("Andrew Zagarri","Portfolio Manager")]),
 ("Boston Partners","Boston, MA","bostonpartners.com",[
   ("Joseph F. Feeney","Chief Executive Officer and Co-Chief Investment Officer"),("Joshua White","Portfolio Manager and Co-Chief Investment Officer"),
   ("Todd Knightly","Director of Fundamental Research"),("Duilio R. Ramallo","Portfolio Manager (Premium Equity)"),
   ("Steven L. Pollack","Portfolio Manager (Mid Cap Value)"),("George Gumpert","Portfolio Manager (Small/SMID Cap Value)"),
   ("Christopher K. Hart","Portfolio Manager"),("David T. Cohen","Portfolio Manager")]),
 ("Telemark Asset Management","Boston, MA",None,[
   ("Colin McNay","President (majority owner)"),("Brian C. Miley","Chief Financial Officer / Chief Compliance Officer")]),
 ("Westfield Capital Management","Boston, MA","westfieldcapital.com",[
   ("Will Muggia","President, CEO & Chief Investment Officer"),("Rich Lee","Managing Partner, Chief Investment Officer"),
   ("John Montgomery","Managing Partner, Portfolio Strategist & COO"),("Rob Flores","Managing Partner, Director of Disruptive Technology Research")]),
]
tot=0
for firm,city,domain,people in E:
    ppl=[{"name":clean(html.unescape(n)),"title":html.unescape(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} (target-list verify, Jul 2026)", people=ppl)
    tot+=res["added"]; print(f"{firm[:30]:30s} | {city[:14]:14s} | +{res['added']} new, {res['merged']} merged")
print(f"\nBOSTON: +{tot} new across {len(E)} firms")
