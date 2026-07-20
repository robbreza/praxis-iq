"""core/form_adv.py — SEC Form ADV (Investment Adviser Information Reports).

NAMING: this module is `form_adv`, never bare `adv` — in this codebase "ADV" already means AVERAGE
DAILY VOLUME (see core/risk_scorecard.py's float/ADV liquidity signal). Keep them distinct.

WHAT THIS IS FOR
Our contact layer had zero domains (see core/contacts.py), so every Anymail Finder lookup fell back
to `company_name` when the vendor calls `domain` "most accurate". Form ADV Item 1I carries each
registered adviser's website. It also carries real regulatory AUM (Item 5F), the main office
address, and the phone — free, authoritative, filed under penalty of perjury, refreshed monthly.

WHY THE JOIN IS SAFE
The dataset includes a `CIK#` column, so we join to our 13F holders EXACTLY by CIK. That matters:
core/fund_addresses.py documents an explicit policy against automatic name->CIK matching because it
false-matches badly ("BlackRock" resolving to a tiny Isle-of-Man subsidiary). We never name-match
here. Roughly half of all advisers have no CIK (they never file with EDGAR) — those simply don't
join, which is correct rather than guessed.

WHAT IT DOES NOT HAVE (checked, not assumed)
The bulk report covers Form ADV Items 1-11 only. It does NOT include the Item 1J Chief Compliance
Officer email, and it does NOT include Schedule A (direct owners / executive officers). So this
closes the DOMAIN gap and gives real AUM — it does not hand us investment-role contacts. Those
still need IAPD per-firm lookups or the relationship layer.

NO PARALLEL STORES
Addresses are owned by core/fund_addresses.py. This module feeds that module's set_address() API
with source="form_adv" rather than creating a competing address book.
"""
import csv
import io
import re
import zipfile

import requests

# Identify Praxis Point to the SEC (their fair-access policy asks for a real contact).
_UA = {"User-Agent": "PraxisPoint IR robbreza@yahoo.com"}
_INDEX_URL = ("https://www.sec.gov/data-research/sec-markets-data/"
              "information-about-registered-investment-advisers-exempt-reporting-advisers")
_FILE_RE = re.compile(r'href="([^"]*/ia(\d{2})(\d{2})(\d{2})[^"]*\.zip)"', re.I)

# Column headers in the FOIA firm-roster CSV (verified against the June 2026 file).
COL_CIK = "CIK#"
COL_NAME = "Primary Business Name"
COL_LEGAL = "Legal Name"
COL_CRD = "Organization CRD#"
COL_WEBSITE = "Website Address"
COL_PHONE = "Main Office Telephone Number"
COL_ADDR1 = "Main Office Street Address 1"
COL_ADDR2 = "Main Office Street Address 2"
COL_CITY = "Main Office City"
COL_STATE = "Main Office State"
COL_ZIP = "Main Office Postal Code"
COL_RAUM = "5F(2)(c)"          # regulatory assets under management ($)
COL_ACCOUNTS = "5F(2)(f)"      # number of accounts


def latest_dataset_url():
    """Discover the newest monthly Investment Adviser Information Report ZIP.

    Deliberately discovered, not hardcoded — the filename encodes a date (ia<MMDDYY>.zip, sometimes
    with a `_0` suffix) and would go stale every month."""
    r = requests.get(_INDEX_URL, headers=_UA, timeout=30)
    r.raise_for_status()
    best, best_key = None, None
    for m in _FILE_RE.finditer(r.text):
        href, mm, dd, yy = m.group(1), m.group(2), m.group(3), m.group(4)
        # Test the FILENAME, not the path: the real files live in a directory literally named
        # "...advisers-exempt-reporting-advisers/", so matching on the whole href excludes every
        # good file and silently falls back to a years-old stray artifact. The reduced
        # exempt-reporting dataset is the one named "ia<date>-exempt.zip".
        if "exempt" in href.rsplit("/", 1)[-1].lower():
            continue
        key = (yy, mm, dd)
        if best_key is None or key > best_key:
            best, best_key = href, key
    if not best:
        return None
    return best if best.startswith("http") else f"https://www.sec.gov{best}"


# Firms sometimes file a SOCIAL or directory URL in Item 1I instead of their own site (Citadel
# filed instagram.com, SeaBridge filed linkedin.com). Storing those as the firm's domain is worse
# than storing nothing: an email lookup keyed on "instagram.com" burns credits and can return an
# address at the wrong company entirely.
_NON_CORPORATE_DOMAINS = {
    "linkedin.com", "instagram.com", "facebook.com", "fb.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "google.com", "plus.google.com", "sec.gov",
    "adviserinfo.sec.gov", "brokercheck.finra.org", "finra.org", "wordpress.com",
    "blogspot.com", "wixsite.com", "godaddysites.com",
}


