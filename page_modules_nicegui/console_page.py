"""page_modules_nicegui/console_page.py — the Praxis Point Console portfolio home.

A staff-only surface that sits ABOVE the tenants (see core/portfolio): one card per client,
built from cheap cached signals, click a card to drill into that tenant's workspace. Rendered
by app_nicegui's @ui.page("/console") AFTER it has confirmed the user is praxis_staff — so this
module does no auth of its own; it just draws.
"""
import json
import re
from datetime import date, datetime
from urllib.parse import quote

from nicegui import app, ui

from config.theme_tokens import ACTIVE as COLORS
from core import portfolio


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def _open_add_client_dialog():
    """Onboard a new tenant from the Console: write the client record to the DB, reload the
    registry, and seed its two standard IR logins — no code change, no deploy."""
    with ui.dialog() as dialog, ui.card().style(
            f"width:430px;padding:22px;background:{COLORS['surface_bg']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;gap:6px;"):
        ui.label("Add a client").classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label("Creates the tenant and its two standard IR logins "
                 "(directorofir@ / irassistant@).").style(
            f"color:{COLORS['text_muted']};font-size:12px;margin-bottom:6px;")
        name_in = ui.input("Company name").props("outlined dense autofocus").classes("w-full")
        ticker_in = ui.input("Ticker").props("outlined dense").classes("w-full")
        cid_in = ui.input("Client ID", placeholder="lowercase id — blank = derive from ticker") \
            .props("outlined dense").classes("w-full")
        exch_in = ui.select(_EXCHANGES, value="NASDAQ", label="Exchange") \
            .props("outlined dense").classes("w-full")
        domain_in = ui.input("Email domain", placeholder="e.g. standardaero.com") \
            .props("outlined dense").classes("w-full")
        ui.label("Client ID is the permanent tenant key (can't change later). "
                 "Mail-gateway identity will be irconnect@<domain>.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        msg = ui.label("").style("color:#B91C1C;font-size:12px;min-height:16px;")

        def _create():
            from config.client_config import CLIENT_REGISTRY, reload_registry
            from core import client_store, auth
            name = (name_in.value or "").strip()
            ticker = (ticker_in.value or "").strip().upper()
            exch = (exch_in.value or "").strip()
            domain = (domain_in.value or "").strip().lower().removeprefix("www.")
            if not name or not ticker or not domain:
                msg.set_text("Name, ticker and email domain are required."); return
            if "@" in domain or "." not in domain or " " in domain:
                msg.set_text("Enter a bare email domain, e.g. acme.com."); return
            # explicit Client ID if given, else derive from ticker; slugified either way
            cid = _slug(cid_in.value) or _slug(ticker)
            if not cid:
                msg.set_text("Client ID (or ticker) must contain letters or numbers."); return
            if cid in CLIENT_REGISTRY:
                msg.set_text(f"A client '{cid}' already exists."); return
            record = {
                "ticker": ticker, "name": name, "exchange": exch, "email_domain": domain,
                "ir_contact": {"irconnect": f"irconnect@{domain}"}, "executives": {},
                # empty defaults so downstream accessors (CA/CE/CF/CP...) never KeyError
                "analysts": [], "peers": [], "earnings": {}, "financials": {},
                "guidance": {}, "guidance_policy": {},
            }
            client_store.upsert_client(cid, record, active=True)
            reload_registry()
            logins = auth.seed_client_users(cid)
            dialog.close()
            ui.notify(
                f"Added {name} ({ticker}). Logins: {', '.join(logins) or '—'} · "
                f"password {auth.default_user_password()} (must change on first sign-in).",
                type="positive", timeout=10000)
            ui.navigate.reload()

        with ui.row().classes("w-full justify-end").style("gap:8px;margin-top:8px;"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Create", on_click=_create).props("color=primary")
    dialog.open()


def _eng_badge(r):
    """Small clickable engagement chip on a card: status + MRR; opens the engagement dialog."""
    status = r.get("eng_status")
    label, color, bg = _ENG_STATUS.get(status, ("Set engagement", COLORS["text_muted"], "rgba(100,116,139,.10)"))
    mrr = r.get("eng_mrr")
    txt = label + (f" · ${mrr:,.0f}/mo" if mrr else "")
    ui.label(txt).style(
        f"background:{bg};color:{color};font-size:9.5px;font-weight:700;letter-spacing:.02em;"
        "padding:2px 8px;border-radius:10px;cursor:pointer;width:fit-content;") \
        .on("click.stop", lambda _e=None, cid=r["cid"]: _open_engagement_dialog(cid)) \
        .tooltip("Edit engagement / billing")


def _open_engagement_dialog(cid):
    """View/edit a client's engagement + billing terms (stored on the client record under
    'engagement'). Written as a partial overlay, so it merges with the rest of the record."""
    from config.client_config import get_client
    eng = (get_client(cid) or {}).get("engagement") or {}
    with ui.dialog() as dialog, ui.card().style(
            f"width:420px;padding:22px;background:{COLORS['surface_bg']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;gap:6px;"):
        ui.label(f"Engagement — {cid}").classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label("Praxis Point engagement & billing terms for this client.").style(
            f"color:{COLORS['text_muted']};font-size:11px;margin-bottom:4px;")
        status_in = ui.select(_ENG_STATUSES, value=eng.get("status") or "active", label="Status") \
            .props("outlined dense").classes("w-full")
        plan_in = ui.input("Plan / tier", value=eng.get("plan") or "").props("outlined dense").classes("w-full")
        mrr_in = ui.number("Monthly retainer ($)", value=eng.get("mrr"), step=100).props("outlined dense").classes("w-full")
        with ui.row().classes("w-full").style("gap:8px;"):
            start_in = ui.input("Start date (YYYY-MM-DD)", value=eng.get("start_date") or "").props("outlined dense").style("flex:1;")
            renewal_in = ui.input("Renewal date (YYYY-MM-DD)", value=eng.get("renewal_date") or "").props("outlined dense").style("flex:1;")
        with ui.row().classes("w-full").style("gap:8px;"):
            contact_in = ui.input("Primary contact", value=eng.get("primary_contact") or "").props("outlined dense").style("flex:1;")
            bemail_in = ui.input("Billing email", value=eng.get("billing_email") or "").props("outlined dense").style("flex:1;")

        # Billing notices — compose a draft in the operator's own mail client (mailto); the
        # operator reviews and sends. Nothing is sent from the app.
        def _compose(kind):
            to = (bemail_in.value or "").strip()
            if not to:
                ui.notify("Add a billing email first.", type="warning"); return
            name = (get_client(cid) or {}).get("name", cid)
            who = (contact_in.value or "").strip() or "there"
            if kind == "declined":
                subj = f"Payment issue on your Praxis Point IR account — {name}"
                body = (f"Hi {who},\n\nWe attempted to process your monthly Praxis Point IR retainer "
                        "and the card on file was declined. To avoid any interruption to your IR "
                        "program, please update your payment details at your convenience, or reply "
                        "here and we'll help.\n\nThank you,\nPraxis Point")
            else:
                rd = (renewal_in.value or "").strip()
                subj = f"Upcoming renewal — {name} Praxis Point IR"
                body = (f"Hi {who},\n\nYour Praxis Point IR engagement is coming up for renewal"
                        + (f" on {rd}" if rd else "") + ". We'd be glad to keep supporting your IR "
                        "program — let us know if you'd like to review terms.\n\nThank you,\nPraxis Point")
            href = f"mailto:{to}?subject={quote(subj)}&body={quote(body)}"
            ui.run_javascript(f"window.location.href = {json.dumps(href)}")
        with ui.row().style("gap:8px;margin-top:2px;"):
            ui.button("Email: payment declined", icon="mail", on_click=lambda: _compose("declined")).props("flat dense").style(f"color:{COLORS['text_muted']};")
            ui.button("Email: renewal reminder", icon="event", on_click=lambda: _compose("renewal")).props("flat dense").style(f"color:{COLORS['text_muted']};")

        def _save():
            from config.client_config import reload_registry
            from core import client_store
            client_store.upsert_client(cid, {"engagement": {
                "status": status_in.value,
                "plan": (plan_in.value or "").strip(),
                "mrr": mrr_in.value,
                "start_date": (start_in.value or "").strip(),
                "renewal_date": (renewal_in.value or "").strip(),
                "primary_contact": (contact_in.value or "").strip(),
                "billing_email": (bemail_in.value or "").strip(),
            }}, active=True)
            reload_registry()
            dialog.close()
            ui.notify(f"Engagement updated for {cid}.", type="positive")
            ui.navigate.reload()

        with ui.row().classes("w-full justify-end").style("gap:8px;margin-top:8px;"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=_save).props("color=primary")
    dialog.open()


def _open_edit_client_dialog(cid):
    """Edit an existing tenant (writes a partial DB overlay onto its record) or deactivate it.
    client_id is immutable — it's the permanent tenant key — so only the descriptive fields and
    the active flag are editable here."""
    from config.client_config import get_client
    rec = get_client(cid)
    with ui.dialog() as dialog, ui.card().style(
            f"width:430px;padding:22px;background:{COLORS['surface_bg']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;gap:6px;"):
        ui.label(f"Edit client — {cid}").classes("text-lg font-bold").style(
            f"color:{COLORS['text_heading']};")
        ui.label("Client ID is permanent and can't be changed.").style(
            f"color:{COLORS['text_muted']};font-size:11px;margin-bottom:4px;")
        name_in = ui.input("Company name", value=rec.get("name", "")).props("outlined dense autofocus").classes("w-full")
        ticker_in = ui.input("Ticker", value=rec.get("ticker", "")).props("outlined dense").classes("w-full")
        _cur_exch = rec.get("exchange", "") or "NASDAQ"
        _exch_opts = _EXCHANGES if _cur_exch in _EXCHANGES else [_cur_exch] + _EXCHANGES
        exch_in = ui.select(_exch_opts, value=_cur_exch, label="Exchange") \
            .props("outlined dense").classes("w-full")
        domain_in = ui.input("Email domain", value=rec.get("email_domain", "")) \
            .props("outlined dense").classes("w-full")
        active_sw = ui.switch("Active (unchecking hides the tenant everywhere)", value=True)
        msg = ui.label("").style("color:#B91C1C;font-size:12px;min-height:16px;")

        def _save():
            from config.client_config import reload_registry, CLIENT_REGISTRY, DEFAULT_CLIENT_ID
            from core import client_store
            name = (name_in.value or "").strip()
            ticker = (ticker_in.value or "").strip().upper()
            exch = (exch_in.value or "").strip()
            domain = (domain_in.value or "").strip().lower().removeprefix("www.")
            active = bool(active_sw.value)
            if not name or not ticker or not domain:
                msg.set_text("Name, ticker and email domain are required."); return
            if "@" in domain or "." not in domain or " " in domain:
                msg.set_text("Enter a bare email domain, e.g. acme.com."); return
            if not active and cid == DEFAULT_CLIENT_ID:
                msg.set_text(f"Can't deactivate the default client ({cid})."); return
            if not active and len(CLIENT_REGISTRY) <= 1:
                msg.set_text("Can't deactivate the only active client."); return
            overlay = {
                "name": name, "ticker": ticker, "exchange": exch, "email_domain": domain,
                "ir_contact": {"irconnect": f"irconnect@{domain}"},
            }
            client_store.upsert_client(cid, overlay, active=active)
            reload_registry()
            dialog.close()
            ui.notify(f"Updated {name}." + ("" if active else "  Deactivated — now hidden."),
                      type="positive", timeout=6000)
            ui.navigate.reload()

        with ui.row().classes("w-full justify-end").style("gap:8px;margin-top:8px;"):
            ui.button("Cancel", on_click=dialog.close).props("flat")
            ui.button("Save", on_click=_save).props("color=primary")
    dialog.open()

_UP, _DOWN, _AMBER, _AMBER_BG = "#15803D", "#B91C1C", "#B45309", "#FEF3C7"

# Exchange choices for the add/edit client dialogs (US primary listings we onboard against).
_EXCHANGES = ["NASDAQ", "NYSE", "NYSE American", "Cboe BZX", "OTC Markets"]

# Engagement lifecycle statuses -> (label, text color, chip background).
_ENG_STATUSES = ["onboarding", "active", "paused", "churned"]
_ENG_STATUS = {
    "active":     ("Active",     "#15803D", "rgba(21,128,61,.12)"),
    "onboarding": ("Onboarding", "#1D4ED8", "rgba(29,78,216,.12)"),
    "paused":     ("Paused",     "#B45309", "rgba(180,83,9,.12)"),
    "churned":    ("Churned",    "#B91C1C", "rgba(185,28,28,.12)"),
}


def _fmt_date(iso, with_year=False):
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "").split("+")[0].split("T")[0][:10] if "T" not in str(iso)
                                   else str(iso).split("T")[0])
        return d.strftime("%b %-d, %Y" if with_year else "%b %-d")
    except Exception:
        # %-d isn't portable to Windows strftime; fall back to a manual build
        try:
            d = datetime.fromisoformat(str(iso).split("T")[0][:10])
            mon = d.strftime("%b")
            return f"{mon} {d.day}, {d.year}" if with_year else f"{mon} {d.day}"
        except Exception:
            return "—"


