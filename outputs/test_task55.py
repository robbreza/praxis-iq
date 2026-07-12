"""
Sandbox verification for task #55 fixes:
- investors_page.py: _client_ev_rev(), NDR Requests (_seed/_load/_save_ndr_requests)
- reports_page.py: Weekly Briefs real-generation, All Downloads real-file-check

Run against the real project location (no bridging needed now that the
Desktop folder is directly mounted).
"""
import sys
sys.path.insert(0, "/sessions/sweet-dreamy-fermat/mnt/Praxis_Point_IR")

import os
from datetime import datetime, timedelta
from unittest import mock

# NOTE: this script is run with cwd = an isolated scratch dir (not the real
# project folder), so core.db's relative DB_PATH ("data/app.db") resolves to
# a throwaway file there instead of touching the real project's live SQLite
# data. Do not run this from inside the project folder itself.

import core.db as db
import core.market_data as market_data
import config.client_config as client_config

# ── Test _client_ev_rev() ──────────────────────────────────────────────
import page_modules_nicegui.investors_page as investors_page

FAKE_SNAPSHOT = {"last_price": 2.50, "change_pct": 1.2}

with mock.patch("core.market_data.get_snapshot", return_value=FAKE_SNAPSHOT):
    result = investors_page._client_ev_rev()
    assert result is not None, "Expected a computed multiple, got None"
    assert isinstance(result, float)
    print("TEST1_CLIENT_EV_REV_COMPUTES_REAL_VALUE_OK result=%s" % result)

with mock.patch("core.market_data.get_snapshot", return_value=None):
    # investors_page imported CT by name, so patch its own module-level
    # reference (patching config.client_config.CT wouldn't reach it).
    with mock.patch("page_modules_nicegui.investors_page.CT", side_effect=lambda k, d=None: d):
        result2 = investors_page._client_ev_rev()
        assert result2 is None, "Expected None when no price available, got %s" % result2
        print("TEST2_CLIENT_EV_REV_NONE_WHEN_NO_PRICE_OK")

# ── Test NDR Requests seed/load/save/resolve ───────────────────────────
seeded = investors_page._seed_ndr_requests()
assert len(seeded) == 3
today = datetime.now().date()
for r in seeded:
    received_date = datetime.strptime(r["received"], "%b %d, %Y").date()
    assert received_date <= today, "Seed date %s is in the future!" % r["received"]
    assert (today - received_date).days < 30, "Seed date %s is implausibly stale" % r["received"]
    assert r["resolved"] is False
print("TEST3_NDR_SEED_DATES_ARE_RELATIVE_NOT_HARDCODED_OK")

loaded = investors_page._load_ndr_requests()
assert len(loaded) == 3
print("TEST4_NDR_LOAD_SEEDS_ONCE_OK")

loaded2 = investors_page._load_ndr_requests()
assert loaded2 == loaded, "Second load should return the persisted (not re-seeded) list"
print("TEST5_NDR_LOAD_IS_IDEMPOTENT_OK")

# Resolve one and confirm it drops from the unresolved filter used by _render_big_picture
loaded2[0]["resolved"] = True
investors_page._save_ndr_requests(loaded2)
after = investors_page._load_ndr_requests()
unresolved = [r for r in after if not r.get("resolved")]
assert len(unresolved) == 2, "Expected 2 unresolved after resolving 1, got %d" % len(unresolved)
print("TEST6_NDR_RESOLVE_REMOVES_FROM_UNRESOLVED_FILTER_OK")

# Log a brand-new request (mimics _render_ndr_requests_tab's log_request())
current = investors_page._load_ndr_requests()
current.append({
    "id": "test-new-1", "analyst": "Test Analyst", "firm": "Test Firm",
    "city": "Denver", "metro": "Texas / Denver", "reason": "Test reason",
    "received": datetime.now().strftime("%b %d, %Y"), "resolved": False, "seeded": False,
})
investors_page._save_ndr_requests(current)
final = investors_page._load_ndr_requests()
assert len(final) == 4
assert any(r["id"] == "test-new-1" for r in final)
print("TEST7_NDR_LOG_NEW_REQUEST_OK")

print("ALL_INVESTORS_PAGE_UNIT_TESTS_PASSED")

# ── Test reports_page.py Weekly Briefs ─────────────────────────────────
import page_modules_nicegui.reports_page as reports_page

seeded_briefs = reports_page._seed_weekly_briefs()
assert len(seeded_briefs) == 3
assert all(b.get("seeded") is True for b in seeded_briefs)
print("TEST8_WEEKLY_BRIEFS_SEED_OK")

loaded_briefs = reports_page._load_weekly_briefs()
assert len(loaded_briefs) == 3
print("TEST9_WEEKLY_BRIEFS_LOAD_SEEDS_ONCE_OK")

with mock.patch("core.market_data.get_snapshot", return_value={"last_price": 3.14}), \
     mock.patch("core.activity_log.count_this_week", return_value=7), \
     mock.patch("core.db.load_json", side_effect=lambda k, d=None: d):
    composed = reports_page._compose_weekly_brief()
    assert "$3.14" in composed
    assert "7 IR action" in composed
    assert "not yet started" in composed
    print("TEST10_COMPOSE_WEEKLY_BRIEF_FROM_LIVE_DATA_OK: %s" % composed)

with mock.patch("core.market_data.get_snapshot", return_value=None):
    composed2 = reports_page._compose_weekly_brief()
    assert "not yet fetched" in composed2, "Should gracefully degrade, not fabricate a price"
    print("TEST11_COMPOSE_WEEKLY_BRIEF_GRACEFUL_NO_PRICE_OK: %s" % composed2)

print("ALL_REPORTS_PAGE_UNIT_TESTS_PASSED")

# ── Full NiceGUI render pass ────────────────────────────────────────────
from nicegui import ui
import page_modules_nicegui.nav as nav

nav.go_to = lambda *a, **k: None
nav.highlights = {}

with ui.column():
    investors_page.render_investors_page()
print("TEST12_INVESTORS_PAGE_FULL_RENDER_OK")

with ui.column():
    reports_page.render_reports_page()
print("TEST13_REPORTS_PAGE_FULL_RENDER_OK")

print("ALL_TASK55_TESTS_PASSED")
