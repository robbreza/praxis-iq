import json
from core.security import load_environment; load_environment()
from core import db, email_finder
c=db.get_connection().cursor()
c.execute("SELECT contact_id, name, firm, domain FROM contacts WHERE source='firm_site' AND (email IS NULL OR email='') AND domain IS NOT NULL")
rows=[{"contact_id":r[0],"name":r[1],"firm":r[2],"domain":r[3]} for r in c.fetchall()]
found=credits=0; byst={}
for con in rows:
    r=email_finder.enrich_contact(con)
    byst[r["status"]]=byst.get(r["status"],0)+1
    credits+=r.get("credits") or 0
    if r.get("email"): found+=1
    if r["status"] in ("unauthorized","out_of_credits","no_api_key"): break
out={"attempted":len(rows),"found":found,"credits_spent":credits,"by_status":byst}
open(r"C:\Users\Owner\AppData\Local\Temp\claude\C--Users-Owner\65c8460b-e1df-4008-ad04-3b22512af89e\scratchpad\emailfind_result.json","w").write(json.dumps(out,indent=1))
print(json.dumps(out,indent=1))
