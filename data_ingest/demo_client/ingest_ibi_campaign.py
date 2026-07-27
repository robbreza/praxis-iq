"""Ingest the Lytham/IBI Group (IBG) 1x1 meeting-invite campaign engagement (Jan 28 2022) into the
house CRM. Same micro/small-cap universe as the ProStar campaign -> heavy overlap; overlapping
people get ENRICHED with a second engagement event (a firm that engaged BOTH 1x1s = strong
'takes small-cap meetings' signal). Opens=warm, Clicks=hot. Tagged micro,small; sell-side bankers
flagged firm_type=sell_side. source='lytham_ibi_campaign'. Goes to the house book, NOT the demo tenant."""
import re, openpyxl
from core.security import load_environment; load_environment()
from core import db, contacts as C, contact_classifier as cc

F = r"E:\Copy of IBI Group Email Report as of 013122.xlsx"
wb = openpyxl.load_workbook(F, read_only=True, data_only=True)
opens = [(r[0], r[1], r[2], r[3], r[4]) for r in wb["Opens"].iter_rows(min_row=2, values_only=True) if r and r[3]]
clickmap = {}
for r in wb["Clicks"].iter_rows(min_row=2, values_only=True):
    if r and r[3]:
        e = (r[3] or "").strip().lower()
        try: n = int(r[5] or 1)
        except Exception: n = 1
        clickmap[e] = clickmap.get(e, 0) + n

# overlap: how many IBI openers already in the CRM (by email)?
cur = db.get_connection().cursor()
cur.execute("SELECT lower(email) FROM contacts WHERE email IS NOT NULL AND email<>''")
existing = {r[0] for r in cur.fetchall()}
ibi_emails = {(o[3] or "").strip().lower() for o in opens}
overlap = len(ibi_emails & existing)
print(f"IBI openers: {len(opens)} | already in CRM by email: {overlap} | net-new: {len(ibi_emails - existing)}")

BANK = re.compile(r"securities|capital markets|broker|invest.*bank|Aegis|Ladenburg|Stifel|Gagnon|"
                  r"Regal Securities|GT Securities|ViewTrade|Valens Securities|Maxim|Canaccord|Cowen|"
                  r"Oppenheimer|Wainwright|Northland|Lake Street|Stonegate Capital Market|Roth ", re.I)
def clean(s): return re.sub(r"\s+", " ", (s or "").strip())

added = sell = hot = 0
for fn, ln, firm, email, oc in opens:
    name = clean(f"{fn or ''} {ln or ''}"); firm = clean(firm); email = (email or "").strip().lower()
    if not name or not firm or not email:
        continue
    dom = email.split("@")[-1] if "@" in email else None
    try: opens_n = int(oc or 1)
    except Exception: opens_n = 1
    clk = clickmap.get(email, 0)
    is_bank = bool(BANK.search(firm))
    prov = f"IBI Group (IBG) 1x1 campaign (Lytham, Jan 2022): opened {opens_n}x" + (f"; clicked {clk}x" if clk else "")
    cid = C.upsert_contact(name=name, firm=firm, email=email, domain=dom, email_status="valid",
                           email_source="campaign_open", source="lytham_ibi_campaign", source_ref="IBI/Lytham Jan2022")
    if not cid: continue
    ftype = "sell_side" if is_bank else cc.firm_type_for(firm, dom)
    C.update_classification(cid, primary_role="ss_unspecified" if is_bank else None, firm_type=ftype,
                            market_cap_focus="micro,small", validation_status="engaged",
                            confidence=85 if clk else 75, provenance=prov)
    added += 1
    if is_bank: sell += 1
    if clk: hot += 1
print(f"ingested {added} IBI campaign contacts | sell-side flagged: {sell} | clicked (hot): {hot}")
