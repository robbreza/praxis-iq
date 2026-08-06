"""Pin core.sales_pipeline: the unified 'praxis' lead board — inbound-first priority,
manual reply-marking, the follow-up reminder surfacer, and idempotent inbound ingestion.
All against the in-memory store (mem_db); no real tenant is touched."""
from core import sales_pipeline as sp


def _enrich(ticker="WAL", company="Western Alliance", ir="Miles Pondelik"):
    return {"ticker": ticker, "company": company, "ir_name": ir,
            "ir_title": "VP Investor Relations", "ir_kind": "ir",
            "suggested_email": "ir@westernalliance.com",
            "domain": "westernalliance.com", "market_cap": 8_000_000_000}


def test_add_outbound_starts_identified(mem_db):
    lead = sp.add_outbound(_enrich())
    assert lead["source"] == "outbound" and lead["stage"] == "identified"
    assert lead["ticker"] == "WAL" and lead["email"] == "ir@westernalliance.com"
    assert lead["contact_name"] == "Miles Pondelik"
    assert sp.lead_id("outbound", "Western Alliance", "WAL") == "out:WAL"


def test_log_touch_advances_and_sets_followup(mem_db):
    lead = sp.add_outbound(_enrich())
    sp.log_touch(lead["id"], kind="email", note="first outreach")
    got = sp.list_leads()[0]
    assert got["stage"] == "contacted"                      # identified → contacted
    assert got["last_touch"] and got["next_follow_up"]      # follow-up clock started
    assert any(a["kind"] == "email" for a in got["activity"])
    # a second touch does NOT bump an already-advanced lead back
    sp.log_touch(lead["id"], kind="call")
    assert sp.list_leads()[0]["stage"] == "contacted"


def test_manual_reply_marking(mem_db):
    lead = sp.add_outbound(_enrich())
    sp.mark_replied(lead["id"])
    assert sp.list_leads()[0]["stage"] == "replied"


def test_won_is_terminal_and_drops_out(mem_db):
    lead = sp.add_outbound(_enrich())
    sp.set_follow_up(lead["id"], "2000-01-01")              # would be overdue
    sp.set_stage(lead["id"], "won")
    got = sp.list_leads()[0]
    assert got["stage"] == "won" and got["next_follow_up"] is None
    assert sp.due_followups() == []                         # terminal never reminds
    assert sp.summary()["open"] == 0 and sp.summary()["won"] == 1


def test_inbound_ingest_idempotent_and_preserves_stage(mem_db):
    mem_db[("praxis", "web_flow_visitors.json")] = [
        {"org": "Acme Corp", "category": "Identified lead", "demo_request": True,
         "email": "cfo@acme.com", "ticker": None, "downloads": ["Demo request"]},
        {"org": "New — unidentified", "category": "New — unidentified"},   # skipped
    ]
    assert sp.ingest_inbound() == 1                          # one identified lead
    lid = sp.lead_id("inbound", "Acme Corp")
    sp.set_stage(lid, "meeting")                             # advance it
    assert sp.ingest_inbound() == 0                          # re-sync creates nothing new
    lead = next(l for l in sp.list_leads() if l["id"] == lid)
    assert lead["stage"] == "meeting"                        # stage preserved across re-sync
    assert lead["demo_request"] is True and lead["source"] == "inbound"


def test_inbound_demo_request_outranks_outbound(mem_db):
    sp.add_outbound(_enrich())                               # outbound, identified
    mem_db[("praxis", "web_flow_visitors.json")] = [
        {"org": "Hot Lead Inc", "category": "Identified lead", "demo_request": True,
         "email": "ir@hot.com", "downloads": ["Demo request"]}]
    sp.ingest_inbound()
    assert sp.list_leads()[0]["company"] == "Hot Lead Inc"   # inbound demo request is #1


def test_overdue_outranks_current_and_appears_in_reminders(mem_db):
    a = sp.add_outbound(_enrich("AAA", "Alpha"))
    b = sp.add_outbound(_enrich("BBB", "Bravo"))
    sp.set_stage(a["id"], "contacted")                       # current follow-up (future)
    sp.set_stage(b["id"], "contacted")
    sp.set_follow_up(b["id"], "2000-01-01")                  # Bravo is overdue
    assert sp.list_leads()[0]["ticker"] == "BBB"             # overdue floats up
    due = sp.due_followups()
    assert [d["ticker"] for d in due] == ["BBB"]


def test_add_outbound_carries_onboarding_facts(mem_db):
    lead = sp.add_outbound(_enrich())
    assert lead["domain"] == "westernalliance.com" and lead["market_cap"] == 8_000_000_000
    assert lead["onboarded_cid"] is None


def test_mark_onboarded(mem_db):
    lead = sp.add_outbound(_enrich())
    sp.set_stage(lead["id"], "won")
    sp.mark_onboarded(lead["id"], "wal")
    got = sp.list_leads()[0]
    assert got["onboarded_cid"] == "wal" and got["stage"] == "won"
    assert got["next_follow_up"] is None
    assert any(a["kind"] == "onboarded" for a in got["activity"])


def test_summary_counts(mem_db):
    sp.add_outbound(_enrich("AAA", "Alpha"))
    b = sp.add_outbound(_enrich("BBB", "Bravo"))
    sp.set_stage(b["id"], "won")
    s = sp.summary()
    assert s["total"] == 2 and s["open"] == 1 and s["won"] == 1
    assert s["by_stage"]["identified"] == 1 and s["by_stage"]["won"] == 1