def _fmt_age(minutes):
    if minutes is None:
        return ""
    if minutes < 1:
        return "just now"
    if minutes < 60:
        return f"{minutes}m ago"
    if minutes < 1440:
        return f"{minutes // 60}h ago"
    return f"{minutes // 1440}d ago"


def _price_text(r):
    p, pct = r["last_price"], r["pct_change"]
    if p is None:
        return "—", COLORS["text_muted"]
    if pct is None:
        return f"${p:,.2f}", COLORS["text_body"]
    color = _UP if pct >= 0 else _DOWN
    return f"${p:,.2f}   {'+' if pct >= 0 else ''}{pct:.1f}%", color


def _earnings_cell(r):
    d = r["earnings_date"]
    if not d:
        return "—", COLORS["text_body"]
    n = r["days_to_earnings"]
    txt = _fmt_date(d)
    if n is None:
        return txt, COLORS["text_body"]
    if n < 0:
        return f"{txt} · reported", COLORS["text_muted"]
    color = _AMBER if n <= 14 else COLORS["text_body"]
    return f"{txt} · in {n}d", color


def _f13_cell(r):
    n = r["holder_count"]
    if not n:
        return "none on file", _AMBER
    fetched = _fmt_date(r["f13_fetched_at"]) if r["f13_fetched_at"] else "?"
    stale = "13F stale" in r["attention"]
    return f"{n} · {fetched}", (_AMBER if stale else COLORS["text_body"])


