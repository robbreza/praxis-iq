"""
data/seed/peer_fundamentals.py — per-peer fundamentals for the live peer
benchmarking analysis (core/benchmarking_engine.py).

The peer *list* and EV/Revenue come from the tracked peer universe (CP()); this
supplies the two metrics that aren't in that store — gross margin and revenue
growth — plus a fallback EV/Revenue for peers whose store value is blank. Keyed
by ticker. Representative figures for the payment/fintech comp group; demo data,
refine against filings when a real fundamentals feed is wired.

    gross_margin — most recent gross margin, %
    rev_growth   — most recent YoY revenue growth, %
    ev_rev       — EV/Revenue (fallback only; CP() wins when it has a value)
"""

PEER_FUNDAMENTALS = {
    # Primary valuation peers
    "RPAY": {"gross_margin": 70.0, "rev_growth": 6.0,  "ev_rev": 2.8},
    "FOUR": {"gross_margin": 32.0, "rev_growth": 28.0, "ev_rev": 4.2},
    "PSFE": {"gross_margin": 56.0, "rev_growth": 10.0, "ev_rev": 1.5},
    "CSGS": {"gross_margin": 49.0, "rev_growth": 5.0,  "ev_rev": 2.2},
    "PAY":  {"gross_margin": 25.0, "rev_growth": 30.0, "ev_rev": 2.5},
    "CASS": {"gross_margin": 62.0, "rev_growth": 4.0,  "ev_rev": 2.2},
    "GDOT": {"gross_margin": 36.0, "rev_growth": 3.0,  "ev_rev": 1.2},
    # Large-cap reference (excluded from the median). GPN/TOST resolve live, so these
    # are last-resort fallbacks only. FI (Fiserv) removed 2026-07-16 — too big to inform
    # a micro-cap comp, and it had no live data on either side, so this curated row was
    # the ONLY thing that ever rendered for it.
    "GPN":  {"gross_margin": 63.0, "rev_growth": 6.0,  "ev_rev": 4.5},
    "TOST": {"gross_margin": 24.0, "rev_growth": 24.0, "ev_rev": 3.5},
    # Retired from the active set but kept for any historical reference.
    "PRTH": {"gross_margin": 38.0, "rev_growth": 18.0, "ev_rev": 1.8},
    "EEFT": {"gross_margin": 52.0, "rev_growth": 9.0,  "ev_rev": 2.5},
    "PAX":  {"gross_margin": 35.0, "rev_growth": -5.0, "ev_rev": 1.3},
}


def get_peer_fundamentals():
    return {k: dict(v) for k, v in PEER_FUNDAMENTALS.items()}
