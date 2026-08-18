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
# Accent (indigo) wash for the signature-capability banner — a distinct register from amber/status.
_ACCENT_WASH = "rgba(30,64,175,.05)"
_ACCENT_BORDER = "rgba(30,64,175,.20)"


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


def empty_state(message, hint=None):
    """Neutral "nothing here yet" placeholder — the calm counterpart to the amber waiting_signal.
    Use for a genuinely empty list ("no items match", "none logged yet"), NOT for a data source that
    isn't wired (that's waiting_signal). One shared shape so empty states read the same across pages."""
    with ui.card().classes("w-full").style(
            f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "border-radius:8px;padding:12px 16px;gap:2px;"):
        ui.label(message).style(f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);")
        if hint:
            ui.label(hint).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")


def capability_banner(title, why, *, tag="IRconnect capability", icon="◆", compact=False):
    """Elevate a SIGNATURE, LIVE capability in a page's hierarchy so it reads as a platform
    strength at a glance — not commodity data sitting flat among equal-weight cards. The accent
    left-rail + subtle indigo wash is a distinct register from the amber `waiting_signal` and the
    green/red status colours, reserved for the real differentiators (proprietary consensus, "why
    is the stock moving" attribution, analyst tone-shift, 13F holder-flow targeting, the risk
    dashboard). ONLY use for capabilities that actually run live — never for wired-not-live features.

      title  — the capability, in plain buyer vocabulary ("Consensus you build, not license").
      why    — one line on WHAT makes it differentiated / how it's produced.
      tag    — the small eyebrow marker (kept consistent app-wide).
    """
    with ui.element("div").classes("w-full").style(
            f"background:{_ACCENT_WASH};border:1px solid {_ACCENT_BORDER};"
            f"border-left:4px solid {COLORS['accent']};border-radius:8px;"
            f"padding:{'8px 12px' if compact else '11px 15px'};"):
        with ui.row().classes("items-center").style("gap:6px;margin-bottom:2px;"):
            ui.label(icon).style(f"color:{COLORS['accent']};font-size:var(--fs-xs);line-height:1;")
            ui.label(tag.upper()).style(
                f"color:{COLORS['accent']};font-size:var(--fs-2xs);font-weight:700;"
                "text-transform:uppercase;letter-spacing:.08em;")
        ui.label(title).style(
            f"color:{COLORS['text_heading']};font-size:var(--fs-lg);font-weight:700;"
            "letter-spacing:-.01em;line-height:1.2;")
        if why:
            ui.label(why).style(f"color:{COLORS['text_secondary']};font-size:var(--fs-sm);"
                                "line-height:1.45;margin-top:1px;")


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
