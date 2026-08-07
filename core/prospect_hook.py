"""core/prospect_hook.py — a real, data-driven outreach hook for a prospect.

For a prospect ticker we pull TWO consecutive quarters of SEC's Form 13F BULK dataset (the
complete institutional holder list with real share counts, dollar values, and each filing
manager's city/state), diff them, and surface:
  * the top ownership MOVES this quarter (new / added / trimmed / exited), ranked by dollar impact
  * the METRO TREND among those movers, via the NDR canonical-metro vocabulary
  * a holders-by-metro chart (PIL PNG) for the Console prep view

Everything traces to a filing — nothing is invented; hook_text() is built deterministically from
the diff (no AI, no guessed figures). Heavy (two ~100MB SEC downloads), so prepare() is a
deliberate, cached, off-render action; hook_text()/metro_chart_png() read the cache. This is the
reusable engine behind the personalized prospect email.
"""
import io
import re
from collections import Counter
from datetime import datetime, timezone

from core import db, sec_filings

_CACHE_KEY_FMT = "prospect_hook_{ticker}.json"
_CACHE_TENANT = "praxis"


def _now():
    return datetime.now(timezone.utc).isoformat()


# Financial-hub cities whose NDR canonical label has a suffix/paren that canonical_metro's
# leading-segment match can't reach ("New York" ↛ "New York Metro"). The rest (Boston, Chicago,
# Denver, LA, Philadelphia, San Francisco) resolve through canonical_metro directly.
_HUB_BY_CITY = {
    "new york": "New York Metro", "brooklyn": "New York Metro", "new york city": "New York Metro",
    "jersey city": "New York Metro", "greenwich": "New York Metro", "stamford": "New York Metro",
    "dallas": "Texas (Dallas / Austin)", "austin": "Texas (Dallas / Austin)",
    "houston": "Texas (Dallas / Austin)", "fort worth": "Texas (Dallas / Austin)",
    "miami": "Florida (Miami / Tampa)", "tampa": "Florida (Miami / Tampa)",
    "fort lauderdale": "Florida (Miami / Tampa)", "west palm beach": "Florida (Miami / Tampa)",
    "boca raton": "Florida (Miami / Tampa)", "palm beach": "Florida (Miami / Tampa)",
}


def _metro(city, state):
    """Filer city/state -> the NDR canonical metro label, else 'City, ST', else None. SEC gives
    the city uppercase, so normalize case before matching."""
    city = (city or "").strip()
    state = (state or "").strip()
    if not city:
        return state or None
    if city.lower() in _HUB_BY_CITY:
        return _HUB_BY_CITY[city.lower()]
    try:
        from core.ndr_calendar import canonical_metro, known_metros
        canon = canonical_metro(city.title())
        if canon and canon in set(known_metros()):
            return canon
    except Exception:
        pass
    # Append the state ONLY for a US state code (2 letters); SEC uses digit-bearing codes like
    # "X0"/"Q8" for non-US filers ("London, X0"), which read badly in a board briefing.
    if state and len(state) == 2 and state.isalpha():
        return f"{city.title()}, {state.upper()}"
    return city.title()


def _key(h):
    """Stable holder identity across quarters: CIK if present, else normalized filer name."""
    return (str(h.get("cik") or "").strip()
            or sec_filings._normalize_company_name(h.get("filer") or ""))


# Big managers file 13F under several legal entities, and they reshuffle holdings between those
# entities — so a naive per-filer diff shows "Vanguard Group exited $620M" next to two other
# Vanguard entities "opening new positions", which is a filing artifact, not a real move. Netting
# the known multi-entity families to one line is standard 13F practice and the honest read. Only
# these curated, unambiguous families are collapsed; every other filer stays itself.
_FAMILY_PREFIXES = [
    ("VANGUARD", "Vanguard"), ("BLACKROCK", "BlackRock"), ("STATE STREET", "State Street"),
    ("FMR ", "Fidelity"), ("FIDELITY", "Fidelity"), ("GEODE", "Geode"),
    ("JPMORGAN", "JPMorgan"), ("J P MORGAN", "JPMorgan"), ("JP MORGAN", "JPMorgan"),
    ("MORGAN STANLEY", "Morgan Stanley"), ("GOLDMAN SACHS", "Goldman Sachs"),
    ("BANK OF AMERICA", "Bank of America"), ("MERRILL LYNCH", "Bank of America"),
    ("WELLINGTON", "Wellington"), ("NORTHERN TRUST", "Northern Trust"),
    ("CHARLES SCHWAB", "Charles Schwab"), ("SCHWAB", "Charles Schwab"),
    ("UBS ", "UBS"), ("DEUTSCHE BANK", "Deutsche Bank"), ("CITADEL", "Citadel"),
    ("BARCLAYS", "Barclays"), ("T. ROWE PRICE", "T. Rowe Price"), ("T ROWE PRICE", "T. Rowe Price"),
]


