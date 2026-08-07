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


def _open_add_client_dialog(prefill=None, on_created=None):
    """Onboard a new tenant from the Console: write the client record to the DB, reload the
    registry, and seed its two standard IR logins — no code change, no deploy.

    `prefill` (optional) seeds the form — used by the sales-pipeline Won → onboarding hand-off,
    so a closed lead's company/ticker/domain/market-cap carry straight into the new client.
    `on_created(cid)` fires after a successful create (e.g. to mark the lead onboarded)."""
    prefill = prefill or {}
    _mcap_m = prefill.get("market_cap_m")
    if _mcap_m is None and prefill.get("market_cap"):
        _mcap_m = round(prefill["market_cap"] / 1_000_000)         # yfinance gives absolute $
    with ui.dialog() as dialog, ui.card().style(
            f"width:430px;padding:22px;background:{COLORS['surface_bg']};"
            f"border:1px solid {COLORS['border']};border-radius:10px;gap:6px;"):
        ui.label("Add a client").classes("text-lg font-bold").style(f"color:{COLORS['text_heading']};")
        ui.label("Creates the tenant and its two standard IR logins "
                 "(directorofir@ / irassistant@).").style(
            f"color:{COLORS['text_muted']};font-size:12px;margin-bottom:6px;")
        if prefill.get("from_lead"):
            ui.label(f"Onboarding {prefill.get('name') or 'this lead'} from the sales pipeline — "
                     "confirm the details below.").style(
                f"color:{COLORS['accent']};font-size:11.5px;font-weight:600;")
        name_in = ui.input("Company name", value=prefill.get("name") or "").props(
            "outlined dense autofocus").classes("w-full")
        ticker_in = ui.input("Ticker", value=prefill.get("ticker") or "").props(
            "outlined dense").classes("w-full")
        cid_in = ui.input("Client ID", placeholder="lowercase id — blank = derive from ticker") \
            .props("outlined dense").classes("w-full")
        exch_in = ui.select(_EXCHANGES, value="NASDAQ", label="Exchange") \
            .props("outlined dense").classes("w-full")
        mcap_in = ui.number("Market cap ($M)", value=_mcap_m, step=10, min=0) \
            .props("outlined dense").classes("w-full")
        domain_in = ui.input("Email domain", value=prefill.get("domain") or "",
                             placeholder="e.g. standardaero.com") \
            .props("outlined dense").classes("w-full")
        ui.label("Market cap sizes investor-targeting gates (micro <$300M · small <$2B · mid <$10B "
                 "· large). Left blank ⇒ microcap gates until set. Client ID is the permanent tenant "
                 "key. Mail-gateway identity will be irconnect@<domain>.").style(
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
                # sizes the investor-targeting gates (peer_prospects.size_profile); None ⇒ microcap
                "market_cap_m": mcap_in.value if mcap_in.value else None,
                "ir_contact": {"irconnect": f"irconnect@{domain}"}, "executives": {},
                # empty defaults so downstream accessors (CA/CE/CF/CP...) never KeyError
                "analysts": [], "peers": [], "earnings": {}, "financials": {},
                "guidance": {}, "guidance_policy": {},
            }
            client_store.upsert_client(cid, record, active=True)
            reload_registry()
            logins = auth.seed_client_users(cid)
            if on_created:
                try:
                    on_created(cid)
                except Exception as exc:
                    print(f"[console] on_created hook failed: {exc}")
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
        mcap_in = ui.number("Market cap ($M)", value=rec.get("market_cap_m"), step=10, min=0) \
            .props("outlined dense").classes("w-full")
        ui.label("Market cap sizes the investor-targeting gates; blank ⇒ microcap gates.").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
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
                "market_cap_m": mcap_in.value if mcap_in.value else None,
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
        # CHAINED: re-pull signatory contacts from the refreshed holder set — new holders bring new
        # 13F signatories, so the contact identity layer must move with ownership. Free EDGAR call.
        try:
            from core import contacts
            n_contacts = len(contacts.refresh_from_13f(client_id=cid, ticker=ticker))
        except Exception:
            n_contacts = None
        return res, enr, n_contacts

    try:
        res, enr, n_contacts = await asyncio.to_thread(_work)
        n = len(res.get("holders", []))
        _ctc = f" · {n_contacts} contacts re-pulled" if n_contacts is not None else ""
        ui.notify(f"{ticker}: 13F refreshed — {n} holders, {enr.get('enriched', 0)} with real "
                  f"position size{_ctc} (reload to update).", type="positive", timeout=9000)
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


