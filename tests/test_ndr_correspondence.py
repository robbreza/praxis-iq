"""Pin core.ndr_correspondence: the reply trail + status on an inbound NDR request. In-memory
store (mem_db); activity_log stubbed so no SQL is touched."""
import pytest

from core import ndr_correspondence as nc


@pytest.fixture
def seeded(mem_db, monkeypatch):
    monkeypatch.setattr(nc.activity_log, "log_event", lambda *a, **k: None)
    mem_db[("t", "ndr_requests.json")] = [
        {"id": "r1", "analyst": "Jane Doe", "firm": "Fidelity", "city": "Boston", "reason": "meet mgmt"}]
    return mem_db


def test_status_awaiting_before_any_reply(seeded):
    assert nc.status(seeded[("t", "ndr_requests.json")][0]) == "awaiting"


def test_record_reply_flips_to_replied_and_logs_trail(seeded):
    req = nc.record_reply("r1", "jane@fidelity.com", "Re: your meeting request",
                          "Hi Jane, glad to coordinate.", via="Zoho", client_id="t")
    assert req is not None
    assert nc.status(req) == "replied" and req["replied_at"]
    entries = nc.trail(req)
    assert len(entries) == 1 and entries[0]["direction"] == "out"
    assert entries[0]["to"] == "jane@fidelity.com" and entries[0]["via"] == "Zoho"
    # persisted to the store
    assert seeded[("t", "ndr_requests.json")][0]["response_status"] == "replied"


def test_record_reply_unknown_request_returns_none(seeded):
    assert nc.record_reply("nope", "x@y.com", "s", "b", client_id="t") is None


def test_second_reply_appends_to_trail(seeded):
    nc.record_reply("r1", "jane@fidelity.com", "Re: meeting", "first", client_id="t")
    req = nc.record_reply("r1", "jane@fidelity.com", "Re: meeting (2)", "follow-up", client_id="t")
    assert len(nc.trail(req)) == 2


def test_inbound_reply_does_not_count_as_our_response(seeded):
    req = nc.record_inbound("r1", "jane@fidelity.com", "Re: your note", "Thanks!", client_id="t")
    assert nc.status(req) == "awaiting"                      # THEIR reply isn't OUR reply
    assert nc.trail(req)[0]["direction"] == "in"
