"""Ingest verified Jackson Hole / Teton County, WY active PUBLIC-EQUITY managers (Jul 2026).
Only genuine stock-pickers with named people. Excluded (not NDR targets): HRTG GPE & Grand Teton
(family offices), Bank of Jackson Hole Trust (bank trust dept), Flat Rock Global (private credit),
Greybull (PE), Green Tuatara / Wind River (wealth RIAs), Corax (<$100M, no named person),
Founders Equity (strategy unconfirmed). Friess CIK 820289 bound directly (active 13F filer)."""
from core.security import load_environment; load_environment()
from core import roster

FIRMS = {
 "Friess Associates": ("820289", "active_filer", "Jackson, WY", None, [
   ("Renae Leonard","Portfolio Manager")]),
 "Flat Footed LLC": (None, None, "Wilson, WY", None, [
   ("Marc Andersen","Co-Founder & Portfolio Manager"),
   ("Paul Carpenter","Co-Founder")]),
 "Gervais Capital Management": (None, None, "Wilson, WY", None, [
   ("Donald G. Gervais, Jr.","Founder & Chief Executive Officer")]),
}
for firm,(cik,cur,city,domain,people) in FIRMS.items():
    ppl=[{"name":n,"title":t} for n,t in people]
    res=roster.add_people(firm=firm, firm_cik=cik, city=city, domain=domain, side="buy",
                          country="US", firm_currency=cur,
                          source_note=f"{firm} (Jackson Hole WY, verified Jul 2026)", people=ppl)
    print(f"{firm[:26]:26s} | {city[:12]:12s} cik={cik or '-':>8} | +{res['added']} new, {res['merged']} merged | {res['by_role']}")
