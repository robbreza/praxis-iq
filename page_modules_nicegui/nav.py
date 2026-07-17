"""
page_modules_nicegui/nav.py — shared navigation hook.

Ported pages (today_page.py, etc.) need to trigger a sidebar section change
(e.g. "Open Full Investor Pipeline" jumps to Investors) without importing
app_nicegui.py directly — that would be circular, since app_nicegui.py is
the one importing each page module in the first place.

app_nicegui.py calls register(go_to, on_tab_change) once, at startup. Any page
can then call nav.go_to("Investors") — or nav.go_to("Reports", tab="90-Day IR
Plan") to deep-link straight to a specific tab — and it behaves exactly like
clicking that item (or sub-item) in the sidebar. highlights is a small shared
dict for the "jumped here because of X" banners (e.g. Calendar showing why it
was opened from Today).

Two-way sync for the nested sidebar:
  • Sidebar → page: go_to() stashes the requested tab via set_target_tab(); the
    target page reads it once with consume_target_tab() when it builds its tab
    strip, so the page opens on the requested tab instead of its first one.
  • Page → sidebar: when the user clicks a tab *inside* a page, the page calls
    tab_changed(tab_name) so the sidebar can move its highlight to the matching
    sub-item. Only a page's primary (top-level) tab strip should call this.
"""

_go_to = None
_on_tab_change = None
_target_tab = None
highlights = {}


def register(go_to_fn, on_tab_change_fn=None):
    global _go_to, _on_tab_change
    _go_to = go_to_fn
    _on_tab_change = on_tab_change_fn


def go_to(section, tab=None, **highlight_kwargs):
    highlights.update(highlight_kwargs)
    if _go_to:
        _go_to(section, tab)


def set_target_tab(name):
    """Stash the tab a pending navigation wants the target page to open on."""
    global _target_tab
    _target_tab = name


def consume_target_tab():
    """Read-and-clear the requested tab. A page calls this once, while building
    its primary tab strip, to decide which tab to open on (None → its default)."""
    global _target_tab
    v = _target_tab
    _target_tab = None
    return v


def tab_changed(tab_name):
    """A page calls this when the user switches its primary tab, so the sidebar
    can re-highlight the matching sub-item."""
    if _on_tab_change:
        _on_tab_change(tab_name)
