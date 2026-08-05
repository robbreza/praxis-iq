"""Pin the loud SQLite-fallback banner: db.is_degraded_fallback() flags exactly the
'Neon is the authoritative store but unreachable' state, and signals.fallback_banner
renders a visible warning then / nothing when the DB is healthy. The banner render uses
a synthetic NiceGUI Client (same technique as smoke_render); the component lives in the
import-safe signals module so no app_nicegui (ui.run()) import is needed."""
from nicegui import Client, ui
from nicegui.page import page

from core import db
from page_modules_nicegui import signals


def test_is_degraded_fallback_logic(monkeypatch):
    # configured (Neon authoritative) but unreachable -> degraded
    monkeypatch.setattr(db, "postgres_configured", lambda: True)
    monkeypatch.setattr(db, "_pg_reachable", lambda: False)
    assert db.is_degraded_fallback() is True
    # reachable -> healthy, not degraded
    monkeypatch.setattr(db, "_pg_reachable", lambda: True)
    assert db.is_degraded_fallback() is False
    # not configured (SQLite is the intended backend) -> not a "degraded fallback"
    monkeypatch.setattr(db, "postgres_configured", lambda: False)
    monkeypatch.setattr(db, "_pg_reachable", lambda: False)
    assert db.is_degraded_fallback() is False


def _render_text(fn):
    client = Client(page("/"), request=None)
    with client:
        fn()
    chunks = []
    for el in client.elements.values():
        t = getattr(el, "_text", None)
        if isinstance(t, str) and t:
            chunks.append(t)
        for k in ("label", "text"):
            v = getattr(el, "_props", {}).get(k)
            if isinstance(v, str) and v:
                chunks.append(v)
    return "\n".join(chunks)


def test_banner_renders_when_degraded(monkeypatch):
    monkeypatch.setattr(db, "is_degraded_fallback", lambda: True)
    text = _render_text(signals.fallback_banner)
    assert "Database offline" in text
    assert "DATABASE_URL" in text


def test_banner_silent_when_healthy(monkeypatch):
    monkeypatch.setattr(db, "is_degraded_fallback", lambda: False)
    text = _render_text(signals.fallback_banner)
    assert "Database offline" not in text


def test_banner_silent_on_error(monkeypatch):
    def _boom():
        raise RuntimeError("db check failed")
    monkeypatch.setattr(db, "is_degraded_fallback", _boom)
    text = _render_text(signals.fallback_banner)   # must swallow the error, render nothing
    assert "Database offline" not in text
