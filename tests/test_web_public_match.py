"""Pin the public-company matcher (core.web_ingest.public_match): an identified visitor
firm is matched to a ticker ONLY on a conservative distinctive-token match against SEC
company_tickers — no fuzzy guessing — and the ticker flows onto the visitor row and through
the web_flow analyzer. SEC index is monkeypatched (no live SEC call)."""
import pytest

from core import web_ingest


@pytest.fixture(autouse=True)
def fake_sec(monkeypatch):
    # A tiny SEC ticker→name map; reset the process cache so each test rebuilds from it.
    monkeypatch.setattr("core.sec_filings.ticker_name_map",
                        lambda force=False: {"ROP": "Roper Technologies, Inc.",
                                             "USIO": "Usio, Inc.",
                                             "AAPL": "Apple Inc."}, raising=False)
    monkeypatch.setattr(web_ingest, "_public_idx", {"map": None})
    return None


def test_public_firm_matches_ticker():
    assert web_ingest.public_match("Roper Technologies")["ticker"] == "ROP"
    assert web_ingest.public_match("USIO, INC.")["ticker"] == "USIO"        # case/suffix-insensitive
    assert web_ingest.public_match("Apple Inc.")["ticker"] == "AAPL"


def test_private_or_unknown_firm_is_none():
    assert web_ingest.public_match("Meridian IR Advisors LLC") is None      # not public
    assert web_ingest.public_match("New — unidentified") is None
    assert web_ingest.public_match("") is None
    assert web_ingest.public_match(None) is None


def test_ticker_flows_onto_visitor_row():
    row = web_ingest._session_to_visitor([
        {"event_type": "pageview", "created_at": "2026-08-05T10:00:00+00:00"},
        {"event_type": "demo_request", "org": "Roper Technologies", "email": "",
         "created_at": "2026-08-05T10:02:00+00:00"},
    ])
    assert row["org"] == "Roper Technologies" and row["ticker"] == "ROP"

    anon = web_ingest._session_to_visitor(
        [{"event_type": "pageview", "created_at": "2026-08-05T11:00:00+00:00"}])
    assert anon["ticker"] is None and anon["category"] == "New — unidentified"