def _consensus_cell(r):
    """Praxis Consensus roll-up state for the card: value + source tag, green when authoritative
    (model roll-up cleared coverage), amber when provisional (street/override/thin models)."""
    v = r.get("consensus_rev_m")
    if v is None:
        return "— (need models)", _AMBER
    src = r.get("consensus_source")
    if src == "models":
        tag = f"Praxis {r.get('consensus_n_models', 0)}/{r.get('consensus_n_covering', 0)}"
    elif src == "street":
        tag = "street"
    else:
        tag = "override"
    authoritative = r.get("consensus_status") == "authoritative"
    return f"${v:,.1f}M · {tag}", (COLORS["text_body"] if authoritative else _AMBER)


def _nobo_cell(r):
    n = r.get("nobo_uploads", 0)
    if not n:
        return "no Broadridge upload", _AMBER
    return f"{n} upload{'s' if n != 1 else ''} · {r.get('nobo_latest') or '?'}", COLORS["text_body"]


def _metric(label, value, value_color=None):
    with ui.row().classes("w-full items-center").style("gap:8px;"):
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:11.5px;")
        ui.space()
        ui.label(value).style(
            f"color:{value_color or COLORS['text_body']};font-size:12.5px;font-weight:600;"
            "text-align:right;")


def _stat_tile(label, value, amber=False):
    with ui.card().style(
            f"padding:10px 16px;background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
            "border-radius:10px;min-width:120px;gap:1px;box-shadow:0 1px 2px rgba(15,23,42,.05);"):
        ui.label(value).style(
            f"color:{'#B45309' if amber else COLORS['text_heading']};font-size:18px;font-weight:800;")
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:10.5px;letter-spacing:.03em;")


