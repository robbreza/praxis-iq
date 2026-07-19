"""core/targets.py — the investor target universe, built from REAL 13F holders.

WHAT CHANGED AND WHY
The target database used to come from `data/seed/buyside_institutions.py`: 62 curated demo records
carrying fabricated engagement numbers (Call_Score, Visit_Score, IR_Visits_30d, Conviction). Those
numbers had no source — they were demo scaffolding that looked like analysis. This module replaces
them with the actual 13F holder universe, where every field traces to a filing.

THE HONEST-FIELD RULE
A field appears here only if it can be derived from real data. Anything without a source is
returned as None rather than invented, so a consumer can render "no data" instead of a fabricated
score. Specifically:
  * DERIVED FROM FILINGS — Fund, cik, shares, position value, book_total (the filer's whole 13F
    book, i.e. an AUM proxy), book_positions, geography, and Book_Pct.
  * JOINED — the real person behind the filer (name/title/phone/email) from core.contacts by CIK.
  * NOT AVAILABLE (None) — IR_Visits_30d and Visit_Score (web analytics: no source), Call_Score
    (partial: a live q2_listeners set exists but is not a score), QoQ_Change (needs a prior-quarter
    holder cache, which is empty until two consecutive pulls exist).

BOOK_PCT IS THE POINT
Position value / the filer's whole 13F book is the conviction signal the fabricated "Conviction:
High" was pretending to be. For SARO it separates River Road ($196.8M = ~2.2% of its $9.0B book —
a core position) from Wells Fargo ($0.6M of $530.3B — index-scale noise). Same dollar universe,
completely different IR priority. The tier labels below are a transparent bucketing of that one
real number, not a judgement layered on top of nothing.
"""
from core import contacts as contacts_mod

# Book_Pct tiers — a documented bucketing of one real number (position / filer's whole 13F book).
CONVICTION_TIERS = ((1.0, "Core"), (0.1, "Meaningful"), (0.01, "Small"), (0.0, "Index-scale"))


def conviction_tier(book_pct):
    """Label a position by how much of the holder's OWN book it represents. None if unknown —
    never guess a conviction level we can't compute."""
    if book_pct is None:
        return None
    for floor, label in CONVICTION_TIERS:
        if book_pct >= floor:
            return label
    return "Index-scale"


def _metro(holder):
    city, state = (holder.get("city") or "").strip(), (holder.get("state") or "").strip()
    if city and state:
        return f"{city.title()}, {state}"
    return city.title() or state or None


def targets_from_13f(client_id=None, ticker=None, include_contacts=True):
    """The target universe for a client: one record per real 13F holder.

    Rows that haven't been through sec_filings.enrich_holder_positions() carry no magnitude
    (size_known False); their size fields come back None rather than the 1-share/$0 sentinels, so
    a caller never mistakes a placeholder for a real position."""
    from config.client_config import CT, get_active_client_id
    from core import sec_filings

    cid = client_id or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    book = sec_filings.get_cached_13f_holders(tk) or {}
    holders = book.get("holders") or []

    # one query, indexed by CIK — not one lookup per holder
    by_cik = {}
    if include_contacts:
        for c in contacts_mod.list_contacts():
            if c.get("cik"):
                by_cik.setdefault(c["cik"], c)

    out = []
    for h in holders:
        known = bool(h.get("size_known"))
        shares = h.get("shares") if known else None
        value = h.get("value") if known else None
        book_total = h.get("book_total") or None
        book_pct = (value / book_total * 100) if (value and book_total) else None

        contact = by_cik.get(contacts_mod.norm_cik(h.get("cik"))) if include_contacts else None
        out.append({
            "Fund": h.get("filer"),
            "cik": h.get("cik"),
            "Holder": True,                     # they filed a 13F showing the position
            "Shares": shares,
            "Position_Value": value,
            "Book_Total": book_total,           # filer's whole 13F book — AUM proxy
            "Book_Positions": h.get("book_positions"),
            "Book_Pct": round(book_pct, 4) if book_pct is not None else None,
            "Conviction": conviction_tier(book_pct),
            "Metro": _metro(h),
            "Contact_Name": (contact or {}).get("name"),
            "Contact_Title": (contact or {}).get("title"),
            "Contact_Phone": (contact or {}).get("phone"),
            "Contact_Email": (contact or {}).get("email"),
            "Contact_Email_Status": (contact or {}).get("email_status"),
            "Filed": h.get("file_date"),
            "Source": "EDGAR 13F",
            # No source yet — returned as None so nothing downstream invents a number.
            "QoQ_Change": None,                 # needs a prior-quarter holder cache
            "IR_Visits_30d": None,              # web analytics: no source
            "Visit_Score": None,                # ditto
            "Call_Score": None,                 # q2_listeners is a set, not a score
            "Call_Listener": None,
        })

    out.sort(key=lambda r: (r["Position_Value"] or 0), reverse=True)
    return out


def coverage(client_id=None, ticker=None):
    """How complete the target universe is — what share of holders carry real magnitude and a
    reachable contact. Use this to decide whether targeting is ready to drive off 13F for a client
    rather than assuming it is."""
    rows = targets_from_13f(client_id=client_id, ticker=ticker)
    n = len(rows)
    sized = sum(1 for r in rows if r["Position_Value"] is not None)
    named = sum(1 for r in rows if r["Contact_Name"])
    mailed = sum(1 for r in rows if r["Contact_Email"])
    return {"holders": n, "with_position_size": sized, "with_contact": named,
            "with_email": mailed,
            "position_value_total": sum(r["Position_Value"] or 0 for r in rows)}
