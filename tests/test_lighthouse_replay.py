"""Phase 0 guard test — the no-look-ahead invariant must hold. If this ever fails, the whole
credibility of Lighthouse's backtests is compromised, so it runs in CI as a first-class gate."""
import pytest
from lighthouse.replay import AsOf, PointInTimeError


AS_OF = "2024-05-05T21:00:00Z"   # e.g. after the 2024-05-05 session close


def test_knows_past_and_present_not_future():
    a = AsOf(AS_OF)
    assert a.knows("2024-05-05T20:00:00Z")      # earlier same day -> visible
    assert a.knows(AS_OF)                         # exactly at horizon -> visible
    assert not a.knows("2024-05-06T13:30:00Z")    # next day -> NOT visible


def test_visible_filters_and_fails_closed_on_missing_stamp():
    a = AsOf(AS_OF)
    recs = [
        {"id": 1, "knowledge_ts": "2024-05-01T00:00:00Z"},   # past -> kept
        {"id": 2, "knowledge_ts": "2024-06-01T00:00:00Z"},   # future -> dropped
        {"id": 3},                                            # unstamped -> dropped (fail-closed)
    ]
    got = {r["id"] for r in a.visible(recs)}
    assert got == {1}


def test_assert_pit_raises_on_lookahead():
    a = AsOf(AS_OF)
    a.assert_pit("2024-05-04T00:00:00Z", "10-Q")   # fine
    with pytest.raises(PointInTimeError):
        a.assert_pit("2024-05-06T13:30:00Z", "guidance PR")


def test_sql_gate_shape():
    a = AsOf(AS_OF)
    frag, val = a.where_sql("published_at")
    assert frag == "published_at <= %s"
    assert val == a.as_of


def test_knowledge_ts_is_publication_not_content_date():
    """A 10-Q for the quarter ended Mar 31, filed May 5, is knowable May 5 — not Mar 31."""
    a = AsOf("2024-04-15T00:00:00Z")   # mid-April horizon
    assert not a.knows("2024-05-05T00:00:00Z")   # the May-5 filing is NOT yet knowable
