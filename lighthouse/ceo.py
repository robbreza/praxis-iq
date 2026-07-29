"""Lighthouse Phase 1 — Evidence Fusion v0 + the CEO one-pager (Spec: CEO View).

Fuses the two live lenses — Market/Peer Attribution and Event Intelligence — into a single verdict
for a day, then renders the conclusion-first CEO note. Non-negotiable discipline (Spec):
  * separate ABNORMALITY confidence (how unusual the move is) from EXPLANATION confidence (do we know
    why) — a move can be highly abnormal with an unknown cause;
  * report what was FOUND and what was CHECKED-BUT-NOT-FOUND (missing source != nothing found);
  * never assert causation the evidence doesn't support; label the unexplained portion honestly;
  * conclusion first, evidence one click away (deep links).
Verdicts persist to lh_verdict as `draft` (Spec 12.4 lifecycle: draft -> revised -> settled), so a
lagged catalyst can revise the record later.
"""
from __future__ import annotations
from datetime import datetime, timezone, time
import json

import psycopg2
from core.security import get_database_url
from lighthouse.replay import AsOf
from lighthouse import events, technician

_CONF_NUM = {"HIGH": 0.85, "MODERATE": 0.6, "LOW": 0.3, "ROUTINE": 0.15}
_MATERIAL = ("10-Q", "10-K", "8-K")


def _conn(): return psycopg2.connect(get_database_url())


def build_verdict(client_id, ticker, day, model_row, lookback_days=10, conn=None) -> dict:
    own = conn is None
    conn = conn or _conn()
    as_of = AsOf(datetime.combine(day, time(21, 0), tzinfo=timezone.utc))
    move = model_row["actual_ret"]; exp = model_row["expected_ret"]
    resid = model_row["residual"]; rarity = model_row.get("residual_pctile")

    win = events.window_for_day(ticker, day, lookback_days=lookback_days, as_of=as_of, conn=conn)
    candidates = [e for e in win if "candidate" in e["timing"]]
    prior = [e for e in win if "prior-window" in e["timing"]]
    rolled = [e for e in win if "rolls to next" in e["timing"]]

    # market/peer directional share of the move
    mp_share = max(0.0, min(1.0, (exp / move))) if move and (exp * move) > 0 else 0.0

    # multi-factor rigor (Spec 13.1): the residual is standardized by conditional vol → z, with a
    # significance t-stat and the model's in-window R². rarity is the normal-tail mass within ±|z|.
    z = model_row.get("z"); t_stat = model_row.get("t_stat")
    r2 = model_row.get("r2"); n_factors = model_row.get("n_factors")

    # abnormality confidence from rarity (now z-calibrated: 0.90 ≈ 1.6σ, 0.75 ≈ 1.15σ)
    abn = "HIGH" if (rarity or 0) >= 0.90 else "MODERATE" if (rarity or 0) >= 0.75 else "ROUTINE"

    drivers, found, not_found = [], [], []
    if candidates:
        c = candidates[0]
        material = any(c["headline"].startswith(m) for m in _MATERIAL)
        expl = "HIGH" if material else "MODERATE"
        drivers.append(dict(cls="primary", label=c["headline"][:80],
                            detail=f"public {c['days_before']}d before the move ({c['timing']})", link=c.get("url")))
        found += [f"{e['headline'][:80]} [{e['published_at'].date()}]" for e in candidates]
    elif prior:
        p = prior[0]; expl = "MODERATE" if (rarity or 0) < 0.9 else "LOW"
        drivers.append(dict(cls="diffusing", label=p["headline"][:80],
                            detail=f"filed {p['days_before']}d earlier — possible diffusion/lag (Spec 12)", link=p.get("url")))
        found += [f"{e['headline'][:80]} [{e['published_at'].date()}]" for e in prior]
    elif mp_share >= 0.6 and (rarity or 0) < 0.75:
        expl = "MODERATE"
        drivers.append(dict(cls="primary", label="Common risk factors (market/size/value/momentum/sector/rate)",
                            detail=f"~{mp_share*100:.0f}% of the move is explained by common factors", link=None))
    else:
        expl = "LOW"
        drivers.append(dict(cls="unexplained", label="Unexplained by current lenses",
                            detail="idiosyncratic move; no in-window SEC catalyst; flow lens not yet wired", link=None))

    if mp_share > 0.15 and drivers[0]["cls"] != "primary":
        drivers.append(dict(cls="contributing", label="Market & peers",
                            detail=f"~{mp_share*100:.0f}% directional", link=None))
    if not (candidates or prior):
        not_found.append(f"No 8-K / 10-Q / 10-K / insider (Form 4) filing in the {lookback_days}-day window (checked EDGAR).")
    not_found.append("Non-SEC news, options/flow, and short/borrow lenses are not yet wired (Phase 3).")

    # Technician lens (Spec 3): how the move was expressed/amplified — never the cause.
    tech = technician.compute_technicals(ticker, day, benchmark="IWM", as_of=as_of, conn=conn)
    for s in tech.get("signals", []):
        drivers.append(dict(cls=s["role"], label=s["label"], detail="technical structure", link=None))

    if own:
        conn.close()
    unexplained_pct = abs(resid) / abs(move) if move else 0.0
    return dict(client_id=client_id, ticker=ticker, day=day, as_of=as_of.as_of,
                actual=move, expected=exp, expected_lo=model_row["expected_lo"], expected_hi=model_row["expected_hi"],
                residual=resid, rarity=rarity, mp_share=mp_share, unexplained_pct=unexplained_pct,
                z=z, t_stat=t_stat, r2=r2, n_factors=n_factors,
                abnormality_conf=abn, explanation_conf=expl, drivers=drivers, found=found, not_found=not_found,
                technical=tech.get("summary"))


