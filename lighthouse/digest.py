"""Lighthouse — Verdict Digest (push delivery).

The engine is only as useful as its delivery: a CEO/CFO will not log into a dashboard to learn why
the stock moved, but will glance at a phone at 5:10pm. This module turns the daily Lighthouse verdict
into a phone-glanceable push — a tight, <30-second executive brief — and delivers it by email now and
SMS when configured. It is the piece that decides whether Lighthouse is the most-used or most-ignored
feature (see docs/lighthouse and the mobile roadmap).

Discipline carried over from the CEO one-pager:
  * ABNORMALITY and EXPLANATION confidence stay separate (a move can be abnormal with an unknown cause);
  * we prioritise rather than blast — a per-verdict tier (Critical / Important / Informational /
    Monitoring, per the mobile alert-center spec) gates *whether* and *how loudly* we push, so the
    channel never trains the reader to ignore it.

SAFETY: sending is outward-facing, so this is DISABLED by default and fail-closed. Nothing leaves the
box until the operator sets LIGHTHOUSE_DIGEST_ENABLED=1 and at least one recipient. With no config it
renders and returns — never sends — which is exactly what the CLI preview and tests exercise.
"""
from __future__ import annotations
import os
import base64
import smtplib
import traceback
import urllib.parse
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Alert-center tiers (mobile spec 6): higher rank = louder. Email fires at/above the email floor,
# SMS only at/above the (higher) SMS floor, so a routine day never buzzes a phone.
_TIER_RANK = {"monitoring": 0, "informational": 1, "important": 2, "critical": 3}
_TIER_COLOR = {"critical": "#c0392b", "important": "#d97706", "informational": "#2563eb", "monitoring": "#6b7280"}


def _ord(n) -> str:
    n = int(round(n))
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# ── config (all env-driven; absent → disabled, never crashes) ──────────────────────────────────────
def config() -> dict:
    try:
        from core.security import load_environment
        load_environment()
    except Exception:
        pass
    g = os.environ.get
    smtp_user = g("LIGHTHOUSE_SMTP_USER") or ""
    return dict(
        enabled=str(g("LIGHTHOUSE_DIGEST_ENABLED", "")).strip().lower() in ("1", "true", "yes", "on"),
        email_to=[a.strip() for a in (g("LIGHTHOUSE_DIGEST_TO", "") or "").split(",") if a.strip()],
        sms_to=[p.strip() for p in (g("LIGHTHOUSE_DIGEST_SMS_TO", "") or "").split(",") if p.strip()],
        email_floor=_TIER_RANK.get((g("LIGHTHOUSE_DIGEST_EMAIL_TIER", "informational") or "").strip().lower(), 1),
        sms_floor=_TIER_RANK.get((g("LIGHTHOUSE_DIGEST_SMS_TIER", "important") or "").strip().lower(), 2),
        smtp_host=g("LIGHTHOUSE_SMTP_HOST", "smtpout.secureserver.net"),
        smtp_port=int(g("LIGHTHOUSE_SMTP_PORT", "465") or 465),
        smtp_user=smtp_user,
        smtp_password=g("LIGHTHOUSE_SMTP_PASSWORD") or "",
        from_email=g("LIGHTHOUSE_FROM_EMAIL") or smtp_user,
        app_url=(g("LIGHTHOUSE_APP_URL", "") or "").rstrip("/"),
        twilio_sid=g("TWILIO_ACCOUNT_SID") or "",
        twilio_token=g("TWILIO_AUTH_TOKEN") or "",
        twilio_from=g("TWILIO_FROM_NUMBER") or "",
    )


def is_enabled() -> bool:
    c = config()
    return bool(c["enabled"] and (c["email_to"] or c["sms_to"]))


# ── priority + rendering (pure; no I/O — this is what tests pin) ────────────────────────────────────
def priority(v: dict) -> dict:
    """Map (abnormality, explanation) confidence to an alert-center tier + a plain-English IR action."""
    abn, expl = v["abnormality_conf"], v["explanation_conf"]
    top = v["drivers"][0]["label"] if v.get("drivers") else "current lenses"
    if abn == "HIGH" and expl == "LOW":
        tier, action = "critical", "Management attention now — an abnormal move with no confirmed cause."
    elif abn == "HIGH":
        tier, action = "important", f"IR review today — abnormal, but largely explained ({top})."
    elif abn == "MODERATE" and expl == "LOW":
        tier, action = "important", "IR review today — an unusual move whose cause isn't yet confirmed."
    elif abn == "MODERATE":
        tier, action = "informational", "Include in the next brief — moderately unusual, and explained."
    else:
        tier, action = "monitoring", "No action — within the normal range for the day."
    return dict(tier=tier, rank=_TIER_RANK[tier], action=action)


def _headline(v: dict) -> str:
    return (f"{v['ticker']} moved {v['actual']*100:+.1f}% vs an expected {v['expected']*100:+.1f}% "
            f"(market & payments peers); unexplained residual {v['residual']*100:+.1f}%, "
            f"{_ord((v.get('rarity') or 0)*100)}-percentile rare.")


