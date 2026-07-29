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
        ui.label(label).style(f"color:{COLORS['text_muted']};font-size:11px;")
        ui.label(value).style(f"color:{color};font-weight:700;font-size:11px;")


def _bar_row(label, note, value, scale, *, is_issuer=False, is_comp=False, rel=None):
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
            ui.label(label).style(f"color:{lab_color};font-weight:{weight};font-size:12px;text-align:right;")
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
            rel_txt = f"  ·  USIO {rel*100:+.1f} pts"
        with ui.row().classes("items-baseline").style("width:150px;gap:0;flex:none;"):
            ui.label(val).style(f"color:{color};font-weight:{weight};font-size:12px;")
            if rel is not None:
                ui.label(rel_txt).style(f"color:{(red if rel < 0 else green)};font-size:11px;")
    if note:
        pass


def _render_week_in_context(wk, _weekly):
    drift_color = "#B91C1C" if wk["resid_sum"] < 0 else "#15803D"
    ctx = wk.get("context") or []
    scale = max([abs(wk["car_actual"])] + [abs(c["ret"]) for c in ctx] + [0.005])
    with ui.card().classes("w-full").style("border:1px solid #B4530955;background:#FFFDF7;margin-bottom:12px;padding:14px 16px;"):
        with ui.row().classes("items-center w-full justify-between"):
            ui.label(f"THIS WEEK IN CONTEXT · {wk['week']}").style("color:#B45309;font-weight:800;font-size:11px;letter-spacing:.04em;")
            ui.label(f"{_weekly.ordinal(wk['weekly_rarity']*100)}-percentile week") \
                .style(f"color:{COLORS['text_muted']};font-size:11px;")
        # punchline sentence — the number never appears without its comparison
        if wk.get("context_read"):
            ui.label(f"USIO {wk['context_read']}").style(f"color:{COLORS['text_heading']};font-size:14px;font-weight:600;margin:6px 0 2px;")
        # the shared-axis comparison
        with ui.column().classes("w-full").style("gap:0;margin:8px 0 4px;"):
            _bar_row("USIO", "", wk["car_actual"], scale, is_issuer=True)
            for c in ctx:
                _bar_row(c["label"], c["note"], c["ret"], scale, is_comp=c["relevant"], rel=c["rel"])
        ui.label("● comp = the peer basket & size index the attribution model uses · lighter bars are broad-market reference") \
            .style(f"color:{COLORS['text_muted']};font-size:10px;margin-top:2px;")
        # the drift + honest read
        ui.element("div").style("height:1px;background:#E2E8F0;margin:8px 0;")
        with ui.row().classes("items-baseline gap-2"):
            ui.label("After stripping market & peer moves:").style(f"color:{COLORS['text_muted']};font-size:12px;")
            ui.label(f"{wk['resid_sum']*100:+.1f}% unexplained drift").style(f"color:{drift_color};font-size:15px;font-weight:800;")
            ui.label(f"· {wk['abnormal_days']} abnormal day(s) of {wk['trading_days']}").style(f"color:{COLORS['text_muted']};font-size:12px;")
        ui.label(f"Read: {wk['driver']}").style(f"color:{COLORS['text_body']};font-size:12px;font-style:italic;margin-top:2px;")
        if wk.get("holders") and wk["holders"].get("lines"):
            ui.label("Holder lens (" + str(wk["holders"]["quarter"]) + "): " +
                     "; ".join(wk["holders"]["lines"][:3]) + " — " + wk["holders"]["note"] + ".") \
                .style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:2px;")


