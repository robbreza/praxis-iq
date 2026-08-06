"""core/zoho_mail.py — send a reviewed outreach email through the operator's Zoho account.

Used by the Console lead-email flow: the human reviews (and edits) the personalized draft in
the dialog, then clicks "Send via Zoho" — a deliberate send, not automatic. This is SALES
outreach to a prospective CLIENT who visited praxispointir.com, distinct from the
IR/shareholder comms that IRconnect never auto-sends (Reg FD); still, it always goes out only
on an explicit click after review.

Auth is plain SMTP with an app-specific password (no OAuth): the operator generates an app
password in Zoho (Settings -> Security -> App passwords) and sets ZOHO_SMTP_USER /
ZOHO_SMTP_PASS in the app's .env. Regional data centers are handled via ZOHO_SMTP_HOST
(default smtp.zoho.com) — e.g. smtp.zoho.eu / smtp.zoho.in. Credentials are read from the
environment; this module never stores or logs them.
"""
import os
import smtplib
import ssl
from email.message import EmailMessage


def _cfg():
    return (os.environ.get("ZOHO_SMTP_USER"), os.environ.get("ZOHO_SMTP_PASS"),
            os.environ.get("ZOHO_SMTP_HOST", "smtp.zoho.com"),
            int(os.environ.get("ZOHO_SMTP_PORT", "465")),
            os.environ.get("ZOHO_FROM_NAME", "Praxis Point"))


def is_configured():
    """True once ZOHO_SMTP_USER and ZOHO_SMTP_PASS are set — the "Send via Zoho" button
    only appears then, so the app degrades cleanly to Copy / Open-in-email before setup."""
    u, p, *_ = _cfg()
    return bool(u and p)


def verify_connection():
    """Connect and authenticate to Zoho SMTP WITHOUT sending anything — confirms the app
    password is valid before it's relied on. Returns (ok, error)."""
    user, pw, host, port, _ = _cfg()
    if not (user and pw):
        return False, "Zoho isn't connected yet — set ZOHO_SMTP_USER and ZOHO_SMTP_PASS."
    try:
        ctx = ssl.create_default_context()
        if port == 587:
            with smtplib.SMTP(host, port, timeout=25) as s:
                s.starttls(context=ctx)
                s.login(user, pw)
        else:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=25) as s:
                s.login(user, pw)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, ("Zoho rejected the login — ZOHO_SMTP_PASS must be an app-specific "
                       "password (not your normal password), and ZOHO_SMTP_USER your full email.")
    except Exception as e:
        return False, str(e)


def send_email(to, subject, body):
    """Send one email from the configured Zoho account. Returns (ok, error). Blocking SMTP —
    call from a worker thread (asyncio.to_thread) so the UI event loop isn't held."""
    user, pw, host, port, from_name = _cfg()
    if not (user and pw):
        return False, "Zoho isn't connected yet — set ZOHO_SMTP_USER and ZOHO_SMTP_PASS."
    if not (to or "").strip():
        return False, "No recipient email on this lead."

    msg = EmailMessage()
    msg["From"] = f"{from_name} <{user}>" if from_name else user
    msg["To"] = to.strip()
    msg["Subject"] = subject or ""
    msg.set_content(body or "")
    try:
        ctx = ssl.create_default_context()
        if port == 587:
            with smtplib.SMTP(host, port, timeout=25) as s:
                s.starttls(context=ctx)
                s.login(user, pw)
                s.send_message(msg)
        else:
            with smtplib.SMTP_SSL(host, port, context=ctx, timeout=25) as s:
                s.login(user, pw)
                s.send_message(msg)
        return True, None
    except smtplib.SMTPAuthenticationError:
        return False, ("Zoho rejected the login — check ZOHO_SMTP_USER is your full email and "
                       "ZOHO_SMTP_PASS is an app-specific password (not your normal password).")
    except Exception as e:
        return False, str(e)
