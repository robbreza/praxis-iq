"""Pin the loop-readiness assessment (core.loop_readiness.assess): each earnings-script /
Q&A input reports ready/waiting correctly, the optional research-notes stage doesn't block
'fully lit', and the required-count / fully-lit summary is right. Hermetic — the subsystem
reads (speakers, transcripts, inbox_queue) are monkeypatched and the workflow state comes
from the in-memory `mem_db` store."""
import pytest

from core import loop_readiness as lr


@pytest.fixture
def lr_env(mem_db, monkeypatch):
    """Controllable subsystem stubs. Defaults = a bare client with nothing provided."""
    state = {"period": "Q2 2026", "confirmed": False, "notes": 0, "transcript": None}
    monkeypatch.setattr(lr, "get_active_client_id", lambda: "acme", raising=False)
    monkeypatch.setattr(lr.speakers, "current_period", lambda cid=None: state["period"], raising=False)
    monkeypatch.setattr(lr.speakers, "is_confirmed", lambda p, cid=None: state["confirmed"], raising=False)
    monkeypatch.setattr(lr.inbox_queue, "list_items_by_category",
                        lambda cat, client_id=None: [{}] * state["notes"], raising=False)
    monkeypatch.setattr(lr.transcripts, "get_transcript",
                        lambda q, cid=None: state["transcript"], raising=False)
    return {"state": state, "db": mem_db}


def _stage(res, key):
    return next(s for s in res["stages"] if s["key"] == key)


def test_bare_client_nothing_ready(lr_env):
    res = lr.assess("acme")
    assert res["ready_required"] == 0 and res["fully_lit"] is False
    assert all(not s["ready"] for s in res["stages"])
    # every waiting stage names what to provide and what it unlocks
    for s in res["stages"]:
        assert s["waiting_for"] and s["todo"] and s["unlocks"]


def test_stages_light_up_from_workflow_state(lr_env):
    lr_env["state"]["confirmed"] = True
    lr_env["state"]["notes"] = 2
    lr_env["state"]["transcript"] = {"full_text": "Operator... prepared remarks... Q&A..."}
    # seed the client's workflow state in the in-memory db
    lr_env["db"][("acme", "script_workflow_state.json")] = {
        "q2_numbers": {"rev": 102.5},
        "script_text": {"ir_open": "Welcome.", "cfo_fin": "Revenue was $102.5M."},
        "adversarial_qa": {"items": [{"question": "Q1?", "source": "ai"},
                                     {"question": "Q2?", "source": "recurring"}]},
    }
    res = lr.assess("acme")
    assert _stage(res, "speakers")["ready"]
    assert _stage(res, "cfo_numbers")["ready"]
    assert _stage(res, "script")["ready"] and "2 section" in _stage(res, "script")["detail"]
    assert _stage(res, "research")["ready"]
    assert _stage(res, "adversarial")["ready"]        # has an AI-sourced item
    assert _stage(res, "transcript")["ready"]
    assert res["fully_lit"] and res["ready_required"] == res["total_required"]


def test_adversarial_needs_an_ai_item_not_only_recurring(lr_env):
    lr_env["db"][("acme", "script_workflow_state.json")] = {
        "adversarial_qa": {"items": [{"question": "recurring only", "source": "recurring"}]}}
    assert not _stage(lr.assess("acme"), "adversarial")["ready"]


def test_optional_research_does_not_block_fully_lit(lr_env):
    lr_env["state"]["confirmed"] = True
    lr_env["state"]["notes"] = 0                       # research notes absent (optional)
    lr_env["state"]["transcript"] = {"full_text": "call text"}
    lr_env["db"][("acme", "script_workflow_state.json")] = {
        "q2_numbers": {"rev": 100.0},
        "script_text": {"ir_open": "x"},
        "adversarial_qa": {"items": [{"question": "q", "source": "ai"}]}}
    res = lr.assess("acme")
    assert not _stage(res, "research")["ready"]        # research is waiting...
    assert res["fully_lit"]                            # ...but it's optional, so loop is fully lit
    assert _stage(res, "research")["optional"] is True


def test_no_period_still_assesses(lr_env):
    lr_env["state"]["period"] = None
    res = lr.assess("acme")
    assert res["period"] is None
    assert not _stage(res, "speakers")["ready"]
    assert not _stage(res, "transcript")["ready"]
