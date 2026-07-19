"""core/contacts.py — the person-level IDENTITY layer for the investor universe.

WHY THIS EXISTS
The target database is institution-level (fund, AUM, holdings, conviction). The person layer used
to be `data/seed/institution_contacts.py` — 62 fabricated records ("IR Desk", 555- phone numbers,
generic ir@firm.com addresses). Those were demo scaffolding that was never replaced with the real
extraction, and they fed the mail gateway's contact_lookup, so inbound routing was matching against
addresses that don't exist.

WHERE THE REAL DATA COMES FROM
Every Form 13F carries a `<signatureBlock>` on its cover page (primary_doc.xml) with the filer's
signing officer: NAME, TITLE and a direct PHONE. We already store each holder's CIK + accession
(see core/sec_filings), so this is a free, authoritative, structured pull — no name-matching, no
guessing. EDGAR does NOT publish filer email addresses; that gap is what an email-finder service
(Anymailfinder, Phase 2) fills, and it only works because these names are real.

SCOPE — IDENTITY vs RELATIONSHIP
This store is deliberately NOT scoped by client_id. A Vanguard VP is the same person whichever
tenant we're targeting for, so we resolve a person once and reuse them everywhere (that also means
one paid email lookup, not one per client). The RELATIONSHIP layer — holdings, conviction, coverage
priority, meetings, notes, outreach history — stays client-scoped in the JSON stores where it
already lives.
"""
import html
import re
from datetime import datetime

from core import db

# email_status values (populated in Phase 2 by the email finder; 'unknown' until then)
EMAIL_UNKNOWN = "unknown"

# 60s memo for institution_contacts_map() — see its docstring. Cleared on every write.
_MAP_MEMO = {"at": None, "val": None}

_COLS = ("contact_id", "cik", "firm", "firm_key", "name", "title", "phone", "email",
         "email_status", "email_source", "email_checked_at", "domain", "source",
         "source_ref", "created_at", "updated_at")


def _norm(s):
    """Normalize a firm name for matching (same intent as fund_addresses._norm)."""
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


def _slug(s):
    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")


def norm_cik(cik):
    """Canonical CIK: digits, no leading zeros. EDGAR emits zero-padded ('0001364742') in some
    places and bare in others; storing one form keeps lookups by CIK reliable."""
    if cik is None:
        return None
    d = re.sub(r"\D", "", str(cik))
    return (d.lstrip("0") or "0") if d else None


def contact_id_for(cik, name, firm=None):
    """Deterministic id so re-running the EDGAR pull UPSERTS instead of duplicating people."""
    if cik:
        return f"{norm_cik(cik)}:{_slug(name)}"
    return f"manual:{_slug(firm)}:{_slug(name)}"


def _row(r):
    return dict(zip(_COLS, r))


def upsert_contact(name, firm, cik=None, title=None, phone=None, email=None,
                   email_status=None, email_source=None, domain=None,
                   source="manual", source_ref=None):
    """Insert or update one person (keyed by contact_id_for). Returns the contact_id.

    Only overwrites email fields when an email is actually supplied, so a later EDGAR re-pull
    (which carries no email) never wipes an address resolved in Phase 2."""
    if not name or not firm:
        return None
    cik = norm_cik(cik)
    cid = contact_id_for(cik, name, firm)
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        now = datetime.now()
        now_v = now if pg else now.isoformat()
        cur.execute(f"SELECT contact_id FROM contacts WHERE contact_id = {ph}", (cid,))
        exists = cur.fetchone() is not None
        if exists:
            sets = [f"firm = {ph}", f"firm_key = {ph}", f"name = {ph}", f"updated_at = {ph}"]
            vals = [firm, _norm(firm), name, now_v]
            for col, val in (("cik", cik), ("title", title), ("phone", phone),
                             ("domain", domain), ("source", source), ("source_ref", source_ref)):
                if val is not None:
                    sets.append(f"{col} = {ph}")
                    vals.append(val)
            if email is not None:
                sets += [f"email = {ph}", f"email_status = {ph}", f"email_source = {ph}",
                         f"email_checked_at = {ph}"]
                vals += [email, email_status or EMAIL_UNKNOWN, email_source, now_v]
            vals.append(cid)
            cur.execute(f"UPDATE contacts SET {', '.join(sets)} WHERE contact_id = {ph}", vals)
        else:
            cur.execute(
                f"INSERT INTO contacts ({', '.join(_COLS)}) "
                f"VALUES ({', '.join([ph] * len(_COLS))})",
                (cid, cik, firm, _norm(firm), name, title, phone, email,
                 (email_status or EMAIL_UNKNOWN) if email else EMAIL_UNKNOWN,
                 email_source, now_v if email else None, domain, source, source_ref,
                 now_v, now_v))
        conn.commit()
        _MAP_MEMO.update({"at": None, "val": None})
        return cid
    finally:
        conn.close()


def set_email_result(contact_id, email, status, source="anymailfinder"):
    """Record an email-finder outcome — including a MISS. Storing not_found/risky (with a
    checked_at stamp) is what stops us re-querying the same person forever; only `valid` results
    put an actual address on the record, so outreach can never fire at an unverified one."""
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        now = datetime.now()
        now_v = now if pg else now.isoformat()
        cur.execute(
            f"UPDATE contacts SET email = {ph}, email_status = {ph}, email_source = {ph}, "
            f"email_checked_at = {ph}, updated_at = {ph} WHERE contact_id = {ph}",
            (email, status, source, now_v, now_v, contact_id))
        conn.commit()
        _MAP_MEMO.update({"at": None, "val": None})
        return cur.rowcount
    finally:
        conn.close()


