"""Ingest three OLD contact lists (2021-22) into the house CRM: LPVIC (Lytham VIC ACT list, Sep 2022 —
Company/Contact/Email/Phone/Title), TAAL (Lytham 1x1 campaign opens, Jan 2021), Northland call list
(Company/Name/Email/City/Quality). Keep fund/email/phone (+title/city). OLD -> email_status left
UNKNOWN (can't vouch for current deliverability); validation_status='stale' with age in provenance.
Sell-side flagged. Cross-file dup is low; dedup vs CRM handled by upsert + a later email_dedup pass."""
import re, openpyxl
from core.security import load_environment; load_environment()
from core import contacts as C, contact_classifier as cc

BANK = re.compile(r"securities|capital markets|broker|invest.*bank|Aegis|Ladenburg|Stifel|Maxim|"
                  r"Canaccord|Cowen|Oppenheimer|Wainwright|Northland|Lake Street|Water Tower|"
                  r"William Blair.*Co|Stonegate|B\.?\s?Riley|Craig.?Hallum|Roth ", re.I)
EMAIL = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
def clean(s): return re.sub(r"\s+", " ", (s or "").strip())
def name_clean(n):
    n = clean(n)
    n = re.sub(r"^(Mr\.?|Ms\.?|Mrs\.?|Dr\.?)\s+", "", n, flags=re.I)
    n = re.sub(r",?\s+(CFA|CPA|CAIA|Jr\.?|Sr\.?|III|IV|Ph\.?D\.?)\b.*$", "", n, flags=re.I)
    return n.strip(" ,")

def add(name, firm, email, phone=None, title=None, city=None, source="", sellside=False, note=""):
    name = name_clean(name); firm = clean(firm); email = (email or "").strip().lower()
    if not email or not EMAIL.match(email): return 0
    if not name and not firm: return 0
    firm = firm or "(unknown firm)"
    if not name: name = email.split("@")[0]
    dom = email.split("@")[-1]
    cid = C.upsert_contact(name=name, firm=firm, title=title or None, phone=phone or None, email=email,
                           domain=dom, source=source, source_ref=note)   # email_status left None = unknown
    if not cid: return 0
    ftype = "sell_side" if (sellside or BANK.search(firm)) else cc.firm_type_for(firm, dom)
    C.update_classification(cid, primary_role="ss_unspecified" if ftype=="sell_side" else None,
                            firm_type=ftype, city=city or None, market_cap_focus="micro,small",
                            validation_status="stale", confidence=45, provenance=note)
    return 1

tot=0
# ---- LPVIC ----
wb=openpyxl.load_workbook(r"E:\Contacts (LPVIC)-Rob 091922.xlsx", read_only=True, data_only=True)
ws=wb["ContactList (Rob)"]; hdr_seen=False; n=0
for row in ws.iter_rows(values_only=True):
    cells=[clean(str(c)) if c is not None else "" for c in row]
    if not hdr_seen:
        if "E-mail" in cells or "E-Mail" in cells or "Email" in cells: hdr_seen=True
        continue
    # positions: 2=Company 3=Contact 4=E-mail 5=Phone 7=Title
    company=cells[2] if len(cells)>2 else ""; contact=cells[3] if len(cells)>3 else ""
    email=cells[4] if len(cells)>4 else ""; phone=cells[5] if len(cells)>5 else ""
    title=cells[7] if len(cells)>7 else ""
    n+=add(contact, company, email, phone, title, None, "lpvic_list", note="Lytham LP VIC ACT list (Rob), Sep 2022 — OLD, verify deliverability")
tot+=n; print(f"LPVIC: +{n}")
# ---- TAAL (Opens) ----
wb=openpyxl.load_workbook(r"E:\Copy of TAAL Campaign Report as of 011321 (002).xlsx", read_only=True, data_only=True)
n=0
for r in wb["Opens"].iter_rows(min_row=2, values_only=True):
    if not r or not r[1]: continue
    ss = isinstance(r[4],str) and "sell" in r[4].lower()
    n+=add(r[0], r[2], r[1], None, None, None, "taal_campaign", sellside=ss, note="Lytham TAAL 1x1 campaign opens, Jan 2021 — OLD")
tot+=n; print(f"TAAL: +{n}")
# ---- Northland (ContactList) ----
wb=openpyxl.load_workbook(r"E:\Copy of Northland Call People in Act.xlsx", read_only=True, data_only=True)
n=0
for r in wb["ContactList"].iter_rows(min_row=2, values_only=True):
    if not r or not r[3]: continue
    name=clean(f"{r[1] or ''} {r[2] or ''}"); city=clean(str(r[4])) if len(r)>4 and r[4] else None
    n+=add(name, r[0], r[3], None, None, city, "northland_call_list", note="Northland Capital Markets call list — OLD, verify")
tot+=n; print(f"Northland: +{n}")
print(f"\nOLD LISTS: {tot} rows upserted (net-new + enriched overlaps)")