def render_sms(v: dict, pr: dict | None = None, app_url: str = "") -> str:
    """ASCII-safe, ~1 segment: the one thing a phone should show. No emoji (SMS gateways choke)."""
    pr = pr or priority(v)
    top = v["drivers"][0]["label"] if v.get("drivers") else "current lenses"
    txt = (f"[{pr['tier'].upper()}] {v['ticker']} {v['actual']*100:+.1f}% ({v['day']}). "
           f"Exp {v['expected']*100:+.1f}%, residual {v['residual']*100:+.1f}% "
           f"({_ord((v.get('rarity') or 0)*100)}-pctile). Abn {v['abnormality_conf']}/Expl {v['explanation_conf']}. "
           f"{top}. -> {pr['action']}")
    if app_url:
        txt += f" {app_url}"
    # SMS gateways choke on non-ASCII; fold typographic punctuation, then hard-guard to ASCII.
    txt = txt.replace("—", "-").replace("–", "-").replace("·", "-").replace("→", "->")
    return txt.encode("ascii", "ignore").decode()


def render_text(v: dict, pr: dict | None = None, app_url: str = "") -> str:
    pr = pr or priority(v)
    L = [f"{v['ticker']} — {v['day']}  [{pr['tier'].upper()}]",
         "", _headline(v),
         f"Abnormality {v['abnormality_conf']} · Explanation {v['explanation_conf']}",
         f"IR action: {pr['action']}", "", "Drivers:"]
    for d in v.get("drivers", []):
        L.append(f"  · {d['cls'].title()} — {d['label']} — {d.get('detail','')}")
    if v.get("technical"):
        L += ["", f"Technical (how, not why): {v['technical']}"]
    if v.get("not_found"):
        L += ["", "Checked but not found:"] + [f"  · {n}" for n in v["not_found"]]
    if app_url:
        L += ["", f"Full read: {app_url}"]
    return "\n".join(L)


def render_html(v: dict, pr: dict | None = None, app_url: str = "") -> str:
    pr = pr or priority(v)
    color = _TIER_COLOR[pr["tier"]]
    up = v["actual"] >= 0
    move_c = "#15803d" if up else "#b91c1c"
    rows = ""
    for d in v.get("drivers", []):
        link = f' &nbsp;<a href="{d["link"]}" style="color:#2563eb;">evidence</a>' if d.get("link") else ""
        rows += (f'<tr><td style="padding:6px 0;border-top:1px solid #eee;">'
                 f'<span style="display:inline-block;font-size:11px;color:#666;text-transform:uppercase;'
                 f'letter-spacing:.04em;">{d["cls"]}</span><br>'
                 f'<b>{d["label"]}</b> — <span style="color:#444;">{d.get("detail","")}</span>{link}</td></tr>')
    nf = "".join(f"<li>{n}</li>" for n in v.get("not_found", []))
    cta = (f'<a href="{app_url}" style="display:inline-block;margin-top:16px;padding:10px 18px;'
           f'background:{color};color:#fff;text-decoration:none;border-radius:8px;font-weight:600;">'
           f'Open the full read →</a>') if app_url else ""
    tech = (f'<p style="margin:14px 0 0;font-size:13px;color:#555;"><b>Technical</b> (how, not why): '
            f'{v["technical"]}</p>') if v.get("technical") else ""
    return f"""\
<div style="max-width:480px;margin:0 auto;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#111;">
  <div style="background:{color};color:#fff;padding:10px 16px;border-radius:10px 10px 0 0;font-weight:700;
              font-size:13px;letter-spacing:.04em;text-transform:uppercase;">{pr['tier']} · Lighthouse</div>
  <div style="border:1px solid #e5e7eb;border-top:none;border-radius:0 0 10px 10px;padding:18px 16px;">
    <div style="font-size:13px;color:#666;">{v['ticker']} · {v['day']}</div>
    <div style="font-size:34px;font-weight:800;color:{move_c};line-height:1.1;margin:2px 0 8px;">
      {v['actual']*100:+.1f}%</div>
    <p style="margin:0;font-size:14px;line-height:1.5;">{_headline(v)}</p>
    <p style="margin:12px 0 0;font-size:13px;">
      <b>Abnormality:</b> {v['abnormality_conf']} &nbsp;·&nbsp; <b>Explanation:</b> {v['explanation_conf']}</p>
    <p style="margin:8px 0 0;font-size:14px;background:#f8fafc;border-left:3px solid {color};
              padding:8px 10px;border-radius:4px;"><b>IR action:</b> {pr['action']}</p>
    <table style="width:100%;border-collapse:collapse;margin-top:14px;font-size:14px;">{rows}</table>
    {tech}
    <p style="margin:14px 0 4px;font-size:12px;color:#888;">Checked but not found</p>
    <ul style="margin:0;padding-left:18px;font-size:12px;color:#888;">{nf}</ul>
    {cta}
    <p style="margin:18px 0 0;font-size:11px;color:#aaa;">Point-in-time attribution. Abnormality ≠ cause;
      the unexplained portion is labelled honestly, not guessed.</p>
  </div>
</div>"""


