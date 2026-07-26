"""Ingest Baltimore/Maryland verification-cleared firms, Jul 2026. Only real, active public-equity
managers with confirmed current people. Rejected: Investment Counselors of Maryland (acquired by
William Blair 2021), Legg Mason (absorbed into Franklin Templeton 2020). T. Rowe rosters corrected
to 2025-26 filings (Currie on New Horizons; Woodruff/Easley on Mid-Cap Growth)."""
import re
from core.security import load_environment; load_environment()
from core import roster

_CREDS = {"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","frm","jd","mba","ii","iii"}
def clean(name):
    parts = [p.strip() for p in name.split(",")]
    kept = [parts[0]] + [p for p in parts[1:] if p.lower().strip(". ") not in _CREDS]
    return ", ".join([k for k in kept if k]).strip(" ,")

FIRMS = {
 "Brown Advisory": ("Baltimore, MD", "brownadvisory.com", [
   ("Christopher Berrier","Portfolio Manager, U.S. Small-Cap Growth Strategy"),
   ("George Sakellaris","Portfolio Manager, U.S. Small-Cap Growth Strategy")]),
 "Brown Capital Management": ("Baltimore, MD", "browncapital.com", [
   ("Keith A. Lee","President, COO and Portfolio Manager"),
   ("Robert E. Hall","Managing Director and Senior Portfolio Manager"),
   ("Kempton M. Ingersol","Managing Director and Senior Portfolio Manager"),
   ("Damien Davis","Portfolio Manager")]),
 "T. Rowe Price": ("Baltimore, MD", "troweprice.com", [
   ("Shaun M. Currie","Portfolio Manager, New Horizons Fund (small-cap growth)"),
   ("David Wagner","Portfolio Manager, Small-Cap Value Fund"),
   ("Ashley R. Woodruff","Portfolio Manager, Mid-Cap Growth Fund"),
   ("Donald J. Easley","Co-Portfolio Manager, Mid-Cap Growth Fund")]),
 "Adams Diversified Equity Fund": ("Baltimore, MD", "adamsfunds.com", [
   ("James P. Haynie","Chief Executive Officer and Portfolio Manager"),
   ("Gregory W. Buckley","Executive Vice President and Portfolio Manager")]),
 "Croft-Leominster": ("Baltimore, MD", "croftfunds.com", [
   ("Kent G. Croft","Chief Investment Officer / Portfolio Manager"),
   ("G. Russell Croft","Portfolio Manager"),
   ("Patrick X. Halloran","Portfolio Manager")]),
 "D.F. Dent and Company": ("Baltimore, MD", "dfdent.com", [
   ("Matthew F. Dent","Vice President and Portfolio Manager, Small Cap Growth Fund"),
   ("Bruce L. Kennedy II","Vice President and Portfolio Manager, Small Cap Growth Fund")]),
 "Chevy Chase Trust": ("Bethesda, MD", "chevychasetrust.com", [
   ("Amy P. Raskin","Chief Investment Officer")]),
}
tot_new = tot_merged = 0
for firm, (city, domain, people) in FIRMS.items():
    ppl = [{"name": clean(n), "title": t} for n, t in people]
    res = roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                            country="US", source_note=f"{firm} team page (verified Jul 2026)", people=ppl)
    tot_new += res["added"]; tot_merged += res["merged"]
    print(f"{firm[:30]:30s} | {city[:14]:14s} | {len(ppl):2d} -> +{res['added']} new, {res['merged']} merged | {res['by_role']}")
print(f"\nBALTIMORE/MD TOTAL: +{tot_new} new, {tot_merged} merged")
