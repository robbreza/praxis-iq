"""
data/seed/nobo_holders.py — representative NOBO (Non-Objecting Beneficial
Owner) list for the Market Intelligence > NOBO Ownership tab.

A real NOBO list is purchased from Broadridge as of a record date and contains
each non-objecting holder's name, address, and share position. This module
generates a believable stand-in — a mix of institutional and retail holders —
as TWO dated pulls (a prior quarter and the current one) so the two-pull flow
analysis (who accumulated / trimmed / is new / exited) is live for the demo.

Deterministic (seeded RNG) so the numbers are stable across renders. Demo data
only: real institution names with fabricated positions, plus procedurally
generated retail holders. Swap get_nobo_pulls() for a real Broadridge-file
parser when live NOBO data is available — the engine and UI consume this shape:

    {
      "shares_outstanding": int,
      "prior":   {"record_date": "YYYY-MM-DD", "holders": [holder, ...]},
      "current": {"record_date": "YYYY-MM-DD", "holders": [holder, ...]},
    }
    holder = {"name", "type": "Institutional"|"Retail", "shares", "city", "state"}
"""

import random

# USIO trades ~$2 on ~26.8M shares outstanding — a micro-cap where NOBO is the
# clearest window into the (retail-heavy) base that 13F never captures.
SHARES_OUTSTANDING = 26_800_000

# Institutional NOBO holders (the subset that don't object to disclosure), with
# (prior_shares, current_shares). The deltas are deliberately a story:
#   • Perkins quietly accumulating 3.9% -> 4.9% (about to trip a 13G) — the
#     kind of builder the CEO watches NOBO to catch early.
#   • Dimensional and Wasatch trimming; Royce a brand-new holder.
_INST = [
    # name,                             city,            st,   prior,     current
    ("Perkins Investment Management",   "Chicago",       "IL", 1_050_000, 1_310_000),
    ("Vanguard Group Inc",              "Malvern",       "PA", 1_150_000, 1_180_000),
    ("Franklin Templeton",              "San Mateo",     "CA",   270_000,   258_000),
    ("Dimensional Fund Advisors",       "Austin",        "TX",   235_000,   205_000),
    ("Lord Abbett",                     "Jersey City",   "NJ",   165_000,   182_000),
    ("Royce Investment Partners",       "New York",      "NY",         0,   140_000),
    ("Heartland Advisors",              "Milwaukee",     "WI",   120_000,   126_000),
    ("Ariel Investments",               "Chicago",       "IL",    90_000,   118_000),
    ("Wasatch Advisors",                "Salt Lake City","UT",   145_000,   110_000),
    ("Gabelli Funds (GAMCO)",           "Rye",           "NY",    75_000,    72_000),
]

_FIRST = ["James", "Mary", "Robert", "Patricia", "John", "Jennifer", "Michael", "Linda", "David",
          "Elizabeth", "William", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas",
          "Karen", "Charles", "Sarah", "Daniel", "Nancy", "Matthew", "Lisa", "Anthony", "Margaret",
          "Mark", "Betty", "Donald", "Sandra", "Steven", "Ashley", "Paul", "Kimberly", "Andrew",
          "Emily", "Joshua", "Donna", "Kenneth", "Michelle", "Kevin", "Carol", "Brian", "Amanda",
          "George", "Melissa", "Edward", "Deborah", "Ronald", "Stephanie"]
_LAST = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez",
         "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor",
         "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez",
         "Clark", "Ramirez", "Lewis", "Robinson", "Walker", "Young", "Allen", "King", "Wright",
         "Scott", "Torres", "Nguyen", "Hill", "Flores", "Green", "Adams", "Nelson", "Baker", "Hall"]
_CITIES = [("San Antonio", "TX"), ("Austin", "TX"), ("Houston", "TX"), ("Dallas", "TX"),
           ("New York", "NY"), ("Chicago", "IL"), ("Los Angeles", "CA"), ("Phoenix", "AZ"),
           ("Miami", "FL"), ("Denver", "CO"), ("Boston", "MA"), ("Seattle", "WA"), ("Atlanta", "GA"),
           ("Charlotte", "NC"), ("Columbus", "OH"), ("San Diego", "CA"), ("Nashville", "TN"),
           ("Tampa", "FL"), ("Portland", "OR"), ("Minneapolis", "MN")]


def get_nobo_pulls(client_id=None):
    rng = random.Random(4242)
    prior, current = [], []

    for name, city, st, p_sh, c_sh in _INST:
        if p_sh > 0:
            prior.append({"name": name, "type": "Institutional", "city": city, "state": st, "shares": p_sh})
        if c_sh > 0:
            current.append({"name": name, "type": "Institutional", "city": city, "state": st, "shares": c_sh})

    # ~380 retail identities. A stable per-holder identity (name+initial+city)
    # carries across both pulls so flow-matching is meaningful; the per-holder
    # branch below encodes the quarter's churn — net accumulation, a broadening
    # holder count (more new entrants than exits), plus some full exits.
    for _ in range(380):
        mid = chr(rng.randint(65, 90))
        name = f"{rng.choice(_FIRST)} {mid}. {rng.choice(_LAST)}"
        city, st = rng.choice(_CITIES)
        base = rng.choice([1, 2, 3, 5, 8, 12]) * rng.randint(400, 3000)
        r = rng.random()
        if r < 0.10:        # new holder this pull
            p_sh, c_sh = 0, base
        elif r < 0.15:      # exited
            p_sh, c_sh = base, 0
        elif r < 0.45:      # accumulated
            p_sh, c_sh = base, int(base * rng.uniform(1.1, 1.6))
        elif r < 0.58:      # trimmed
            p_sh, c_sh = base, int(base * rng.uniform(0.5, 0.9))
        else:               # unchanged
            p_sh, c_sh = base, base
        h = {"name": name, "type": "Retail", "city": city, "state": st}
        if p_sh > 0:
            prior.append({**h, "shares": p_sh})
        if c_sh > 0:
            current.append({**h, "shares": c_sh})

    return {
        "shares_outstanding": SHARES_OUTSTANDING,
        "prior": {"record_date": "2026-03-31", "holders": prior},
        "current": {"record_date": "2026-06-30", "holders": current},
    }
