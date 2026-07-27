"""Ingest Mid West verified firms WITH confirmed rosters (target-list build-out). Agent's web budget
ran out, so verified-no-roster (Anchor Bolt, Carnegie, Copia, Heitman, Nationwide, Parkwest,
Sheffield, Shine) and UNCONFIRMED rejects (Acrospire, Blue Rock, Brazos, Cloverdale, Continental,
IronBridge) are held for a re-verify pass. Confirmed-dead (Denver Inv->SBH, Woodway->Westwood,
Peak6, Fosun, Harrison Street public arm, Gerald Ray, AMP) excluded."""
import html
from core.security import load_environment; load_environment()
from core import roster
def unesc(s): return html.unescape(s)
E=[
 ("Acuta Capital Partners","Larkspur, CA","acutacapital.com",[("Anupam Dalal","Chief Investment Officer")]),
 ("Chickasaw Capital Management","Memphis, TN","chickasawcap.com",[
   ("Geoffrey P. Mavar","Principal & Managing Director"),("Matthew G. Mead","Principal & Managing Director")]),
 ("Crystal Rock Capital","Bannockburn, IL","crystalrockcap.com",[
   ("Jay Howard Freedman","Managing Member, Chief Compliance Officer")]),
 ("GEM Realty Capital","Chicago, IL","gemrc.com",[
   ("Michael Elrad","Founding Partner | Executive Chairman - Public Markets"),
   ("Brad Caldwell","Co-CIO, Public Markets"),("Michael Geller","Co-CIO, Public Markets"),
   ("Jeremy Franklin","Senior Managing Director, Investments & Strategy"),
   ("Emily Huang","Vice President, Investments"),("R.J. Thauer","Associate, Investments")]),
 ("Magnetar Capital","Evanston, IL","magnetar.com",[("Alec N. Litowitz","Chairman & CEO")]),
 ("Oak Ridge Investments","Chicago, IL","oakridgeinvest.com",[("David M. Klaskin","Chairman & CIO")]),
 ("Oberweis Asset Management","Lisle, IL","oberweis.net",[
   ("James W. Oberweis","President"),("Kenneth Farsalas","Director of Domestic Equities, Portfolio Manager")]),
 ("Pentwater Capital Management","Naples, FL","pentwater.com",[("Matthew C. Halbower","CEO & CIO")]),
 ("Skyline Asset Management","Chicago, IL","skylinelp.com",[
   ("Michael Maloney","Partner & Portfolio Manager"),("Mark N. Odegard","Partner & Portfolio Manager")]),
 ("venBio","San Francisco, CA","venbio.com",[
   ("Richard Gaster","Managing Partner"),("Corey Goodman","Managing Partner"),("Aaron Royston","Managing Partner")]),
]
tot=0
for firm,city,domain,people in E:
    ppl=[{"name":unesc(n),"title":unesc(t)} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} (target-list verify, Jul 2026)", people=ppl)
    tot+=res["added"]; print(f"{firm[:30]:30s} | {city[:16]:16s} | +{res['added']} new, {res['merged']} merged")
print(f"\nMID WEST: +{tot} new across {len(E)} firms")
