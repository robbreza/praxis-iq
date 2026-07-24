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
_TIGHT_FALLBACK = {"RPAY", "CASS", "CSGS", "PSFE", "PAY"}


def tight_comps(cid=None):
    """The client's CLOSEST comps — holding one of these is the highest-conviction
    signal, and the prospect score weights them accordingly.

    Derived from the client's own peer set (tiers 'core'/'close'). This was a
    hardcoded USIO ticker list, so every other tenant scored zero tight-comp points
    for every prospect — the strongest component of the model was silently dead for
    them. Falls back to the original list only if a client defines no peer tiers."""
    try:
        tight = {(p.get("ticker") or "").upper() for p in CP()
                 if p.get("tier") in ("core", "close") and p.get("ticker")}
        if tight:
            return tight
    except Exception:
        pass
    return set(_TIGHT_FALLBACK)
_DECISIONS_KEY = "peer_prospect_decisions.json"

# ─────────────────────────────────────────────────────────────────────────
# Two DIFFERENT kinds of "big holder", split because they warrant different
# treatment. The old code lumped them together and DROPPED both on the
# assumption that they "never take a micro-cap NDR" — which is wrong as IR
# practice. A large fund may not chase a meeting, but if you're already in
# their city and they own you or a comp, they'll usually take one; and analysts
# there often WANT to meet a non-held competitor for candid industry colour.
# So these are now bucketed for review, not discarded.
#
# _MARKET_MAKER is the genuine exception: HFT/prop/ETF-mechanics books hold
# inventory with no fundamental PM on the other side of the table, so there is
# nobody to meet. They get their own bucket rather than vanishing silently.
_MARKET_MAKER = [
    "susquehanna", "two sigma", "jane street", "millennium", "d e shaw", "de shaw",
    "optiver", "imc ", "imc b.v.", "flow traders", "virtu", "drw ", "jump trading",
    "hudson river trading", "tower research", "xtx ", "quantbot", "gamma investing",
    "squarepoint", "headlands technologies", "citadel", "renaissance tech",
    # ETF issuers — the holding is index mechanics, not a PM's decision
    "themes management", "global x", "first trust", "wisdomtree", "vaneck",
    "direxion", "proshares", "exchange traded concepts",
]

