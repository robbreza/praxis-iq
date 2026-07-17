"""
core/nobo_engine.py — NOBO (Non-Objecting Beneficial Owner) ownership analytics.

Pure computation, no UI — the Market Intelligence > NOBO Ownership tab renders
what these functions return. Same engine pattern as core/guidance_engine.py.

The analytics a CFA would run on a NOBO list:
  • analyze_pull    — composition, concentration (top-10, HHI), coverage of
                      shares outstanding, retail vs institutional split.
  • flow            — two-pull delta: accumulators / distributors / new / exited,
                      the "who moved" read the CEO watches between record dates.
  • threshold_alerts— holders approaching 5% (13D/G), over 5%, or over 10%.
  • cross_reference — NOBO institutions you already track (contactable) vs large
                      holders not in your tracked universe/13F.
  • ceo_read        — a plain-English BLUF of the top signals.
"""


def _key(h):
    """Stable holder identity across pulls — name + address, since a NOBO list
    has no account id (matches how you'd reconcile two Broadridge files)."""
    return (h["name"], h.get("city", ""), h.get("state", ""))


def analyze_pull(pull, shares_out):
    holders = pull["holders"]
    total = sum(h["shares"] for h in holders)
    inst = [h for h in holders if h["type"] == "Institutional"]
    retail = [h for h in holders if h["type"] == "Retail"]
    inst_sh = sum(h["shares"] for h in inst)
    retail_sh = sum(h["shares"] for h in retail)
    ordered = sorted(holders, key=lambda h: -h["shares"])
    top10_sh = sum(h["shares"] for h in ordered[:10])
    # HHI on the visible NOBO base (sum of squared percent shares) — a rough
    # concentration gauge; low means a broad, diffuse base.
    hhi = sum((h["shares"] / total * 100) ** 2 for h in holders) if total else 0
    return {
        "record_date": pull["record_date"],
        "n_holders": len(holders), "n_inst": len(inst), "n_retail": len(retail),
        "total_shares": total, "inst_shares": inst_sh, "retail_shares": retail_sh,
        "nobo_pct_so": (total / shares_out * 100) if shares_out else 0,
        "inst_pct": (inst_sh / total * 100) if total else 0,
        "retail_pct": (retail_sh / total * 100) if total else 0,
        "top10_shares": top10_sh, "top10_pct": (top10_sh / total * 100) if total else 0,
        "hhi": hhi,
        "avg_retail": (retail_sh / len(retail)) if retail else 0,
        "top_holders": ordered[:15],
    }


def flow(current, prior):
    cur = {_key(h): h for h in current["holders"]}
    pri = {_key(h): h for h in prior["holders"]}
    accumulators, distributors, new, exited = [], [], [], []
    for k, h in cur.items():
        if k in pri:
            d = h["shares"] - pri[k]["shares"]
            if d > 0:
                accumulators.append((h, d))
            elif d < 0:
                distributors.append((h, d))
        else:
            new.append((h, h["shares"]))
    for k, h in pri.items():
        if k not in cur:
            exited.append((h, -h["shares"]))
    accumulators.sort(key=lambda x: -x[1])
    distributors.sort(key=lambda x: x[1])
    new.sort(key=lambda x: -x[1])
    exited.sort(key=lambda x: x[1])
    net = sum(h["shares"] for h in current["holders"]) - sum(h["shares"] for h in prior["holders"])
    return {
        "accumulators": accumulators, "distributors": distributors, "new": new, "exited": exited,
        "net_change": net,
        "n_acc": len(accumulators), "n_dist": len(distributors),
        "n_new": len(new), "n_exit": len(exited),
        "acc_shares": sum(d for _, d in accumulators) + sum(s for _, s in new),
        "dist_shares": sum(-d for _, d in distributors) + sum(-s for _, s in exited),
    }


