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

PER-CLIENT, NOT PROCESS-GLOBAL. This used to be a single module-level dict, and
that silently swallowed writes. set_page_context() runs during a render, but the
button callbacks that later read it fire long afterwards — so with two browser
tabs open, tab B's render overwrote the context, and a click in tab A then
evaluated can_edit() against tab B's page. Where that came back False, every
_save_state()-style RBAC choke point discarded the write and the control simply
appeared dead (this is what killed Today's "Show automation stats" toggle, and
could equally have dropped a resolve/mute/mark-noted action).

State is therefore keyed by nicegui's client id and cleaned up on disconnect —
the same fix, for the same reason, as page_modules_nicegui/nav.py. Outside a
NiceGUI client (tests, scripts, the smoke renderer) it falls back to one shared
slot, which is correct there because those are single-threaded and sequential.
"""

from config.client_config import role_can_edit, DEFAULT_ROLE_KEY

_slots = {}          # client_id -> {"role", "page"}


def _slot():
    """This client's context, created (and scheduled for cleanup) on first use."""
    cid = "_global"
    try:                                   # lazy: core/ must import cleanly without nicegui
        from nicegui import context
        cid = context.client.id
    except Exception:
        pass
    s = _slots.get(cid)
    if s is None:
        s = _slots[cid] = {"role": DEFAULT_ROLE_KEY, "page": None}
        if cid != "_global":
            try:
                from nicegui import context
                context.client.on_disconnect(lambda cid=cid: _slots.pop(cid, None))
            except Exception:
                pass
    return s


def set_page_context(role, page):
    """Called by app_nicegui.render_page() right before it renders `page`,
    recording which role is viewing which page for the render that follows."""
    s = _slot()
    s["role"] = role or DEFAULT_ROLE_KEY
    s["page"] = page


def current_role():
    return _slot()["role"]


def current_page():
    return _slot()["page"]


def can_edit():
    """True if the active role has full (read/write) access to the page
    currently being rendered. Gate any control that writes or persists data
    behind this.

    A client_user session is read-only at the TENANT level regardless of role —
    core.db marks the session read-only and refuses writes at the data layer, so
    the UI must never offer a mutating control it can't honor. That check wins
    over the per-role RBAC below."""
    from core import db
    if db.session_is_readonly():
        return False
    s = _slot()
    return role_can_edit(s["role"], s["page"])


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
    from core import db
    if db.session_is_readonly():
        msg = "🔒 View-only — client access is read-only."
    else:
        # Name the page only when we actually have one — this read "can't edit
        # None" whenever the context wasn't set for this client.
        _s = _slot()
        _pg = f" {_s['page']}" if _s.get("page") else " this page"
        msg = f"🔒 View-only — the {_s['role']} role can't edit{_pg}."
    ui.label(msg) \
        .style("color:#B45309;background:#FEF3C7;border:1px solid #FCD34D;"
               "border-radius:6px;padding:6px 12px;font-size:13px;font-weight:600;"
               "display:inline-block;margin-bottom:8px;")
