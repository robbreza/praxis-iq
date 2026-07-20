"""tests/smoke_render.py — render every page, for every tenant, and fail on any exception.

WHY THIS EXISTS
Booting the server and curling `/` proves almost nothing. NiceGUI builds a page module's UI on a
websocket NAVIGATION event, not on the initial HTTP GET, so `/` can return 200 while Investor
Targeting raises on render. That is exactly what happened: one record with Metro=None made
`sorted({i["Metro"] ...})` raise TypeError and the page died with "server did not load", while
every route still answered 200.

The same class of bug bit three times in a row — a ticker used as an issuer-name token, 13F
amendments read as full snapshots, Metro=None — each failing late and quietly rather than at the
boundary. This closes the gap between "the server starts" and "the pages actually work".

HOW
NiceGUI 3.x exposes Client(page, request=None) as a context manager, so each render function can be
driven headlessly into a synthetic client with no browser and no websocket. Every page is rendered
once per tenant, because the bugs above were all TENANT-SPECIFIC: USIO rendered fine while SARO
crashed, and vice versa.

RUN
    python tests/smoke_render.py            # every tenant, every page
    python tests/smoke_render.py --client saro
Exit code is non-zero if any page fails, so it can gate a commit or a deploy.
"""
import argparse
import importlib
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nicegui import Client, ui                                    # noqa: E402
from nicegui.page import page                                     # noqa: E402


def render_one(module_path, render_fn_name, client_id, role="IR"):
    """Render a single page for a single tenant. Returns (ok, detail)."""
    from config.client_config import set_active_client_id
    from core import ui_context

    set_active_client_id(client_id)
    # Pages read the active role/page to decide whether to draw mutating controls.
    ui_context.set_page_context(role, render_fn_name.replace("render_", "").replace("_page", "").title())

    module = importlib.import_module(module_path)
    fn = getattr(module, render_fn_name, None)
    if fn is None:
        return False, f"missing {render_fn_name}()"

    try:
        with Client(page("/"), request=None):
            fn()
        return True, ""
    except Exception:
        return False, traceback.format_exc()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", help="only this client_id (default: all registered tenants)")
    ap.add_argument("--page", help="only this page name, e.g. Investors")
    ap.add_argument("-q", "--quiet", action="store_true", help="suppress tracebacks; summary only")
    args = ap.parse_args()

    from config.client_config import CLIENT_REGISTRY, reload_registry
    reload_registry()                       # pick up DB-defined tenants, same as app startup

    # app_nicegui calls ui.run() at import time, which would try to bind port 8502 (and fail if the
    # dev server is already up). Neutralise it: we want the module's PORTED map, not its server.
    ui.run = lambda *a, **k: None
    import app_nicegui                      # noqa: F401  — PORTED is the app's own page map,
    ported = app_nicegui.PORTED             #   imported so this test can never drift from it

    clients = [args.client] if args.client else list(CLIENT_REGISTRY)
    pages = {args.page: ported[args.page]} if args.page else ported

    failures, checked = [], 0
    for cid in clients:
        print(f"\n=== {cid} ===")
        for name, module_path in pages.items():
            fn_name = f"render_{name.lower()}_page"
            ok, detail = render_one(module_path, fn_name, cid)
            checked += 1
            print(f"  {'PASS' if ok else 'FAIL'}  {name}")
            if not ok:
                failures.append((cid, name, detail))

    print(f"\n{'-' * 62}")
    print(f"rendered {checked} page/tenant combinations · {len(failures)} failed")
    for cid, name, detail in failures:
        print(f"\nFAIL {cid} / {name}")
        if not args.quiet:
            print(detail.rstrip())
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