def _family(filer):
    up = (filer or "").upper().strip()
    for prefix, label in _FAMILY_PREFIXES:
        if up.startswith(prefix):
            return label
    return None


# PASSIVE / FLOW managers: index complexes, bulge-bracket bank broker-dealers, and market makers.
# Their 13F swings are mechanical (index tracking, customer facilitation, delta hedges), NOT
# conviction — a $3.5B Barclays move says nothing an IR team can act on. Everything NOT on this
# list is treated as an ACTIVE manager (a real repositioning worth a conversation). Fuzzy at the
# margins by nature; curated to the clearly-mechanical names. Values here are family labels (post
# _aggregate) or raw-name prefixes for firms that don't get family-netted.
_FLOW_LABELS = {
    "Vanguard", "BlackRock", "State Street", "Geode", "Northern Trust", "Charles Schwab",
    "JPMorgan", "Morgan Stanley", "Goldman Sachs", "Bank of America", "Barclays", "UBS",
    "Deutsche Bank", "Citadel",
}
_FLOW_NAME_PREFIXES = [
    "JANE STREET", "SUSQUEHANNA", "VIRTU", "WOLVERINE", "JUMP TRADING", "IMC ", "OPTIVER",
    "CITADEL SECURITIES", "TWO SIGMA SECURITIES", "CITIGROUP", "CITIBANK", "WELLS FARGO",
    "BNY MELLON", "BANK OF NEW YORK", "MELLON", "ROYAL BANK OF CANADA", "BANK OF MONTREAL",
    "TORONTO-DOMINION", "TORONTO DOMINION", "BNP PARIBAS", "HSBC", "NOMURA", "MIZUHO",
    "SOCIETE GENERALE", "CREDIT SUISSE", "MACQUARIE", "SUMITOMO", "NATIONAL BANK OF CANADA",
]


def _is_flow(name):
    """True if `name` is a passive/flow manager (index / bank broker-dealer / market maker)."""
    if name in _FLOW_LABELS:
        return True
    up = (name or "").upper().strip()
    return any(up.startswith(p) for p in _FLOW_NAME_PREFIXES)


_ENTITY_TOKENS = {"Llc", "Llp", "Lp", "Inc", "Ltd", "Lt", "Plc", "Na", "Us", "Uk", "Lp.",
                  "Ii", "Iii", "Iv", "Sa", "Ag", "Nv", "Ab", "Co", "Corp", "Sec", "Mgmt"}


def _clean_filer(name):
    """Tidy a raw SEC filer name for display: drop a trailing ' / CT' state tag, and title-case
    an ALL-CAPS name while keeping entity suffixes (LLC/LP/INC) upper. Mixed-case names untouched."""
    n = re.sub(r"\s*/\s*[A-Za-z]{2}\s*$", "", (name or "").strip())
    if n.isupper():
        n = n.title()
        n = re.sub(r"[A-Za-z]+", lambda m: m.group(0).upper() if m.group(0) in _ENTITY_TOKENS
                   else m.group(0), n)
    return n


def _aggregate(holders):
    """Collapse the known multi-entity fund families to one group; keep every other filer as
    itself. Group key is stable across quarters. Metro/name follow the family's largest entity."""
    groups = {}
    for h in holders:
        fam = _family(h.get("filer"))
        gk = f"fam:{fam}" if fam else f"id:{_key(h)}"
        val = h.get("value") or 0
        sh = h.get("shares") or 0
        g = groups.get(gk)
        if not g:
            groups[gk] = {"name": fam or h.get("filer"), "is_family": bool(fam),
                          "cik": None if fam else h.get("cik"),   # single-entity filer -> its CIK
                          "shares": sh, "value": val, "city": h.get("city"),
                          "state": h.get("state"), "_maxval": val}
        else:
            g["shares"] += sh
            g["value"] += val
            if val > g["_maxval"]:
                g["_maxval"], g["city"], g["state"] = val, h.get("city"), h.get("state")
    return groups


