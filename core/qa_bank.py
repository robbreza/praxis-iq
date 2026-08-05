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

from config.client_config import get_active_client_id
from core import db

GLOBAL = "_global"
_KEY = "qa_house_bank.json"

# Common cross-client (payments / small-cap) recurring analyst questions, so the bank
# is populated before any call has been graded. Generic question templates — not a
# claim about any client. Users/accrual add on top; a stored row wins on conflict.
_GLOBAL_SEED = [
    "How is the current quarter tracking versus guidance, and what's the H2 cadence?",
    "What is your capital allocation priority — buyback, M&A, debt paydown, or reinvestment?",
    "How defensible is your position as larger technology platforms move into payments?",
    "What is driving the change in take rate / gross margin, and is it sustainable?",
    "How much of the beat is durable run-rate versus one-time items?",
    "What are your assumptions for interest income / float given the rate environment?",
    "What is your customer concentration and net revenue retention?",
    "What are the puts and takes on the full-year guidance range — what gets you to the high vs low end?",
]


def _norm(q):
    """Normalized dedup key: lowercase, alnum+space only, collapsed, truncated."""
    s = re.sub(r"[^a-z0-9 ]+", " ", (q or "").lower())
    return re.sub(r"\s+", " ", s).strip()[:90]


def _seed_records():
    return [{"key": _norm(q), "question": q, "kind": "seed", "source_client": None,
             "source_quarter": None, "added_by": "seed", "added_at": None, "seed": True}
            for q in _GLOBAL_SEED]


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
    This is the full bank a client's adversarial pass should be seeded with."""
    cid = cid or get_active_client_id()
    out, seen = [], set()
    for r in list_scope("client", cid) + list_scope("global", cid):
        k = r.get("key")
        if k and k not in seen:
            seen.add(k)
            out.append(r)
    return out


def questions(cid=None, limit=30):
    """The merged bank as plain question strings, for seeding the adversarial prompt."""
    qs = [r.get("question", "").strip() for r in merged(cid) if r.get("question", "").strip()]
    return qs[:limit]


def add(question, kind="manual", scope="client", cid=None, source_quarter=None, added_by=None):
    """Add (or update in place) a question in the given scope. Keyed by normalized
    text, so re-adding the same question updates rather than duplicating. Returns
    True if a NEW row was created, False if it updated an existing one."""
    question = (question or "").strip()
    if not question:
        return False
    key = _norm(question)
    rows = _load(scope, cid)
    for r in rows:
        if r.get("key") == key:
            r.update({"question": question, "kind": r.get("kind") or kind})
            _save(scope, cid, rows)
            return False
    rows.append({"key": key, "question": question, "kind": kind,
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


def accrue(cid, quarter, surprises, hits=None):
    """Fold a call's outcomes into the bank: SURPRISES (questions we didn't predict)
    go to BOTH the client history AND the global house book — that's the cross-client
    learning; asked-and-HIT questions go to the client history only. The illustrative
    demo tenant accrues to its OWN bank only, never the shared house book. Returns
    {new_global, new_client} counts. Idempotent per question text."""
    to_global = cid not in _ILLUSTRATIVE
    new_global = new_client = 0
    for q in (surprises or []):
        if add(q, kind="surprise", scope="client", cid=cid, source_quarter=quarter, added_by="accrual"):
            new_client += 1
        if to_global and add(q, kind="surprise", scope="global", source_quarter=quarter,
                             added_by=f"accrual:{cid}"):
            new_global += 1
    for q in (hits or []):
        if add(q, kind="asked", scope="client", cid=cid, source_quarter=quarter, added_by="accrual"):
            new_client += 1
    return {"new_global": new_global, "new_client": new_client}
