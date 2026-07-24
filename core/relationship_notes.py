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
# Each seed carries `filer` (the real 13F name whose _norm equals this key — so the
# seed overlays the actual holder) and a friendlier `name` for display. The account
# list opens the profile by `filer`, keeping list and profile consistent.
_SEED = {
    fund_lineup._norm("FMR LLC"): {                       # Fidelity
        "filer": "FMR LLC", "name": "Fidelity (FMR)",
        "quality": "good", "note": "Really good to deal with."},
    fund_lineup._norm("Price T Rowe Associates Inc"): {   # T. Rowe Price
        "filer": "Price T Rowe Associates Inc", "name": "T. Rowe Price",
        "quality": "good", "note": "Really good to deal with."},
    fund_lineup._norm("Mairs & Power Inc"): {
        "filer": "Mairs & Power Inc", "name": "Mairs & Power", "quality": "low_touch",
        "note": "Met once in ~20 years (in San Francisco — they're a St. Paul shop)."},
}


def _norm(name):
    return fund_lineup._norm(name)


def _store():
    return db.load_json(_KEY, {}, client_id=_GLOBAL) or {}


def _key(name, cik=None, register=True):
    """Canonical account key for this firm (see core.accounts). The store is keyed by
    identity, not by raw name, so a note follows the firm across name variants."""
    from core import accounts
    return accounts.resolve(name, cik=cik, register=register)


def get(name, cik=None):
    """Merged relationship note for a firm: the code seed (by normalized name) as a
    default, overlaid with the stored note (by canonical account key). {} if none."""
    nk = _norm(name)
    if not nk:
        return {}
    e = dict(_SEED.get(nk, {}))
    s = _store()
    key = _key(name, cik, register=False)
    stored = s.get(key)
    if stored is None and nk in s:            # legacy note keyed by bare norm (pre-identity)
        stored = s.get(nk)
    if stored:
        e.update(stored)
    return e


def save(name, cik=None, **fields):
    """Upsert relationship fields (quality, last_contact, touches, note) for a firm.
    Resolves + registers the canonical account identity, then field-merges."""
    nk = _norm(name)
    if not nk:
        return {}
    key = _key(name, cik)                     # resolve + register identity
    s = _store()
    e = dict(_SEED.get(nk, {}))
    e.update(s.get(key, {}))
    if nk in s and key != nk:                 # fold a legacy bare-norm note forward
        e.update(s.pop(nk))
    for k, v in fields.items():
        e[k] = v
    e["updated_at"] = datetime.now().isoformat()
    s[key] = e
    db.save_json(_KEY, s, client_id=_GLOBAL)
    return e


def get_by_key(key):
    """Stored note for a resolved canonical key (no seed overlay — used by the account
    API when it already holds the key)."""
    return dict(_store().get(key, {})) if key else {}


def save_by_key(key, **fields):
    """Field-merge a stored note directly onto a canonical key."""
    if not key:
        return {}
    s = _store()
    e = dict(s.get(key, {}))
    for k, v in fields.items():
        e[k] = v
    e["updated_at"] = datetime.now().isoformat()
    s[key] = e
    db.save_json(_KEY, s, client_id=_GLOBAL)
    return e


def _migrate_key(old_key, new_key):
    """Move a stored note from one account key to another (used when identity merges a
    house id into a CIK id). The destination wins on any field conflict."""
    if old_key == new_key:
        return
    s = _store()
    if old_key not in s:
        return
    merged = dict(s.pop(old_key))
    merged.update(s.get(new_key, {}))         # keep the more-specific record's edits
    s[new_key] = merged
    db.save_json(_KEY, s, client_id=_GLOBAL)
