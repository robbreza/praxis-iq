"""Register the verified Philadelphia-metro active-equity shops into the GLOBAL curated NDR
house book (core.curated_targets, scope='global'). These are relationship/roadshow TARGETS worth
a Philadelphia NDR stop for a small/mid-cap issuer — tagged 'Curated', never 'holds a comp'.
all_candidates() de-dups any that already surface as a real holder/derived prospect per client."""
from core.security import load_environment; load_environment()
from core import curated_targets as ct

# filer, city, state, rationale
FIRMS = [
 ("Cooke & Bieler", "PHILADELPHIA", "PA", "Independent Philadelphia value-equity boutique (est. 1949, ~$10.7B); all-cap incl. small/mid-cap value. Prime NDR target."),
 ("Penn Capital Management", "PHILADELPHIA", "PA", "Micro/small/SMID-cap equity specialist (est. 1988). Core small/mid NDR account."),
 ("Chartwell Investment Partners", "BERWYN", "PA", "Small-cap growth + SMID active manager (Raymond James IM). NDR target."),
 ("Emerald Advisers", "LEOLA", "PA", "Small-cap growth manager (~$2.6B; Emerald Growth Fund). Small-cap NDR target."),
 ("Glenmede Investment Management", "PHILADELPHIA", "PA", "Fundamental + quantitative active equity (~$6.2B). NDR target."),
 ("Gardner Russo & Quinn", "LANCASTER", "PA", "Concentrated global value compounders (Semper Vic). Relationship/NDR target."),
 ("DuPont Capital Management", "WILMINGTON", "DE", "Active Equities group (global/EM + merger arb, ~$10-12B). Wilmington NDR stop."),
 ("abrdn Inc.", "PHILADELPHIA", "PA", "US Smaller Companies / North American equity desk of abrdn plc. Small-cap NDR target."),
 ("Macquarie Asset Management (Delaware Funds)", "PHILADELPHIA", "PA", "US Small-Mid Cap Value Equity team (Delaware legacy). SMID NDR target. (Note: business transitioning to Nomura.)"),
 ("Haverford Trust Company", "RADNOR", "PA", "Active 'Quality Investing' large-cap equity (Radnor). Quality/large-cap NDR target."),
 ("Penn Mutual Asset Management", "HORSHAM", "PA", "All-cap value equity sleeve (Cipolloni/Saylor, ex-Chartwell). NDR target."),
]
added = 0
for filer, city, state, rationale in FIRMS:
    rec = ct.add(filer, city=city, state=state, rationale=rationale, scope="global", added_by="geo-sweep-2026-07")
    added += 1
    print(f"  + {filer[:40]:40s} {city}, {state}")
print(f"\nregistered {added} Philadelphia-metro firms into GLOBAL curated NDR book")
print("global book size now:", ct.counts().get("global"))