async def _open_lead_email_dialog(v):
    """Compose a personalized outreach email to a website lead: an activity-based draft
    (core.lead_outreach), editable, opened in the operator's mail client (never auto-sent),
    plus a compliant LinkedIn people-search link for a manual lookup."""
    import asyncio

    from core import lead_outreach, sales_pipeline, zoho_mail
    _zoho = zoho_mail.is_configured()

    def _track(note=None):
        """Record this inbound web lead + the touch in the sales pipeline."""
        demo = bool(v.get("demo_request")) or ("Demo request" in (v.get("downloads") or []))
        lead = sales_pipeline.upsert_lead(
            "inbound", company=v.get("org"), ticker=v.get("ticker"),
            email=v.get("email"), demo_request=demo)
        if note:
            sales_pipeline.log_touch(lead["id"], kind="email", note=note)

    with ui.dialog() as dlg, ui.card().style("min-width:480px;max-width:620px;"):
        ui.label(f"Email {v.get('org') or 'lead'}").classes("font-bold").style(
            f"color:{COLORS['text_heading']};font-size:14px;")
        bits = []
        if v.get("ticker"):
            bits.append(v["ticker"])
        if v.get("device"):
            bits.append(v["device"])
        bits.append(f"intent {v.get('intent', 0)}")
        dls = ", ".join(v.get("downloads") or []) or "no downloads"
        ui.label(" · ".join(bits) + " · " + dls).style(f"color:{COLORS['text_muted']};font-size:11.5px;")
        ui.link("Find on LinkedIn ↗", lead_outreach.linkedin_search_url(v), new_tab=True).style(
            f"color:{COLORS['accent']};font-size:12px;")

        _subj = ui.input("Subject").props("outlined dense").classes("w-full").style("font-size:12px;")
        _body = ui.textarea("Message").props("outlined autogrow dense").classes("w-full").style("font-size:12px;")
        _status = ui.label("Drafting from the lead's activity…").style(
            f"color:{COLORS['text_muted']};font-size:11px;")
        with ui.row().classes("justify-end w-full gap-2 items-center").style("margin-top:4px;"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")

            def _copy(_subj=_subj, _body=_body, to=v.get("email")):
                text = f"To: {to}\nSubject: {_subj.value or ''}\n\n{_body.value or ''}"
                ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(text)})")
                ui.notify("Draft copied — paste into Zoho (or any email).", type="positive")
            ui.button("Copy", icon="content_copy", on_click=_copy).props("flat dense")

            def _open_mail(_subj=_subj, _body=_body, to=v.get("email")):
                href = f"mailto:{to}?subject={quote(_subj.value or '')}&body={quote(_body.value or '')}"
                ui.run_javascript(f"window.location.href = {json.dumps(href)}")
                _track(note=_subj.value or "email opened")
                ui.notify("Tracked in the pipeline (Contacted).", type="positive")
            ui.button("Open in email", icon="mail", on_click=_open_mail).props(
                "flat dense" if _zoho else "color=primary dense")

            if _zoho:
                async def _send(_subj=_subj, _body=_body, to=v.get("email")):
                    if not (to or "").strip():
                        ui.notify("No email on this lead.", type="warning")
                        return
                    ui.notify("Sending via Zoho…", type="info")
                    ok, err = await asyncio.to_thread(
                        zoho_mail.send_email, to, _subj.value or "", _body.value or "")
                    if ok:
                        _track(note=_subj.value or "sent via Zoho")
                        ui.notify(f"Sent to {to} — tracked in the pipeline.", type="positive")
                        dlg.close()
                    else:
                        ui.notify(f"Zoho send failed: {err}", type="negative")
                ui.button("Send via Zoho", icon="send", on_click=_send).props("color=primary dense")
    dlg.open()

    try:
        d = await asyncio.to_thread(lead_outreach.draft_email, v)
    except Exception as exc:
        d = None
        print(f"[console] lead draft failed: {exc}")
    if d:
        _subj.value, _body.value = d["subject"], d["body"]
        _status.text = "Draft ready — edit as needed, then Open in email."
    else:
        _status.text = "Couldn't draft automatically — write your message above, then Open in email."


_STAGE_STYLE = {
    "identified": ("#64748B", "rgba(100,116,139,.14)"),
    "contacted":  ("#2563EB", "rgba(37,99,235,.14)"),
    "replied":    ("#0891B2", "rgba(8,145,178,.14)"),
    "meeting":    ("#7C3AED", "rgba(124,58,237,.14)"),
    "demo":       ("#B45309", "rgba(180,83,9,.14)"),
    "won":        ("#15803D", "rgba(21,128,61,.14)"),
    "lost":       ("#B91C1C", "rgba(185,28,28,.12)"),
}


