"""Pin the peer-tier synthesis (Spec 14 capstone): tier membership (trading excludes indices/ETFs),
the cross-lens overlaps, and the surfaced insights. Pure logic on lens-cache fixtures."""
from lighthouse import peer_synthesis as ps


def _fixtures():
    comovement = {"top_correlates": [
        {"ticker": "IWO", "category": "small growth"}, {"ticker": "UPST", "category": "fintech"},
        {"ticker": "SOFI", "category": "fintech"}, {"ticker": "SPY", "category": "broad market"}],
        "sparse_r2": 0.06, "defined_basket_r2": 0.02}
    coownership = {"n_holders": 25, "n_focused": 2}
    coverage = {"payments_coverage_peers": [{"ticker": "RPAY"}, {"ticker": "PRTH"}, {"ticker": "FPAY"}],
                "new_payments_peers": ["PRTH", "FPAY"], "defined_not_covered": ["PSFE", "PAY"]}
    return comovement, coownership, coverage


def test_tiers_membership_and_stock_filter():
    cm, co, cv = _fixtures()
    s = ps.synthesize(cm, co, cv, ["RPAY", "PSFE", "PAY"])
    tiers = {t["key"]: t for t in s["tiers"]}
    assert "IWO" not in tiers["trading"]["members"] and "SPY" not in tiers["trading"]["members"]   # ETFs/indices out
    assert "UPST" in tiers["trading"]["members"] and "SOFI" in tiers["trading"]["members"]
    assert tiers["narrative"]["members"] == ["RPAY", "PRTH", "FPAY"]
    assert tiers["fundamental"]["members"] == ["RPAY", "PSFE", "PAY"]


def test_overlaps_and_insights():
    cm, co, cv = _fixtures()
    s = ps.synthesize(cm, co, cv, ["RPAY", "PSFE", "PAY"])
    assert s["overlaps"]["narrative_fundamental"] == ["RPAY"]      # RPAY shared by narrative + fundamental
    assert s["overlaps"]["all"] == []                             # no name is a peer by all three
    assert any("PRTH" in i for i in s["insights"])                # missing narrative peers surfaced
    assert "RPAY" in s["headline"]                                # headline names the one shared name


def test_handles_empty_caches():
    s = ps.synthesize(None, None, None, ["RPAY"])
    assert {t["key"] for t in s["tiers"]} == {"trading", "narrative", "fundamental"}
    assert s["tiers"][2]["members"] == ["RPAY"]                   # fundamental still from defined peers
