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


def render_lighthouse_page():
    client_id = get_active_client_id()
    ticker = CT("ticker")
    ui.label("Lighthouse").classes("text-2xl font-bold").style(f"color:{COLORS['text_heading']};")
    ui.label(f"Why is {ticker} moving? — evidence-based attribution, point-in-time, no invented causes.") \
        .style(f"color:{COLORS['text_muted']};margin-bottom:8px;")

    if ticker != "USIO":
        with ui.card().classes("w-full").style("background:#EEF2F7;border:1px solid #D3DBE4;"):
            ui.label(f"Lighthouse is wired for USIO in this MVP.").classes("font-bold")
            ui.label(f"A new client is a config file + a historical data load — {ticker} isn't loaded yet.") \
                .style(f"color:{COLORS['text_muted']};font-size:12px;")
        return

    try:
        from lighthouse import data, ceo
        from lighthouse.attribution import market_peer_model
        from lighthouse.config.usio import USIO
        import psycopg2
        from core.security import get_database_url
        rets = data.returns_frame(["USIO", "IWM"] + USIO["business_peers"])
        model = market_peer_model(rets, issuer="USIO", market="IWM", peers=USIO["business_peers"], window=126)
        rows = list(model.iterrows())[-4:][::-1]
        conn = psycopg2.connect(get_database_url())          # one shared connection for all cards
        verdicts = [ceo.build_verdict(client_id, ticker, d, m, conn=conn) for d, m in rows]
        conn.close()
    except Exception as e:
        ui.label(f"Lighthouse engine error: {e}").style("color:#B91C1C;")
        return

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
