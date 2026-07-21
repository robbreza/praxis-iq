"""core/insider_feed.py — insider transactions (SEC Form 4), per issuer.

Free, authoritative, open — SEC EDGAR Form 4 (Section 16: directors, officers, 10% owners). A
timely signal 13F can't give: the company's OWN people buying or selling, at the transaction price,
within ~2 business days of the trade. Reuses core.sec_filings for CIK resolution and the SEC-
compliant HTTP layer; for each Form 4 it reads the filing's form4.xml (reporting owner + the
non-derivative transaction table).

Per-client store. Nothing fabricated — an empty result means EDGAR had nothing (or the fetch failed,
surfaced via `.last_status`). Open-market buys (code P) and sells (code S) are the signal; grants,
option exercises and tax-withholding (A/M/F/G) are routine comp and are kept but flagged separately.
"""
import xml.etree.ElementTree as ET

from config.client_config import CT, get_active_client_id
from core import db, sec_filings

_STORE_KEY = "insider_txns.json"

# Form 4 transaction codes -> (verb, plain description, is_open_market)
_CODE = {
    "P": ("bought", "open-market purchase", True),
    "S": ("sold", "open-market sale", True),
    "A": ("granted", "grant / award", False),
    "M": ("exercised", "option exercise", False),
    "X": ("exercised", "option exercise", False),
    "F": ("withheld", "shares withheld for tax", False),
    "G": ("gifted", "gift", False),
    "C": ("converted", "conversion", False),
}


def _txt(el, path):
    x = el.find(path) if el is not None else None
    return (x.text or "").strip() if x is not None and x.text else ""


def _owner_role(rel):
    if _txt(rel, "isOfficer") in ("1", "true"):
        return _txt(rel, "officerTitle") or "Officer"
    if _txt(rel, "isDirector") in ("1", "true"):
        return "Director"
    if _txt(rel, "isTenPercentOwner") in ("1", "true"):
        return "10% owner"
    return ""


def _fmt_name(raw):
    """EDGAR reports 'Last First Middle'. Title-case; leave order (it's how filings read)."""
    return " ".join(w.capitalize() for w in (raw or "").split())


def _parse_form4(xml_bytes):
    root = ET.fromstring(xml_bytes)
    ro = root.find(".//reportingOwner")
    owner = _fmt_name(_txt(ro, ".//rptOwnerName"))
    role = _owner_role(ro.find(".//reportingOwnerRelationship") if ro is not None else None)
    out = []
    for tx in root.findall(".//nonDerivativeTransaction"):
        code = _txt(tx, ".//transactionCode")
        date = _txt(tx, ".//transactionDate/value")
        try:
            shares = float(_txt(tx, ".//transactionShares/value") or 0)
        except ValueError:
            shares = 0.0
        if not date or not shares:
            continue
        try:
            price = float(_txt(tx, ".//transactionPricePerShare/value") or 0)
        except ValueError:
            price = 0.0
        try:
            after = float(_txt(tx, ".//sharesOwnedFollowingTransaction/value") or 0)
        except ValueError:
            after = 0.0
        out.append({
            "owner": owner, "role": role, "code": code,
            "ad": _txt(tx, ".//transactionAcquiredDisposedCode/value"),   # A acquired / D disposed
            "shares": shares, "price": price, "shares_after": after, "date": date,
            "open_market": _CODE.get(code, ("", "", False))[2],
        })
    return out


def refresh(cid=None, ticker=None, max_filings=40):
    """Pull recent Form 4 filings for the issuer and merge parsed transactions into the per-client
    store. Bounded to the most recent `max_filings` (one HTTP call each). Returns the stored list."""
    cid = cid or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    existing = db.load_json(_STORE_KEY, [], client_id=cid) or []
    if not tk:
        refresh.last_status = "no_ticker"
        return existing
    try:
        cik = sec_filings.resolve_cik(tk)
        if not cik:
            refresh.last_status = "no_cik"
            return existing
        entries = sec_filings._fetch_ownership_filings_atom(cik, "4")
    except Exception as e:
        refresh.last_status = f"error:{type(e).__name__}"
        return existing

    by_id = {i["id"]: i for i in existing if i.get("id")}
    for e in entries[:max_filings]:
        folder = e.get("link", "").rsplit("/", 1)[0] + "/"
        try:
            idx = sec_filings._get(folder + "index.json").json()
            xmls = [it["name"] for it in idx.get("directory", {}).get("item", []) if it["name"].endswith(".xml")]
            doc = "form4.xml" if "form4.xml" in xmls else (xmls[0] if xmls else None)
            if not doc:
                continue
            xb = sec_filings._get(folder + doc).content
            for txn in _parse_form4(xb):
                txn["ticker"] = tk
                txn["filed"] = e.get("date")
                txn["id"] = f"{tk}|{txn['owner']}|{txn['date']}|{txn['code']}|{txn['shares']}"
                by_id[txn["id"]] = txn
        except Exception:
            continue

    refresh.last_status = "ok"
    out = sorted(by_id.values(), key=lambda i: i.get("date") or "", reverse=True)
    db.save_json(_STORE_KEY, out, client_id=cid)
    return out


refresh.last_status = None


def recent(cid=None, limit=None, ticker=None, open_market_only=False):
    """Read stored insider transactions for the ticker (never fetches — safe on a render path)."""
    cid = cid or get_active_client_id()
    tk = (ticker or CT("ticker") or "").upper()
    items = [i for i in (db.load_json(_STORE_KEY, [], client_id=cid) or [])
             if (i.get("ticker") or "").upper() == tk]
    if open_market_only:
        items = [i for i in items if i.get("open_market")]
    items.sort(key=lambda i: i.get("date") or "", reverse=True)
    return items[:limit] if limit else items


def net_open_market(cid=None, ticker=None, days=None):
    """Net open-market share change (buys − sells) — the headline insider signal."""
    buys = sells = 0.0
    for t in recent(cid, ticker=ticker, open_market_only=True):
        if t.get("code") == "P":
            buys += t.get("shares") or 0
        elif t.get("code") == "S":
            sells += t.get("shares") or 0
    return {"buy_shares": buys, "sell_shares": sells, "net_shares": buys - sells}


def describe(t):
    verb = _CODE.get(t.get("code"), ("transacted", "", False))[0]
    who = t.get("owner", "")
    role = f" ({t['role']})" if t.get("role") else ""
    px = f" @ ${t['price']:.2f}" if t.get("price") else ""
    val = (t.get("shares") or 0) * (t.get("price") or 0)
    amt = f" · ${val:,.0f}" if val else ""
    return f"{who}{role} {verb} {int(t.get('shares') or 0):,} sh{px}{amt} ({t.get('date')})"


def glyph(t):
    code = t.get("code")
    if code == "P":
        return "▲"
    if code == "S":
        return "▼"
    return "•"