def _direction(prior_sh, cur_sh):
    if prior_sh <= 0 and cur_sh > 0:
        return "new"
    if cur_sh <= 0 and prior_sh > 0:
        return "exited"
    if cur_sh > prior_sh:
        return "added"
    if cur_sh < prior_sh:
        return "trimmed"
    return "unchanged"


def _coverage_false(cik, direction, cusip):
    """Guard against a two-quarter bulk COVERAGE GAP masquerading as a real move. A holder marked
    'new' or 'exited' by the diff may actually be a CONTINUING holder whose position in one of the
    two quarters wasn't captured (a filer reporting a share-class CUSIP variant, a parse gap, etc.).
    Confirm against the filer's OWN multi-quarter 13F filing history:
      * a 'new' position is false if the filer has held the security across several recent filings;
      * an 'exited' position is false if the filer's most recent filing still shows a position.
    Returns True when the label is contradicted (so the caller drops it). Fails open (False)."""
    try:
        h = sec_filings.holder_history(int(cik), cusip=cusip, quarters=6)
    except Exception:
        return False
    series = [x.get("shares") for x in (h.get("history") or [])]
    real = [s for s in series if s]
    if direction == "new":
        return len(real) >= 2                       # an established holder, not a genuine initiation
    return bool(series) and bool(series[0])         # 'exited' but the latest filing still holds


def prepare(ticker, company, force=False, top_n=10, client_id=None):
    """Pull two quarters of 13F, diff, and cache the hook payload for `ticker`. Returns the
    payload dict (with 'error' set on failure). Idempotent: a cached payload for the current
    quarter is returned as-is unless force=True.

    `client_id` scopes the cache: prospects cache under the internal 'praxis' tenant (default);
    a client's own holder-move briefing caches under that client's id so it lives with its data."""
    tenant = client_id or _CACHE_TENANT
    ticker = (ticker or "").upper()
    cached = db.load_json(_CACHE_KEY_FMT.format(ticker=ticker), default=None, client_id=tenant)
    datasets = sec_filings._recent_13f_datasets(2)
    if len(datasets) < 2:
        return {"ticker": ticker, "company": company, "top_changes": [],
                "error": "SEC has fewer than two 13F datasets posted."}
    if cached and not force and cached.get("quarter") == datasets[0][1] and not cached.get("error"):
        return cached

    cur = sec_filings.refresh_13f_bulk_all([(ticker, company)], dataset=datasets[0], save=False)[ticker]
    prior = sec_filings.refresh_13f_bulk_all([(ticker, company)], dataset=datasets[1], save=False)[ticker]
    n_cur_raw, n_pri_raw = len(cur.get("holders") or []), len(prior.get("holders") or [])
    cusip = cur.get("cusip") or prior.get("cusip")
    cur_g = _aggregate(cur.get("holders") or [])
    pri_g = _aggregate(prior.get("holders") or [])
    if not cur_g:
        return {"ticker": ticker, "company": company, "top_changes": [],
                "quarter": datasets[0][1], "prior_quarter": datasets[1][1],
                "error": f"No 13F holders found for {company} in the {datasets[0][1]} dataset."}

    changes = []
    for k in set(cur_g) | set(pri_g):
        c, p = cur_g.get(k), pri_g.get(k)
        base = c or p
        cur_sh, pri_sh = (c or {}).get("shares") or 0, (p or {}).get("shares") or 0
        cur_val, pri_val = (c or {}).get("value") or 0, (p or {}).get("value") or 0
        name = base.get("name")
        changes.append({
            "filer": _clean_filer(name),
            "family": bool(base.get("is_family")),
            "passive": _is_flow(name),
            "cik": base.get("cik"),
            "city": base.get("city"), "state": base.get("state"),
            "metro": _metro(base.get("city"), base.get("state")),
            "shares": cur_sh, "prior_shares": pri_sh, "delta_shares": cur_sh - pri_sh,
            "value": cur_val, "prior_value": pri_val, "delta_value": cur_val - pri_val,
            "direction": _direction(pri_sh, cur_sh),
        })
    movers = [c for c in changes if c["direction"] != "unchanged"]
    # dollar impact desc; filer name as a stable tiebreaker so equal-impact moves don't reorder
    movers.sort(key=lambda c: (-abs(c["delta_value"]), (c["filer"] or "")))

    # Verify the 'new'/'exited' labels among the strongest movers against each filer's OWN 13F
    # history — a bulk coverage gap in one quarter can fake an initiation or an exit (see the
    # Whittier/USIO case). Drop the contradicted ones so they never reach a board or a prospect.
    kept, dropped = [], 0
    for m in movers[:max(2 * top_n, 20)]:
        if (m["direction"] in ("new", "exited") and not m.get("family") and m.get("cik") and cusip
                and _coverage_false(m["cik"], m["direction"], cusip)):
            dropped += 1
            continue
        kept.append(m)
    kept.extend(movers[max(2 * top_n, 20):])       # tail (rarely shown) left unverified
    top = kept[:top_n]
    top_active = [c for c in kept if not c["passive"]][:top_n]   # conviction moves only

    metro_counts = Counter(c["metro"] for c in top if c.get("metro"))
    trend = metro_counts.most_common(1)[0] if metro_counts else None
    active_counts = Counter(c["metro"] for c in top_active if c.get("metro"))
    active_trend = active_counts.most_common(1)[0] if active_counts else None

    by_cnt, by_val = Counter(), Counter()
    for g in cur_g.values():
        m = _metro(g.get("city"), g.get("state"))
        if m:
            by_cnt[m] += 1
            by_val[m] += (g.get("value") or 0)

    payload = {
        "ticker": ticker, "company": company,
        "quarter": datasets[0][1], "prior_quarter": datasets[1][1],
        "n_holders": n_cur_raw, "n_prior": n_pri_raw,
        "top_changes": top,
        "top_active": top_active,
        "metro_trend": ({"metro": trend[0], "count": trend[1], "of": len(top)} if trend else None),
        "metro_trend_active": ({"metro": active_trend[0], "count": active_trend[1],
                                "of": len(top_active)} if active_trend else None),
        "holders_by_metro": by_cnt.most_common(12),
        "value_by_metro": by_val.most_common(12),
        "coverage_dropped": dropped,           # new/exited labels the filer's own history refuted
        "prepared_at": _now(), "error": None,
    }
    db.save_json(_CACHE_KEY_FMT.format(ticker=ticker), payload, client_id=tenant)
    return payload


