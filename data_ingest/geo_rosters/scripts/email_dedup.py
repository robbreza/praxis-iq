"""Cross-firm dedup by shared email (same email + same surname = same person). Keeps the richest
record (CIK-linked > real role > title > phone), backfills, deletes the rest. Guarded: different
surnames on one email = a shared/role inbox, so skip."""
import re
from collections import defaultdict
from core.security import load_environment, get_database_url
load_environment()
import psycopg2
conn = psycopg2.connect(get_database_url()); cur = conn.cursor()
cols = ["contact_id","email","name","firm","firm_cik","cik","phone","title","primary_role","roles",
        "seniority","firm_currency","market_cap_focus","country","email_status","email_source"]
cur.execute(f"SELECT {','.join(cols)} FROM contacts WHERE email IS NOT NULL AND email <> ''")
rows = [dict(zip(cols, r)) for r in cur.fetchall()]
by_email = defaultdict(list)
for r in rows:
    by_email[r["email"].lower()].append(r)

def lastn(n):
    t = re.sub(r"[^a-z ]", " ", (n or "").lower()).split()
    return t[-1] if t else ""

def score(r):
    real = r["primary_role"] and r["primary_role"] not in ("bs_unspecified","ss_unspecified","ir_other")
    return (8 if r["firm_cik"] else 0)+(4 if real else 0)+(2 if r["title"] else 0)+(1 if r["phone"] else 0)

updates, deletes = [], []
for g in by_email.values():
    if len(g) < 2:
        continue
    if len({lastn(r["name"]) for r in g}) != 1:   # shared inbox across different people -> skip
        continue
    g.sort(key=score, reverse=True)
    primary, others = g[0], g[1:]
    patch = {}
    for o in others:
        for f in ("phone","title","firm_cik","cik","firm_currency","market_cap_focus","country","email_status","email_source"):
            if not primary.get(f) and o.get(f) and f not in patch:
                patch[f] = o[f]
        if (primary["primary_role"] in (None,"bs_unspecified","ss_unspecified")
                and o["primary_role"] not in (None,"bs_unspecified","ss_unspecified") and "primary_role" not in patch):
            patch["primary_role"], patch["roles"], patch["seniority"] = o["primary_role"], o["roles"], o["seniority"]
    if patch:
        updates.append((primary["contact_id"], patch))
    deletes += [o["contact_id"] for o in others]

for cid, patch in updates:
    sets = ", ".join(f"{k} = %s" for k in patch)
    cur.execute(f"UPDATE contacts SET {sets}, updated_at = now() WHERE contact_id = %s", list(patch.values())+[cid])
if deletes:
    cur.execute("DELETE FROM contacts WHERE contact_id = ANY(%s)", (deletes,))
conn.commit()
print("email-dedup: merged", len(updates), "| deleted", len(deletes))
conn.close()
