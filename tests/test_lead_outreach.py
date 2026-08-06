"""Pin the lead-outreach helpers (core.lead_outreach): the deterministic fallback draft is
personalized to the lead's activity (demo request, pages viewed, company), the page-phrase
humanizes paths, and the LinkedIn search URL is a compliant people-search link. The AI path
is monkeypatched off so these stay hermetic and fast."""
import pytest

from core import lead_outreach


@pytest.fixture(autouse=True)
def no_ai(monkeypatch):
    # Force the deterministic fallback (no live model call).
    monkeypatch.setattr("core.email_classifier._call_claude", lambda *a, **k: None, raising=False)


def test_pages_phrase_humanizes_paths():
    assert lead_outreach.pages_phrase(["/pricing"]) == "pricing"
    assert lead_outreach.pages_phrase(["/product.html", "/pricing"]) == "the product overview and pricing"
    assert lead_outreach.pages_phrase(["/", "/product", "/security"]) == \
        "the homepage, the product overview, and security and data"
    assert lead_outreach.pages_phrase([]) == ""


def test_name_from_email():
    assert lead_outreach.name_from_email("robert.breza@acme.com") == "Robert Breza"
    assert lead_outreach.name_from_email("") == ""


def test_linkedin_url_uses_name_and_company():
    url = lead_outreach.linkedin_search_url({"email": "jane.doe@roper.com", "org": "Roper Technologies"})
    assert url.startswith("https://www.linkedin.com/search/results/people/?keywords=")
    assert "Jane" in url and "Roper" in url


def test_demo_request_draft_references_the_demo():
    d = lead_outreach.draft_email({"org": "Roper Technologies", "ticker": "ROP", "demo_request": True,
                                   "paths": ["/demo"], "downloads": ["Demo request"], "intent_label": "High intent"})
    assert "demo" in d["subject"].lower()
    assert "demo" in d["body"].lower() and "Praxis Point" in d["body"]


def test_reader_draft_references_pages_not_demo():
    d = lead_outreach.draft_email({"org": "Meridian IR", "demo_request": False,
                                   "paths": ["/product.html", "/pricing"], "downloads": [],
                                   "intent_label": "Engaged reader"})
    assert d["subject"] == "IRconnect for Meridian IR"
    assert "product overview" in d["body"] and "pricing" in d["body"]


def test_anonymous_lead_has_generic_subject():
    d = lead_outreach.draft_email({"org": "New — unidentified", "paths": ["/"], "downloads": []})
    assert d["subject"] == "IRconnect — a quick hello"
