"""
page_modules_nicegui/nav.py — shared navigation hook.

Ported pages (today_page.py, etc.) need to trigger a sidebar section change
(e.g. "Open Full Investor Pipeline" jumps to Investors) without importing
app_nicegui.py directly — that would be circular, since app_nicegui.py is
the one importing each page module in the first place.

app_nicegui.py calls register(go_to) once, at startup. Any page can then
call nav.go_to("Investors") and it'll behave exactly like clicking that
item in the sidebar. highlights is a small shared dict for the "jumped
here because of X" banners (e.g. Calendar showing why it was opened from
Today) — same idea as the old st.session_state["highlight_conference"]
pattern, just file-free since it only needs to live for one navigation.
"""

_go_to = None
highlights = {}


def register(go_to_fn):
    global _go_to
    _go_to = go_to_fn


def go_to(section, **highlight_kwargs):
    highlights.update(highlight_kwargs)
    if _go_to:
        _go_to(section)
