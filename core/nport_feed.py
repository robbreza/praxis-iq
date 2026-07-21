"""core/nport_feed.py — mutual fund & ETF holders via SEC Form N-PORT.

'40-Act registered funds report their holdings monthly on Form N-PORT — a fund-level ownership lens
the 13F manager-level view doesn't cleanly give, and it catches funds that don't file 13F at all.
Reverse lookup by the issuer's CUSIP through EDGAR full-text search (efts), deduped to the most
recent N-PORT per fund. Free, authoritative, no key — reuses core.sec_filings for CUSIP + the SEC
User-Agent.

MVP scope: NAMES the funds holding the stock + their latest N-PORT date (a real ownership
cross-check). Exact position size lives inside each large N-PORT XML — that deeper parse is deferred
(a "Premium"-tier build). Nothing fabricated; empty means none were found (or the fetch failed).
"""
import datetime
import re

from config.client_config import CT, get_active_client_id
from core import db, sec_filings

_STORE_KEY = "nport_holders.json"
_EFTS = "https://efts.sec.gov/LATEST/search-index"
_CIK_RE = re.compile(r"\(CIK\s*(\d+)\)", re.I)


def _cusip_for(cid, tk):
    """The issuer CUSIP — the precise reverse-lookup key — taken from the 13F holder cache
    (targets exposes it). A plain name search is far too noisy (4k+ loose matches)."""
    from core import targets
    for h in targets.targets_from_13f(cid, ticker=tk):
        if h.get("cusip"):
            return h["cusip"]
    return None


def refresh(cid=None, ticker=None, lookback_days=400):
    """Reverse-lookup the funds whose recent N-PORT lists this issuer's CUSIP, dedupe to the latest
    filing per fund, and store. Returns the stored list; typed `.last_status` on any early exit."""
    cid = cid or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    existing = db.load_json(_STORE_KEY, [], client_id=cid) or []
    if not tk:
        refresh.last_status = "no_ticker"
        return existing
    cusip = _cusip_for(cid, tk)
    if not cusip:
        refresh.last_status = "no_cusip"
        return existing

    import requests
    frm = (datetime.date.today() - datetime.timedelta(days=lookback_days)).isoformat()
    to = datetime.date.today().isoformat()
    funds = {}
    try:
        start = 0
        while True:
            r = requests.get(_EFTS, params={"q": cusip, "forms": "NPORT-P",
                                            "startdt": frm, "enddt": to, "from": start},
                             headers={"User-Agent": sec_filings._user_agent()}, timeout=25)
            r.raise_for_status()
            hits = r.json().get("hits", {}).get("hits", [])
            if not hits:
                break
            for h in hits:
                src = h.get("_source", {})
                raw = (src.get("display_names") or ["?"])[0]
                m = _CIK_RE.search(raw)
                cik = m.group(1) if m else None
                name = _CIK_RE.sub("", raw).strip()
                date = src.get("file_date", "")
                key = cik or name
                if key not in funds or date > funds[key]["date"]:
                    funds[key] = {"fund": name, "cik": cik, "date": date,
                                  "form": src.get("root_form") or "NPORT-P"}
            if len(hits) < 100:
                break
            start += len(hits)
            if start >= 400:   # safety cap — a single issuer's fund holders fit well within this
                break
        refresh.last_status = "ok"
    except Exception as e:
        refresh.last_status = f"error:{type(e).__name__}"
        return existing

    out = [{"ticker": tk, **v} for v in funds.values()]
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    db.save_json(_STORE_KEY, out, client_id=cid)
    return out


refresh.last_status = None


def recent(cid=None, limit=None, ticker=None):
    """Fund holders on file for the ticker (never fetches — safe on a render path)."""
    cid = cid or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    items = [i for i in (db.load_json(_STORE_KEY, [], client_id=cid) or [])
             if (i.get("ticker") or "").upper() == tk]
    items.sort(key=lambda x: x.get("date") or "", reverse=True)
    return items[:limit] if limit else items