def _drill_in(cid):
    # Reuses the tenant-switch mechanism: set the session's active client, land in the workspace.
    app.storage.user["active_client_id"] = cid
    ui.navigate.to("/")


async def _refresh_13f(cid, ticker, name):
    """Re-pull this tenant's institutional 13F holders from EDGAR, off the event loop so the UI
    stays responsive. 13F is the one genuinely on-demand data source (price auto-refreshes;
    consensus is registry/auto; NOBO is a Broadridge upload).

    CHAINED: the full-text search returns presence-only rows (shares=1/value=0), which would
    silently DOWNGRADE holders that already carry real magnitude. enrich_holder_positions() then
    reads each filer's own info table for the actual shares/value/book total. That second pass is
    the slow part (one document per filer), hence the up-front warning."""
    import asyncio
    ui.notify(f"Refreshing 13F for {ticker} — bulk SEC pull, takes several minutes…",
              type="info", timeout=8000)

    def _work():
        from config.client_config import set_active_client_id, CP
        from core import sec_filings
        set_active_client_id(cid)   # scope the cache write to this tenant (runs in this thread)
        # BULK dataset, not the full-text search. Full-text only confirms WHO holds, sparsely, for
        # issuers its index happens to cover — for SARO it returned 324 -> 36 holders (11%) and
        # missed Carlyle's $2.18B sponsor stake entirely. Refreshing through that path would
        # silently DESTROY ~90% of a complete holder list. One bulk download is slow but exact, and
        # it covers the peer set in the same pass (which peer prospecting needs anyway).
        pairs = [(ticker, name)] + [(p["ticker"], p.get("name") or p["ticker"]) for p in CP()]
        res_all = sec_filings.refresh_13f_bulk_all(pairs)
        res = res_all.get(ticker.upper(), {})
        enr = {"enriched": sum(1 for h in (res.get("holders") or []) if h.get("size_known"))}
        return res, enr

    try:
        res, enr = await asyncio.to_thread(_work)
        n = len(res.get("holders", []))
        ui.notify(f"{ticker}: 13F refreshed — {n} holders, {enr.get('enriched', 0)} with real "
                  f"position size (reload to update).", type="positive", timeout=9000)
    except Exception as e:
        ui.notify(f"{ticker}: 13F refresh failed — {e}", type="negative", timeout=8000)