def threshold_alerts(pull, shares_out, near=4.0):
    """Holders at/above `near`% of shares outstanding — the 13D/13G watch. A
    NOBO position crossing 5% means a Schedule 13D/13G becomes due; 10% adds
    Section 16 insider-reporting. Approaching 5% is the early-warning band."""
    out = []
    for h in pull["holders"]:
        pct = (h["shares"] / shares_out * 100) if shares_out else 0
        if pct >= near:
            if pct >= 10:
                level, color = ">10% — Section 16 / major position", "#B91C1C"
            elif pct >= 5:
                level, color = ">5% — 13D/13G filer", "#B45309"
            else:
                level, color = "approaching 5% — 13D/G watch", "#1E40AF"
            out.append({"holder": h, "pct": pct, "level": level, "color": color})
    out.sort(key=lambda x: -x["pct"])
    return out


def cross_reference(pull, tracked_funds):
    """Split the institutional NOBO holders into ones already in your tracked
    universe (contactable — route to IR) vs large holders you do NOT track
    (surfaced by NOBO but missing from your book / 13F)."""
    tracked = set(tracked_funds)
    inst = [h for h in pull["holders"] if h["type"] == "Institutional"]
    contactable = sorted([h for h in inst if h["name"] in tracked], key=lambda h: -h["shares"])
    untracked = sorted([h for h in inst if h["name"] not in tracked], key=lambda h: -h["shares"])[:10]
    return {"contactable": contactable, "untracked": untracked}


def ceo_read(cur, prev, fl, alerts):
    """Plain-English BLUF — the handful of signals worth leading with. Works
    with two pulls (flow read) or a single pull (snapshot read)."""
    parts = []
    if fl and prev:
        net = fl["net_change"]
        parts.append(
            f"NOBO base {'grew' if net >= 0 else 'shrank'} {abs(net):,} shares since {prev['record_date']} — "
            f"net {'accumulation' if net >= 0 else 'distribution'} across the holders you can see "
            f"({fl['n_acc']} adding, {fl['n_dist']} trimming, {fl['n_new']} new, {fl['n_exit']} exited).")
        dr = cur["n_retail"] - prev["n_retail"]
        parts.append(
            f"Retail base {'broadened' if dr >= 0 else 'thinned'} to {cur['n_retail']:,} holders "
            f"({dr:+,} vs prior), {cur['retail_pct']:.0f}% of NOBO shares — "
            f"{'a widening, stickier float' if dr >= 0 else 'an eroding retail float worth watching'}.")
    else:
        parts.append(
            f"Snapshot as of {cur['record_date']}: {cur['n_holders']:,} NOBO holders "
            f"({cur['n_inst']} institutional, {cur['n_retail']:,} retail) holding {cur['total_shares']:,} shares. "
            f"Upload an earlier pull to unlock the flow read.")
        parts.append(
            f"Retail is {cur['retail_pct']:.0f}% of the visible base; top-10 holders are {cur['top10_pct']:.0f}% "
            f"(HHI {cur['hhi']:.0f}).")
    if alerts:
        a = alerts[0]
        parts.append(f"Watch {a['holder']['name']} at {a['pct']:.1f}% of shares outstanding — {a['level']}.")
    if fl and fl["accumulators"]:
        h, d = fl["accumulators"][0]
        parts.append(f"Largest accumulator: {h['name']} (+{d:,} shares).")
    parts.append(
        f"You can see {cur['nobo_pct_so']:.0f}% of shares outstanding through NOBO; the balance sits in "
        f"OBO, registered, and insider hands.")
    return parts


# ─────────────────────────────────────────────────────────────────────────
# Broadridge NOBO file ingestion + uploaded-pull store. Uploaded pulls persist
# under "nobo_pulls.json"; get_active_pulls() prefers them (two most recent =
# current/prior for the flow read) and falls back to the demo seed when none
# are loaded, so the tab always has something to show.
# ─────────────────────────────────────────────────────────────────────────
import csv as _csv
import io as _io
import re as _re

