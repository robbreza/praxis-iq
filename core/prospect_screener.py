"""core/prospect_screener.py — screen public companies as IRconnect SALES prospects, by metro,
industry, and sell-side analyst coverage.

Thesis (user's): a company with >5 sell-side analysts has a growing IR pain point — a prime
prospect; >15 likely already runs a competing tool. So the sweet spot is the 6-15 band.

Metro grouping reuses the NDR vocabulary (core.ndr_calendar) where it overlaps and extends it
with company-HQ metros the buy-side NDR hubs don't cover (e.g. Phoenix). Analyst counts and
firmographics (city, sector, industry, market cap) come from Yahoo via yfinance; a screen is
cached per metro so re-filtering by industry / threshold is instant.

The per-metro ticker UNIVERSE is curated + growable (stored in the DB, seedable). Reliable
enumeration of every public company by geography needs a paid data provider (Capital IQ /
bigdata connectors) — until one is authorized, the universe is a maintained list, not exhaustive.
"""
import time

import yfinance as yf

from core import db

_UNIVERSE_KEY = "prospect_universe.json"       # {metro: [tickers]} — operator-editable, seeded below
_SCREEN_KEY = "prospect_screen.json"           # {metro: {fetched_at, rows}} — cached enrichment

# Seed universe. Phoenix is fully seeded (verified pull); other metros grow as tickers are added.
_SEED_UNIVERSE = {
    "Phoenix / Arizona": [
        "FCX", "RSG", "AVT", "MCHP", "ON", "AXON", "CVNA", "NSIT", "SFM", "WAL", "AMKR", "KNX",
        "MTH", "TMHC", "FSLR", "BHE", "ROG", "VVI", "UHAL", "CVCO", "VRRM", "OPAD", "LOPE", "GWRS", "PIII",
    ],
}


def _load_universe():
    stored = db.load_json(_UNIVERSE_KEY, None)
    if stored is None:
        db.save_json(_UNIVERSE_KEY, _SEED_UNIVERSE)     # persist the seed once
        return dict(_SEED_UNIVERSE)
    return stored


def metros():
    """Metros the screener knows about — seeded/edited universes plus the NDR vocabulary
    (an NDR metro with no universe yet simply screens empty until tickers are added)."""
    from core.ndr_calendar import known_metros
    have = _load_universe()
    names = set(have) | set(known_metros())
    return sorted(names)


def tickers_for(metro):
    return list(_load_universe().get(metro, []))


def add_tickers(metro, tickers):
    """Add tickers to a metro's universe (dedup, upper-cased). Returns count added."""
    uni = _load_universe()
    cur = uni.setdefault(metro, [])
    have = {t.upper() for t in cur}
    added = 0
    for t in tickers:
        t = (t or "").strip().upper()
        if t and t not in have:
            cur.append(t)
            have.add(t)
            added += 1
    db.save_json(_UNIVERSE_KEY, uni)
    return added


def _enrich(ticker):
    """One ticker -> firmographics + analyst count from Yahoo. analysts=None on failure."""
    try:
        info = yf.Ticker(ticker).info or {}
        n = info.get("numberOfAnalystOpinions")
        return {
            "ticker": ticker,
            "name": info.get("shortName") or info.get("longName") or ticker,
            "city": info.get("city"), "state": info.get("state"),
            "sector": info.get("sector"), "industry": info.get("industry"),
            "analysts": (int(n) if n else 0) if n is not None else None,
            "market_cap": info.get("marketCap"),
        }
    except Exception:
        return {"ticker": ticker, "name": ticker, "city": None, "state": None,
                "sector": None, "industry": None, "analysts": None, "market_cap": None}


def classify(analysts, min_analysts=6, max_analysts=15):
    """Map an analyst count to a prospect band per the thesis."""
    if analysts is None:
        return "unknown"
    if analysts < min_analysts:
        return "early"                                   # too little coverage yet
    if analysts <= max_analysts:
        return "prime"                                   # growing pain point — the sweet spot
    return "tooled"                                      # likely already runs a competing tool


def _enrich_metro(metro, refresh=False):
    """Enriched rows for a metro's whole universe, cached in the DB. refresh re-pulls from Yahoo."""
    cache = db.load_json(_SCREEN_KEY, {}) or {}
    if not refresh and metro in cache and cache[metro].get("rows"):
        return cache[metro]["rows"]
    rows = []
    for t in tickers_for(metro):
        rows.append(_enrich(t))
        time.sleep(0.3)                                  # be gentle with Yahoo
    cache[metro] = {"fetched_at": None, "rows": rows}    # timestamp stamped by caller (no Date.now here)
    db.save_json(_SCREEN_KEY, cache)
    return rows


def screen(metro, industry=None, min_analysts=6, max_analysts=15, refresh=False):
    """Screen a metro. Returns {metro, rows, prime, tooled, early, counts}. `industry` is a
    keyword matched against a company's sector OR industry (case-insensitive)."""
    rows = _enrich_metro(metro, refresh=refresh)
    kw = (industry or "").strip().lower()
    if kw:
        rows = [r for r in rows
                if kw in (r.get("sector") or "").lower() or kw in (r.get("industry") or "").lower()]
    for r in rows:
        r["band"] = classify(r.get("analysts"), min_analysts, max_analysts)
    by = lambda band: sorted([r for r in rows if r["band"] == band],
                             key=lambda r: -(r.get("analysts") or 0))
    prime, tooled, early = by("prime"), by("tooled"), by("early")
    return {"metro": metro, "rows": rows, "prime": prime, "tooled": tooled, "early": early,
            "counts": {"total": len(rows), "prime": len(prime), "tooled": len(tooled),
                       "early": len(early)}}