async def _refresh_price(cid, ticker):
    """Force-refresh this tenant's market snapshot (bypasses the freshness check)."""
    import asyncio
    ui.notify(f"Refreshing price for {ticker}…", type="info")

    def _work():
        from core import market_data
        return market_data.refresh_one(ticker, client_id=cid)

    try:
        fresh = await asyncio.to_thread(_work)
        if fresh and fresh.get("last_price") is not None:
            pct = fresh.get("pct_change")
            pct_txt = f" ({'+' if (pct or 0) >= 0 else ''}{pct:.1f}%)" if pct is not None else ""
            ui.notify(f"{ticker}: ${fresh['last_price']:.2f}{pct_txt} (reload to update card).",
                      type="positive", timeout=6000)
        else:
            ui.notify(f"{ticker}: no price data returned.", type="warning", timeout=6000)
    except Exception as e:
        ui.notify(f"{ticker}: price refresh failed — {e}", type="negative", timeout=8000)


async def _refresh_consensus(cid, ticker):
    """Recompute this tenant's consensus (registry value wins; else a period-verified live
    estimate). Reports the result via toast — the card shows the curated registry value, so a
    live estimate surfaces here rather than mutating the card."""
    import asyncio
    ui.notify(f"Refreshing consensus for {ticker}…", type="info")

    def _work():
        from config.client_config import set_active_client_id
        from core import market_data
        set_active_client_id(cid)   # consensus_rev resolves ticker/registry from the active client
        return market_data.refresh_consensus(client_id=cid)

    try:
        res = await asyncio.to_thread(_work)
        val, src, ver = res.get("value_m"), res.get("source"), res.get("verified")
        if val is not None and (src == "registry" or ver):
            tag = "registry" if src == "registry" else "live · verified"
            ui.notify(f"{ticker}: consensus ${val:.1f}M ({tag}).", type="positive", timeout=6000)
        elif val is not None:
            ui.notify(f"{ticker}: live estimate ${val:.1f}M but period UNVERIFIED — not used.",
                      type="warning", timeout=8000)
        else:
            ui.notify(f"{ticker}: no consensus (no registry value, no verified live estimate).",
                      type="warning", timeout=8000)
    except Exception as e:
        ui.notify(f"{ticker}: consensus refresh failed — {e}", type="negative", timeout=8000)


