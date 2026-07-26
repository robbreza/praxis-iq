"""Ingest the REMAINING verified Philadelphia-metro active-equity shops (2nd sweep, Jul 2026).
Union of two discovery agents, deduped, fuller roster kept. Rejected (wealth-only / PE / quant /
allocator): SEI/SIMC, FS Investments, PNC (Baltimore), Vanguard QEG, Old Glory, Addison, Malvern
Capital, Mill Creek, Franklin Park, Atairos, Graham Partners. Names cleaned of credential suffixes."""
import re
from core.security import load_environment; load_environment()
from core import roster

_CREDS = {"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","frm","jd","mba","ii","iii"}
def clean(name):
    parts=[p.strip() for p in name.split(",")]
    kept=[parts[0]]+[p for p in parts[1:] if p.lower().strip(". ") not in _CREDS]
    return ", ".join([k for k in kept if k]).strip(" ,")

FIRMS = {
 "Copeland Capital Management": ("Conshohocken, PA", "copelandcapital.com", [
   ("Mark Giovanniello, CFA","Chief Investment Officer, Portfolio Manager"),
   ("Eric Brown, CFA","Chief Executive Officer, Portfolio Manager"),
   ("Erik Granade, CFA","Head of International Equities, Portfolio Manager"),
   ("Willard Kwak, CFA","Portfolio Manager"),
   ("Kenneth Lee","Portfolio Manager, Research Analyst"),
   ("David McGonigle, CFA","Portfolio Manager, Research Analyst"),
   ("Jeffrey Walkenhorst, CFA","Portfolio Manager, Research Analyst"),
   ("John Cummings, CFA","Portfolio Manager, Research Analyst"),
   ("Ryan Buckley, CFA","Research Analyst"),
   ("Jonathan Honda","Research Analyst"),
   ("Edward Rorer","Chairman")]),
 "Conestoga Capital Advisors": ("Wayne, PA", "conestogacapital.com", [
   ("Robert M. Mitchell","Co-Founder, Managing Partner, Chief Investment Officer, Portfolio Manager"),
   ("Duane R. D'Orazio, CFA","Partner, Portfolio Manager"),
   ("Joseph F. Monahan, CFA","Co-Portfolio Manager (Micro Cap), Research Analyst"),
   ("Derek S. Johnston, CFA","Partner, Portfolio Manager (Small Cap Growth)"),
   ("David Neiderer, CFA","Director of Research, Co-Portfolio Manager (Micro Cap Growth)"),
   ("Ted Chang, CFA","Assistant Portfolio Manager (Mid Cap Growth), Equity Analyst"),
   ("Larry Carlin, CFA","Research Analyst"),
   ("Zach Weiss, CFA","Research Analyst"),
   ("John Schipper","Research Analyst"),
   ("Jaisal Khatiwala","Research Analyst")]),
 "CenterSquare Investment Management": ("Plymouth Meeting, PA", "centersquare.com", [
   ("Dean Frankel, CFA","Managing Director, Head of Real Estate Securities (lead PM)"),
   ("Eric Rothman, CFA","Portfolio Manager, Real Estate Securities")]),
 "Xponance": ("Philadelphia, PA", "xponance.com", [
   ("Tina Byles Williams","Founder, Chief Executive Officer, Chief Investment Officer, Lead Portfolio Manager")]),
 "Barton Investment Management": ("West Conshohocken, PA", "bartonim.com", [
   ("J. Barton Riley, CFA","Managing Partner and Founder"),
   ("H. Barton Riley, CFA","Partner and Co-Founder"),
   ("Michael D. Jones, CFA","Portfolio Manager"),
   ("Peter Shouvlin","Portfolio Manager")]),
 "Radnor Capital Management": ("Wayne, PA", "radnorcm.com", [
   ("Douglas Pyle","Founder"),
   ("Jennifer Byrne, CFA","Managing Director, Portfolio Manager"),
   ("J. August Gerhardt, CFA","Senior Portfolio Manager"),
   ("James Gowen, CFA","Senior Portfolio Manager"),
   ("Elisabeth Schwan, CFA","Director of Research")]),
}
tot_new=tot_merged=0
for firm,(city,domain,people) in FIRMS.items():
    ppl=[{"name":clean(n),"title":t} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                          country="US", source_note=f"{firm} team page (verified Jul 2026, 2nd sweep)", people=ppl)
    tot_new+=res["added"]; tot_merged+=res["merged"]
    print(f"{firm[:34]:34s} | {city[:18]:18s} | {len(ppl):2d} -> +{res['added']} new, {res['merged']} merged")
print(f"\nPHILLY 2nd SWEEP: +{tot_new} new, {tot_merged} merged")
