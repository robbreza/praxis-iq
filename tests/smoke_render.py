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
import os
import sys
import traceback
from pathlib import Path

# Rendering pages here would otherwise log spurious Lighthouse "views" into the real engagement
# telemetry — suppress those writes so the used-vs-ignored numbers stay clean.
os.environ.setdefault("LIGHTHOUSE_TELEMETRY_OFF", "1")

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
    """Render a single page for a single tenant. Returns (ok, detail, demo_hits, lazy) where
    `lazy` is a list of (tab_name, ok, detail, hits) for the page's LAZY tab-panels — content that
    only builds on tab-click and is otherwise invisible to this test (see core/lazy_tab_probe)."""
    from config.client_config import set_active_client_id
    from core import lazy_tab_probe, ui_context

    set_active_client_id(client_id)
    ui_context.set_page_context(role, render_fn_name.replace("render_", "").replace("_page", "").title())

    module = importlib.import_module(module_path)
    fn = getattr(module, render_fn_name, None)
    if fn is None:
        return False, f"missing {render_fn_name}()", [], []

    lazy_tab_probe.set_capturing(True)
    lazy_tab_probe.reset()
    try:
        client = Client(page("/"), request=None)
        with client:
            fn()
        text = _client_text(client)
        hits = sorted({tok for tok in DEMO_TOKENS if tok in text})
    except Exception:
        return False, traceback.format_exc(), [], []

    # Now exercise each lazy tab this page registered — build its deferred content and check it the
    # same way (render exception + demo leak). Each in its own client so one failure can't taint the
    # next. The build_fn closures still reference the page state built above.
    lazy = []
    for _pg, tab, build_fn in lazy_tab_probe.captured():
        try:
            sub = Client(page("/"), request=None)
            with sub:
                build_fn()
            th = sorted({tok for tok in DEMO_TOKENS if tok in _client_text(sub)})
            lazy.append((tab, True, "", th))
        except Exception:
            lazy.append((tab, False, traceback.format_exc(), []))
    lazy_tab_probe.reset()
    return True, "", hits, lazy


def check_ndr_planning_render(cid):
    """Regression guard (2026-08-08): the Active NDRs panel crashed rendering a PLANNING NDR when a
    candidate in the trip's metro had a missing/None Engagement_Score — `_ndr_target_candidates`
    sorted by `-x["Engagement_Score"]`, and the exception aborted the panel MID-LOOP so the card
    never drew (the user saw the completed cards but not the new one). smoke_render already renders
    the NDR lazy tab, but the SEEDED trips sit in 'safe' metros, so the condition never fired. Force
    it: score the universe, blank one holder's score, point a Planning trip (with a shortlist) at
    its metro, render the NDR tab. A render exception fails the run. Returns (ok, detail)."""
    from config.client_config import set_active_client_id
    from core import ui_context, targets as tm
    set_active_client_id(cid)
    ui_context.set_page_context("IR", "Investors")
    import page_modules_nicegui.investors_page as IP
    try:
        raw = IP._merge_sec_universe(tm.targets_as_institutions(cid), cid)
        _ex = {IP._norm_name(i["Fund"]) for i in raw}
        raw += [p for p in IP._promoted_prospect_records(cid) if IP._norm_name(p["Fund"]) not in _ex]
        IP._enrich_peer_holdings_with_live_13f(raw, [p["ticker"] for p in IP._load_peer_universe()])
        insts = IP._score_institutions(raw, "pre", set(), IP._load_meeting_log())
    except Exception:
        return False, traceback.format_exc()
    if not insts:
        return True, ""                       # nothing tracked for this tenant — nothing to exercise
    insts[0]["Engagement_Score"] = None       # the exact condition that used to crash the panel
    metro = insts[0].get("Metro") or "Unknown (SEC)"
    trip = {"name": "SMOKE Planning NDR", "city": metro, "ndr_type": "in-person", "status": "Planning",
            "shortlist": [{"institution": insts[0]["Fund"], "status": "shortlisted"}], "meetings": [],
            "days": 2, "slots_per_day": 6, "team": [], "focus": "", "notes": "", "sponsor_bank": "",
            "dates": "TBD", "debrief": {}}
    _orig = IP._load_json
    IP._load_json = lambda name, default=None: [trip] if name == "ndr_trips.json" else _orig(name, default)
    try:
        client = Client(page("/"), request=None)
        with client:
            IP._render_ndr_tab(insts, IP._load_meeting_log(), cid, "pre")
        return True, ""
    except Exception:
        return False, traceback.format_exc()
    finally:
        IP._load_json = _orig


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

    render_fails, demo_fails, checked, lazy_checked = [], [], 0, 0
    for cid in clients:
        print(f"\n=== {cid} ===")
        for name, module_path in pages.items():
            fn_name = f"render_{name.lower()}_page"
            ok, detail, hits, lazy = render_one(module_path, fn_name, cid)
            checked += 1
            if not ok:
                render_fails.append((cid, name, detail))
                print(f"  RENDER FAIL  {name}")
            elif hits:
                demo_fails.append((cid, name, hits))
                print(f"  DEMO LEAK    {name}  -> {', '.join(hits)}")
            else:
                print(f"  PASS         {name}")
            # lazy tab-panels this page deferred (built here, not at page render)
            for tab, tok, tdetail, thits in lazy:
                lazy_checked += 1
                label = f"{name} › {tab}"
                if not tok:
                    render_fails.append((cid, label, tdetail))
                    print(f"  RENDER FAIL  {label}  (lazy tab)")
                elif thits:
                    demo_fails.append((cid, label, thits))
                    print(f"  DEMO LEAK    {label}  -> {', '.join(thits)}")
                else:
                    print(f"  PASS         {label}  (lazy tab)")

        # Targeted regression: NDR Active-cards panel must render a PLANNING NDR whose metro holds an
        # unscored candidate (the crash that hid a just-planned NDR's card). Runs when Investors is in
        # scope, once per tenant.
        if not args.page or args.page == "Investors":
            ok_ndr, ndr_detail = check_ndr_planning_render(cid)
            checked += 1
            _lbl = "Investors › Active NDRs (Planning-card regression)"
            if not ok_ndr:
                render_fails.append((cid, _lbl, ndr_detail))
                print(f"  RENDER FAIL  {_lbl}")
            else:
                print(f"  PASS         {_lbl}")

    print(f"\n{'-' * 64}")
    print(f"rendered {checked} page/tenant combinations + {lazy_checked} lazy tab(s) · "
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