def get_cached(ticker, client_id=None):
    return db.load_json(_CACHE_KEY_FMT.format(ticker=(ticker or "").upper()),
                        default=None, client_id=client_id or _CACHE_TENANT)


# Clients whose 13F briefing should NOT be auto-pulled — the illustrative demo tenant has a
# fabricated ticker, so a real SEC pull for it is meaningless (mirrors the app-wide demo guard).
_NO_AUTO = {"demo"}


def latest_quarter_label():
    """The label of the most recently posted 13F dataset — one cheap index-page fetch."""
    ds = sec_filings._recent_13f_datasets(1)
    return ds[0][1] if ds else None


def refresh_client_briefings(clients, force=False, latest_label=None):
    """Quarterly auto-refresh: for each (client_id, ticker, company), (re)prepare the holder-move
    briefing ONLY when it's stale — i.e. a NEW 13F quarter has posted since the cache was written.
    The staleness check is a cheap DB read; the ~90s SEC pull runs only for stale clients, so this
    is safe to call daily and it does real work ~quarterly. Sequential (one heavy download at a
    time). Returns a per-client status list. Never rejects — each client's failure is isolated."""
    if latest_label is None:
        latest_label = latest_quarter_label()
    out = []
    for cid, tk, name in clients:
        if cid in _NO_AUTO or not tk:
            out.append({"client": cid, "ticker": tk, "status": "skipped"})
            continue
        try:
            cached = get_cached(tk, client_id=cid)
            current = bool(cached and not cached.get("error") and cached.get("quarter") == latest_label)
            if current and not force:
                out.append({"client": cid, "ticker": tk, "status": "current", "quarter": latest_label})
                continue
            d = prepare(tk, name, force=True, client_id=cid)
            out.append({"client": cid, "ticker": tk, "quarter": d.get("quarter"),
                        "status": "error" if d.get("error") else "refreshed", "error": d.get("error")})
        except Exception as e:
            out.append({"client": cid, "ticker": tk, "status": "failed", "error": str(e)})
    return out


# ── deterministic hook copy ────────────────────────────────────────────────
def _fmt_shares(n):
    n = abs(int(n or 0))
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return str(n)


def _fmt_usd(v):
    # Post-2023 Form 13F reports VALUE in whole dollars (older sets were thousands).
    v = abs(int(v or 0))
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.1f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.0f}M"
    if v >= 1_000:
        return f"${v / 1_000:.0f}K"
    return f"${v}"


