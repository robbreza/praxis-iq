"""core/web_flow.py — the IR-website "web flow": who visits the investor site and
whether they DOWNLOAD material or just READ pages.

The old "IR Website Visitor Log" only ever modelled READING — Pages_Viewed +
Time_On_Site. It never captured the stronger signal: a visitor who pulls the investor
deck, the earnings model, or the 10-Q is doing real work, not skimming. This module
separates the two intent tiers and scores them accordingly:

  READ      = page views + dwell time (browsing interest).
  DOWNLOAD  = pulling an asset (deck / model / fact sheet / filing). Weighted much
              higher — a deck+model pull from a non-holder is a hot prospect.

DATA SOURCE, stated honestly (no fabrication for real tenants):
  * Real clients have NO live web-analytics feed wired yet (GA4 / Q4 / IRWIN export).
    Until one is uploaded to the store key "web_flow_visitors.json", compose() returns
    available=False and the UI shows a Waiting signal — never invented numbers.
  * The labelled illustrative demo tenant (client_id "demo" — Northlake Payments) is
    seeded with representative visitors so the capability is demonstrable. That is the
    ONLY tenant that receives illustrative data. See data/seed/web_flow.py and
    [[illustrative-demo-tenant]].
"""
import re

from config.client_config import get_active_client_id
from core import db

STORE_KEY = "web_flow_visitors.json"

# Generic firm-name words dropped when matching a web visitor org to a 13F institution
# name (which arrives as e.g. "HALEWOOD CAPITAL MANAGEMENT LP"). What's left is the
# distinctive part ("HALEWOOD"), which is what the two names actually share.
_ORG_STOPWORDS = {
    "LLC", "INC", "LP", "LLP", "LTD", "PLC", "CO", "CORP", "THE", "AND",
    "GROUP", "MANAGEMENT", "MGMT", "CAPITAL", "PARTNERS", "ADVISORS", "ADVISERS",
    "ASSOCIATES", "ASSET", "ASSETS", "INVESTMENTS", "INVESTMENT", "INVESTORS",
    "TRUST", "COMPANY", "HOLDINGS", "GLOBAL", "FUND", "FUNDS", "SECURITIES",
    "EQUITY", "MANAGERS",
}

# Assets an investor can pull off an IR site, ranked by how much intent a download of
# each implies. A model/deck pull is deep diligence; a press release is light.
ASSET_INTENT = {
    "Earnings model": 5, "Investor deck": 4, "10-Q": 3, "10-K": 3, "Fact sheet": 3,
    "Transcript": 2, "Press release": 2, "ESG report": 2,
    # Marketing-site actions — Praxis's OWN site (praxispointir.com) surfaces prospective
    # CLIENTS (leads), not investors; a demo request is the strongest signal there.
    "Demo request": 5, "Pricing": 4, "Product overview": 3, "Security overview": 3,
    "Services overview": 2,
    "Other": 1,
}


def _intent(pages, minutes, downloads):
    """0–100 intent score. Downloads dominate; reads contribute but are capped so a long
    idle tab can't masquerade as strong interest (the old score's weakness)."""
    read_pts = min(35, (pages or 0) * 6 + (minutes or 0) * 2)
    dl_pts = sum(ASSET_INTENT.get(a, 1) for a in (downloads or [])) * 8
    return min(100, round(read_pts + dl_pts))


def _label(score, has_downloads):
    if has_downloads and score >= 60:
        return "High intent"
    if score >= 40:
        return "Engaged reader"
    return "Browser"


def _normalize(v):
    """One raw visitor dict (either our schema or the legacy CSV column names) → the
    canonical shape the UI renders, with the derived intent score."""
    downloads = [a for a in (v.get("downloads") or []) if a]
    pages = int(v.get("pages") or v.get("Pages_Viewed") or 0)
    minutes = int(v.get("minutes") or v.get("Time_On_Site_Min") or 0)
    score = _intent(pages, minutes, downloads)
    return {
        "org": v.get("org") or v.get("Visitor_Organization") or "—",
        "category": v.get("category") or v.get("Category") or "New — unidentified",
        "is_holder": bool(v.get("is_holder")),
        "ticker": v.get("ticker"),   # public-company ticker when the visitor firm is public

        "pages": pages, "minutes": minutes, "visits": int(v.get("visits") or 1),
        "downloads": downloads, "n_downloads": len(downloads),
        "last_visit": v.get("last_visit") or v.get("Date") or "",
        "intent": score, "intent_label": _label(score, bool(downloads)),
    }


