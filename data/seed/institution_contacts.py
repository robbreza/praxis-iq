"""
data/seed/institution_contacts.py — known institutional investor contacts.

Unlike conferences.py, this is NOT client-specific: these are real-world
funds/institutions (Vanguard, BlackRock, Dimensional, etc.) that could hold
shares in, or be a targeting prospect for, ANY of Praxis Point's clients —
the same institution shows up whether the client is USIO or client #2. So
this is shared reference data used across all tenants, not one record per
client_id like client_config.py or conferences.py.

Judgment call flagged for the user: if it turns out each client actually
needs their OWN separate institution-contact list (e.g. because client #2's
IR team has different existing relationships that shouldn't show up for
USIO), this should be restructured to be keyed by client_id like
conferences.py. Kept shared for now since the original data itself
(fund names/contacts) had nothing USIO-specific in it.

Used by: institution cards, the NDR planner, and the bulk email-draft
generator (per the original comment in app.py) — kept as one source so
those three don't each maintain their own copy.
"""

INSTITUTION_CONTACTS = {
    "Perkins Investment Management": {"name": "Michael Perkins",   "email": "ir@perkinsfunds.com",     "title": "Portfolio Manager",     "phone": "+1 312-555-0142"},
    "Vanguard Group Inc":            {"name": "Index Relations",   "email": "indexir@vanguard.com",    "title": "Index Relations",       "phone": "+1 610-555-0100"},
    "Rutabaga Capital Management":   {"name": "Paul Kovacs",       "email": "pk@rutabagacap.com",      "title": "Senior Analyst",        "phone": "+1 617-555-0188"},
    "Ancora Advisors":               {"name": "Frederick DiSanto", "email": "fd@ancora.net",           "title": "CEO & Portfolio Manager","phone": "+1 216-555-0176"},
    "Wasatch Advisors":              {"name": "Research Team",     "email": "research@wasatchadv.com", "title": "Small-Cap Research",    "phone": "+1 801-555-0123"},
    "BlackRock Small Cap Growth":    {"name": "IR Team",           "email": "ir@blackrock.com",        "title": "Portfolio Relations",   "phone": "+1 212-555-0155"},
    "Heartland Advisors":            {"name": "Will Nasgovitz",    "email": "wn@heartlandadv.com",     "title": "Portfolio Manager",     "phone": "+1 414-555-0169"},
    "Dimensional Fund Advisors":     {"name": "DFA Relations",     "email": "ir@dfaus.com",            "title": "Portfolio Relations",   "phone": "+1 512-555-0134"},
    # Expanded targeting universe (Jul 14, 2026) — demo contacts for the
    # funds added to data/seed/buyside_institutions.py. Keys match the "Fund"
    # names there exactly so the NDR finder and meeting rows resolve them.
    # New York Metro
    "Royce Investment Partners":       {"name": "Small-Cap Desk",     "email": "ir@royceinvest.com",         "title": "Small-Cap PM",          "phone": "+1 212-555-0210"},
    "Gabelli Funds (GAMCO)":           {"name": "Research Desk",      "email": "ir@gabelli.com",             "title": "Research Analyst",      "phone": "+1 914-555-0222"},
    "Cramer Rosenthal McGlynn":        {"name": "Jay Abramson",       "email": "ja@crmllc.com",              "title": "Portfolio Manager",     "phone": "+1 212-555-0255"},
    "Bandera Partners":                {"name": "Jeff Gramm",         "email": "jg@banderapartners.com",     "title": "Managing Partner",      "phone": "+1 212-555-0312"},
    "Greenhaven Associates":           {"name": "Portfolio Desk",     "email": "ir@greenhavenassoc.com",     "title": "Portfolio Manager",     "phone": "+1 914-555-0301"},
    "First Eagle Investment Management": {"name": "Small-Cap Team",   "email": "ir@firsteagle.com",          "title": "Portfolio Manager",     "phone": "+1 212-555-0244"},
    "Tocqueville Asset Management":     {"name": "Research Team",      "email": "ir@tocqueville.com",         "title": "Research Analyst",      "phone": "+1 212-555-0266"},
    "Lord Abbett":                     {"name": "Value Team",         "email": "ir@lordabbett.com",          "title": "Portfolio Manager",     "phone": "+1 201-555-0288"},
    "Neuberger Berman":                {"name": "IR Desk",            "email": "ir@nb.com",                  "title": "Portfolio Specialist",  "phone": "+1 212-555-0233"},
    "Van Eck Associates":              {"name": "IR Team",            "email": "ir@vaneck.com",              "title": "Sector Analyst",        "phone": "+1 212-555-0277"},
    "AllianceBernstein":               {"name": "Small-Cap Desk",     "email": "smallcap@alliancebernstein.com", "title": "Research Analyst",  "phone": "+1 212-555-0299"},
    # Boston / New England
    "Wellington Management":           {"name": "SCV Team",           "email": "ir@wellington.com",          "title": "Investment Director",   "phone": "+1 617-555-0334"},
    "Adage Capital Management":        {"name": "Research Desk",      "email": "ir@adagecapital.com",        "title": "Research Analyst",      "phone": "+1 617-555-0389"},
    "Fidelity Management & Research":  {"name": "Small-Cap Growth Desk", "email": "ir@fmr.com",              "title": "Portfolio Manager",     "phone": "+1 617-555-0323"},
    "Loomis Sayles":                   {"name": "Growth Team",        "email": "ir@loomissayles.com",        "title": "Research Analyst",      "phone": "+1 617-555-0367"},
    "MFS Investment Management":       {"name": "Value Desk",         "email": "ir@mfs.com",                 "title": "Research Analyst",      "phone": "+1 617-555-0345"},
    "Putnam Investments":              {"name": "IR Team",            "email": "ir@putnam.com",              "title": "Portfolio Manager",     "phone": "+1 617-555-0356"},
    "Eaton Vance (Morgan Stanley IM)": {"name": "SMID Value Desk",    "email": "ir@eatonvance.com",          "title": "Portfolio Manager",     "phone": "+1 617-555-0378"},
    # West Coast (SF / LA)
    "Kayne Anderson Rudnick":          {"name": "Quality Growth Team", "email": "ir@kar.com",                "title": "Portfolio Manager",     "phone": "+1 310-555-0434"},
    "Osterweis Capital Management":    {"name": "Portfolio Desk",     "email": "ir@osterweis.com",           "title": "Portfolio Manager",     "phone": "+1 415-555-0456"},
    "Franklin Templeton":              {"name": "Small-Cap Value",    "email": "ir@franklintempleton.com",   "title": "Portfolio Manager",     "phone": "+1 650-555-0412"},
    "Dodge & Cox":                     {"name": "Equity Research",    "email": "ir@dodgeandcox.com",         "title": "Research Analyst",      "phone": "+1 415-555-0401"},
    "PRIMECAP Management":             {"name": "Research Team",      "email": "ir@primecap.com",            "title": "Research Analyst",      "phone": "+1 626-555-0445"},
    "Capital Group (American Funds)":  {"name": "IR Desk",            "email": "ir@capgroup.com",            "title": "Investment Analyst",    "phone": "+1 213-555-0423"},
    # Chicago / Midwest
    "Ariel Investments":               {"name": "Portfolio Desk",     "email": "ir@arielinvestments.com",    "title": "Portfolio Manager",     "phone": "+1 312-555-0467"},
    "Driehaus Capital Management":     {"name": "Micro-Cap Team",     "email": "ir@driehaus.com",            "title": "Portfolio Manager",     "phone": "+1 312-555-0490"},
    "William Blair":                   {"name": "Small-Cap Growth",   "email": "ir@williamblair.com",        "title": "Portfolio Manager",     "phone": "+1 312-555-0489"},
    "Harris Associates (Oakmark)":     {"name": "Oakmark Desk",       "email": "ir@harrisassoc.com",         "title": "Research Analyst",      "phone": "+1 312-555-0478"},
    # San Francisco / Bay Area
    "Parnassus Investments":           {"name": "ESG Research Desk",  "email": "ir@parnassus.com",           "title": "Research Analyst",      "phone": "+1 415-555-0502"},
    "Allspring Global Investments":    {"name": "Small-Cap Growth",   "email": "ir@allspringglobal.com",     "title": "Portfolio Manager",     "phone": "+1 415-555-0513"},
    "ValueAct Capital":                {"name": "Investment Team",    "email": "ir@valueact.com",            "title": "Partner",               "phone": "+1 415-555-0524"},
    "Victory Capital (RS Investments)": {"name": "Growth Desk",       "email": "ir@vcm.com",                 "title": "Portfolio Manager",     "phone": "+1 415-555-0535"},
    # Los Angeles / SoCal
    "First Pacific Advisors (FPA)":    {"name": "Value Team",         "email": "ir@fpa.com",                 "title": "Portfolio Manager",     "phone": "+1 310-555-0546"},
    "Hotchkis & Wiley":                {"name": "Small-Cap Value",    "email": "ir@hwcm.com",                "title": "Portfolio Manager",     "phone": "+1 310-555-0557"},
    "Aristotle Capital Management":    {"name": "Quality Team",       "email": "ir@aristotlecap.com",        "title": "Research Analyst",      "phone": "+1 310-555-0568"},
    "TCW Group":                       {"name": "Growth Desk",        "email": "ir@tcw.com",                 "title": "Research Analyst",      "phone": "+1 213-555-0579"},
    "Payden & Rygel":                  {"name": "Equity Desk",        "email": "ir@payden.com",              "title": "Research Analyst",      "phone": "+1 213-555-0580"},
    # Denver / Mountain West
    "ArrowMark Partners":              {"name": "Small-Cap Growth",   "email": "ir@arrowmarkpartners.com",   "title": "Portfolio Manager",     "phone": "+1 303-555-0591"},
    "Cambiar Investors":               {"name": "Value Team",         "email": "ir@cambiar.com",             "title": "Portfolio Manager",     "phone": "+1 303-555-0602"},
    "Segall Bryant & Hamill":          {"name": "Small-Cap Desk",     "email": "ir@sbhic.com",               "title": "Research Analyst",      "phone": "+1 303-555-0613"},
    "Janus Henderson":                 {"name": "IR Desk",            "email": "ir@janushenderson.com",      "title": "Portfolio Manager",     "phone": "+1 303-555-0624"},
    "Marsico Capital Management":      {"name": "Growth Desk",        "email": "ir@marsico.com",             "title": "Research Analyst",      "phone": "+1 303-555-0635"},
    # Texas (Dallas / Austin)
    "Hodges Capital Management":       {"name": "Craig Hodges Team",  "email": "ir@hodgescapital.com",       "title": "Portfolio Manager",     "phone": "+1 214-555-0646"},
    "Barrow Hanley":                   {"name": "Value Team",         "email": "ir@barrowhanley.com",        "title": "Portfolio Manager",     "phone": "+1 214-555-0657"},
    "Westwood Holdings":               {"name": "SMID Value",         "email": "ir@westwoodgroup.com",       "title": "Portfolio Manager",     "phone": "+1 214-555-0668"},
    "Luther King Capital (LKCM)":      {"name": "Core Equity Desk",   "email": "ir@lkcm.com",                "title": "Research Analyst",      "phone": "+1 817-555-0679"},
    "Bares Capital Management":        {"name": "Brian Bares Team",   "email": "ir@barescapital.com",        "title": "Portfolio Manager",     "phone": "+1 512-555-0680"},
    "Q Investments":                   {"name": "Investment Desk",    "email": "ir@qinvest.com",             "title": "Research Analyst",      "phone": "+1 817-555-0691"},
    # Florida (Miami / Tampa)
    "Eagle Asset Management":          {"name": "Small-Cap Growth",   "email": "ir@eagleasset.com",          "title": "Portfolio Manager",     "phone": "+1 727-555-0702"},
    "Carillon Tower Advisers":         {"name": "Growth Desk",        "email": "ir@carillontower.com",       "title": "Research Analyst",      "phone": "+1 727-555-0713"},
    "GQG Partners":                    {"name": "IR Desk",            "email": "ir@gqg.com",                 "title": "Investment Analyst",    "phone": "+1 954-555-0724"},
    "Elliott Investment Management":   {"name": "Equity Team",        "email": "ir@elliottmgmt.com",         "title": "Research Analyst",      "phone": "+1 561-555-0735"},
    "Point72 Asset Management":        {"name": "IR Desk",            "email": "ir@point72.com",             "title": "Research Analyst",      "phone": "+1 305-555-0746"},
    "Balyasny Asset Management":       {"name": "Equity Desk",        "email": "ir@bamfunds.com",            "title": "Research Analyst",      "phone": "+1 305-555-0757"},
}


def get_institution_contacts():
    return INSTITUTION_CONTACTS
