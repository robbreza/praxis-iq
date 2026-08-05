"""Pin the Q&A prep helpers (earnings_page): source tagging, dedup key, quarter
ordering, the cross-quarter accuracy series, and the responder-suggestion heuristic
(CFO for financial questions, CEO for strategy/ambiguous). All pure — no DB/config."""
from page_modules_nicegui import earnings_page as ep


def test_qa_key_normalizes_for_dedup():
    # dedups on case, collapsed whitespace, punctuation/symbols -> spaces
    assert ep._qa_key("Capital Allocation — buyback?") == ep._qa_key("capital allocation   buyback")
    assert ep._qa_key("Capital allocation — buyback or M&A?").startswith("capital allocation")
    assert ep._qa_key("") == ""


def test_item_source_resolution():
    assert ep._qa_item_source({"source": "recurring"}) == "recurring"
    assert ep._qa_item_source({"manual": True}) == "manual"
    assert ep._qa_item_source({}) == "ai"  # legacy items with no source default to AI


def test_quarter_sort_key_orders_chronologically():
    ordered = sorted(["Q2 2026", "Q4 2025", "Q1 2026", "Q3 2025"], key=ep._quarter_sort_key)
    assert ordered == ["Q3 2025", "Q4 2025", "Q1 2026", "Q2 2026"]


def test_prep_accuracy_series_sorted_and_filtered():
    ss = {"prep_vs_actual": {
        "Q2 2026": {"qa": {"hit_rate": 29, "hits": [1, 2], "misses": [1, 2, 3, 4, 5], "surprises": [1, 2]}},
        "Q1 2026": {"qa": {"hit_rate": 17, "hits": [1], "misses": [1, 2, 3, 4, 5], "surprises": [1, 2]}},
        "Q3 2026": {"qa": {"hit_rate": None}},        # no rate yet -> excluded
    }}
    s = ep._prep_accuracy_series(ss)
    assert [p["quarter"] for p in s] == ["Q1 2026", "Q2 2026"]
    assert s[0]["rate"] == 17 and s[0]["total"] == 6
    assert s[1]["rate"] == 29 and s[1]["total"] == 7 and s[1]["surprises"] == 2


def test_prep_accuracy_series_empty():
    assert ep._prep_accuracy_series({}) == []
    assert ep._prep_accuracy_series({"prep_vs_actual": {"Q1 2026": {"qa": {"hit_rate": None}}}}) == []


def test_suggest_responder_routes_by_topic():
    opts = ["IR — Dana", "CEO — Marcus", "CFO — Priya"]
    assert ep._suggest_responder("What is driving the change in gross margin?", opts) == "CFO — Priya"
    assert ep._suggest_responder("What are your EPS and EBITDA assumptions?", opts) == "CFO — Priya"
    assert ep._suggest_responder("How defensible is your competitive positioning?", opts) == "CEO — Marcus"
    assert ep._suggest_responder("Tell us about the product roadmap and pipeline.", opts) == "CEO — Marcus"


def test_suggest_responder_default_and_empty():
    opts = ["IR — Dana", "CEO — Marcus", "CFO — Priya"]
    # ambiguous / no keyword -> defaults to the CEO
    assert ep._suggest_responder("Any general comment on the environment?", opts) == "CEO — Marcus"
    # no roster at all
    assert ep._suggest_responder("anything", []) == "Unassigned"


def test_role_of_option():
    assert ep._role_of_option("CFO — Priya Raman") == "CFO"
    assert ep._role_of_option("no dash here") == ""
