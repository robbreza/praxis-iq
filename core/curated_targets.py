"""
core/curated_targets.py — hand-curated NDR targets the automated crawl can't find.

peer_prospects.py discovers prospects by crawling the 13F holders of a client's
PEERS, so a fund only surfaces if it ALREADY owns a comp. That structurally
misses every account you know is a fit but that doesn't hold a peer *today*: a
Geneva private bank like Lombard Odier, a Lugano discretionary manager, a
relationship an IRO carries from a prior seat, a fund that just sold out but
stays warm. Those are entered here by hand and shown alongside the derived
prospects — always tagged "Curated", never "holds a comp" — so the line between
an evidence-backed prospect and a relationship call is never blurred.

Two scopes, one shape:
  • per-client (client_id = <cid>)     — this issuer's own known-account book.
  • global     (client_id = GLOBAL)    — the house book: accounts worth a look
    for ANY client, which accretes as Praxis Point onboards more issuers. A
    client's view sees BOTH (global ∪ its own); a client entry wins on conflict.

Storage is the ordinary client_data JSON store (db.load_json/save_json), so a
global entry is just a row under the reserved GLOBAL client id — no schema
change. On top of the stored rows sits a small code-seeded default book
(_GLOBAL_SEED) so the global list is useful out of the box and survives whichever
DB backend is live; user-added rows accrete on top of it and win on conflict.

De-dup / suppression:
  • merged() folds global + client, keyed by normalized name, client winning.
  • all_candidates() drops any curated name that already appears as a real holder
    or a derived prospect, so curating a name that later starts holding a comp
    never double-lists it.
"""

from datetime import datetime

from config.client_config import get_active_client_id
from core import db
from core.peer_prospects import _norm

GLOBAL = "_global"
_KEY = "curated_targets.json"

# ── Code-seeded global default book ──────────────────────────────────────────
# Real, well-known institutions that a peer-holder crawl will never surface for a
# small/mid US issuer (Swiss private banks rarely file US 13Fs tied to the comp
# set). Seeded GLOBAL because they're relevant to any client with an
# international book, and so the feature is populated on day one. These are
# TARGETS worth a relationship call — NOT a claim that they hold anything. Users
# add/override via add(); a client entry of the same name wins.
_GLOBAL_SEED = [
    {"filer": "Lombard Odier Investment Managers", "city": "GENEVA", "state": "V8",
     "rationale": "Geneva private bank / discretionary equity — relationship-sourced; "
                  "does not appear in the peer-holder crawl."},
    {"filer": "Union Bancaire Privée (UBP)", "city": "GENEVA", "state": "V8",
     "rationale": "Geneva private bank with active equity mandates — relationship target."},
    {"filer": "Mirabaud Asset Management", "city": "GENEVA", "state": "V8",
     "rationale": "Geneva boutique manager — discretionary equity; not a peer-holder."},
    {"filer": "Banca del Ceresio", "city": "LUGANO", "state": "V8",
     "rationale": "Lugano private bank (Ceresio / Haussmann equity) — relationship target."},
    {"filer": "Cornèr Banca", "city": "LUGANO", "state": "V8",
     "rationale": "Lugano private bank — international discretionary book; relationship call."},
]


def _seed_records():
    """The code-seeded global defaults, shaped like stored rows."""
    out = []
    for s in _GLOBAL_SEED:
        out.append({
            "key": _norm(s["filer"]), "filer": s["filer"],
            "city": s.get("city"), "state": s.get("state"),
            "rationale": s.get("rationale", ""), "scope": "global",
            "added_by": "seed", "added_at": None, "seed": True,
        })
    return out


def _load(scope, cid):
    """Raw stored rows for one scope."""
    client = GLOBAL if scope == "global" else (cid or get_active_client_id())
    return db.load_json(_KEY, [], client_id=client) or []


def _save(scope, cid, rows):
    client = GLOBAL if scope == "global" else (cid or get_active_client_id())
    db.save_json(_KEY, rows, client_id=client)


def list_scope(scope, cid=None):
    """Every curated entry in one scope. For 'global', the code-seeded defaults
    are folded in (stored rows win on conflict, so a user can override a seed)."""
    rows = _load(scope, cid)
    if scope != "global":
        return list(rows)
    have = {r.get("key") for r in rows}
    return list(rows) + [s for s in _seed_records() if s["key"] not in have]


def add(filer, city=None, state=None, rationale="", scope="client", cid=None, added_by=None):
    """Add (or update) a curated target in the given scope. Keyed by normalized
    name, so re-adding the same firm updates it in place rather than duplicating."""
    filer = (filer or "").strip()
    if not filer:
        raise ValueError("a firm name is required")
    if scope not in ("client", "global"):
        raise ValueError("scope must be 'client' or 'global'")
    rows = _load(scope, cid)
    key = _norm(filer)
    rec = {
        "key": key, "filer": filer,
        "city": (city or "").strip() or None, "state": (state or "").strip() or None,
        "rationale": (rationale or "").strip(), "scope": scope,
        "added_by": added_by, "added_at": datetime.now().isoformat(),
    }
    rows = [r for r in rows if r.get("key") != key] + [rec]
    _save(scope, cid, rows)
    return rec


def remove(key, scope="client", cid=None):
    """Remove a user-added curated entry by key. Code-seeded global defaults have
    no stored row, so removing one is a no-op (there's nothing to delete) — the
    caller should hide the delete control for seeds."""
    rows = _load(scope, cid)
    rows = [r for r in rows if r.get("key") != key]
    _save(scope, cid, rows)


def merged(cid=None):
    """Global ∪ client, deduped by normalized name with the CLIENT entry winning,
    each shaped like a peer_prospects candidate so the unified metro view and
    promote() can consume it directly (kind='curated', tier='Curated', no comps,
    no conviction — these aren't scored against evidence-backed prospects)."""
    cid = cid or get_active_client_id()
    out, seen = [], set()
    for scope in ("client", "global"):          # client first ⇒ it wins on conflict
        for r in list_scope(scope, cid):
            k = r.get("key") or _norm(r.get("filer", ""))
            if not k or k in seen:
                continue
            seen.add(k)
            out.append({
                "key": k, "norm": k, "filer": r.get("filer"),
                "city": r.get("city"), "state": r.get("state"),
                "comps": {}, "peer_value": 0, "book_total": None, "book_positions": None,
                "conviction": None, "concentration": None, "file_date": None,
                "kind": "curated", "tier": "Curated",
                "rationale": r.get("rationale", ""), "scope": r.get("scope", scope),
                "seed": r.get("seed", False), "added_by": r.get("added_by"),
            })
    return out


def counts(cid=None):
    cid = cid or get_active_client_id()
    return {
        "client": len(list_scope("client", cid)),
        "global": len(list_scope("global", cid)),
        "total": len(merged(cid)),
    }
