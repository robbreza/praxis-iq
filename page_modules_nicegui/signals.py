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
            ui.label("⏳").style("font-size:15px;line-height:1;")
            ui.label(f"Waiting for {what}").style(
                f"color:{_AMBER};font-weight:700;font-size:{'12px' if compact else '13px'};")
        if detail:
            ui.label(detail).style(f"color:{COLORS['text_muted']};font-size:11.5px;")
        if unlocks:
            ui.label(f"Unlocks: {unlocks}").style(
                f"color:{COLORS['text_muted']};font-size:10.5px;font-style:italic;")


def waiting_chip(what):
    """A one-line inline chip version — for a table cell / metric row where a full card is too big."""
    ui.label(f"⏳ waiting for {what}").style(
        f"background:{_AMBER_BG};color:{_AMBER};font-size:10px;font-weight:700;"
        "padding:2px 8px;border-radius:9px;white-space:nowrap;")
