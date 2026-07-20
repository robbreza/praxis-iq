"""
core/ndr_by_city.py — NDR coverage by city: where the money is vs where we're going.

Built because the CFO asked for it and it didn't exist. Every input already did — the
buy-side institution list with metros, the scored engagement, and the booked NDR trips —
so this is a join the platform could always have done and never had.

THE METRIC IS THE WHOLE ARGUMENT, AND THE OBVIOUS ONE IS WRONG.

The intuitive move is to average engagement score across every fund in a metro. Do that
and New York looks WEAK (avg 51, second-lowest of eight) and the NDR schedule looks
inverted — we appear to be spending our best days in our worst market. That read is an
artefact: New York has 15 funds and Chicago has 6, so New York's average is diluted by a
long tail we would never actually meet.

An NDR is not an average. You fly somewhere and take four to six meetings. So the question
is not "what is the mean fund here" but "how good are the meetings I could actually FILL A
DAY with" — the top 5 non-holders in that metro. On that metric New York is the strongest
market (74) and the schedule is positively correlated with opportunity (+0.44). The
schedule is directionally right.

The finding survives anyway, and it is sharper for being true:
  * Boston has a TRIP ON THE CALENDAR WITH ZERO MEETINGS IN IT, in a metro tied for
    second-best (69). A booked day with nothing in it.
  * Chicago (69) and San Francisco (68) are as strong as Texas (69), which gets four
    meetings. They get none.
  * Los Angeles (60) ranks 6th of 8 and gets four meetings.

That is a real, actionable read, and it is the opposite of the one the naive metric gives.
"""

from collections import defaultdict
from datetime import datetime

from config.client_config import CT, get_active_client_id

# A day on the road is 4-6 meetings. Scoring a metro on more than you could hold there
# measures a market you can't visit.
DAY_CAPACITY = 5


def _scored(client_id=None):
    # Real 13F holders, not the fabricated buyside seed — the NDR-by-city planner feeds a
    # client-facing PDF (report_pdf.ndr_by_city_pdf), so demo funds here recommended visiting
    # institutions that don't hold the stock and, in some cases, don't exist.
    from core.investor_scoring import score_institutions
    from core import targets
    cid = client_id or get_active_client_id()
    return score_institutions(targets.targets_as_institutions(client_id=cid),
                              "pre_earnings", set(), [])


def _normalise_city(city, metros):
    """Join an NDR trip's city label to an institution metro label.

    Delegates to ndr_calendar.canonical_metro(), which owns the canonical vocabulary
    (_METRO_TZ) that routing._METRO_FOCUS and the buy-side Metro field also key off.
    This module had its own copy of the normaliser for about an hour; two normalisers
    for one vocabulary is how the vocabulary drifts in the first place.

    The underlying data is now fixed too — the trip saved as "Boston" is stored as
    "Boston / New England" — so this is a belt-and-braces guard rather than the fix.
    """
    if not city:
        return "—"
    try:
        from core.ndr_calendar import canonical_metro
        canon = canonical_metro(city)
        if canon in metros:
            return canon
    except Exception:
        pass
    return city if city in metros else city


def _booked(metros):
    """Meetings per metro from the live NDR calendar. Breaks aren't meetings."""
    from core import db
    out, trips = defaultdict(int), defaultdict(list)
    unmatched = []
    for t in db.load_json("ndr_trips.json", default=None) or []:
        raw = t.get("city") or "—"
        city = _normalise_city(raw, metros)
        if city not in metros and raw != "—":
            unmatched.append(raw)
        ms = [m for m in (t.get("meetings") or []) if m.get("type") != "break"]
        out[city] += len(ms)
        trips[city].append({"name": t.get("name"), "dates": t.get("dates") or t.get("date"),
                            "meetings": len(ms), "city_label": raw})
    return out, trips, unmatched


def by_city(client_id=None):
    scored = _scored(client_id)
    by = defaultdict(list)
    for i in scored:
        by[i.get("Metro") or "—"].append(i)
    booked, trips, unmatched = _booked(set(by))
    if unmatched:
        print(f"[ndr_by_city] trip cities that do not join to any metro: {unmatched}")

    rows = []
    for metro, funds in by.items():
        holders = [f for f in funds if f.get("USIO_Holder")]
        non = sorted([f for f in funds if not f.get("USIO_Holder")],
                     key=lambda f: -(f.get("Engagement_Score") or 0))
        top = non[:DAY_CAPACITY]
        top_avg = (sum(f.get("Engagement_Score") or 0 for f in top) / len(top)) if top else 0
        n_booked = booked.get(metro, 0)
        rows.append({
            "metro": metro, "funds": len(funds), "holders": len(holders),
            "non_holders": len(non), "top_avg": top_avg,
            "can_fill_a_day": len(non) >= 4,
            "booked": n_booked, "trips": trips.get(metro, []),
            "top_targets": [{"fund": f.get("Fund"), "score": f.get("Engagement_Score")} for f in top],
        })
    rows.sort(key=lambda r: -r["top_avg"])
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return rows


