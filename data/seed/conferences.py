"""
data/seed/conferences.py — seed data for the IR Conference & Events Calendar.

This is real product data, not throwaway demo content: the Calendar page
(and the "On Your Calendar" card on Today) reads this the very first time a
client's calendar CSV doesn't exist yet, then the client's own edits take
over from the CSV going forward. Confirmed: this feature ships in the
commercial product, so it's organized the same multi-tenant way as
config/client_config.py — one seed list per client_id, keyed in
SEED_CONFERENCES — rather than a single hardcoded global list.

Onboarding client #2: add a "client_id": [...] entry to SEED_CONFERENCES
below (can be an empty list [] if they have no seed events yet). Nothing
else needs to change — get_seed_conferences() and the Calendar page both
already key off the active client automatically.
"""

SEED_CONFERENCES = {
    "usio": [
        {
            "Event":        "Q2 2026 Earnings Call",
            "Type":         "Earnings",
            "Date":         "2026-08-12",
            "Location":     "Virtual / Conference Bridge",
            "Organizer":    "USIO Internal",
            "Status":       "Confirmed",
            "Deadline":     "2026-08-11",
            "Notes":        "4:30 PM ET · Chorus Call dial-in confirmed · Webcast at usio.com/events/",
            "Source":       "Press Release",
            "Attending":    "Management + IR",
            "Priority":     "High",
        },
        {
            "Event":        "H.C. Wainwright Annual Global Investment Conference",
            "Type":         "Investor Conference",
            "Date":         "2026-09-08",
            "Location":     "New York, NY",
            "Organizer":    "H.C. Wainwright & Co.",
            "Status":       "Invited — pending confirmation",
            "Deadline":     "2026-07-31",
            "Notes":        "Scott Buck typically presents covered companies · 1x1 meetings available · Strong attendance from micro-cap tech funds",
            "Source":       "Analyst relationship",
            "Attending":    "CFO + IR",
            "Priority":     "High",
        },
        {
            "Event":        "Ladenburg Thalmann Technology Expo",
            "Type":         "Investor Conference",
            "Date":         "2026-10-14",
            "Location":     "New York, NY",
            "Organizer":    "Ladenburg Thalmann",
            "Status":       "Invited — pending confirmation",
            "Deadline":     "2026-08-30",
            "Notes":        "Jon Hickman hosts covered companies · Good for buy-side 1x1s with RPAY/PRTH holders",
            "Source":       "Analyst relationship",
            "Attending":    "CFO + IR",
            "Priority":     "High",
        },
        {
            "Event":        "Money20/20 USA",
            "Type":         "Industry Conference",
            "Date":         "2026-10-25",
            "Location":     "Las Vegas, NV",
            "Organizer":    "Money20/20",
            "Status":       "Evaluating",
            "Deadline":     "2026-09-01",
            "Notes":        "Largest fintech conference — good for PayFac and ACH visibility · Press/media exposure · Not primarily investor-focused",
            "Source":       "Industry",
            "Attending":    "TBD",
            "Priority":     "Medium",
        },
        {
            "Event":        "Maxim Group Virtual Investor Conference",
            "Type":         "Investor Conference",
            "Date":         "2026-11-05",
            "Location":     "Virtual",
            "Organizer":    "Maxim Group",
            "Status":       "Not yet contacted",
            "Deadline":     "2026-09-15",
            "Notes":        "Michael Diana covers USIO — good opportunity to re-engage after expected PT upgrade",
            "Source":       "Analyst relationship",
            "Attending":    "TBD",
            "Priority":     "Medium",
        },
        {
            "Event":        "Q3 2026 Earnings Call",
            "Type":         "Earnings",
            "Date":         "2026-11-12",
            "Location":     "Virtual / Conference Bridge",
            "Organizer":    "USIO Internal",
            "Status":       "Scheduled",
            "Deadline":     "2026-11-11",
            "Notes":        "Estimated date — confirm 4-6 weeks prior · First full quarter post-analyst upgrade cycle",
            "Source":       "Earnings schedule",
            "Attending":    "Management + IR",
            "Priority":     "High",
        },
    ],
    # Add client #2's seed conference list here, same shape as "usio" above.
}


def get_seed_conferences(client_id):
    """Seed conference/event list for the given client_id. Empty list if
    that client has no seed data configured yet (rather than an error) —
    an empty Calendar page is a valid starting state for a brand-new client."""
    return SEED_CONFERENCES.get(client_id, [])