def _domain_from_website(url):
    """'HTTPS://WWW.EXAMPLE.COM/advisors' -> 'example.com'. None if unusable or non-corporate."""
    if not url:
        return None
    u = str(url).strip().lower()
    u = re.sub(r"^[a-z]+://", "", u)
    u = u.split("/")[0].split("?")[0].strip()
    u = re.sub(r"^www\d?\.", "", u)
    if not u or "." not in u or " " in u:
        return None
    if u in _NON_CORPORATE_DOMAINS:
        return None
    return u


def _num(s):
    try:
        return float(re.sub(r"[^\d.\-]", "", str(s or "")) or 0) or None
    except ValueError:
        return None


def fetch_by_cik(ciks, url=None):
    """Download the latest report and return {normalized_cik: record} for the requested CIKs only.

    We extract just the CIKs we hold rather than persisting ~15k advisers — the file is ~5MB and
    parses in seconds, so there's no reason to carry a copy of the whole registry."""
    from core.contacts import norm_cik
    wanted = {norm_cik(c) for c in (ciks or []) if norm_cik(c)}
    if not wanted:
        return {}
    url = url or latest_dataset_url()
    if not url:
        return {}
    r = requests.get(url, headers=_UA, timeout=180)
    r.raise_for_status()

    out = {}
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
        if not name:
            return {}
        with z.open(name) as fh:
            text = io.TextIOWrapper(fh, encoding="latin-1", newline="")
            for row in csv.DictReader(text):
                cik = norm_cik(row.get(COL_CIK))
                if not cik or cik not in wanted or cik in out:
                    continue
                site = row.get(COL_WEBSITE)
                out[cik] = {
                    "cik": cik,
                    "firm": (row.get(COL_NAME) or row.get(COL_LEGAL) or "").strip(),
                    "crd": (row.get(COL_CRD) or "").strip() or None,
                    "website": (site or "").strip() or None,
                    "domain": _domain_from_website(site),
                    "phone": (row.get(COL_PHONE) or "").strip() or None,
                    "address": ", ".join(p for p in [
                        (row.get(COL_ADDR1) or "").strip(),
                        (row.get(COL_ADDR2) or "").strip()] if p) or None,
                    "city": (row.get(COL_CITY) or "").strip() or None,
                    "state": (row.get(COL_STATE) or "").strip() or None,
                    "postal": (row.get(COL_ZIP) or "").strip() or None,
                    "raum": _num(row.get(COL_RAUM)),
                    "accounts": _num(row.get(COL_ACCOUNTS)),
                }
    return out


def backfill(ciks=None, write_addresses=True, dry_run=False):
    """Join Form ADV to our contacts by CIK and fill the gaps.

    * DOMAIN onto every contact at that firm (contacts.domain) — the input Anymail Finder calls
      "most accurate" and which we currently have for zero contacts.
    * ADDRESS into core.fund_addresses via its own set_address() API (source="form_adv"), so the
      canonical address book stays the single owner.

    Returns a summary. dry_run reports what would change without writing."""
    from core import contacts as contacts_mod
    rows = contacts_mod.list_contacts()
    if ciks is None:
        ciks = [c["cik"] for c in rows if c.get("cik")]
    found = fetch_by_cik(ciks)

    domains, addresses, misses = 0, 0, []
    for c in rows:
        rec = found.get(contacts_mod.norm_cik(c.get("cik")))
        if not rec:
            if c.get("cik"):
                misses.append(c["firm"])
            continue
        if rec.get("domain") and not c.get("domain") and not dry_run:
            contacts_mod.upsert_contact(name=c["name"], firm=c["firm"], cik=c["cik"],
                                        domain=rec["domain"], source=c.get("source") or "manual")
        if rec.get("domain"):
            domains += 1

    if write_addresses and not dry_run:
        from core import fund_addresses
        seen = set()
        for rec in found.values():
            if rec.get("address") and rec["firm"] and rec["firm"] not in seen:
                metro = ", ".join(p for p in [rec.get("city"), rec.get("state")] if p) or None
                fund_addresses.set_address(rec["firm"], rec["address"], source="form_adv",
                                           hq_metro=metro, cik=rec["cik"])
                addresses += 1
                seen.add(rec["firm"])

    return {"contacts": len(rows), "adv_matched_ciks": len(found),
            "contacts_with_domain": domains, "addresses_written": addresses,
            "unmatched_firms": sorted(set(misses)), "dry_run": dry_run}
