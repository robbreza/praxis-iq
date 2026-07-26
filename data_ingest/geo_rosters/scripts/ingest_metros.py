"""Ingest verified Chicago + Milwaukee + Salt Lake active-equity shops (Jul 2026 metro sweep).
Artisan Partners is split into its real per-team office cities (Milwaukee/SF/Atlanta/Boston/Chicago/
NY/Denver). CIK left None -> resolved by the scoped currency pass afterward. Names cleaned of creds."""
import re
from core.security import load_environment; load_environment()
from core import roster

_CREDS={"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","frm","jd","mba","msf","bfa","cic","ii","iii","iv"}
def clean(name):
    parts=[p.strip() for p in name.split(",")]
    kept=[parts[0]]+[p for p in parts[1:] if p.lower().strip(". ") not in _CREDS]
    return ", ".join([k for k in kept if k]).strip(" ,")

# (firm, city, domain, [(name,title)])
ENTRIES = [
 # ---------- CHICAGO ----------
 ("Ariel Investments","Chicago, IL","arielinvestments.com",[
   ("John W. Rogers, Jr.","Founder, Chairman, Co-CEO & Chief Investment Officer"),
   ("Kenneth E. Kuhrt","EVP, Co-CIO Domestic Equities & Portfolio Manager"),
   ("Charles K. Bobrinskoy","Vice Chairman, Head of Investment Group & Portfolio Manager"),
   ("Henry S. Mallari-D'Auria","EVP, CIO Global & Emerging Markets Equities")]),
 ("Harris Associates","Chicago, IL","harrisassoc.com",[
   ("William C. Nygren","Partner, Portfolio Manager & Co-CIO U.S."),
   ("Alex Fitch","Partner, Portfolio Manager, Director of U.S. Research & Co-CIO U.S."),
   ("David G. Herro","Partner, Portfolio Manager & Co-CIO International Equities"),
   ("Tony Coniaris","Partner, Chairman, Portfolio Manager & Co-CIO International Equities"),
   ("Robert F. Bierig","Partner, Deputy Chairman, Portfolio Manager & U.S. Investment Analyst"),
   ("Justin D. Hance","Partner, Portfolio Manager & Director of International Research"),
   ("Colin Hudson","Partner, Portfolio Manager & U.S. Equity Investment Analyst"),
   ("Michael A. Nicolas","Partner, Portfolio Manager & U.S. Investment Analyst"),
   ("John A. Sitarz","Partner, Portfolio Manager & U.S. Investment Analyst"),
   ("Eric Liu","Partner, Portfolio Manager & Sr. International Investment Analyst"),
   ("Jeremy G. Thames","Partner, Associate Director of U.S. Research & U.S. Investment Analyst"),
   ("Alex A. Frey","Partner & Associate Director of International Research")]),
 ("LSV Asset Management","Chicago, IL","lsvasset.com",[
   ("Josef Lakonishok","CEO, CIO & Founding Partner"),
   ("Puneet Mansharamani","Portfolio Manager, Senior Quantitative Analyst & Partner"),
   ("Menno Vermeulen","Portfolio Manager, Senior Quantitative Analyst & Partner"),
   ("Guy Lakonishok","Portfolio Manager & Partner"),
   ("Jason Karceski","Portfolio Manager, Research & Partner"),
   ("Greg Sleight","Portfolio Manager & Partner"),
   ("Gal Skarishevsky","Portfolio Manager & Partner")]),
 ("Great Lakes Advisors","Chicago, IL","greatlakesadvisors.com",[
   ("Dan Oshinskie","Chief Investment Officer - Fundamental Equity"),
   ("Scott Macke","Associate Portfolio Manager & Senior Research Analyst (Fundamental Equity)"),
   ("Jon E. Quigley","Chief Investment Officer - Disciplined Equity"),
   ("John D. Bright","Portfolio Manager (Disciplined Equity)")]),
 ("Advisory Research","Chicago, IL","advisoryresearch.com",[
   ("Matthew Swaim","Chairman & Portfolio Manager"),
   ("Chris Harvey","Managing Director & Portfolio Manager"),
   ("Adam Steffanus","Managing Director & Portfolio Manager"),
   ("Michael Valentinas","Managing Director & Portfolio Manager"),
   ("Bruce Zessar","Managing Director & Portfolio Manager"),
   ("Andrew Cupps","Managing Director & Portfolio Manager"),
   ("William Florida","Managing Director & Research Analyst"),
   ("Connor Prassas","Assistant Vice President & Research Analyst")]),
 ("Segall Bryant & Hamill, LLC","Denver, CO","sbhic.com",[
   ("Jeff Paulis","Senior Portfolio Manager (Small Cap; lead PM SMID Cap & Small Cap Core)"),
   ("Shaun Nicholson","Senior Portfolio Manager (Small Cap strategies)"),
   ("Zach Rosenstock","Senior Equity Analyst & Assistant Portfolio Manager (Small Cap Core & SMID)")]),
 ("Ativo Capital Management","Chicago, IL","ativocapital.com",[
   ("Ricardo Bekin","Founder, CEO & Chief Investment Officer"),
   ("Ram G. Gandikota","Deputy CIO & Director of Research"),
   ("Adan Galvan","COO & Senior Portfolio Manager"),
   ("Jeremy Wojcik","Senior Investment Analyst")]),
 ("Zacks Investment Management","Chicago, IL","zacksim.com",[
   ("Mitch Zacks","CEO & Senior Portfolio Manager")]),
 # ---------- MILWAUKEE / WISCONSIN ----------
 ("Fiduciary Management, Inc. (FMI)","Milwaukee, WI","fmimgt.com",[
   ("Jonathan T. Bloom","Partner, Chief Investment Officer"),
   ("Patrick J. English","Chairman, Partner"),
   ("Benjamin D. Karek","Partner, Director of Research, Senior Analyst"),
   ("Matthew T. Sullivan","Partner, Senior Analyst"),
   ("Dain C. Tofson","Partner, Senior Analyst"),
   ("Robert M. Helf","Partner, Senior Analyst"),
   ("Jake E. Strole","Senior Analyst")]),
 ("Baird Equity Asset Management","Milwaukee, WI","bairdassetmanagement.com",[
   ("Kenneth Hemauer","Managing Director, Senior Portfolio Manager (U.S. Growth)"),
   ("Jonathan Good","Managing Director, Senior Portfolio Manager (U.S. Growth)"),
   ("Corbin Weyer","Managing Director, Senior Portfolio Manager & Director of Research"),
   ("Chaitanya Yaramada","Managing Director, Senior Portfolio Manager (U.S. Growth)"),
   ("Chuck Severson","Managing Director, Portfolio Manager - Senior Advisor"),
   ("Christopher Brennan","Vice President, Senior Research Analyst"),
   ("Josh Heinen","Vice President, Senior Research Analyst")]),
 ("Nicholas Company, Inc.","Milwaukee, WI","nicholasfunds.com",[
   ("David O. Nicholas","CEO, President, CIO & Portfolio Manager"),
   ("Lawrence J. Pavelec","COO, EVP & Separate Account Portfolio Manager"),
   ("Brian J. Janowski","Senior Research Analyst & Portfolio Manager"),
   ("Ryan P. Bushman","Senior Research Analyst & Portfolio Manager"),
   ("Jeffrey J. Strong","Senior Research Analyst & Portfolio Manager (Co-PM, Nicholas Fund)"),
   ("Paul J. Knych","Senior Research Analyst & Co-Portfolio Manager"),
   ("Aaron D. Hizmi","Equity Analyst")]),
 ("Mason Street Advisors","Milwaukee, WI","northwesternmutual.com",[
   ("Matthew P. Stucky","Vice President - Chief Portfolio Manager, Equities"),
   ("Jeffery S. Nelson","Senior Director / Senior Portfolio Manager, Equities")]),
 ("Madison Investments","Madison, WI","madisoninvestments.com",[
   ("Haruki Toyama","Head of Mid & Large Cap Team, Portfolio Manager, Director of Research"),
   ("Rich Eisinger","Portfolio Manager (Mid Cap / Large Cap)"),
   ("Andy Romanowich","Portfolio Manager (Mid Cap)")]),
 ("Broadview Advisors, LLC","Milwaukee, WI","broadviewadv.com",[
   ("Rick Lane","Founder & Lead Portfolio Manager"),
   ("Faraz Farzam","Portfolio Manager"),
   ("Aaron J. Garcia","Portfolio Manager")]),
 # ---------- ARTISAN (per-team office cities) ----------
 ("Artisan Partners","Milwaukee, WI","artisanpartners.com",[
   ("Jim Hamel","Managing Director & Portfolio Manager, Growth Team (lead PM, Global Opportunities)"),
   ("Matt Kamm","Managing Director & Portfolio Manager, Growth Team (Global Discovery; co-lead U.S. Mid-Cap Growth)"),
   ("Jason White","Portfolio Manager, Growth Team (co-lead U.S. Mid-Cap Growth)"),
   ("Jay Warner","Portfolio Manager, Growth Team (lead PM, U.S. Small-Cap Growth)"),
   ("Angela Wu","Portfolio Manager, Growth Team")]),
 ("Artisan Partners","San Francisco, CA","artisanpartners.com",[
   ("Mark L. Yockey","Managing Director & Portfolio Manager, Global Equity Team"),
   ("Charles-Henri Hamker","Portfolio Manager, Global Equity Team"),
   ("Lewis S. Kaufman","Managing Director & Founding Portfolio Manager, Developing World Team")]),
 ("Artisan Partners","Atlanta, GA","artisanpartners.com",[
   ("Daniel L. Kane","Managing Director & Portfolio Manager, U.S. Value Team (U.S. Mid-Cap Value)"),
   ("Thomas A. Reynolds IV","Portfolio Manager, U.S. Value Team"),
   ("Craig Inman","Portfolio Manager, U.S. Value Team")]),
 ("Artisan Partners","Boston, MA","artisanpartners.com",[
   ("N. David Samra","Managing Director & Founding Partner, International Value Team (lead PM)"),
   ("Ian McGonigle","Portfolio Manager, International Value Team"),
   ("Joseph Vari","Portfolio Manager, International Value Team")]),
 ("Artisan Partners","Chicago, IL","artisanpartners.com",[
   ("Daniel J. O'Keefe","Managing Director & Founding Partner, Global Value Team (Global Value & Select Equity)"),
   ("Michael J. McKinnon","Portfolio Manager, Global Value Team")]),
 ("Artisan Partners","New York, NY","artisanpartners.com",[
   ("Maria Negrete-Gruson","Managing Director & Portfolio Manager, Sustainable Emerging Markets Team")]),
 ("Artisan Partners","Denver, CO","artisanpartners.com",[
   ("Christopher Smith","Managing Director & Founding Portfolio Manager, Antero Peak Group (Thematic)")]),
 # ---------- SALT LAKE / UTAH ----------
 ("Wasatch Global Investors","Salt Lake City, UT","wasatchglobal.com",[
   ("Ajay Krishnan","Lead Portfolio Manager, Emerging Markets Select / Emerging India / EM Small Cap"),
   ("Anh Hoang","Associate Portfolio Manager, EM Small Cap & EM Select"),
   ("Austin Bone","Lead Portfolio Manager, Small Cap Value; PM, U.S. Select"),
   ("Chris Leikhim","Associate Portfolio Manager, International Micro Cap"),
   ("Dan Aloisio","Portfolio Manager"),
   ("Dan Chace","Portfolio Manager, Emerging Markets Small Cap"),
   ("David Powers","Lead Portfolio Manager, Global Value & International Value"),
   ("Derrick Tzau","Lead Portfolio Manager, International Select; PM, Global Select"),
   ("Gene Robin","Lead Portfolio Manager, Micro Cap Value"),
   ("Jim Shaughnessy","Portfolio Manager, U.S. Select"),
   ("John Malooly","Lead Portfolio Manager, Small Cap Ultra Growth"),
   ("Justin Weaver","Portfolio Manager, Emerging India; Assoc PM, International Micro Cap"),
   ("Kai Pan","Associate Portfolio Manager, International Micro Cap"),
   ("Karson Schrader","Associate Portfolio Manager, Global Small Cap Value & Intl Small Cap Value"),
   ("Ken Applegate","Lead Portfolio Manager, International Small Cap Growth & International Select"),
   ("Ken Korngiebel","Lead Portfolio Manager, Micro Cap Growth; PM, Small Cap Growth"),
   ("Kevin Unger","Associate Portfolio Manager, Emerging Markets Small Cap"),
   ("Kipling Weisel","Associate Portfolio Manager, Small Cap Core Growth"),
   ("Lakshman Venkitaraman","Associate Portfolio Manager, Emerging India & EM Select"),
   ("Mark Madsen","Lead Portfolio Manager, Global Small Cap Value & Intl Small Cap Value"),
   ("Mick Rasmussen","Lead Portfolio Manager, Long/Short Alpha; PM, Global Select & U.S. Select"),
   ("Mike Valentine","Lead Portfolio Manager, Small Cap Core Growth; PM, U.S. Select"),
   ("Nakul Chaturvedi","Associate Portfolio Manager, Global Value & International Value"),
   ("Natalie Pesqué","Lead Portfolio Manager, Small Cap Ultra Growth; PM, Micro Cap & Small Cap Growth"),
   ("Paul Lambert","Lead Portfolio Manager, Small Cap Core Growth; PM, Global Small Cap"),
   ("Pedro Huerta","Associate Portfolio Manager"),
   ("Ryan Snow","Lead Portfolio Manager, Small Cap Growth; PM, Global Small Cap"),
   ("Scott Thomas","Lead Portfolio Manager, Frontier Emerging Small Countries & EM Small Cap"),
   ("Stuart Rigby","Lead Portfolio Manager, Emerging Markets Select; PM, Global Select"),
   ("Thomas Bradley","Lead Portfolio Manager, Micro Cap Value & Micro Cap Growth")]),
 ("Grandeur Peak Global Advisors","Salt Lake City, UT","grandeurpeakglobal.com",[
   ("Randy Pearce","Chief Investment Officer"),
   ("Brad Barth","Deputy Chief Investment Officer"),
   ("Robert Gardiner","Chairman & Co-Founder (Portfolio Manager)"),
   ("Blake Walker","CEO & Co-Founder (Portfolio Manager)"),
   ("Juliette Douglas","Director of Research"),
   ("Benjamin Gardiner","Research Analyst & Portfolio Manager"),
   ("Liping Cai","Research Analyst & Portfolio Manager"),
   ("Tyler Glauser","Research Analyst & Portfolio Manager"),
   ("Spencer Hackett","Research Analyst & Portfolio Manager"),
   ("Phil Naylor","Research Analyst & Portfolio Manager"),
   ("Dane Nielson","Research Analyst & Portfolio Manager"),
   ("Amy Hu Sunderland","Research Analyst & Portfolio Manager"),
   ("Preston Williams","Research Analyst & Portfolio Manager"),
   ("Ryan Bischoff","Senior Research Analyst"),
   ("Matt Kaelberer","Senior Research Analyst"),
   ("Nick Luong","Senior Research Analyst"),
   ("Ayden Richards","Senior Research Analyst"),
   ("Spencer Randall","Senior Research Analyst"),
   ("Erik Christiansen","Research Analyst"),
   ("Joseph Nydegger","Research Analyst"),
   ("Alexis Watson","Research Analyst"),
   ("Daniel Xu","Research Analyst")]),
 ("Seven Canyons Advisors","Salt Lake City, UT","sevencanyonsadvisors.com",[
   ("Spencer Stewart","Portfolio Manager"),
   ("Andrey Kutuzov","Portfolio Manager"),
   ("Wesley Golby","Portfolio Manager"),
   ("Matthew Harris","Research Analyst"),
   ("Samuel Gilson","Quantitative Analyst")]),
 ("Alta Capital Management","Salt Lake City, UT","altacapital.com",[
   ("Casey D. Nelsen","Chief Investment Officer"),
   ("Michael O. Tempest","Portfolio Manager"),
   ("Charles Radtke","Portfolio Manager"),
   ("Carter Allen","Associate Portfolio Manager"),
   ("Nirvon Mahdavi","Associate Portfolio Manager"),
   ("Daniel Lasky","Research Analyst"),
   ("Ethan Kastenschmidt","Equity Research Analyst")]),
 ("Summit Global Investments","Bountiful, UT","sgiam.com",[
   ("David Harden","President & Chief Investment Officer (Founder)")]),
 ("Albion Financial Group","Salt Lake City, UT","albionfinancial.com",[
   ("Jason Ware","Chief Investment Officer, Lead Portfolio Manager, Head of Research"),
   ("Walter Joseph","Head Trader, Analyst"),
   ("Zachary Riley","Trader, Analyst"),
   ("Bo Wilkinson","Trader, Analyst")]),
]
tot_new=tot_merged=0; by_firm={}
for firm,city,domain,people in ENTRIES:
    ppl=[{"name":clean(n),"title":t} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} team page (verified Jul 2026, metro sweep)", people=ppl)
    tot_new+=res["added"]; tot_merged+=res["merged"]
    by_firm[firm]=by_firm.get(firm,0)+res["added"]
    print(f"{firm[:32]:32s} | {city[:16]:16s} | +{res['added']} new, {res['merged']} merged")
print(f"\nMETRO SWEEP: +{tot_new} new, {tot_merged} merged across {len(by_firm)} firms")
