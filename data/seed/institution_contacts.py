"""
data/seed/institution_contacts.py — known institutional investor contacts.

Unlike conferences.py, this is NOT client-specific: these are real-world
funds/institutions (Vanguard, BlackRock, Dimensional, etc.) that could hold
shares in, or be a targeting prospect for, ANY of Praxis Point's clients —
the same institution shows up whether the client is USIO or client #2. So
this is shared reference data used across all tenants, not one record per
client_id like client_config.py or conferences.py.

Judgment call flagged for the user: if it turns out each client actually
needs their OWN separate institution-contact list (e.g. because client #2's
IR team has different existing relationships that shouldn't show up for
USIO), this should be restructured to be keyed by client_id like
conferences.py. Kept shared for now since the original data itself
(fund names/contacts) had nothing USIO-specific in it.

Used by: institution cards, the NDR planner, and the bulk email-draft
generator (per the original comment in app.py) — kept as one source so
those three don't each maintain their own copy.
"""

INSTITUTION_CONTACTS = {
    "Perkins Investment Management": {"name": "Michael Perkins",   "email": "ir@perkinsfunds.com",     "title": "Portfolio Manager"},
    "Vanguard Group Inc":            {"name": "Index Relations",   "email": "indexir@vanguard.com",    "title": "Index Relations"},
    "Rutabaga Capital Management":   {"name": "Paul Kovacs",       "email": "pk@rutabagacap.com",      "title": "Senior Analyst"},
    "Ancora Advisors":               {"name": "Frederick DiSanto", "email": "fd@ancora.net",           "title": "CEO & Portfolio Manager"},
    "Wasatch Advisors":              {"name": "Research Team",     "email": "research@wasatchadv.com", "title": "Small-Cap Research"},
    "BlackRock Small Cap Growth":    {"name": "IR Team",           "email": "ir@blackrock.com",        "title": "Portfolio Relations"},
    "Heartland Advisors":            {"name": "Will Nasgovitz",    "email": "wn@heartlandadv.com",     "title": "Portfolio Manager"},
    "Dimensional Fund Advisors":     {"name": "DFA Relations",     "email": "ir@dfaus.com",            "title": "Portfolio Relations"},
}


def get_institution_contacts():
    return INSTITUTION_CONTACTS
