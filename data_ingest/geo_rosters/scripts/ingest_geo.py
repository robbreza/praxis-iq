import sys, json, html, re
from core.security import load_environment; load_environment()
from core import roster
_CRED = re.compile(r",?\s*\b(CFA|CPA|CFP|CAIA|CMT|CIPM|CIMA|FRM|ChFC|CIC|CFA)\b\.?", re.I)
def clean(n):
    return re.sub(r"\s+", " ", _CRED.sub("", html.unescape(n or ""))).strip().strip(",").strip()
data = json.load(open(sys.argv[1], encoding="utf-8"))
tot_new = tot_merge = 0
for firm, payload in data.items():
    firm = html.unescape(firm)
    city = payload.get("city"); domain = payload.get("domain")
    people = [{"name": clean(p.get("name", "")), "title": html.unescape(p.get("title") or "")}
              for p in (payload.get("people") or [])]
    people = [p for p in people if p["name"]]
    if not people:
        print(f"  {firm[:34]:34s} | (no people)"); continue
    res = roster.add_people(firm=firm, city=city, domain=domain, side="buy", country="US",
                            source_note=f"Discovery: {city}, Jul 2026", people=people)
    tot_new += res["added"]; tot_merge += res["merged"]
    print(f"  {firm[:30]:30s} | {str(city)[:16]:16s} | {len(people):2d} -> +{res['added']} new, {res['merged']} merged")
print(f"TOTAL: +{tot_new} new, {tot_merge} merged")