async def _open_pipeline_email_dialog(lead, on_sent=None):
    """Compose outreach to a pipeline lead; on send/open it logs a touch back to the pipeline
    (advancing identified → contacted and starting the follow-up clock)."""
    import asyncio

    from core import ir_contact, sales_pipeline, zoho_mail
    _zoho = zoho_mail.is_configured()
    d = ir_contact.draft_email({"ir_name": lead.get("contact_name"),
                                "company": lead.get("company"), "ticker": lead.get("ticker"),
                                "analysts": None})
    with ui.dialog() as dlg, ui.card().style("min-width:480px;max-width:620px;"):
        ui.label(f"Email {lead.get('company') or 'lead'}").classes("font-bold").style(
            f"color:{COLORS['text_heading']};font-size:14px;")
        who = " · ".join(x for x in [lead.get("contact_name"), lead.get("contact_title")] if x)
        if who:
            ui.label(who).style(f"color:{COLORS['text_muted']};font-size:11.5px;")
        _to = ui.input("To", value=lead.get("email") or "").props("outlined dense").classes(
            "w-full").style("font-size:12px;")
        _subj = ui.input("Subject", value=d["subject"]).props("outlined dense").classes(
            "w-full").style("font-size:12px;")
        _body = ui.textarea("Message", value=d["body"]).props("outlined autogrow dense").classes(
            "w-full").style("font-size:12px;")

        def _logged(note):
            sales_pipeline.log_touch(lead["id"], kind="email", note=note)
            if on_sent:
                on_sent()

        with ui.row().classes("justify-end w-full gap-2 items-center").style("margin-top:4px;"):
            ui.button("Cancel", on_click=dlg.close).props("flat dense")

            def _copy(_to=_to, _subj=_subj, _body=_body):
                ui.run_javascript("navigator.clipboard.writeText(" + json.dumps(
                    f"To: {_to.value}\nSubject: {_subj.value or ''}\n\n{_body.value or ''}") + ")")
                ui.notify("Draft copied.", type="positive")
            ui.button("Copy", icon="content_copy", on_click=_copy).props("flat dense")

            def _open_mail(_to=_to, _subj=_subj, _body=_body):
                href = f"mailto:{_to.value}?subject={quote(_subj.value or '')}&body={quote(_body.value or '')}"
                ui.run_javascript(f"window.location.href = {json.dumps(href)}")
                _logged(_subj.value or "email opened")
                ui.notify("Logged as a touch — lead moved to Contacted.", type="positive")
                dlg.close()
            ui.button("Open in email", icon="mail", on_click=_open_mail).props(
                "flat dense" if _zoho else "color=primary dense")

            if _zoho:
                async def _send(_to=_to, _subj=_subj, _body=_body):
                    if not (_to.value or "").strip():
                        ui.notify("Add a recipient email.", type="warning")
                        return
                    ui.notify("Sending via Zoho…", type="info")
                    ok, err = await asyncio.to_thread(
                        zoho_mail.send_email, _to.value, _subj.value or "", _body.value or "")
                    if ok:
                        _logged(_subj.value or "sent via Zoho")
                        ui.notify(f"Sent to {_to.value} — logged to the pipeline.", type="positive")
                        dlg.close()
                    else:
                        ui.notify(f"Zoho send failed: {err}", type="negative")
                ui.button("Send via Zoho", icon="send", on_click=_send).props("color=primary dense")
    dlg.open()


