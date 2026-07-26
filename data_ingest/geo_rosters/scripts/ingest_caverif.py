"""Ingest Canada verification-agent-cleared firms (TO/Montreal/Vancouver, Jul 2026). Only VERIFIED
active public-equity managers with confirmed people. Rejected/off-mandate firms deliberately absent.
Wrong source-list names (Sylvain Boulianne, Mathieu Gauvin) were dropped by the verifier."""
from core.security import load_environment; load_environment()
from core import roster

FIRMS = {
 "Connor, Clark & Lunn Investment Management": (None, "Vancouver", "cclgroup.com", [
   {"name": "Steven Huang", "title": "Director & Portfolio Manager, Co-Head of Quantitative Equity"},
   {"name": "Jennifer Drake", "title": "Co-Head of Quantitative Equity"},
 ]),
 "Sprott Asset Management": (None, "Toronto", "sprott.com", [
   {"name": "Whitney George", "title": "Senior Portfolio Manager (Sprott Focus Trust, US small/mid-cap value)"},
 ]),
 "Agilith Capital": (None, "Toronto", "agilith.com", [
   {"name": "Patrick Horan", "title": "Principal & Portfolio Manager"},
 ]),
 "Letko, Brosseau & Associates": (None, "Montreal", "lba.ca", [
   {"name": "Peter Letko", "title": "Co-founder & Partner"},
   {"name": "Daniel Brosseau", "title": "Co-founder & Partner"},
   {"name": "Terry Howard", "title": "Senior Portfolio Manager & Partner"},
   {"name": "Mila Krassiouk", "title": "Senior Portfolio Manager & Partner"},
   {"name": "Charmaine Lim Uy", "title": "Senior Portfolio Manager & Partner"},
   {"name": "Victor Swishchuk", "title": "Senior Portfolio Manager & Partner"},
 ]),
 "Montrusco Bolton Investments": (None, "Montreal", "montruscobolton.com", [
   {"name": "Marc Lecavalier", "title": "Senior Portfolio Manager, Small and Mid-Cap Equities"},
   {"name": "Patrick Lauziere", "title": "Assistant Portfolio Manager, Small and Mid-Cap Equities"},
   {"name": "John Goldsmith", "title": "Head of Canadian Equities"},
 ]),
 "Formula Growth": (None, "Montreal", "formulagrowth.com", [
   {"name": "Randall Kelly", "title": "Chief Executive Officer & Chief Investment Officer"},
   {"name": "Anthony Staples", "title": "Senior Vice President & Portfolio Manager"},
   {"name": "Nelson Cheung", "title": "Senior Vice President & Portfolio Manager"},
   {"name": "James Sinclair", "title": "Senior Vice President & Portfolio Manager"},
 ]),
}
for firm, (cik, city, domain, people) in FIRMS.items():
    res = roster.add_people(firm=firm, firm_cik=cik, city=city, domain=domain, side="buy",
                            country="Canada", firm_currency="active_filer" if cik else None,
                            source_note=f"{firm} team page (verified Jul 2026)", people=people)
    print(f"{firm[:34]:34s} | {city[:10]:10s} | {len(people)} -> +{res['added']} new, {res['merged']} merged | {res['by_role']}")
