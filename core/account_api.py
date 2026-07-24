"""core/account_api.py — the ONE door to an account's CRM data.

Every surface (the 360 profile, a Buy-Side card, Today, the meeting log) reads and
writes an account through these three functions and nothing else. Behind them sit the
three layers, fused by a single canonical identity (core.accounts):

  get_account(...)        -> identity + relationship (human) + interactions (derived)
  save_relationship(...)  -> field-merge the human opinion (quality / note / owner …)
  log_interaction(...)    -> append one event (touches / last_contact recompute)

Address a firm by name(+cik) or by a pre-resolved canonical `key`. Passing the cik
(it rides on the 13F data) keys the account off SEC identity; name-only mints/uses a
house id. Reads never register a new account; a write (save/log) does. The AUTO layer
— holdings, fund lineup — is derived by the caller from the filing data and is
deliberately not stored here, so this API owns exactly the persisted/derived layers.
"""
from core import accounts, interactions, relationship_notes
from core.relationship_notes import QUALITY       # re-export so surfaces need one import
from core.interactions import TYPES                # re-export


def _resolve(name, cik, key, register):
    if key:
        return key
    return accounts.resolve(name, cik=cik, register=register)


def get_account(name=None, cik=None, key=None):
    """Everything persisted/derived about an account, in one read:
    {key, name, cik, aliases, relationship:{…}, interactions:{touches,last_contact,events}}.
    None if neither a name/cik nor a key is given."""
    k = _resolve(name, cik, key, register=False)
    if not k:
        return None
    rec = accounts.get(k) or {"id": k, "name": name, "cik": accounts._cik_int(cik), "aliases": []}
    relationship = relationship_notes.get(name, cik) if name else relationship_notes.get_by_key(k)
    return {
        "key": k,
        "name": rec.get("name") or name,
        "cik": rec.get("cik"),
        "aliases": rec.get("aliases", []),
        "relationship": relationship,
        "interactions": interactions.summary(k),
    }


def save_relationship(name=None, cik=None, key=None, **fields):
    """Field-merge the human opinion layer (only the keys passed are touched). Registers
    the account. Returns {key, relationship}."""
    if name is not None:
        rel = relationship_notes.save(name, cik=cik, **fields)     # resolves+registers, seed/legacy aware
        k = _resolve(name, cik, key, register=True)
    else:
        k = key
        rel = relationship_notes.save_by_key(k, **fields)
    return {"key": k, "relationship": rel}


def log_interaction(name=None, cik=None, key=None, type="note", date=None, who=None,
                    summary=None, source="manual"):
    """Append one interaction event. Registers the account. Returns the event."""
    k = _resolve(name, cik, key, register=True)
    return interactions.log(k, type=type, date=date, who=who, summary=summary, source=source)


def list_accounts(cid=None):
    """The relationship book: every account the user has actually engaged — anything
    with a relationship note, a logged/derived interaction, a registered identity, or a
    code-seeded relationship. Each row carries name, quality, note, touches,
    last_contact. This is what the Account 360 destination lists."""
    from config.client_config import get_active_client_id
    cid = cid or get_active_client_id()

    # seed norms carry a display name; resolve each to its (house) key
    seed_by_key = {}
    for s in relationship_notes._SEED.values():
        nm = s.get("name")
        k = accounts.resolve(nm, register=False) if nm else None
        if k:
            seed_by_key[k] = s

    keys = set(seed_by_key)
    keys |= set(relationship_notes._store().keys())
    keys |= {e.get("account") for e in interactions._manual(cid) if e.get("account")}
    keys |= set(accounts._g(accounts._ACCT_KEY, {}).keys())

    out = []
    for k in keys:
        if not k:
            continue
        rec = accounts.get(k) or {}
        merged = dict(seed_by_key.get(k, {}))
        merged.update(relationship_notes.get_by_key(k))
        ix = interactions.summary(k, cid)
        out.append({
            "key": k,
            "name": rec.get("name") or merged.get("name") or k,
            "cik": rec.get("cik"),
            "quality": merged.get("quality"),
            "note": merged.get("note"),
            "touches": ix["touches"],
            "last_contact": ix["last_contact"],
        })
    out.sort(key=lambda a: (a["last_contact"] or "", a["touches"]), reverse=True)
    return out
