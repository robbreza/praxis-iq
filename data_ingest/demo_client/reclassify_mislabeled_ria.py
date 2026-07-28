"""Fix institutional funds that firm_type_for() mislabeled 'ria' because their name contains
'Advisors/Advisory'. These are real buy-side managers/hedge funds, not wealth RIAs -> asset_manager.
Notably Conestoga Capital Advisors (12 records, rostered in the Philly sweep) was all tagged ria."""
from core.security import load_environment, get_database_url; load_environment()
import psycopg2
FUNDS=["Rosalind","Apis Capital","Long Cast","Kopp Investment","Columbia Pacific","Yorkville","Conestoga Capital Advisors"]
conn=psycopg2.connect(get_database_url()); cur=conn.cursor()
for pat in FUNDS:
    cur.execute("UPDATE contacts SET firm_type='asset_manager', updated_at=now() WHERE firm ILIKE %s AND firm_type='ria'", (f"%{pat}%",))
    print(pat, cur.rowcount)
conn.commit(); conn.close()
