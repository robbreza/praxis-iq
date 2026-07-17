"""
core/peer_prospects.py — high-conviction peer-overlap prospect candidates.

Turns the raw "owns a comp, not USIO" 13F pool (hundreds of names, mostly
index/passive noise) into a short, explainable, false-positive-filtered list of
*active, appropriately-sized* managers worth an NDR — each shown with its
evidence and gated behind a promote/dismiss review so nothing enters the pipeline
unvetted.

Noise control (rank by conviction, not dollars):
  • concentration — the payments-comp position as a share of the fund's whole
    13F book (a 3% Repay bet beats Vanguard's 0.001%);
  • focus on the TIGHT comps (Repay/Cass/CSG/Paysafe/Paymentus), not the sector;
  • breadth — fewer holdings ⇒ active manager, not a quasi-index book;
  • size fit — smaller books rank higher (a $500B manager can't move on a micro-cap).

False-positive control:
  • suppress anyone already ours — USIO's 13F holders, NOBO owners, the tracked
    universe, and 13D/G filers (so a sub-threshold or NOBO-only holder isn't
    mis-flagged as a prospect);
  • de-dupe by CIK (SEC's unique filer id), not by name;
  • drop pure passive/market-maker books outright;
  • every candidate carries its evidence + filing date so a bad one costs a glance.
"""

from datetime import datetime

from config.client_config import CP, CT, get_active_client_id

# Closest small/mid-cap payment comps — holding these is the highest signal.
_TIGHT = {"RPAY", "CASS", "CSGS", "PSFE", "PAY"}
_DECISIONS_KEY = "peer_prospect_decisions.json"

# Pure passive / index / market-maker / mega-diversified books — they hold
# ~everything and never take a micro-cap NDR. Substring match on the lowercased
# filer name; the breadth filter catches the rest generically.
_PASSIVE = [
    # Index / passive / mega-diversified
    "vanguard", "blackrock", "state street", "geode", "northern trust",
    "charles schwab investment", "dimensional fund", "invesco", "nuveen",
    "teachers advisors", "fmr llc", "geode capital", "legal & general",
    "legal and general",
    # Market makers / HFT / prop — hold everything as inventory, never take an NDR
    "susquehanna", "citadel", "two sigma", "renaissance tech", "jane street",
    "millennium", "d e shaw", "de shaw", "optiver", "imc ", "imc b.v.",
    "flow traders", "virtu", "drw ", "jump trading", "hudson river trading",
    "tower research", "xtx ", "quantbot", "gamma investing", "squarepoint",
    "headlands technologies",
    # ETF issuers — the holding is index mechanics, not a PM's decision
    "themes management", "global x", "first trust", "wisdomtree", "vaneck",
    "direxion", "proshares", "exchange traded concepts",
    # Banks / brokerages
    "morgan stanley", "goldman sachs", "jpmorgan", "jp morgan", "bank of america",
    "wells fargo", "royal bank of canada", "bnp paribas", "ubs ", "deutsche bank",
    "barclays", "citigroup", "bnym", "bank of new york",
]

# RIA aggregators / wealth managers. Split OUT of _PASSIVE deliberately: these
# are not noise to throw away — they genuinely own the stock, they're just not
# NDR targets (they hold via client accounts, so there's no PM to pitch). They
# get their own bucket so the IR lead can see who owns adjacent names through
# the retail/advisory channel without polluting the institutional target list.
_RIA_NAMES = [
    "focus financial", "newedge advisors", "captrust", "creative planning",
    "mariner wealth", "kestra", "cetera", "lpl financial", "osaic",
    "commonwealth equity", "avantax", "ameriprise", "edward jones",
    "stifel", "raymond james financial services", "pnc financial services",
    "corient", "motley fool wealth",
]

# Real institutional managers whose LEGAL name trips a generic RIA pattern.
# Checked first — an allowlist hit always wins. This exists because "Massachusetts
# Financial Services Co /MA/" is MFS Investment Management, a top-tier
# institutional manager, not a wealth shop; a pure pattern match buried it.
_INSTITUTIONAL_ALLOW = [
    "massachusetts financial services",   # MFS Investment Management
    "fiduciary management",               # FMI
    "eagle asset management",
    "brandywine global investment",
]

