"""One-time dedup: clean e-sign prefixes in names, then merge near-duplicate people within the
same firm (exact normalized name, or a strict token-subset sharing the surname). Keeps the richest
record (email > phone > title > real role), backfills its gaps, deletes the rest. House contacts
are referenced by email/account-key elsewhere, not by contact_id, so deleting dup rows is safe."""
import re
from collections import defaultdict

from core.security import load_environment, get_database_url
load_environment()
import psycopg2

conn = psycopg2.connect(get_database_url())
cur = conn.cursor()

# 1) clean '/s/' and '(s)' e-signature markers filers typed into the name field
cur.execute(r"SELECT contact_id, name FROM contacts WHERE name ~* '^\s*(/s/|\(s\))'")
pref = cur.fetchall()
for cid, name in pref:
    clean = re.sub(r"^\s*(?:/s/|\(s\))\s*", "", name, flags=re.I).strip(" .,")
    if clean:
        cur.execute("UPDATE contacts SET name = %s WHERE contact_id = %s", (clean, cid))
conn.commit()
print("cleaned e-sign prefixes:", len(pref))

# 2) merge near-duplicate people within a firm
cols = ["contact_id", "firm_cik", "name", "email", "phone", "title", "primary_role", "roles",
        "seniority", "firm_currency", "market_cap_focus", "email_status", "email_source"]
cur.execute(f"SELECT {','.join(cols)} FROM contacts WHERE firm_cik IS NOT NULL AND firm_cik <> ''")
rows = [dict(zip(cols, r)) for r in cur.fetchall()]
by_firm = defaultdict(list)
for r in rows:
    by_firm[r["firm_cik"]].append(r)


def nkey(n):
    return " ".join(re.sub(r"[^a-z ]", " ", (n or "").lower()).split())


def score(r):
    real = r["primary_role"] and r["primary_role"] not in ("bs_unspecified", "ss_unspecified", "ir_other")
    return (8 if r["email"] else 0) + (4 if r["phone"] else 0) + (2 if r["title"] else 0) + (1 if real else 0)


def merge_ok(a, b):
    ka, kb = nkey(a["name"]), nkey(b["name"])
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    ta, tb = ka.split(), kb.split()
    if (set(ta) < set(tb) or set(tb) < set(ta)) and ta[-1] == tb[-1]:  # subset sharing surname
        return True
    return False


updates, deletes = [], []
for recs in by_firm.values():
    n = len(recs)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    for i in range(n):
        for j in range(i + 1, n):
            if merge_ok(recs[i], recs[j]):
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i in range(n):
        groups[find(i)].append(recs[i])
    for g in groups.values():
        if len(g) < 2:
            continue
        g.sort(key=score, reverse=True)
        primary, others = g[0], g[1:]
        patch = {}
        for o in others:
            for f in ("email", "phone", "title", "email_status", "email_source", "firm_currency", "market_cap_focus"):
                if not primary.get(f) and o.get(f) and f not in patch:
                    patch[f] = o[f]
            if (primary["primary_role"] in (None, "bs_unspecified", "ss_unspecified")
                    and o["primary_role"] not in (None, "bs_unspecified", "ss_unspecified")
                    and "primary_role" not in patch):
                patch["primary_role"], patch["roles"], patch["seniority"] = o["primary_role"], o["roles"], o["seniority"]
        if patch:
            updates.append((primary["contact_id"], patch))
        deletes += [o["contact_id"] for o in others]

for cid, patch in updates:
    sets = ", ".join(f"{k} = %s" for k in patch)
    cur.execute(f"UPDATE contacts SET {sets}, updated_at = now() WHERE contact_id = %s",
                list(patch.values()) + [cid])
if deletes:
    cur.execute("DELETE FROM contacts WHERE contact_id = ANY(%s)", (deletes,))
conn.commit()
print("merged (backfilled) primaries:", len(updates), "| deleted duplicate rows:", len(deletes))
conn.close()
