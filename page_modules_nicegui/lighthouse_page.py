"""Lighthouse page — the CEO "why is my stock moving?" view.

Renders the last few sessions' verdicts as conclusion-first cards, recomputed live from the
DB-backed engine (lh_ohlcv / lh_event — no network on render): expected vs actual vs residual,
abnormality vs explanation confidence, drivers, found vs checked-but-not-found, technical expression,
with one-click evidence links. MVP is wired for USIO; other tickers show a graceful notice.
"""
from nicegui import ui

from config.client_config import CT, get_active_client_id
from config.theme_tokens import ACTIVE as COLORS

_ROLE_COLOR = {"primary": "#1D4ED8", "contributing": "#0EA5E9", "amplifier": "#7C3AED",
               "diffusing": "#D97706", "coincident": "#64748B", "unexplained": "#DC2626",
               "contributor": "#0EA5E9"}


def _conf_badge(label, value):
    color = {"HIGH": "#B91C1C", "MODERATE": "#B45309", "LOW": "#64748B", "ROUTINE": "#64748B"}.get(value, "#64748B")
    with ui.element("div").style(f"display:inline-flex;gap:6px;align-items:center;"
                                 f"border:1px solid {color}55;border-radius:999px;padding:2px 10px;background:{color}11;"):
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        ui.label(value).style(f"color:{color};font-weight:700;font-size:var(--fs-xs);")


def _bar_row(label, note, value, scale, *, is_issuer=False, is_comp=False, rel=None, issuer="USIO"):
    """One diverging bar (zero-centered) on a shared scale, so every benchmark is read against the
    same axis and USIO's position among them is visible at a glance."""
    green, red = "#15803D", "#B91C1C"
    color = green if value >= 0 else red
    half = 108
    blen = min(half, abs(value) / scale * half) if scale else 0
    left = half if value >= 0 else half - blen
    lab_color = COLORS["text_heading"] if is_issuer else COLORS["text_body"] if is_comp else COLORS["text_muted"]
    weight = "800" if is_issuer else "600"
    with ui.row().classes("items-center w-full").style("gap:10px;margin:1px 0;"):
        with ui.row().classes("items-center justify-end").style("width:150px;gap:6px;flex:none;"):
            ui.element("div").style(f"width:7px;height:7px;border-radius:999px;flex:none;"
                                    f"background:{'#0F172A' if is_issuer else '#1D4ED8' if is_comp else '#CBD5E1'};")
            ui.label(label).style(f"color:{lab_color};font-weight:{weight};font-size:var(--fs-sm);text-align:right;")
        # bar track with a centre zero line
        with ui.element("div").style(f"position:relative;width:{half*2}px;height:16px;flex:none;"
                                     f"background:{COLORS.get('surface_alt', '#F1F5F9')};border-radius:4px;"):
            ui.element("div").style(f"position:absolute;left:{half}px;top:0;width:1px;height:16px;background:#94A3B8;")
            ui.element("div").style(f"position:absolute;left:{left}px;top:3px;width:{blen}px;height:10px;"
                                    f"background:{color};border-radius:3px;opacity:{'1' if (is_issuer or is_comp) else '0.55'};")
        val = f"{value*100:+.1f}%"
        rel_txt = ""
        if rel is not None:
            rc = red if rel < 0 else green
            rel_txt = f"  ·  {issuer} {rel*100:+.1f} pts"
        with ui.row().classes("items-baseline").style("width:150px;gap:0;flex:none;"):
            ui.label(val).style(f"color:{color};font-weight:{weight};font-size:var(--fs-sm);")
            if rel is not None:
                ui.label(rel_txt).style(f"color:{(red if rel < 0 else green)};font-size:var(--fs-xs);")
    if note:
        pass


