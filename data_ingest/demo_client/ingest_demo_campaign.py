"""Ingest the Lytham/ProStar 1x1 meeting-invite campaign engagement (Jan 2022) into the house CRM
as the demo client's engaged micro-cap investor base. Real names/firms/emails. Opens = warm (email
verified by the open), Clicks = hot. Tagged micro_cap; sell-side/banker firms flagged firm_type=
sell_side (segregated from buy-side targets). Engagement recorded in provenance. Deduped after via
email_dedup. Source='demo_campaign' so the cohort is identifiable."""
import re, openpyxl
from core.security import load_environment; load_environment()
from core import contacts as C, contact_classifier as cc

SRC = r"E:\MAPS Email Campaign Report as of 012522.xlsx"
wb = openpyxl.load_workbook(SRC, read_only=True, data_only=True)
opens = [(r[0], r[1], r[2], r[3], r[4]) for r in wb["Opens"].iter_rows(min_row=2, values_only=True) if r and r[3]]
# clicks: email -> total clicks
clickmap = {}
for r in wb["Clicks"].iter_rows(min_row=2, values_only=True):
    if r and r[3]:
        e = (r[3] or "").strip().lower()
        try: n = int(r[5] or 1)
        except Exception: n = 1
        clickmap[e] = clickmap.get(e, 0) + n

# sell-side / banker detector (broker-dealers, small IBs) -> firm_type sell_side, not a buy-side target
BANK = re.compile(r"securities|capital markets|broker|invest.*bank|\bLLC\b.*securit|Aegis|Ladenburg|"
                  r"Stifel|Gagnon|Regal Securities|GT Securities|ViewTrade|Valens Securities|Maxim|"
                  r"Roth |Canaccord|Cowen|Oppenheimer|Craig.?Hallum|B\.?\s?Riley|Wainwright|Northland|"
                  r"Lake Street|EF Hutton|Rothschild Asset", re.I)

def clean(s): return re.sub(r"\s+", " ", (s or "").strip())

added = sell = engaged_hot = 0
for fn, ln, firm, email, oc in opens:
    name = clean(f"{fn or ''} {ln or ''}")
    firm = clean(firm); email = (email or "").strip().lower()
    if not name or not firm or not email:
        continue
    dom = email.split("@")[-1] if "@" in email else None
    try: opens_n = int(oc or 1)
    except Exception: opens_n = 1
    clk = clickmap.get(email, 0)
    is_bank = bool(BANK.search(firm))
    prov = f"ProStar 1x1 campaign (Lytham, Jan 2022): opened {opens_n}x" + (f"; clicked {clk}x" if clk else "")
    cid = C.upsert_contact(name=name, firm=firm, email=email, domain=dom,
                           email_status="valid", email_source="campaign_open",
                           source="demo_campaign", source_ref="ProStar/Lytham Jan2022")
    if not cid:
        continue
    ftype = "sell_side" if is_bank else cc.firm_type_for(firm, dom)
    prole = "ss_unspecified" if is_bank else None
    C.update_classification(cid, primary_role=prole, firm_type=ftype, market_cap_focus="micro",
                            validation_status="engaged", confidence=85 if clk else 75, provenance=prov)
    added += 1
    if is_bank: sell += 1
    if clk: engaged_hot += 1
print(f"ingested {added} campaign contacts | sell-side/banker flagged: {sell} | clicked (hot): {engaged_hot}")
