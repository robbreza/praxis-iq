"""core/firm_book.py — the FIRM layer of the house CRM.

Contacts are people; this is the institution they sit in. For every firm we hold contacts at
that files a 13F, enrich it from the cover page: business CITY/STATE, portfolio AUM (dollars —
active filers post-date the 2023 rule so it's comparable), position count, and the current
signatory. That gives a rankable firm universe — "top 25 firms by city" — which is the target
list that drives filling out each firm's PM/analyst roster.

Stored as a single global JSON blob keyed by CIK (firm data is tenant-independent, same as the
contacts identity layer). No db connection held across the throttled EDGAR phase.
"""
import time
from datetime import datetime

from core import db, contacts, sec_filings as sf

_KEY = "crm_firms"
_SCOPE = "_global"


def load_firms():
    return db.load_json(_KEY, {}, client_id=_SCOPE) or {}


def save_firms(d):
    db.save_json(_KEY, d, client_id=_SCOPE)


def _firm_rows(currencies):
    """(firm_cik, our_contact_count, representative_name, currency) for firms we hold contacts
    at whose currency is in `currencies`. Currency filtered in Python (dialect-agnostic)."""
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT firm_cik, count(*), max(firm), max(firm_currency) FROM contacts "
                    "WHERE firm_cik IS NOT NULL GROUP BY firm_cik")
        return [r for r in cur.fetchall() if r[3] in currencies]
    finally:
        conn.close()


def enrich(throttle=0.15, limit=None, currencies=("active_filer",)):
    """Enrich every in-scope firm from its latest 13F cover page. Idempotent; checkpoints every
    50 firms so a mid-run stop still persists progress. Returns a summary."""
    rows = _firm_rows(currencies)
    if limit:
        rows = rows[:limit]
    firms = load_firms()
    done = failed = 0
    for cik, cnt, our_name, currency in rows:
        try:
            fils = sf.filer_13f_filings(int(cik), limit=1)
            time.sleep(throttle)
            if not fils:
                failed += 1
                continue
            info = contacts.cover_info_from_13f(int(cik), fils[0]["accession"])
            time.sleep(throttle)
            if not info:
                failed += 1
                continue
            firms[str(cik)] = {
                "cik": str(cik), "manager": info.get("manager") or our_name, "our_name": our_name,
                "city": (info.get("city") or "").title() or None,
                "state": info.get("state"), "aum": info.get("aum"), "positions": info.get("positions"),
                "currency": currency, "contacts": int(cnt), "last_13f": fils[0].get("date"),
                "signatory": (info.get("signatory") or {}).get("name"),
                "updated_at": datetime.now().isoformat(),
            }
            done += 1
            if done % 50 == 0:
                save_firms(firms)
        except Exception:
            failed += 1
    save_firms(firms)
    return {"firms_enriched": done, "failed": failed, "total_in_book": len(firms)}


def top_firms(n=25, by="aum"):
    firms = [f for f in load_firms().values() if f.get(by) is not None]
    firms.sort(key=lambda f: f.get(by) or 0, reverse=True)
    return firms[:n]


def by_city(min_firms=2, by="aum"):
    """Firms grouped by metro city, cities ordered by total AUM — the NDR lens (which cities are
    worth a visit and who's there)."""
    cities = {}
    for f in load_firms().values():
        c = f.get("city") or "—"
        cities.setdefault(c, []).append(f)
    out = []
    for c, fs in cities.items():
        if len(fs) < min_firms:
            continue
        fs.sort(key=lambda x: x.get(by) or 0, reverse=True)
        out.append({"city": c, "firms": fs, "n": len(fs),
                    "total_aum": sum(x.get("aum") or 0 for x in fs),
                    "contacts": sum(x.get("contacts") or 0 for x in fs)})
    out.sort(key=lambda x: x["total_aum"], reverse=True)
    return out
