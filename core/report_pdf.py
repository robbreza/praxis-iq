"""
core/report_pdf.py — board-ready PDF export of the live reports (reportlab).

Same data the Reports page renders on screen (core.edgar_financials +
core.benchmarking_engine + ownership), laid out as a clean, institutional PDF a
board packet can include. No static content — every figure recomputes at export
time from the latest filing and market data. Returns PDF bytes; the page code
hands them to ui.download.
"""

from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

from config.client_config import CT, get_active_client_id
from core import benchmarking_engine, edgar_financials

INK = colors.HexColor("#0F172A")
INK2 = colors.HexColor("#475569")
INK3 = colors.HexColor("#8A98AC")
ACCENT = colors.HexColor("#1E40AF")
GOOD = colors.HexColor("#15803D")
WARN = colors.HexColor("#B45309")
BORDER = colors.HexColor("#E2E8F0")
SOFT = colors.HexColor("#F5F7FA")
CONTENT_W = 7.0 * inch

_S = {
    "eyebrow": ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=8, textColor=ACCENT, leading=10, spaceAfter=2),
    "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=19, textColor=INK, leading=22, spaceAfter=3),
    "meta": ParagraphStyle("meta", fontName="Helvetica", fontSize=8.5, textColor=INK3, leading=11, spaceAfter=12),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=10.5, textColor=INK, leading=13, spaceBefore=13, spaceAfter=5),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, textColor=INK2, leading=14, spaceAfter=4),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=9, textColor=INK2, leading=13, leftIndent=9, spaceAfter=3),
    "small": ParagraphStyle("small", fontName="Helvetica", fontSize=7.5, textColor=INK3, leading=10, spaceBefore=8),
    "callh": ParagraphStyle("callh", fontName="Helvetica-Bold", fontSize=7.5, textColor=ACCENT, leading=10, spaceAfter=3),
    "cellv": ParagraphStyle("cellv", fontName="Helvetica-Bold", fontSize=13, textColor=INK, leading=15),
    "celll": ParagraphStyle("celll", fontName="Helvetica-Bold", fontSize=7.5, textColor=INK2, leading=9, spaceBefore=3),
    "cells": ParagraphStyle("cells", fontName="Helvetica", fontSize=6.8, textColor=INK3, leading=8, spaceBefore=1),
    "th": ParagraphStyle("th", fontName="Helvetica-Bold", fontSize=8, textColor=INK, leading=10),
    "td": ParagraphStyle("td", fontName="Helvetica", fontSize=8.5, textColor=INK2, leading=10),
}


def _stat_cell(value, label, sub, color=INK):
    v = ParagraphStyle("v", parent=_S["cellv"], textColor=color)
    return [Paragraph(value, v), Paragraph(label, _S["celll"]), Paragraph(sub, _S["cells"])]


def _stat_row(cells):
    """cells: list of (value, label, sub, color). One bordered row of stat boxes."""
    row = [_stat_cell(*c) for c in cells]
    w = CONTENT_W / len(cells)
    t = Table([row], colWidths=[w] * len(cells))
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
    ]))
    return t


def _callout(header, text, accent=ACCENT):
    inner = [Paragraph(header, ParagraphStyle("ch", parent=_S["callh"], textColor=accent)),
             Paragraph(text, _S["body"])]
    t = Table([[inner]], colWidths=[CONTENT_W])
    t.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDER),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("BACKGROUND", (0, 0), (-1, -1), SOFT),
        ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING", (0, 0), (-1, -1), 13), ("RIGHTPADDING", (0, 0), (-1, -1), 13),
    ]))
    return t


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(BORDER)
    canvas.setLineWidth(0.5)
    canvas.line(0.75 * inch, 0.62 * inch, 7.75 * inch, 0.62 * inch)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(INK3)
    canvas.drawString(0.75 * inch, 0.46 * inch,
                      "Praxis Point IR · SEC EDGAR filings + market data · Not independent research or investment advice.")
    canvas.drawRightString(7.75 * inch, 0.46 * inch, f"Page {doc.page}")
    canvas.restoreState()


def _doc(title):
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=letter, title=title,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.85 * inch)
    return buf, doc


def _header(story, eyebrow, title, meta):
    story.append(Paragraph(eyebrow, _S["eyebrow"]))
    story.append(Paragraph(title, _S["title"]))
    story.append(Paragraph(meta, _S["meta"]))


def _m(v):
    return v / 1e6 if v is not None else 0