def list_contacts(firm=None, cik=None, limit=None):
    """Contacts, optionally filtered by firm (normalized match) or CIK."""
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        where, params = [], []
        if firm:
            where.append(f"firm_key = {ph}")
            params.append(_norm(firm))
        if cik:
            where.append(f"cik = {ph}")
            params.append(norm_cik(cik))
        sql = f"SELECT {', '.join(_COLS)} FROM contacts"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY firm, name"
        if limit:
            sql += f" LIMIT {int(limit)}"
        cur.execute(sql, params)
        return [_row(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_contact(contact_id):
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"SELECT {', '.join(_COLS)} FROM contacts WHERE contact_id = {ph}", (contact_id,))
        row = cur.fetchone()
        return _row(row) if row else None
    finally:
        conn.close()


def delete_contact(contact_id):
    conn = db.get_connection()
    pg = db.connection_is_postgres(conn)
    try:
        cur = conn.cursor()
        ph = "%s" if pg else "?"
        cur.execute(f"DELETE FROM contacts WHERE contact_id = {ph}", (contact_id,))
        conn.commit()
        _MAP_MEMO.update({"at": None, "val": None})
        return cur.rowcount
    finally:
        conn.close()


def count_contacts():
    conn = db.get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM contacts")
        return cur.fetchone()[0]
    finally:
        conn.close()


def institution_contacts_map():
    """`{firm_name: {name, email, title, phone}}` — the shape the app's existing callers expect
    (investors_page meeting contacts / autocomplete, mail_gateway's contact_lookup, search).
    Backed by the real contacts store now instead of the fabricated seed. One primary person per
    firm (the first by name); the full list is available via list_contacts(firm=...).

    MEMOISED (60s): this replaced a module-level constant, and several call sites invoke it inside
    per-row loops — without the memo that's one Postgres round-trip per meeting row. Writes clear
    the memo, so edits show up immediately."""
    hit = _MAP_MEMO.get("val")
    if hit is not None and (datetime.now() - _MAP_MEMO["at"]).total_seconds() < 60:
        return hit
    out = {}
    for c in list_contacts():
        if c["firm"] not in out:
            out[c["firm"]] = {"name": c["name"], "email": c["email"] or "",
                              "title": c["title"] or "", "phone": c["phone"] or ""}
    _MAP_MEMO.update({"at": datetime.now(), "val": out})
    return out


# ── EDGAR extraction ───────────────────────────────────────────────────────
_SIG_RE = re.compile(r"<signatureBlock>(.*?)</signatureBlock>", re.S | re.I)


def _tag(block, tag):
    m = re.search(rf"<{tag}>(.*?)</{tag}>", block, re.S | re.I)
    if not m:
        return None
    # unescape XML entities — filers write "Operations &amp; Investor Services"
    return re.sub(r"\s+", " ", html.unescape(m.group(1))).strip()


def _clean_name(name):
    """Some filers type the electronic-signature marker into the name field (BlackRock files
    '/s/ Spencer Fleming'). Strip it so the person's name — and the derived contact_id — are clean."""
    n = re.sub(r"^\s*/s/\s*", "", name or "", flags=re.I).strip()
    return re.sub(r"\s+", " ", n).strip(" .,")


def signatory_from_13f(cik, accession, timeout=20):
    """Pull the signing officer (name/title/phone) off one 13F cover page (primary_doc.xml).
    Returns a dict or None. This is the authoritative, free source for the person layer."""
    from core import sec_filings
    try:
        cik_i = str(int(cik))
    except Exception:
        return None
    acc = str(accession or "").replace("-", "")
    if not acc:
        return None
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_i}/{acc}/primary_doc.xml"
    try:
        xml = sec_filings._get(url, timeout=timeout).content.decode("utf-8", "ignore")
    except Exception:
        return None
    m = _SIG_RE.search(xml)
    if not m:
        return None
    blk = m.group(1)
    name = _clean_name(_tag(blk, "name"))
    if not name:
        return None
    return {"name": name, "title": _tag(blk, "title"), "phone": _tag(blk, "phone")}


def refresh_from_13f(client_id=None, ticker=None, throttle=0.15, limit=None):
    """Walk the cached 13F holders for a client's ticker and store each filer's signing officer.

    Free and authoritative — no name-matching, because each holder already carries its CIK and the
    exact accession we read. Idempotent (deterministic contact_id), and never clobbers an email
    resolved later. Returns a summary dict."""
    import time
    from core import sec_filings
    from config.client_config import CT

    tk = (ticker or CT("ticker") or "").upper()
    book = sec_filings.get_cached_13f_holders(tk) if tk else None
    holders = (book or {}).get("holders") or []
    if limit:
        holders = holders[:limit]

    made, skipped, failed = [], 0, 0
    for h in holders:
        cik, acc, firm = h.get("cik"), h.get("accession"), h.get("filer")
        if not (cik and acc and firm):
            skipped += 1
            continue
        sig = signatory_from_13f(cik, acc)
        if not sig:
            failed += 1
        else:
            cid = upsert_contact(name=sig["name"], firm=firm, cik=str(cik),
                                 title=sig.get("title"), phone=sig.get("phone"),
                                 source="edgar_13f", source_ref=acc)
            if cid:
                made.append((firm, sig["name"]))
        if throttle:
            time.sleep(throttle)   # be polite to SEC
    return {"ticker": tk, "holders": len(holders), "stored": len(made),
            "no_signature_block": failed, "skipped": skipped, "contacts": made}
