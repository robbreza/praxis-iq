"""Pin core.zoho_mail: config gating, that a send builds the right message and logs into the
configured Zoho SMTP host, and that failures return a helpful (ok=False, error) — all with
smtplib mocked, so no real network / credentials."""
import smtplib

from core import zoho_mail


def test_not_configured_is_a_clean_failure(monkeypatch):
    monkeypatch.delenv("ZOHO_SMTP_USER", raising=False)
    monkeypatch.delenv("ZOHO_SMTP_PASS", raising=False)
    assert not zoho_mail.is_configured()
    ok, err = zoho_mail.send_email("lead@example.com", "s", "b")
    assert not ok and "connect" in err.lower()


class _FakeSMTP:
    captured = {}

    def __init__(self, host, port, context=None, timeout=None):
        _FakeSMTP.captured.update(host=host, port=port)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def login(self, u, p):
        _FakeSMTP.captured["login"] = (u, p)

    def send_message(self, msg):
        _FakeSMTP.captured["msg"] = msg


def test_send_builds_message_and_authenticates(monkeypatch):
    monkeypatch.setenv("ZOHO_SMTP_USER", "me@praxispointir.com")
    monkeypatch.setenv("ZOHO_SMTP_PASS", "app-pass")
    monkeypatch.delenv("ZOHO_SMTP_PORT", raising=False)   # default 465 -> SSL path
    monkeypatch.delenv("ZOHO_FROM_NAME", raising=False)
    _FakeSMTP.captured = {}
    monkeypatch.setattr(zoho_mail.smtplib, "SMTP_SSL", _FakeSMTP)

    ok, err = zoho_mail.send_email("lead@example.com", "Hello", "Body text")
    c = _FakeSMTP.captured
    assert ok and err is None
    assert c["host"] == "smtp.zoho.com" and c["port"] == 465
    assert c["login"] == ("me@praxispointir.com", "app-pass")
    assert c["msg"]["To"] == "lead@example.com" and c["msg"]["Subject"] == "Hello"
    assert "me@praxispointir.com" in c["msg"]["From"]
    assert c["msg"].get_content().strip() == "Body text"


def test_auth_error_gives_helpful_message(monkeypatch):
    monkeypatch.setenv("ZOHO_SMTP_USER", "me@x.com")
    monkeypatch.setenv("ZOHO_SMTP_PASS", "wrong")

    def boom(*a, **k):
        raise smtplib.SMTPAuthenticationError(535, b"auth failed")

    monkeypatch.setattr(zoho_mail.smtplib, "SMTP_SSL", boom)
    ok, err = zoho_mail.send_email("lead@example.com", "s", "b")
    assert not ok and "app-specific" in err


def test_missing_recipient(monkeypatch):
    monkeypatch.setenv("ZOHO_SMTP_USER", "me@x.com")
    monkeypatch.setenv("ZOHO_SMTP_PASS", "p")
    ok, err = zoho_mail.send_email("", "s", "b")
    assert not ok and "recipient" in err.lower()


def test_verify_connection_logs_in_without_sending(monkeypatch):
    monkeypatch.setenv("ZOHO_SMTP_USER", "me@praxispointir.com")
    monkeypatch.setenv("ZOHO_SMTP_PASS", "app-pass")
    monkeypatch.delenv("ZOHO_SMTP_PORT", raising=False)
    _FakeSMTP.captured = {}
    monkeypatch.setattr(zoho_mail.smtplib, "SMTP_SSL", _FakeSMTP)
    ok, err = zoho_mail.verify_connection()
    assert ok and err is None
    assert _FakeSMTP.captured["login"] == ("me@praxispointir.com", "app-pass")
    assert "msg" not in _FakeSMTP.captured        # verify never sends a message
