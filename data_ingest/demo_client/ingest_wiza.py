"""Ingest the Wiza LinkedIn 'Global Equity Research' export (2022) into the house CRM. WIZA_B is the
superset of WIZA_A (A ⊂ B) so only B is loaded. Rich Wiza schema: Wiza-VERIFIED email + type +
title + company + location + LinkedIn + company_country. Equity-RESEARCH segment (analysts /
research boutiques) — distinct from the investor book. Title -> classifier roles. LinkedIn + email
type stashed in provenance. validation_status='probable' (Wiza-verified, but 2022 -> re-validate
before outbound). Only email_status='valid' rows; personal emails flagged in provenance."""
import openpyxl, re
from core.security import load_environment; load_environment()
from core import contacts as C, contact_classifier as cc

F=r"E:\WIZA_Global_Equity_Research_linkedIn_421105.xlsx"
wb=openpyxl.load_workbook(F, read_only=True, data_only=True)
ws=wb.worksheets[0]
rows=list(ws.iter_rows(values_only=True))
hdr=[str(c).strip() if c is not None else "" for c in rows[0]]
ix={h:i for i,h in enumerate(hdr)}
def g(r,k):
    i=ix.get(k); return (str(r[i]).strip() if i is not None and i<len(r) and r[i] is not None else "")

added=sell=personal=0
for r in rows[1:]:
    if g(r,"email_status").lower()!="valid": continue
    email=g(r,"email").lower();
    if "@" not in email: continue
    name=g(r,"full_name") or f"{g(r,'first_name')} {g(r,'last_name')}".strip()
    firm=g(r,"company"); title=g(r,"title") or None
    loc=g(r,"location"); country=g(r,"company_country") or None
    li=g(r,"linkedin"); etype=g(r,"email_type").lower(); dom=g(r,"domain") or email.split("@")[-1]
    if not name or not firm: continue
    is_personal = etype=="personal"
    prov=(f"Wiza LinkedIn Global-Equity-Research pull (2022); email_status=valid/{etype or 'work'}. "
          f"OLD — re-validate before outbound." + (f" LinkedIn: {li}" if li else ""))
    cid=C.upsert_contact(name=name, firm=firm, title=title, email=email, domain=dom,
                         email_status="valid" if not is_personal else "personal",
                         email_source="wiza_linkedin", source="wiza_equity_research_2022",
                         source_ref=li or "Wiza LinkedIn export")
    if not cid: continue
    roles,primary=cc.classify_roles(title or "", side="buy")
    ftype=cc.firm_type_for(firm, dom)
    C.update_classification(cid, roles=",".join(roles) or None, primary_role=primary,
                            seniority=cc.seniority_for(roles), firm_type=ftype,
                            city=loc or None, country=country, validation_status="probable",
                            confidence=70, provenance=prov)
    added+=1
    if ftype=="sell_side": sell+=1
    if is_personal: personal+=1
print(f"WIZA_B: ingested {added} equity-research contacts | sell-side firms: {sell} | personal-email flagged: {personal}")