_VERB = {"new": "opened a new position", "added": "added", "trimmed": "trimmed", "exited": "exited"}


def _move_phrase(c):
    v = _VERB.get(c["direction"], c["direction"])
    # a netted fund family reads "across its funds" so the reader knows it's the whole house
    tail = " across its funds" if c.get("family") else ""
    if c["direction"] == "new":
        return f"{c['filer']} {v} ({_fmt_usd(c['value'])}){tail}"
    if c["direction"] == "exited":
        return f"{c['filer']} {v} (was {_fmt_usd(c['prior_value'])}){tail}"
    return f"{c['filer']} {v} {_fmt_shares(c['delta_shares'])} shares ({_fmt_usd(c['delta_value'])}){tail}"


def net_posture(data):
    """Board-level read of the quarter: are the biggest movers net accumulating or distributing?
    Counts direction across the top moves (adds/new vs trims/exits)."""
    top = (data or {}).get("top_changes") or []
    acc = sum(1 for c in top if c["direction"] in ("added", "new"))
    dist = sum(1 for c in top if c["direction"] in ("trimmed", "exited"))
    label = ("net accumulation" if acc > dist else
             "net distribution" if dist > acc else "mixed")
    return {"label": label, "accumulating": acc, "trimming": dist}


def briefing_text(data):
    """A board-toned summary of the quarter's institutional moves — distinct from the outreach
    hook_text (which is written to a prospect). Factual, no invented figures. '' if no moves."""
    if not data or data.get("error") or not data.get("top_changes"):
        return ""
    p = net_posture(data)
    active = [c for c in (data.get("top_active") or []) if abs(c["delta_value"]) >= _MIN_ACTIVE_USD][:3]
    lead = (f"Across the {data['prior_quarter']} → {data['quarter']} 13F filings, the ten largest "
            f"ownership moves were {p['label']} ({p['accumulating']} adding or initiating, "
            f"{p['trimming']} trimming or exiting).")
    if active:
        lead += " Notable active-manager moves: " + "; ".join(_move_phrase(c) for c in active) + "."
    tr = data.get("metro_trend_active") or data.get("metro_trend")
    if tr and tr.get("count", 0) >= 2:
        lead += f" {tr['count']} of the biggest active moves sit in {tr['metro']}."
    return lead


_MIN_ACTIVE_USD = 25_000_000        # ignore trivially small "active" moves when choosing the lead


def _metro_line(trend, noun):
    return (f" {trend['count']} of the {noun} are {trend['metro']} funds — "
            f"a metro you could cover in a single day of meetings.")


def hook_text(data):
    """A short, factual outreach paragraph built deterministically from the diff — no AI, no
    invented figures. ADAPTS to the prospect: when there are real active-manager moves it leads
    with those (the conviction signal), and only claims a metro cluster when the ACTIVE movers
    genuinely concentrate; otherwise it falls back to the biggest moves overall. '' if no movers."""
    if not data or data.get("error") or not data.get("top_changes"):
        return ""
    co = data.get("company") or data.get("ticker")
    pq, q = data["prior_quarter"], data["quarter"]
    active = [c for c in (data.get("top_active") or []) if abs(c["delta_value"]) >= _MIN_ACTIVE_USD]

    if len(active) >= 2:
        lead = (f"I ran {co}'s last two 13F quarters ({pq} → {q}). The notable active-manager moves: "
                + "; ".join(_move_phrase(c) for c in active[:3]) + ".")
        tr = data.get("metro_trend_active")
        n_active = len(data.get("top_active") or [])
        if tr and tr["count"] >= max(2, round(0.4 * n_active)):     # a real cluster, not passive noise
            lead += _metro_line(tr, "biggest active moves")
        return lead

    # fallback: the move set is dominated by passive/flow — report the biggest moves overall
    top = data["top_changes"]
    lead = (f"I ran {co}'s last two 13F quarters ({pq} → {q}). Among the {len(top)} biggest "
            f"ownership moves: " + "; ".join(_move_phrase(c) for c in top[:3]) + ".")
    trend = data.get("metro_trend")
    if trend and trend["count"] >= 2:
        lead += (f" {trend['count']} of those {trend['of']} movers are {trend['metro']} funds — "
                 f"a metro you could cover in a single day of meetings.")
    return lead


