"""Pin core.prospect_screener: the analyst-coverage thesis bands (early / prime / tooled),
the metro screen split + counts, the industry keyword filter, and universe add/dedup — all
against the in-memory store with Yahoo (yfinance) mocked."""
import pytest

from core import prospect_screener as ps


class _FakeTicker:
    data = {
        "AAA": {"numberOfAnalystOpinions": 8, "sector": "Technology", "industry": "Semiconductors",
                "shortName": "Alpha Corp", "marketCap": 1_000_000_000, "city": "Phoenix", "state": "AZ"},
        "BBB": {"numberOfAnalystOpinions": 20, "sector": "Technology", "industry": "Software",
                "shortName": "Beta Inc", "marketCap": 5_000_000_000},
        "CCC": {"numberOfAnalystOpinions": 3, "sector": "Industrials", "industry": "Trucking",
                "shortName": "Gamma LLC"},
    }

    def __init__(self, t):
        self.t = t

    @property
    def info(self):
        if self.t == "BOOM":
            raise RuntimeError("yahoo unavailable")
        return _FakeTicker.data.get(self.t, {})


@pytest.fixture
def screener(mem_db, monkeypatch):
    monkeypatch.setattr(ps.yf, "Ticker", _FakeTicker)
    ps.add_tickers("TestMetro", ["AAA", "BBB", "CCC", "BOOM"])
    return mem_db


def test_classify_bands():
    assert ps.classify(3) == "early"
    assert ps.classify(6) == "prime" and ps.classify(15) == "prime"   # inclusive band
    assert ps.classify(16) == "tooled" and ps.classify(20) == "tooled"
    assert ps.classify(None) == "unknown"


def test_screen_splits_and_counts(screener):
    res = ps.screen("TestMetro")
    assert res["counts"] == {"total": 4, "prime": 1, "tooled": 1, "early": 1}
    assert [r["ticker"] for r in res["prime"]] == ["AAA"]
    assert [r["ticker"] for r in res["tooled"]] == ["BBB"]
    boom = next(r for r in res["rows"] if r["ticker"] == "BOOM")
    assert boom["analysts"] is None and boom["band"] == "unknown"      # failure never counts as a prospect


def test_industry_filter(screener):
    res = ps.screen("TestMetro", industry="semiconductor")
    assert {r["ticker"] for r in res["rows"]} == {"AAA"}               # matches on sector/industry
    assert [r["ticker"] for r in res["prime"]] == ["AAA"]


def test_min_max_thresholds_shift_bands(screener):
    res = ps.screen("TestMetro", min_analysts=10, max_analysts=25)
    # with a higher floor, the 8-analyst AAA drops to 'early'; BBB(20) becomes 'prime'
    assert [r["ticker"] for r in res["prime"]] == ["BBB"]
    assert "AAA" in [r["ticker"] for r in res["early"]]


def test_add_tickers_dedups(screener):
    before = len(ps.tickers_for("TestMetro"))
    added = ps.add_tickers("TestMetro", ["AAA", "ddd", "DDD"])         # AAA dup, ddd/DDD same
    assert added == 1 and len(ps.tickers_for("TestMetro")) == before + 1
