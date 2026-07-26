"""Register the 2nd-sweep verified Philadelphia-metro shops into the GLOBAL curated NDR house book."""
from core.security import load_environment; load_environment()
from core import curated_targets as ct
FIRMS = [
 ("Conestoga Capital Advisors","WAYNE","PA","Employee-owned Micro/Small/SMid/Mid-cap GROWTH boutique (~$8B). Prime small/mid NDR target."),
 ("Copeland Capital Management","CONSHOHOCKEN","PA","Dividend-growth active equity across the cap range incl. Small/SMid (~$4B). NDR target."),
 ("Barton Investment Management","WEST CONSHOHOCKEN","PA","Concentrated (10-15 name) growth-equity stock-picker, 13F filer (~$1B). NDR target."),
 ("Radnor Capital Management","WAYNE","PA","Active equity (Small Cap / Core / Equity Income), in-house research (~$855M). NDR target."),
 ("CenterSquare Investment Management","PLYMOUTH MEETING","PA","Active listed real-assets/REIT stock-picker. Sector-specialist NDR target."),
 ("Xponance","PHILADELPHIA","PA","Diverse-owned active global equity (founder-led) + systematic platform. NDR target."),
]
for filer,city,state,rat in FIRMS:
    ct.add(filer, city=city, state=state, rationale=rat, scope="global", added_by="geo-sweep-2026-07")
    print(f"  + {filer[:34]:34s} {city}, {state}")
print("global NDR book size now:", ct.counts().get("global"))