def build_digest(v: dict, app_url: str = "") -> dict:
    """Render one verdict dict into every channel. Pure — no send. `app_url` deep-links the CTA."""
    pr = priority(v)
    subject = f"[{pr['tier'].upper()}] {v['ticker']} {v['actual']*100:+.1f}% ({v['day']})"   # ASCII — safe header
    return dict(tier=pr["tier"], rank=pr["rank"], subject=subject,
                sms=render_sms(v, pr, app_url), text=render_text(v, pr, app_url),
                html=render_html(v, pr, app_url))


# ── delivery (each channel fails closed and reports; never raises) ─────────────────────────────────
def send_email(subject, html, text, to_list, c) -> dict:
    if not (c["smtp_user"] and c["smtp_password"] and c["from_email"] and to_list):
        return {"ok": False, "reason": "email_not_configured"}
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = c["from_email"]
        msg["To"] = ", ".join(to_list)
        msg.attach(MIMEText(text, "plain"))
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP_SSL(c["smtp_host"], c["smtp_port"], timeout=30) as s:
            s.login(c["smtp_user"], c["smtp_password"])
            s.sendmail(c["from_email"], to_list, msg.as_string())
        return {"ok": True, "sent_to": to_list}
    except Exception as e:
        return {"ok": False, "reason": f"email_send_error: {e!r}"}


def send_sms(text, to_list, c) -> dict:
    """Twilio via raw HTTP (no extra dependency). Off unless TWILIO_* creds are present."""
    if not (c["twilio_sid"] and c["twilio_token"] and c["twilio_from"] and to_list):
        return {"ok": False, "reason": "sms_not_configured"}
    url = f"https://api.twilio.com/2010-04-01/Accounts/{c['twilio_sid']}/Messages.json"
    auth = base64.b64encode(f"{c['twilio_sid']}:{c['twilio_token']}".encode()).decode()
    sent, errs = [], []
    for num in to_list:
        try:
            data = urllib.parse.urlencode({"To": num, "From": c["twilio_from"], "Body": text[:1500]}).encode()
            req = urllib.request.Request(url, data=data)
            req.add_header("Authorization", "Basic " + auth)
            urllib.request.urlopen(req, timeout=20).read()
            sent.append(num)
        except Exception as e:
            errs.append(f"{num}: {e!r}")
    return {"ok": bool(sent), "sent_to": sent, "errors": errs or None}


def dispatch(v: dict, dry_run: bool | None = None) -> dict:
    """Build + deliver one verdict to every channel whose tier floor it clears. Safe to call from the
    scheduler: gated (disabled by default), tier-filtered, and fully wrapped — it can never raise."""
    try:
        c = config()
        dig = build_digest(v, app_url=c["app_url"])
        report = {"tier": dig["tier"], "subject": dig["subject"], "email": None, "sms": None, "sent": False}
        will_send = (dry_run is False) or (dry_run is None and c["enabled"])
        if not will_send:
            report["reason"] = "preview" if not c["enabled"] else "dry_run"
            return report
        if dig["rank"] >= c["email_floor"] and c["email_to"]:
            report["email"] = send_email(dig["subject"], dig["html"], dig["text"], c["email_to"], c)
        if dig["rank"] >= c["sms_floor"] and c["sms_to"]:
            report["sms"] = send_sms(dig["sms"], c["sms_to"], c)
        report["sent"] = bool((report["email"] or {}).get("ok") or (report["sms"] or {}).get("ok"))
        return report
    except Exception:
        traceback.print_exc()
        return {"sent": False, "reason": "dispatch_error"}


# ── standalone compute (for the CLI preview + a manual re-send) ────────────────────────────────────
def compute_latest_verdict(client_id="usio", cfg=None, conn=None) -> dict:
    """Rebuild (without persisting) the most-recent session's verdict, mirroring shadow's model path."""
    from lighthouse import data, ceo
    from lighthouse.attribution import market_peer_model
    from lighthouse.shadow import SHADOW_TICKERS
    if cfg is None:
        from lighthouse.config.usio import USIO
        cfg = USIO
    rets = data.returns_frame(SHADOW_TICKERS, conn=conn)
    model = market_peer_model(rets, issuer=cfg["ticker"], market="IWM",
                              peers=cfg["business_peers"], window=126)
    day = list(model.index)[-1]
    return ceo.build_verdict(client_id, cfg["ticker"], day, model.loc[day], conn=conn)


if __name__ == "__main__":
    import sys
    send = "--send" in sys.argv                       # default is PREVIEW (never sends)
    v = compute_latest_verdict()
    c = config()
    dig = build_digest(v, app_url=c["app_url"])
    print("=" * 72)
    print("SUBJECT:", dig["subject"])
    print("-" * 72)
    print(dig["text"])
    print("-" * 72)
    print("SMS:", dig["sms"], f"({len(dig['sms'])} chars)")
    print("=" * 72)
    if send:
        print("[digest] sending…", dispatch(v, dry_run=False))
    else:
        print(f"[digest] preview only. enabled={c['enabled']} email_to={c['email_to'] or '—'} "
              f"sms_to={c['sms_to'] or '—'}. Re-run with --send to deliver.")