# Generic name patterns that mark a retail wealth/advisory shop rather than an
# institutional manager. Caught the long tail the named list can't enumerate
# (Arcadia Wealth Management, TCI Wealth Advisors, Summit Financial Strategies…).
# Kept narrow on purpose — "capital management" / "asset management" are NOT here,
# since that's what real institutional PMs are called.
_RIA_PATTERNS = [
    "wealth management", "wealth advisors", "wealth advisers", "wealth partners",
    "wealth strategies", "wealth group", "wealth services", "private wealth",
    "wealth llc", "financial strategies", "financial advisors",
    "financial advisers", "financial planning", "financial network",
    "advisory services",
    # NOTE: "financial services" is deliberately NOT a pattern — it swept up
    # Massachusetts Financial Services (MFS). Firms like PNC that genuinely
    # belong here are named explicitly in _RIA_NAMES instead.
]

# Corporate-form suffixes stripped for cross-source name matching, so
# "PERKINS INVESTMENT MGMT" (SEC) matches "Perkins Investment Management" (seed).
_SUFFIXES = {"inc", "incorporated", "llc", "lp", "llp", "corp", "corporation", "co",
             "company", "ltd", "limited", "plc", "trust", "sa", "ag", "nv", "the",
             "group", "holdings", "mgmt"}


def _norm(n):
    toks = "".join(c if c.isalnum() else " " for c in str(n).lower()).split()
    return "".join(t for t in toks if t not in _SUFFIXES)


def _lower(n):
    return " ".join(str(n).lower().split())


def is_passive(name):
    """True if a filer is an index/passive book, market maker, bank, or ETF
    issuer — it holds the name as inventory or index mechanics, so it's never a
    target and is dropped outright. Public because core.prospecting's
    coverage-network pipeline shares this denylist; one list governs both
    prospect surfaces.

    NOTE: RIAs/wealth managers are NOT here — see is_ria()."""
    lo = _lower(name)
    return any(p in lo for p in _PASSIVE)


def is_ria(name):
    """True if a filer is an RIA / wealth manager / advisory platform. These own
    real positions but aren't institutional NDR targets, so callers bucket them
    separately rather than dropping them (see is_passive() for the drop list).

    The allowlist is checked first so a real institutional manager can never be
    demoted by a generic name pattern."""
    lo = _lower(name)
    if any(a in lo for a in _INSTITUTIONAL_ALLOW):
        return False
    return any(p in lo for p in _RIA_NAMES) or any(p in lo for p in _RIA_PATTERNS)


def is_excluded(name):
    """Everything that shouldn't appear in an institutional prospect list —
    passive/market-maker noise AND RIA/wealth shops. Used by surfaces that don't
    keep a separate RIA bucket."""
    return is_passive(name) or is_ria(name)


# Back-compat alias for existing internal call sites (peer prospects has no RIA
# bucket, so its filter keeps the original all-in-one behaviour).
_is_passive = is_excluded


def _suppressed(cid):
    """Normalized names + CIKs of everyone already ours, so a fund that already
    owns USIO (even sub-13F-threshold or NOBO-only) is never flagged a prospect."""
    from core import sec_filings, nobo_engine
    from data.seed.buyside_institutions import get_seed_buyside_institutions
    names, ciks = set(), set()
    tk = CT("ticker")
    for h in sec_filings.get_cached_13f_holders(tk).get("holders", []):
        if h.get("filer"):
            names.add(_norm(h["filer"]))
        if h.get("cik"):
            ciks.add(str(h["cik"]).lstrip("0"))
    try:
        for h in nobo_engine.get_active_pulls(cid)["current"]["holders"]:
            if h.get("name"):
                names.add(_norm(h["name"]))
    except Exception:
        pass
    for i in get_seed_buyside_institutions(cid):
        names.add(_norm(i["Fund"]))
    try:
        for f in sec_filings.get_cached_13d_13g(tk, refresh_if_stale=False).get("filings", []):
            nm = f.get("filer") or f.get("name")
            if nm:
                names.add(_norm(nm))
    except Exception:
        pass
    return names, ciks


