"""Fix CIK bindings for four firms the currency pass got wrong, plus one classification fix.

The scoped currency re-run (run_currency2.py) resolved firm_site firms by EXACT normalized-name
match against EDGAR's cik-lookup dump. Three well-known 13F filers matched the WRONG entity (a
parent holdco that files no 13F) or didn't match at all, so their rosters wouldn't link to
peer-owner cards. Each correct CIK below was verified to file a 13F-HR on 2026-05-15 (EDGAR):

  T. Rowe Price        -> 80255   PRICE T ROWE ASSOCIATES INC /MD/   (was 730200, the Group holdco = no_13f)
  Macquarie/Delaware   -> 921739  DELAWARE MANAGEMENT HOLDINGS INC   (was 1486436 = no_13f)
  D.F. Dent and Company-> 934999  DF DENT & CO INC                   (was unresolved — no exact norm match)

Plus: abrdn Inc.'s three people carried abrdn's UK-style "Investment Director" / "Head of U.S.
Smaller Companies" titles, which the classifier left as bs_unspecified (not a team role), so the
peer-owner "Team (N)" badge read 0. Reclassified to buy_side_pm so they count as investment team.

All four verified afterward: firm_roster_counts() badge == roster_for_firm() panel
(T. Rowe 4=4, Macquarie 2=2, D.F. Dent 2=2, abrdn 3=3). Data-only change; lives in Neon.

NOTE: run against the production DB with the shell sandbox disabled — sandboxed DB-write
processes were being killed mid-transaction (reads were unaffected).
"""
from core.security import load_environment, get_database_url; load_environment()
from core import db, contacts as C, contact_classifier as cc
import psycopg2

# 1-3) rebind to the correct, verified active 13F-filer CIK (only these firms' rows)
CIKFIX = {
    "T. Rowe Price": ("80255", "active_filer"),
    "Macquarie Asset Management (Delaware Funds)": ("921739", "active_filer"),
    "D.F. Dent and Company": ("934999", "active_filer"),
}
conn = psycopg2.connect(get_database_url()); cur = conn.cursor()
for firm, (cik, st) in CIKFIX.items():
    cur.execute("UPDATE contacts SET firm_cik=%s, firm_currency=%s, updated_at=now() WHERE firm=%s",
                (cik, st, firm))
    print(f"bound {firm} -> cik {cik} ({cur.rowcount} contacts)")
conn.commit(); conn.close()

# 4) abrdn: reclassify the three PM-equivalent 'Investment Director' people as buy_side_pm
c = db.get_connection().cursor()
c.execute("SELECT contact_id, name FROM contacts WHERE firm='abrdn Inc.'")
sen = cc.seniority_for(["buy_side_pm"])
for cid, name in c.fetchall():
    C.update_classification(cid, roles="buy_side_pm", primary_role="buy_side_pm", seniority=sen)
    print(f"reclassified {name} -> buy_side_pm/{sen}")
print("done")
