"""Guard the in-process scheduler's run predicate: it must fire once per weekday after the US close,
and never pre-close, on weekends, or twice in a day."""
from datetime import datetime, timezone
from lighthouse.scheduler import _should_run


def _dt(y, mo, d, h):
    return datetime(y, mo, d, h, 0, tzinfo=timezone.utc)


def test_fires_weekday_after_close_once():
    assert _should_run(_dt(2026, 7, 28, 22), None) is True          # Tue 22:00 UTC, not run
    assert _should_run(_dt(2026, 7, 28, 23), None) is True


def test_not_before_close():
    assert _should_run(_dt(2026, 7, 28, 19), None) is False          # pre-close


def test_not_on_weekend():
    assert _should_run(_dt(2026, 7, 25, 22), None) is False          # Sat
    assert _should_run(_dt(2026, 7, 26, 22), None) is False          # Sun


def test_not_twice_same_day():
    assert _should_run(_dt(2026, 7, 28, 22), "2026-07-28") is False  # already ran today
