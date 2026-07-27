"""Create the anonymized demo tenant (fictional micro-cap) and seed its curated NDR book from the
HOT clickers (buy-side firms that clicked the 1x1 meeting invite). Investor data is real; the issuer
is illustrative. client_store.upsert_client persists the tenant; reload_registry overlays it live."""
import re, openpyxl
from core.security import load_environment; load_environment()
from core import client_store, curated_targets as ct

DEMO = {
 "ticker": "MGEO",
 "name": "Meridian GeoData, Inc.",
 "exchange": "NASDAQ",
 "email_domain": "meridiangeodata.com",
 "sector": "Geospatial / Precision-Mapping SaaS",
 "chain": "software",
 "last_price": 3.20, "price_date": "illustrative", "market_cap_m": 85, "ev_m": 78,
 "ir_contact": {"irconnect": "irconnect@meridiangeodata.com"},
 "demo": True,
 "note": ("Anonymized DEMO tenant. Investor base is REAL — seeded from a micro-cap 1x1 "
          "meeting-invite campaign engagement (opens=warm, clicks=hot). Issuer name/ticker/"
          "figures are illustrative, not a real company."),
 "executives": {}, "analysts": [], "peers": [], "earnings": {}, "financials": {}, "guidance": {},
 "fy_guidance": "", "fls_items": [], "guidance_policy": {},
}
client_store.upsert_client("demo", DEMO, active=True, merge=True)
print("demo tenant created:", DEMO["name"], f"({DEMO['ticker']}) — micro-cap ${DEMO['market_cap_m']}M")

# Seed demo's client-scoped curated NDR book from HOT clickers (buy-side firms only)
wb = openpyxl.load_workbook(r"E:\MAPS Email Campaign Report as of 012522.xlsx", read_only=True, data_only=True)
BANK = re.compile(r"securities|capital markets|broker|Aegis|Ladenburg|Stifel|Gagnon|Regal Securities|"
                  r"GT Securities|ViewTrade|Valens Securities|Maxim|Canaccord|Cowen|Oppenheimer|"
                  r"Wainwright|Northland|Lake Street|Rothschild Asset", re.I)
seen=set(); added=0
for r in wb["Clicks"].iter_rows(min_row=2, values_only=True):
    if not r or not r[2]: continue
    firm=re.sub(r"\s+"," ",(r[2] or "").strip())
    k=firm.lower()
    if not firm or k in seen or BANK.search(firm): continue
    seen.add(k)
    ct.add(firm, rationale="Clicked the 1x1 meeting invite — HOT engaged micro-cap prospect (Jan 2022 campaign).",
           scope="client", cid="demo", added_by="demo-seed")
    added+=1
print(f"seeded {added} hot buy-side firms into demo client's curated NDR book")
print("demo curated counts:", ct.counts("demo"))
