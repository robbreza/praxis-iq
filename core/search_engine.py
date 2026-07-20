"""
core/search_engine.py — cross-database search for the global header search box.

One query, every database the platform holds: the tracked buy-side universe and
manually-added prospects (by fund name, contact, metro, style, holder status),
NOBO beneficial owners, SEC 13F institutional holders, and sell-side analysts /
their firms. Pure compute — the header UI (app_nicegui.render_header_search)
renders the ranked results and each one deep-links to where that record lives.

Returns a flat, ranked list of result dicts so the header can group them by
`type`; per-source caps keep one large table (NOBO has hundreds of rows) from
crowding out the rest. `prefill` is the string the destination surface should
pre-search on arrival (Target Database reads it via nav.highlights).
"""

from config.client_config import CA, CT, get_active_client_id

# Per-source cap before ranking — enough to be useful, not so many that a common
# word ("capital", "partners") floods the dropdown from the 300+ NOBO rows.
_CAP = 6
_MIN_QUERY = 2


def _score(q, text):
    """Rank: exact match, then prefix, then word-start, then anywhere."""
    t = (text or "").lower()
    if not t:
        return 0
    if t == q:
        return 100
    if t.startswith(q):
        return 80
    if any(w.startswith(q) for w in t.split()):
        return 60
    return 40


def _result(kind, label, sub, section, tab, prefill=None, score=40):
    return {"type": kind, "label": label, "sublabel": sub,
            "section": section, "tab": tab, "prefill": prefill, "score": score}


def _fund_results(q, cid):
    # Real 13F holders + their real contacts, not the fabricated buyside seed — global search is on
    # every page (a client can use it), so seed names here surfaced demo funds/people to clients.
    from core import targets
    out = []
    for i in targets.targets_as_institutions(client_id=cid):
        fund = i.get("Fund", "")
        hay = " ".join([fund, i.get("Metro") or "", i.get("Contact_Name") or "",
                        i.get("Contact_Email") or "", i.get("Contact_Title") or ""]).lower()
        if q in hay:
            sub = f"{i.get('Metro', '')} · {'Holder' if i.get('USIO_Holder') else 'Non-holder'}"
            if i.get("Contact_Name"):
                sub += f" · {i['Contact_Name']}"
            out.append(_result("Fund", fund, sub, "Investors", "Target Database",
                               prefill=fund, score=_score(q, fund) if q in fund.lower() else 45))
    return out


def _prospect_results(q, cid):
    from core import db
    out = []
    for p in db.load_json("prospects.json", [], client_id=cid):
        fund = p.get("fund", "")
        hay = " ".join([fund, p.get("metro", ""), p.get("style", "")]).lower()
        if q in hay:
            out.append(_result("Prospect", fund,
                               f"{p.get('metro', '—')} · {p.get('style', '—')} · prospect",
                               "Investors", "Target Database", prefill=fund,
                               score=_score(q, fund) if q in fund.lower() else 45))
    return out


def _nobo_results(q, cid):
    from core import nobo_engine
    try:
        holders = nobo_engine.get_active_pulls(cid)["current"]["holders"]
    except Exception:
        return []
    out = []
    for h in holders:
        name = h.get("name", "")
        hay = " ".join([name, h.get("city", ""), h.get("state", ""), h.get("type", "")]).lower()
        if q in hay:
            out.append(_result("NOBO holder", name,
                               f"{h.get('type', '')} · {h.get('city', '')}, {h.get('state', '')} · "
                               f"{h.get('shares', 0):,} sh",
                               "Investors", "NOBO Ownership", score=_score(q, name) if q in name.lower() else 45))
    return out


def _f13_results(q):
    try:
        from core import sec_filings
        holders = sec_filings.get_cached_13f_holders(CT("ticker")).get("holders", [])
    except Exception:
        return []
    out = []
    for h in holders:
        filer = h.get("filer", "")
        hay = " ".join([filer, h.get("city", ""), h.get("state", "")]).lower()
        if q in hay:
            out.append(_result("13F holder", filer,
                               f"SEC 13F · {h.get('city', '')}, {h.get('state', '')} · {h.get('shares', 0):,} sh",
                               "Investors", "SEC Intelligence", score=_score(q, filer) if q in filer.lower() else 45))
    return out


def _analyst_results(q):
    out = []
    for a in CA():
        hay = " ".join([a.get("name", ""), a.get("firm", ""), a.get("email", "")]).lower()
        if q in hay:
            status = "active" if a.get("status") == "active" else "inactive"
            pt = f"${a['pt']:.2f} PT" if a.get("pt") else "no PT"
            out.append(_result("Analyst", a.get("name", ""), f"{a.get('firm', '')} · {pt} · {status}",
                               "Markets", "Consensus / Guidance", score=_score(q, a.get("name", ""))))
    return out


def search(query, client_id=None):
    """Ranked cross-database matches for `query`. Empty list for a query under
    two characters. Each source is capped and de-duplicated, then everything is
    ranked together so the strongest matches (exact / prefix) lead."""
    q = (query or "").strip().lower()
    if len(q) < _MIN_QUERY:
        return []
    cid = client_id or get_active_client_id()

    results = []
    for group in (_fund_results(q, cid), _prospect_results(q, cid), _nobo_results(q, cid),
                  _f13_results(q), _analyst_results(q)):
        group.sort(key=lambda r: -r["score"])
        results.extend(group[:_CAP])

    # De-dupe identical (type, label) rows, keep the highest score.
    seen = {}
    for r in results:
        key = (r["type"], r["label"].lower())
        if key not in seen or r["score"] > seen[key]["score"]:
            seen[key] = r
    return sorted(seen.values(), key=lambda r: -r["score"])
