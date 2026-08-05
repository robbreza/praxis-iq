"""Pin the house Q&A bank (core.qa_bank): sector normalization + filtering (a payments
question never seeds an aerospace client), accrual/banking to client + global, the
illustrative-tenant isolation (demo never reaches the shared global book), and dedup /
idempotency. Runs against the in-memory `mem_db` scratch store with fake client sectors,
so it touches neither the real DB nor a real tenant."""
import pytest

from core import qa_bank

_CLIENTS = {
    "payco": {"sector": "Fintech / Payments"},
    "aeroco": {"sector": "Aerospace — Engine MRO (aftermarket)"},
    "demo": {"sector": "Fintech / Payments"},   # illustrative tenant (see qa_bank._ILLUSTRATIVE)
}


@pytest.fixture
def bank_env(mem_db, monkeypatch):
    """In-memory store + fake client sectors, so bank logic is fully hermetic."""
    monkeypatch.setattr(qa_bank, "get_client", lambda cid=None: _CLIENTS.get(cid, {}), raising=False)
    monkeypatch.setattr(qa_bank, "get_active_client_id", lambda: "payco", raising=False)
    return mem_db


def test_sector_key_maps_known_sectors():
    assert qa_bank._sector_key("Fintech / Payments") == "payments"
    assert qa_bank._sector_key("Aerospace — Engine MRO (aftermarket)") == "aerospace"
    assert qa_bank._sector_key("") == "general"


def test_seeds_are_sector_scoped(bank_env):
    pay = [q.lower() for q in qa_bank.questions("payco", limit=100)]
    aero = [q.lower() for q in qa_bank.questions("aeroco", limit=100)]
    assert any("take rate" in q for q in pay)          # payments-tagged seed
    assert not any("take rate" in q for q in aero)     # filtered out for aerospace
    assert any("capital allocation" in q for q in pay)   # universal seed
    assert any("capital allocation" in q for q in aero)  # ...reaches every sector


def test_accrue_client_and_global_counts(bank_env):
    res = qa_bank.accrue("payco", "Q2 2026",
                         surprises=["How exposed are you to interchange caps?"],
                         hits=["Is the take-rate improvement durable?"])
    assert res == {"new_global": 1, "new_client": 2}   # surprise->client+global, hit->client


def test_accrued_surprise_is_sector_filtered(bank_env):
    qa_bank.accrue("payco", "Q2 2026", surprises=["How exposed are you to interchange caps?"])
    assert any("interchange" in q.lower() for q in qa_bank.questions("payco", limit=200))
    assert not any("interchange" in q.lower() for q in qa_bank.questions("aeroco", limit=200))


def test_accrue_is_idempotent(bank_env):
    qa_bank.accrue("payco", "Q2 2026", surprises=["A repeated surprise question?"])
    res = qa_bank.accrue("payco", "Q3 2026", surprises=["A repeated surprise question?"])
    assert res == {"new_global": 0, "new_client": 0}


def test_demo_never_reaches_global(bank_env):
    res = qa_bank.accrue("demo", "Q2 2026", surprises=["A demo-only surprise?"])
    assert res["new_global"] == 0
    assert not any("demo-only" in e.get("question", "").lower()
                   for e in qa_bank.list_scope("global", "payco"))
    assert any("demo-only" in e.get("question", "").lower()
               for e in qa_bank.list_scope("client", "demo"))


def test_bank_one_question_and_idempotent(bank_env):
    assert qa_bank.bank("payco", "A new recurring question?", kind="recurring") == \
        {"new_client": True, "new_global": True}
    assert qa_bank.bank("payco", "A new recurring question?", kind="recurring") == \
        {"new_client": False, "new_global": False}


def test_bank_demo_is_client_only(bank_env):
    res = qa_bank.bank("demo", "A demo banked question?", kind="manual")
    assert res["new_client"] is True and res["new_global"] is False
