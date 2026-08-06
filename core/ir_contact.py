"""core/ir_contact.py — identify the IR decision-maker at a prospect company + a draft outreach.

For a public company (by ticker) we need "who do we email about IRconnect?" Yahoo's
companyOfficers surfaces this surprisingly well: it usually lists the actual head of Investor
Relations, and always the CFO. So the ladder is: a real IR-titled officer → the CFO (the de
facto IR lead at most small/mid caps, clearly labelled as a default) → the CEO. Transcripts
aren't used here — we only hold transcripts for our own CLIENTS, and there's no free transcript
feed for cold prospects; Yahoo covers it.

enrich(ticker) returns the contact + firmographics + a suggested IR inbox (ir@domain, a real
address at many companies) — never a fabricated personal email; the operator confirms/edits the
recipient before anything sends.
"""
import re

import yfinance as yf


def _clean_name(n):
    n = re.sub(r"^(mr|ms|mrs|dr)\.?\s+", "", (n or "").strip(), flags=re.I)
    return re.sub(r"\s+", " ", n).strip()


def _domain(website):
    if not website:
        return None
    d = re.sub(r"^https?://", "", website.strip(), flags=re.I)
    d = re.sub(r"^www\.", "", d, flags=re.I).split("/")[0].strip()
    return d or None


def _officer(officers, *needles):
    for o in officers:
        t = (o.get("title") or "").lower()
        if any(n in t for n in needles):
            return o
    return None


def enrich(ticker):
    """Firmographics + the IR decision-maker for a ticker (Yahoo). ir_kind is 'ir' (a real IR
    officer), 'cfo' (default), 'ceo' (last resort), or 'none'."""
    info = yf.Ticker(ticker).info or {}
    offs = info.get("companyOfficers") or []
    ir = _officer(offs, "investor relations", "investor")
    cfo = _officer(offs, "cfo", "chief financial")
    ceo = _officer(offs, "chief executive", "ceo")
    if ir:
        dm, kind = ir, "ir"
    elif cfo:
        dm, kind = cfo, "cfo"
    elif ceo:
        dm, kind = ceo, "ceo"
    else:
        dm, kind = None, "none"
    dom = _domain(info.get("website"))
    n = info.get("numberOfAnalystOpinions")
    return {
        "ticker": ticker,
        "company": info.get("shortName") or info.get("longName") or ticker,
        "city": info.get("city"), "state": info.get("state"),
        "sector": info.get("sector"), "industry": info.get("industry"),
        "website": info.get("website"), "domain": dom,
        "market_cap": info.get("marketCap"),
        "analysts": (int(n) if n else 0) if n is not None else None,
        "ir_name": _clean_name(dm.get("name")) if dm else None,
        "ir_title": (dm.get("title") if dm else None),
        "ir_kind": kind,
        "ceo_name": _clean_name(ceo.get("name")) if ceo else None,
        "cfo_name": _clean_name(cfo.get("name")) if cfo else None,
        "phone": info.get("phone"),
        "suggested_email": (f"ir@{dom}" if dom else None),
        "summary": (info.get("longBusinessSummary") or "")[:600],
    }


def contact_label(e):
    """Human label for the decision-maker, noting when it's a default."""
    return {"ir": e.get("ir_title") or "Investor Relations",
            "cfo": "CFO — default IR contact",
            "ceo": "CEO — no IR/CFO listed",
            "none": "No contact found"}.get(e.get("ir_kind"), "")


def draft_email(e):
    """A personalized IRconnect prospecting draft that leads with the analyst-coverage signal."""
    first = (e.get("ir_name") or "").split(" ")[0] if e.get("ir_name") else "there"
    co = e.get("company") or e.get("ticker")
    n = e.get("analysts")
    cover = (f"you're covered by {n} sell-side analysts" if n
             else "your sell-side coverage is growing")
    subject = f"IRconnect for {co}"
    body = (
        f"Hi {first},\n\n"
        f"I follow {co} and noticed {cover} — and as coverage grows, so does the IR workload: "
        f"consensus wrangling, investor targeting, earnings-script prep, and Reg FD-safe Q&A.\n\n"
        f"IRconnect is an investor relations platform that computes that work from real, disclosed "
        f"data — investor targeting, guidance analytics, earnings-script prep, and risk monitoring.\n\n"
        f"Would you be open to a short walkthrough?\n\n"
        f"Best regards,\nPraxis Point\npraxispointir.com")
    return {"subject": subject, "body": body}
