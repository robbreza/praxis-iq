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


def _imap_host():
    host = os.environ.get("ZOHO_SMTP_HOST", "smtp.zoho.com")
    return host.replace("smtp.", "imap.", 1) if host.startswith("smtp.") else "imap.zoho.com"


def imap_login():
    """A logged-in imaplib.IMAP4_SSL to the Zoho account (same app password as SMTP), or
    (None, error). Callers must close it. Used to file Sent copies and to poll for replies."""
    import imaplib
    user, pw, *_ = _cfg()
    if not (user and pw):
        return None, "Zoho isn't connected yet — set ZOHO_SMTP_USER and ZOHO_SMTP_PASS."
    try:
        im = imaplib.IMAP4_SSL(_imap_host(), 993)
        im.login(user, pw)
        return im, None
    except Exception as e:
        return None, str(e)


def _append_to_sent(msg):
    """Best-effort: file a copy of a just-sent message into the Zoho 'Sent' folder via IMAP, so
    it shows up in the mailbox exactly like a normally-sent email. An SMTP send does NOT do this
    on its own — that's why sends from the app never appeared in Sent. Non-fatal: any failure
    (IMAP disabled, wrong folder name) is swallowed by the caller; the email still went out and
    the in-app correspondence trail is the authoritative record regardless."""
    import imaplib
    import time
    copy = EmailMessage()
    for k in ("From", "To", "Subject", "Message-ID"):
        if msg[k]:
            copy[k] = msg[k]
    copy.set_content(msg.get_content())          # drop Bcc etc. from the filed copy
    im, err = imap_login()
    if not im:
        raise RuntimeError(err)
    try:
        im.append("Sent", "\\Seen", imaplib.Time2Internaldate(time.time()), copy.as_bytes())
    finally:
        try:
            im.logout()
        except Exception:
            pass


def send_email(to, subject, body, bcc=None, save_to_sent=True, message_id=None):
    """Send one email from the configured Zoho account. Returns (ok, error). Blocking SMTP —
    call from a worker thread (asyncio.to_thread) so the UI event loop isn't held.

    `bcc` blind-copies an address (e.g. the sender itself) so there's always a durable record.
    `save_to_sent` also files a copy into the Zoho 'Sent' folder via IMAP (best-effort) — since a
    plain SMTP send otherwise leaves no trace in the mailbox's Sent folder."""
    user, pw, host, port, from_name = _cfg()
    if not (user and pw):
        return False, "Zoho isn't connected yet — set ZOHO_SMTP_USER and ZOHO_SMTP_PASS."
    if not (to or "").strip():
        return False, "No recipient email on this lead."

    msg = EmailMessage()
    msg["From"] = f"{from_name} <{user}>" if from_name else user
    msg["To"] = to.strip()
    if bcc:
        msg["Bcc"] = bcc.strip() if isinstance(bcc, str) else ", ".join(bcc)
    msg["Subject"] = subject or ""
    if message_id:                               # stable id so an inbound reply can be threaded back
        msg["Message-ID"] = message_id
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
    except smtplib.SMTPAuthenticationError:
        return False, ("Zoho rejected the login — check ZOHO_SMTP_USER is your full email and "
                       "ZOHO_SMTP_PASS is an app-specific password (not your normal password).")
    except Exception as e:
        return False, str(e)

    if save_to_sent:
        try:
            _append_to_sent(msg)
        except Exception as e:
            print(f"[zoho_mail] sent-folder copy skipped (non-fatal): {e}")
    return True, None
