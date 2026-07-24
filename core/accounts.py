"""core/accounts.py — canonical account identity, the CRM spine.

Every surface that talks about a firm must resolve to the SAME record, or notes and
interactions fragment (a note on "FMR LLC" never meeting one on "Fidelity"). This
module maps any observed handle — an SEC CIK or a firm name — to ONE stable account
key.

Resolution priority:
  1. SEC CIK  -> "cik:<n>"     (globally unique, and already carried in the 13F data)
  2. an existing alias        (this norm was resolved before)
  3. a minted house id -> "acct:<slug>"  (deterministic from the normalized name, so
     the same unknown firm always mints the same id — a private bank, family office,
     curated target with no CIK)

Self-healing: a firm first seen by NAME gets a house key; when it later shows up WITH
a CIK, the alias is re-pointed to the CIK key and the older record (and its
relationship note) is merged onto it — so identity converges instead of splitting.

Global, like the fund-lineup crosswalk: an account is a firm, the same for every
client. Keyed via fund_lineup._norm so it shares the crosswalk's name normalization.
"""
import re
from datetime import datetime

from core import db, fund_lineup

_ALIAS_KEY = "crm_account_aliases"     # {norm_name: canonical_id}
_ACCT_KEY = "crm_accounts"             # {canonical_id: {id, name, cik, aliases[], created_at}}
_GLOBAL = "_global"


def _norm(name):
    return fund_lineup._norm(name)


def _g(key, default):
    return db.load_json(key, default, client_id=_GLOBAL) or default


def _s(key, value):
    db.save_json(key, value, client_id=_GLOBAL)


def _cik_int(cik):
    try:
        return int(str(cik).lstrip("0") or 0) or None
    except (TypeError, ValueError):
        return None


def cik_key(cik):
    n = _cik_int(cik)
    return f"cik:{n}" if n else None


def _house_key(norm):
    return "acct:" + (re.sub(r"\s+", "-", norm) if norm else "unknown")


def is_cik_key(key):
    return isinstance(key, str) and key.startswith("cik:")


def resolve(name=None, cik=None, register=True):
    """Canonical account key for a firm. Pass `cik` whenever it's known (it rides on
    the 13F holder data) so the account keys off SEC identity rather than a name.
    Returns None only when neither a name nor a CIK is given."""
    norm = _norm(name) if name else ""
    aliases = _g(_ALIAS_KEY, {})
    ck = cik_key(cik)
    if ck:
        cid = ck
    elif norm and norm in aliases:
        return aliases[norm]                 # already resolved (house or cik key)
    elif norm:
        cid = _house_key(norm)
    else:
        return None
    if register and norm:
        _register(cid, norm, name, cik)
    return cid


def _register(cid, norm, name, cik):
    aliases = _g(_ALIAS_KEY, {})
    accts = _g(_ACCT_KEY, {})
    prev = aliases.get(norm)
    if prev and prev != cid:                 # this name used to resolve elsewhere -> merge
        _merge(prev, cid, accts)
    aliases[norm] = cid
    acct = accts.get(cid) or {"id": cid, "name": None, "cik": None,
                              "aliases": [], "created_at": datetime.now().isoformat()}
    n = _cik_int(cik)
    if n and not acct.get("cik"):
        acct["cik"] = n
    # prefer a human-cased display name over a screaming-caps one
    if name and (not acct.get("name") or acct["name"].isupper()):
        acct["name"] = name
    if norm not in acct["aliases"]:
        acct["aliases"].append(norm)
    accts[cid] = acct
    _s(_ALIAS_KEY, aliases)
    _s(_ACCT_KEY, accts)


def _merge(old_id, new_id, accts):
    """Fold an old account (usually a house id) into the canonical one (usually a CIK
    id). Moves the relationship note and unions the aliases; the new id wins."""
    from core import relationship_notes as rn
    rn._migrate_key(old_id, new_id)
    old = accts.pop(old_id, None)
    if not old:
        return
    cur = accts.get(new_id) or {"id": new_id, "name": None, "cik": None,
                                "aliases": [], "created_at": old.get("created_at")}
    cur["aliases"] = list(dict.fromkeys((cur.get("aliases") or []) + (old.get("aliases") or [])))
    if not cur.get("name"):
        cur["name"] = old.get("name")
    if not cur.get("cik"):
        cur["cik"] = old.get("cik")
    accts[new_id] = cur
    # re-point any other alias that still referenced the old id
    aliases = _g(_ALIAS_KEY, {})
    changed = False
    for k, v in list(aliases.items()):
        if v == old_id:
            aliases[k] = new_id
            changed = True
    if changed:
        _s(_ALIAS_KEY, aliases)


def get(key):
    """The account record for a canonical key: {id, name, cik, aliases, created_at}."""
    return _g(_ACCT_KEY, {}).get(key)


def get_for(name=None, cik=None):
    """Resolve + fetch in one step (no registration)."""
    return get(resolve(name, cik=cik, register=False))