_INST_WORDS = {
    "capital", "management", "advisors", "advisor", "partners", "fund", "funds", "llc", "lp", "trust",
    "associates", "investment", "investments", "group", "asset", "holdings", "securities", "bank",
    "insurance", "company", "inc", "corp", "global", "ventures", "co", "financial", "counsel", "wealth",
}


def _infer_type(name):
    tokens = _re.split(r"[^a-z]+", name.lower())
    return "Institutional" if any(t in _INST_WORDS for t in tokens) else "Retail"


def _to_int(s):
    try:
        return int(float(str(s).replace(",", "").replace("$", "").strip() or 0))
    except (TypeError, ValueError):
        return 0


def parse_nobo_csv(text, record_date):
    """Parse a Broadridge-style NOBO CSV. Column names are matched flexibly by
    keyword (holder/name, shares/position/quantity, city, state, type), so the
    exact export layout doesn't have to be known ahead of time. Holder type is
    inferred from the name when the file doesn't supply it."""
    reader = _csv.DictReader(_io.StringIO(text))

    def pick(row, *wants):
        for k in row:
            kl = (k or "").strip().lower()
            if any(w in kl for w in wants):
                return row[k]
        return ""

    holders = []
    for row in reader:
        name = (pick(row, "name", "holder", "registration") or "").strip()
        shares = _to_int(pick(row, "shares", "position", "quantity", "amount"))
        if not name or shares <= 0:
            continue
        typ = (pick(row, "type", "category") or "").strip().title()
        if typ not in ("Institutional", "Retail"):
            typ = _infer_type(name)
        holders.append({
            "name": name, "type": typ, "shares": shares,
            "city": (pick(row, "city") or "").strip(),
            "state": (pick(row, "state", "province") or "").strip()[:2].upper(),
        })
    return {"record_date": (record_date or "uploaded").strip(), "holders": holders}


_STORE_KEY = "nobo_pulls.json"


def _empty_store():
    return {"shares_outstanding": None, "pulls": []}


def load_pull_store(client_id=None):
    from core import db
    return db.load_json(_STORE_KEY, _empty_store(), client_id=client_id) or _empty_store()


def save_uploaded_pull(pull, shares_out=None, client_id=None):
    """Persist an uploaded pull, replacing any existing pull with the same
    record date. Returns the number of stored pulls."""
    from core import db
    store = load_pull_store(client_id)
    pulls = [p for p in store.get("pulls", []) if p.get("record_date") != pull["record_date"]]
    pulls.append(pull)
    pulls.sort(key=lambda p: p.get("record_date", ""))
    store["pulls"] = pulls
    if shares_out:
        store["shares_outstanding"] = int(shares_out)
    db.save_json(_STORE_KEY, store, client_id=client_id)
    return len(pulls)


def reset_to_demo(client_id=None):
    from core import db
    db.save_json(_STORE_KEY, _empty_store(), client_id=client_id)


def get_active_pulls(client_id=None):
    """Resolve which NOBO data to show: uploaded pulls if present (two most
    recent become current/prior), otherwise the demo seed. Returns
    {shares_outstanding, current, prior|None, source, n_pulls}."""
    from data.seed.nobo_holders import SHARES_OUTSTANDING
    store = load_pull_store(client_id)
    pulls = sorted(store.get("pulls", []), key=lambda p: p.get("record_date", ""))
    so = store.get("shares_outstanding") or SHARES_OUTSTANDING
    if len(pulls) >= 2:
        return {"shares_outstanding": so, "current": pulls[-1], "prior": pulls[-2],
                "source": "uploaded", "n_pulls": len(pulls)}
    if len(pulls) == 1:
        return {"shares_outstanding": so, "current": pulls[-1], "prior": None,
                "source": "uploaded-single", "n_pulls": 1}
    from data.seed.nobo_holders import get_nobo_pulls
    d = get_nobo_pulls(client_id)
    return {"shares_outstanding": d["shares_outstanding"], "current": d["current"],
            "prior": d["prior"], "source": "demo", "n_pulls": 2}
