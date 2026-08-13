"""Guards for two per-client call-structure upgrades (added after the USIO Q2 FY2026 script-vs-
transcript diff):

  1. speaker_order — a client whose call doesn't follow the default IR->CEO->CRO->CFO shape sets
     `speaker_order` on its record; _active_personas() must honor it (USIO runs CAO-first, CEO last
     with guidance), while a client without one keeps the legacy order.
  2. catalyst_freshness — policy catalysts carry an as-of quarter; the guard flags them stale when
     they predate the quarter being drafted, and stays silent when undated (don't cry wolf).
"""
import os

os.environ.setdefault("LIGHTHOUSE_TELEMETRY_OFF", "1")

from config.client_config import set_active_client_id
from core import guidance_engine as ge
from page_modules_nicegui import earnings_page as ep


def _order(cid):
    set_active_client_id(cid)
    return [role for role, _key, _label in ep._active_personas()]


def test_usio_speaker_order_is_cao_first_ceo_last():
    # Michael White (CAO) opens + delivers financials, Greg Carter (CRO) covers the business,
    # Louis Hoch (CEO) closes with guidance (guidance always follows the LAST persona).
    assert _order("usio") == ["IR", "CFO", "CRO", "CEO"]


def test_default_client_keeps_legacy_order():
    # A client without speaker_order preserves the module PERSONAS order.
    assert _order("saro") == ["IR", "CEO", "CRO", "CFO"]


def test_speaker_order_reorders_without_dropping_or_duplicating_roles():
    roles = _order("usio")
    assert sorted(roles) == sorted(r for r, _k, _l in ep.PERSONAS)   # same set, just reordered
    assert len(roles) == len(set(roles))                            # no dupes


def test_catalyst_freshness_flags_stale_policy_list():
    set_active_client_id("usio")   # known_h2_catalysts_asof = "Q1 2026"
    f = ge.catalyst_freshness("Q2 2026")
    assert f["stale"] is True
    assert f["asof"] == "Q1 2026" and f["current"] == "Q2 2026"
    assert "Q1 2026" in f["note"]


def test_catalyst_freshness_not_stale_when_current():
    set_active_client_id("usio")
    f = ge.catalyst_freshness("Q1 2026")   # drafting the same quarter the list was refreshed
    assert f["stale"] is False and f["note"] == ""


def test_catalyst_freshness_silent_when_undated():
    # A client whose policy never set known_h2_catalysts_asof must NOT be flagged stale.
    set_active_client_id("saro")
    f = ge.catalyst_freshness("Q2 2026")
    assert f["stale"] is False


# ── _clean_persona_draft: strip title artifacts + correct the call-identifier year ──

def test_clean_draft_strips_markdown_title_header():
    set_active_client_id("usio")
    out = ep._clean_persona_draft("# USIO CEO Narrative - Q2 2026 Earnings Call\n\nWe delivered a strong quarter.")
    assert out == "We delivered a strong quarter."


def test_clean_draft_strips_plain_title_line():
    set_active_client_id("usio")
    out = ep._clean_persona_draft("Business Operations Summary\n\nUsio processed $2.47 billion this quarter.")
    assert out == "Usio processed $2.47 billion this quarter."


def test_clean_draft_fixes_call_identifier_year():
    set_active_client_id("usio")   # current_quarter = Q2 2026
    out = ep._clean_persona_draft("Welcome to USIO's second quarter 2025 earnings call. I'm Michael White.")
    assert "second quarter 2026 earnings call" in out
    assert "2025" not in out


def test_clean_draft_leaves_prior_year_comps_alone():
    set_active_client_id("usio")
    # A YoY comparison to the prior year is NOT the call identifier — must survive untouched.
    txt = "Revenue grew 19% versus the second quarter of 2025."
    assert ep._clean_persona_draft(txt) == txt


def test_clean_draft_passes_through_clean_remarks():
    set_active_client_id("usio")
    txt = "Good afternoon. Revenue was $23.7 million, up 19% year over year."
    assert ep._clean_persona_draft(txt) == txt
