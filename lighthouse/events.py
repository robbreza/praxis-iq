"""Lighthouse Phase 1 — Event Intelligence overlay (Spec 4 + Spec 12 timing).

Pulls the issuer's own SEC filings from EDGAR's submissions API (reusing Praxis's throttled fetcher)
into lh_event, stamped with `knowledge_ts = acceptanceDateTime` — the precise instant the filing
became public. That precision is what makes the Spec 12 timing test real: at daily resolution, a
filing accepted BEFORE the 4pm ET close is a candidate cause for that day's move; accepted AFTER the
close it rolls to the next session (an event published after the move cannot explain it). The overlay
then, for any residual day, reports what was filed in the window AND — critically — that the window
was checked (missing source != nothing found).
"""
from __future__ import annotations
from datetime import datetime, timezone, timedelta, time

import psycopg2
from core import sec_filings as sf
from core.security import get_database_url
from core import db as _db

CLOSE_UTC = time(20, 0)   # ~16:00 ET

# 8-K item codes worth surfacing as "what happened" signal
ITEM_LABEL = {
    "1.01": "material agreement", "1.03": "bankruptcy", "2.02": "results / earnings",
    "3.01": "listing/deficiency", "3.02": "unregistered equity sale", "5.02": "officer/director change",
    "7.01": "Reg FD disclosure", "8.01": "other material event",
}
FORM_KIND = {"8-K": "announcement", "10-Q": "earnings", "10-K": "earnings", "DEF 14A": "proxy",
             "S-1": "capital_raise", "S-3": "capital_raise", "424B": "capital_raise"}


def _conn(): return _db.get_connection()


def fetch_sec_events(ticker, client_id, cik=None, limit=120) -> list[dict]:
    cik = cik or sf.resolve_cik(ticker)
    if not cik:
        return []
    r = sf._get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", timeout=25)
    rec = (r.json() or {}).get("filings", {}).get("recent", {})
    forms = rec.get("form", []); dates = rec.get("filingDate", [])
    acc = rec.get("acceptanceDateTime", []); accn = rec.get("accessionNumber", [])
    items = rec.get("items", []); pdoc = rec.get("primaryDocument", [])
    pdesc = rec.get("primaryDocDescription", [])
    out = []
    for i, form in enumerate(forms[:limit]):
        base = form.split("/")[0]
        kind = next((v for k, v in FORM_KIND.items() if base.startswith(k)), "sec_filing")
        a = acc[i] if i < len(acc) and acc[i] else (dates[i] + "T20:00:00.000Z")
        pub = datetime.fromisoformat(a.replace("Z", "+00:00")).astimezone(timezone.utc)
        it = (items[i] if i < len(items) else "") or ""
        labels = "; ".join(ITEM_LABEL.get(x.strip(), x.strip()) for x in it.split(",") if x.strip())
        head = form + (f" — {labels}" if labels else "") + (f" ({pdesc[i]})" if i < len(pdesc) and pdesc[i] else "")
        cikn = int(cik); an = (accn[i] if i < len(accn) else "").replace("-", "")
        url = (f"https://www.sec.gov/Archives/edgar/data/{cikn}/{an}/{pdoc[i]}"
               if i < len(pdoc) and pdoc[i] and an else None)
        out.append(dict(client_id=client_id, ticker=ticker, kind=kind, headline=head[:300],
                        published_at=pub, materiality="confirmed", url=url))
    return out


def load_events(ticker, client_id, cik=None, conn=None) -> int:
    own = conn is None; conn = conn or _conn(); cur = conn.cursor()
    evs = fetch_sec_events(ticker, client_id, cik)
    for e in evs:
        cur.execute("""INSERT INTO lh_event (client_id,ticker,kind,headline,published_at,materiality,url)
                       VALUES (%(client_id)s,%(ticker)s,%(kind)s,%(headline)s,%(published_at)s,%(materiality)s,%(url)s)""", e)
    conn.commit()
    if own: conn.close()
    return len(evs)


def window_for_day(ticker, day, lookback_days=10, as_of=None, conn=None) -> list[dict]:
    """Events in [day-lookback, day], each timing-classified for whether it can explain `day`'s move.
    Respects the point-in-time horizon if `as_of` is given."""
    own = conn is None; conn = conn or _conn(); cur = conn.cursor()
    start = datetime.combine(day - timedelta(days=lookback_days), time.min, tzinfo=timezone.utc)
    end = datetime.combine(day, time(23, 59), tzinfo=timezone.utc)
    gate, params = "", [ticker, start, end]
    if as_of is not None:
        frag, val = as_of.where_sql("published_at"); gate = " AND " + frag; params.append(val)
    cur.execute(f"""SELECT headline, published_at, kind, url FROM lh_event
                    WHERE ticker=%s AND published_at BETWEEN %s AND %s{gate} ORDER BY published_at""", params)
    day_close = datetime.combine(day, CLOSE_UTC, tzinfo=timezone.utc)
    out = []
    for head, pub, kind, url in cur.fetchall():
        pub = pub if pub.tzinfo else pub.replace(tzinfo=timezone.utc)
        same = pub.date() == day
        if pub <= day_close:
            timing = "candidate cause (public before close)"
        elif same:
            timing = "AFTER close — rolls to next session (cannot explain today)"
        else:
            timing = "prior-window catalyst (possible diffusion/lag)"
        out.append(dict(headline=head, published_at=pub, kind=kind, url=url, timing=timing,
                        days_before=(day - pub.date()).days))
    if own: conn.close()
    return out
