"""Ingest batch-A no-roster firms now rostered. Rejected: Brompton Cross (no trace), Copia (dormant).
FLAGS: Camelot resolved to Camelot Capital Partners (Laguna Beach CA) and Parkwest to Park West Asset
Mgmt (Mill Valley CA) — ambiguous vs the user's NY framing; verify."""
import html
from core.security import load_environment; load_environment()
from core import roster
_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","cim","frm","jd","md","mba","ii","iii","iv","jr","sr"}
def clean(n):
    p=[x.strip() for x in n.split(",")]
    return ", ".join([p[0]]+[x for x in p[1:] if x.lower().strip(". ") not in _CREDS]).strip(" ,")
E=[
 ("1798 Alternatives (Lombard Odier)","New York, NY","lombardodier.com",[
   ("Christophe Khaw","Chief Investment Officer, 1798 Alternatives"),
   ("Raj Dave","Portfolio Manager (event-driven / special situations)"),
   ("Jean-Pascal Porcherot","CEO of 1798 Alternatives; Managing Partner & Co-Head, LOIM")]),
 ("Camelot Capital Partners","Laguna Beach, CA",None,[("William Barker","Managing Partner, CIO & Portfolio Manager")]),
 ("Anchor Bolt Capital","Chicago, IL",None,[("Robert Polak","Founder, CEO & Chief Investment Officer")]),
 ("Carnegie Investment Counsel","Pepper Pike, OH","carnegieinvest.com",[
   ("Ben Connard","Chief Investment Officer"),("Christopher Carey","Portfolio Manager"),("Richard Alt","Chief Executive Officer")]),
 ("Heitman","Chicago, IL","heitman.com",[
   ("Charles Harbin","Managing Director, Co-Head & Portfolio Manager, Public Real Estate Securities"),
   ("Jeff Yurk","Managing Director, Co-Head & Portfolio Manager, Public Real Estate Securities")]),
 ("Nationwide Fund Advisors","Columbus, OH","nationwide.com",[
   ("Christopher Graham","Chief Investment Officer / Head of Investment Strategies, Nationwide Funds"),
   ("Keith Robinette","Portfolio Manager (Asset Strategies, co-PM)"),("Andrew Urban","Portfolio Manager (Asset Strategies, co-PM)")]),
 ("Park West Asset Management","Mill Valley, CA",None,[("Peter S. Park","Founder, Managing Member & Portfolio Manager")]),
 ("Sheffield Asset Management","Chicago, IL","sheffieldmgmt.com",[
   ("Brian J. Feltzin","Managing Partner & Portfolio Manager"),("William Rice","Analyst")]),
 ("Shine Investment Advisory Services","Greenwood Village, CO",None,[("Judith Shine","President & Founder")]),
 ("Madera Technology Partners","New York, NY","maderatp.com",[("Kristopher Drankiewicz","Founder & CEO (Portfolio Manager)")]),
]
tot=0
for firm,city,domain,people in E:
    ppl=[{"name":clean(html.unescape(n)),"title":html.unescape(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} (no-roster fill, Jul 2026)", people=ppl)
    tot+=res["added"]; print(f"{firm[:34]:34s} | {city[:16]:16s} | +{res['added']} new, {res['merged']} merged")
print(f"\nBATCH A: +{tot} new across {len(E)} firms")
