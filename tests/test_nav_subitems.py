"""Guard: the sidebar sub-items for the heavy pages MUST match those pages' actual top-level tabs,
in order — so a newly-added tab can't silently become unreachable from the nav (the drift that
hid Website / Import list / Prep Brief). Uses core.lazy_tab_probe to read each page's real tab set.
"""
import importlib
import os

os.environ.setdefault("LIGHTHOUSE_TELEMETRY_OFF", "1")

import pytest
from nicegui import Client, ui
from nicegui.page import page

ui.run = lambda *a, **k: None                 # app_nicegui calls ui.run() at import — neutralize it
import app_nicegui                            # noqa: E402


def _page_tabs(page_name, module_path, render_fn, cid="usio"):
    from config.client_config import reload_registry, set_active_client_id
    from core import lazy_tab_probe, ui_context
    reload_registry()
    set_active_client_id(cid)
    ui_context.set_page_context("IR", page_name)
    lazy_tab_probe.set_capturing(True)
    lazy_tab_probe.reset()
    mod = importlib.import_module(module_path)
    client = Client(page("/"), request=None)
    with client:
        getattr(mod, f"render_{render_fn}_page")()
    tabs = [tab for _pg, tab, _fn in lazy_tab_probe.captured()]
    lazy_tab_probe.reset()
    return tabs


@pytest.mark.parametrize("page_name,module,fn", [
    # Investor Targeting was split into three rail SECTIONS (Ownership / Targeting / Roadshow) whose
    # tabs live only on the page — they deliberately have no NAV_SUBITEMS, so this drift check no
    # longer applies to them. Earnings still surfaces its tabs as sidebar sub-items.
    ("Earnings", "page_modules_nicegui.earnings_page", "earnings"),
])
def test_sidebar_subitems_match_page_tabs(page_name, module, fn):
    tabs = _page_tabs(page_name, module, fn)
    assert tabs, f"{page_name} registered no lazy tabs — probe hook missing?"
    assert tabs == app_nicegui.NAV_SUBITEMS[page_name], (
        f"{page_name} sidebar sub-items have drifted from its tabs.\n"
        f"  page tabs : {tabs}\n"
        f"  NAV_SUBITEMS: {app_nicegui.NAV_SUBITEMS[page_name]}\n"
        f"Update NAV_SUBITEMS['{page_name}'] in app_nicegui.py to match (order included).")