def correlation(rows):
    """Does the schedule track the opportunity? Reported either way, because the
    interesting answer is the one we didn't expect."""
    pts = [(r["top_avg"], r["booked"]) for r in rows]
    n = len(pts)
    if n < 3:
        return None
    mx, my = sum(p[0] for p in pts) / n, sum(p[1] for p in pts) / n
    cov = sum((p[0] - mx) * (p[1] - my) for p in pts) / n
    sx = (sum((p[0] - mx) ** 2 for p in pts) / n) ** 0.5
    sy = (sum((p[1] - my) ** 2 for p in pts) / n) ** 0.5
    return (cov / (sx * sy)) if (sx and sy) else None


def findings(rows):
    """The specific, actionable gaps — not a restatement of the table."""
    out = []
    for r in rows:
        empty = [t for t in r["trips"] if t["meetings"] == 0]
        if empty:
            for t in empty:
                out.append({
                    "level": "red",
                    "title": f"{r['metro']} — a trip is booked with ZERO meetings in it",
                    "detail": (f"“{t['name']}” ({t['dates']}) is on the calendar with nothing "
                               f"scheduled. {r['metro']} ranks #{r['rank']} of {len(rows)} on "
                               f"opportunity (top-{DAY_CAPACITY} avg {r['top_avg']:.0f}) with "
                               f"{r['non_holders']} non-holders on file — this is a day already "
                               f"committed and currently wasted. Top targets: "
                               + ", ".join(f"{x['fund']} ({x['score']})" for x in r["top_targets"][:3])
                               + "."),
                })
    covered = [r for r in rows if r["booked"] > 0]
    weakest_covered = min(covered, key=lambda r: r["top_avg"]) if covered else None
    for r in rows:
        if r["booked"] == 0 and r["can_fill_a_day"] and not [t for t in r["trips"]]:
            if weakest_covered and r["top_avg"] > weakest_covered["top_avg"]:
                out.append({
                    "level": "amber",
                    "title": f"{r['metro']} — no trip, and it outranks a market we are visiting",
                    "detail": (f"Top-{DAY_CAPACITY} avg {r['top_avg']:.0f} (#{r['rank']} of "
                               f"{len(rows)}) against {weakest_covered['metro']} at "
                               f"{weakest_covered['top_avg']:.0f} (#{weakest_covered['rank']}), which "
                               f"has {weakest_covered['booked']} meetings booked. "
                               f"{r['non_holders']} non-holders here — enough to fill a day. "
                               + ", ".join(f"{x['fund']} ({x['score']})" for x in r["top_targets"][:3])
                               + "."),
                })
    return out


def read(rows, corr):
    booked_total = sum(r["booked"] for r in rows)
    covered = [r for r in rows if r["booked"] > 0]
    top = rows[0] if rows else None
    s = (f"{booked_total} meetings booked across {len(covered)} of {len(rows)} metros, from "
         f"{sum(r['funds'] for r in rows)} institutions on file. ")
    if corr is not None:
        if corr > 0.2:
            s += (f"The schedule tracks the opportunity (correlation {corr:+.2f}) — "
                  + (f"{top['metro']} is both the strongest market (top-{DAY_CAPACITY} avg "
                     f"{top['top_avg']:.0f}) and the most-booked. The plan is directionally right. "
                     if top and top["booked"] else ""))
        elif corr < -0.2:
            s += (f"The schedule runs AGAINST the opportunity (correlation {corr:+.2f}) — we are "
                  f"booking fewest meetings where the best targets are. ")
        else:
            s += f"The schedule is uncorrelated with the opportunity (correlation {corr:+.2f}). "
    s += (f"Ranking is on the top-{DAY_CAPACITY} non-holders in each metro, not the average across "
          f"every fund: an NDR is {DAY_CAPACITY} meetings in a day, not a survey. Averaging the "
          f"whole list penalises deep markets for their tail — on that (wrong) metric New York "
          f"looks like the second-weakest market on the board, which is how a good schedule gets "
          f"talked out of.")
    return s


def compose(client_id=None):
    rows = by_city(client_id)
    corr = correlation(rows)
    return {
        "ticker": CT("ticker"), "name": CT("name"), "as_of": datetime.now(),
        "rows": rows, "correlation": corr, "findings": findings(rows),
        "read": read(rows, corr), "day_capacity": DAY_CAPACITY,
        "total_booked": sum(r["booked"] for r in rows),
        "total_funds": sum(r["funds"] for r in rows),
    }
