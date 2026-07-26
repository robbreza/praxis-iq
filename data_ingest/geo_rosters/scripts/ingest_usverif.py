"""Ingest US verification-agent-cleared firms (SF/Denver/NY, Jul 2026). Only VERIFIED, real,
active public-equity managers with confirmed people. Rejected firms are deliberately absent."""
from core.security import load_environment; load_environment()
from core import roster

# firm: (cik|None, city, domain, [people]). CIK None -> resolved later via currency batch.
FIRMS = {
 "Jackson Square Partners": (None, "San Francisco, CA", "jspartners.com", [
   {"name": "Ian Ferry", "title": "Chief Investment Officer, Portfolio Manager"},
   {"name": "Billy Montana", "title": "Lead Portfolio Manager, Large Cap Growth"},
   {"name": "Jeffrey Van Harte", "title": "Founding Partner and Board Member"},
 ]),
 "Fuller & Thaler Asset Management": (None, "San Mateo, CA", "fullerthaler.com", [
   {"name": "Raife Giovinazzo", "title": "Managing Partner, Portfolio Manager"},
   {"name": "David Potter", "title": "Partner, Portfolio Manager"},
   {"name": "Raymond Lin", "title": "Partner, Portfolio Manager"},
   {"name": "Frederick Stanske", "title": "Partner, Portfolio Manager"},
   {"name": "Richard Thaler", "title": "Principal"},
   {"name": "Russell Fuller", "title": "Founder, Emeritus"},
 ]),
 "GHP Investment Advisors": (None, "Denver, CO", "ghpia.com", [
   {"name": "Brian J. Friedman", "title": "President and Chief Investment Officer"},
   {"name": "Brad Engle", "title": "Director of Research, Trading, and Portfolio Analytics"},
   {"name": "Christian Lewton", "title": "Chief Investment Analyst"},
 ]),
 "Tyro Capital Management": (None, "New York, NY", "tyropartners.com", [
   {"name": "Daniel McMurtrie", "title": "Co-Founder and Portfolio Manager"},
   {"name": "D. Alex Draime", "title": "Co-Founder and Senior Analyst"},
 ]),
}
for firm, (cik, city, domain, people) in FIRMS.items():
    res = roster.add_people(firm=firm, firm_cik=cik, city=city, domain=domain, side="buy",
                            country="US", firm_currency="active_filer" if cik else None,
                            source_note=f"{firm} team page (verified Jul 2026)", people=people)
    print(f"{firm[:32]:32s} | {city[:18]:18s} | {len(people)} -> +{res['added']} new, {res['merged']} merged | {res['by_role']}")
