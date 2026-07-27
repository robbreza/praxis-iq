"""Ingest batch-B no-roster firms now rostered. Pangaea rejected (=PanAgora, already have);
1838 still empty. AGF/Barometer/Mackenzie(IGM)/Polar=Canada; Afton/Bain/JHIM/LMCG/Putnam=US."""
import html
from core.security import load_environment; load_environment()
from core import roster
_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","cim","ctfa","frm","jd","md","mba","ii","iii","iv","jr","sr"}
def clean(n):
    p=[x.strip() for x in n.split(",")]
    return ", ".join([p[0]]+[x for x in p[1:] if x.lower().strip(". ") not in _CREDS]).strip(" ,")
E=[
 ("Afton Capital Management","Charlotte, NC","US","aftoncapital.com",[("Coy Monk","Managing Member / Portfolio Manager")]),
 ("AGF Investments","Toronto","Canada","agf.com",[
   ("Stephen Way","SVP and Head of Global & Emerging Markets Equities"),
   ("David Stonehouse","SVP and Head of North American and Specialty Investments"),
   ("Regina Chi","VP & Portfolio Manager (Emerging Markets)"),
   ("Mike Archibald","VP & Portfolio Manager (U.S., Global and Canadian Growth Equity)"),
   ("Auritro Kundu","VP & Portfolio Manager (U.S., Global and Canadian Growth Equity)"),
   ("Bill DeRoche","SVP, Head of Quantitative Investing"),
   ("Richard McGrath","Executive Director and Head of Investments, AGF International Advisors")]),
 ("Barometer Capital Management","Toronto","Canada","barometercapital.ca",[
   ("David Burrows","Chairman, Chief Investment Officer"),("Amit Joshi","Portfolio Manager"),
   ("Brian MacNicol","Portfolio Manager"),("James Callahan","Portfolio Manager"),
   ("Diana Avigdor","Head of Trading"),("Geoffrey Spidle","President (Partner)"),("Peter McCarthy","Managing Partner")]),
 ("Mackenzie Investments","Toronto","Canada","mackenzieinvestments.com",[
   ("Lesley Marks","SVP, Investment Management; Chief Investment Officer, Equities"),
   ("David Arpin","Portfolio Manager & Co-Lead, Mackenzie Bluewater Team"),
   ("Shah Khan","SVP, Portfolio Manager & Co-Lead, Mackenzie Bluewater Team")]),
 ("Polar Asset Management Partners","Toronto","Canada","polaramp.com",[
   ("Paul Sabourin","Chairman & Chief Investment Officer (Co-Founder; Lead PM, Multi-Strategy)"),
   ("Bill Peckford","Deputy CIO and Head of Equities"),("Mike Beaton","Deputy CIO and Head of Portfolio Construction"),
   ("Jason Cope","Head of Global Fixed Income and Rates"),("Greg Lemaich","President and Chief Executive Officer")]),
 ("Bain Capital Public Equity","Boston, MA","US","baincapital.com",[
   ("Dewey Awad","Managing Director (Head of Bain Capital Public Equity)"),("Andrew S. Viens","Managing Director"),
   ("Joshua Ross","Managing Director"),("Karl Spielmann","Managing Director"),("Michael Treisman","Managing Director")]),
 ("John Hancock Investment Management","Boston, MA","US","jhinvestments.com",[
   ("Colin Purdie","Global Chief Investment Officer, Public Markets (Manulife)"),
   ("Kristie Feinberg","President & CEO, John Hancock Investment Management")]),
 ("LMCG Investments","Boston, MA","US","lmcg.com",[
   ("David Weeks","Managing Partner, Chief Investment Officer, Serenitas Investment Team"),
   ("Andreas Eckner","Partner, Portfolio Manager, Serenitas Investment Team"),
   ("Guillaume Horel","Partner, Portfolio Manager, Serenitas Investment Team"),
   ("Ajit Kumar","Partner, Portfolio Manager, Serenitas Investment Team"),
   ("Edwin Tsui","Partner, Portfolio Manager, Serenitas Investment Team"),
   ("Matthew Guleserian","Partner, Portfolio Manager, Fixed Income Investment Team"),
   ("Lars Cianciolo","Investment Analyst, Equity Investment Team"),
   ("Anjali Papadopoulos","Investment Analyst, Equity Investment Team")]),
 ("Putnam Investments","Boston, MA","US","putnam.com",[
   ("Shep Perkins","Chief Investment Officer, Equities"),("Kathryn B. Lakin","Director of Equity Research"),
   ("Katherine Collins","Head of Sustainable Investing"),("Marc Lindquist","Head of Equity Trading")]),
]
tot=0
for firm,city,country,domain,people in E:
    ppl=[{"name":clean(html.unescape(n)),"title":html.unescape(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country=country, source_note=f"{firm} (no-roster fill, Jul 2026)", people=ppl)
    tot+=res["added"]; print(f"{firm[:32]:32s} | {city[:12]:12s} | +{res['added']} new, {res['merged']} merged")
print(f"\nBATCH B: +{tot} new across {len(E)} firms")
