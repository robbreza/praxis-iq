"""Pin the Today-page analyst-vs-guidance classifier (_alignment_rows): out-of-line analysts
rank first, in-line within tolerance, and analysts with no model on file are labelled 'none'
(never fabricated into a position)."""
from page_modules_nicegui.today_page import _alignment_rows

PERIOD = "FY 2026E"
GUIDANCE = {PERIOD: {"Revenue Est ($M)": 100.0, "EPS Est": 0.20}}
ANALYSTS = [
    {"firm": "Above Co", "name": "A", "pt": 5.0, "rating": "Buy"},
    {"firm": "Below Co", "name": "B", "pt": 4.0, "rating": "Buy"},
    {"firm": "Inline Co", "name": "C", "pt": 4.5, "rating": "Buy"},
    {"firm": "NoModel Co", "name": "D", "pt": None, "rating": "Hold"},
]
ESTIMATES = {PERIOD: {
    "Above Co": {"Revenue Est ($M)": 110.0, "EPS Est": 0.20},   # rev +10% -> above
    "Below Co": {"Revenue Est ($M)": 90.0, "EPS Est": 0.20},    # rev -10% -> below
    "Inline Co": {"Revenue Est ($M)": 101.0, "EPS Est": 0.205}, # within 2% / 3% -> inline
    # NoModel Co absent -> none
}}


def test_classification_and_ranking():
    rows, meta = _alignment_rows(ANALYSTS, GUIDANCE, ESTIMATES, PERIOD)
    assert meta["has_guidance"] and meta["guide_rev"] == 100.0 and meta["guide_eps"] == 0.20
    by = {r["firm"]: r for r in rows}
    assert by["Above Co"]["rev_status"] == "above" and abs(by["Above Co"]["rev_pct"] - 0.10) < 1e-9
    assert by["Below Co"]["rev_status"] == "below"
    assert by["Inline Co"]["rev_status"] == "inline" and by["Inline Co"]["eps_status"] == "inline"
    assert by["NoModel Co"]["rev_status"] == "none" and by["NoModel Co"]["has_model"] is False
    # out-of-line (Above/Below) must sort ahead of the in-line and no-model analysts
    assert [r["firm"] for r in rows[:2]] == ["Above Co", "Below Co"] or \
           [r["firm"] for r in rows[:2]] == ["Below Co", "Above Co"]
    assert rows[-1]["firm"] == "NoModel Co"
    assert by["Above Co"]["out_of_line"] and not by["Inline Co"]["out_of_line"]


def test_no_guidance_marks_everything_none():
    rows, meta = _alignment_rows(ANALYSTS, {}, {}, PERIOD)
    assert meta["has_guidance"] is False
    assert all(r["rev_status"] == "none" and r["eps_status"] == "none" for r in rows)
    assert not any(r["out_of_line"] for r in rows)


def test_eps_zero_guide_uses_cent_floor():
    # EPS guide of 0.00 must not divide-by-zero; a $0.005 estimate is within the $0.01 floor.
    g = {PERIOD: {"Revenue Est ($M)": 100.0, "EPS Est": 0.0}}
    e = {PERIOD: {"Above Co": {"Revenue Est ($M)": 100.0, "EPS Est": 0.005}}}
    rows, _ = _alignment_rows([ANALYSTS[0]], g, e, PERIOD)
    assert rows[0]["eps_status"] == "inline"
