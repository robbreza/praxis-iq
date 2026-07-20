"""tests/smoke_render.py — render every page, for every tenant, and fail on any exception
OR on any known demo/fabricated token appearing in a client-facing surface.

WHY THIS EXISTS
Booting the server and curling `/` proves almost nothing. NiceGUI builds a page module's UI on a
websocket NAVIGATION event, not on the initial HTTP GET, so `/` can return 200 while Investor
Targeting raises on render. That is exactly what happened: one record with Metro=None made
`sorted({i["Metro"] ...})` raise TypeError and the page died with "server did not load", while
every route still answered 200.

And a whole class of bugs shipped fabricated data instead of crashing: functions that returned
demo/seed data when the real store was empty (seed institutions, meeting log, NOBO, earnings
surprises, global search, NDR-by-city). Silent, convincing, and — once the app went multi-tenant —
USIO's demo data showed up under SARO. Reading PDFs field-by-field is how we caught six of them.

This test closes both gaps mechanically:
  1. RENDER every page for every tenant into a synthetic NiceGUI Client (no browser, no websocket)
     — a render-time exception fails the run.
  2. SCAN the rendered element text for DEMO_TOKENS — curated strings that only ever come from
     fabricated seed/demo data and must never reach a client surface. A hit fails the run.

Each page is rendered once per tenant because the bugs were tenant-specific: USIO rendered while
SARO crashed, and vice versa.

RUN
    python tests/smoke_render.py                 # every tenant, every page
    python tests/smoke_render.py --client saro
    python tests/smoke_render.py --page Investors
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

# ── Demo tokens ────────────────────────────────────────────────────────────
# CURATED, not the whole seed: many seed fund names (e.g. "Vanguard Group Inc") legitimately match
# real 13F holders, so banning every seed name would false-positive. These strings only ever come
# from fabricated demo data and have a distinct real-world counterpart, so their appearance in a
# rendered client surface is proof a demo fallback leaked:
#   * "Perkins Investment Management" — demo fund; the real holder is "PERKINS CAPITAL MANAGEMENT INC"
#   * "Rutabaga Capital"              — demo buyside seed fund; not a real holder in our data
#   * "Ancora Advisors" / "Frederick DiSanto" — demo meeting-log entry + attendee
#   * "Michael Perkins"               — demo contact; the real Perkins contact is "Richard Perkins"
#   * "irconnect@usio.com" is NOT here — that's a real configured address, not demo.
DEMO_TOKENS = [
    "Perkins Investment Management",
    "Rutabaga Capital",
    "Ancora Advisors",
    "Frederick DiSanto",
    "Michael Perkins",
]


def _client_text(client):
    """All human-visible text in a rendered client: label/html text plus text-bearing props
    (label, text, innerHTML, placeholder, tooltip, caption). This is where a leaked demo string
    would surface, regardless of which widget carried it."""
    chunks = []
    for el in client.elements.values():
        t = getattr(el, "_text", None)
        if isinstance(t, str) and t:
            chunks.append(t)
        for key in ("label", "text", "innerHTML", "placeholder", "tooltip", "caption", "title"):
            v = getattr(el, "_props", {}).get(key)
            if isinstance(v, str) and v:
                chunks.append(v)
    return "\n".join(chunks)


def render_one(module_path, render_fn_name, client_id, role="IR"):
    """Render a single page for a single tenant. Returns (ok, detail, demo_hits)."""
    from config.client_config import set_active_client_id
    from core import ui_context

    set_active_client_id(client_id)
    ui_context.set_page_context(role, render_fn_name.replace("render_", "").replace("_page", "").title())

    module = importlib.import_module(module_path)
    fn = getattr(module, render_fn_name, None)
    if fn is None:
        return False, f"missing {render_fn_name}()", []

    try:
        client = Client(page("/"), request=None)
        with client:
            fn()
        text = _client_text(client)
        hits = sorted({tok for tok in DEMO_TOKENS if tok in text})
        return True, "", hits
    except Exception:
        return False, traceback.format_exc(), []


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

    render_fails, demo_fails, checked = [], [], 0
    for cid in clients:
        print(f"\n=== {cid} ===")
        for name, module_path in pages.items():
            fn_name = f"render_{name.lower()}_page"
            ok, detail, hits = render_one(module_path, fn_name, cid)
            checked += 1
            if not ok:
                render_fails.append((cid, name, detail))
                print(f"  RENDER FAIL  {name}")
            elif hits:
                demo_fails.append((cid, name, hits))
                print(f"  DEMO LEAK    {name}  -> {', '.join(hits)}")
            else:
                print(f"  PASS         {name}")

    print(f"\n{'-' * 64}")
    print(f"rendered {checked} page/tenant combinations · "
          f"{len(render_fails)} render failures · {len(demo_fails)} demo leaks")
    for cid, name, detail in render_fails:
        print(f"\nRENDER FAIL {cid} / {name}")
        if not args.quiet:
            print(detail.rstrip())
    for cid, name, hits in demo_fails:
        print(f"\nDEMO LEAK {cid} / {name}: {', '.join(hits)}")

    return 1 if (render_fails or demo_fails) else 0


if __name__ == "__main__":
    sys.exit(main())
