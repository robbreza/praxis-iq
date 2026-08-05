"""Shared pytest fixtures.

`mem_db` is the scratch-store fixture: it redirects core.db's JSON storage to an
in-memory dict for the duration of a test, so store-touching logic (qa_bank, etc.)
runs against a throwaway backend and NEVER writes the real DB or a real tenant's
data. It's opt-in (not autouse), so the existing Lighthouse tests are unaffected.
This is the structural fix for the "test clobbered a real/demo store" hazard.
"""
import pytest


@pytest.fixture
def mem_db(monkeypatch):
    """In-memory replacement for core.db.load_json / save_json, keyed by
    (client_id, key). Returns the backing dict so a test can inspect writes."""
    store = {}

    def load_json(key, default=None, client_id=None):
        val = store.get((client_id, key))
        return val if val is not None else default

    def save_json(key, data, client_id=None):
        store[(client_id, key)] = data

    monkeypatch.setattr("core.db.load_json", load_json, raising=False)
    monkeypatch.setattr("core.db.save_json", save_json, raising=False)
    return store
