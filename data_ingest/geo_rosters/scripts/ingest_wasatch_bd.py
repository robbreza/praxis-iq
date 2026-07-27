"""Add Wasatch Global Investors' 5 PUBLISHED business-development / institutional contacts with
their REAL emails + phones from wasatchglobal.com/contact (verified, not inferred). These are
distribution/BD/board people, not the investment team — useful for routing IR meetings."""
from datetime import datetime
from core.security import load_environment, get_database_url; load_environment()
from core import contacts as C, contact_classifier as cc
import psycopg2

FIRM = "Wasatch Global Investors"
PEOPLE = [
 ("Brandon Fries","Regional Vice President of Sales, Central United States","brandon@wasatchglobal.com","801.983.4147"),
 ("Eric Bergeson","Board Member","eric@wasatchglobal.com","801.983.4119"),
 ("Dustin McCarty","Head of Global Client and Distribution","dmccarty@wasatchglobal.com","801.415.5524"),
 ("Albert Trinkl","Managing Director, Institutional Business Development, EMEA","atrinkl@wasatchglobal.com","385.218.7746"),
 ("Lydia Gaylord","Vice President, Institutional Business Development","lgaylord@wasatchglobal.com","801.983.4143"),
]
conn = psycopg2.connect(get_database_url()); cur = conn.cursor()
cur.execute("SELECT firm_cik FROM contacts WHERE firm=%s AND firm_cik IS NOT NULL AND firm_cik<>'' LIMIT 1",(FIRM,))
row=cur.fetchone(); fcik = row[0] if row else None
now=datetime.now()
cols=["contact_id","cik","firm","firm_key","name","title","phone","email","email_status",
      "source","source_ref","created_at","updated_at","roles","primary_role","seniority",
      "firm_type","country","city","market_cap_focus","validation_status","confidence","provenance",
      "firm_cik","firm_currency"]
for name,title,email,phone in PEOPLE:
    cid=C.contact_id_for(fcik, name, FIRM)
    roles,primary=cc.classify_roles(title, side="buy")
    vals=[cid, fcik, FIRM, C._norm(FIRM), name, title, phone, email, "verified",
          "firm_site","wasatchglobal.com/contact page (verified Jul 2026)", now, now,
          ",".join(roles) or None, primary, cc.seniority_for(roles),
          cc.firm_type_for(FIRM,"wasatchglobal.com"), "US", "Salt Lake City, UT", "micro,small",
          "verified", 95, "Published on wasatchglobal.com contact page", fcik, "active_filer" if fcik else None]
    setc=", ".join(f"{c2}=EXCLUDED.{c2}" for c2 in cols if c2 not in ("contact_id","created_at"))
    cur.execute(f"INSERT INTO contacts ({','.join(cols)}) VALUES ({','.join(['%s']*len(cols))}) "
                f"ON CONFLICT (contact_id) DO UPDATE SET {setc}", vals)
    print(f"  + {name:20s} {email:32s} {phone}  [{primary}]")
conn.commit(); conn.close()
print(f"\nadded 5 verified Wasatch BD/institutional contacts (firm_cik={fcik})")
