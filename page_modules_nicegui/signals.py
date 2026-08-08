"""page_modules_nicegui/signals.py — the "Intelligence Signal" component.

A consistent ⏳ "Waiting for X" card, used in place of a demo fallback or a silent blank. When a
section has no real data yet (no NOBO file uploaded, no analyst models logged, no PT history
accumulated), it tells the user EXACTLY what the engine is waiting to ingest — instead of either
fabricating a convincing demo (the bug class we spent a session removing) or showing an empty box
that reads as broken.

Doubles as a visible roadmap of what the platform consumes: every "Waiting for X" is a real,
nameable input the client can provide to light that section up.
"""
from nicegui import ui

from config.theme_tokens import ACTIVE as COLORS

_AMBER = "#B45309"
_AMBER_BG = "rgba(180,83,9,.07)"


def waiting_signal(what, detail=None, unlocks=None, compact=False):
    """Render a ⏳ "Waiting for {what}" card.

      what    — the missing input, phrased as a noun ("your Broadridge NOBO file").
      detail  — one line on how it arrives / what to do.
      unlocks — what the section will show once it's provided (the payoff).
      compact — tighter padding for inline use inside another card.
    """
    with ui.card().classes("w-full").style(
            f"background:{_AMBER_BG};border:1px solid rgba(180,83,9,.22);"
            f"border-left:4px solid {_AMBER};border-radius:8px;"
            f"padding:{'8px 12px' if compact else '12px 16px'};gap:2px;"):
        with ui.row().classes("items-center").style("gap:8px;"):
            ui.label("⏳").style("font-size:var(--fs-md);line-height:1;")
            ui.label(f"Waiting for {what}").style(
                f"color:{_AMBER};font-weight:700;font-size:{'12px' if compact else '13px'};")
        if detail:
            ui.label(detail).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        if unlocks:
            ui.label(f"Unlocks: {unlocks}").style(
                f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);font-style:italic;")


def fallback_banner():
    """A loud, page-top banner when the app is running on the local SQLite fallback
    because Neon (the authoritative store) is unreachable — so a degraded/stale state is
    never silent (it previously only printed one console line). Renders nothing when the
    database is healthy. Lives here (an import-safe UI module) so it's reusable across
    app pages and unit-testable without importing app_nicegui (which calls ui.run())."""
    try:
        from core import db
        if not db.is_degraded_fallback():
            return
    except Exception:
        return
    with ui.element("div").style(
            "width:100%;background:#B91C1C;color:#fff;padding:9px 18px;display:flex;align-items:center;"
            "gap:12px;box-shadow:0 1px 6px rgba(0,0,0,.28);z-index:6;"):
        ui.label("⚠").style("font-size:var(--fs-xl);line-height:1;")
        with ui.column().classes("gap-0"):
            ui.label("Database offline — running on a local fallback").style(
                "font-weight:700;font-size:var(--fs-base);")
            ui.label("Live tenants aren't loading and changes are NOT saved to your database. Check "
                     "DATABASE_URL / your Neon plan, then restart the app to reconnect.").style(
                "font-size:var(--fs-xs);opacity:.93;")


def waiting_chip(what):
    """A one-line inline chip version — for a table cell / metric row where a full card is too big."""
    ui.label(f"⏳ waiting for {what}").style(
        f"background:{_AMBER_BG};color:{_AMBER};font-size:var(--fs-2xs);font-weight:700;"
        "padding:2px 8px;border-radius:9px;white-space:nowrap;")
