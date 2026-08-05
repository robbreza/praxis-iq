"""Pin the number tie-out audit (earnings_page._number_tieout): every figure spoken in
the assembled script tied to the submitted actuals. The valuable, fragile parts are the
rounding-aware equality (so "$103M" ties out to a submitted 102.5 but a typo'd "$102.3M"
does not) and the keyword-anchored near-miss (so a "$100M guide" / "$102M Street"
comparison right next to revenue is NOT flagged as a misstated revenue). The assembled
script and the consensus lookup are monkeypatched, so this is pure logic — no DB/config."""
from page_modules_nicegui import earnings_page as ep


def _wire(monkeypatch, script, consensus=102.0):
    monkeypatch.setattr(ep, "_assembled_script_text", lambda ss: script)
    monkeypatch.setattr(ep.market_data, "consensus_rev_value", lambda: consensus)


def test_exact_figures_tie_out(monkeypatch):
    _wire(monkeypatch, "Revenue was $102.5 million; adjusted EBITDA was $14.5 million; gross margin 24 percent.")
    t = ep._number_tieout({"q2_numbers": {"rev": 102.5, "ebitda": 14.5, "gm": 24.0}, "guidance_decision": {}})
    assert t["mismatches"] == []
    assert {"Revenue", "Adjusted EBITDA", "Gross margin"} <= set(t["matched"])


def test_rounded_headline_is_not_a_mismatch(monkeypatch):
    _wire(monkeypatch, "Revenue was $103 million this quarter.")
    t = ep._number_tieout({"q2_numbers": {"rev": 102.5}, "guidance_decision": {}})
    assert t["mismatches"] == []           # $103 is a legit commercial rounding of 102.5
    assert "Revenue" in t["matched"]


def test_typo_flagged_even_amid_guide_and_street(monkeypatch):
    _wire(monkeypatch,
          "Revenue was $102.3 million, ahead of the $100 million guide and $102 million Street.",
          consensus=102.0)
    t = ep._number_tieout({"q2_numbers": {"rev": 102.5}, "guidance_decision": {}})
    labels = [m["label"] for m in t["mismatches"]]
    assert "Revenue" in labels
    m = next(m for m in t["mismatches"] if m["label"] == "Revenue")
    assert round(m["script"], 1) == 102.3 and round(m["source"], 1) == 102.5


def test_comparison_figures_not_false_flagged(monkeypatch):
    # revenue stated correctly; the $100M guide and $102M Street nearby must NOT flag
    _wire(monkeypatch,
          "Revenue was $102.5 million, ahead of the $100 million guide and $102 million Street.",
          consensus=102.0)
    t = ep._number_tieout({"q2_numbers": {"rev": 102.5}, "guidance_decision": {}})
    assert t["mismatches"] == []


def test_submitted_but_unstated_metric_is_omitted(monkeypatch):
    _wire(monkeypatch, "Revenue was $102.5 million.")
    t = ep._number_tieout({"q2_numbers": {"rev": 102.5, "eps": 0.34}, "guidance_decision": {}})
    assert "GAAP EPS" in t["omitted"]
    assert "Revenue" not in t["omitted"]


def test_guidance_range_ties_out(monkeypatch):
    _wire(monkeypatch, "We are raising full-year guidance to $405.9 million to $413.3 million.")
    t = ep._number_tieout({"q2_numbers": {}, "guidance_decision": {"new_low": 405.9, "new_hi": 413.3}})
    assert t["mismatches"] == []
    assert any("guidance" in lbl.lower() for lbl in t["matched"])


def test_empty_script_reports_absent(monkeypatch):
    _wire(monkeypatch, "")
    t = ep._number_tieout({"q2_numbers": {"rev": 102.5}, "guidance_decision": {}})
    assert t["present"] is False


def test_fmt_val_by_metric():
    assert ep._fmt_val(102.5, "Revenue") == "$102.5M"
    assert ep._fmt_val(24.0, "Gross margin") == "24%"
    assert ep._fmt_val(0.34, "GAAP EPS") == "$0.34"
    assert ep._fmt_val(8.9, "Volume processed") == "$8.9B"
