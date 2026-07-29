"""Pin the coverage-overlap core (Spec 14c): specialist-vs-generalist split, payments-first ranking,
and the diff against our defined peer set. Pure logic, no DB."""
from lighthouse import coverage as cov


def _coverage():
    return {
        "spec": {"analyst": "Jon", "firm": "Ladenburg", "coverage": [
            {"ticker": "RPAY", "name": "Repay", "sector": "ACH / Vertical Payments", "relevance": 95},
            {"ticker": "PRTH", "name": "Priority", "sector": "PayFac / SMB", "relevance": 90}]},
        "gen": {"analyst": "Scott", "firm": "HCW", "coverage": [
            {"ticker": "FPAY", "name": "FlexShopper", "sector": "Fintech / LTO", "relevance": 95},
            {"ticker": "KSCP", "name": "Knightscope", "sector": "Security Robotics", "relevance": 35},
            {"ticker": "GCTS", "name": "GCT", "sector": "Semiconductor", "relevance": 20}]},
    }


def test_is_payments_classifier():
    assert cov._is_payments("ACH / Vertical Payments") and cov._is_payments("Fintech / LTO")
    assert cov._is_payments("PayFac / SMB") and not cov._is_payments("Security Robotics")


def test_specialist_vs_generalist():
    out = cov.aggregate(_coverage(), defined_peers=["RPAY", "PSFE"], issuer="USIO")
    assert out["n_analysts"] == 2 and out["n_specialists"] == 1     # Jon 2/2 payments; Scott 1/3


def test_payments_first_and_defined_diff():
    out = cov.aggregate(_coverage(), defined_peers=["RPAY", "PSFE"], issuer="USIO")
    top3 = {p["ticker"] for p in out["coverage_peers"][:3]}
    assert top3 == {"RPAY", "PRTH", "FPAY"}                          # payments peers rank ahead of the tech names
    assert set(out["new_payments_peers"]) == {"PRTH", "FPAY"}        # payments peers we didn't define
    assert "RPAY" in out["defined_covered"] and out["defined_not_covered"] == ["PSFE"]