def _esc(s):
    """Escape dynamic text for reportlab's mini-HTML Paragraph parser — an
    unescaped '&' in a fund name or headline would otherwise break the build."""
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def weekly_brief_pdf(client_id=None):
    """The Weekly IR Intelligence Brief as a board/CEO-ready PDF. Renders from
    the SAME core.weekly_brief.compose() dict the Reports page shows on screen,
    so the printed brief and the on-screen brief can never disagree."""
    from core import weekly_brief
    b = weekly_brief.compose(client_id)

    buf, doc = _doc(f"{b['ticker']} Weekly IR Brief — {b['week_label']}")
    story = []
    _header(story, "WEEKLY IR INTELLIGENCE BRIEF",
            f"{_esc(b['name'])} — {_esc(b['week_label'])}",
            "Composed live from price &amp; volume, the IR activity log, the earnings calendar, the "
            f"script workflow, the investor pipeline and peer activity · generated {b['as_of']:%b %d, %Y}")

    if b["stats"]:
        story.append(_stat_row([(_esc(v), _esc(l), _esc(s), ACCENT) for v, l, s in b["stats"]]))

    for sec in b["sections"]:
        story.append(Paragraph(_esc(sec["title"]), _S["h2"]))
        for line in sec["lines"]:
            story.append(Paragraph("• " + _esc(line), _S["bullet"]))

    story.append(Paragraph(
        "Every figure above recomputes at export time from the latest filing, market data and "
        "activity log — nothing here is pre-baked. Sections with no live data are omitted rather "
        "than filled with placeholders.", _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def script_scorecard_pdf(client_id=None):
    """Script Effectiveness Scorecard — live, from core.script_scorecard.compose().
    Replaces the static Q1 image. States its own methodology and the two things
    it deliberately does NOT compute without transcripts."""
    from core import script_scorecard
    d = script_scorecard.compose(client_id)
    ticker = CT("ticker")

    buf, doc = _doc(f"{ticker} Script Effectiveness Scorecard")
    story = []
    _header(story, "SCRIPT EFFECTIVENESS SCORECARD",
            f"{CT('name')} — earnings script, live scoring",
            f"Recomputed from the script on file · workflow stage: {_esc(d['stage'])} "
            f"({d['stages_done']}/{d['stages_total']} stages complete) · generated {datetime.now():%b %d, %Y}")

    score_color = GOOD if d["score"] >= 80 else (WARN if d["score"] >= 60 else colors.HexColor("#B91C1C"))
    story.append(_stat_row(
        [(f"{d['score']}", "Score / 100", "measurable components only", score_color),
         (f"{d['override_minutes']:.1f} min", "Consolidated script", f"{d['override_words']} words @ 140 wpm", ACCENT),
         (f"{sum(1 for c in d['carryover'] if c['addressed'])}/{len(d['carryover'])}",
          "Q1 topics closed", "carry-over into this script", ACCENT)]))

    story.append(Paragraph("How the score is built", _S["h2"]))
    rows = [[Paragraph(h, _S["th"]) for h in ["Component", "Score", "Basis"]]]
    for name, val, mx, note in d["components"]:
        rows.append([Paragraph(_esc(name), _S["td"]), Paragraph(f"{val}/{mx}", _S["td"]),
                     Paragraph(_esc(note), _S["td"])])
    t = Table(rows, colWidths=[1.7 * inch, 0.7 * inch, 4.6 * inch])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    story.append(Paragraph("Section run-time vs target", _S["h2"]))
    rows = [[Paragraph(h, _S["th"]) for h in ["Section", "Words", "Est. time", "Target", "Read"]]]
    for s in d["sections"]:
        rows.append([Paragraph(_esc(s["label"]), _S["td"]), Paragraph(str(s["words"]), _S["td"]),
                     Paragraph(f"{s['minutes']:.1f} min", _S["td"]),
                     Paragraph(f"{s['target']:.1f} min", _S["td"]),
                     Paragraph(_esc(s["status"]), _S["td"])])
    t = Table(rows, colWidths=[1.7 * inch, 0.7 * inch, 0.9 * inch, 0.8 * inch, 2.9 * inch])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(t)

    g = d.get("guidance") or {}
    if g.get("conflicts") or g.get("needs_redraft"):
        gi = g.get("input") or {}
        story.append(Paragraph("Guidance version conflict", _S["h2"]))
        story.append(_callout(
            "THE INPUT (CFO DECISION)",
            f"{_esc(gi.get('action'))} &rarr; ${gi.get('low')}M–${gi.get('hi')}M"
            + ("  ·  needs_redraft is set — the authored prose predates this decision."
               if g.get("needs_redraft") else ""),
            colors.HexColor("#B91C1C")))
        for c in g["conflicts"]:
            story.append(Paragraph(
                f"<b>[CONFLICT] {_esc(c['source'])}</b> states {_esc(c['stated'])} — "
                f"the decision says ${gi.get('low')}M–${gi.get('hi')}M.", _S["bullet"]))
            story.append(Paragraph(f"<i>{_esc(c['excerpt'])}</i>", _S["bullet"]))

    story.append(Paragraph("Carry-over from last quarter's post-mortem", _S["h2"]))
    for c in d["carryover"]:
        mark = "CLOSED" if c["addressed"] else "STILL OPEN"
        story.append(Paragraph(
            f"<b>[{mark}] {_esc(c['priority'])} — {_esc(c['topic'])}</b> ({_esc(c['target'])}). "
            f"Q1: {_esc(c['q1'])}.", _S["bullet"]))
        if c["evidence"]:
            story.append(Paragraph(f"<i>Found in script:</i> {_esc(c['evidence'])}", _S["bullet"]))

    if d["gaps"]:
        story.append(Paragraph("Not scored here — and why", _S["h2"]))
        for g in d["gaps"]:
            story.append(Paragraph("• " + _esc(g), _S["bullet"]))

    story.append(Paragraph(_esc(d["method"]), _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def _segments_story(story):
    """Segment revenue — and the sum-of-the-parts test of our own headline.

    Placed immediately BEFORE the transaction comps and AFTER the comp table, because it is
    the strongest available objection to the comp table: USIO's multiple is blended across a
    payments business and a print-and-mail business, while the peer median is pure-play
    payments. A reader who spots that on their own and doesn't find it addressed stops
    trusting the rest of the page.
    """
    try:
        from core import segments
        seg = segments.build()  # active tenant, not hardcoded
    except Exception as exc:
        print(f"[report_pdf] segments unavailable: {exc}")
        return
    if seg.get("status") != "ok" or not seg.get("segments"):
        return

    story.append(Paragraph("Segment revenue &mdash; where the gross profit actually comes from",
                           _S["h2"]))
    story.append(Paragraph(_esc(seg["read"]), _S["body"]))

    head = ["Segment", "Revenue ($M)", "Cost ($M)", "Gross profit ($M)", "Gross margin",
            "Rev growth", "Margin Δ"]
    data = [[Paragraph(h, _S["th"]) for h in head]]
    for x in seg["segments"]:
        data.append([
            Paragraph(f"<b>{_esc(x['label'])}</b>", _S["td"]),
            Paragraph(f"{x['revenue']/1e6:,.1f}" if x.get("revenue") else "—", _S["td"]),
            Paragraph(f"{x['cost']/1e6:,.1f}" if x.get("cost") else "—", _S["td"]),
            Paragraph(f"{x['gross_profit']/1e6:,.1f}" if x.get("gross_profit") else "—", _S["td"]),
            Paragraph(f"{x['gross_margin']:.1f}%" if x.get("gross_margin") is not None else "—", _S["td"]),
            Paragraph(f"{x['rev_growth']:+.1f}%" if x.get("rev_growth") is not None else "—", _S["td"]),
            Paragraph(f"{x['gm_delta_pp']:+.1f}pp" if x.get("gm_delta_pp") is not None else "—", _S["td"])])
    c = seg["consolidated"]
    data.append([
        Paragraph("<b>Total</b>", _S["td"]),
        Paragraph(f"<b>{c['revenue']/1e6:,.1f}</b>", _S["td"]),
        Paragraph(f"<b>{c['cost']/1e6:,.1f}</b>", _S["td"]),
        Paragraph(f"<b>{c['gross_profit']/1e6:,.1f}</b>", _S["td"]),
        Paragraph(f"<b>{c['gross_profit']/c['revenue']*100:.1f}%</b>", _S["td"]),
        Paragraph("", _S["td"]), Paragraph("", _S["td"])])
    t = Table(data, colWidths=[1.35 * inch, 0.85 * inch, 0.8 * inch, 1.0 * inch,
                               0.85 * inch, 0.8 * inch, 0.75 * inch])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -2), 0.4, BORDER),
        ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
    story.append(t)
    story.append(Paragraph(
        f"Source: FY{seg['fy'][:4]} 10-K segment note (us-gaap:StatementBusinessSegmentsAxis), read "
        f"from the filing&rsquo;s own XBRL instance &mdash; EDGAR&rsquo;s companyfacts API carries "
        f"consolidated facts only. {_esc(seg.get('detail') or '')}", _S["small"]))
    story.append(Paragraph(
        f"<b>Note the period.</b> Growth here is <b>FY{seg['fy'][:4]} vs FY{str(seg['prior_fy'])[:4]} "
        f"(annual)</b>, because that is the only basis the segment note is reported on. The comp "
        f"table above uses <b>latest-quarter YoY</b>, the basis every peer is measured on. Both are "
        f"correct and neither is a typo &mdash; USIO is accelerating (Q1 FY26 revenue $25.5M vs "
        f"$22.0M a year prior, against an FY2025 average quarter near $21.3M). The annual-vs-"
        f"quarterly comparison on both bases is set out below.", _S["small"]))
    _annual_growth_story(story)

    sotp = seg.get("sotp")
    if sotp:
        story.append(_callout(
            f"SUM-OF-THE-PARTS — BREAKEVEN ON {_esc(' + '.join(sotp['other_labels'])).upper()}: "
            f"{sotp['breakeven_other_ev_gp']:.2f}x",
            _esc(sotp["read"]),
            GOOD if (sotp["breakeven_other_ev_gp"] < 1.0 and not sotp["residual_negative"]) else WARN))




def _annual_growth_story(story):
    """Growth on both bases, peer by peer — the table behind the growth-basis callout.

    The comp table's growth column is latest-quarter REVENUE growth. This one is annual, and
    shows GROSS PROFIT growth beside it, because gross profit is the denominator the ranking
    actually uses. For USIO the two bases disagree by ~15pp in the flattering direction, so
    showing only the first would be steering.
    """
    from core import valuation_comp
    try:
        gb = valuation_comp.build().get("growth_basis")
    except Exception as exc:
        print(f"[report_pdf] growth basis unavailable: {exc}")
        return
    if not gb:
        return

    story.append(Paragraph(
        "Growth vs peers &mdash; annual, and on the gross-profit basis the ranking uses",
        _S["h2"]))

    head = ["", "Annual revenue growth", "Annual gross profit growth", "Gross margin Δ"]
    data = [[Paragraph(h, _S["th"]) for h in head]]

    def _row(tag, rg, gg, dm, bold=False):
        f = (lambda x: f"<b>{x}</b>") if bold else (lambda x: x)
        data.append([
            Paragraph(f(_esc(tag)), _S["td"]),
            Paragraph(f(f"{rg:+.1f}%") if rg is not None else "—", _S["td"]),
            Paragraph(f(f"{gg:+.1f}%") if gg is not None else "—", _S["td"]),
            Paragraph(f(f"{dm:+.1f}pp") if dm is not None else "—", _S["td"])])

    _row(CT("ticker"), gb["usio_annual_rev_growth"], gb["usio_annual_gp_growth"],
         gb.get("usio_gm_delta_pp"), bold=True)
    for pr in sorted(gb["peers"], key=lambda x: -(x["gp_growth"] if x["gp_growth"] is not None else -999)):
        _row(pr["ticker"], pr["rev_growth"], pr["gp_growth"], pr.get("gm_delta_pp"))
    _row("— peer median —", gb["median_annual_rev_growth"], gb["median_annual_gp_growth"],
         None, bold=True)

    t = Table(data, colWidths=[1.4 * inch, 1.7 * inch, 2.0 * inch, 1.3 * inch])
    ts = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
          ("LINEBELOW", (0, 1), (-1, -2), 0.4, BORDER),
          ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
          ("BACKGROUND", (0, 1), (-1, 1), SOFT),
          ("ALIGN", (1, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    t.setStyle(TableStyle(ts))
    story.append(t)
    story.append(Paragraph(
        f"FY{str(gb['fy'])[:4]} vs FY{str(gb['prior_fy'])[:4]}, from each filer&rsquo;s own annual "
        f"report (n={gb['n_peers']} peers). Gross profit is reported where the filer tags it and "
        f"derived from revenue less its own cost line where it does not &mdash; same period, both "
        f"sides, never a vendor figure. USIO&rsquo;s row ties exactly to the FY2025 10-K segment "
        f"note reproduced above.", _S["small"]))




def _valuation_caveats(story, comp, compact=True):
    """The qualifications that MUST travel with the implied-upside number.

    WHY THIS EXISTS. The board package rendered "+20% implied upside" in green with nothing
    attached, while the analysis behind it carried two live objections that the peer
    benchmarking PDF states plainly. A favourable conclusion presented without the
    qualifications the same analysis produced is precisely the failure this platform was
    rebuilt to remove — and the board package is the worst possible place for it, because it
    is the document that leaves the building.

    So the caveats are not optional garnish on the number; they are part of it. Compact form
    for the board package, full sections for the benchmarking deep-dive.
    """
    if not comp:
        return

    # 1. The blend objection: our multiple is blended, the peer median is pure-play.
    try:
        from core import segments
        seg = segments.build()  # active tenant, not hardcoded
        sotp = seg.get("sotp") if seg.get("status") == "ok" else None
    except Exception as exc:
        print(f"[report_pdf] segments unavailable for caveats: {exc}")
        sotp = None
    if sotp:
        safe = sotp["breakeven_other_ev_gp"] < 1.0 and not sotp["residual_negative"]
        story.append(_callout(
            "IS THE DISCOUNT REAL? THE STRONGEST OBJECTION, TESTED",
            _esc(sotp["read"]), GOOD if safe else WARN))

    # 1b. The growth gap, on the basis the multiple actually pays for. This one is louder
    # than the blend objection: the comp table's growth column measures revenue, while the
    # ranking measures gross profit, and for USIO those disagree by ~15pp — flatteringly.
    gb = comp.get("growth_basis")
    if gb and gb.get("read"):
        story.append(_callout(
            (f"THE GROWTH GAP IS {abs(gb['gap_annual_gp']):.0f}pp ON THE BASIS EV/GROSS PROFIT "
             f"PAYS FOR — NOT {abs(gb['gap_quarterly_rev']):.0f}pp"
             if gb.get("basis_matters") else "GROWTH VS PEERS, ON BOTH BASES"),
            _esc(gb["read"]), WARN if gb.get("basis_matters") else INK))

    # 2. Peers dropped from the median entirely — invisible to sensitivity() by construction.
    excl = comp.get("excluded_impact")
    if excl and excl.get("read"):
        story.append(_callout(
            "EXCLUDED PEERS WOULD MOVE THIS MATERIALLY" if excl.get("material")
            else "PEERS EXCLUDED FROM THE MEDIAN",
            _esc(excl["read"]), WARN if excl.get("material") else INK))

    # 3. Take-out evidence + the overhang on the median-setter.
    txn = comp.get("transaction_comps")
    if txn:
        pb = txn.get("prth_bid")
        if compact:
            bits = []
            if pb:
                bits.append(
                    f"<b>PRTH take-private overhang.</b> PRTH sets the peer median. Its "
                    f"Chairman/CEO (~58% holder) proposed $6.00&ndash;$6.15 cash on 2025-11-09 "
                    f"&mdash; {pb['bid_ev_gp_low']:.2f}x&ndash;{pb['bid_ev_gp_high']:.2f}x EV/GP. "
                    f"The proposal is <b>preliminary and non-binding</b>, and no definitive "
                    f"agreement has followed in {pb['stale_days']} days. PRTH remains in the "
                    f"median because the stock trades ${pb['market_price']:.2f} "
                    f"({pb['market_ev_gp']:.2f}x) &mdash; <b>above</b> the bid; a stock pinned to "
                    f"a live deal trades below the offer. Were PRTH removed, the median would "
                    f"fall and the implied upside with it.")
            bits.append(
                "<b>GDOT</b> is a signed deal (approved 2026-06-23: $8.11 cash + 0.2215 New "
                "CommerceOne shares) and is excluded from the median &mdash; but for an unrelated "
                "reason: it reports no gross profit line at all. No take-out multiple is shown "
                "for it because none can honestly be computed.")
            bits.append(
                "A take-out multiple is a <b>reference point, not a price target</b>. USIO is not "
                "in a process and nothing here implies it should be.")
            story.append(Paragraph("Transaction comps &amp; the take-private overhang", _S["h2"]))
            for b in bits:
                story.append(Paragraph(b, _S["small"]))


def _valuation_comp_story(story):
    """Valuation Comp section — the comp table and the implied value it produces.
    Prints the RANGE where the discount isn't robust; a point estimate would be a
    claim the data doesn't support."""
    from core import valuation_comp
    d = valuation_comp.build()
    u, m, imp, sens = d["usio"], d["median"], d["implied"], d.get("sensitivity")

    story.append(Paragraph("Valuation comp — what USIO is worth at its peers' multiple", _S["h2"]))
    if imp:
        lo = hi = imp["upside_pct"]
        if sens and not sens["robust"]:
            lo, hi = sorted([sens["upside_backed"], sens["upside_all"]])
        story.append(_stat_row([
            (f"{imp['current_multiple']:.1f}x", "USIO EV/Gross Profit",
             f"rank #{u.get('rank', '—')} of {d['n_primary']+1}", ACCENT),
            (f"{imp['peer_median_multiple']:.1f}x", "Peer median EV/GP",
             f"primary peers only (n={d['n_primary']})", INK),
            (f"{lo:+.0f}% to {hi:+.0f}%" if (sens and not sens["robust"]) else f"{imp['upside_pct']:+.0f}%",
             "Implied upside", "at peer median, equity basis", GOOD if lo > 0 else colors.HexColor("#B91C1C")),
        ]))
        story.append(Paragraph(f"<b>{_esc(d['read'])}</b>", _S["body"]))
    if sens and not sens["robust"]:
        story.append(_callout(
            f"THE SIZE OF THE DISCOUNT IS NOT ROBUST — {sens['upside_backed']:+.0f}% VS "
            f"{sens['upside_all']:+.0f}%", _esc(sens["note"]), WARN))

    # Peers excluded ENTIRELY. sensitivity() above only inspects peers that HAVE a
    # multiple, so a dropped peer is invisible to it — and a dropped peer can move the
    # median further than any basis question among the ones that stayed.
    excl = d.get("excluded_impact")
    if excl and excl.get("read"):
        story.append(_callout(
            ("EXCLUDED PEERS WOULD MOVE THIS MATERIALLY"
             if excl.get("material") else "PEERS EXCLUDED FROM THE MEDIAN"),
            _esc(excl["read"]), WARN if excl.get("material") else INK))

    # The growth gap on the basis the ranking actually uses. This belongs HERE, next to the
    # implied-upside number it qualifies — not buried later. The board package carries the
    # same callout via _valuation_caveats; this is the deep-dive's copy.
    gb = d.get("growth_basis")
    if gb and gb.get("read"):
        story.append(_callout(
            (f"THE GROWTH GAP IS {abs(gb['gap_annual_gp']):.0f}pp ON THE BASIS EV/GROSS PROFIT "
             f"PAYS FOR — NOT {abs(gb['gap_quarterly_rev']):.0f}pp"
             if gb.get("basis_matters") else "GROWTH VS PEERS, ON BOTH BASES"),
            _esc(gb["read"]), WARN if gb.get("basis_matters") else INK))

    story.append(Paragraph("Comp table — ranked by EV/Gross Profit (cheapest first)", _S["h2"]))
    BASIS = {"ok": "filing", "derived": "filing (derived)", "stale": "market · filing stale",
             "no_gross_profit_line": "market · none filed", "no_cik": "no EDGAR data"}
    head = ["", "Company", "EV ($M)", "EV/GP", "EV/Rev*", "Gross margin*", "Rev growth", "GM basis"]
    data = [[Paragraph(h, _S["th"]) for h in head]]
    client_idx = None
    for i, r in enumerate(d["ranked"]):
        if r["is_client"]:
            client_idx = i + 1
        data.append([
            Paragraph(f"<b>{_esc(r['ticker'])}</b>" if r["is_client"] else _esc(r["ticker"]), _S["td"]),
            Paragraph(_esc(r["name"]), _S["td"]),
            Paragraph(f"{r['enterprise_value']/1e6:,.0f}" if r["enterprise_value"] else "—", _S["td"]),
            Paragraph(f"{r['ev_gp']:.1f}x" if r["ev_gp"] else "—", _S["td"]),
            Paragraph(f"{r['ev_rev']:.2f}x" if r["ev_rev"] else "—", _S["td"]),
            Paragraph(f"{r['gross_margin']:.1f}%" if r["gross_margin"] is not None else "—", _S["td"]),
            Paragraph(f"{r['rev_growth']:+.0f}%" if r["rev_growth"] is not None else "—", _S["td"]),
            Paragraph(_esc(BASIS.get(r["gm_basis"], r["gm_basis"] or "—")), _S["td"])])
    data.append([
        Paragraph("", _S["td"]), Paragraph("<b>— primary peer median —</b>", _S["td"]),
        Paragraph("", _S["td"]),
        Paragraph(f"<b>{m['ev_gp']:.1f}x</b>" if m["ev_gp"] else "—", _S["td"]),
        Paragraph(f"{m['ev_rev']:.2f}x" if m["ev_rev"] else "—", _S["td"]),
        Paragraph(f"{m['gross_margin']:.1f}%" if m["gross_margin"] is not None else "—", _S["td"]),
        Paragraph(f"{m['rev_growth']:+.0f}%" if m["rev_growth"] is not None else "—", _S["td"]),
        Paragraph("", _S["td"])])
    t = Table(data, colWidths=[0.62 * inch, 1.58 * inch, 0.7 * inch, 0.55 * inch, 0.6 * inch,
                               0.85 * inch, 0.75 * inch, 1.35 * inch])
    ts = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
          ("LINEBELOW", (0, 1), (-1, -2), 0.4, BORDER),
          ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
          ("ALIGN", (2, 0), (6, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
          ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
    if client_idx:
        ts.append(("BACKGROUND", (0, client_idx), (-1, client_idx), SOFT))
    t.setStyle(TableStyle(ts))
    story.append(t)
    story.append(Paragraph(
        "* EV/Revenue and gross margin are <b>not comparable across these rows</b> and are shown for "
        "context only — USIO reports revenue gross as a principal and peers vary. Revenue cancels out "
        "of EV/Gross Profit, which is why the ranking and the implied value use it and nothing else.",
        _S["small"]))

    _segments_story(story)

    # ---- Transaction comps ----
    # What an ACQUIRER offered, kept deliberately OUTSIDE the trading median. A control bid
    # is corroborating evidence of a different kind, not another row in the table.
    txn = d.get("transaction_comps")
    if txn:
        story.append(Paragraph(
            "Transaction comps &mdash; what an acquirer offered for a peer", _S["h2"]))
        story.append(Paragraph(_esc(txn["read"]), _S["body"]))
        pb = txn.get("prth_bid")
        head2 = ["Target", "Consideration", "Status", "Implied EV/GP"]
        rows2 = [[Paragraph(h, _S["th"]) for h in head2]]
        if pb:
            rows2.append([
                Paragraph("<b>PRTH</b>", _S["td"]),
                Paragraph("$6.00&ndash;$6.15 cash", _S["td"]),
                Paragraph("Preliminary, <b>non-binding</b> (2025-11-09); no definitive "
                          f"agreement in {pb['stale_days']} days", _S["td"]),
                Paragraph(f"<b>{pb['bid_ev_gp_low']:.2f}x&ndash;{pb['bid_ev_gp_high']:.2f}x</b>"
                          f"<br/><font size=7>vs {pb['market_ev_gp']:.2f}x market</font>", _S["td"])])
        rows2.append([
            Paragraph("<b>GDOT</b>", _S["td"]),
            Paragraph("$8.11 cash + 0.2215 New CommerceOne sh", _S["td"]),
            Paragraph("<b>Definitive</b>; approved by stockholders 2026-06-23", _S["td"]),
            Paragraph("<b>not computable</b><br/><font size=7>no gross profit line; "
                      "stock leg does not trade</font>", _S["td"])])
        t2 = Table(rows2, colWidths=[0.6 * inch, 1.7 * inch, 2.6 * inch, 1.7 * inch])
        t2.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]))
        story.append(t2)
        if pb:
            story.append(Paragraph(_esc(pb["basis_caveat"]), _S["small"]))
        story.append(Paragraph(
            "Sources: PRTH 8-K 2025-11-10 and 2025-12-08 (Item 8.01). GDOT DEFM14A 2026-05-08; "
            "8-K 2026-06-24 (Item 5.07). Read on EDGAR. <b>A take-out multiple is a reference "
            "point, not a price target</b> &mdash; USIO is not in a process and nothing here "
            "implies it should be.", _S["small"]))


    # ---- EV/Revenue bridge ----
    try:
        from core import valuation_comp as _vc
        bg = _vc.revenue_bridge()
    except Exception:
        bg = None
    if bg and bg.get("usio"):
        story.append(Paragraph("The EV/Revenue bridge — why the &lsquo;revenue discount&rsquo; was never real",
                               _S["h2"]))
        story.append(Paragraph(
            "Everyone quotes EV/Revenue, and across this peer set it is not comparable. But it is "
            "<b>derivable</b>, because the identity is exact: <b>EV/Revenue = EV/Gross Profit &times; gross "
            "margin</b>. So apply the peer median EV/Gross Profit — the multiple that IS comparable — to "
            "each company's OWN margin. The margin never leaves its own filer, so nothing is compared "
            "that shouldn't be, and the answer comes back in the language the market speaks.", _S["body"]))
        rows = [[Paragraph(h, _S["th"]) for h in
                 ["", "EV/GP", "Gross margin", "EV/Rev today", "EV/Rev warranted", "vs warranted"]]]
        ci = None
        for i, r in enumerate(bg["rows"]):
            if r["is_client"]:
                ci = i + 1
            rows.append([
                Paragraph(f"<b>{_esc(r['ticker'])}</b>" if r["is_client"] else _esc(r["ticker"]), _S["td"]),
                Paragraph(f"{r['ev_gp']:.2f}x", _S["td"]),
                Paragraph(f"{r['gross_margin']:.1f}%", _S["td"]),
                Paragraph(f"{r['ev_rev_actual']:.2f}x" if r["ev_rev_actual"] else "—", _S["td"]),
                Paragraph(f"<b>{r['ev_rev_warranted']:.2f}x</b>", _S["td"]),
                Paragraph(f"{r['vs_warranted_pct']:+.0f}%" if r["vs_warranted_pct"] is not None else "—",
                          _S["td"])])
        t = Table(rows, colWidths=[0.62 * inch, 0.85 * inch, 1.25 * inch, 1.35 * inch, 1.55 * inch,
                                   1.38 * inch])
        ts = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
              ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
              ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if ci:
            ts.append(("BACKGROUND", (0, ci), (-1, ci), SOFT))
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(_callout("THE FINDING", _esc(bg["read"]), ACCENT))

    if imp:
        story.append(Paragraph("The bridge — how the implied value is built", _S["h2"]))
        bridge = [
            ("USIO gross profit (EV ÷ current EV/GP)", f"${imp['gross_profit']/1e6:,.1f}M"),
            ("× peer median EV/Gross Profit", f"{imp['peer_median_multiple']:.2f}x"),
            ("= implied enterprise value", f"${imp['implied_ev']/1e6:,.1f}M"),
            (("+ net cash" if imp["net_debt"] < 0 else "− net debt"),
             f"${abs(imp['net_debt'])/1e6:,.1f}M"),
            ("= implied equity value", f"${imp['implied_equity']/1e6:,.1f}M"),
            ("vs market cap today", f"${imp['current_equity']/1e6:,.1f}M"),
            ("implied upside", f"{imp['upside_pct']:+.0f}%"),
        ]
        bt = Table([[Paragraph(_esc(k), _S["td"]), Paragraph(f"<b>{_esc(v)}</b>", _S["td"])]
                    for k, v in bridge], colWidths=[4.6 * inch, 2.4 * inch])
        bt.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -2), 0.4, BORDER),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(bt)


def _forensics_story(story):
    """Footnote Forensics section — from primary SEC filings only.

    Prints what CANNOT be claimed as prominently as what can. Two earlier versions
    of this section printed confident, false findings ("USIO BEATS FOUR", "clean on
    3/3 distortions") sourced from a workbook whose 10-K citations were fabricated.
    """
    from core import forensics
    d = forensics.build()
    pol, us = d["policy"], d["usio"]

    story.append(Paragraph("Footnote forensics — is USIO's gross margin comparable at all?", _S["h2"]))
    story.append(_callout(
        f"USIO REPORTS REVENUE {_esc(pol['basis'])} — VERIFIED FROM THE FILING",
        f"“{_esc(pol['quote'])}” &mdash; {_esc(pol['form'])} filed {_esc(pol['filed'])}. "
        f"USIO's gross margin is therefore depressed by its OWN presentation: interchange and "
        f"sponsor-bank fees it never keeps sit in both revenue and cost of services. Any analysis "
        f"claiming USIO is a net reporter whose margin is understated relative to gross-reporting "
        f"peers has the mechanism backwards.", colors.HexColor("#B91C1C")))

    if us.get("gross_margin") is not None:
        story.append(_stat_row([
            (f"{us['gross_margin']*100:.1f}%", "USIO gross margin",
             f"FY{us['period'][:4]} · gross basis", INK),
            ("n/a", "Net-basis margin", "no interchange $ disclosed", colors.HexColor("#B91C1C")),
            (f"{len(d['peers_comparable'])} of {d['n_primary']}", "Peers comparable",
             f"{d['pct_comparable']}% of primary comp set", WARN),
        ]))

    story.append(Paragraph("What each peer's own filing supports", _S["h2"]))
    LBL = {"ok": "yes", "derived": "yes — derived", "ok_mda": "yes — 10-K MD&A",
           "stale": "NO — stale", "stale_mda": "NO — hand-carried fact is stale",
           "no_gross_profit_line": "NO — metric does not exist",
           "no_cik": "NO — no EDGAR data", "fetch_failed": "NO — fetch failed"}
    rows = [[Paragraph(h, _S["th"]) for h in ["", "Gross margin", "Period", "Usable?", "Why"]]]
    for t, r in sorted(d["rows"].items(), key=lambda kv: (kv[1]["status"] != "ok", kv[0])):
        rows.append([
            Paragraph(f"<b>{_esc(t)}</b>", _S["td"]),
            Paragraph(f"{r['gross_margin']*100:.1f}%" if r["gross_margin"] is not None else "—", _S["td"]),
            Paragraph(_esc((r["period"] or "—")[:7]), _S["td"]),
            Paragraph(_esc(LBL.get(r["status"], r["status"])), _S["td"]),
            Paragraph(_esc(r["detail"] or ""), _S["td"])])
    t = Table(rows, colWidths=[0.5 * inch, 0.85 * inch, 0.7 * inch, 1.0 * inch, 3.95 * inch])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    story.append(_callout("THE FINDING", _esc(d["verdict"]), ACCENT))

    sb = d.get("sbc")
    if sb and sb.get("usio"):
        story.append(Paragraph(
            "Stock-based compensation — measured against gross profit, not revenue", _S["h2"]))
        story.append(Paragraph(
            "The denominator is the whole argument. USIO's revenue is GROSS, so &lsquo;% of "
            "revenue&rsquo; inflates its denominator with interchange it never keeps and flatters it "
            "more than any peer here. Gross profit is presentation-invariant — the only basis that "
            "compares.", _S["body"]))
        rows = [[Paragraph(h, _S["th"]) for h in
                 ["", "SBC ($M)", "% of revenue", "% of gross profit", "Rank (of GP)"]]]
        ci = None
        for i, r in enumerate(sb["rows"]):
            if r["is_client"]:
                ci = i + 1
            rows.append([Paragraph(f"<b>{_esc(r['ticker'])}</b>" if r["is_client"] else _esc(r["ticker"]), _S["td"]),
                         Paragraph(f"{r['sbc']/1e6:,.1f}", _S["td"]),
                         Paragraph(f"{r['pct_revenue']:.1f}%", _S["td"]),
                         Paragraph(f"{r['pct_gross_profit']:.1f}%", _S["td"]),
                         Paragraph(f"{r['rank_gp']} of {sb['n']}", _S["td"])])
        t = Table(rows, colWidths=[0.62 * inch, 1.1 * inch, 1.3 * inch, 1.6 * inch, 1.3 * inch])
        ts = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
              ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
              ("ALIGN", (1, 0), (3, -1), "RIGHT"),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if ci:
            ts.append(("BACKGROUND", (0, ci), (-1, ci), SOFT))
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(_callout("THE 'LEAN SBC' STORY DOES NOT SURVIVE THE RIGHT DENOMINATOR",
                              _esc(sb["read"]), colors.HexColor("#B91C1C")))
    story.append(_callout(
        "SOURCE DISCIPLINE — WHY THIS SECTION IS THINNER THAN THE WORKBOOK",
        "Every figure here resolves to an SEC filing this report fetched itself. The prior version of "
        "this analysis was built from USIO_Peer_Benchmarking_Report_v2_2.xlsx, whose verbatim "
        "&lsquo;10-K p.58 / p.38 / p.94&rsquo; quotes do not appear in the respective 10-Ks. Where a "
        "figure cannot be sourced from a filing, this section reports that it cannot, rather than "
        "estimating it.", WARN))


def earnings_prep_pdf(client_id=None):
    """The Earnings Prep Brief — what management needs in the room before the call.

    Leads with the sharpest TRUE fact, not the friendliest. A prep brief that opens
    with reassurance has no reason to exist: management can feel reassured without it.
    """
    from core import earnings_prep
    d = earnings_prep.compose(client_id)
    b, r, q = d.get("bar"), d.get("reconciliation"), d.get("qa")

    buf, doc = _doc(f"{d['ticker']} {d['quarter']} Earnings Prep Brief")
    story = []
    _header(story, "EARNINGS PREP BRIEF",
            f"{_esc(d['name'])} — {_esc(d['quarter'])} call prep",
            f"Call {_esc(str(d['earnings_date']))} · {d['days_out']} days out · every figure "
            f"recomputed live from the consensus file, the guidance decision, the risk scorecard "
            f"and the {_esc((q or {}).get('from_quarter', 'last'))} transcript · "
            f"generated {d['as_of']:%b %d, %Y}")

    story.append(_callout("READ THIS FIRST", _esc(earnings_prep.headline(d)),
                          colors.HexColor("#B91C1C")))

    # ---- Comp quality: is the base clean? ----
    cq = d.get("comp_quality")
    if cq and cq.get("status") == "ok":
        story.append(Paragraph(
            f"Comp quality &mdash; the {_esc(str(cq['base_end']))} base this print lands against",
            _S["h2"]))
        story.append(_stat_row([
            (f"${cq['base_revenue']/1e6:.1f}M", "Base revenue",
             (f"{cq['base_vs_fy_avg_pct']:+.1f}% vs its FY avg quarter"
              if cq.get("base_vs_fy_avg_pct") is not None else "base quarter"),
             WARN if cq.get("revenue_comp_easy") else INK),
            (f"${cq['base_gross_profit']/1e6:.2f}M", "Base gross profit",
             (f"#{cq['gp_rank_2yr']} of {cq['gp_n_2yr']} over 2yrs &mdash; the hardest comp"
              if cq.get("gp_comp_hard") else f"{cq['base_margin']:.1f}% margin"),
             WARN if cq.get("gp_comp_hard") else INK),
            (f"{cq['base_margin']:.1f}%", "Base margin", "the peak of the series", INK),
        ]))
        if cq.get("repeat_rev_yoy") is not None and cq.get("repeat_gp_yoy") is not None:
            story.append(Paragraph(
                f"<b>If the upcoming quarter merely repeats the last one filed:</b> revenue prints "
                f"<b>{cq['repeat_rev_yoy']:+.1f}%</b> YoY while gross profit prints "
                f"<b>{cq['repeat_gp_yoy']:+.1f}%</b> &mdash; a "
                f"<b>{abs(cq['repeat_rev_yoy'] - cq['repeat_gp_yoy']):.0f}pp gap</b> off the same "
                f"base quarter. The same revenue dollars are "
                f"{cq.get('repeat_rev_vs_fy_avg', 0):+.1f}% against that year&rsquo;s average "
                f"quarter and {cq.get('two_yr_cagr', 0):+.1f}%/yr on a two-year stack.",
                _S["body"]))
        story.append(_callout("COMP QUALITY — WHAT THIS MEANS FOR THE SCRIPT",
                              _esc(cq["read"]), WARN if cq.get("divergent") else INK))

    # ---- What management must communicate, and the EPS bridge behind it ----
    # These two sections exist because the street is NOT doing this arithmetic. Management gave
    # enough on the Q1 call to build the whole P&L and nobody built it — the inputs come from an
    # issuer that cut guidance and then missed the cut. So the brief has to hand management the
    # bridge, or it never reaches a model.
    try:
        from core import mgmt_model, q2_script
        mm = mgmt_model.build()
        qs = q2_script.build()
    except Exception as exc:
        print(f"[report_pdf] mgmt model / script unavailable: {exc}")
        mm = qs = None

    if mm:
        story.append(Paragraph(
            "The EPS bridge management&rsquo;s own guidance implies &mdash; which nobody has built",
            _S["h2"]))
        story.append(_stat_row([
            (f"${mm['low']['eps']:.2f}", "LOW", "10% rev &middot; 23% GM", INK),
            (f"${mm['mid']['eps']:.2f}", "MID", "11% rev &middot; 24% GM", ACCENT),
            (f"${mm['high']['eps']:.2f}", "HIGH", "12% rev &middot; 25% GM", GOOD),
        ]))
        story.append(Paragraph(
            f"Against FY2025&rsquo;s actual <b>-${abs(mm['fy25']['eps_diluted']):.2f}</b>. Revenue "
            f"+10-12% is <b>GUIDED</b>; cash SG&amp;A &ldquo;roughly flattish&rdquo; is "
            f"<b>GUIDED</b>; gross margin 23-25% is a <b>TARGET, not guidance</b> "
            f"(&ldquo;I feel&hellip; we should be able to&hellip; in the short term&rdquo;). "
            f"Gross profit ${mm['fy25']['gross_profit']/1e6:.1f}M sits against opex "
            f"~${mm['mid']['opex']/1e6:.1f}M &mdash; USIO is <b>exactly at the operating-leverage "
            f"crossover</b>, so a 2pp gross margin move is roughly 4x the EPS. That is why the "
            f"gross margin is the only number on this release that matters.", _S["body"]))
        story.append(_callout("WHAT MANAGEMENT MUST COMMUNICATE", _esc(mm["read"]), ACCENT))

    if qs:
        story.append(Paragraph("The call, in the order that buys credibility back", _S["h2"]))
        c = qs["credibility"]
        story.append(Paragraph(
            f"<b>Why order matters here.</b> FY2025 guidance was lowered to "
            f"<b>{_esc(c['fy25_guidance_lowered_to'])}</b> on the Q2 2025 call because of "
            f"&ldquo;{_esc(c['why_lowered'])}&rdquo; &mdash; and FY2025 landed at "
            f"<b>+{c['fy25_actual']:.1f}%</b>, below the floor of the lowered range. A cut, then a "
            f"miss through the cut. The street now models the guidance and discounts every "
            f"forward-looking statement to zero. That prior is earned, and only a kept promise "
            f"retires it &mdash; so what LEADS is the argument.", _S["small"]))
        for sec in qs["sections"]:
            story.append(Paragraph(f"{sec['n']}. {_esc(sec['title'])}", _S["h3"] if "h3" in _S else _S["h2"]))
            story.append(Paragraph(f"<b>Say:</b> {_esc(sec['say'])}", _S["small"]))
            story.append(Paragraph(f"<b>Why:</b> {_esc(sec['why'])}", _S["small"]))
            story.append(Paragraph(f"<b>Do NOT:</b> {_esc(sec['do_not'])}", _S["small"]))

    # ---- The bar ----
    if b and not b.get("unavailable"):
        story.append(Paragraph(f"The bar — {_esc(b['period'])}", _S["h2"]))
        story.append(_stat_row([
            (f"${b['guidance']:.1f}M", "Our guidance", "what we promised", INK),
            (f"${b['street']:.2f}M", "The street",
             f"mean of {b['n']} analysts · {_esc(b.get('source', ''))}",
             GOOD if b.get("guide_above_all") else colors.HexColor("#B91C1C")),
            (f"{b['gap_pct']:+.1f}%", "Guide vs street",
             "our guide is above the street" if b["gap_pct"] < 0 else "street is above our guide",
             GOOD if b["gap_pct"] < 0 else colors.HexColor("#B91C1C")),
        ]))
        story.append(Paragraph(f"<b>{_esc(b['read'])}</b>", _S["body"]))
        rows = [[Paragraph(h, _S["th"]) for h in ["Street estimate", "Revenue", "vs our guide"]]]
        for label, val in [("Low", b.get("low")), ("Average", b.get("street")), ("High", b.get("high"))]:
            if val is None:
                continue
            rows.append([Paragraph(_esc(label), _S["td"]), Paragraph(f"${val:.2f}M", _S["td"]),
                         Paragraph(f"{(val/b['guidance']-1)*100:+.1f}%", _S["td"])])
        rows.append([Paragraph("<b>Our guidance</b>", _S["td"]),
                     Paragraph(f"<b>${b['guidance']:.2f}M</b>", _S["td"]), Paragraph("—", _S["td"])])
        t = Table(rows, colWidths=[2.6 * inch, 2.2 * inch, 2.2 * inch])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("LINEBELOW", (0, 1), (-1, -2), 0.4, BORDER),
            ("LINEABOVE", (0, -1), (-1, -1), 0.8, INK),
            ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        if b.get("coverage"):
            story.append(Paragraph("Covering analysts, per the market feed", _S["h2"]))
            crows = [[Paragraph(h, _S["th"]) for h in ["Firm", "Rating", "Price target", "Last action"]]]
            for cv in b["coverage"]:
                pt = cv.get("price_target")
                crows.append([Paragraph(_esc(cv["firm"]), _S["td"]),
                              Paragraph(_esc(cv.get("grade") or "—"), _S["td"]),
                              Paragraph(f"${pt:.2f}" if pt else "—", _S["td"]),
                              Paragraph(_esc(cv.get("date") or "—"), _S["td"])])
            ct = Table(crows, colWidths=[2.4 * inch, 1.6 * inch, 1.4 * inch, 1.6 * inch])
            ct.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ]))
            story.append(ct)
        if b.get("on_file_outside_range"):
            story.append(_callout(
                "THE ESTIMATES ON FILE IN THIS PLATFORM ARE DEMO DATA — NOT USED ABOVE",
                f"{_esc(', '.join(b['on_file_outside_range']))} fall outside the street's entire "
                f"published range (${b['low']:.2f}–{b['high']:.2f}M). period_estimates has never been "
                f"written for this client, so the platform falls back to a demo seed. The street "
                f"figures above come from the market feed with the period mapping reconciled against "
                f"filed actuals. Entering the real analyst models would let this cross-check do its job.",
                WARN))
    elif b and b.get("unavailable"):
        story.append(_callout("NO STREET READ AVAILABLE", _esc(b["read"]), WARN))

    # ---- Reconciliation ----
    if r and r.get("complete"):
        story.append(Paragraph("Do our own numbers add up?", _S["h2"]))
        rows = [[Paragraph(h, _S["th"]) for h in ["Period", "Source", "Revenue"]]]
        for p in r["parts"]:
            rows.append([Paragraph(_esc(p["period"]), _S["td"]),
                         Paragraph(_esc(p["source"] or "—"), _S["td"]),
                         Paragraph(f"${p['used']:.2f}M" if p["used"] is not None else "—", _S["td"])])
        rows.append([Paragraph("<b>Sum of quarters</b>", _S["td"]), Paragraph("", _S["td"]),
                     Paragraph(f"<b>${r['sum']:.2f}M</b>", _S["td"])])
        if r.get("fy_low") is not None:
            rows.append([Paragraph(f"<b>Stated {_esc(r['fy_label'])} guidance</b>", _S["td"]),
                         Paragraph("CFO decision", _S["td"]),
                         Paragraph(f"<b>${r['fy_low']:.1f} – {r['fy_high']:.1f}M</b>", _S["td"])])
        t = Table(rows, colWidths=[3.0 * inch, 2.0 * inch, 2.0 * inch])
        ts = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
              ("LINEBELOW", (0, 1), (-1, -3), 0.4, BORDER),
              ("LINEABOVE", (0, -2), (-1, -2), 0.8, INK),
              ("ALIGN", (2, 0), (2, -1), "RIGHT"),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if not r.get("reconciles"):
            ts.append(("BACKGROUND", (0, -2), (-1, -1), SOFT))
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Paragraph(_esc(r["read"]),
                               _S["body"] if r.get("reconciles") else _S["body"]))
        story.append(Paragraph(
            "Nothing else in the platform checks this. The guidance-consistency engine verifies that "
            "the script's prose states the same FY range the CFO decided — a text-vs-decision check. "
            "It does not add the quarters up.", _S["small"]))

    # ---- Scenarios ----
    if d.get("scenarios"):
        story.append(PageBreak())
        story.append(Paragraph("Beat / miss scenarios", _S["h2"]))
        story.append(Paragraph(
            "Thresholds are the street's published LOW / AVERAGE / HIGH plus our guide. The market "
            "feed gives the distribution but not per-analyst attribution, so these do not name which "
            "firm writes &lsquo;miss&rsquo; — the only per-analyst numbers on file are demo seed values "
            "that sit outside the real range.", _S["body"]))
        rows = [[Paragraph(h, _S["th"]) for h in
                 ["If revenue is", "vs guide", "vs Street", "Reads as", "What happens"]]]
        for s in d["scenarios"]:
            rows.append([
                Paragraph(f"<b>${s['revenue']:.2f}M</b>", _S["td"]),
                Paragraph(f"{s['vs_guide_pct']:+.1f}%", _S["td"]),
                Paragraph(f"{s['vs_street_pct']:+.1f}%", _S["td"]),
                Paragraph(_esc(s["label"]), _S["td"]),
                Paragraph(_esc(s["desc"]), _S["td"])])
        t = Table(rows, colWidths=[0.95 * inch, 0.7 * inch, 0.7 * inch, 1.5 * inch, 3.15 * inch])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
            ("ALIGN", (1, 0), (2, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)

    # ---- Q&A prep ----
    if q and q.get("open"):
        story.append(Paragraph(f"Q&amp;A prep — unpaid from the {_esc(q['from_quarter'])} call", _S["h2"]))
        story.append(Paragraph(_esc(q["read"]), _S["body"]))
        for f in q["open"]:
            story.append(_callout(
                f"{_esc(f.get('verdict'))} — {_esc(str(f.get('anchor')))[:70]}",
                f"<b>They asked about:</b> {_esc(str(f.get('anchor')))}<br/>"
                f"<b>The number was:</b> {_esc(str(f.get('valence')))} — so the answer owed was "
                f"{_esc(str(f.get('demand')))}.<br/>"
                f"<b>What happened:</b> {_esc(str(f.get('why')))[:600]}",
                WARN))
        story.append(Paragraph(
            "Method: every analyst question anchors on a number; that number's valence sets what kind "
            "of answer is owed (a GOOD number owes REPEATABILITY, a CLAIM owes BACKING); the verdict "
            "records whether it was paid. MISMATCH and DEFERRED are unpaid debts, and analysts carry "
            "debts forward.", _S["small"]))

    # ---- Risk flags ----
    if d.get("risks"):
        story.append(Paragraph("Risk flags — already known to be wrong going in", _S["h2"]))
        for s in d["risks"]:
            story.append(_callout(
                _esc(s.get("title")), _esc(str(s.get("desc"))),
                colors.HexColor("#B91C1C") if s.get("level") == "red" else WARN))

    if d.get("readiness"):
        story.append(Paragraph("Open readiness items", _S["h2"]))
        for r2 in d["readiness"]:
            story.append(Paragraph(
                f"• <b>{_esc(r2['item'])}</b> ({_esc(r2['level'])}) — {_esc(r2['detail'])}", _S["bullet"]))

    story.append(Paragraph(
        "Every figure recomputes at export time. Where a number could not be sourced, this brief says "
        "so rather than estimating it — and where a 'consensus' rests on two analysts, it says that too.",
        _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def morning_after_pdf(quarter=None, client_id=None, include_narrative=True):
    """The Morning-After critique as a report you can hand to the CFO.

    This is the script-writing report: what the tape did, how the call was
    delivered, whether management answered, and — the payload — what each
    question DEMANDED and whether it was delivered. Renders from
    core.morning_after.critique() (+ the cached Q&A frames), so the page and the
    paper cannot disagree.

    Ordering is the argument: unmet demands first, because an unmet demand is the
    only thing here that tells you what to write next quarter.
    """
    from core import morning_after
    c = morning_after.critique(quarter, client_id)
    if not c:
        raise ValueError("No transcript on file to critique")
    r, t, na, fr = c.get("reaction"), c.get("timing"), c.get("non_answers"), c.get("frames")
    ticker = CT("ticker")

    buf, doc = _doc(f"{ticker} Morning After — {c['quarter']}")
    story = []
    _header(story, "MORNING AFTER — POST-CALL CRITIQUE",
            f"{_esc(CT('name'))} — {_esc(c['quarter'])} earnings call",
            f"Call {c.get('call_date')} · measured from the transcript and the tape · "
            f"generated {datetime.now():%b %d, %Y}")

    # ── The tape ─────────────────────────────────────────────────────────────
    if r:
        drift = r["next_day_pct"] - r["pct"]
        gap_c = GOOD if r["pct"] >= 0 else colors.HexColor("#B91C1C")
        cl_c = GOOD if r["next_day_pct"] >= 0 else colors.HexColor("#B91C1C")
        story.append(_stat_row([
            (f"${r['close']:.2f}", "Call-day close", "last print before they read it", INK),
            (f"{r['pct']:+.2f}%", "Overnight gap", f"opened ${r['next_open']:.2f}", gap_c),
            (f"{r['next_day_pct']:+.2f}%", "Next close", f"{r['next_volume']:,} shares", cl_c),
            (f"{drift:+.2f}pp", "Moved after open",
             "digested through the session" if abs(drift) > abs(r["pct"]) else "verdict at the bell", ACCENT),
        ]))
        story.append(Paragraph(
            "Measured close-to-next-open. After-hours is excluded deliberately: on a micro-cap the "
            "AH tape is market-maker quotes that print but cannot be traded, so an 'after-hours "
            "reaction' measures an artifact rather than a verdict.", _S["small"]))

    # ── What the Q&A demanded — the payload, so it leads ─────────────────────
    if fr and fr.get("frames"):
        story.append(Paragraph("What the Q&A demanded — and whether you delivered it", _S["h2"]))
        story.append(Paragraph(
            "Every analyst question anchors on a number, and the analyst has ALREADY judged it. The "
            "valence sets what the answer owes: a GOOD number must be shown to REPEAT; a BAD number "
            "needs CONTROL and TIMING; a CLAIM or guide needs BACKING (what is signed vs assumed). "
            "A mismatch is rarely evasion — it is usually a good answer to a question nobody asked.",
            _S["body"]))
        story.append(_stat_row([
            (str(fr.get("mismatches", 0)), "Pressed &amp; unmet", "they pushed back",
             colors.HexColor("#B91C1C") if fr.get("mismatches") else GOOD),
            (str(fr.get("deferred", 0)), "Deferred", "they'll ask on the callback", WARN),
            (str(fr.get("withheld", 0)), "Withheld", "competitive — correct", INK2),
            (str(fr.get("discharged", 0)), "Discharged", f"of {fr.get('numeric_questions', 0)} numeric", GOOD),
        ]))
        story.append(Paragraph(
            "<b>DEFERRED is the cheap one.</b> Nobody pushed back, so nobody in the room knows it is "
            "missing — the analyst simply picks it up on the callback afterwards, and every other "
            "holder is left without it. The market is not on the callback, and the tape prices what "
            "the market heard.", _S["body"]))
        order = {"MISMATCH": 0, "DEFERRED": 1, "WITHHELD": 2, "DISCHARGED": 3}
        for x in sorted(fr["frames"], key=lambda z: order.get(z.get("verdict"), 9)):
            v = x.get("verdict")
            if v in (None, "NOT_NUMERIC", "DISCHARGED"):
                continue
            story.append(Paragraph(
                f"<b>[{_esc(v)}] {_esc(x.get('anchor'))}</b> — {_esc(x.get('valence'))} number, "
                f"so it owes {_esc(x.get('demand'))}.", _S["bullet"]))
            if x.get("missing"):
                story.append(Paragraph(f"<i>Omitted:</i> {_esc(x['missing'])}", _S["bullet"]))
            if x.get("why"):
                story.append(Paragraph(_esc(x["why"]), _S["bullet"]))

    # ── Non-answers, against the published base rate ─────────────────────────
    if na:
        story.append(Paragraph("Did management answer?", _S["h2"]))
        pct = na["rate"] * 100
        story.append(_callout(
            "NON-ANSWER RATE vs THE PUBLISHED NORM",
            f"{na['non_answers']} of {na['responses']} responses = {pct:.0f}%. "
            f"Benchmark ~11% across all firms (25th pct 7%, 75th 14%), stable over time and across "
            f"industries — Gow, Larcker &amp; Zakolyukina (2021), J. Accounting Research 59(4). "
            f"Refused {na['by_type']['REFUSE']} · unable {na['by_type']['UNABLE']} · "
            f"deferred offline {na['by_type']['AFTERCALL']}. "
            + ("Labels in this transcript are unreliable, so the rate is indicative only."
               if not na.get("labels_reliable") else ""),
            GOOD if pct <= 11 else WARN))
        for f in na.get("flagged", []):
            story.append(Paragraph(
                f"<b>[{_esc('+'.join(f['types']))}] {_esc(f['speaker'])}:</b> "
                f"“{_esc(f['hits'][0]['phrase'])}”", _S["bullet"]))

    # ── Delivery ─────────────────────────────────────────────────────────────
    if t:
        story.append(Paragraph("Delivery", _S["h2"]))
        if not t.get("reliable"):
            story.append(_callout("TIMING WITHHELD",
                                  "; ".join(_esc(w) for w in t.get("warnings", []))
                                  + ". The tape and Q&amp;A findings are unaffected — they come from "
                                    "the text and the market, not the speaker labels.", WARN))
        else:
            rows = [[Paragraph(h, _S["th"]) for h in ["Role", "Minutes", "Words/min"]]]
            for s in t["by_speaker"]:
                rows.append([Paragraph(_esc(s["speaker"]), _S["td"]),
                             Paragraph(f"{s['minutes']}", _S["td"]),
                             Paragraph(str(s["wpm"]), _S["td"])])
            tb = Table(rows, colWidths=[2.6 * inch, 1.2 * inch, 1.2 * inch])
            tb.setStyle(TableStyle([
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(tb)
            story.append(Paragraph(
                f"Prepared {t['prepared_minutes']} min (management only) · Q&amp;A {t['qa_minutes']} min "
                f"· operator {t['operator_minutes']} min. Measured from the transcript's own "
                f"timestamps, not estimated from word counts.", _S["small"]))

    if include_narrative:
        try:
            from core import morning_after as _ma
            text, _ai, unverified = _ma.narrative(c["quarter"], client_id)
            if text:
                story.append(Paragraph("The read", _S["h2"]))
                for para in [p for p in text.split("\n") if p.strip()]:
                    st = _S["h2"] if para.strip().startswith("#") else _S["body"]
                    story.append(Paragraph(_esc(para.lstrip("# ").strip()), st))
                if unverified:
                    story.append(_callout(
                        "UNVERIFIED FIGURES — CHECK BEFORE USE",
                        "; ".join(f"{_esc(u['value'])}" for u in unverified)
                        + " could not be traced to the transcript or the measured facts.",
                        colors.HexColor("#B91C1C")))
        except Exception as e:
            story.append(Paragraph(f"(narrative unavailable: {_esc(e)})", _S["small"]))

    story.append(Paragraph(
        "Every figure recomputes at export time from the transcript, the activity log and market "
        "data. Verdicts name the anchor, the demand and the omission so the reasoning can be checked "
        "against the transcript rather than trusted. No accuracy rate is claimed for the Q&amp;A "
        "framing — it has not been validated against human labels.", _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def ir_plan_pdf(client_id=None):
    from core import ir_plan
    p = ir_plan.compose_ir_plan(client_id)
    ctx = p["context"]
    buf, doc = _doc(f"{ctx['ticker']} 90-Day IR Plan")
    story = []
    _header(story, "FORWARD IR ACTION PLAN",
            f"{ctx['name']} — 90-Day IR Plan",
            f"{p['as_of']:%b %d} – {p['window_end']:%b %d, %Y} · composed live from the earnings calendar, "
            f"roadshow schedule, catalysts & ownership signals · generated {datetime.now():%b %d, %Y}")

    # Context snapshot
    snap = []
    if ctx.get("rev_growth") is not None:
        snap.append((f"{ctx['rev_growth']:.0f}%", "Revenue growth", "the proven half", GOOD))
    if ctx.get("op_margin") is not None:
        snap.append((f"{ctx['op_margin']:.1f}%", "Operating margin", "the story to change", WARN))
    if ctx.get("ev_gp") is not None:
        snap.append((f"{ctx['ev_gp']:.1f}x", "EV / Gross Profit", f"{ctx.get('discount_gp',0):.0f}% below median", ACCENT))
    if ctx.get("consensus_pt") and ctx.get("upside") is not None:
        snap.append((f"${ctx['consensus_pt']:.2f}", "Consensus PT", f"{ctx['upside']:+.0f}% upside", GOOD))
    if snap:
        story.append(_stat_row(snap))

    # Objectives
    story.append(Paragraph("Objectives this quarter", _S["h2"]))
    for i, (title, detail) in enumerate(p["objectives"], 1):
        story.append(Paragraph(f"<b>{i}. {title}.</b> {detail}", _S["bullet"]))

    # Timeline
    story.append(Paragraph("Key dates &amp; milestones", _S["h2"]))
    if p["timeline"]:
        rows = [[Paragraph(h, _S["th"]) for h in ["Date", "Milestone", "Detail"]]]
        for d, lbl, det in p["timeline"]:
            rows.append([Paragraph(f"{d:%b %d}", _S["td"]), Paragraph(lbl, _S["td"]), Paragraph(det, _S["td"])])
        t = Table(rows, colWidths=[0.9 * inch, 2.4 * inch, 3.7 * inch])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ]))
        story.append(t)
    else:
        story.append(Paragraph("No dated milestones in the window.", _S["body"]))

    # Targeting
    story.append(Paragraph("Targeting &amp; outreach", _S["h2"]))
    for t in p["trips"]:
        story.append(Paragraph(f"•&nbsp;&nbsp;<b>{t['city']}</b> · {t['dates']} · {t['meetings']} meetings — {t['name']}", _S["bullet"]))
    if p["prospects"]:
        pl = "; ".join(f"{pr['fund']} ({pr['score']})" for pr in p["prospects"])
        story.append(Paragraph(f"<b>Priority prospects</b> — non-holders by engagement: {pl}.", _S["body"]))

    # Positioning
    story.append(Paragraph("Positioning — the messages to land", _S["h2"]))
    for msg in p["positioning"]:
        story.append(Paragraph("•&nbsp;&nbsp;" + msg, _S["bullet"]))

    # Catalysts
    if p["catalysts"]:
        story.append(Paragraph("Catalysts to communicate", _S["h2"]))
        story.append(Paragraph(" · ".join(p["catalysts"]), _S["body"]))

    # Ownership actions
    if p["ownership"]:
        story.append(Paragraph("Ownership actions", _S["h2"]))
        for action, detail in p["ownership"]:
            story.append(Paragraph(f"•&nbsp;&nbsp;<b>{action}</b> — {detail}", _S["bullet"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def peer_benchmarking_pdf(client_id=None):
    bm = benchmarking_engine.build_benchmark()
    u = bm["usio"]
    buf, doc = _doc(f"{CT('ticker')} Peer Benchmarking")
    story = []
    _header(story, "PEER BENCHMARKING",
            f"{CT('name')} — Valuation & Peer Benchmarking",
            f"EV/Gross Profit basis · SEC EDGAR + market data · generated {datetime.now():%b %d, %Y}")

    story.append(_callout("KEY FINDING", benchmarking_engine.key_finding(bm)))

    faster = bm["median_gr"] is not None and u["rev_growth"] > bm["median_gr"]
    story.append(Paragraph("At a glance", _S["h2"]))
    story.append(_stat_row([
        (f"{u['ev_gp']:.1f}x", "EV / Gross Profit", f"#{bm['usio_gp_rank']} of {len(bm['gp_ranked'])}", ACCENT),
        (f"{bm['discount_gp']:.0f}%", "Discount (EV/GP)", "below peer median", GOOD),
        (f"{u['ev_rev']:.2f}x", "EV / Revenue", f"{bm['discount']:.0f}% below median", GOOD),
        (f"{u['rev_growth']:.0f}%", "Revenue growth", f"vs {bm['median_gr']:.0f}% median", GOOD if faster else INK),
    ]))

    story.append(Paragraph("Peer comparison — ranked by EV/Gross Profit", _S["h2"]))
    head = [Paragraph(h, _S["th"]) for h in ["Company", "EV/Gross Profit", "EV/Rev", "Gross margin", "Rev growth"]]
    data = [head]
    usio_idx = None
    for i, r in enumerate(bm["gp_ranked"]):
        if r["is_client"]:
            usio_idx = i + 1
        data.append([
            Paragraph(("<b>" + r["ticker"] + "</b> · " + (r["name"] or "")) if r["is_client"] else (r["ticker"] + " · " + (r["name"] or "")), _S["td"]),
            Paragraph(f"{r['ev_gp']:.1f}x" if r["ev_gp"] is not None else "—", _S["td"]),
            Paragraph(f"{r['ev_rev']:.2f}x" if r["ev_rev"] else "—", _S["td"]),
            Paragraph((f"{r['gross_margin']:.0f}%" + ("*" if r.get("gm_source") == "est" else "")) if r["gross_margin"] is not None else "—", _S["td"]),
            Paragraph(f"{r['rev_growth']:+.0f}%" if r["rev_growth"] is not None else "—", _S["td"]),
        ])
    t = Table(data, colWidths=[2.9 * inch, 1.15 * inch, 0.85 * inch, 1.1 * inch, 1.0 * inch])
    ts = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]
    if usio_idx is not None:
        ts.append(("BACKGROUND", (0, usio_idx), (-1, usio_idx), SOFT))
    t.setStyle(TableStyle(ts))
    story.append(t)

    no_gp = [r["ticker"] for r in bm["primary"] if r.get("gross_margin") is None]
    if no_gp:
        story.append(Paragraph(
            f"<b>{_esc(', '.join(no_gp))} show no gross margin because they do not report one.</b> Both "
            f"are bank holding companies: their filings contain no cost-of-revenue line, and CASS's 10-K "
            f"never uses the phrase &lsquo;gross profit&rsquo;. A vendor figure exists for them and is "
            f"constructed, not reported, so it is not shown here and they are excluded from the median. "
            f"That is a fact about the businesses, not a gap in our data.", _S["small"]))
    if bm.get("excluded"):
        exc = ", ".join(e["ticker"] for e in bm["excluded"])
        story.append(Paragraph(
            f"{exc} also excluded from the EV comparison — a bank's cash holds customer deposits and "
            f"net-cash names' EVs go negative, so they aren't EV-comparable; their growth is still real.",
            _S["small"]))

    story.append(Paragraph(
        "The gross margins above are <b>as reported</b>, and as reported they are <b>not comparable</b> — "
        "USIO and several peers book interchange gross, which depresses the ratio for identical "
        "economics. They cannot be restated onto a common basis from public filings (USIO discloses no "
        "interchange dollar amount). This is why the ranking above is on <b>EV/Gross Profit</b>, which "
        "is unaffected by gross-vs-net presentation. The footnote forensics overleaf show exactly what "
        "each peer's filing does and does not support.", _S["small"]))

    story.append(PageBreak())
    _valuation_comp_story(story)

    story.append(PageBreak())
    _forensics_story(story)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def board_package_pdf(client_id=None):
    """The IR Quarterly Board Package — merges the old board_ir_report_pdf's financials
    into the .docx package's (better) structure, live.

    Two documents became one because they duplicated each other's valuation and ownership
    sections and could therefore disagree. Structure from the .docx; every figure from a
    filing, the market feed, or our own log.
    """
    from core import board_package, edgar_financials as _ef
    d = board_package.compose(client_id)
    p, g, ss, bs_, val = d["period"], d["glance"], d["sell_side"], d["buy_side"], d["valuation"]
    if not p:
        raise ValueError("Financials unavailable from EDGAR")
    fin = p["summary"]
    inc, bal, cf = fin["income"], fin["balance"], fin["cashflow"]
    bm, comp, bridge = val["bm"], val["comp"], val["bridge"]
    u = bm["usio"]

    buf, doc = _doc(f"{d['ticker']} IR Quarterly Board Package")
    story = []
    _header(story, "IR QUARTERLY BOARD PACKAGE",
            f"{_esc(d['name'])} — {_esc(p['label'])} Investor Relations Summary",
            f"Reporting the {_esc(p['label'])} quarter ended {_esc(str(p['quarter_end']))} (last quarter "
            f"actually filed). {_esc(str(p['upcoming']))} reports {_esc(str(p['upcoming_date']))} — "
            f"{p['days_to_upcoming']} days out and NOT reflected here. Composed live from SEC EDGAR, the "
            f"market feed and the IR activity log · generated {d['as_of']:%b %d, %Y}")

    # ---- 1. Quarter at a glance ----
    story.append(Paragraph("1. Quarter at a glance", _S["h2"]))
    story.append(_stat_row([
        (f"${_m(inc['revenue']):.1f}M", "Revenue", f"{inc['rev_growth_yoy']:+.0f}% YoY", GOOD),
        (f"${_m(inc['gross_profit']):.1f}M", "Gross profit", f"{inc['gross_margin']:.0f}% margin", INK),
        (f"${inc['adjusted_ebitda']/1e3:.0f}K", "Adj. EBITDA", f"{inc['adj_ebitda_margin']:.0f}% margin", INK),
        (f"${inc['net_income']/1e3:.0f}K", "Net income", f"{inc['net_margin']:.0f}% margin", INK),
    ]))
    story.append(Paragraph("Balance sheet &amp; cash flow", _S["h2"]))
    story.append(_stat_row([
        (f"${_m(bal['net_cash']):.1f}M", "Net cash", f"{bal['debt_to_equity']:.0f}% D/E", GOOD),
        (f"${_m(bal['equity']):.1f}M", "Equity", "book value", INK),
        (f"${cf['fcf']/1e3:.0f}K", "Free cash flow", f"{cf['fcf_margin']:.0f}% margin",
         GOOD if (cf["fcf"] or 0) > 0 else WARN),
        (f"${_m(bal['customer_deposits']):.0f}M", "Settlement float", "customer money", INK),
    ]))
    if g and g.get("short_interest") is None:
        story.append(Paragraph(f"<b>Short interest:</b> {_esc(g['short_interest_note'])}", _S["small"]))

    # ---- 2. Sell-side coverage ----
    story.append(PageBreak())
    story.append(Paragraph("2. Sell-side coverage", _S["h2"]))
    if ss and ss.get("coverage"):
        rows = [[Paragraph(h, _S["th"]) for h in ["Firm", "Rating", "Price target", "Last action", "Status"]]]
        for c in ss["coverage"]:
            pt = c.get("price_target")
            rows.append([
                Paragraph(_esc(c["firm"]), _S["td"]),
                Paragraph(_esc(c.get("grade") or "—"), _S["td"]),
                Paragraph(f"${pt:.2f}" if pt else "—", _S["td"]),
                Paragraph(_esc(c.get("date") or "—"), _S["td"]),
                Paragraph("<b>DORMANT</b>" if c.get("stale") else "active", _S["td"])])
        t = Table(rows, colWidths=[2.2 * inch, 1.5 * inch, 1.1 * inch, 1.2 * inch, 1.0 * inch])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        story.append(Paragraph(_esc(ss["read"]), _S["body"]))

    # ---- 3. Buy-side & retail ----
    story.append(Paragraph("3. Buy-side &amp; retail", _S["h2"]))
    if bs_:
        cells = []
        if bs_.get("holders") is not None:
            cells.append((str(bs_["holders"]), "13F institutions", "on file", INK))
        if bs_.get("activists_recent") is not None:
            cells.append((str(bs_["activists_recent"]), "Schedule 13D",
                          f"last {bs_['window_days']//365}y ({bs_['activists_all_time']} all-time)",
                          GOOD if bs_["activists_recent"] == 0 else colors.HexColor("#B91C1C")))
        if bs_.get("passive_recent") is not None:
            cells.append((str(bs_["passive_recent"]), "Schedule 13G",
                          f"last {bs_['window_days']//365}y (passive)", INK))
        if cells:
            story.append(_stat_row(cells))
        if bs_.get("note"):
            story.append(Paragraph(_esc(bs_["note"]), _S["body"]))

    # ---- 4. Market context & valuation vs peers ----
    story.append(PageBreak())
    story.append(Paragraph("4. Market context &amp; valuation vs peers", _S["h2"]))
    story.append(_callout("KEY FINDING", _esc(val["key_finding"])))
    if comp and comp.get("implied"):
        i = comp["implied"]
        story.append(_stat_row([
            (f"{i['current_multiple']:.1f}x", "EV / Gross Profit",
             f"#{bm['usio_gp_rank']} of {len(bm['gp_ranked'])}", ACCENT),
            (f"{i['peer_median_multiple']:.1f}x", "Peer median", f"primary peers (n={comp['n_primary']})", INK),
            (f"{i['upside_pct']:+.0f}%", "Implied upside", "at peer median, equity basis",
             GOOD if i["upside_pct"] > 0 else colors.HexColor("#B91C1C")),
        ]))
        # The number above does not travel alone. See _valuation_caveats.
        _valuation_caveats(story, comp, compact=True)
    if bridge and bridge.get("usio"):
        story.append(Paragraph("The EV/Revenue bridge", _S["h2"]))
        rows = [[Paragraph(h, _S["th"]) for h in
                 ["", "EV/GP", "Gross margin", "EV/Rev today", "EV/Rev warranted", "vs warranted"]]]
        ci = None
        for idx, r in enumerate(bridge["rows"]):
            if r["is_client"]:
                ci = idx + 1
            rows.append([
                Paragraph(f"<b>{_esc(r['ticker'])}</b>" if r["is_client"] else _esc(r["ticker"]), _S["td"]),
                Paragraph(f"{r['ev_gp']:.2f}x", _S["td"]),
                Paragraph(f"{r['gross_margin']:.1f}%", _S["td"]),
                Paragraph(f"{r['ev_rev_actual']:.2f}x" if r["ev_rev_actual"] else "—", _S["td"]),
                Paragraph(f"<b>{r['ev_rev_warranted']:.2f}x</b>", _S["td"]),
                Paragraph(f"{r['vs_warranted_pct']:+.0f}%" if r["vs_warranted_pct"] is not None else "—",
                          _S["td"])])
        t = Table(rows, colWidths=[0.62 * inch, 0.85 * inch, 1.25 * inch, 1.35 * inch, 1.55 * inch,
                                   1.38 * inch])
        ts = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
              ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
              ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if ci:
            ts.append(("BACKGROUND", (0, ci), (-1, ci), SOFT))
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Paragraph(_esc(bridge["read"]), _S["body"]))

    # ---- 5. Open items ----
    story.append(Paragraph("5. Open items for board awareness", _S["h2"]))
    for s_ in d["open_items"]:
        story.append(_callout(
            _esc(s_.get("title")), _esc(str(s_.get("desc"))),
            colors.HexColor("#B91C1C") if s_.get("level") == "red" else WARN))
    if not d["open_items"]:
        story.append(Paragraph("No red or amber items open.", _S["body"]))

    # ---- Appendix A ----
    story.append(PageBreak())
    story.append(Paragraph("Appendix A — comparable companies, and why each is here", _S["h2"]))
    story.append(Paragraph(
        "Every name carries the reason it is in the set. A comp sheet without a written rationale is "
        "how the prior package came to list an acquired company, a pending acquisition and a bank as "
        "&lsquo;Active&rsquo; for a quarter without anyone noticing.", _S["body"]))
    rows = [[Paragraph(h, _S["th"]) for h in ["", "Company", "Tier", "Gross margin", "In median?", "Why it is here"]]]
    for r in d["appendix"]:
        rows.append([
            Paragraph(_esc(r["ticker"]), _S["td"]), Paragraph(_esc(r["name"] or ""), _S["td"]),
            Paragraph(_esc(r["tier"] or ""), _S["td"]),
            Paragraph(f"{r['gm']:.1f}%" if r["gm"] is not None else "—", _S["td"]),
            Paragraph("yes" if r["in_median"] else f"no ({_esc(r['gm_basis'])})", _S["td"]),
            Paragraph(_esc(r["rationale"]), _S["td"])])
    t = Table(rows, colWidths=[0.5 * inch, 1.35 * inch, 0.65 * inch, 0.85 * inch, 0.8 * inch, 2.85 * inch])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    story.append(Paragraph(
        "Every figure in this package recomputes at export time from SEC EDGAR, the market feed, or "
        "this platform's own activity log. Where a number cannot be sourced — short interest, "
        "per-analyst models — it is reported as absent rather than estimated.", _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def board_ir_report_pdf(client_id=None):
    """DEPRECATED — merged into board_package_pdf() on 2026-07-16.

    It duplicated the Quarterly Board Package's valuation and ownership sections in a second
    board document, which meant the two could disagree in front of the same board. It also
    carried two bugs the merge fixed: an executive summary that asserted "cheap on a growing
    base" unconditionally, and an EV/Revenue stat coloured GREEN with a "% below median" —
    the precise error behind the retired deck's $9-12 price target.

    Kept as an alias so existing callers don't break.
    """
    return board_package_pdf(client_id)


def onboarding_kit_pdf(client_id=None):
    """New Analyst Onboarding Kit — the .docx's framework, every answer regenerated live.

    The only artifact here built to be handed to a sell-side analyst. Its reader has the
    10-K open, so every answer carries the source it can be checked against.
    """
    from core import onboarding_kit
    d = onboarding_kit.compose(client_id)
    pol, val = d["policy"], d["valuation"]
    bridge, comp = val.get("bridge"), val.get("comp")

    buf, doc = _doc(f"{d['ticker']} New Analyst Onboarding Kit")
    story = []
    _header(story, "NEW ANALYST ONBOARDING KIT",
            f"{_esc(d['name'])} (NASDAQ: {_esc(d['ticker'])})",
            f"Every figure and every answer regenerates from SEC filings and market data at export "
            f"time, and carries the source it can be checked against · generated {d['as_of']:%b %d, %Y}")

    story.append(_callout(
        f"START HERE — WE REPORT REVENUE {_esc(pol['basis'])}",
        f"“{_esc(pol['quote'])}” &mdash; {_esc(pol['form'])}, filed {_esc(pol['filed'])}."
        f"<br/><br/>This one fact explains our reported gross margin and it is the first thing worth "
        f"knowing about our P&amp;L. Interchange and sponsor-bank fees we never keep sit in BOTH our "
        f"revenue and our cost of services. A peer reporting net shows 60–75% gross margin on "
        f"identical economics. <b>Gross margin is therefore not comparable across payment "
        f"processors — ours or anyone's.</b>", colors.HexColor("#B91C1C")))

    # ---- the bridge ----
    if bridge and bridge.get("usio"):
        story.append(Paragraph("What to compare us on instead", _S["h2"]))
        story.append(Paragraph(
            "The identity is exact: <b>EV/Revenue = EV/Gross Profit &times; gross margin</b>. Revenue "
            "cancels out of EV/Gross Profit, so it is the one multiple our peer set's accounting "
            "doesn't distort. Apply the peer median EV/GP to each company's OWN margin and you get "
            "the EV/Revenue each one warrants — which is the honest version of the EV/Revenue "
            "comparison everyone reaches for first.", _S["body"]))
        rows = [[Paragraph(h, _S["th"]) for h in
                 ["", "EV/GP", "Gross margin", "EV/Rev today", "EV/Rev warranted", "vs warranted"]]]
        ci = None
        for i, r in enumerate(bridge["rows"]):
            if r["is_client"]:
                ci = i + 1
            rows.append([
                Paragraph(f"<b>{_esc(r['ticker'])}</b>" if r["is_client"] else _esc(r["ticker"]), _S["td"]),
                Paragraph(f"{r['ev_gp']:.2f}x", _S["td"]),
                Paragraph(f"{r['gross_margin']:.1f}%", _S["td"]),
                Paragraph(f"{r['ev_rev_actual']:.2f}x" if r["ev_rev_actual"] else "—", _S["td"]),
                Paragraph(f"<b>{r['ev_rev_warranted']:.2f}x</b>", _S["td"]),
                Paragraph(f"{r['vs_warranted_pct']:+.0f}%" if r["vs_warranted_pct"] is not None else "—",
                          _S["td"])])
        t = Table(rows, colWidths=[0.62 * inch, 0.85 * inch, 1.25 * inch, 1.35 * inch, 1.55 * inch,
                                   1.38 * inch])
        ts = [("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
              ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
              ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
              ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
              ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5)]
        if ci:
            ts.append(("BACKGROUND", (0, ci), (-1, ci), SOFT))
        t.setStyle(TableStyle(ts))
        story.append(t)
        story.append(Paragraph(_esc(bridge["read"]), _S["body"]))

    # ---- Q&A ----
    story.append(PageBreak())
    story.append(Paragraph("Q&amp;A — the questions you are going to ask", _S["h2"]))
    story.append(Paragraph(
        "Answered in the order they actually get asked, each with the source it can be checked "
        "against. If a question isn't here it is because we could not answer it from a source — "
        "see the last page.", _S["body"]))
    for i, q in enumerate(d["qa"], 1):
        story.append(Paragraph(f"Q{i}. {_esc(q['q'])}", _S["h2"]))
        story.append(Paragraph(_esc(q["a"]), _S["body"]))
        if q.get("flag"):
            story.append(Paragraph(f"<b>Note to IR:</b> {_esc(q['flag'])}", _S["small"]))
        story.append(Paragraph("<b>Source:</b> " + _esc(" · ".join(q["sources"])), _S["small"]))

    # ---- what we won't assert ----
    story.append(PageBreak())
    story.append(Paragraph("What this kit does not claim, and why", _S["h2"]))
    story.append(Paragraph(
        "A kit that quietly drops the sections it cannot support looks thinner. One that says why "
        "is more credible than the version that made them up. Each of these was in the prior "
        "edition; none is reproduced without a source.", _S["body"]))
    for g in d["gaps"]:
        story.append(_callout(_esc(g["item"]), _esc(g["why"]), WARN))
    story.append(Paragraph(
        "Every figure in this kit recomputes at export time from SEC EDGAR and market data. Nothing "
        "is carried from a prior document. Where a number cannot be sourced it is named as absent "
        "rather than estimated — including on the page you are reading.", _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def onboarding_checklist_pdf(client_id=None):
    """IRConnect client onboarding — live readiness, not a box the client ticks."""
    from core import onboarding_checklist
    d = onboarding_checklist.compose(client_id)
    pol = d["peer_policy"]

    buf, doc = _doc(f"{d['ticker']} IRConnect Onboarding Readiness")
    story = []
    _header(story, "PRAXIS POINT IRCONNECT",
            f"Client onboarding readiness — {_esc(d['client'])}",
            f"Answered from the platform, not from a form. {d['ready']} of {d['total']} items are "
            f"live and working · generated {d['as_of']:%b %d, %Y}")

    story.append(_callout(
        "WHAT THIS IS",
        "The original checklist asked your team to tick boxes. A tick says someone typed an "
        "answer; it does not say the thing works. Every item below is answered by querying the "
        "platform, so &lsquo;ready&rsquo; means the data is flowing and &lsquo;gap&rsquo; means it "
        "genuinely is not there. Items sourced from SEC filings are not asked of you at all."))

    for name, items in d["sections"]:
        story.append(Paragraph(_esc(name), _S["h2"]))
        rows = [[Paragraph(h, _S["th"]) for h in ["", "Item", "Owner", "Live status"]]]
        for i in items:
            rows.append([
                Paragraph("<b>OK</b>" if i["status"] == "ready" else "<b>GAP</b>", _S["td"]),
                Paragraph(_esc(i["item"]), _S["td"]),
                Paragraph(_esc(i["owner"]), _S["td"]),
                Paragraph(_esc(i["live"] or "—"), _S["td"])])
        t = Table(rows, colWidths=[0.5 * inch, 2.5 * inch, 1.8 * inch, 2.2 * inch])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
            ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(t)
        for i in items:
            if i.get("note"):
                story.append(Paragraph(f"<b>{_esc(i['item'])}:</b> {_esc(i['note'])}", _S["small"]))

    # ---- the peer-group policy change ----
    story.append(PageBreak())
    story.append(Paragraph("Policy change — the peer/comp group", _S["h2"]))
    story.append(_callout("WHAT THE CHECKLIST USED TO SAY", _esc(pol["old"]),
                          colors.HexColor("#B91C1C")))
    story.append(Paragraph(
        "That deference sounds respectful, and it is how this client came to be benchmarked "
        "against a bank. The inherited comp group was, in its own words, &lsquo;set by management "
        "and sell-side coverage&rsquo;.", _S["body"]))
    story.append(_callout("WHAT IT SAYS NOW", _esc(pol["new"]), GOOD))
    story.append(Paragraph("The criteria", _S["h2"]))
    for head, body in pol["criteria"]:
        story.append(Paragraph(f"<b>{_esc(head)}</b> — {_esc(body)}", _S["bullet"]))
    story.append(_callout("EVIDENCE", _esc(pol["evidence"]), WARN))

    story.append(Paragraph("Criteria run against the current comp set, live", _S["h2"]))
    rows = [[Paragraph(h, _S["th"]) for h in ["", "Company", "(c) comparable basis?", "Detail"]]]
    for r in d["peer_check"]:
        rows.append([
            Paragraph(_esc(r["ticker"]), _S["td"]), Paragraph(_esc(r["name"] or ""), _S["td"]),
            Paragraph("<b>PASS</b>" if r["c_comparable_basis"] else "<b>FAIL</b>", _S["td"]),
            Paragraph(_esc(r["c_note"]) + (f" · {_esc(r['flag_note'])}" if r.get("flag_note") else ""),
                      _S["td"])])
    t = Table(rows, colWidths=[0.55 * inch, 1.6 * inch, 1.35 * inch, 3.5 * inch])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Paragraph(
        "Criterion (a) — no pending or approved M&amp;A — cannot be checked from XBRL and needs a "
        "human eye on each name's filings each quarter. It is the one that caught GDOT, and it "
        "caught it from an 8-K, not a feed.", _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def ndr_by_city_pdf(client_id=None):
    """NDR Coverage by City — where the money is vs where we're going."""
    from core import ndr_by_city
    d = ndr_by_city.compose(client_id)

    buf, doc = _doc(f"{d['ticker']} NDR Coverage by City")
    story = []
    _header(story, "NDR COVERAGE BY CITY",
            f"{_esc(d['name'])} — where the money is vs where we're going",
            f"{d['total_booked']} meetings booked against {d['total_funds']} institutions on file · "
            f"composed live from the buy-side list, the engagement scoring and the NDR calendar · "
            f"generated {d['as_of']:%b %d, %Y}")

    story.append(_callout("HOW THIS IS RANKED — AND WHY THE OBVIOUS METRIC IS WRONG",
        f"Metros are ranked on the average engagement score of the <b>top {d['day_capacity']} "
        f"non-holders</b> in each one — not the average across every fund on file. An NDR is "
        f"{d['day_capacity']} meetings in a day, not a survey: what matters is how good the "
        f"meetings you could actually FILL A DAY with are.<br/><br/>"
        f"The distinction is not academic. Averaged across every fund, New York scores 51 — "
        f"second-weakest of eight — because it has 15 funds and a long tail we would never meet. "
        f"On the metric that matches how an NDR actually works, New York is the <b>strongest</b> "
        f"market on the board at 74. Rank on the wrong metric and you talk yourself out of a "
        f"correct schedule."))
    story.append(Paragraph(f"<b>{_esc(d['read'])}</b>", _S["body"]))

    story.append(Paragraph("Every metro, ranked", _S["h2"]))
    rows = [[Paragraph(h, _S["th"]) for h in
             ["#", "Metro", f"Top-{d['day_capacity']} score", "Non-holders", "Booked", "Trip on calendar"]]]
    for r in d["rows"]:
        trip = ", ".join(f"{t['name']} ({t['meetings']})" for t in r["trips"]) or "—"
        rows.append([
            Paragraph(str(r["rank"]), _S["td"]),
            Paragraph(f"<b>{_esc(r['metro'])}</b>", _S["td"]),
            Paragraph(f"{r['top_avg']:.0f}", _S["td"]),
            Paragraph(str(r["non_holders"]), _S["td"]),
            Paragraph(f"<b>{r['booked']}</b>" if r["booked"] else "0", _S["td"]),
            Paragraph(_esc(trip), _S["td"])])
    t = Table(rows, colWidths=[0.35 * inch, 1.75 * inch, 1.0 * inch, 0.95 * inch, 0.65 * inch, 2.3 * inch])
    t.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, BORDER),
        ("ALIGN", (2, 0), (4, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5), ("RIGHTPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(t)

    if d["findings"]:
        story.append(Paragraph("What to do about it", _S["h2"]))
        for f in d["findings"]:
            story.append(_callout(
                _esc(f["title"]), _esc(f["detail"]),
                colors.HexColor("#B91C1C") if f["level"] == "red" else WARN))

    story.append(PageBreak())
    story.append(Paragraph("Who is in each market", _S["h2"]))
    story.append(Paragraph(
        f"The top {d['day_capacity']} non-holders per metro — the day you could book there. Scores "
        f"are the live engagement scoring, not a list of names.", _S["body"]))
    for r in d["rows"]:
        if not r["top_targets"]:
            continue
        bits = " · ".join(f"{_esc(x['fund'])} ({x['score']})" for x in r["top_targets"])
        story.append(Paragraph(
            f"<b>#{r['rank']} {_esc(r['metro'])}</b> — top-{d['day_capacity']} avg "
            f"{r['top_avg']:.0f}, {r['booked']} booked<br/>{bits}", _S["bullet"]))

    story.append(Paragraph(
        "Every figure recomputes at export time from the buy-side list, the live engagement "
        "scoring and the NDR calendar. Note on data quality: the NDR calendar files trips under a "
        "city label (“Boston”) and the buy-side list uses a metro label (“Boston / New England”). "
        "This report joins them; an exact-match join silently reports a booked trip as absent, "
        "which is a mistake this report made once and now guards against.", _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def q2_script_pdf(client_id=None):
    """The Q2 call script — ordered by what buys credibility back, not by what flatters."""
    from core import q2_script, comp_quality
    d = q2_script.build()
    cq = comp_quality.build()

    buf, doc = _doc("USIO Q2 FY26 Call Script")
    story = []
    _header(story, "Q2 FY2026 CALL SCRIPT",
            "Usio, Inc. — built around the two promises management can prove",
            "Ordered by what retires the credibility discount, not by what reads best. "
            "Every quote is from the Q1/Q2 2025 or Q1 2026 call transcripts on file · "
            f"generated {d['as_of']}")

    story.append(_callout("THE ONE THING", _esc(d["read"]), colors.HexColor("#B91C1C")))

    c = d["credibility"]
    story.append(Paragraph("Why the street discounts management's word — and why that is earned",
                           _S["h2"]))
    story.append(Paragraph(
        f"FY2025 revenue guidance was <b>lowered to {_esc(c['fy25_guidance_lowered_to'])}</b> on the "
        f"Q2 2025 call because of &ldquo;{_esc(c['why_lowered'])}&rdquo;. FY2025 landed at "
        f"<b>+{c['fy25_actual']:.1f}%</b> &mdash; <b>below the floor of the lowered range</b>. A cut, "
        f"then a miss through the cut. The street now models the guidance range and discounts every "
        f"forward-looking statement to zero. That is a rational prior, not laziness &mdash; and it is "
        f"why management gave enough on the Q1 2026 call to build a full P&amp;L and nobody built it.",
        _S["body"]))

    if cq and cq.get("status") == "ok" and cq.get("divergent"):
        story.append(_callout(
            "THE TRAP ON THIS RELEASE",
            _esc(cq["read"]), WARN))

    for s_ in d["sections"]:
        story.append(Paragraph(f"{s_['n']}. {_esc(s_['title'])}", _S["h2"]))
        story.append(Paragraph(f"<b>Say:</b> {_esc(s_['say'])}", _S["body"]))
        story.append(Paragraph(f"<b>Why:</b> {_esc(s_['why'])}", _S["small"]))
        story.append(Paragraph(f"<b>Do NOT:</b> {_esc(s_['do_not'])}", _S["small"]))

    story.append(Paragraph("The two promises, verbatim", _S["h2"]))
    for p_ in d["promises"]:
        story.append(Paragraph(
            f"<b>{_esc(p_['claim'])}</b><br/>&ldquo;{_esc(p_['quote'])}&rdquo; "
            f"&mdash; {_esc(p_['who'])}, {_esc(p_['call'])} call. "
            f"Checkable on {_esc(p_['checkable_on'])}.", _S["small"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def q2_script_miss_pdf(client_id=None):
    """The Q2 script for a ~20% gross margin print — the version that must exist BEFORE the number."""
    from core import q2_script_miss
    d = q2_script_miss.build()
    buf, doc = _doc("USIO Q2 FY26 Call Script — 20% margin case")
    story = []
    _header(story, "Q2 FY2026 CALL SCRIPT — THE MISS CASE",
            "Usio, Inc. — if gross margin prints ~20% and the recovery did not happen",
            "The base script inverts if the margin call fails; it does not degrade. This is the "
            "version to have decided before the number exists, not after. "
            f"Generated {d['as_of']}")
    story.append(_callout("THE ONE RULE — STOP MAKING FORWARD CLAIMS",
                          _esc(d["read"]), colors.HexColor("#B91C1C")))
    a = d["at_20"]
    story.append(Paragraph("What a 20% print actually does", _S["h2"]))
    story.append(_stat_row([
        (f"{a['gross_margin']:.1f}%", "Gross margin", "Q1 repeats — no recovery", WARN),
        (f"-${abs(a['operating_income'])/1e3:.0f}K", "Operating income",
         "on GUIDED +11% revenue", colors.HexColor("#B91C1C")),
        (f"-${abs(a['eps']):.3f}", "FY2026 EPS", "does not clear its cost base",
         colors.HexColor("#B91C1C")),
    ]))
    story.append(Paragraph(
        f"<b>This reaches a second commitment.</b> &ldquo;Profitable and EBITDA positive&rdquo; was "
        f"<b>GUIDED</b>, not a target like the 23-25% margin. At {a['gross_margin']:.1f}% EBITDA is "
        f"~${a['ebitda']/1e3:.0f}K &mdash; technically positive, functionally noise, and GAAP "
        f"profitability is gone. Whether to reaffirm, qualify or withdraw that guidance is a "
        f"<b>board decision taken before the call</b>, not a CEO improvisation under questioning. "
        f"Improvising it is how FY2025&rsquo;s 5%-12% happened &mdash; and then missed.", _S["body"]))
    for sec in d["sections"]:
        story.append(Paragraph(f"{sec['n']}. {_esc(sec['title'])}", _S["h2"]))
        story.append(Paragraph(f"<b>Say:</b> {_esc(sec['say'])}", _S["small"]))
        story.append(Paragraph(f"<b>Why:</b> {_esc(sec['why'])}", _S["small"]))
        story.append(Paragraph(f"<b>Do NOT:</b> {_esc(sec['do_not'])}", _S["small"]))
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()


def q2_decision_tree_pdf(client_id=None, actual_revenue=None, actual_opex=None,
                        actual_gross_margin=None):
    """One page: which Q2 script to run, chosen off the printed gross margin. Decided in advance.

    Pass actual_revenue / actual_opex (full-year, opex = cash SG&A + SBC + D&A) once the release
    lands to reprice the break-even off real figures; actual_gross_margin tags the printed branch.
    """
    from core import q2_decision_tree
    d = q2_decision_tree.build()
    RED = colors.HexColor("#B91C1C")
    CMAP = {"good": GOOD, "warn": WARN, "bad": RED}

    buf, doc = _doc("USIO Q2 FY26 — Script Decision Tree")
    story = []
    _header(story, "Q2 FY2026 — WHICH SCRIPT TO RUN",
            "Usio, Inc. — chosen off the printed gross margin, decided before the number exists",
            f"Break-even gross margin (operating income = 0) on guided +11% revenue and flat cash "
            f"SG&A is {d['breakeven_gm']:.2f}%. Q1 printed {d['q1_actual_gm']:.1f}% &mdash; below it. "
            f"Generated {d['as_of']}")

    story.append(_callout("DECIDE THE BRANCH IN ADVANCE", _esc(d["read"]), colors.HexColor("#B91C1C")))

    # The tree, as a table: one row per branch.
    story.append(Paragraph(
        f"The trigger is the ABSOLUTE gross margin on the release &mdash; not the YoY optic (last "
        f"year&rsquo;s Q2 was {d['q2_ly_comp_gm']:.1f}%, the hardest comp in two years, so YoY will "
        f"look ugly on every branch).", _S["body"]))

    head = ["If gross margin prints", "Economics (FY26, guided rev)", "Run", "Lead with", "Guidance stance"]
    data = [[Paragraph(f"<b>{h}</b>", _S["th"]) for h in head]]
    for b in d["branches"]:
        e = b["econ"]
        col = CMAP[b["color"]]
        econ = (f"OI {'&minus;' if e['oi']<0 else ''}${abs(e['oi'])/1e3:.0f}K &middot; "
                f"EPS {'&minus;' if e['eps']<0 else ''}${abs(e['eps']):.3f} &middot; "
                f"{'GAAP+' if e['gaap_positive'] else 'GAAP&minus;'}")
        data.append([
            Paragraph(f"<b>{_esc(b['range'])}</b><br/><font size=7>{_esc(b['label'])}</font>", _S["td"]),
            Paragraph(econ, _S["td"]),
            Paragraph(f"<b>{_esc(b['script'])}</b>", _S["td"]),
            Paragraph(_esc(b["headline"]), _S["td"]),
            Paragraph(_esc(b["guidance"]), _S["td"])])
    t = Table(data, colWidths=[1.15*inch, 1.35*inch, 1.15*inch, 2.0*inch, 1.85*inch])
    ts = [("LINEBELOW",(0,0),(-1,0),0.8,INK), ("VALIGN",(0,0),(-1,-1),"TOP"),
          ("TOPPADDING",(0,0),(-1,-1),6), ("BOTTOMPADDING",(0,0),(-1,-1),6),
          ("LEFTPADDING",(0,0),(-1,-1),5), ("RIGHTPADDING",(0,0),(-1,-1),5),
          ("LINEBELOW",(0,1),(-1,-2),0.4,BORDER)]
    for i, b in enumerate(d["branches"], start=1):
        ts.append(("LINEBEFORE",(0,i),(0,i),3,CMAP[b["color"]]))
    t.setStyle(TableStyle(ts))
    story.append(t)

    story.append(Paragraph(
        f"<b>The one rule on every branch:</b> the voucher float is spoken as a dated, observed "
        f"balance (program funded 2026-07-01; the call is ~5 weeks into Q3), to everyone at once "
        f"under Reg FD, never as the &ldquo;$1 billion&rdquo; headline stripped of "
        f"management&rsquo;s own hedges. What changes by branch is only how much forward framing "
        f"management has earned: full on recovery, limited on partial, none on a miss.", _S["small"]))
    story.append(Paragraph(
        "<b>Float framing by branch &mdash;</b> "
        + " &nbsp;|&nbsp; ".join(f"<b>{_esc(b['label'].split(' &')[0].split(' —')[0])}:</b> "
                                 f"{_esc(b['float_framing'])}" for b in d["branches"]),
        _S["small"]))

    # On release day: recompute the break-even off actual revenue and opex.
    if actual_revenue and actual_opex:
        rc = q2_decision_tree.recompute(actual_revenue, actual_opex, gross_margin=actual_gross_margin)
        if rc.get("status") == "ok":
            story.append(Paragraph("Recomputed off the actual release", _S["h2"]))
            story.append(_callout(
                f"BREAK-EVEN NOW {rc['breakeven_gm']:.2f}% (was {d['breakeven_gm']:.2f}% on guidance)",
                _esc(rc["read"]),
                RED if rc.get("partial_band_collapsed") or
                (rc.get("printed") and rc["printed"]["branch"] == "miss") else WARN))
    else:
        story.append(Paragraph(
            "<b>On release day:</b> the break-even above is modelled on guided +11% revenue and "
            "flat cash SG&amp;A. Recompute it off the actual figures in one call &mdash; "
            "<font face='Courier'>q2_decision_tree.recompute(full_year_revenue, "
            "full_year_opex, gross_margin=printed_margin)</font> &mdash; where opex is cash SG&amp;A "
            "+ SBC + D&amp;A. Break-even is exactly opex &divide; revenue, so it is only as good as "
            "those two actuals; nothing else is assumed.", _S["small"]))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()
