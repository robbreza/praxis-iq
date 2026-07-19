"""data/seed/institution_contacts.py — COMPATIBILITY SHIM (no longer a seed).

This module used to hold 62 FABRICATED institution contacts ("IR Desk" / "Equity Team" names,
555- phone numbers, generic ir@firm.com addresses). They were demo scaffolding that was never
replaced with the real extraction — and because they fed the mail gateway's contact_lookup,
inbound email routing was matching against addresses that do not exist. Deleted 2026-07-19.

The real person layer now comes from EDGAR 13F signature blocks (name / title / direct phone),
lives in core/contacts.py, and is backed by the unscoped `contacts` table. This module is kept
only so existing call sites (app.py, core/search_engine.py, investors_page.py) keep working
unchanged — it simply delegates.
"""
from core.contacts import institution_contacts_map


def get_institution_contacts():
    """`{firm_name: {name, email, title, phone}}`, from the REAL contacts store (memoised)."""
    return institution_contacts_map()
