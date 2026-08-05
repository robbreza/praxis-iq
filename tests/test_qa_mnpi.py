"""Pin the Reg FD MNPI scan (shareholder_reply.scan_mnpi) used by the Promote-to-KB
guardrail: legitimate PUBLIC answers must pass clean (no false positives that would
train the IR team to ignore the warning), and forward-looking / unreleased-period
language must flag with the right reasons. Pure regex — no DB, no AI."""
from core import shareholder_reply as sr


def test_safe_public_answers_pass_clean():
    for txt in (
        "Northlake does not currently pay a dividend and is reinvesting in the business. "
        "Any change would be announced publicly.",
        "Our SEC filings and press releases are available on EDGAR and in the Investor Relations "
        "section of our website.",
        "Our transfer agent is Continental Stock Transfer & Trust; please contact them for share matters.",
    ):
        assert not sr.scan_mnpi(txt)["flagged"], f"false positive on: {txt}"


def test_forward_looking_statement_flags():
    r = sr.scan_mnpi("We expect margins to improve in the second half of the year.")
    assert r["flagged"]
    assert "forward-looking statement" in r["reasons"]
    assert "half-year outlook" in r["reasons"]


def test_current_quarter_and_guidance_flag():
    r = sr.scan_mnpi("So far this quarter revenue is tracking ahead and we are on track to beat guidance.")
    assert r["flagged"]
    assert "current (unreleased) quarter" in r["reasons"]
    assert "guidance / outlook reference" in r["reasons"]
    assert "forward commitment" in r["reasons"]  # "on track to"


def test_offending_phrases_returned_for_display():
    r = sr.scan_mnpi("Our outlook for next quarter is strong; we're targeting double-digit growth.")
    assert r["flagged"]
    assert any("targeting" in p.lower() for p in r["phrases"])
    assert any("next quarter" in p.lower() for p in r["phrases"])


def test_empty_and_none_are_clean():
    assert not sr.scan_mnpi("")["flagged"]
    assert not sr.scan_mnpi(None)["flagged"]
    assert sr.scan_mnpi("")["phrases"] == []