def _load(cid):
    """(rows, source_label) — an uploaded export wins; else illustrative demo; else none."""
    rows = db.load_json(STORE_KEY, None, client_id=cid)
    if rows:
        return rows, "your uploaded web-analytics export"
    if cid == "demo":
        try:
            from data.seed.web_flow import get_seed_web_flow
            return get_seed_web_flow(), "illustrative demo data"
        except Exception:
            return None, None
    return None, None


def compose(client_id=None):
    """The web-flow summary for a tenant. available=False when there's no feed."""
    cid = client_id or get_active_client_id()
    rows, source = _load(cid)
    if not rows:
        return {"available": False, "source": None}

    visitors = sorted((_normalize(v) for v in rows), key=lambda x: -x["intent"])
    downloaders = [v for v in visitors if v["n_downloads"] > 0]
    readers = [v for v in visitors if v["n_downloads"] == 0]

    asset_counts = {}
    for v in visitors:
        for a in v["downloads"]:
            asset_counts[a] = asset_counts.get(a, 0) + 1
    by_asset = sorted(asset_counts.items(), key=lambda kv: (-kv[1], kv[0]))

    # Hot prospects: high-intent DOWNLOADERS who aren't holders yet — the reason this
    # view exists. Someone pulling the deck + model who doesn't own you is a target.
    hot_prospects = [v for v in downloaders if not v["is_holder"] and v["intent"] >= 50]

    return {
        "available": True, "source": source,
        "visitors": visitors,
        "n_visitors": len(visitors),
        "n_downloaders": len(downloaders),
        "n_readers": len(readers),
        "download_pct": round(100 * len(downloaders) / len(visitors)) if visitors else 0,
        "total_downloads": sum(v["n_downloads"] for v in visitors),
        "by_asset": by_asset,
        "hot_prospects": hot_prospects,
        "n_new_unidentified": sum(1 for v in visitors if "unidentified" in v["category"].lower()),
    }


# ── Matching web visitors to tracked institutions (for the engagement-score fold) ──
def _org_key(name):
    """Distinctive tokens of a firm name, uppercased, generic words dropped. 'Halewood
    Capital Management LP' and 'HALEWOOD CAPITAL MGMT' both reduce to ('HALEWOOD',)."""
    toks = re.sub(r"[^A-Za-z0-9 ]", " ", str(name or "")).upper().split()
    core = tuple(t for t in toks if t not in _ORG_STOPWORDS)
    return core or tuple(toks)


def intent_map(client_id=None):
    """{ distinctive-name-key : normalized visitor } for this tenant, or {} when no
    web-flow feed exists (real tenants without an upload). Keyed for institution joins."""
    d = compose(client_id)
    if not d.get("available"):
        return {}
    out = {}
    for v in d["visitors"]:
        out[_org_key(v["org"])] = v
    return out


def intent_for(org_name, client_id=None, _map=None):
    """The web-flow visitor matching a tracked institution's name, or None. Exact
    distinctive-key match first, then a first-token fallback (best-effort for the
    free-text names a real analytics export would carry). None ⇒ no web signal, so the
    caller contributes nothing (never a fabricated zero)."""
    m = _map if _map is not None else intent_map(client_id)
    if not m:
        return None
    key = _org_key(org_name)
    if key in m:
        return m[key]
    first = key[0] if key else None
    if first:
        for k, v in m.items():
            if k and k[0] == first:
                return v
    return None


def target_queue_keys(client_id=None):
    """Distinctive-name keys already in the manual target pipeline (prospects.json), so
    the UI can show which hot prospects are already queued."""
    cid = client_id or get_active_client_id()
    plist = db.load_json("prospects.json", [], client_id=cid) or []
    return {_org_key(p.get("fund", "")) for p in plist}


def is_in_queue(org, queued_keys):
    """Is this org already in the target pipeline? (given a set from target_queue_keys)."""
    return _org_key(org) in queued_keys


