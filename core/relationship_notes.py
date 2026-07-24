"""core/relationship_notes.py — the human relationship layer over the auto-derived book.

Filings tell you WHO owns you and what they hold. Only the IR team knows a desk is
"good to deal with," or was last seen years ago. Those judgments can't be computed —
they're the value an IR professional adds on top. This module stores them.

Notes are GLOBAL (a house book, like the fund-lineup crosswalk) and keyed by the same
normalized manager name, so a note attaches to a FIRM regardless of which client's
screen you're on — "Fidelity is great to deal with" is true for every issuer. Stored
notes override the code seed; the seed captures what the user has already told us.
"""
from datetime import datetime

from core import db, fund_lineup

_KEY = "ir_relationship_notes"
_GLOBAL = "_global"

# Relationship-quality options — the human read, NOT derived from holdings.
QUALITY = {
    "good": "Good to deal with",
    "responsive": "Responsive",
    "neutral": "Neutral",
    "hard": "Hard to reach",
    "low_touch": "Low-touch",
}

# Code-seeded from the user's ~20 years in IR (see memory: ir-relationship-notes).
# Keyed by fund_lineup._norm of the real 13F filer name (FMR LLC -> "fmr", etc.).
_SEED = {
    fund_lineup._norm("FMR LLC"): {                       # Fidelity
        "quality": "good", "note": "Really good to deal with."},
    fund_lineup._norm("Price T Rowe Associates Inc"): {   # T. Rowe Price
        "quality": "good", "note": "Really good to deal with."},
    fund_lineup._norm("Mairs & Power Inc"): {
        "quality": "low_touch", "touches": 1,
        "note": "Met once in ~20 years (in San Francisco — they're a St. Paul shop)."},
}


def _norm(name):
    return fund_lineup._norm(name)


def _store():
    return db.load_json(_KEY, {}, client_id=_GLOBAL) or {}


def get(name):
    """Merged relationship note for a manager (seed + stored, stored wins). {} if none."""
    nk = _norm(name)
    if not nk:
        return {}
    e = dict(_SEED.get(nk, {}))
    e.update(_store().get(nk, {}))
    return e


def save(name, **fields):
    """Upsert relationship fields (quality, last_contact, touches, note) for a manager."""
    nk = _norm(name)
    if not nk:
        return {}
    s = _store()
    e = dict(_SEED.get(nk, {}))
    e.update(s.get(nk, {}))
    for k, v in fields.items():
        e[k] = v
    e["updated_at"] = datetime.now().isoformat()
    s[nk] = e
    db.save_json(_KEY, s, client_id=_GLOBAL)
    return e
