"""Pin the website-traffic ingestion (core.web_ingest): raw web_events grouped by session
into web_flow visitor rows — pages, dwell minutes, downloads (incl. a demo request), and the
firm/lead identity from a self-identify event — and that the result feeds the existing
web_flow analyzer (an identified demo-requester surfaces as a hot prospect). Runs against a
temp SQLite web_events DB + the in-memory `mem_db` JSON store; touches no real tenant."""
import sqlite3

import pytest

from core import db, web_flow, web_ingest


@pytest.fixture
def wdb(monkeypatch, tmp_path):
    """A temp SQLite file for web_events, with the real schema applied. Also stubs the SEC
    public-company index so aggregation never makes a live SEC call (kept hermetic + fast)."""
    path = str(tmp_path / "web.db")
    c = sqlite3.connect(path)
    c.executescript(db._SQLITE_SCHEMA)
    c.commit()
    c.close()
    monkeypatch.setattr(web_ingest.db, "get_connection", lambda: sqlite3.connect(path), raising=False)
    monkeypatch.setattr("core.sec_filings.ticker_name_map", lambda force=False: {}, raising=False)
    monkeypatch.setattr(web_ingest, "_public_idx", {"map": None})
    return path


def _seed(tenant="praxis"):
    # an identified, high-intent lead: two pages, a download, then a demo request
    web_ingest.record_event(tenant, "s1", "pageview", path="/product.html", created_at="2026-08-05T10:00:00+00:00")
    web_ingest.record_event(tenant, "s1", "pageview", path="/pricing.html", created_at="2026-08-05T10:03:00+00:00")
    web_ingest.record_event(tenant, "s1", "download", asset="Security overview", created_at="2026-08-05T10:04:00+00:00")
    web_ingest.record_event(tenant, "s1", "demo_request", org="Meridian IR Advisors",
                            email="ir@meridian.com", created_at="2026-08-05T10:05:00+00:00")
    # an anonymous reader: one page, no download
    web_ingest.record_event(tenant, "s2", "pageview", path="/about.html", created_at="2026-08-05T11:00:00+00:00")


def test_aggregate_builds_visitor_rows(wdb):
    _seed()
    out = web_ingest.aggregate(save=False)
    assert out["sessions"] == 2 and out["identified"] == 1
    lead = next(r for r in out["rows"] if r["category"] == "Identified lead")
    assert lead["org"] == "Meridian IR Advisors"
    assert "Demo request" in lead["downloads"] and "Security overview" in lead["downloads"]
    assert lead["pages"] == 2
    assert lead["is_holder"] is False           # marketing site — a lead, never a holder
    assert lead["minutes"] >= 4                 # 10:00 -> 10:05
    anon = next(r for r in out["rows"] if r["category"] != "Identified lead")
    assert anon["org"] == "New — unidentified" and anon["downloads"] == []


def test_identified_sessions_merge_by_firm(wdb):
    _seed()
    # the SAME firm comes back in a later session (name variant), views another page + a new download
    web_ingest.record_event("praxis", "s3", "pageview", path="/product.html", org="Meridian IR Advisors LLC",
                            created_at="2026-08-07T09:00:00+00:00")
    web_ingest.record_event("praxis", "s3", "pageview", path="/security.html", org="Meridian IR Advisors LLC",
                            created_at="2026-08-07T09:06:00+00:00")
    web_ingest.record_event("praxis", "s3", "download", asset="ROI one-pager", org="Meridian IR Advisors LLC",
                            created_at="2026-08-07T09:07:00+00:00")
    out = web_ingest.aggregate(save=False)
    assert out["sessions"] == 3                                   # raw session count preserved
    leads = [r for r in out["rows"] if r["category"] == "Identified lead"]
    assert len(leads) == 1                                        # both Meridian sessions -> ONE firm row
    m = leads[0]
    assert m["visits"] == 2                                       # two sessions
    assert m["demo_request"] is True                             # carried from the first visit
    # unions across sessions
    assert "ROI one-pager" in m["downloads"] and "Security overview" in m["downloads"]
    assert "/security.html" in m["paths"] and "/pricing.html" in m["paths"]
    assert m["last_visit"] == "2026-08-07"                        # latest


def test_feeds_web_flow_analyzer(wdb, mem_db):
    _seed()
    web_ingest.aggregate(tenant="praxis", save=True)     # persists via the in-memory store
    d = web_flow.compose("praxis")
    assert d["available"]
    assert d["n_visitors"] == 2 and d["n_downloaders"] == 1
    # the identified demo-requester is a hot prospect: high intent, not a holder
    assert any(v["org"] == "Meridian IR Advisors" for v in d["hot_prospects"])


def test_empty_tenant_is_clean(wdb):
    out = web_ingest.aggregate(tenant="praxis", save=False)
    assert out == {"sessions": 0, "identified": 0, "rows": []}