# _DIVERSIFIED — index families and bank/brokerage asset-management arms. These
# DO have active fundamental PMs (Fidelity's active funds, Capital Group, GSAM,
# MSIM, JPMAM, Nuveen, Invesco active). Bucketed for review, never dropped.
_DIVERSIFIED = [
    # Index / passive / mega-diversified
    "vanguard", "blackrock", "state street", "geode", "northern trust",
    "charles schwab investment", "dimensional fund", "invesco", "nuveen",
    "teachers advisors", "fmr llc", "geode capital", "legal & general",
    "legal and general",
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


def is_market_maker(name):
    """True for HFT / prop / ETF-mechanics books. These hold the name as inventory with no
    fundamental PM on the other side, so there is genuinely nobody to meet — the one group where
    "won't take a meeting" is a fact about the business model, not an assumption about size."""
    lo = _lower(name)
    return any(p in lo for p in _MARKET_MAKER)


def is_diversified(name):
    """True for index families and bank/brokerage asset-management arms (Fidelity, Capital Group,
    Invesco, Nuveen, GSAM, MSIM, JPMAM...).

    These are NOT dropped. They run active fundamental strategies with real PMs, and IR practice is
    that a large holder who won't chase a meeting will usually take one if you're already in their
    city and they own you or a comp — analysts there often want to meet a non-held competitor for
    candid industry colour. They go to a review bucket so the IR lead decides, not the filter."""
    lo = _lower(name)
    return any(p in lo for p in _DIVERSIFIED)


def is_passive(name):
    """Back-compat: either kind of big book. Retained because core.prospecting's coverage-network
    pipeline calls it. Prefer is_market_maker() / is_diversified() — they mean different things and
    warrant different treatment."""
    return is_market_maker(name) or is_diversified(name)


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


# ─────────────────────────────────────────────────────────────────────────
# CLIENT-SIZE-AWARE GATES
#
# Every threshold here is relative to the CLIENT's market cap, because "too big and diversified to
# bother meeting us" is meaningless in the abstract. Calibrating once for a $61M micro-cap (USIO)
# and applying it to an $8.9B issuer (SARO) is what pushed Fidelity and Capital Group into a review
# bucket for a company they would unambiguously take a meeting with.
#
# tier: (max_market_cap_m, breadth_max, diversified_are_targets, breadth_bands, prefer_small_books)
#   breadth_max            — position count above which a book goes to review (None = no gate)
#   diversified_are_targets— True: index-family / bank-AM managers are PRIMARY NDR targets, not a
#                            review bucket. A large issuer is core holding territory for them.
#   breadth_bands          — (b1,b2,b3) scoring bands; a 400-position book is wide for a micro-cap
#                            specialist and unremarkable for a large-cap manager.
#   prefer_small_books     — micro/small caps fit best with small managers (the position can be
#                            meaningful to them). For mid/large the reverse holds: you want a
#                            manager big enough to build a real position.
_SIZE_TIERS = (
    (300,    "micro", 600,  False, (60, 150, 300),   True),
    (2000,   "small", 1200, False, (100, 250, 500),  True),
    (10000,  "mid",   3000, True,  (200, 500, 1000), False),
    (None,   "large", None, True,  (400, 1000, 2000), False),
)


def size_profile(cid=None):
    """Gate settings for this client, derived from its market cap. Falls back to the micro-cap
    profile when no market cap is on record — the conservative choice, since it filters hardest."""
    try:
        mcap = float(CT("market_cap_m") or 0)
    except (TypeError, ValueError):
        mcap = 0
    for cap, tier, breadth_max, div_targets, bands, prefer_small in _SIZE_TIERS:
        if cap is None or mcap < cap:
            return {"tier": tier, "market_cap_m": mcap, "breadth_max": breadth_max,
                    "diversified_are_targets": div_targets, "breadth_bands": bands,
                    "prefer_small_books": prefer_small, "has_market_cap": mcap > 0}
    return {"tier": "micro", "market_cap_m": mcap, "breadth_max": 600,
            "diversified_are_targets": False, "breadth_bands": (60, 150, 300),
            "prefer_small_books": True, "has_market_cap": mcap > 0}


def _score(r, size_rank, profile=None):
    """0–100 conviction. size_rank in [0,1], 1 = smallest book.

    Breadth banding and the size-fit direction both come from the client's size profile: a wide
    book is a negative for a micro-cap and normal for a large-cap, and "smallest manager wins" is
    only true when the issuer is small enough for a small manager to move the needle."""
    profile = profile or size_profile()
    b1, b2, b3 = profile["breadth_bands"]
    conc = (r["peer_value"] / r["book_total"]) if r.get("book_total") else 0
    s = min(conc * 1200, 45)                                   # conviction (0–45)
    tight = sum(1 for c in r["comps"].values() if c["tight"])
    s += {0: 0, 1: 12, 2: 20}.get(tight, 25)                  # focus on close comps (0–25)
    bp = r.get("book_positions") or 0
    s += 0 if not bp else (20 if bp < b1 else 14 if bp < b2 else 8 if bp < b3 else 3)  # breadth (0–20)
    # Size fit (0–10): smallest-is-best for a micro/small cap, largest-is-best above that.
    s += (size_rank if profile["prefer_small_books"] else (1 - size_rank)) * 10
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
    profile = size_profile(cid)          # gates scale with THIS client's market cap
    sup_names, sup_ciks = _suppressed(cid)
    decisions = db.load_json(_DECISIONS_KEY, {}, client_id=cid) or {}

    _tight = tight_comps(cid)
    cand = {}
    for p in prospecting:
        tkr = p["ticker"]
        tight = tkr in _tight
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
    kept, rias, diversified, makers = [], [], [], []
    for key, r in cand.items():
        if (r["cik"] and r["cik"] in sup_ciks) or r["norm"] in sup_names:
            continue
        dec = decisions.get(key, {}).get("decision")
        if dec == "dismissed" and not include_dismissed:
            continue
        r["decision"] = dec
        # Market makers: no fundamental PM to meet. Bucketed, not silently dropped.
        if is_market_maker(r["filer"]):
            r["kind"] = "market_maker"
            makers.append(r)
            continue
        # Large diversified / bank AM arms: they DO have active PMs. Whether they're a primary
        # target or a review bucket depends on the CLIENT's size — for a mid/large-cap issuer these
        # are core holding territory and belong in the main NDR list; for a micro-cap they're a
        # judgement call the IR lead should make.
        if is_diversified(r["filer"]):
            if profile["diversified_are_targets"]:
                r["kind"] = "institutional"
                r["diversified_house"] = True
                kept.append(r)
            else:
                r["kind"] = "diversified"
                diversified.append(r)
            continue
        if is_ria(r["filer"]):
            # RIA/wealth bucket — video-call tier, not an NDR target. NO breadth
            # gate here: an RIA holding thousands of positions is normal (that's
            # what a wealth platform looks like), so breadth says nothing about
            # them. Only include a name backed by a real position.
            if (r.get("peer_value") or 0) > 0:
                r["kind"] = "ria"
                rias.append(r)
            continue
        _breadth_max = profile["breadth_max"]
        if _breadth_max is not None and (r.get("book_positions") or 0) > _breadth_max:
            # Breadth alone is NOT disqualifying. This cliff was dropping the largest peer
            # positions in the universe — Capital World Investors (Capital Group) at $107M runs
            # ~620 positions, Clearbridge $80M at 794, Ensign Peak $136M at 1,708. A wide book is
            # what a large active manager looks like, not evidence they won't meet. Bucket it.
            r["kind"] = "diversified"
            r["broad_book"] = True
            diversified.append(r)
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

    if kind in ("diversified", "market_maker"):
        # Review buckets. Not conviction-scored — these aren't ranked against the NDR target list;
        # the IR lead reviews them and promotes anyone worth a meeting. Ranked by how much of the
        # peer group they actually own, which is what makes one worth the call.
        bucket = diversified if kind == "diversified" else makers
        for r in bucket:
            r["tight_comps"] = sum(1 for c in r["comps"].values() if c["tight"])
            r["n_comps"] = len(r["comps"])
            r["concentration"] = (r["peer_value"] / r["book_total"]) if r.get("book_total") else None
            r["conviction"] = None
            r["promoted"] = r.get("decision") == "promoted"
        bucket.sort(key=lambda r: (-int(r["promoted"]), -(r["peer_value"] or 0)))
        return bucket[:limit] if limit else bucket

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
        r["conviction"] = _score(r, _size_rank(r.get("book_total")), profile)
        r["promoted"] = r.get("decision") == "promoted"

    _key = _SORTS.get(sort, _SORTS["conviction"])
    kept.sort(key=lambda r: (-int(r["promoted"]), _key(r)))
    return kept[:limit] if limit else kept


def all_candidates(cid=None):
    """Every qualified peer-owner across ALL buckets — institutional, RIA/wealth, diversified, and
    market-maker — each tagged with its `tier`. The complete "who owns the peer set but not us"
    universe, for a unified view. Deduped by key (a fund lands in one bucket, but guard anyway).

    Hand-curated targets (core.curated_targets — accounts you know are a fit but that don't hold a
    peer today, e.g. a Geneva/Lugano private bank) are folded in last, tagged tier='Curated', but
    ONLY if the name isn't already a real holder or a derived prospect, so nothing double-lists."""
    cid = cid or get_active_client_id()
    out, seen, seen_norms = [], set(), set()
    for kind, tier in [("institutional", "Institutional"), ("ria", "RIA / wealth"),
                       ("diversified", "Diversified"), ("market_maker", "Market maker")]:
        for c in build_candidates(cid, limit=None, kind=kind):
            k = c.get("key")
            if k in seen:
                continue
            seen.add(k)
            seen_norms.add(c.get("norm"))
            c = dict(c)
            c["tier"] = tier
            out.append(c)

    # Curated overlay — suppress any that already appear as a real holder (13F/NOBO/tracked/13D-G)
    # or as a derived prospect above, so a curated name that later starts holding a comp collapses
    # into its evidence-backed row rather than showing twice.
    try:
        from core import curated_targets
        sup_names, _ = _suppressed(cid)
        for c in curated_targets.merged(cid):
            nk = c.get("norm") or _norm(c.get("filer", ""))
            if not nk or nk in seen_norms or nk in sup_names:
                continue
            seen_norms.add(nk)
            out.append(c)
    except Exception:
        pass
    return out


def counts(cid=None):
    """Headline counts for the review surface."""
    cid = cid or get_active_client_id()
    from core import db
    decisions = db.load_json(_DECISIONS_KEY, {}, client_id=cid) or {}
    active = build_candidates(cid, limit=None)
    return {
        "candidates": len(active),
        "rias": len(build_candidates(cid, limit=None, kind="ria")),
        "diversified": len(build_candidates(cid, limit=None, kind="diversified")),
        "market_makers": len(build_candidates(cid, limit=None, kind="market_maker")),
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
    _norm_name = candidate.get("norm") or _norm(candidate.get("filer", ""))
    if not any(_norm(p.get("fund", "")) == _norm_name for p in plist):
        metro = ", ".join(x for x in [candidate.get("city"), candidate.get("state")] if x) or "Unknown (SEC)"
        comps = ", ".join(sorted(candidate["comps"].keys()))
        ria = candidate.get("kind") == "ria"
        curated = candidate.get("kind") == "curated"
        if curated:
            style = "Curated target — " + (candidate.get("rationale") or "known account, relationship-sourced")
            source = "Curated" + (f" ({candidate.get('scope')})" if candidate.get("scope") else "")
        else:
            style = ("RIA / wealth manager — holds " if ria else "Holds ") + comps
            source = "Peer overlap (13F)" + (" — RIA" if ria else "")
        rec = {
            "fund": candidate["filer"], "metro": metro,
            "style": style,
            # RIAs and curated targets aren't conviction-scored, so fall back to 0
            # rather than int(None) — they're ranked by position size / by hand.
            "score": int(candidate["conviction"]) if candidate.get("conviction") is not None else 0,
            "outcome": None,
            "source": source,
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
