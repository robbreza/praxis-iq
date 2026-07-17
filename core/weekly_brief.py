"""
core/weekly_brief.py — composes the Weekly IR Intelligence Brief.

Replaces the old one-line summary (a single sentence stored on a card, with no
document behind it and nothing to print) with a real, sectioned brief built
entirely from what's actually on file this week: live price/volume, the IR
activity log, the earnings + quiet-period calendar, the script workflow stage,
the investor pipeline, the NDR schedule, peer moves/filings, and ownership
events.

HOUSE RULE, same as the rest of the platform: never invent a figure. Every
source is read defensively — if a source is unavailable the brief says so
plainly ("stock price not yet fetched") rather than printing a placeholder
number. A section with nothing real to say is omitted entirely.

Shape returned by compose():
  { week_label, as_of, ticker, name,
    headline: str,                     # the one-liner the brief card shows
    stats:    [(value, label, sub)],   # market stat row
    sections: [ {title, lines: [str]} ] }
Both the Reports UI and report_pdf.weekly_brief_pdf() render from this, so the
screen and the PDF can never drift apart.
"""

from datetime import datetime

from config.client_config import CE, CT, get_active_client_id
from core import db

_STAGE_NAMES = [
    ("cfo_numbers", "CFO Numbers In"), ("ir_review", "IR Review"),
    ("exec_review", "CFO+CEO+CRO Review"), ("consolidate", "Consolidation"),
    ("legal_signoff", "Legal Sign-Off"),
]


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def script_stage():
    """Current earnings-script workflow stage, in plain words."""
    ss = _safe(lambda: db.load_json("script_workflow_state.json", None))
    if not (ss and ss.get("stages")):
        return "Script workflow not yet started"
    if ss.get("current_stage") == "FINAL":
        return "Earnings script FINALIZED"
    active = next((nm for sid, nm in _STAGE_NAMES
                   if ss["stages"].get(sid, {}).get("status") == "active"), None)
    return f"Script workflow at {active}" if active else "Script workflow not yet started"


def _market_section(ticker):
    from core import market_data
    snap = _safe(lambda: market_data.get_snapshot(ticker)) or {}
    stats, lines = [], []
    px = snap.get("last_price")
    if px is None:
        return stats, ["Stock price not yet fetched — run the market pull in Settings."]
    chg = snap.get("pct_change")
    sub = f"{chg:+.1f}% on the day" if chg is not None else "change unavailable"
    stats.append((f"${px:.2f}", "Last price", sub))
    lines.append(f"Closed at ${px:.2f}" + (f", {chg:+.1f}% on the day." if chg is not None else "."))

    vol, avg = snap.get("volume"), snap.get("avg_volume_10d")
    if vol and avg:
        ratio = vol / avg
        stats.append((f"{ratio:.1f}x", "Volume vs 10d avg", f"{vol:,.0f} vs {avg:,.0f}"))
        read = ("unusually heavy — worth knowing who traded" if ratio >= 2
                else "elevated" if ratio >= 1.3 else "normal" if ratio >= 0.7 else "light")
        lines.append(f"Volume {vol:,.0f} vs {avg:,.0f} 10-day average ({ratio:.1f}x) — {read}.")

    pt = _safe(lambda: __import__("core.risk_scorecard", fromlist=["x"])._consensus_pt_avg())
    if pt and px:
        upside = (pt - px) / px * 100
        stats.append((f"${pt:.2f}", "Consensus PT", f"{upside:+.0f}% upside"))
        lines.append(f"Consensus price target ${pt:.2f} — {upside:+.0f}% from here.")
    return stats, lines


def _activity_section():
    from core import activity_log
    n = _safe(lambda: activity_log.count_this_week(), 0) or 0
    lines = []
    if not n:
        return ["No IR actions logged this week."]
    lines.append(f"{n} IR action(s) logged this week.")
    bd = _safe(lambda: activity_log.breakdown_this_week(), None)
    if isinstance(bd, dict) and bd:
        parts = ", ".join(f"{k.replace('_',' ')} {v}" for k, v in sorted(bd.items(), key=lambda kv: -kv[1]) if v)
        if parts:
            lines.append(f"Breakdown: {parts}.")
    mins = _safe(lambda: activity_log.minutes_saved_this_week(), None)
    if mins:
        lines.append(f"Estimated {mins} minutes of manual work saved by automation this week.")
    return lines