def _render_sales_pipeline_panel():
    """The unified Praxis sales pipeline (core.sales_pipeline, tenant 'praxis'). Inbound
    demo-requests and overdue follow-ups surface first; reply-marking is manual; nothing
    auto-sends. Fed by the web-traffic analyzer (inbound) and the prospect screener (outbound)."""
    from core import sales_pipeline as sp
    from core import web_ingest
    from page_modules_nicegui.signals import waiting_signal

    box = ui.column().classes("w-full").style("gap:8px;margin-top:8px;")

    def _stage_chip(stage):
        clr, bg = _STAGE_STYLE.get(stage, ("#64748B", "rgba(100,116,139,.14)"))
        ui.label(stage.upper()).style(
            f"background:{bg};color:{clr};font-size:9px;font-weight:800;letter-spacing:.04em;"
            "padding:2px 8px;border-radius:9px;")

    def _lead_card(lead, overdue):
        src = lead.get("source")
        border = "#B45309" if (src == "inbound" and lead.get("demo_request")) else (
            "#B91C1C" if overdue else (COLORS["accent"] if src == "inbound" else COLORS["border"]))
        with ui.card().classes("w-full").style(
                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                f"border-left:4px solid {border};padding:6px 10px;"):
            with ui.row().classes("w-full items-center").style("gap:7px;"):
                ui.icon("call_received" if src == "inbound" else "search").style(
                    f"color:{COLORS['text_muted']};font-size:14px;").tooltip(
                    "Inbound — came to us" if src == "inbound" else "Outbound — we found them")
                ui.label(lead.get("company") or "—").style(
                    f"color:{COLORS['text_heading']};font-size:13px;font-weight:600;")
                if lead.get("ticker"):
                    ui.label(lead["ticker"]).style(
                        "background:#15803D;color:white;font-size:9.5px;font-weight:800;"
                        "padding:1px 7px;border-radius:9px;")
                if lead.get("demo_request"):
                    ui.label("DEMO REQUEST").style(
                        "background:#B45309;color:white;font-size:9px;font-weight:800;"
                        "padding:1px 7px;border-radius:9px;")
                if overdue:
                    ui.label("FOLLOW-UP DUE").style(
                        "background:#B91C1C;color:white;font-size:9px;font-weight:800;"
                        "padding:1px 7px;border-radius:9px;")
                ui.space()
                _stage_chip(lead.get("stage"))
            who = " · ".join(x for x in [lead.get("contact_name"), lead.get("contact_title"),
                                         lead.get("email")] if x)
            if who:
                ui.label(who).style(f"color:{COLORS['text_muted']};font-size:11px;")
            with ui.row().classes("w-full items-center").style("gap:8px;margin-top:2px;"):
                sel = ui.select(sp.STAGES, value=lead.get("stage")).props("dense outlined").style(
                    "font-size:11px;min-width:120px;")

                def _on_stage(e, lid=lead["id"]):
                    sp.set_stage(lid, e.value)
                    _render()
                sel.on("update:model-value", _on_stage)

                nf = ui.input(value=lead.get("next_follow_up") or "").props(
                    "type=date dense outlined").style("font-size:11px;max-width:150px;").tooltip(
                    "Next follow-up")

                def _on_nf(e, lid=lead["id"], nf=nf):
                    sp.set_follow_up(lid, (nf.value or "").strip() or None)
                    _render()
                nf.on("blur", _on_nf)

                ui.space()
                if lead.get("stage") in ("contacted", "identified"):
                    ui.button("Mark replied", icon="mark_email_read",
                              on_click=lambda lid=lead["id"]: (sp.mark_replied(lid), _render())).props(
                        "flat dense").style(f"color:{COLORS['accent']};font-size:10.5px;")
                if lead.get("onboarded_cid"):
                    ui.label(f"Onboarded → {lead['onboarded_cid']}").style(
                        "background:rgba(21,128,61,.14);color:#15803D;font-size:10px;font-weight:800;"
                        "padding:2px 8px;border-radius:9px;")
                elif lead.get("stage") == "won":
                    ui.button("Onboard as client", icon="rocket_launch",
                              on_click=lambda lead=lead: _onboard_won_lead(lead)).props(
                        "dense").style("font-size:10.5px;")
                ui.button("Email", icon="send",
                          on_click=lambda lead=lead: _open_pipeline_email_dialog(lead, on_sent=_render)).props(
                    "flat dense").style(f"color:{COLORS['accent']};font-size:10.5px;")

        def _onboard_won_lead(lead):
            """Hand a Won lead to the standard add-client onboarding, prefilled from the lead."""
            domain = lead.get("domain")
            if not domain and (lead.get("email") or "").count("@") == 1:
                domain = lead["email"].split("@", 1)[1].strip().lower()
            _open_add_client_dialog(
                prefill={"from_lead": True, "name": lead.get("company"),
                         "ticker": lead.get("ticker"), "domain": domain,
                         "market_cap": lead.get("market_cap")},
                on_created=lambda cid, lid=lead["id"]: (sp.mark_onboarded(lid, cid), None)[1])

    def _render():
        box.clear()
        with box:
            with ui.row().classes("w-full items-center").style("gap:8px;"):
                ui.label("Sales pipeline").classes("text-lg font-bold").style(
                    f"color:{COLORS['text_heading']};")
                ui.space()

                def _sync():
                    try:
                        web_ingest.aggregate("praxis")
                        new = sp.ingest_inbound()
                    except Exception as e:
                        ui.notify(f"Sync failed: {e}", type="negative")
                        return
                    ui.notify(f"Synced inbound traffic — {new} new lead(s).", type="positive")
                    _render()
                ui.button("Sync inbound leads", icon="sync", on_click=_sync).props(
                    "flat dense").style(f"color:{COLORS['text_muted']};")
            ui.label("One board for IRconnect prospects — inbound demo requests and overdue "
                     "follow-ups first. Reply-marking is manual; nothing auto-sends.").style(
                f"color:{COLORS['text_muted']};font-size:12px;")

            s = sp.summary()
            with ui.row().style("gap:12px;flex-wrap:wrap;"):
                _stat_tile("Open leads", str(s["open"]))
                _stat_tile("Inbound", str(s["inbound"]))
                _stat_tile("Follow-ups due", str(s["due"]), amber=s["due"] > 0)
                _stat_tile("Won", str(s["won"]))

            leads = sp.list_leads()
            if not leads:
                waiting_signal("your sales pipeline",
                               "Click a company in the prospect screener to track it, or Sync "
                               "inbound leads to pull demo requests from praxispointir.com.",
                               "who's in play, what stage, and what needs a follow-up today",
                               compact=True)
                return

            due = sp.due_followups()
            if due:
                ui.label(f"Needs attention today — {len(due)}").style(
                    f"color:#B45309;font-size:12px;font-weight:800;margin-top:4px;")
                for lead in due:
                    _lead_card(lead, overdue=True)
                ui.label("Pipeline").style(
                    f"color:{COLORS['text_muted']};font-size:12px;font-weight:700;margin-top:6px;")
            due_ids = {d["id"] for d in due}
            for lead in leads:
                if lead["id"] in due_ids:
                    continue
                _lead_card(lead, overdue=sp.is_overdue(lead))

    _render()