def render_ceo(v: dict) -> str:
    L = []
    L.append(f"# {v['ticker']} — What happened on {v['day']}")
    verdict = (v['drivers'][0]['label'] if v['explanation_conf'] != "LOW"
               else "No confirmed cause identified")
    L.append(f"**{v['ticker']} moved {v['actual']*100:+.1f}% vs an expected {v['expected']*100:+.1f}% "
             f"(range {v['expected_lo']*100:+.1f}% to {v['expected_hi']*100:+.1f}%).** "
             f"Unexplained residual **{v['residual']*100:+.1f}%** "
             f"(~{v['unexplained_pct']*100:.0f}% of the move), {int((v['rarity'] or 0)*100)}th-percentile rare.")
    L.append(f"\n**Abnormality confidence: {v['abnormality_conf']}  ·  Explanation confidence: {v['explanation_conf']}**")
    if v.get("z") is not None:
        L.append(f"\n_Model:_ {int(v.get('n_factors') or 0)}-factor risk model, R² {(v.get('r2') or 0)*100:.0f}%; "
                 f"the residual is **{v['z']:+.1f}σ** (t {v.get('t_stat') or 0:+.1f}) — "
                 f"volatility-regime-adjusted, so abnormality reflects today's tape, not a static history.")
    L.append(f"\n_Best read:_ {verdict}.")
    L.append("\n**Drivers**")
    for d in v["drivers"]:
        link = f"  [evidence]({d['link']})" if d.get("link") else ""
        L.append(f"- _{d['cls'].title()}_ — {d['label']} — {d['detail']}{link}")
    if v["found"]:
        L.append("\n**Found (in window)**")
        L += [f"- {f}" for f in v["found"]]
    if v.get("technical"):
        L.append(f"\n**Technical expression** (how, not why)\n- {v['technical']}")
    L.append("\n**Checked but not found**")
    L += [f"- {n}" for n in v["not_found"]]
    return "\n".join(L)


def persist_verdict(v: dict, conn=None) -> int:
    own = conn is None; conn = conn or _conn(); cur = conn.cursor()
    cur.execute("""INSERT INTO lh_verdict (client_id,ticker,d,as_of,lifecycle,abnormality_conf,
                     explanation_conf,summary,drivers,found,not_found)
                   VALUES (%s,%s,%s,%s,'draft',%s,%s,%s,%s,%s,%s) RETURNING verdict_id""",
                (v["client_id"], v["ticker"], v["day"], v["as_of"],
                 _CONF_NUM[v["abnormality_conf"]], _CONF_NUM[v["explanation_conf"]],
                 render_ceo(v).split("\n")[1], json.dumps(v["drivers"]),
                 json.dumps(v["found"]), json.dumps(v["not_found"])))
    vid = cur.fetchone()[0]
    for d in v["drivers"]:
        if d.get("link"):
            cur.execute("""INSERT INTO lh_evidence (verdict_id,kind,deep_link,detail,knowledge_ts)
                           VALUES (%s,'event',%s,%s,%s)""", (vid, d["link"], json.dumps(d), v["as_of"]))
    conn.commit()
    if own: conn.close()
    return vid
