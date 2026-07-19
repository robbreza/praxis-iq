"""core/email_finder.py — Anymail Finder integration (the email half of the contact layer).

WHY: EDGAR gives us the real person behind every 13F filer — name, title, direct phone (see
core/contacts.py) — but it does NOT publish email addresses. This module fills only that gap, and
it only works because those names are real; enriching the old fabricated "IR Desk" placeholders
would have burned credits for nothing.

API CONTRACT (verified against anymailfinder.com/email-finder-api/docs, v5.1):
    POST https://api.anymailfinder.com/v5.1/find-email/person
    Header: Authorization: <api_key>          (a bare key — NOT "Bearer <key>")
    Body:   {full_name, and one of domain (most accurate) | company_name}
    200 -> {credits_charged, email, email_status, valid_email, mx_domain, ...}
           email_status: valid | risky | not_found | blacklisted
    400 bad request · 401 bad/missing key · 402 out of credits

COST DISCIPLINE — the rules that keep this cheap:
  * Only `valid` charges a credit; risky/not_found/blacklisted are FREE, and a repeat search for
    the same person within 30 days is free.
  * We RECORD misses (status + checked_at) so we never re-query the same person in a loop.
  * On-demand only — never called from a page render, same rule as the 13F/consensus refreshes.
  * enrich_missing() takes an explicit limit and supports dry_run, so a bulk run can be previewed
    before it spends anything.

The API key is read from the environment (ANYMAILFINDER_API_KEY) and is never logged.
"""
import os
import re

import requests

from core import contacts

API_URL = "https://api.anymailfinder.com/v5.1/find-email/person"
DEFAULT_TIMEOUT = 180          # the vendor's own recommendation — lookups can be slow
VALID = "valid"

# Legal-entity suffixes on EDGAR filer names ("CITADEL ADVISORS LLC") hurt company-name matching.
_SUFFIX_RE = re.compile(
    r"\b(l\.?l\.?c|inc|incorporated|corp|corporation|co|company|l\.?p|l\.?l\.?p|ltd|limited|plc|"
    r"n\.?a|trust|holdings?|group|partners|management|advisors|advisers)\b\.?", re.I)


def api_key():
    """The Anymail Finder key from the environment. Returns None if unset — callers must degrade
    rather than crash, exactly like the optional routing key."""
    try:
        from core.security import load_environment
        load_environment()
    except Exception:
        pass
    return os.environ.get("ANYMAILFINDER_API_KEY") or None


def api_key_present():
    return bool(api_key())


def clean_company(name):
    """EDGAR filer name -> a company name the finder can match ('CITADEL ADVISORS LLC' ->
    'CITADEL'). Drops parentheticals like 'AMERIPRISE FINANCIAL INC  (AMP)' and entity suffixes.
    Falls back to the original if stripping leaves nothing."""
    n = re.sub(r"\(.*?\)", " ", name or "")
    n = _SUFFIX_RE.sub(" ", n)
    n = re.sub(r"[^\w& ]+", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n or (name or "").strip()


def find_person_email(full_name, domain=None, company_name=None, timeout=DEFAULT_TIMEOUT):
    """One lookup. Returns a normalized dict — never raises for an API-level failure:
        {ok, email, status, credits, error}
    status is the vendor's email_status (valid/risky/not_found/blacklisted) or an error slug."""
    key = api_key()
    if not key:
        return {"ok": False, "email": None, "status": "no_api_key", "credits": 0,
                "error": "ANYMAILFINDER_API_KEY is not set"}
    if not full_name or not (domain or company_name):
        return {"ok": False, "email": None, "status": "bad_request", "credits": 0,
                "error": "need full_name plus domain or company_name"}

    body = {"full_name": full_name}
    if domain:
        body["domain"] = domain          # most accurate per the vendor
    else:
        body["company_name"] = company_name

    try:
        r = requests.post(API_URL, json=body, timeout=timeout,
                          headers={"Authorization": key, "Content-Type": "application/json"})
    except Exception as e:
        return {"ok": False, "email": None, "status": "request_failed", "credits": 0, "error": str(e)}

    if r.status_code == 401:
        return {"ok": False, "email": None, "status": "unauthorized", "credits": 0,
                "error": "API key rejected"}
    if r.status_code == 402:
        return {"ok": False, "email": None, "status": "out_of_credits", "credits": 0,
                "error": "insufficient credits"}
    if r.status_code == 400:
        return {"ok": False, "email": None, "status": "bad_request", "credits": 0,
                "error": (r.text or "")[:200]}
    if r.status_code != 200:
        return {"ok": False, "email": None, "status": f"http_{r.status_code}", "credits": 0,
                "error": (r.text or "")[:200]}

    try:
        d = r.json()
    except Exception:
        return {"ok": False, "email": None, "status": "bad_response", "credits": 0,
                "error": (r.text or "")[:200]}

    status = (d.get("email_status") or "unknown").lower()
    # Only trust an address the vendor calls valid; `valid_email` is populated only in that case.
    email = d.get("valid_email") or (d.get("email") if status == VALID else None)
    return {"ok": status == VALID, "email": email, "status": status,
            "credits": d.get("credits_charged") or 0, "error": None}


def enrich_contact(contact, dry_run=False):
    """Resolve one contact's email and persist the outcome (including a miss). `contact` is a row
    from core.contacts.list_contacts()."""
    name = contact.get("name")
    domain = contact.get("domain")
    company = None if domain else clean_company(contact.get("firm"))
    if dry_run:
        return {"contact_id": contact["contact_id"], "name": name,
                "query": {"domain": domain} if domain else {"company_name": company},
                "status": "dry_run", "credits": 0}
    res = find_person_email(name, domain=domain, company_name=company)
    # Persist valid hits AND misses; only a `valid` result stores an actual address.
    if res["status"] not in ("no_api_key", "unauthorized", "out_of_credits", "request_failed"):
        contacts.set_email_result(contact["contact_id"], res["email"], res["status"])
    return {"contact_id": contact["contact_id"], "name": name, "firm": contact.get("firm"),
            "email": res["email"], "status": res["status"], "credits": res["credits"],
            "error": res.get("error")}


def enrich_missing(limit=None, dry_run=False, firm=None, recheck=False):
    """Enrich contacts that have no email yet.

    Skips anyone already resolved, and (unless recheck=True) anyone already checked — that's what
    prevents re-querying known misses. `limit` caps the run; `dry_run` previews it without
    spending. Stops early on a fatal API condition (bad key / out of credits) rather than
    hammering."""
    rows = contacts.list_contacts(firm=firm)
    todo = [c for c in rows if not c.get("email") and
            (recheck or not c.get("email_checked_at"))]
    if limit:
        todo = todo[:limit]

    out, credits, found = [], 0, 0
    for c in todo:
        r = enrich_contact(c, dry_run=dry_run)
        out.append(r)
        credits += r.get("credits") or 0
        if r.get("email"):
            found += 1
        if r.get("status") in ("unauthorized", "out_of_credits", "no_api_key"):
            break                      # fatal — stop the batch
    return {"considered": len(rows), "attempted": len(out), "found": found,
            "credits_spent": credits, "dry_run": dry_run, "results": out}
