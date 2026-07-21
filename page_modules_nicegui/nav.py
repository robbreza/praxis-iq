"""
page_modules_nicegui/nav.py — shared navigation hook (PER-CLIENT).

Ported pages (today_page.py, etc.) need to trigger a sidebar section change
(e.g. "Open Full Investor Pipeline" jumps to Investors) without importing
app_nicegui.py directly — that would be circular, since app_nicegui.py is
the one importing each page module in the first place.

CRITICAL — this state is PER CLIENT (per browser tab), not module-global.
app_nicegui.py's main_page() is an @ui.page("/") handler, so it runs — and calls
register() — once PER connection. If the go_to closure (which renders into THAT
connection's content area) were stored in a module global, the last tab to load
would overwrite it, and clicking a nav button in an OLDER tab would render into
the NEWEST tab — the tab you clicked would appear to do nothing. With several
IRconnect tabs open that is exactly what happened. So every callback and every
bit of nav state is keyed by the current client id and cleaned up on disconnect.

Any page can call nav.go_to("Investors") — or nav.go_to("Reports", tab="90-Day
IR Plan") to deep-link straight to a specific tab — and it behaves exactly like
clicking that item (or sub-item) in the sidebar of the SAME tab.

Two-way sync for the nested sidebar:
  • Sidebar → page: go_to() stashes the requested tab via set_target_tab(); the
    target page reads it once with consume_target_tab() when it builds its tab
    strip, so the page opens on the requested tab instead of its first one.
  • Page → sidebar: when the user clicks a tab *inside* a page, the page calls
    tab_changed(tab_name) so the sidebar can move its highlight to the matching
    sub-item. Only a page's primary (top-level) tab strip should call this.

Highlights ("jumped here because of X" banners) are per-client too — set them
via go_to(..., key=value) and read them with pop_highlight(key).
"""
from nicegui import context

_slots = {}   # client_id -> {"go_to", "on_tab_change", "target_tab", "highlights"}


def _slot():
    """The current client's nav state, created (and scheduled for cleanup) on first use.
    Falls back to a shared '_global' slot outside a client context (e.g. background tasks)."""
    try:
        cid = context.client.id
    except Exception:
        cid = "_global"
    s = _slots.get(cid)
    if s is None:
        s = {"go_to": None, "on_tab_change": None, "target_tab": None, "highlights": {}}
        _slots[cid] = s
        if cid != "_global":
            try:
                context.client.on_disconnect(lambda cid=cid: _slots.pop(cid, None))
            except Exception:
                pass
    return s


def register(go_to_fn, on_tab_change_fn=None):
    s = _slot()
    s["go_to"] = go_to_fn
    s["on_tab_change"] = on_tab_change_fn


def go_to(section, tab=None, **highlight_kwargs):
    s = _slot()
    s["highlights"].update(highlight_kwargs)
    if s["go_to"]:
        s["go_to"](section, tab)


def set_target_tab(name):
    """Stash the tab a pending navigation wants the target page to open on."""
    _slot()["target_tab"] = name


def consume_target_tab():
    """Read-and-clear the requested tab. A page calls this once, while building
    its primary tab strip, to decide which tab to open on (None → its default)."""
    s = _slot()
    v = s["target_tab"]
    s["target_tab"] = None
    return v


def tab_changed(tab_name):
    """A page calls this when the user switches its primary tab, so the sidebar
    can re-highlight the matching sub-item."""
    s = _slot()
    if s["on_tab_change"]:
        s["on_tab_change"](tab_name)


def pop_highlight(key, default=None):
    """Read-and-clear a per-client highlight flag (set via go_to(key=value))."""
    return _slot()["highlights"].pop(key, default)


def set_highlight(**kwargs):
    _slot()["highlights"].update(kwargs)