def _client_card(r):
    card = ui.card().classes("cursor-pointer").style(
        f"padding:16px;background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
        "border-radius:10px;gap:6px;box-shadow:0 1px 2px rgba(15,23,42,.05);")
    card.on("click", lambda _e=None, cid=r["cid"]: _drill_in(cid))
    with card:
        with ui.row().classes("w-full items-start").style("gap:8px;"):
            with ui.column().style("gap:3px;"):
                ui.label(r["name"]).classes("text-base font-bold").style(
                    f"color:{COLORS['text_heading']};line-height:1.2;")
                ui.label(f"{r['exchange']}: {r['ticker']}" if r["exchange"] else r["ticker"]).style(
                    f"color:{COLORS['text_muted']};font-size:11px;letter-spacing:.02em;")
                _eng_badge(r)
            ui.space()
            with ui.column().style("align-items:flex-end;gap:2px;"):
                ptxt, pcolor = _price_text(r)
                ui.label(ptxt).style(f"color:{pcolor};font-weight:700;font-size:12.5px;white-space:nowrap;")
                if r.get("px_age_min") is not None:
                    ui.label(f"px {_fmt_age(r['px_age_min'])}").style(
                        f"color:{COLORS['text_muted']};font-size:9.5px;")
                # action icons — click.stop so they don't also trigger the card's drill-in.
                # Distinct topic icons (price / holders / consensus) each REFRESH that source.
                _mut = f"color:{COLORS['text_muted']};"
                with ui.row().style("gap:0;"):
                    async def _rp(_e=None, _cid=r["cid"], _tk=r["ticker"]):
                        await _refresh_price(_cid, _tk)

                    async def _rf(_e=None, _cid=r["cid"], _tk=r["ticker"], _nm=r["name"]):
                        await _refresh_13f(_cid, _tk, _nm)

                    async def _rc(_e=None, _cid=r["cid"], _tk=r["ticker"]):
                        await _refresh_consensus(_cid, _tk)

                    ui.button(icon="show_chart").props("flat dense round size=sm").style(_mut) \
                        .on("click.stop", _rp).tooltip("Refresh price")
                    ui.button(icon="groups").props("flat dense round size=sm").style(_mut) \
                        .on("click.stop", _rf).tooltip("Refresh 13F holders")
                    ui.button(icon="insights").props("flat dense round size=sm").style(_mut) \
                        .on("click.stop", _rc).tooltip("Refresh consensus")
                    ui.button(icon="edit").props("flat dense round size=sm").style(_mut) \
                        .on("click.stop", lambda _e=None, cid=r["cid"]: _open_edit_client_dialog(cid)) \
                        .tooltip("Edit client")
        ui.separator().style("margin:6px 0;")
        etxt, ecolor = _earnings_cell(r)
        _metric("Next earnings", etxt, ecolor)
        _metric("Consensus", *_consensus_cell(r))
        ftxt, fcolor = _f13_cell(r)
        _metric("13F holders", ftxt, fcolor)
        _metric("NOBO", *_nobo_cell(r))
        if r["attention"]:
            with ui.row().style("gap:6px;flex-wrap:wrap;margin-top:6px;"):
                for a in r["attention"]:
                    ui.label(a).style(
                        f"background:{_AMBER_BG};color:{_AMBER};font-size:10px;font-weight:700;"
                        "padding:2px 8px;border-radius:10px;")


