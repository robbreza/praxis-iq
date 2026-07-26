"""Ingest the Bill Miller franchise (verified Jul 2026):
 - Miller Value Partners  -> Sarasota, FL (moved from MD; NOT Milwaukee). Bill Miller IV CIO. 13F 1135778.
 - Patient Capital Mgmt    -> Baltimore, MD. Samantha McLemore CIO (Opportunity Trust successor). 13F 1854794.
Bill Miller III is retired/passive at Miller Value; included as Senior Advisor at Patient Capital."""
from core.security import load_environment; load_environment()
from core import roster

FIRMS = {
 "Miller Value Partners": ("1135778", "Sarasota, FL", "millervalue.com", [
   ("Bill Miller IV","Chief Investment Officer & Portfolio Manager"),
   ("Daniel Lysik","Senior Portfolio Manager"),
   ("Jack Metzger","Research Analyst")]),
 "Patient Capital Management": ("1854794", "Baltimore, MD", "patientcapitalmanagement.com", [
   ("Samantha McLemore","Founder & Chief Investment Officer"),
   ("Christina Siegel Malbon","Assistant Portfolio Manager"),
   ("Tyler Grason","Senior Analyst"),
   ("Finn McGinnis","Junior Analyst"),
   ("Panpan Xiao","Analyst"),
   ("Bill Miller III","Senior Advisor")]),
}
for firm,(cik,city,domain,people) in FIRMS.items():
    ppl=[{"name":n,"title":t} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=cik, city=city, domain=domain, side="buy",
                          country="US", firm_currency="active_filer",
                          source_note=f"{firm} team page (verified Jul 2026)", people=ppl)
    print(f"{firm[:28]:28s} | {city[:14]:14s} cik={cik} | {len(ppl)} -> +{res['added']} new, {res['merged']} merged | {res['by_role']}")
