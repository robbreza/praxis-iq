"""Register the metro-sweep FUNDAMENTAL active-equity shops into the GLOBAL curated NDR house book.
Pure-quant (LSV, Ativo, Zacks, Summit Global) and captive (Mason Street) are intentionally NOT
registered as NDR targets (weak management-access fit) though they remain in the contact CRM."""
from core.security import load_environment; load_environment()
from core import curated_targets as ct
FIRMS = [
 # Chicago
 ("Ariel Investments","CHICAGO","IL","John Rogers' fundamental value shop; dedicated small & SMID value. Prime NDR target."),
 ("Harris Associates","CHICAGO","IL","Oakmark value stock-pickers (Nygren). Premier NDR target."),
 ("Great Lakes Advisors","CHICAGO","IL","Fundamental Equity team (Large Cap Value, Small Cap). NDR target."),
 ("Advisory Research","CHICAGO","IL","Employee-owned high-conviction fundamental equity (US value/growth). NDR target."),
 # Milwaukee / Wisconsin
 ("Fiduciary Management, Inc. (FMI)","MILWAUKEE","WI","Focused value (Large/All Cap, International), ~$9B. Prime NDR target."),
 ("Baird Equity Asset Management","MILWAUKEE","WI","U.S. Growth team (Mid Cap, Small/Mid Growth). NDR target."),
 ("Nicholas Company, Inc.","MILWAUKEE","WI","Family-founded active growth equity (David Nicholas). NDR target."),
 ("Madison Investments","MADISON","WI","Bottom-up 'moat' equity (Large/Mid Cap). NDR target."),
 ("Broadview Advisors, LLC","MILWAUKEE","WI","Small/mid-cap value stock-picker (~$400M). NDR target (verify roster)."),
 ("Artisan Partners","MILWAUKEE","WI","Multi-team active equity; teams in Milwaukee/SF/Atlanta/Boston/Chicago/NY/Denver. Major NDR target across metros."),
 # Salt Lake / Utah
 ("Wasatch Global Investors","SALT LAKE CITY","UT","Small/micro-cap growth specialist (~$29B). Prime small-cap NDR target."),
 ("Grandeur Peak Global Advisors","SALT LAKE CITY","UT","Micro/small-cap global boutique (Wasatch spinoff, ~$6B). Prime NDR target."),
 ("Seven Canyons Advisors","SALT LAKE CITY","UT","Global small/micro-cap growth (Sam Stewart's boutique). Strong small-cap NDR target."),
 ("Alta Capital Management","SALT LAKE CITY","UT","Fundamental quality-growth stock-picker (~$1.8B), 13F filer. NDR target."),
 ("Albion Financial Group","SALT LAKE CITY","UT","In-house individual-stock selection (CIO-led); wealth-anchored. Lower-priority NDR target."),
]
for filer,city,state,rat in FIRMS:
    ct.add(filer, city=city, state=state, rationale=rat, scope="global", added_by="geo-sweep-2026-07")
    print(f"  + {filer[:34]:34s} {city}, {state}")
print("global NDR book size now:", ct.counts().get("global"))