def _render_week_in_context(wk, _weekly, issuer="USIO"):
    drift_color = "#B91C1C" if wk["resid_sum"] < 0 else "#15803D"
    ctx = wk.get("context") or []
    scale = max([abs(wk["car_actual"])] + [abs(c["ret"]) for c in ctx] + [0.005])
    with ui.card().classes("w-full").style("border:1px solid #B4530955;background:#FFFDF7;margin-bottom:12px;padding:14px 16px;"):
        with ui.row().classes("items-center w-full justify-between"):
            ui.label(f"THIS WEEK IN CONTEXT · {wk['week']}").style("color:#B45309;font-weight:800;font-size:var(--fs-xs);letter-spacing:.04em;")
            ui.label(f"{_weekly.ordinal(wk['weekly_rarity']*100)}-percentile week") \
                .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        # punchline sentence — the number never appears without its comparison
        if wk.get("context_read"):
            ui.label(f"{issuer} {wk['context_read']}").style(f"color:{COLORS['text_heading']};font-size:var(--fs-md);font-weight:600;margin:6px 0 2px;")
        # the shared-axis comparison
        with ui.column().classes("w-full").style("gap:0;margin:8px 0 4px;"):
            _bar_row(issuer, "", wk["car_actual"], scale, is_issuer=True, issuer=issuer)
            for c in ctx:
                _bar_row(c["label"], c["note"], c["ret"], scale, is_comp=c["relevant"], rel=c["rel"], issuer=issuer)
        ui.label("● comp = the peer basket & size index the attribution model uses · lighter bars are broad-market reference") \
            .style(f"color:{COLORS['text_muted']};font-size:var(--fs-2xs);margin-top:2px;")
        # the drift + honest read
        ui.element("div").style("height:1px;background:#E2E8F0;margin:8px 0;")
        with ui.row().classes("items-baseline gap-2"):
            ui.label("After stripping market & peer moves:").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
            ui.label(f"{wk['resid_sum']*100:+.1f}% unexplained drift").style(f"color:{drift_color};font-size:var(--fs-md);font-weight:800;")
            ui.label(f"· {wk['abnormal_days']} abnormal day(s) of {wk['trading_days']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        ui.label(f"Read: {wk['driver']}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);font-style:italic;margin-top:2px;")
        if wk.get("holders") and wk["holders"].get("lines"):
            ui.label("Holder lens (" + str(wk["holders"]["quarter"]) + "): " +
                     "; ".join(wk["holders"]["lines"][:3]) + " — " + wk["holders"]["note"] + ".") \
                .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:2px;")


def _render_peer_synthesis(s):
    """The Spec-14 capstone card: trading vs narrative vs fundamental peers, side by side."""
    if not s or s.get("error"):
        return
    tier_color = {"trading": "#0EA5E9", "narrative": "#7C3AED", "fundamental": "#B45309"}
    with ui.card().classes("w-full").style("border:1px solid #9AA6B8;margin-bottom:12px;padding:14px 16px;"):
        ui.label("PEER INTELLIGENCE — three definitions of “peer”") \
            .style("color:#0F172A;font-weight:800;font-size:var(--fs-sm);letter-spacing:.04em;")
        ui.label(s.get("headline", "")).style(f"color:{COLORS['text_body']};font-size:var(--fs-base);font-style:italic;margin-bottom:6px;")
        with ui.row().classes("w-full").style("gap:12px;flex-wrap:wrap;"):
            for t in s["tiers"]:
                c = tier_color.get(t["key"], "#64748B")
                with ui.column().style(f"flex:1;min-width:200px;border-top:3px solid {c};padding-top:6px;gap:2px;"):
                    ui.label(t["label"]).style(f"color:{c};font-weight:800;font-size:var(--fs-sm);")
                    ui.label(t["subtitle"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    with ui.row().style("flex-wrap:wrap;gap:4px;margin:4px 0;"):
                        for m in t["members"]:
                            ui.label(m).style(f"background:{c}18;color:{c};border-radius:4px;padding:1px 7px;font-size:var(--fs-xs);font-weight:600;")
                        if not t["members"]:
                            ui.label("—").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    ui.label(t["note"]).style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);line-height:1.4;")
        for i in s["insights"]:
            ui.label("• " + i).style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);margin-top:2px;")


def _lh_ready(client_id, ticker):
    """Lighthouse renders live for USIO (first deployment) and for illustrative demo tenants (which
    seed a synthetic OHLCV history + engine run). Other tenants get the graceful 'not loaded' notice."""
    if ticker == "USIO":
        return True
    try:
        from core.curated_targets import _is_illustrative
        return _is_illustrative(client_id)
    except Exception:
        return False


def _shadow_tickers_for(ticker):
    """Ticker set the attribution model runs over — issuer + comps + factor/benchmark ETFs."""
    if ticker == "USIO":
        from lighthouse.shadow import SHADOW_TICKERS
        return SHADOW_TICKERS
    from lighthouse.factors import FACTOR_ETFS
    from lighthouse.weekly import BENCHMARK_TICKERS
    from config.client_config import CP
    etfs = sorted(set(FACTOR_ETFS) | set(BENCHMARK_TICKERS))
    return [ticker] + [p["ticker"] for p in CP()] + etfs


