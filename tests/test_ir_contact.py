"""Pin core.ir_contact: the IR decision-maker ladder (real IR officer -> CFO default -> CEO),
name/domain cleanup, and the personalized draft. Yahoo (yfinance) is mocked."""
from core import ir_contact


class _FT:
    def __init__(self, t):
        self.t = t

    @property
    def info(self):
        return _FT.data.get(self.t, {})

    data = {
        "IRCO": {"shortName": "IR Co", "website": "https://www.irco.com", "phone": "480-555-1000",
                 "numberOfAnalystOpinions": 8, "city": "Phoenix", "state": "AZ",
                 "companyOfficers": [
                     {"title": "President & CEO", "name": "Mr. Jane A. Chief"},
                     {"title": "Executive VP & CFO", "name": "Mr. Bob B. Money"},
                     {"title": "Vice President of Investor Relations", "name": "Ms. Ivy R. Voice"}]},
        "CFONLY": {"shortName": "CFO Only Inc", "website": "http://cfoonly.com",
                   "numberOfAnalystOpinions": 6,
                   "companyOfficers": [
                       {"title": "Chief Executive Officer", "name": "A CEO"},
                       {"title": "CFO & Treasurer", "name": "The CFO"}]},
        "CEOONLY": {"shortName": "Tiny Co", "companyOfficers": [{"title": "CEO & Director", "name": "Solo Boss"}]},
        "BARE": {"shortName": "Bare Co", "companyOfficers": []},
    }


def _patch(monkeypatch):
    monkeypatch.setattr(ir_contact.yf, "Ticker", _FT)


def test_prefers_real_ir_officer(monkeypatch):
    _patch(monkeypatch)
    e = ir_contact.enrich("IRCO")
    assert e["ir_kind"] == "ir"
    assert e["ir_name"] == "Ivy R. Voice"                 # title honorific stripped
    assert e["cfo_name"] == "Bob B. Money" and e["ceo_name"] == "Jane A. Chief"
    assert e["domain"] == "irco.com" and e["suggested_email"] == "ir@irco.com"


def test_falls_back_to_cfo(monkeypatch):
    _patch(monkeypatch)
    e = ir_contact.enrich("CFONLY")
    assert e["ir_kind"] == "cfo" and e["ir_name"] == "The CFO"
    assert "default IR contact" in ir_contact.contact_label(e)


def test_falls_back_to_ceo_then_none(monkeypatch):
    _patch(monkeypatch)
    assert ir_contact.enrich("CEOONLY")["ir_kind"] == "ceo"
    e = ir_contact.enrich("BARE")
    assert e["ir_kind"] == "none" and e["ir_name"] is None and e["suggested_email"] is None


def test_draft_personalizes(monkeypatch):
    _patch(monkeypatch)
    d = ir_contact.draft_email(ir_contact.enrich("IRCO"))
    assert "IR Co" in d["subject"]
    assert d["body"].startswith("Hi Ivy,")               # first name
    assert "8 sell-side analysts" in d["body"]