def _render_web_traffic_panel():
    """Dogfood: praxispointir.com's own traffic through the IRconnect web-flow analyzer.
    Identified visitors here are prospective CLIENTS (leads), not investors. Aggregated from
    the web_events table (core/web_ingest) that the site's capture snippet feeds."""
    from core import web_flow, web_ingest
    from page_modules_nicegui.signals import waiting_signal

    box = ui.column().classes("w-full").style("gap:8px;margin-top:8px;")

    def _render():
        box.clear()
        with box:
            with ui.row().classes("w-full items-center").style("gap:8px;"):
                ui.label("praxispointir.com — live traffic").classes("text-lg font-bold").style(
                    f"color:{COLORS['text_heading']};")
                ui.space()

                def _refresh():
                    try:
                        web_ingest.aggregate("praxis")
                    except Exception as e:
                        ui.notify(f"Refresh failed: {e}", type="negative")
                        return
                    _render()
                ui.button("Refresh from live traffic", icon="refresh", on_click=_refresh).props(
                    "flat dense").style(f"color:{COLORS['text_muted']};")
            ui.label("Our own marketing site through the web-flow analyzer — an identified visitor is a "
                     "prospective client (a lead), not an investor.").style(
                f"color:{COLORS['text_muted']};font-size:12px;")

            d = web_flow.compose("praxis")
            if not d.get("available"):
                waiting_signal("praxispointir.com traffic",
                               "Deploy the site capture snippet and set DATABASE_URL in Netlify, then Refresh.",
                               "who's evaluating IRconnect, what they read, and the hottest leads", compact=True)
                return
            n_public = sum(1 for v in d["visitors"] if v.get("ticker"))
            with ui.row().style("gap:12px;flex-wrap:wrap;"):
                _stat_tile("Visitors", str(d["n_visitors"]))
                _stat_tile("Identified leads", str(d["n_visitors"] - d["n_new_unidentified"]))
                _stat_tile("Public cos", str(n_public), amber=n_public > 0)
                _stat_tile("Hot leads", str(len(d["hot_prospects"])), amber=len(d["hot_prospects"]) > 0)
            # Lead by intent; a public company visiting (ticker) is worth calling out.
            leads = [v for v in d["visitors"] if v["category"] != "New — unidentified"]
            for v in (d["hot_prospects"] or leads)[:12]:
                with ui.card().classes("w-full").style(
                        f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                        "border-left:4px solid #B45309;padding:6px 10px;"):
                    with ui.row().classes("w-full items-center justify-between"):
                        with ui.row().classes("items-center").style("gap:6px;"):
                            if v.get("device") in ("mobile", "desktop"):
                                ui.icon("smartphone" if v["device"] == "mobile" else "computer").style(
                                    f"color:{COLORS['text_muted']};font-size:15px;").tooltip(v["device"])
                            ui.label(v["org"]).style(
                                f"color:{COLORS['text_heading']};font-size:13px;font-weight:600;")
                            if v.get("ticker"):
                                ui.label(v["ticker"]).style(
                                    "background:#15803D;color:white;font-size:10px;font-weight:800;"
                                    "padding:1px 7px;border-radius:9px;")
                        ui.label(f"intent {v['intent']} · {v['intent_label']}").style(
                            "color:#B45309;font-size:11px;font-weight:700;")
                    ui.label(f"{v['pages']} pages · {v['minutes']} min · "
                             + (", ".join(v["downloads"]) or "no downloads")).style(
                        f"color:{COLORS['text_muted']};font-size:11px;")
                    if v.get("email"):
                        with ui.row().classes("items-center").style("gap:6px;margin-top:3px;"):
                            ui.icon("mail").style(f"color:{COLORS['text_muted']};font-size:13px;")
                            ui.label(v["email"]).style(f"color:{COLORS['accent']};font-size:11.5px;font-weight:600;")
                            ui.button("Email", icon="send",
                                      on_click=lambda v=v: _open_lead_email_dialog(v)).props(
                                "flat dense").style(f"color:{COLORS['accent']};font-size:11px;")

    _render()