def _score(r, size_rank):
    """0–100 conviction. size_rank in [0,1], 1 = smallest book (best micro-cap fit)."""
    conc = (r["peer_value"] / r["book_total"]) if r.get("book_total") else 0
    s = min(conc * 1200, 45)                                   # conviction (0–45)
    tight = sum(1 for c in r["comps"].values() if c["tight"])
    s += {0: 0, 1: 12, 2: 20}.get(tight, 25)                  # focus on close comps (0–25)
    bp = r.get("book_positions") or 0
    s += 0 if not bp else (20 if bp < 60 else 14 if bp < 150 else 8 if bp < 300 else 3)  # breadth (0–20)
    s += size_rank * 10                                        # micro-cap fit (0–10)
    return round(min(s, 100), 1)


_SORTS = {
    "conviction": lambda r: -r["conviction"],
    "size": lambda r: -(r["peer_value"] or 0),
    "concentration": lambda r: -((r.get("concentration") or 0)),
}


def build_candidates(cid=None, limit=40, include_dismissed=False, sort="conviction",
                     kind="institutional"):
    """Ranked, filtered, evidence-bearing peer-overlap candidates. `sort` flips
    the ranking between conviction (default), raw 13F position size, and
    concentration; promoted names always float to the top.

    kind="institutional" (default) → real NDR targets, conviction-scored.
    kind="ria" → the RIA/wealth bucket: firms that genuinely own the peers but
    have no PM to pitch (video-call tier), ranked by position size. They were
    previously discarded entirely."""
    from core import db, sec_filings
    cid = cid or get_active_client_id()
    prospecting = [p for p in CP() if p.get("tier") != "reference"]
    sup_names, sup_ciks = _suppressed(cid)
    decisions = db.load_json(_DECISIONS_KEY, {}, client_id=cid) or {}

    cand = {}
    for p in prospecting:
        tkr = p["ticker"]
        tight = tkr in _TIGHT
        for h in sec_filings.get_cached_13f_holders(tkr).get("holders", []):
            name = (h.get("filer") or "").strip()
            if not name:
                continue
            cik = str(h.get("cik") or "").lstrip("0")
            key = cik or _norm(name)
            r = cand.get(key)
            if not r:
                r = cand[key] = {
                    "key": key, "cik": cik, "filer": name, "norm": _norm(name),
                    "city": h.get("city"), "state": h.get("state"), "comps": {},
                    "peer_value": 0, "book_total": h.get("book_total"),
                    "book_positions": h.get("book_positions"), "file_date": h.get("file_date"),
                }
            r["comps"][tkr] = {"value": h.get("value") or 0, "shares": h.get("shares") or 0, "tight": tight}
            r["peer_value"] += h.get("value") or 0
            if h.get("book_total") and (not r["book_total"] or h["book_total"] > r["book_total"]):
                r["book_total"], r["book_positions"] = h["book_total"], h.get("book_positions")

    # Filter: suppress existing holders, drop passive/market-makers outright,
    # route RIAs to their own bucket, drop extreme-breadth quasi-index books and
    # dismissed decisions.
    kept, rias = [], []
    for key, r in cand.items():
        if (r["cik"] and r["cik"] in sup_ciks) or r["norm"] in sup_names:
            continue
        if is_passive(r["filer"]):
            continue
        dec = decisions.get(key, {}).get("decision")
        if dec == "dismissed" and not include_dismissed:
            continue
        r["decision"] = dec
        if is_ria(r["filer"]):
            # RIA/wealth bucket — video-call tier, not an NDR target. NO breadth
            # gate here: an RIA holding thousands of positions is normal (that's
            # what a wealth platform looks like), so breadth says nothing about
            # them. Only include a name backed by a real position.
            if (r.get("peer_value") or 0) > 0:
                r["kind"] = "ria"
                rias.append(r)
            continue
        if (r.get("book_positions") or 0) > 600:
            continue
        r["kind"] = "institutional"
        kept.append(r)

    if kind == "ria":
        for r in rias:
            r["tight_comps"] = sum(1 for c in r["comps"].values() if c["tight"])
            r["n_comps"] = len(r["comps"])
            r["concentration"] = (r["peer_value"] / r["book_total"]) if r.get("book_total") else None
            r["conviction"] = None          # not scored — these aren't ranked as targets
            r["promoted"] = r.get("decision") == "promoted"
        # Position size is the only thing that makes one of these worth a call.
        rias.sort(key=lambda r: (-int(r["promoted"]), -(r["peer_value"] or 0)))
        return rias[:limit] if limit else rias

    # Relative size fit — smallest book ⇒ rank 1.0 (best for a micro-cap).
    books = sorted([r["book_total"] for r in kept if r.get("book_total")])
    def _size_rank(bt):
        if not bt or not books:
            return 0.5
        below = sum(1 for b in books if b > bt)
        return below / len(books)

    for r in kept:
        r["tight_comps"] = sum(1 for c in r["comps"].values() if c["tight"])
        r["n_comps"] = len(r["comps"])
        r["concentration"] = (r["peer_value"] / r["book_total"]) if r.get("book_total") else None
        r["conviction"] = _score(r, _size_rank(r.get("book_total")))
        r["promoted"] = r.get("decision") == "promoted"

    _key = _SORTS.get(sort, _SORTS["conviction"])
    kept.sort(key=lambda r: (-int(r["promoted"]), _key(r)))
    return kept[:limit] if limit else kept


