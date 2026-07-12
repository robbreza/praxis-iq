"""
core/signals.py — shared "mute a risk signal" primitive.

Backs the mute/snooze button on the closed-loop resolve/note/reset signal
cards used across today_page.py's Risk Signals and markets_page.py's IR
Risk Dashboard. Muting hides a signal card for a chosen window without
resolving or noting it — the underlying issue is still open, it's just not
nagging today. See TRAINING_MANUAL_NOTES.md #2 for the full explanation
(written for end users, not developers).

Deliberately NOT wired into reports_page.py's Reg FD Flags (each entry is
a dated, individually-reviewed legal/compliance record — a HIGH-risk MNPI
flag or an open 8-K isn't a recurring daily nag you'd want to snooze for a
week, it's a specific thing legal needs to see) or earnings_page.py's
5-stage Script Generation gates (those are mandatory sequential sign-offs,
not optional signals — muting a stage gate wouldn't make sense).

This module never imports nicegui — same boundary as every other core/
module. Each caller (a page module) still owns its own state dict, its own
state-file save call, and its own ui.notify/nav.go_to after calling these.
"""

from datetime import datetime, timedelta

from core import activity_log

MUTE_OPTIONS = [(1, "1 day"), (3, "3 days"), (7, "7 days"), (30, "30 days")]


def is_muted(state, key):
    """True if `state` has an unexpired "<key>_muted_until" timestamp."""
    until = state.get(f"{key}_muted_until")
    if not until:
        return False
    try:
        return datetime.now() < datetime.fromisoformat(until)
    except ValueError:
        return False


def muted_until_label(state, key, fmt="%b %d, %Y"):
    until = state.get(f"{key}_muted_until")
    try:
        return datetime.fromisoformat(until).strftime(fmt)
    except (TypeError, ValueError):
        return "—"


def mute(state, key, days, launched_from, client_id=None):
    """Mutates `state` in place and logs a signal_muted event. Caller is
    still responsible for persisting `state` (each page has its own state
    file / save function) and refreshing the page."""
    state[f"{key}_muted_until"] = (datetime.now() + timedelta(days=days)).isoformat()
    activity_log.log_event("signal_muted", entity=key, client_id=client_id, days=days, launched_from=launched_from)


def unmute(state, key):
    state.pop(f"{key}_muted_until", None)
