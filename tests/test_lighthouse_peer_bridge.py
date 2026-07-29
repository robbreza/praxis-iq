"""Pin the onboarding bridge (Spec 14): the co-movement candidate universe is TRIANGULATED per client
(SIC screen + defined + valuation + coverage + anchors), falls back when thin, and discover() honors a
passed universe. Sources are monkeypatched so no EDGAR/DB is hit."""
import numpy as np
import pandas as pd
from lighthouse import comovement as cm


def test_discover_honors_passed_universe():
    np.random.seed(0)
    n = 200
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    d = {"AAA": np.random.normal(0, 0.01, n), "BBB": np.random.normal(0, 0.01, n),
         "CCC": np.random.normal(0, 0.01, n)}
    d["USIO"] = 0.7 * d["AAA"] + np.random.normal(0, 0.008, n)          # USIO tracks AAA
    rets = pd.DataFrame(d, index=idx)
    out = cm.discover("USIO", rets, ["BBB"],
                      universe={"AAA": "custom-cat", "BBB": "defined peer", "CCC": "other"},
                      top_corr=5, max_select=3)
    assert out["top_correlates"][0]["ticker"] == "AAA"
    assert out["top_correlates"][0]["category"] == "custom-cat"          # category from the passed universe


def test_candidate_universe_triangulates(monkeypatch):
    monkeypatch.setattr("core.peer_discovery.discover",
                        lambda t: {"sic_desc": "Test SIC", "sic_tickers": ["AAA", "BBB", "USIO"]}, raising=False)
    monkeypatch.setattr("core.db.load_json", lambda *a, **k: [{"ticker": "VVV"}], raising=False)
    monkeypatch.setattr("core.db.save_json", lambda *a, **k: None, raising=False)
    monkeypatch.setattr("lighthouse.coverage.load_cache", lambda *a, **k: {"coverage_peers": [{"ticker": "COV1"}]}, raising=False)
    uni = cm.candidate_universe("USIO", client_id="x", defined_peers=["DEF1"])
    assert uni.get("AAA") == "Test SIC" and "USIO" not in uni            # SIC names in; issuer excluded
    assert uni.get("DEF1") == "defined peer" and uni.get("VVV") == "valuation comp"
    assert uni.get("COV1") == "coverage peer"
    assert "SPY" in uni and "IWM" in uni                                 # market anchors always present


def test_candidate_universe_falls_back_when_thin(monkeypatch):
    monkeypatch.setattr("core.peer_discovery.discover", lambda t: {}, raising=False)   # SIC screen empty
    monkeypatch.setattr("core.db.load_json", lambda *a, **k: None, raising=False)
    monkeypatch.setattr("lighthouse.coverage.load_cache", lambda *a, **k: None, raising=False)
    uni = cm.candidate_universe("XYZ", client_id="x", defined_peers=[])
    assert uni == cm.CANDIDATE_UNIVERSE                                  # too few companies -> built-in set
