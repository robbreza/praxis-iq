"""core/lazy_tab_probe.py — a test hook to make LAZY tab-panel content visible to smoke_render.

Some pages defer a tab's content: the tab panel shows a spinner, and its real render function only
runs when the tab is clicked (see the `lazy_panels` dicts in investors_page / earnings_page). That
content is invisible to tests/smoke_render.py, which only builds the top-level page — a blind spot
that let a crashing tab (the NDR Planner: 'int' object is not iterable) ship undetected.

Pages call register() with their `{tab_name: (panel, build_fn)}` dict. It's a no-op in normal
runtime (capture off); only smoke_render turns capture on, so it can enumerate every lazy build_fn
and invoke it to catch render exceptions and demo-token leaks. Zero overhead in production.
"""
_capturing = False
_captured = []          # list of (page, tab_name, build_fn)


def set_capturing(on):
    global _capturing
    _capturing = bool(on)


def reset():
    _captured.clear()


def register(page, lazy_panels):
    """Record a page's lazy tab build functions — only while capturing (tests). `lazy_panels` maps
    tab name -> (panel, build_fn) (or a bare build_fn)."""
    if not _capturing:
        return
    for name, val in (lazy_panels or {}).items():
        build_fn = val[1] if isinstance(val, (tuple, list)) and len(val) > 1 else val
        if callable(build_fn):
            _captured.append((page, name, build_fn))


def captured():
    return list(_captured)
