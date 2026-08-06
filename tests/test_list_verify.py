"""Pin core.list_verify: SEC-backed firm verification (real vs unconfirmable, with the
distinctive-token guard against false positives), local reconciliation vs the client universe,
and promote-only-verified. SEC EDGAR and the data sources are mocked — no network."""
import pytest

from core import list_verify


class _Resp:
    def __init__(self, text):
        self.text = text


def _atom(*pairs):
    body = "".join(f"<company-info><cik>{c}</cik><conformed-name>{n}</conformed-name></company-info>"
                   for n, c in pairs)
    return _Resp(f"<feed>{body}</feed>")


@pytest.fixture(autouse=True)
def _clear_cache():
    list_verify._verify_cache.clear()
    yield


def test_verify_real_firm_returns_cik(monkeypatch):
    monkeypatch.setattr(list_verify.sec_filings, "_get",
                        lambda url, params=None: _atom(("WHITEBOX ADVISORS LLC", "1049502")))
    r = list_verify.verify_firm("Whitebox Advisors, LLC")
    assert r["is_real"] and r["cik"] == "1049502" and "WHITEBOX" in r["edgar_name"].upper()


def test_unconfirmed_when_edgar_empty(monkeypatch):
    monkeypatch.setattr(list_verify.sec_filings, "_get", lambda url, params=None: _atom())
    r = list_verify.verify_firm("Totally Fake Nonexistent Fund XYZ")
    assert r["is_real"] is False and r["cik"] is None


def test_token_guard_rejects_unrelated_match(monkeypatch):
    # EDGAR returns a real but UNRELATED filer; no shared distinctive token -> not confirmed.
    monkeypatch.setattr(list_verify.sec_filings, "_get",
                        lambda url, params=None: _atom(("VANGUARD GROUP INC", "102909")))
    assert list_verify.verify_firm("Zephyr Quant Partners")["is_real"] is False


def test_verify_is_cached(monkeypatch):
    calls = {"n": 0}

    def _get(url, params=None):
        calls["n"] += 1
        return _atom(("ACME CAPITAL LLC", "111"))
    monkeypatch.setattr(list_verify.sec_filings, "_get", _get)
    list_verify.verify_firm("Acme Capital LLC")
    list_verify.verify_firm("Acme Capital LLC")
    assert calls["n"] == 1


def test_reconcile_priority():
    uni = {"WHITEBOX": {"contacts"}, "ACME": {"holder", "prospect"}, "CORSAIR": {"prospect"}}
    assert list_verify.reconcile("Whitebox Advisors, LLC", uni) == "contacts"
    assert list_verify.reconcile("Acme Capital", uni) == "holder"       # holder wins
    assert list_verify.reconcile("Corsair Capital Management", uni) == "prospect"
    assert list_verify.reconcile("Brand New Fund", uni) == "new"


def test_verify_and_reconcile_dedups_and_labels(monkeypatch):
    monkeypatch.setattr(list_verify.sec_filings, "_get",
                        lambda url, params=None: _atom(("CORSAIR CAPITAL MANAGEMENT LP", "902")))
    monkeypatch.setattr(list_verify, "client_universe",
                        lambda cid=None: {"CORSAIR": {"prospect"}})
    rows = list_verify.verify_and_reconcile(
        ["Corsair Capital Management, L.P.", "corsair capital management, l.p.", ""], client_id="usio")
    assert len(rows) == 1                                   # deduped, blank dropped
    assert rows[0]["is_real"] and rows[0]["status"] == "prospect"
    assert rows[0]["status_label"] == "Already a prospect"


def test_promote_only_verified(monkeypatch):
    added = []
    monkeypatch.setattr("core.curated_targets.add",
                        lambda name, **kw: added.append(name) or True, raising=False)
    rows = [
        {"name": "Real Fund LLC", "is_real": True, "cik": "123"},
        {"name": "Unconfirmed Fund", "is_real": False, "cik": None},
    ]
    n = list_verify.promote(rows, client_id="usio")
    assert n == 1 and added == ["Real Fund LLC"]           # the unverified one is never promoted