def counts(cid=None):
    """Headline counts for the review surface."""
    cid = cid or get_active_client_id()
    from core import db
    decisions = db.load_json(_DECISIONS_KEY, {}, client_id=cid) or {}
    active = build_candidates(cid, limit=None)
    return {
        "candidates": len(active),
        "rias": len(build_candidates(cid, limit=None, kind="ria")),
        "promoted": sum(1 for v in decisions.values() if v.get("decision") == "promoted"),
        "dismissed": sum(1 for v in decisions.values() if v.get("decision") == "dismissed"),
    }


def _set_decision(key, decision, cid):
    from core import db
    d = db.load_json(_DECISIONS_KEY, {}, client_id=cid) or {}
    if decision is None:
        d.pop(key, None)
    else:
        d[key] = {"decision": decision, "date": datetime.now().isoformat()}
    db.save_json(_DECISIONS_KEY, d, client_id=cid)


def promote(candidate, cid=None):
    """Mark promoted and add to the manual prospect pipeline (Target Database).
    Handles both kinds: an institutional candidate carries its conviction score,
    while an RIA (conviction is None by design — they're not ranked as targets)
    is tagged into the video-call tier instead."""
    from core import db
    cid = cid or get_active_client_id()
    _set_decision(candidate["key"], "promoted", cid)
    plist = db.load_json("prospects.json", [], client_id=cid) or []
    if not any(_norm(p.get("fund", "")) == candidate["norm"] for p in plist):
        metro = ", ".join(x for x in [candidate.get("city"), candidate.get("state")] if x) or "Unknown (SEC)"
        comps = ", ".join(sorted(candidate["comps"].keys()))
        ria = candidate.get("kind") == "ria"
        rec = {
            "fund": candidate["filer"], "metro": metro,
            "style": ("RIA / wealth manager — holds " if ria else "Holds ") + comps,
            # RIAs aren't conviction-scored, so fall back to 0 rather than
            # int(None) — they're ranked by position size, not score.
            "score": int(candidate["conviction"]) if candidate.get("conviction") is not None else 0,
            "outcome": None,
            "source": "Peer overlap (13F)" + (" — RIA" if ria else ""),
        }
        if ria:
            rec["touch"] = "video-call"
            rec["outreach"] = "Video call — assistant can schedule"
        plist.append(rec)
        db.save_json("prospects.json", plist, client_id=cid)


def dismiss(key, cid=None):
    _set_decision(key, "dismissed", cid or get_active_client_id())


def reset(key, cid=None):
    _set_decision(key, None, cid or get_active_client_id())