def render_lighthouse_page():
    client_id = get_active_client_id()
    ticker = CT("ticker")
    ui.label("Lighthouse").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
    ui.label(f"Why is {ticker} moving? — evidence-based attribution, point-in-time, no invented causes.") \
        .style(f"color:{COLORS['text_muted']};margin-bottom:8px;")

    if ticker == "USIO":
        try:                                            # this render is itself a usage signal — log it
            from lighthouse import telemetry as _tel
            _tel.record_view(client_id, "USIO", "lighthouse_page")
        except Exception:
            pass
        try:
            from lighthouse import shadow as _shadow
            st = _shadow.shadow_status("usio", "USIO")
            with ui.row().classes("items-center gap-2").style("margin-bottom:8px;"):
                ui.label("● SHADOW MODE").style("color:#B45309;font-weight:800;font-size:11px;"
                    "border:1px solid #B4530955;border-radius:999px;padding:2px 10px;background:#B4530911;")
                ui.label(f"{st['logged']} sessions logged {st['since'] or ''}..{st['latest'] or ''} · "
                         f"{st['pct_high_abnormality']*100:.0f}% high-abnormality · {st['pct_explained']*100:.0f}% explained · "
                         f"IR review — no automated executive alerts yet.").style(f"color:{COLORS['text_muted']};font-size:11px;")
        except Exception:
            pass
        # Opt in to native-style phone alerts (Web Push). Raw HTML so the permission prompt fires
        # inside a real click; on iOS this works only in the installed PWA. The test-push button beside
        # it sends a real notification on demand — so delivery can be proven without waiting for a
        # Critical market day.
        with ui.row().classes("items-center gap-2").style("margin-bottom:8px;"):
            ui.html('<button onclick="window.irconnectSubscribePush(\'usio\')" '
                    'style="display:inline-flex;align-items:center;gap:6px;background:#1E40AF;color:#fff;'
                    'border:0;border-radius:8px;padding:6px 12px;font:600 12px -apple-system,Segoe UI,Roboto,'
                    'sans-serif;cursor:pointer;">🔔 Enable phone alerts</button>')

            def _send_test_push():
                try:
                    import os
                    from lighthouse import push
                    rep = push.send_to_client(
                        "usio", "USIO — test alert",
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
            eng = _tel.summary(client_id, "USIO", days=30)
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
                    .style(f"color:{COLORS['text_muted']};font-size:11px;margin-bottom:8px;")
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
                        .style(f"color:{COLORS['text_body']};font-size:12px;")
                    for t in cc.get("reliability", []):
                        if not t.get("n"):
                            continue
                        er = f"{t['event_rate']*100:.0f}% w/ catalyst" if t.get("event_rate") is not None else "—"
                        ps = f"{t['persist_rate']*100:.0f}% persist" if t.get("persist_rate") is not None else "—"
                        ui.label(f"{t['bin']}: n={t['n']} · {er} · {ps}") \
                            .style(f"color:{COLORS['text_muted']};font-size:11px;")
        except Exception:
            pass
        try:                                            # market-revealed peers via co-ownership (cached)
            from lighthouse import coownership as _co
            co = _co.load_cache(client_id)
            if co and not co.get("error"):
                with ui.expansion("Market-revealed peers — who owns USIO also owns…", icon="hub") \
                        .classes("w-full").style("margin-bottom:8px;"):
                    ui.label(f"{co['n_holders']} holders · {co['n_focused']} focused/fundamental · "
                             f"{co['n_mechanical']} quant/passive ({co.get('quarter','')})") \
                        .style(f"color:{COLORS['text_body']};font-size:12px;")
                    if not co.get("peers"):
                        ui.label("No concentrated active holders with clear co-holdings — owned via broad/"
                                 "quant/wealth vehicles, i.e. USIO trades on small-cap FLOW, not a peer complex.") \
                            .style(f"color:{COLORS['text_muted']};font-size:11px;")
                    else:
                        ui.label("Co-held by USIO's concentrated active managers — note these are NOT the "
                                 "payments peers we defined:").style(f"color:{COLORS['text_muted']};font-size:11px;")
                        for p in co["peers"][:8]:
                            ui.label(f"{p['issuer']} · held by {p['holders']} · avg wt {p['avg_weight']*100:.1f}%") \
                                .style(f"color:{COLORS['text_muted']};font-size:11px;")
        except Exception:
            pass
        try:                                            # market-revealed peers via co-movement (cached)
            from lighthouse import comovement as _cm
            cm = _cm.load_cache(client_id)
            if cm and not cm.get("error"):
                with ui.expansion("Market-revealed peers — who USIO actually co-moves with", icon="insights") \
                        .classes("w-full").style("margin-bottom:8px;"):
                    ui.label("Top daily-return co-movers (broad universe):") \
                        .style(f"color:{COLORS['text_muted']};font-size:11px;")
                    for t in cm.get("top_correlates", [])[:6]:
                        tag = " · our peer" if t["defined_peer"] else ""
                        ui.label(f"{t['ticker']} {t['corr']:+.2f} · {t['category']}{tag}") \
                            .style(f"color:{COLORS['text_muted']};font-size:11px;")
                    ui.label(f"Data-selected explainers: {', '.join(p['name'] for p in cm.get('sparse', [])) or '—'} · "
                             f"revealed R² {cm.get('sparse_r2', 0):.2f} vs our-peers R² {(cm.get('defined_basket_r2') or 0):.2f}") \
                        .style(f"color:{COLORS['text_body']};font-size:12px;margin-top:4px;")
                    ui.label("Read: USIO co-moves with the small-cap complex / fintech, not the payments "
                             "peers we defined — it trades as small-cap flow.") \
                        .style(f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;")
        except Exception:
            pass

    if ticker != "USIO":
        with ui.card().classes("w-full").style("background:#EEF2F7;border:1px solid #D3DBE4;"):
            ui.label(f"Lighthouse is wired for USIO in this MVP.").classes("font-bold")
            ui.label(f"A new client is a config file + a historical data load — {ticker} isn't loaded yet.") \
                .style(f"color:{COLORS['text_muted']};font-size:12px;")
        return

    try:
        from lighthouse import data, ceo
        from lighthouse.factor_model import attribution
        from lighthouse.shadow import SHADOW_TICKERS
        import psycopg2
        from core.security import get_database_url
        rets = data.returns_frame(SHADOW_TICKERS)
        model = attribution(rets, issuer="USIO", window=126)
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

    # ── THIS WEEK IN CONTEXT — the headline band. A drift number in isolation is uninterpretable, so
    # it never travels alone here: the issuer's weekly move sits beside the peer basket, its size
    # index, and the broad-market indices, each with USIO's relative performance in points.
    if wk and not wk.get("empty"):
        _render_week_in_context(wk, _weekly)

    ui.label("Recent sessions").classes("font-bold").style(f"color:{COLORS['text_heading']};margin:4px 0;")
    for v in verdicts:
        day = v["day"]
        up = v["actual"] >= 0
        move_color = "#15803D" if up else "#B91C1C"
        with ui.card().classes("w-full").style("border:1px solid #D3DBE4;margin-bottom:6px;"):
            with ui.row().classes("items-center w-full justify-between"):
                with ui.row().classes("items-baseline gap-3"):
                    ui.label(str(day)).classes("font-bold").style(f"color:{COLORS['text_heading']};")
                    ui.label(f"{v['actual']*100:+.1f}%").style(f"color:{move_color};font-size:22px;font-weight:800;")
                    ui.label(f"vs expected {v['expected']*100:+.1f}%").style(f"color:{COLORS['text_muted']};font-size:12px;")
                with ui.row().classes("gap-2"):
                    _conf_badge("Abnormality", v["abnormality_conf"])
                    _conf_badge("Explanation", v["explanation_conf"])
            best = v["drivers"][0]["label"] if v["explanation_conf"] != "LOW" else "No confirmed cause identified"
            ui.label(f"Unexplained residual {v['residual']*100:+.1f}%  ·  {int((v['rarity'] or 0)*100)}th-pctile rare  ·  best read: {best}") \
                .style(f"color:{COLORS['text_body']};font-size:13px;margin-top:2px;")
            if v.get("z") is not None:
                _fdr = ""
                if v.get("fdr_significant") is not None:
                    _fdr = ("  ·  FDR: PASSES (genuine discovery)" if v["fdr_significant"]
                            else f"  ·  FDR: gated (q={int((v.get('fdr_q') or 0.1)*100)}% — expected tail-noise, no phone alert)")
                ui.label(f"{int(v.get('n_factors') or 0)}-factor risk model · R² {(v.get('r2') or 0)*100:.0f}% · "
                         f"residual {v['z']:+.1f}σ (t {v.get('t_stat') or 0:+.1f}), vol-regime-adjusted{_fdr}") \
                    .style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:1px;")
            with ui.column().classes("gap-1").style("margin-top:6px;"):
                for d in v["drivers"]:
                    c = _ROLE_COLOR.get(d["cls"], "#64748B")
                    with ui.row().classes("items-center gap-2"):
                        ui.label(d["cls"].title()).style(f"color:{c};font-weight:700;font-size:11px;"
                                                         f"border:1px solid {c}55;border-radius:4px;padding:0 6px;")
                        ui.label(f"{d['label']} — {d['detail']}").style(f"color:{COLORS['text_body']};font-size:12px;")
                        if d.get("link"):
                            ui.link("evidence ↗", d["link"], new_tab=True).style("font-size:11px;")
            if v.get("technical"):
                ui.label(f"Technical (how, not why): {v['technical']}").style(f"color:{COLORS['text_muted']};font-size:11px;margin-top:4px;")
            if v["not_found"]:
                ui.label("Checked but not found: " + " · ".join(v["not_found"])) \
                    .style(f"color:{COLORS['text_muted']};font-size:11px;font-style:italic;margin-top:2px;")
