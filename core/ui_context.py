"""core/ui_context.py — per-render UI context for the NiceGUI app.

The NiceGUI page render functions (page_modules_nicegui/*.render_*_page())
take no arguments — app_nicegui.render_page() dispatches them by name. This
module is how the active RBAC role reaches them: app_nicegui sets the context
immediately before dispatching each page, and pages read it to decide whether
to render mutating controls (edit/save/delete) or lock the page to view-only.

Typical page use:

    from core import ui_context
    ...
    if ui_context.is_read_only():
        ui_context.read_only_banner()   # "🔒 View-only for your role"
    ...
    # gate any control that writes/persists:
    if ui_context.can_edit():
        ui.button("Save", on_click=save)

Caveat: this context is process-global, not per-browser-tab. The platform is
an internal, effectively single-operator tool today — the same simplification
config.client_config.get_active_client_id() already makes (it falls back to a
single default client outside a Streamlit session). If the app ever needs true
multi-user / multi-tab isolation, move this state into nicegui app.storage.tab
and have set_page_context write there instead of a module global.
"""

from config.client_config import role_can_edit, DEFAULT_ROLE_KEY

_ctx = {"role": DEFAULT_ROLE_KEY, "page": None}


def set_page_context(role, page):
    """Called by app_nicegui.render_page() right before it renders `page`,
    recording which role is viewing which page for the render that follows."""
    _ctx["role"] = role or DEFAULT_ROLE_KEY
    _ctx["page"] = page


def current_role():
    return _ctx["role"]


def current_page():
    return _ctx["page"]


def can_edit():
    """True if the active role has full (read/write) access to the page
    currently being rendered. Gate any control that writes or persists data
    behind this."""
    return role_can_edit(_ctx["role"], _ctx["page"])


def is_read_only():
    """Inverse of can_edit() — the active role may view this page but not
    change anything on it."""
    return not can_edit()


def read_only_banner(ui=None):
    """Render a small 'view-only for your role' notice. Pass the page's `ui`
    handle (from `from nicegui import ui`); imported lazily here so this
    module stays importable outside a NiceGUI context (e.g. under Streamlit
    or in tests)."""
    if ui is None:
        from nicegui import ui as _ui
        ui = _ui
    ui.label(f"🔒 View-only — the {_ctx['role']} role can't edit {_ctx['page']}.") \
        .style("color:#B45309;background:#FEF3C7;border:1px solid #FCD34D;"
               "border-radius:6px;padding:6px 12px;font-size:13px;font-weight:600;"
               "display:inline-block;margin-bottom:8px;")