_EVT_STYLE = {
    "Earnings":     ("#1D4ED8", "rgba(29,78,216,.12)"),
    "Renewal":      ("#B45309", "rgba(180,83,9,.12)"),
    "Quiet period": ("#64748B", "rgba(100,116,139,.12)"),
}


def render_console_calendar(user):
    """Cross-client operator calendar — an agenda of what's coming up at every client (earnings,
    engagement renewals, quiet-period starts), so PP can see the whole book's schedule at once."""
    from config.client_config import get_client
    rows = portfolio.portfolio_overview()
    raw = []
    for r in rows:
        if r.get("earnings_date"):
            raw.append((r["earnings_date"], "Earnings", f"{r['ticker']} earnings"))
        if r.get("eng_renewal"):
            raw.append((r["eng_renewal"], "Renewal", f"{r['name']} engagement renewal"))
        qs = (get_client(r["cid"]).get("earnings") or {}).get("quiet_start")
        if qs:
            raw.append((qs, "Quiet period", f"{r['ticker']} quiet period starts"))

    def _pd(s):
        try:
            return date.fromisoformat(str(s)[:10])
        except Exception:
            return None
    today = date.today()
    events = sorted(((d, t, l) for (s, t, l) in raw if (d := _pd(s)) and d >= today), key=lambda e: e[0])

    def _logout():
        app.storage.user.pop("user_id", None)
        app.storage.user.pop("active_client_id", None)
        ui.navigate.to("/login")

    with ui.column().classes("w-full items-center"):
        wrap = ui.column().style("width:min(1000px,94vw);margin-top:24px;gap:14px;")
        with wrap:
            with ui.row().classes("w-full items-center").style("gap:10px;"):
                ui.label("Praxis Point").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
                ui.label("CALENDAR").style(
                    f"background:{COLORS['text_heading']};color:white;font-size:10px;font-weight:800;"
                    "letter-spacing:.08em;padding:3px 9px;border-radius:6px;")
                ui.space()
                ui.button("Back to Console", icon="arrow_back",
                          on_click=lambda: ui.navigate.to("/console")).props("flat dense").style(f"color:{COLORS['text_muted']};")
                ui.button("Sign out", icon="logout", on_click=_logout).props("flat dense").style(f"color:{COLORS['text_muted']};")

            ui.label(f"{len(events)} upcoming across {len(rows)} clients").style(
                f"color:{COLORS['text_muted']};font-size:13px;")

            if not events:
                ui.label("Nothing scheduled yet. Set earnings dates and engagement renewals to "
                         "populate this.").style(f"color:{COLORS['text_muted']};font-size:12.5px;")
                return
            with ui.card().classes("w-full").style(
                    f"padding:0;background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                    "border-radius:10px;overflow:hidden;"):
                for i, (d, typ, label) in enumerate(events):
                    color, bg = _EVT_STYLE.get(typ, (COLORS["text_muted"], "rgba(100,116,139,.12)"))
                    days = (d - today).days
                    when = "today" if days == 0 else ("tomorrow" if days == 1 else f"in {days}d")
                    with ui.row().classes("w-full items-center").style(
                            "gap:12px;padding:11px 16px;"
                            + (f"border-top:1px solid {COLORS['border']};" if i else "")):
                        ui.label(d.strftime("%b %d")).style(
                            f"color:{COLORS['text_heading']};font-weight:700;font-size:12.5px;min-width:60px;")
                        ui.label(typ).style(
                            f"background:{bg};color:{color};font-size:9.5px;font-weight:700;"
                            "padding:2px 8px;border-radius:9px;min-width:86px;text-align:center;")
                        ui.label(label).style(f"color:{COLORS['text_body']};font-size:12.5px;")
                        ui.space()
                        ui.label(when).style(f"color:{COLORS['text_muted']};font-size:11.5px;")


def render_console_home(user):
    rows = portfolio.portfolio_overview()
    needs = sum(1 for r in rows if r["attention"])

    with ui.column().classes("w-full items-center"):
        wrap = ui.column().style("width:min(1100px,94vw);margin-top:24px;gap:16px;")
        with wrap:
            # ── top bar ─────────────────────────────────────────────────────
            with ui.row().classes("w-full items-center").style("gap:10px;"):
                ui.label("Praxis Point").classes("text-2xl font-bold").style(
                    f"color:{COLORS['text_heading']};")
                ui.label("CONSOLE").style(
                    f"background:{COLORS['text_heading']};color:white;font-size:10px;font-weight:800;"
                    "letter-spacing:.08em;padding:3px 9px;border-radius:6px;")
                ui.space()
                ui.label(user.get("display_name") or user["user_id"]).style(
                    f"color:{COLORS['text_muted']};font-size:11.5px;")
                ui.button("Calendar", icon="calendar_month",
                          on_click=lambda: ui.navigate.to("/console/calendar")).props("flat dense") \
                    .style(f"color:{COLORS['text_muted']};")
                ui.button("Add client", icon="add", on_click=_open_add_client_dialog) \
                    .props("dense").style("margin-left:4px;")
                ui.button("User Admin", icon="manage_accounts",
                          on_click=lambda: ui.navigate.to("/admin/users")).props("flat dense") \
                    .style(f"color:{COLORS['text_muted']};")

                def _logout():
                    app.storage.user.pop("user_id", None)
                    app.storage.user.pop("active_client_id", None)
                    ui.navigate.to("/login")
                ui.button("Sign out", icon="logout", on_click=_logout).props("flat dense") \
                    .style(f"color:{COLORS['text_muted']};")

            # ── sub-header ──────────────────────────────────────────────────
            n = len(rows)
            summary = (f"{n} client{'' if n == 1 else 's'} · "
                       + (f"{needs} need{'s' if needs == 1 else ''} attention" if needs else "all clear"))
            ui.label(summary).style(f"color:{COLORS['text_muted']};font-size:13px;")

            # ── engagement / billing roll-up ────────────────────────────────
            total_mrr = sum(r.get("eng_mrr") or 0 for r in rows)
            active = sum(1 for r in rows if r.get("eng_status") == "active")
            renewals = sum(1 for r in rows
                           if r.get("eng_renewal_days") is not None and 0 <= r["eng_renewal_days"] <= 60)
            with ui.row().classes("w-full").style("gap:12px;flex-wrap:wrap;"):
                _stat_tile("MRR", f"${total_mrr:,.0f}")
                _stat_tile("ARR", f"${total_mrr * 12:,.0f}")
                _stat_tile("Active", f"{active}/{n}")
                _stat_tile("Renewals ≤60d", str(renewals),
                           amber=renewals > 0)

            # ── portfolio grid ──────────────────────────────────────────────
            with ui.element("div").style(
                    "display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));"
                    "gap:16px;width:100%;"):
                for r in rows:
                    _client_card(r)