def _earnings_section():
    e = CE() or {}
    lines = []
    today = datetime.now().date()
    ed = _safe(lambda: datetime.strptime(e["earnings_date"], "%Y-%m-%d").date())
    if ed:
        d = (ed - today).days
        when = f"in {d} days" if d > 0 else ("today" if d == 0 else f"{abs(d)} days ago")
        lines.append(f"{e.get('current_quarter','Next quarter')} earnings {when} — {ed:%b %d, %Y}"
                     + (f" at {e['call_time']}." if e.get("call_time") else "."))
    qs = _safe(lambda: datetime.strptime(e["quiet_start"], "%Y-%m-%d").date())
    qe = _safe(lambda: datetime.strptime(e["quiet_end"], "%Y-%m-%d").date())
    if qs and qe:
        if today < qs:
            lines.append(f"Quiet period opens {qs:%b %d} ({(qs-today).days} days) and lifts {qe:%b %d} — "
                         "outreach should land before it opens.")
        elif qs <= today <= qe:
            lines.append(f"IN QUIET PERIOD ({qs:%b %d}–{qe:%b %d}) — no substantive outreach until it lifts.")
        else:
            lines.append(f"Quiet period lifted {qe:%b %d} — free to engage.")
    lines.append(script_stage() + ".")
    return lines


def _pipeline_section(cid):
    lines = []
    pros = _safe(lambda: db.load_json("prospects.json", [], client_id=cid), []) or []
    if pros:
        rias = sum(1 for p in pros if p.get("touch") == "video-call")
        lines.append(f"{len(pros)} prospect(s) in the pipeline"
                     + (f" — {rias} on the video-call tier." if rias else "."))
    c = _safe(lambda: __import__("core.peer_prospects", fromlist=["x"]).counts(cid), None)
    if isinstance(c, dict):
        if c.get("candidates"):
            lines.append(f"{c['candidates']} peer-overlap candidate(s) awaiting qualification"
                         + (f", plus {c['rias']} RIA/wealth holders on the video-call tier." if c.get("rias") else "."))
        if c.get("promoted"):
            lines.append(f"{c['promoted']} promoted into the pipeline to date.")
    return lines


def _ndr_section(cid):
    trips = _safe(lambda: db.load_json("ndr_trips.json", [], client_id=cid), []) or []
    lines = []
    for t in trips:
        ms = t.get("meetings", []) or []
        if not ms:
            continue
        virt = sum(1 for m in ms if m.get("format", "In-person") != "In-person")
        lines.append(f"{t.get('name')} — {t.get('dates','date TBD')} · {len(ms)} meeting(s)"
                     + (f", {virt} virtual" if virt else "") + ".")
    return lines or ["No NDR trips with meetings scheduled."]


def _peer_section():
    lines = []
    mv = _safe(lambda: __import__("core.peer_watch", fromlist=["x"]).notable_movers(), None)
    if mv:
        for m in mv[:5]:
            tk = m.get("ticker") or m.get("symbol")
            pc = m.get("pct_change")
            if tk and pc is not None:
                lines.append(f"{tk} {pc:+.1f}% — a peer move worth a look.")
    fl = _safe(lambda: __import__("core.peer_watch", fromlist=["x"]).recent_filings(), None)
    if fl:
        for f in fl[:5]:
            tk = f.get("ticker") or ""
            form = f.get("form") or f.get("type") or "filing"
            when = f.get("date") or f.get("filed") or ""
            lines.append(f"{tk} filed {form} {when}.".strip())
    return lines


def _news_section():
    items = _safe(lambda: __import__("core.news_feed", fromlist=["x"]).recent(), None) or []
    out = []
    for n in items[:5]:
        t = (n.get("title") or "").strip()
        if t:
            out.append(f"{n.get('ticker','')} — {t}".strip(" —"))
    return out


def compose(client_id=None):
    cid = client_id or get_active_client_id()
    ticker, name = CT("ticker"), CT("name")
    now = datetime.now()

    stats, market_lines = _market_section(ticker)
    sections = []

    def add(title, lines):
        if lines:
            sections.append({"title": title, "lines": lines})

    add("Market", market_lines)
    add("Earnings & script workflow", _earnings_section())
    add("IR activity this week", _activity_section())
    add("Investor pipeline", _pipeline_section(cid))
    add("NDR schedule", _ndr_section(cid))
    add("Peer watch", _peer_section())
    add("Peer news (rolling 7 days)", _news_section())

    # The card headline — the same three facts the old one-liner carried.
    from core import activity_log, market_data
    snap = _safe(lambda: market_data.get_snapshot(ticker)) or {}
    px = snap.get("last_price")
    head = [f"${px:.2f} stock price" if px is not None else "stock price not yet fetched",
            f"{_safe(lambda: activity_log.count_this_week(), 0) or 0} IR action(s) logged this week",
            script_stage()]

    return {
        "week_label": f"Week of {now:%b %d, %Y}",
        "as_of": now, "ticker": ticker, "name": name,
        "headline": " · ".join(head),
        "stats": stats,
        "sections": sections,
    }
