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
from config.client_config import get_active_client_id
from core import db

STORE_KEY = "web_flow_visitors.json"

# Assets an investor can pull off an IR site, ranked by how much intent a download of
# each implies. A model/deck pull is deep diligence; a press release is light.
ASSET_INTENT = {
    "Earnings model": 5, "Investor deck": 4, "10-Q": 3, "10-K": 3, "Fact sheet": 3,
    "Transcript": 2, "Press release": 2, "ESG report": 2, "Other": 1,
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