def _render_prospect_screener():
    """Screen public companies as IRconnect SALES prospects by metro / industry / analyst
    coverage (core.prospect_screener). >5 analysts = a growing IR pain point (prime prospect);
    >15 and they likely already run a competing tool."""
    import asyncio

    from core import prospect_screener as ps

    def _mcap(m):
        return "" if not m else (f"${m / 1e9:.1f}B" if m >= 1e9 else f"${m / 1e6:.0f}M")

    with ui.expansion("Prospect screener — public companies by metro, industry & analyst coverage",
                      icon="travel_explore").classes("w-full").style("margin-top:10px;"):
        ui.label("More than 5 sell-side analysts signals a growing IR pain point (a prime prospect); more "
                 "than 15 and they likely already run a competing tool. Coverage counts from Yahoo. Metro "
                 "universe is curated + growable (add tickers below).").style(
            f"color:{COLORS['text_muted']};font-size:11.5px;")
        _all = ps.metros()
        _default = "Phoenix / Arizona" if "Phoenix / Arizona" in _all else (_all[0] if _all else None)
        with ui.row().classes("items-end").style("gap:10px;flex-wrap:wrap;margin-top:4px;"):
            metro = ui.select(_all, value=_default, label="Metro").props("dense outlined").classes("min-w-[210px]")
            industry = ui.input("Industry (optional)", placeholder="semiconductor · homebuilding").props(
                "dense outlined").classes("min-w-[190px]")
            mn = ui.number("Min analysts", value=6).props("dense outlined").classes("w-[110px]")
            mx = ui.number("Prime cap", value=15).props("dense outlined").classes("w-[110px]")
        out = ui.column().classes("w-full").style("gap:6px;margin-top:6px;")

        async def _open_prospect_dialog(ticker, company):
            import base64

            from core import ir_contact, prospect_hook, sales_pipeline, zoho_mail
            _zoho = zoho_mail.is_configured()
            with ui.dialog() as dlg, ui.card().style("min-width:520px;max-width:640px;"):
                ui.label(f"{company} · {ticker}").classes("font-bold").style(
                    f"color:{COLORS['text_heading']};font-size:14px;")
                _busy = ui.label("Looking up the IR contact on Yahoo…").style(
                    f"color:{COLORS['text_muted']};font-size:12px;")
                _det = ui.column().classes("w-full").style("gap:4px;")
            dlg.open()
            try:
                e = await asyncio.to_thread(ir_contact.enrich, ticker)
            except Exception as exc:
                _busy.text = f"Lookup failed: {exc}"
                return
            _busy.delete()
            with _det:
                bits = [f"{e['analysts']} analysts" if e.get("analysts") is not None else None,
                        _mcap(e.get("market_cap")), e.get("city"), e.get("industry") or e.get("sector")]
                ui.label(" · ".join(x for x in bits if x)).style(f"color:{COLORS['text_muted']};font-size:12px;")
                if e.get("summary"):
                    ui.label(e["summary"]).style(f"color:{COLORS['text_body']};font-size:11.5px;")
                ui.label("IR decision-maker").style(
                    f"color:{COLORS['text_heading']};font-size:12px;font-weight:700;margin-top:4px;")
                if e.get("ir_name"):
                    _clr = "#B45309" if e["ir_kind"] == "cfo" else ("#B91C1C" if e["ir_kind"] == "ceo" else "#15803D")
                    with ui.row().classes("items-center").style("gap:8px;"):
                        ui.icon("badge").style(f"color:{_clr};font-size:16px;")
                        ui.label(e["ir_name"]).style(
                            f"color:{COLORS['text_heading']};font-size:13px;font-weight:600;")
                        ui.label(ir_contact.contact_label(e)).style(
                            f"background:{_clr}1a;color:{_clr};font-size:10px;font-weight:700;"
                            "padding:1px 8px;border-radius:9px;")
                    if e.get("ceo_name") and e["ir_kind"] != "ceo":
                        ui.label(f"CEO: {e['ceo_name']}").style(f"color:{COLORS['text_muted']};font-size:11px;")
                else:
                    ui.label("No IR/CFO listed on Yahoo — add the contact manually below.").style(
                        f"color:{COLORS['text_muted']};font-size:11.5px;")
                with ui.row().classes("items-center").style("gap:12px;"):
                    if e.get("phone"):
                        ui.label(f"☎ {e['phone']}").style(f"color:{COLORS['text_muted']};font-size:11px;")
                    if e.get("website"):
                        ui.link("Website ↗", e["website"], new_tab=True).style(f"color:{COLORS['accent']};font-size:11px;")
                    _q = quote(f"{e.get('ir_name') or ''} {company}".strip())
                    ui.link("Find on LinkedIn ↗",
                            f"https://www.linkedin.com/search/results/people/?keywords={_q}",
                            new_tab=True).style(f"color:{COLORS['accent']};font-size:11px;")

                d = ir_contact.draft_email(e)
                ui.label("Email the prospect").style(
                    f"color:{COLORS['text_heading']};font-size:12px;font-weight:700;margin-top:4px;")
                _to = ui.input("To", value=e.get("suggested_email") or "").props("outlined dense").classes(
                    "w-full").style("font-size:12px;")
                ui.label("Defaults to the company IR inbox (ir@domain) — confirm, or replace with the "
                         "person's address.").style(f"color:{COLORS['text_muted']};font-size:10.5px;")
                _subj = ui.input("Subject", value=d["subject"]).props("outlined dense").classes(
                    "w-full").style("font-size:12px;")
                _bt = ui.textarea("Message", value=d["body"]).props("outlined autogrow dense").classes(
                    "w-full").style("font-size:12px;")

                # ── personalized 13F hook (two-quarter ownership diff + metro trend) ──
                ui.label("Personalized hook — 13F ownership moves").style(
                    f"color:{COLORS['text_heading']};font-size:12px;font-weight:700;margin-top:6px;")
                _hookwrap = ui.column().classes("w-full").style("gap:4px;")

                def _paint_hook(data):
                    _hookwrap.clear()
                    with _hookwrap:
                        if not data or data.get("error"):
                            if data and data.get("error"):
                                ui.label(data["error"]).style(
                                    f"color:{COLORS['text_muted']};font-size:11px;")
                            return
                        txt = prospect_hook.hook_text(data)
                        if txt:
                            if txt not in (_bt.value or ""):
                                _bt.value = txt + "\n\n" + (_bt.value or "")   # prepend into the email
                            ui.label("Added to the message above:").style(
                                f"color:{COLORS['text_muted']};font-size:10.5px;")
                            ui.label(txt).style(
                                f"color:{COLORS['text_body']};font-size:11.5px;"
                                f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                                "border-radius:6px;padding:6px 8px;")
                        # the moves chart IS the visual of the hook; the metro chart answers "where to go"
                        moves_png = prospect_hook.active_moves_chart_png(data)
                        if moves_png:
                            ui.image("data:image/png;base64," + base64.b64encode(moves_png).decode()).style(
                                f"max-width:100%;border:1px solid {COLORS['border']};border-radius:8px;")
                            ui.button("Download moves chart (PNG)", icon="download",
                                      on_click=lambda p=moves_png, tk=ticker: ui.download(
                                          p, f"{tk}_active_moves.png")).props(
                                "flat dense").style(f"color:{COLORS['accent']};font-size:10.5px;")
                        png = prospect_hook.metro_chart_png(data)
                        if png:
                            uri = "data:image/png;base64," + base64.b64encode(png).decode()
                            ui.image(uri).style(
                                f"max-width:100%;border:1px solid {COLORS['border']};border-radius:8px;")
                            ui.button("Download metro chart (PNG)", icon="download",
                                      on_click=lambda png=png, tk=ticker: ui.download(
                                          png, f"{tk}_holders_by_metro.png")).props(
                                "flat dense").style(f"color:{COLORS['accent']};font-size:10.5px;")

                async def _prepare_hook(_btn=None):
                    _hookstatus.text = "Pulling two quarters of 13F from SEC — this takes a couple minutes…"
                    try:
                        data = await asyncio.to_thread(prospect_hook.prepare, ticker, company)
                    except Exception as exc:
                        _hookstatus.text = f"Hook prep failed: {exc}"
                        return
                    if data.get("error"):
                        _hookstatus.text = data["error"]
                        return
                    _hookstatus.text = (f"Ready — {data['n_holders']} holders, "
                                        f"{len(data['top_changes'])} moves ({data['quarter']}).")
                    _paint_hook(data)

                with ui.row().classes("w-full items-center").style("gap:8px;"):
                    ui.button("Prepare hook", icon="insights", on_click=_prepare_hook).props(
                        "flat dense").style(f"color:{COLORS['accent']};font-size:11px;")
                    _hookstatus = ui.label(
                        f"Pulls {company}'s last two 13F quarters (~2 min). Cached after the first run.").style(
                        f"color:{COLORS['text_muted']};font-size:10.5px;")
                _cached_hook = prospect_hook.get_cached(ticker)
                if _cached_hook and not _cached_hook.get("error"):
                    _paint_hook(_cached_hook)

                def _track(note=None):
                    """Add this prospect to the sales pipeline as an outbound lead."""
                    lead = sales_pipeline.add_outbound(e)
                    if note:
                        sales_pipeline.log_touch(lead["id"], kind="email", note=note)
                    return lead

                with ui.row().classes("w-full items-center gap-2").style("margin-top:2px;"):
                    ui.button("Add to pipeline", icon="add_task",
                              on_click=lambda: (_track(), ui.notify(
                                  f"{company} added to the sales pipeline.", type="positive"))).props(
                        "flat dense").style(f"color:{COLORS['accent']};font-size:11px;")
                    ui.space()
                    ui.button("Cancel", on_click=dlg.close).props("flat dense")

                    def _copy(_to=_to, _subj=_subj, _bt=_bt):
                        ui.run_javascript("navigator.clipboard.writeText(" + json.dumps(
                            f"To: {_to.value}\nSubject: {_subj.value or ''}\n\n{_bt.value or ''}") + ")")
                        ui.notify("Draft copied.", type="positive")
                    ui.button("Copy", icon="content_copy", on_click=_copy).props("flat dense")

                    def _openmail(_to=_to, _subj=_subj, _bt=_bt):
                        href = f"mailto:{_to.value}?subject={quote(_subj.value or '')}&body={quote(_bt.value or '')}"
                        ui.run_javascript(f"window.location.href = {json.dumps(href)}")
                        _track(note=_subj.value or "email opened")
                        ui.notify("Tracked in the pipeline (Contacted).", type="positive")
                    ui.button("Open in email", icon="mail", on_click=_openmail).props(
                        "flat dense" if _zoho else "color=primary dense")

                    if _zoho:
                        async def _send(_to=_to, _subj=_subj, _bt=_bt):
                            if not (_to.value or "").strip():
                                ui.notify("Add a recipient email.", type="warning")
                                return
                            ui.notify("Sending via Zoho…", type="info")
                            ok, err = await asyncio.to_thread(
                                zoho_mail.send_email, _to.value, _subj.value or "", _bt.value or "")
                            if ok:
                                _track(note=_subj.value or "sent via Zoho")
                                ui.notify(f"Sent to {_to.value} — tracked in the pipeline.", type="positive")
                                dlg.close()
                            else:
                                ui.notify(f"Zoho send failed: {err}", type="negative")
                        ui.button("Send via Zoho", icon="send", on_click=_send).props("color=primary dense")

        def _rowcard(r, clr):
            with ui.card().classes("w-full").style(
                    f"background:{COLORS['surface_bg']};border:1px solid {COLORS['border']};"
                    f"border-left:4px solid {clr};padding:5px 10px;cursor:pointer;").on(
                    "click", lambda r=r: _open_prospect_dialog(r["ticker"], r["name"])):
                with ui.row().classes("w-full items-center").style("gap:8px;"):
                    ui.label(r["ticker"]).style(
                        f"background:{clr};color:white;font-size:10px;font-weight:800;padding:1px 7px;border-radius:9px;")
                    ui.label(r["name"]).style(f"color:{COLORS['text_heading']};font-size:12.5px;font-weight:600;")
                    ui.space()
                    a = r.get("analysts")
                    ui.label(f"{a if a is not None else '—'} analysts").style(
                        f"color:{clr};font-size:11.5px;font-weight:700;")
                    ui.label(_mcap(r.get("market_cap"))).style(f"color:{COLORS['text_muted']};font-size:11px;")
                sub = " · ".join(x for x in [r.get("city"), r.get("industry") or r.get("sector")] if x)
                if sub:
                    ui.label(sub).style(f"color:{COLORS['text_muted']};font-size:11px;")

        def _render(res):
            out.clear()
            with out:
                c = res["counts"]
                with ui.row().style("gap:12px;flex-wrap:wrap;"):
                    _stat_tile("Screened", str(c["total"]))
                    _stat_tile("Prime (6–15)", str(c["prime"]), amber=c["prime"] > 0)
                    _stat_tile("Likely tooled", str(c["tooled"]))
                    _stat_tile("Too early", str(c["early"]))
                if res["prime"]:
                    ui.label("Prime prospects — the growing pain point").style(
                        f"color:{COLORS['text_heading']};font-size:12px;font-weight:700;margin-top:4px;")
                    for r in res["prime"]:
                        _rowcard(r, "#B45309")
                if res["tooled"]:
                    with ui.expansion(f"Likely already tooled ({len(res['tooled'])})").classes("w-full"):
                        for r in res["tooled"]:
                            _rowcard(r, "#15803D")
                if res["early"]:
                    with ui.expansion(f"Too early — ≤{int(mn.value or 6) - 1} analysts ({len(res['early'])})").classes("w-full"):
                        for r in res["early"]:
                            _rowcard(r, COLORS["text_muted"])

        async def _run(refresh=False):
            if not metro.value or not ps.tickers_for(metro.value):
                ui.notify(f"No company universe seeded for {metro.value} yet — add tickers below.", type="warning")
                return
            ui.notify("Screening via Yahoo…", type="info")
            try:
                res = await asyncio.to_thread(ps.screen, metro.value, industry.value,
                                              int(mn.value or 6), int(mx.value or 15), refresh)
            except Exception as e:
                ui.notify(f"Screen failed: {e}", type="negative")
                return
            _render(res)

        with ui.row().style("gap:8px;margin-top:4px;"):
            ui.button("Screen", icon="search", on_click=lambda: _run(False)).props("color=primary dense")
            ui.button("Refresh from Yahoo", icon="refresh", on_click=lambda: _run(True)).props("flat dense").style(
                f"color:{COLORS['text_muted']};")

        with ui.expansion("Add companies to a metro's universe").classes("w-full").style("margin-top:4px;"):
            addt = ui.textarea("Tickers (comma or space separated)").props("dense outlined").classes(
                "w-full").style("font-size:12px;")

            def _add(metro=metro, addt=addt):
                import re as _re
                toks = [t for t in _re.split(r"[,\s]+", (addt.value or "")) if t.strip()]
                n = ps.add_tickers(metro.value, toks)
                ui.notify(f"Added {n} ticker(s) to {metro.value} — click Screen." if n else "Nothing new to add.",
                          type="positive" if n else "warning")
            ui.button("Add to universe", icon="add", on_click=_add).props("dense").style("margin-top:4px;")


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
                ui.button("House Contacts", icon="contacts",
                          on_click=lambda: ui.navigate.to("/contacts")).props("flat dense") \
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

            # Unified Praxis sales pipeline (inbound demo requests + outbound screener prospects).
            _render_sales_pipeline_panel()
            # Dogfood: our own praxispointir.com traffic through the analyzer.
            _render_web_traffic_panel()
            # IRconnect sales prospecting: screen public cos by metro / industry / analyst coverage.
            _render_prospect_screener()
