"""
seed_test_research_note.py — one-off script to drop a realistic test item
into the inbox queue so the new "Pending Inbox Items" card (CFA-lens
research-note review, Investor Targeting -> Meeting Hub -> Upcoming
Meetings) has something to show. Safe to run against the real database —
it only adds one row to inbox_queue.json via the same core.inbox_queue
API core/mail_gateway.py itself uses, nothing else is touched.

Run once: `python seed_test_research_note.py` from the project root
(or double-click seed_test_data.bat), then restart the app to see it.

Delete this file (and the .bat) once you're done testing — it's not part
of the app, just a demo aid.
"""

from core import inbox_queue

item_id = inbox_queue.enqueue_item(
    category="research_note",
    contact="Maria Gonzalez",
    firm="Maxim Group",
    subject="Research Note: Reiterating Buy, raising PT to $4.50 — USIO Inc (USIO)",
    extracted={
        "rating": "Buy",
        "price_target": 4.50,
        "prior_price_target": 4.00,
        "period": "FY 2026E",
        "thesis_summary": "Reiterating Buy on accelerating bookings momentum and margin "
                           "expansion; raising PT to reflect a steeper revenue growth "
                           "trajectory heading into FY2027.",
        "valuation_method": "EV/Revenue",
        "key_assumptions": "Applies a 2.5x EV/Revenue multiple to FY2027E revenue of "
                            "~$112M, a modest premium to peer median given improving "
                            "unit economics and expanding gross margin.",
        "variant_view": "variant/contrarian",
        "catalysts_risks": "Watch for continued deceleration in customer churn and any "
                            "commentary on gross margin trajectory on the next call; key "
                            "risk is customer concentration in the top 3 accounts.",
        "sentiment": "Bullish",
    },
    filename="Maxim_USIO_ResearchNote_2026-07-09.pdf",
    source="test_seed",
)

print(f"Seeded test research-note inbox item: {item_id}")
print("Restart the app and check Investor Targeting -> Meeting Hub -> Upcoming Meetings.")
