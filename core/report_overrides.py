"""core/report_overrides.py — generic per-report narrative overrides.

The IR Quarterly Board Package keeps its own richer override store
(board_package.EDITABLE_FIELDS + board_package.load/save_overrides). This is the
lightweight shared version for the OTHER reports that each have one editable prose
block — the Earnings Prep Brief's "Read this first" headline, the weekly brief's IR
note. An edit is used on screen AND in the PDF and persists across refreshes, exactly
like the board package.

Per-report, per-client JSON in core.db (key "<report>_narrative_overrides.json"), so a
client's edits never leak across tenants.
"""
from config.client_config import get_active_client_id
from core import db


def _store_key(report):
    return f"{report}_narrative_overrides.json"


def load(report, client_id=None):
    return db.load_json(_store_key(report), {}, client_id=client_id or get_active_client_id()) or {}


def save(report, overrides, client_id=None):
    db.save_json(_store_key(report), overrides or {}, client_id=client_id or get_active_client_id())


def apply(report, field, auto_text, client_id=None):
    """Return the IR-edited text for `field` if one is saved, else the auto text.

    auto_text may be "" (e.g. the weekly brief's IR note, which is empty until the IR
    team writes one) — in that case an unedited report simply has no such block.
    """
    v = (load(report, client_id).get(field) or "").strip()
    return v or (auto_text or "")
