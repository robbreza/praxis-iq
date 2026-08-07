"""Pin core.contacts' per-contact notes timeline: client-scoped store (add/read), empty-note guard,
and the cross-client aggregation for the staff view. upsert_contact (SQL) is mocked; the note store
runs on the in-memory db (mem_db)."""
import config.client_config as cc
from core import contacts as C


def test_add_and_read_client_scoped_notes(mem_db, monkeypatch):
    monkeypatch.setattr(C, "upsert_contact", lambda name, firm, **k: f"cid:{name}:{firm}")
    cid = C.add_contact_note("Jane Doe", "Fidelity", "great meeting", source="test",
                             by="Dana", client_id="usio")
    assert cid == "cid:Jane Doe:Fidelity"
    notes = C.contact_notes(cid, client_id="usio")
    assert len(notes) == 1
    assert notes[0]["note"] == "great meeting" and notes[0]["source"] == "test" and notes[0]["by"] == "Dana"
    # a note added under one client is NOT visible under another (client-scoped)
    assert C.contact_notes(cid, client_id="saro") == []
    # empty / whitespace note is ignored, and no contact/firm -> None
    assert C.add_contact_note("Jane Doe", "Fidelity", "   ", client_id="usio") is None
    assert C.add_contact_note("", "Fidelity", "x", client_id="usio") is None
    assert len(C.contact_notes(cid, client_id="usio")) == 1


def test_newest_first(mem_db, monkeypatch):
    monkeypatch.setattr(C, "upsert_contact", lambda name, firm, **k: "cid1")
    # two notes with explicit ts via monkeypatching the timestamp isn't needed — sort is by ts string
    store = {"cid1": [{"ts": "2026-01-01 09:00", "note": "old"},
                      {"ts": "2026-03-01 09:00", "note": "new"}]}
    mem_db[("usio", "contact_notes.json")] = store
    assert [n["note"] for n in C.contact_notes("cid1", client_id="usio")] == ["new", "old"]


def test_all_contact_notes_aggregates_across_clients(mem_db, monkeypatch):
    monkeypatch.setattr(C, "upsert_contact", lambda name, firm, **k: "cidX")
    monkeypatch.setattr(cc, "CLIENT_REGISTRY", {"usio": {}, "saro": {}})
    C.add_contact_note("A", "B", "from-usio", client_id="usio")
    C.add_contact_note("A", "B", "from-house", client_id="_house")   # staff/global scope
    alln = C.all_contact_notes("cidX")
    assert len(alln) == 2
    assert {(n["note"], n["client"]) for n in alln} == {("from-usio", "usio"), ("from-house", "_house")}
