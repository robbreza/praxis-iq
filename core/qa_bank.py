"""
core/qa_bank.py — the house Q&A bank: questions analysts have actually asked.

The adversarial-Q&A pass (earnings_page._adversarial_qa) predicts the questions a
script leaves exposed. The Morning-After prep-vs-actual comparison then grades those
predictions against the real call and surfaces SURPRISES — questions analysts asked
that we did NOT predict. Those surprises are the most valuable signal in the whole
loop, and they should not evaporate: they belong in a bank that seeds the NEXT
adversarial pass, so the same question can't blindside us twice.

Two scopes, one shape (mirrors core/curated_targets.py):
  • per-client (client_id = <cid>)   — this issuer's own asked-question history.
  • global     (client_id = GLOBAL)  — the house book: recurring questions worth
    checking for ANY client, which accretes as Praxis Point onboards more issuers.
    A client's view sees BOTH (global ∪ its own).

Storage is the ordinary client_data JSON store, so a global entry is just a row
under the reserved GLOBAL client id — no schema change. A small code-seeded default
book (_GLOBAL_SEED) makes the bank useful on day one; accrued/added rows sit on top.

These are QUESTION templates (generic analyst asks), never client facts — so seeding
them is not fabrication. Entries are deduped on a normalized form of the text.
"""
import re
from datetime import datetime

from config.client_config import get_active_client_id, get_client
from core import db

GLOBAL = "_global"
_KEY = "qa_house_bank.json"

# A global entry carries a SECTOR tag so it only seeds clients it's relevant to:
# "universal" seeds everyone; a specific sector key (e.g. "payments") seeds only
# clients in that sector. Free-text client sectors are normalized to a canonical
# key via _SECTOR_ALIASES — extend as Praxis Point onboards new sectors.
_SECTOR_ALIASES = [
    ("payments", ("payment", "fintech")),
    ("aerospace", ("aerospace", "mro", "aviation", "defense")),
]

# Common recurring analyst questions, seeded (question, sector) so the bank is useful
# before any call is graded. Generic templates — not a claim about any client. The
# universal ones apply to any issuer; payments-specific ones only seed payments clients.
_GLOBAL_SEED = [
    ("How is the current quarter tracking versus guidance, and what's the H2 cadence?", "universal"),
    ("What is your capital allocation priority — buyback, M&A, debt paydown, or reinvestment?", "universal"),
    ("How much of the beat is durable run-rate versus one-time items?", "universal"),
    ("What is your customer concentration and net revenue retention?", "universal"),
    ("What are the puts and takes on the full-year guidance range — what gets you to the high vs low end?", "universal"),
    ("How defensible is your position as larger technology platforms move into payments?", "payments"),
    ("What is driving the change in take rate, and is it sustainable?", "payments"),
    ("What are your assumptions for interest income / float given the rate environment?", "payments"),
]


def _sector_key(sector_str):
    """Normalize a free-text client sector to a canonical key for matching."""
    s = (sector_str or "").lower()
    for key, kws in _SECTOR_ALIASES:
        if any(k in s for k in kws):
            return key
    toks = re.sub(r"[^a-z0-9]+", " ", s).split()
    return toks[0] if toks else "general"


def client_sector(cid=None):
    """Canonical sector key for a client (from its config sector string)."""
    cid = cid or get_active_client_id()
    return _sector_key((get_client(cid) or {}).get("sector"))


def _norm(q):
    """Normalized dedup key: lowercase, alnum+space only, collapsed, truncated."""
    s = re.sub(r"[^a-z0-9 ]+", " ", (q or "").lower())
    return re.sub(r"\s+", " ", s).strip()[:90]


def _seed_records():
    return [{"key": _norm(q), "question": q, "kind": "seed", "sector": sec, "source_client": None,
             "source_quarter": None, "added_by": "seed", "added_at": None, "seed": True}
            for q, sec in _GLOBAL_SEED]


def _client_for(scope, cid):
    return GLOBAL if scope == "global" else (cid or get_active_client_id())


def _load(scope, cid):
    return db.load_json(_KEY, [], client_id=_client_for(scope, cid)) or []


def _save(scope, cid, rows):
    db.save_json(_KEY, rows, client_id=_client_for(scope, cid))


def list_scope(scope, cid=None):
    """Every entry in one scope. For 'global', the code-seeded defaults are folded
    in (stored rows win on conflict, so an accrued/edited row can override a seed)."""
    rows = _load(scope, cid)
    if scope != "global":
        return list(rows)
    have = {r.get("key") for r in rows}
    return list(rows) + [s for s in _seed_records() if s["key"] not in have]