def add_to_target_queue(visitor, client_id=None):
    """Push a web-flow hot prospect into the manual target pipeline — the SAME
    prospects.json store the Peer Prospects 'Promote' button writes to, so a
    web-sourced target lands in Target Database / the pipeline like any other, not in a
    disconnected list. Idempotent by distinctive name. Returns (added: bool)."""
    cid = client_id or get_active_client_id()
    plist = db.load_json("prospects.json", [], client_id=cid) or []
    key = _org_key(visitor.get("org", ""))
    if not key or any(_org_key(p.get("fund", "")) == key for p in plist):
        return False
    dl = ", ".join(visitor.get("downloads") or [])
    plist.append({
        "fund": visitor.get("org", ""),
        "metro": "Unknown (web)",
        "style": (f"IR-website engagement — pulled {dl}" if dl else "IR-website engagement — read pages")
                 + f" (intent {int(visitor.get('intent') or 0)})",
        "score": int(visitor.get("intent") or 0),
        "outcome": None,
        "source": "IR Website (web flow)",
    })
    db.save_json("prospects.json", plist, client_id=cid)
    return True


# ── CSV ingest — let a real client drop in a GA4 / Q4 / IRWIN visitor export ───────
# Header aliases so exports from different analytics tools all map to our schema. Match
# is on a squashed header (lowercase, non-alphanumerics stripped): "Time on Site (min)"
# -> "timeonsitemin".
_COL_ALIASES = {
    "org": {"visitororganization", "organization", "organisation", "company", "account",
            "visitor", "org", "fund", "firm", "name", "institution"},
    "category": {"category", "type", "segment", "visitortype", "audience"},
    "pages": {"pagesviewed", "pages", "pageviews", "pageviewscount", "screenviews"},
    "minutes": {"timeonsitemin", "minutes", "timeonsite", "durationmin", "timeminutes",
                "avgsessionmin", "engagementtime", "engagedminutes"},
    "visits": {"visits", "sessions", "visitcount", "sessioncount"},
    "last_visit": {"date", "lastvisit", "lastseen", "visitdate", "lastactivity"},
    "downloads": {"downloads", "assetsdownloaded", "documents", "files", "assets",
                  "downloaded", "downloadedassets", "resources"},
    "is_holder": {"holder", "isholder", "existingholder", "currentholder"},
}


def _squash_header(h):
    return re.sub(r"[^a-z0-9]", "", str(h or "").strip().lower())


def _to_int(x):
    try:
        return int(round(float(str(x).strip().replace(",", "") or 0)))
    except Exception:
        return 0


def parse_visitor_csv(data):
    """Parse a web-analytics CSV export into web-flow visitor rows. Recognizes a broad
    set of column names (see _COL_ALIASES); an Organization column is the only hard
    requirement. Downloads may be one comma/semicolon-separated column of asset names.
    Never raises on a bad row — it's skipped. Returns a list of visitor dicts."""
    import csv
    import io
    text = data.decode("utf-8-sig", "ignore") if isinstance(data, (bytes, bytearray)) else str(data)
    reader = csv.DictReader(io.StringIO(text))
    field_by_col = {}
    for col in (reader.fieldnames or []):
        sq = _squash_header(col)
        for field, aliases in _COL_ALIASES.items():
            if sq in aliases:
                field_by_col[col] = field
                break

    rows = []
    for raw in reader:
        rec = {}
        for col, val in raw.items():
            f = field_by_col.get(col)
            if f and f not in rec:      # first matching column wins
                rec[f] = val
        org = (rec.get("org") or "").strip()
        if not org:
            continue
        downloads = [a.strip() for a in re.split(r"[,;/|]", rec.get("downloads") or "") if a.strip()]
        h = rec.get("is_holder")
        if h is not None and str(h).strip() != "":
            is_holder = str(h).strip().lower() in ("1", "true", "yes", "y", "t", "holder")
        else:
            is_holder = "holder" in (rec.get("category") or "").lower()
        rows.append({
            "org": org,
            "category": (rec.get("category") or "New — unidentified").strip() or "New — unidentified",
            "is_holder": is_holder,
            "pages": _to_int(rec.get("pages")),
            "minutes": _to_int(rec.get("minutes")),
            "visits": _to_int(rec.get("visits")) or 1,
            "last_visit": (rec.get("last_visit") or "").strip(),
            "downloads": downloads,
        })
    return rows


def save_visitor_data(rows, client_id=None):
    """Persist uploaded visitor rows as the tenant's web-flow feed (wins over the demo
    seed for that client)."""
    db.save_json(STORE_KEY, rows or [], client_id=client_id or get_active_client_id())


def clear_visitor_data(client_id=None):
    """Drop an uploaded feed — reverts a real tenant to the Waiting signal (and the demo
    tenant to its illustrative seed)."""
    db.save_json(STORE_KEY, None, client_id=client_id or get_active_client_id())
