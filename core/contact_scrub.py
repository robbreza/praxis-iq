"""core/contact_scrub.py — Phase-2 free-first email/deliverability scrubbing (§04).

First pass: structural + DNS signals that need no paid API and no per-person network
call beyond one MX lookup per DOMAIN (cached for the batch). It catches the
definitively dead (bad syntax, no mail exchanger) and flags the non-personal (role,
free-provider), then writes validation_status + confidence + email_status.

It NEVER upgrades a contact to 'verified' — that requires person/firm currency
(EDGAR firm-exists, current-13F-signatory match, FINRA/IAPD/FCA/ASIC registration —
Phase 2b) or a real-send bounce result. So the best a purely-structural pass can
assert is 'probable': "the address looks deliverable; we have not confirmed the
person is still there." That honesty is the whole point on a 5-year-old list.
"""
import re
from datetime import datetime

from core import db

# consumer/free providers — deliverable but not firm-attributable (kept local so this
# module doesn't drag in the mail_gateway import chain).
_FREE = {"gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com", "hotmail.com",
         "live.com", "aol.com", "icloud.com", "me.com", "mac.com", "proton.me", "protonmail.com",
         "msn.com", "gmx.com", "mail.com", "comcast.net", "verizon.net", "sbcglobal.net"}
_DISPOSABLE = {"mailinator.com", "guerrillamail.com", "10minutemail.com", "tempmail.com",
               "trashmail.com", "yopmail.com", "getnada.com", "throwawaymail.com", "sharklasers.com"}
_SYNTAX = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
_ROLE = re.compile(r"^(info|ir|contact|contactus|sales|admin|administrator|research|team|hello|"
                   r"support|inquiries|enquiries|office|mail|general|marketing|media|press|"
                   r"compliance|operations|ops|help|noreply|no-reply|donotreply|invest)@", re.I)

_MX_CACHE = {}   # domain -> True (has MX) | False (does not resolve) | None (ambiguous/unknown)


def _mx_ok(domain, timeout=4):
    if not domain:
        return None
    if domain in _MX_CACHE:
        return _MX_CACHE[domain]
    try:
        import dns.resolver
    except Exception:
        return None                      # dnspython unavailable -> can't assert
    ok = None
    try:
        ans = dns.resolver.resolve(domain, "MX", lifetime=timeout)
        ok = len(ans) > 0
    except Exception:
        try:
            dns.resolver.resolve(domain, "A", lifetime=timeout)
            ok = None                    # resolves but no MX -> ambiguous, not a hard fail
        except Exception:
            ok = False                   # doesn't resolve at all -> dead
    _MX_CACHE[domain] = ok
    return ok


def check_email(email):
    """Structural + DNS signals for one address. Makes no person-currency claim."""
    e = (email or "").strip().lower()
    out = {"email": e or None, "syntax": False, "domain": None,
           "is_free": False, "is_role": False, "is_disposable": False, "mx": None}
    if not e or "@" not in e:
        return out
    out["syntax"] = bool(_SYNTAX.match(e))
    dom = e.rsplit("@", 1)[-1]
    out.update(domain=dom, is_free=dom in _FREE, is_disposable=dom in _DISPOSABLE,
               is_role=bool(_ROLE.match(e)))
    if out["syntax"]:
        out["mx"] = _mx_ok(dom)
    return out


def score_email(chk):
    """(validation_status, confidence 0-100, email_status) from a check dict.
    Ceiling is 'probable' — structural checks cannot prove a person is current."""
    if not chk.get("email"):
        return "unknown", 0, "unknown"          # no email -> Phase-2b firm checks decide
    if not chk["syntax"]:
        return "invalid", 3, "bad_syntax"
    if chk["is_disposable"]:
        return "invalid", 5, "disposable"
    if chk["mx"] is False:
        return "invalid", 8, "dead_domain"
    if chk["is_role"]:
        return "probable", 30, "role_address"
    if chk["is_free"]:
        return "probable", 40, "free_provider"
    if chk["mx"] is True:
        return "probable", 62, "mx_ok"
    return "probable", 45, "syntax_ok"           # MX unknown (no dnspython / ambiguous)


def batch_scrub(where="email IS NOT NULL", limit=None):
    """Scrub contacts matching `where` (a TRUSTED literal — never interpolate user input),
    writing validation_status/confidence/email_status/email_checked_at. One MX lookup per
    unique domain; a single bulk UPDATE. Returns a status histogram.

    The DNS phase can run for minutes, so it is done holding NO connection — a pooled
    Neon connection left idle that long gets closed server-side ("SSL connection closed
    unexpectedly"). Fetch, then score offline, then write on a fresh connection."""
    # 1. fetch the work set (short-lived connection)
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        sql = f"SELECT contact_id, email FROM contacts WHERE {where}"
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql)
        rows = cur.fetchall()
    finally:
        conn.close()

    # 2. slow scoring — MX lookups, NO DB connection held
    updates, hist = [], {}
    for cid, email in rows:
        status, conf, estatus = score_email(check_email(email))
        updates.append((cid, status, conf, estatus))
        hist[status] = hist.get(status, 0) + 1

    # 3. write on a fresh connection
    if updates:
        _write_updates(updates)
    return {"scrubbed": len(rows), "unique_domains": len(_MX_CACHE),
            "by_status": dict(sorted(hist.items(), key=lambda x: -x[1]))}


def _write_updates(updates):
    """Bulk-write (validation_status, confidence, email_status) — a fresh connection so a
    long DNS phase can't have aged out a pooled one."""
    from core.security import get_database_url
    dsn = get_database_url()
    if dsn:
        import psycopg2
        from psycopg2.extras import execute_values
        conn = psycopg2.connect(dsn)
        try:
            cur = conn.cursor()
            execute_values(
                cur,
                "UPDATE contacts AS c SET validation_status = v.s, confidence = v.conf::int, "
                "email_status = v.es, email_checked_at = now(), updated_at = now() "
                "FROM (VALUES %s) AS v(cid, s, conf, es) WHERE c.contact_id = v.cid",
                updates, page_size=500)
            conn.commit()
        finally:
            conn.close()
    else:
        conn = db.get_connection()
        try:
            cur = conn.cursor()
            now = datetime.now().isoformat()
            for cid, status, conf, estatus in updates:
                cur.execute("UPDATE contacts SET validation_status=?, confidence=?, "
                            "email_status=?, email_checked_at=?, updated_at=? WHERE contact_id=?",
                            (status, conf, estatus, now, now, cid))
            conn.commit()
        finally:
            conn.close()
