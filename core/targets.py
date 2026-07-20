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

    # persisted position-history verdicts (sec_filings.refresh_holder_histories). Absent until
    # that pass has been run for this client, in which case the fields stay None — never guessed.
    hist_by_cik = sec_filings.get_holder_histories(tk, client_id=cid)

    out = []
    for h in holders:
        known = bool(h.get("size_known"))
        shares = h.get("shares") if known else None
        value = h.get("value") if known else None
        book_total = h.get("book_total") or None
        book_pct = (value / book_total * 100) if (value and book_total) else None

        contact = by_cik.get(contacts_mod.norm_cik(h.get("cik"))) if include_contacts else None
        hist = hist_by_cik.get(contacts_mod.norm_cik(h.get("cik"))) or {}
        out.append({
            "Fund": h.get("filer"),
            "cik": h.get("cik"),
            # CUSIP is the exact key for looking this position up in ANY filer's info table —
            # matching on the ticker breaks for issuers whose name doesn't contain it
            # ("SARO" is nowhere in "STANDARDAERO INC"), and fails silently when it does.
            "cusip": h.get("cusip"),
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
            # Position history — the add/trim/new/exit read. Present once refresh_holder_histories
            # has run; None before that. "new" and "exited" matter as much as the net change: a
            # holder who sat at zero for four quarters and then bought is the strongest IR signal
            # there is, and reporting that as no-data buries it.
            "Direction": hist.get("direction"),
            "Net_Change_Shares": hist.get("net_change_shares"),
            "QoQ_Change_Shares": hist.get("qoq_change_shares"),
            "Quarters_Held": hist.get("quarters_held"),
            "Held_Since_At_Least": hist.get("held_since_at_least"),
            "Continuous_Holder": hist.get("continuous"),
            "Peer_Overlap": hist.get("peer_overlap"),
            "History_As_Of": hist.get("as_of"),
            # No source yet — returned as None so nothing downstream invents a number.
            "QoQ_Change": None,                 # legacy field; use QoQ_Change_Shares
            "IR_Visits_30d": None,              # web analytics: no source
            "Visit_Score": None,                # ditto
            "Call_Score": None,                 # q2_listeners is a set, not a score
            "Call_Listener": None,
        })

    out.sort(key=lambda r: (r["Position_Value"] or 0), reverse=True)
    return out


# Direction -> the IR action it implies. A trimming holder is the most urgent call in the book;
# a new position is the warmest. Derived from a real filing trail, not asserted.
_ACTION_BY_DIRECTION = {
    "new": "New position — engage now",
    "adding": "Adding — deepen the relationship",
    "trimming": "Trimming — find out what changed",
    "exited": "Exited — win-back candidate",
    "flat": "Flat — maintain coverage",
}
# Conviction -> coverage priority (1 = highest). A documented mapping of Book_Pct tiers.
_PRIORITY_BY_CONVICTION = {"Core": 1, "Meaningful": 2, "Small": 3, "Index-scale": 4}


def _fmt_aum(v):
    if not v:
        return None
    if v >= 1e9:
        return f"${v / 1e9:.1f}B"
    if v >= 1e6:
        return f"${v / 1e6:.0f}M"
    return f"${v:,.0f}"


def targets_as_institutions(client_id=None, ticker=None):
    """The real 13F target universe in the record shape the Investor Targeting page expects.

    A compatibility layer, deliberately: investors_page and investor_scoring were written against
    data/seed/buyside_institutions.py, and rewriting every consumer at once is how you break a
    client-facing page. This maps real filing data onto those keys and leaves the unmeasurable ones
    None — Call_Score, Visit_Score, IR_Visits_30d and Call_Listener have no source without website
    analytics or a call-listener feed, so scoring omits them rather than scoring them zero."""
    rows = targets_from_13f(client_id=client_id, ticker=ticker)
    out = []
    for r in rows:
        cik = (r.get("cik") or "").lstrip("0")
        out.append({
            "Fund": r["Fund"],
            "cik": r.get("cik"),
            "Type": None,
            "AUM": _fmt_aum(r.get("Book_Total")),
            "Coverage_Priority": _PRIORITY_BY_CONVICTION.get(r.get("Conviction"), 4),
            # the page's holder flag is named for the original single tenant; it means "holds us"
            "USIO_Holder": True,
            "Shares": r.get("Shares"),
            "QoQ_Change": r.get("QoQ_Change_Shares"),
            "Position_Value": r.get("Position_Value"),
            "Book_Pct": r.get("Book_Pct"),
            "Conviction": r.get("Conviction"),
            "Direction": r.get("Direction"),
            "Net_Change_Shares": r.get("Net_Change_Shares"),
            "Held_Since_At_Least": r.get("Held_Since_At_Least"),
            "Peer_Holdings": r.get("Peer_Overlap") or [],
            "Peer_Holdings_Source": "SEC 13F",
            "Metro": r.get("Metro"),
            "Action": _ACTION_BY_DIRECTION.get(r.get("Direction"), "No history pulled yet"),
            # "SEC 13F" matches _sec_universe_records' tag, so _merge_sec_universe recognises these
            # as already-SEC-sourced instead of relabelling them "Seed + SEC-confirmed".
            "Source": "SEC 13F",
            "link": (f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}"
                     f"&type=13F&dateb=&owner=include&count=40") if cik else None,
            "Contact_Name": r.get("Contact_Name"),
            "Contact_Title": r.get("Contact_Title"),
            "Contact_Email": r.get("Contact_Email"),
            "Contact_Phone": r.get("Contact_Phone"),
            # No source — left None so scoring omits them instead of scoring a fabricated zero.
            "Call_Score": None, "Peer_Score": None, "Visit_Score": None,
            "Call_Listener": None, "Listen_Duration": None, "IR_Visits_30d": None,
            "Last_Visit": None, "Turnover_Style": None, "Ownership_Style": None,
        })
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
