"""core/ir_knowledge.py — the IR approved-answer knowledge base.

Pre-vetted, PUBLIC answers to common shareholder questions (dividend policy, transfer
agent, where to find filings, how to reach IR). The shareholder-reply drafter may state
these directly — they're approved by the IR team, so this is the one place a draft can
answer a substantive question instead of deferring to the filings.

Per-client and editable. Real clients seed only universally-safe, config-derived entries
(ticker/exchange, filing locations, IR contact); client-specific answers (dividend,
transfer agent) are the IR team's to add and approve — never fabricated. The demo tenant
is seeded with illustrative extras so the capability is demonstrable. See
[[illustrative-demo-tenant]].
"""
import uuid

from config.client_config import CT, get_active_client_id, get_client
from core import db

STORE_KEY = "ir_knowledge_base.json"


def _ir_email(cid):
    return ((get_client(cid) or {}).get("ir_contact") or {}).get("email")


def _generic_seed(cid):
    """Universally-safe, config-derived answers — fine to seed for any real client."""
    entries = [
        {"topic": "Where to find filings & reports",
         "answer": "Our SEC filings (10-Q, 10-K, 8-K) and press releases are available on the SEC's "
                   "EDGAR system at sec.gov and in the Investor Relations section of our website."},
        {"topic": "Ticker & exchange",
         "answer": f"{CT('name')} trades on {CT('exchange')} under the ticker {CT('ticker')}."},
    ]
    em = _ir_email(cid)
    if em:
        entries.append({"topic": "Contacting Investor Relations",
                        "answer": f"You can reach our Investor Relations team at {em}."})
    return entries


# Illustrative only — DEMO tenant. Never seeded for a real client (would be fabrication).
_DEMO_EXTRA = [
    {"topic": "Dividend policy",
     "answer": "Northlake Payments does not currently pay a dividend and is reinvesting in the "
               "business. Any change to that policy would be announced publicly."},
    {"topic": "Transfer agent",
     "answer": "Our transfer agent is Continental Stock Transfer & Trust Company. For account and "
               "share matters — address changes, lost certificates, direct registration — please "
               "contact them directly at (212) 509-4000."},
    {"topic": "Fiscal year end", "answer": "Our fiscal year ends December 31."},
]


def _seed(cid):
    seed = _generic_seed(cid) + (_DEMO_EXTRA if cid == "demo" else [])
    return [{"id": uuid.uuid4().hex[:12], **e} for e in seed]


def load_entries(client_id=None):
    cid = client_id or get_active_client_id()
    stored = db.load_json(STORE_KEY, None, client_id=cid)
    if stored is not None:
        return stored
    seeded = _seed(cid)
    db.save_json(STORE_KEY, seeded, client_id=cid)  # persist the seed once, like the calendar
    return seeded


def save_entries(entries, client_id=None):
    db.save_json(STORE_KEY, entries or [], client_id=client_id or get_active_client_id())


def add_entry(topic, answer, client_id=None):
    entries = load_entries(client_id)
    entries.append({"id": uuid.uuid4().hex[:12], "topic": (topic or "").strip(),
                    "answer": (answer or "").strip()})
    save_entries(entries, client_id)


def update_entry(entry_id, topic, answer, client_id=None):
    entries = load_entries(client_id)
    for e in entries:
        if e.get("id") == entry_id:
            e["topic"], e["answer"] = (topic or "").strip(), (answer or "").strip()
    save_entries(entries, client_id)


def delete_entry(entry_id, client_id=None):
    save_entries([e for e in load_entries(client_id) if e.get("id") != entry_id], client_id)


def context_block(client_id=None):
    """The KB formatted for the reply-draft prompt, or '' when empty."""
    entries = [e for e in load_entries(client_id) if (e.get("answer") or "").strip()]
    return "\n".join(f"- {e.get('topic') or 'Answer'}: {e['answer'].strip()}" for e in entries)
