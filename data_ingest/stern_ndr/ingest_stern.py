"""Ingest the STILL-LIVE accounts from a 2014/15 Sterne Agee software NDR itinerary (OCR'd from
E:\\HPSCANS\\stern.pdf; analyst R. Breza). Real firm + contact + direct phone per meeting. Contacts
are VINTAGE (2014 US leg / 2015 UK leg) — the firm is live but the PERSON may have moved, so tagged
validation_status='stale', low confidence, with a 'verify before outreach' provenance note. UK leg =
country UK. Firms updated to current names where merged/rebranded.

SKIPPED (dead / merged-away / unconfirmable, cross-checked vs the target-list verifications):
 PresPoint, QCM, Montibus, Archon, Wall Street Associates, GROW (unconfirmable/likely defunct);
 RS Investment Mgmt -> Victory Capital; Rainier -> Manning & Napier; Relational (wound down);
 Alliance Trust Investments -> Liontrust."""
from core.security import load_environment; load_environment()
from core import contacts as C, contact_classifier as cc

# (current_firm, city, country, note, [(name, phone|None)])
LIVE = [
 ("Falcon Point Capital", "San Francisco, CA", "US", None, [("Toby Chanudomchok", "+1 415-782-9600")]),
 ("Columbia Threadneedle Investments", "Menlo Park, CA", "US", "formerly Columbia Management", [("Israel Hernandez", "+1 650-833-4612")]),
 ("Columbia Threadneedle Investments", "Portland, OR", "US", "formerly Columbia Management", [("Brian Neigut", "+1 503-265-5791")]),
 ("PIMCO", "Newport Beach, CA", "US", None, [("Collin McBirney", "+1 949-720-7655"), ("Benjamin Strom", "+1 949-720-4509")]),
 ("Nicholas Investment Partners", "San Diego, CA", "US", None, [("Emmy Sobieski", "+1 858-381-8002")]),
 # ---- UK leg (Jan 2015) ----
 ("Janus Henderson Investors", "Edinburgh, UK", "UK", "formerly Henderson Global Investors", [("Graeme Clark", "+44 131 6565 952")]),
 ("Aviva Investors", "London, UK", "UK", None, [("Richard Saldanha", "+44 20 7809 8707")]),
 ("AXA Investment Managers", "London, UK", "UK", "formerly AXA Framlington", [("Steve Kelly", "+44 20 7330 6557"), ("Jeremy Gleeson", "+44 20 7330 6487")]),
 ("BlackRock (UK)", "London, UK", "UK", "contact William de Gale later founded BlueBox AM — verify", [("William de Gale", "+44 20 7743 4420")]),
 ("Polar Capital", "London, UK", "UK", None, [("Nick Evans", None)]),
 ("M&G Investments", "London, UK", "UK", None, [("Kasper Mikkelsen", "+44 20 7548 2236")]),
 ("USS Investment Management", "London, UK", "UK", "UK pension / asset-owner (Universities Superannuation Scheme)", [("Richard Mercaddo", None)]),
 ("Lansdowne Partners", "London, UK", "UK", None, [("Chris Watson", "+44 207 290 5500")]),
 ("Columbia Threadneedle Investments", "London, UK", "UK", "formerly Threadneedle Asset Management", [("Sachee Trivedi", "+44 207 464 5339")]),
 ("Ninety One", "London, UK", "UK", "formerly Investec Asset Management", [("Scott Winship", "+44 20 7597 2981")]),
]
BASE = "Sterne Agee software NDR (US leg May 2014 / UK leg Jan 2015), analyst R. Breza. Contact + direct phone from the itinerary; VINTAGE — firm live but person may have moved; verify before outreach."
added = 0
for firm, city, country, note, people in LIVE:
    for name, phone in people:
        cid = C.upsert_contact(name=name, firm=firm, phone=phone, source="stern_2014_ndr",
                               source_ref="Sterne Agee NDR itinerary")
        if not cid:
            continue
        prov = BASE + (f" NOTE: {note}." if note else "")
        C.update_classification(cid, firm_type=cc.firm_type_for(firm, None), city=city, country=country,
                                validation_status="stale", confidence=40, provenance=prov)
        added += 1
    print(f"{firm[:34]:34s} | {city[:16]:16s} {country} | {len(people)} contact(s)")
print(f"\nSTERN NDR: +{added} vintage contacts across {len(set(f for f,*_ in LIVE))} live firms")