# ── holders-by-metro chart (PIL, no extra deps) ────────────────────────────
def metro_chart_png(data, width=700, row_h=30, pad=18):
    """A horizontal bar chart of the current holder base by metro (top ~9). Returns PNG bytes,
    or None if there's nothing to plot."""
    from PIL import Image, ImageDraw, ImageFont
    rows = (data or {}).get("holders_by_metro") or []
    rows = rows[:9]
    if not rows:
        return None
    ink, sub, bar, bg = (17, 24, 39), (100, 116, 139), (37, 99, 235), (255, 255, 255)
    title_h, label_w = 46, 190
    height = title_h + pad + row_h * len(rows) + pad
    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 13)
        title_font = ImageFont.truetype("arialbd.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
        title_font = font
    co = (data.get("company") or data.get("ticker"))
    d.text((pad, 14), f"{co} — institutional holders by metro", fill=ink, font=title_font)
    d.text((pad, 32), f"{data.get('n_holders', '')} 13F holders · {data.get('quarter', '')}",
           fill=sub, font=font)
    maxv = max(v for _m, v in rows) or 1
    bar_x = pad + label_w
    bar_max = width - bar_x - pad - 40
    y = title_h + pad
    for metro, v in rows:
        label = (metro[:26] + "…") if len(metro) > 27 else metro
        d.text((pad, y + 5), label, fill=ink, font=font)
        w = max(3, int(bar_max * v / maxv))
        d.rectangle([bar_x, y + 3, bar_x + w, y + row_h - 9], fill=bar)
        d.text((bar_x + w + 6, y + 5), str(v), fill=sub, font=font)
        y += row_h
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def active_moves_chart_png(data, width=760, row_h=32, pad=18):
    """The VISUAL of the hook: the biggest ACTIVE-manager moves this quarter as a diverging bar
    chart — added/new to the right (green), trimmed/exited to the left (red), each labeled with
    the fund, dollar move, and metro. Falls back to the biggest moves overall if no active ones.
    Returns PNG bytes, or None if nothing to plot."""
    from PIL import Image, ImageDraw, ImageFont
    moves = [m for m in ((data or {}).get("top_active") or []) if abs(m.get("delta_value") or 0)]
    if not moves:
        moves = [m for m in ((data or {}).get("top_changes") or []) if abs(m.get("delta_value") or 0)]
    moves = moves[:8]
    if not moves:
        return None
    ink, sub, bg = (17, 24, 39), (100, 116, 139), (255, 255, 255)
    green, red, axis = (21, 128, 61), (185, 28, 28), (203, 213, 225)
    title_h, label_w = 52, 172
    height = title_h + pad + row_h * len(moves) + pad
    img = Image.new("RGB", (width, height), bg)
    d = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 12)
        small = ImageFont.truetype("arial.ttf", 11)
        title_font = ImageFont.truetype("arialbd.ttf", 16)
    except Exception:
        font = small = title_font = ImageFont.load_default()
    co = data.get("company") or data.get("ticker")
    d.text((pad, 12), f"{co} — biggest active-manager moves", fill=ink, font=title_font)
    d.text((pad, 32), f"{data.get('prior_quarter', '')} → {data.get('quarter', '')}   "
                      "▮ added / new    ▮ trimmed / exited", fill=sub, font=small)

    axis_left, axis_right = pad + label_w, width - pad
    center = (axis_left + axis_right) // 2
    half = (axis_right - axis_left) // 2 - 78          # leave room for end labels
    maxv = max(abs(m["delta_value"]) for m in moves) or 1
    d.line([center, title_h + pad - 2, center, height - pad + 2], fill=axis, width=1)
    y = title_h + pad
    for m in moves:
        inflow = m["direction"] in ("added", "new")
        col = green if inflow else red
        name = m["filer"]
        name = (name[:24] + "…") if len(name) > 25 else name
        d.text((pad, y + 6), name, fill=ink, font=font)
        w = max(3, int(half * abs(m["delta_value"]) / maxv))
        if inflow:
            d.rectangle([center, y + 4, center + w, y + row_h - 8], fill=col)
            tag = f"+{_fmt_usd(m['delta_value'])}" + (f" · {m['metro']}" if m.get("metro") else "")
            d.text((center + w + 5, y + 6), tag, fill=sub, font=small)
        else:
            d.rectangle([center - w, y + 4, center, y + row_h - 8], fill=col)
            tag = f"−{_fmt_usd(m['delta_value'])}" + (f" · {m['metro']}" if m.get("metro") else "")
            tw = d.textlength(tag, font=small)
            d.text((center - w - 5 - tw, y + 6), tag, fill=sub, font=small)
        y += row_h
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