def merged(cid=None):
    """Global ∪ client, deduped by normalized key — a client row wins on conflict.
    Global entries are SECTOR-filtered to this client: only "universal" entries and
    entries tagged with the client's own sector are included, so a payments question
    never seeds an aerospace client. This is the full bank a client's adversarial
    pass should be seeded with."""
    cid = cid or get_active_client_id()
    sec = client_sector(cid)
    out, seen = [], set()
    for r in list_scope("client", cid):  # a client's own history is never sector-filtered
        k = r.get("key")
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    for r in list_scope("global", cid):
        rsec = r.get("sector") or "universal"   # legacy rows with no tag are treated as universal
        if rsec not in ("universal", sec):
            continue
        k = r.get("key")
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    return out


def questions(cid=None, limit=30):
    """The merged bank as plain question strings, for seeding the adversarial prompt."""
    qs = [r.get("question", "").strip() for r in merged(cid) if r.get("question", "").strip()]
    return qs[:limit]


def add(question, kind="manual", scope="client", cid=None, source_quarter=None, added_by=None, sector=None):
    """Add (or update in place) a question in the given scope. Keyed by normalized
    text, so re-adding the same question updates rather than duplicating. A global
    entry carries a sector tag (defaults to "universal"); a client entry is tagged
    with the client's own sector. Returns True if a NEW row was created."""
    question = (question or "").strip()
    if not question:
        return False
    if sector is None:
        sector = "universal" if scope == "global" else client_sector(cid)
    key = _norm(question)
    rows = _load(scope, cid)
    for r in rows:
        if r.get("key") == key:
            r.update({"question": question, "kind": r.get("kind") or kind,
                      "sector": r.get("sector") or sector})
            _save(scope, cid, rows)
            return False
    rows.append({"key": key, "question": question, "kind": kind, "sector": sector,
                 "source_client": (cid or get_active_client_id()) if scope == "client" else None,
                 "source_quarter": source_quarter, "added_by": added_by or "user",
                 "added_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "seed": False})
    _save(scope, cid, rows)
    return True


def remove(key, scope="client", cid=None):
    """Remove a stored entry by key from a scope. (Code-seeded global defaults aren't
    stored rows, so they can't be removed — only overridden by adding the same text.)"""
    rows = _load(scope, cid)
    _save(scope, cid, [r for r in rows if r.get("key") != key])


# Illustrative tenants whose accrual must NOT reach the shared global house book real
# clients read from — fabricated-scenario surprises stay in the tenant's own bank only.
_ILLUSTRATIVE = {"demo"}


def bank(cid, question, kind="manual"):
    """Add ONE prep question to the bank — the client's own history plus (unless the
    client is illustrative) the global house book, sector-tagged — so a question the IR
    team knows will come up seeds future adversarial passes (and same-sector clients).
    Returns {new_client, new_global}. Idempotent per question text."""
    cid = cid or get_active_client_id()
    nc = add(question, kind=kind, scope="client", cid=cid, added_by="prep")
    ng = False
    if cid not in _ILLUSTRATIVE:
        ng = add(question, kind=kind, scope="global", added_by="prep", sector=client_sector(cid))
    return {"new_client": bool(nc), "new_global": bool(ng)}


def accrue(cid, quarter, surprises, hits=None):
    """Fold a call's outcomes into the bank: SURPRISES (questions we didn't predict)
    go to BOTH the client history AND the global house book — that's the cross-client
    learning; asked-and-HIT questions go to the client history only. The illustrative
    demo tenant accrues to its OWN bank only, never the shared house book. Returns
    {new_global, new_client} counts. Idempotent per question text."""
    to_global = cid not in _ILLUSTRATIVE
    sec = client_sector(cid)   # tag globally-accrued surprises with the source client's sector
    new_global = new_client = 0
    for q in (surprises or []):
        if add(q, kind="surprise", scope="client", cid=cid, source_quarter=quarter, added_by="accrual"):
            new_client += 1
        if to_global and add(q, kind="surprise", scope="global", source_quarter=quarter,
                             added_by=f"accrual:{cid}", sector=sec):
            new_global += 1
    for q in (hits or []):
        if add(q, kind="asked", scope="client", cid=cid, source_quarter=quarter, added_by="accrual"):
            new_client += 1
    return {"new_global": new_global, "new_client": new_client}
