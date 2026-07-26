"""Ingest Philadelphia-metro (PA/DE) verification-cleared firms, Jul 2026. Union of two verifier
agents, deduped; fuller roster kept. Rejected: Brandywine Global (equity moved to Franklin Equity
Group Jan 2026), Aristotle (no Philly office), Rittenhouse (absorbed into Nuveen). Only real, active
public-equity managers with confirmed current people. Names cleaned of credential suffixes."""
import re
from core.security import load_environment; load_environment()
from core import roster

_CREDS = {"cfa","cfp","clu","cpa","caia","phd","ph.d.","cmt","frm","jd","mba","cff","chfc","asa"}
def clean(name):
    parts = [p.strip() for p in name.split(",")]
    kept = [parts[0]] + [p for p in parts[1:] if p.lower().strip(". ") not in _CREDS]
    return ", ".join([k for k in kept if k]).strip(" ,")

# firm: (city, domain, [(name,title)])
FIRMS = {
 "Cooke & Bieler": ("Philadelphia, PA", "cooke-bieler.com", [
   ("Andrew Armstrong, CFA","Partner, Analyst/Portfolio Manager"),
   ("Steve Lyons, CFA","Partner, Analyst/Portfolio Manager"),
   ("Michael M. Meyer, CFA","Partner, Analyst/Portfolio Manager"),
   ("Edward O'Connor, CFA","Partner, Analyst/Portfolio Manager"),
   ("James O'Neil, CFA","Partner, Analyst/Portfolio Manager"),
   ("Mehul Trivedi, CFA","Partner, Analyst/Portfolio Manager"),
   ("William Weber, CFA","Partner, Analyst/Portfolio Manager"),
   ("Cathy Zhu","Principal, Analyst/Portfolio Manager")]),
 "Penn Capital Management": ("Philadelphia, PA", "penncapital.com", [
   ("Eric J. Green, CFA","Chief Investment Officer, Senior Portfolio Manager"),
   ("Joseph Maguire, CFA","Director of Research, Senior Portfolio Manager"),
   ("J. Paulo Silva, CFA","Senior Portfolio Manager"),
   ("Michael Kehoe","Portfolio Manager, Senior Research Analyst"),
   ("Randall Braunfeld","Senior Research Analyst, Assistant Portfolio Manager"),
   ("Christopher Paciello, CFA","Senior Research Analyst, Assistant Portfolio Manager"),
   ("Bradley D. Tesoriero, CFA","Senior Research Analyst, Assistant Portfolio Manager"),
   ("Ben Pickles, CFA","Research Analyst")]),
 "Chartwell Investment Partners": ("Berwyn, PA", "chartwellip.com", [
   ("Frank Sustersic, CFA","Senior Portfolio Manager, Managing Partner (Small-Cap Growth)"),
   ("Bernard P. Schaffer","Founding Partner & Senior Portfolio Manager (Large-Cap/Closed-End Equity)"),
   ("Douglas Kugler, CFA","Senior Portfolio Manager")]),
 "Emerald Advisers": ("Leola, PA", "teamemerald.com", [
   ("Kenneth G. Mertz II, CFA","Chief Investment Officer & President; Small Cap Portfolio Manager"),
   ("Joseph W. Garner","Portfolio Manager & Director of Research"),
   ("Stacey L. Sears","Portfolio Manager, Senior Vice President"),
   ("Joseph Volpe","Deputy CIO; Portfolio Manager (Mid Cap Growth)")]),
 "Glenmede Investment Management": ("Philadelphia, PA", "glenmede.com", [
   ("Vladimir de Vassal, CFA","Director of Quantitative Research / Portfolio Manager")]),
 "Gardner Russo & Quinn": ("Lancaster, PA", None, [
   ("Thomas A. Russo","Managing Member / Portfolio Manager"),
   ("Timothy C. Quinn","Director of Research")]),
 "DuPont Capital Management": ("Wilmington, DE", "dupontcapital.com", [
   ("Lode Devlaminck","Managing Director, Equities"),
   ("Harris Arch, CFA","Portfolio Manager, Merger Arbitrage & Senior Analyst, Global Equities"),
   ("Dan Moore, CFA","Portfolio Manager, Merger Arbitrage & Senior Credit Analyst"),
   ("Margaret E. Moore","Senior Analyst, Portfolio Manager")]),
 "abrdn Inc.": ("Philadelphia, PA", "abrdn.com", [
   ("Christopher Colarik","Head of U.S. Smaller Companies"),
   ("Mike Cronin, CFA","Investment Director, North American Equities"),
   ("Christopher Haimendorf, CFA","Senior Investment Director, North American Equity Team")]),
 "Macquarie Asset Management (Delaware Funds)": ("Philadelphia, PA", "delawarefunds.com", [
   ("Kelley McKee Carabasi, CFA","Senior Portfolio Manager & Co-CIO, US Small-Mid Cap Value Equity"),
   ("Kent Madden, CFA","Senior Portfolio Manager & Co-CIO, US Small-Mid Cap Value Equity")]),
 "Haverford Trust Company": ("Radnor, PA", "haverfordquality.com", [
   ("Timothy A. Hoyle, CFA","Chief Investment Officer"),
   ("Bryan P. Tracy, CFA","Vice President & Director of Portfolio Management"),
   ("Michael McIntyre","Vice President & Portfolio Manager"),
   ("John D'Anna","Vice President, Portfolio Manager"),
   ("David Moniz","Vice President, Portfolio Manager"),
   ("Mary Sutphen, CFP","Vice President, Portfolio Manager")]),
 "Penn Mutual Asset Management": ("Horsham, PA", "pmam.com", [
   ("George Cipolloni III, CFA","Portfolio Manager (Equity)"),
   ("Mark Saylor, CFA","Portfolio Manager (Equity)")]),
}
tot_new = tot_merged = 0
for firm, (city, domain, people) in FIRMS.items():
    ppl = [{"name": clean(n), "title": t} for n, t in people]
    res = roster.add_people(firm=firm, firm_cik=None, city=city, domain=domain, side="buy",
                            country="US", source_note=f"{firm} team page (verified Jul 2026)", people=ppl)
    tot_new += res["added"]; tot_merged += res["merged"]
    print(f"{firm[:36]:36s} | {city[:16]:16s} | {len(ppl):2d} -> +{res['added']} new, {res['merged']} merged | {res['by_role']}")
print(f"\nPHILLY TOTAL: +{tot_new} new, {tot_merged} merged")