def render_lighthouse_page():
    client_id = get_active_client_id()
    ticker = CT("ticker")
    from page_modules_nicegui.signals import capability_banner
    ui.label("Lighthouse").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
    capability_banner(
        "Why your stock moved — with the evidence",
        f"Point-in-time attribution for {ticker} to real, disclosed drivers — filings, peers, "
        "market factors — never an invented narrative.",
        tag="Stock-move attribution")
    ui.element("div").style("height:8px;")

    if _lh_ready(client_id, ticker):
        try:                                            # this render is itself a usage signal — log it
            from lighthouse import telemetry as _tel
            _tel.record_view(client_id, ticker, "lighthouse_page")
        except Exception:
            pass

        # Lead with the ANSWER, not the instrumentation: this slot sits at the top of the page but
        # is populated further down (once the engine has computed the verdicts + weekly context), so
        # "why is it moving" renders above the shadow-mode / test / calibration diagnostics below.
        _answer_slot = ui.column().classes("w-full").style("gap:8px;")
        try:
            from lighthouse import shadow as _shadow
            st = _shadow.shadow_status(client_id, ticker)
            with ui.row().classes("items-center gap-2").style("margin-bottom:8px;"):
                ui.label("● SHADOW MODE").style("color:#B45309;font-weight:800;font-size:var(--fs-xs);"
                    "border:1px solid #B4530955;border-radius:999px;padding:2px 10px;background:#B4530911;")
                ui.label(f"{st['logged']} sessions logged {st['since'] or ''}..{st['latest'] or ''} · "
                         f"{st['pct_high_abnormality']*100:.0f}% high-abnormality · {st['pct_explained']*100:.0f}% explained · "
                         f"IR review — no automated executive alerts yet.").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        except Exception:
            pass

        # In-app "send test digest" — verifies the email setup from the BROWSER (no Shell/terminal, no
        # paste), showing the delivery result or the exact SMTP error on screen. Forces a send (bypasses
        # the enabled/tier gates) since it's an explicit operator test.
        def _send_test_digest():
            try:
                from lighthouse import digest as _dg
                c = _dg.config()
                if not c["email_to"]:
                    ui.notify("No recipient set — add LIGHTHOUSE_DIGEST_TO in Render → Environment, then save.",
                              type="warning", timeout=15000)
                    return
                rep = _dg.dispatch(_dg.compute_latest_verdict(), dry_run=False, force=True)
                em = rep.get("email") or {}
                if em.get("ok"):
                    ui.notify("✅ Digest emailed to " + ", ".join(em.get("sent_to") or c["email_to"]),
                              type="positive", timeout=12000)
                elif str(em.get("reason", "")).startswith("email_not_configured"):
                    ui.notify("Email not configured — set the LIGHTHOUSE_SMTP_USER / _PASSWORD (and _HOST) "
                              "vars in Render → Environment, save, and try again.", type="warning", timeout=18000)
                else:
                    ui.notify("❌ Send failed — " + str(em.get("reason") or "no email attempted"),
                              type="negative", timeout=25000)
            except Exception as e:
                ui.notify(f"Error: {e}", type="negative", timeout=15000)

        # Operator delivery/test controls — tucked into a collapsed expander so they don't lead the
        # CEO-facing "why did my stock move" answer (which renders above via _answer_slot).
        with ui.expansion("Alert & delivery setup — send a test digest, enable phone alerts",
                          icon="settings", value=False).classes("w-full").style("margin-bottom:8px;"):
            with ui.row().classes("items-center gap-2").style("margin-bottom:8px;"):
                ui.button("✉ Send test digest email", icon="mail", on_click=_send_test_digest) \
                    .props("outline size=sm color=primary")
                ui.label("sends the daily digest to your configured address and shows the result here — "
                         "no terminal needed").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
            # Opt in to native-style phone alerts (Web Push). Raw HTML so the permission prompt fires
            # inside a real click; on iOS this works only in the installed PWA. The test-push button beside
            # it sends a real notification on demand — so delivery can be proven without waiting for a
            # Critical market day.
            with ui.row().classes("items-center gap-2").style("margin-bottom:8px;"):
                ui.html(f'<button onclick="window.irconnectSubscribePush(\'{client_id}\')" '
                        'style="display:inline-flex;align-items:center;gap:6px;background:#1E40AF;color:#fff;'
                        'border:0;border-radius:8px;padding:6px 12px;font:600 12px -apple-system,Segoe UI,Roboto,'
                        'sans-serif;cursor:pointer;">🔔 Enable phone alerts</button>')

                def _send_test_push():
                    try:
                        import os
                        from lighthouse import push
                        rep = push.send_to_client(
                            client_id, f"{ticker} — test alert",
                            "Phone alerts are working. This is a Lighthouse test push.",
                            url=(os.environ.get("LIGHTHOUSE_APP_URL", "") or "/"), tag="lh-test")
                        if rep.get("sent"):
                            ui.notify(f"Test push sent to {rep['sent']} device(s).", type="positive")
                        elif rep.get("total") == 0:
                            ui.notify("No subscribed devices yet — tap Enable phone alerts on your phone first.",
                                      type="warning")
                        else:
                            ui.notify("Couldn't deliver — the subscription may be stale; re-enable on your phone.",
                                      type="warning")
                    except Exception:
                        ui.notify("Test push failed — see server log.", type="negative")

                ui.button("Send test push", on_click=_send_test_push).props("flat dense size=sm")

        try:                                            # used-vs-ignored readout (measure, don't hope)
            from lighthouse import telemetry as _tel
            eng = _tel.summary(client_id, ticker, days=30)
            if eng["app_views"] or eng["emails_sent"]:
                bits = [f"{eng['app_views']} page view(s)"]
                if eng["emails_sent"]:
                    orate = f" ({eng['open_rate']*100:.0f}% open)" if eng["open_rate"] is not None else ""
                    bits.append(f"{eng['emails_opened']}/{eng['emails_sent']} digest(s) opened{orate}")
                if eng["clicks"]:
                    bits.append(f"{eng['clicks']} click-through(s)")
                if eng["last_engaged"]:
                    bits.append(f"last engaged {eng['last_engaged']}")
                ui.label("Engagement (30d): " + " · ".join(bits)) \
                    .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-bottom:8px;")
        except Exception:
            pass
        try:                                            # live calibration (cached; scheduler-refreshed)
            from lighthouse import calibration as _cal
            cc = _cal.load_cache(client_id)
            if cc and not cc.get("error"):
                with ui.expansion("Model calibration — is 'abnormal' actually informative?", icon="verified") \
                        .classes("w-full").style("margin-bottom:8px;"):
                    ui.label(f"{cc['days']} sessions · FDR alerts ~{cc.get('fdr_per_year', 0):.0f}/yr, "
                             f"{(cc.get('fdr_precision') or 0)*100:.0f}% with an identifiable catalyst · "
                             f"top-decile move recall {(cc.get('big_move_recall') or 0)*100:.0f}%") \
                        .style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                    for t in cc.get("reliability", []):
                        if not t.get("n"):
                            continue
                        er = f"{t['event_rate']*100:.0f}% w/ catalyst" if t.get("event_rate") is not None else "—"
                        ps = f"{t['persist_rate']*100:.0f}% persist" if t.get("persist_rate") is not None else "—"
                        ui.label(f"{t['bin']}: n={t['n']} · {er} · {ps}") \
                            .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        except Exception:
            pass
        # The "market-revealed peers" diagnostics (co-ownership / co-movement / sell-side coverage
        # overlap) need a real holder + coverage graph to be meaningful; on the illustrative demo they
        # compute ~0% and are hardcoded to USIO, so skip them — the core verdict + weekly context is
        # the showcase.
        from core.curated_targets import _is_illustrative as _isillus_lh
        _show_mrp = not _isillus_lh(client_id)
        try:                                            # Spec-14 capstone: the three-peer synthesis card
            if _show_mrp:
                from lighthouse import peer_synthesis as _ps
                _render_peer_synthesis(_ps.load_and_synthesize(client_id))
        except Exception:
            pass
        try:                                            # market-revealed peers via co-ownership (cached)
            from lighthouse import coownership as _co
            co = _co.load_cache(client_id)
            if _show_mrp and co and not co.get("error"):
                with ui.expansion("Market-revealed peers — who owns USIO also owns…", icon="hub") \
                        .classes("w-full").style("margin-bottom:8px;"):
                    ui.label(f"{co['n_holders']} holders · {co['n_focused']} focused/fundamental · "
                             f"{co['n_mechanical']} quant/passive ({co.get('quarter','')})") \
                        .style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                    if not co.get("peers"):
                        ui.label("No concentrated active holders with clear co-holdings — owned via broad/"
                                 "quant/wealth vehicles, i.e. USIO trades on small-cap FLOW, not a peer complex.") \
                            .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    else:
                        ui.label("Co-held by USIO's concentrated active managers — note these are NOT the "
                                 "payments peers we defined:").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                        for p in co["peers"][:8]:
                            ui.label(f"{p['issuer']} · held by {p['holders']} · avg wt {p['avg_weight']*100:.1f}%") \
                                .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        except Exception:
            pass
        try:                                            # market-revealed peers via co-movement (cached)
            from lighthouse import comovement as _cm
            cm = _cm.load_cache(client_id)
            if _show_mrp and cm and not cm.get("error"):
                with ui.expansion("Market-revealed peers — who USIO actually co-moves with", icon="insights") \
                        .classes("w-full").style("margin-bottom:8px;"):
                    ui.label("Top daily-return co-movers (broad universe):") \
                        .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    for t in cm.get("top_correlates", [])[:6]:
                        tag = " · our peer" if t["defined_peer"] else ""
                        ui.label(f"{t['ticker']} {t['corr']:+.2f} · {t['category']}{tag}") \
                            .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    ui.label(f"Data-selected explainers: {', '.join(p['name'] for p in cm.get('sparse', [])) or '—'} · "
                             f"revealed R² {cm.get('sparse_r2', 0):.2f} vs our-peers R² {(cm.get('defined_basket_r2') or 0):.2f}") \
                        .style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);margin-top:4px;")
                    ui.label("Read: USIO co-moves with the small-cap complex / fintech, not the payments "
                             "peers we defined — it trades as small-cap flow.") \
                        .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;")
        except Exception:
            pass
        try:                                            # sell-side coverage-overlap peers (cached)
            from lighthouse import coverage as _cov
            cvg = _cov.load_cache(client_id)
            if _show_mrp and cvg and not cvg.get("error"):
                with ui.expansion("Market-revealed peers — who the sell-side brackets USIO with", icon="menu_book") \
                        .classes("w-full").style("margin-bottom:8px;"):
                    ui.label(f"{cvg['n_analysts']} covering analysts · {cvg['n_specialists']} payments specialist(s). "
                             "This is the NARRATIVE peer group (whose upgrade lands in the same inboxes), distinct "
                             "from the trading peers above.").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                    for p in cvg.get("payments_coverage_peers", [])[:6]:
                        tag = "our peer" if p["defined_peer"] else "NEW"
                        ui.label(f"{p['ticker']} · {p['name']} · {p['sector']} [{tag}]") \
                            .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
                    if cvg.get("new_payments_peers"):
                        ui.label(f"Payments peers the sell-side brackets that we DIDN'T define: "
                                 f"{', '.join(cvg['new_payments_peers'])}") \
                            .style(f"color:{COLORS['text_body']};font-size:var(--fs-xs);margin-top:3px;")
                    if cvg.get("defined_not_covered"):
                        ui.label(f"Our defined peers USIO's analysts don't cover: "
                                 f"{', '.join(cvg['defined_not_covered'])}") \
                            .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);")
        except Exception:
            pass

    if not _lh_ready(client_id, ticker):
        with ui.card().classes("w-full").style("background:#EEF2F7;border:1px solid #9AA6B8;"):
            ui.label("Lighthouse is wired for USIO in this MVP.").classes("font-bold")
            ui.label(f"A new client is a config file + a historical data load — {ticker} isn't loaded yet.") \
                .style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
        return

    try:
        from lighthouse import data, ceo
        from lighthouse.factor_model import attribution
        import psycopg2
        from core.security import get_database_url
        rets = data.returns_frame(_shadow_tickers_for(ticker))
        model = attribution(rets, issuer=ticker, window=126)
        rows = list(model.iterrows())[-4:][::-1]
        conn = psycopg2.connect(get_database_url())          # one shared connection for all cards
        verdicts = [ceo.build_verdict(client_id, ticker, d, m, conn=conn) for d, m in rows]
        from lighthouse import weekly as _weekly
        wk = _weekly.weekly_digest(model, ticker, conn=conn)
        _weekly.save_context_cache(client_id, ticker, wk)   # keep the Today-page mirror fresh
        conn.close()
    except Exception as e:
        ui.label(f"Lighthouse engine error: {e}").style("color:#B91C1C;")
        return

    # ── THIS WEEK IN CONTEXT + recent-session verdicts — the ANSWER. Rendered into _answer_slot so
    # it appears at the TOP of the page (above the shadow-mode / test / calibration diagnostics),
    # even though the engine that computes it only finishes here.
    with _answer_slot:
        # A drift number in isolation is uninterpretable, so it never travels alone: the issuer's
        # weekly move sits beside the peer basket, its size index, and the broad-market indices.
        if wk and not wk.get("empty"):
            _render_week_in_context(wk, _weekly, ticker)

        ui.label("Recent sessions").classes("font-bold").style(f"color:{COLORS['text_heading']};margin:4px 0;")
        for v in verdicts:
            day = v["day"]
            up = v["actual"] >= 0
            move_color = "#15803D" if up else "#B91C1C"
            with ui.card().classes("w-full").style("border:1px solid #9AA6B8;margin-bottom:6px;"):
                with ui.row().classes("items-center w-full justify-between"):
                    with ui.row().classes("items-baseline gap-3"):
                        ui.label(str(day)).classes("font-bold").style(f"color:{COLORS['text_heading']};")
                        ui.label(f"{v['actual']*100:+.1f}%").style(f"color:{move_color};font-size:var(--fs-3xl);font-weight:800;")
                        ui.label(f"vs expected {v['expected']*100:+.1f}%").style(f"color:{COLORS['text_muted']};font-size:var(--fs-sm);")
                    with ui.row().classes("gap-2"):
                        _conf_badge("Abnormality", v["abnormality_conf"])
                        _conf_badge("Explanation", v["explanation_conf"])
                best = v["drivers"][0]["label"] if v["explanation_conf"] != "LOW" else "No confirmed cause identified"
                ui.label(f"Unexplained residual {v['residual']*100:+.1f}%  ·  {int((v['rarity'] or 0)*100)}th-pctile rare  ·  best read: {best}") \
                    .style(f"color:{COLORS['text_body']};font-size:var(--fs-base);margin-top:2px;")
                if v.get("z") is not None:
                    _fdr = ""
                    if v.get("fdr_significant") is not None:
                        _fdr = ("  ·  FDR: PASSES (genuine discovery)" if v["fdr_significant"]
                                else f"  ·  FDR: gated (q={int((v.get('fdr_q') or 0.1)*100)}% — expected tail-noise, no phone alert)")
                    _vol = "GARCH(1,1)" if v.get("cond_vol_model") == "garch" else "EWMA"
                    ui.label(f"{int(v.get('n_factors') or 0)}-factor risk model · R² {(v.get('r2') or 0)*100:.0f}% · "
                             f"residual {v['z']:+.1f}σ (t {v.get('t_stat') or 0:+.1f}), {_vol} vol-adjusted{_fdr}") \
                        .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:1px;")
                    if v.get("rvol") is not None:
                        _liq = (f"⚠ on {v['rvol']:.1f}× 20-day volume — thin; possible microstructure, no phone alert"
                                if v.get("thin_tape") else f"on {v['rvol']:.1f}× 20-day volume — tape supports the move")
                        ui.label(f"Liquidity: {_liq}").style(
                            f"color:{'#B45309' if v.get('thin_tape') else COLORS['text_muted']};font-size:var(--fs-xs);")
                with ui.column().classes("gap-1").style("margin-top:6px;"):
                    for d in v["drivers"]:
                        c = _ROLE_COLOR.get(d["cls"], "#64748B")
                        with ui.row().classes("items-center gap-2"):
                            ui.label(d["cls"].title()).style(f"color:{c};font-weight:700;font-size:var(--fs-xs);"
                                                             f"border:1px solid {c}55;border-radius:4px;padding:0 6px;")
                            ui.label(f"{d['label']} — {d['detail']}").style(f"color:{COLORS['text_body']};font-size:var(--fs-sm);")
                            if d.get("link"):
                                ui.link("evidence ↗", d["link"], new_tab=True).style("font-size:var(--fs-xs);")
                if v.get("technical"):
                    ui.label(f"Technical (how, not why): {v['technical']}").style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);margin-top:4px;")
                if v["not_found"]:
                    ui.label("Checked but not found: " + " · ".join(v["not_found"])) \
                        .style(f"color:{COLORS['text_muted']};font-size:var(--fs-xs);font-style:italic;margin-top:2px;")
