"""core/press_release.py — the earnings PRESS RELEASE, the OTHER place guidance lives.

A public company states guidance in TWO artifacts, and they must agree:
  1. the earnings PRESS RELEASE (8-K, Exhibit 99.1) — the FORMAL, verbatim numbers in a dedicated
     "Outlook" / "Guidance" section, plus the financial tables. This is the authoritative source the
     Street quotes and models off of.
  2. the earnings CALL TRANSCRIPT — management REITERATES the same numbers verbally and adds the color
     (why, H2 visibility, tone).

The old demo only had the transcript, so "prior guidance" was a transcript PARAPHRASE. This stores the
per-client, per-quarter release with a structured `guidance` block, so:
  * the guidance workflow reads the AUTHORITATIVE prior guide (the press-release Outlook), not a quote;
  * this quarter's decided range can be verified consistent across BOTH the release AND the transcript;
  * most companies guide only ONE year out — the release carries the full-year guide; FY+1 is the
    Street's number, never presented here as company guidance.

Pure store (db-backed JSON per client), no network. Structured so a real client's release can be
uploaded/parsed into the same shape later.
"""
from core import db

_KEY = "earnings_press_releases.json"


def _load(client_id=None):
    return db.load_json(_KEY, {}, client_id=client_id) or {}


def get(quarter, client_id=None):
    """The full release record for a quarter, or None."""
    if not quarter:
        return None
    return _load(client_id).get(quarter)


def list_releases(client_id=None):
    """{quarter: release} for every stored release, newest-quarter handling left to the caller."""
    return _load(client_id)


def save(quarter, release, client_id=None):
    store = _load(client_id)
    store[quarter] = dict(release, quarter=quarter)
    db.save_json(_KEY, store, client_id=client_id)
    return release


def guidance(quarter, client_id=None):
    """The structured guidance block from a release's Outlook section:
       {statement, fy_low, fy_high, action, ebitda_margin_pct, ...} or None."""
    return (get(quarter, client_id) or {}).get("guidance")


def guidance_statement(quarter, client_id=None):
    """The formal guidance SENTENCE from the Outlook section — the authoritative prior guide, verbatim
    (not a transcript paraphrase). This is what this quarter's language must stay consistent with."""
    g = guidance(quarter, client_id) or {}
    return g.get("statement")
