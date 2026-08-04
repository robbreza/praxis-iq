"""page_modules_nicegui/responsive.py — one table, two layouts.

Wide tables (5+ columns) overflow a 375px phone and force a horizontal scroll that
hides the right-hand columns. `responsive_table()` renders the SAME data as an ordinary
`ui.table` on desktop and as one card per row on phones (heading + label:value lines),
toggled by the global `.resp-wide` / `.resp-stack` 640px breakpoint defined in
app_nicegui's head CSS.

Deliberately NOT `.mobile-only` / `.desktop-only`: those are RESERVED Quasar visibility
classes whose platform-based rules (a desktop browser emulating a small screen still
counts as a desktop *platform*) override a plain media query and force-hide the element.
Custom names are unaffected — see the CSS comment in app_nicegui.py.

Returns the `ui.table` so callers can still `.add_slot(...)` for desktop cell rendering;
the mobile cards show the plain row values (colour/badges degrade to text on phones).
"""
from nicegui import ui

from config.theme_tokens import ACTIVE as COLORS

# A value at least this long (or one whose column has no header) is stacked label-above-
# value on its own line rather than sitting on a cramped label:value row.
_LONG = 32


def responsive_table(columns, rows, *, row_key=None, pagination=None,
                     table_classes="w-full dense-table", table_props="flat dense",
                     primary=None):
    """columns/rows: exactly what you'd pass to ui.table. primary: the field whose value
    is the mobile card heading (defaults to the first column's field)."""
    kwargs = {}
    if row_key is not None:
        kwargs["row_key"] = row_key
    if pagination is not None:
        kwargs["pagination"] = pagination

    # Desktop: the real table, unchanged.
    with ui.element("div").classes("resp-wide w-full"):
        table = ui.table(columns=columns, rows=rows, **kwargs)
        table.classes(table_classes)
        if table_props:
            table.props(table_props)

    fields = [(c["field"], (c.get("label") or "").replace("\\n", " ").replace("\n", " ").strip())
              for c in columns]
    if primary is None:
        primary = fields[0][0] if fields else None

    # Mobile: one card per row.
    with ui.element("div").classes("resp-stack w-full"):
        for r in rows:
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                    "padding:8px 10px;margin:4px 0;"):
                head = r.get(primary)
                ui.label(str(head) if head not in (None, "") else "—").style(
                    f"color:{COLORS['text_heading']};font-size:13px;font-weight:600;")
                for f, lbl in fields:
                    if f == primary:
                        continue
                    v = r.get(f)
                    if v in (None, ""):
                        continue
                    v = str(v)
                    if not lbl or len(v) > _LONG:
                        # Long text / unlabeled: label above (if any), value beneath, full width.
                        with ui.column().classes("w-full").style("gap:0;margin-top:2px;"):
                            if lbl:
                                ui.label(lbl).style(f"color:{COLORS['text_muted']};font-size:11px;")
                            ui.label(v).style(f"color:{COLORS['text_body']};font-size:12px;line-height:1.4;")
                    else:
                        with ui.row().classes("w-full justify-between items-baseline").style("gap:10px;"):
                            ui.label(lbl).style(
                                f"color:{COLORS['text_muted']};font-size:11px;white-space:nowrap;")
                            ui.label(v).style(
                                f"color:{COLORS['text_body']};font-size:12px;text-align:right;")
    return table
