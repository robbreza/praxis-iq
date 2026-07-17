"""
core/geo.py — offline travel-leg estimates for the NDR itinerary.

The goal is the thing a bank's roadshow-logistics desk does by hand: put the
day's meetings in order and know, at a glance, how far apart the stops are and
whether the schedule is even feasible given travel time.

This is deliberately OFFLINE and HONEST about its resolution:

* We do NOT have a street-level geocoder or a live routing API wired in, so we
  never claim exact driving miles between two street addresses. What we CAN do
  accurately with zero dependencies is resolve each stop to a CITY (from the
  meeting address, or the institution's metro, or the trip city) and compute
  the great-circle ("straight-line") distance between city centers.
* For two stops in the SAME city we report a nominal intra-city allowance
  rather than a fake precise number.
* Distances are labelled "straight-line" everywhere so nobody mistakes them for
  odometer miles. Drive-time is an estimate at an effective urban speed and is
  only offered for short, same-metro legs; longer legs are flagged as
  inter-city (book a flight/train), which is the honest read.

Wiring a real Distance Matrix API (Google/Mapbox) later would slot in behind
`leg()` without changing any caller — see `leg()`'s return contract.
"""

from math import asin, cos, radians, sin, sqrt

# City center coordinates (lat, lon). Covers every metro the platform tracks
# plus the specific filer cities that show up in USIO's 13F holder base and the
# common financial hubs an NDR would route through. Keys are UPPERCASE "CITY,ST"
# (US) or "CITY" (international).
_CITY_COORDS = {
    "NEW YORK,NY": (40.7128, -74.0060), "BROOKLYN,NY": (40.6782, -73.9442),
    "GREENWICH,CT": (41.0262, -73.6282), "STAMFORD,CT": (41.0534, -73.5387),
    "JERSEY CITY,NJ": (40.7178, -74.0431), "SHORT HILLS,NJ": (40.7490, -74.3260),
    "BOSTON,MA": (42.3601, -71.0589), "CAMBRIDGE,MA": (42.3736, -71.1097),
    "WELLESLEY,MA": (42.2968, -71.2924),
    "CHICAGO,IL": (41.8781, -87.6298), "OAK BROOK,IL": (41.8850, -87.9290),
    "MILWAUKEE,WI": (43.0389, -87.9065),
    "MINNEAPOLIS,MN": (44.9778, -93.2650), "WAYZATA,MN": (44.9741, -93.5066),
    "SAN FRANCISCO,CA": (37.7749, -122.4194), "SAN MATEO,CA": (37.5630, -122.3255),
    "PALO ALTO,CA": (37.4419, -122.1430), "FOLSOM,CA": (38.6779, -121.1761),
    "LOS ANGELES,CA": (34.0522, -118.2437), "PASADENA,CA": (34.1478, -118.1445),
    "SOUTH PASADENA,CA": (34.1161, -118.1503), "IRVINE,CA": (33.6846, -117.8265),
    "NEWPORT BEACH,CA": (33.6189, -117.9298),
    "PHILADELPHIA,PA": (39.9526, -75.1652), "MALVERN,PA": (40.0362, -75.5138),
    "BALA CYNWYD,PA": (40.0043, -75.2338), "RADNOR,PA": (40.0465, -75.3599),
    "BALTIMORE,MD": (39.2904, -76.6122), "WASHINGTON,DC": (38.9072, -77.0369),
    "DALLAS,TX": (32.7767, -96.7970), "FORT WORTH,TX": (32.7555, -97.3308),
    "AUSTIN,TX": (30.2672, -97.7431), "HOUSTON,TX": (29.7604, -95.3698),
    "DENVER,CO": (39.7392, -104.9903), "BOULDER,CO": (40.0150, -105.2705),
    "MIAMI,FL": (25.7617, -80.1918), "TAMPA,FL": (27.9506, -82.4572),
    "PALM BEACH,FL": (26.7056, -80.0364), "NAPLES,FL": (26.1420, -81.7948),
    "ATLANTA,GA": (33.7490, -84.3880),
    "SCOTTSDALE,AZ": (33.4942, -111.9261), "PHOENIX,AZ": (33.4484, -112.0740),
    "SEATTLE,WA": (47.6062, -122.3321),
    # International hubs (no state suffix)
    "LONDON": (51.5074, -0.1278), "ZURICH": (47.3769, 8.5417),
    "TOKYO": (35.6762, 139.6503), "HONG KONG": (22.3193, 114.1694),
}

# Metro-region labels (as used on the institution records) → a representative
# city key, so a stop with no street address still resolves via its metro.
_METRO_TO_CITY = {
    "New York Metro": "NEW YORK,NY", "Boston / New England": "BOSTON,MA",
    "Chicago / Midwest": "CHICAGO,IL", "Los Angeles / SoCal": "LOS ANGELES,CA",
    "San Francisco / Bay Area": "SAN FRANCISCO,CA",
    "Philadelphia / Baltimore": "PHILADELPHIA,PA",
    "Texas (Dallas / Austin)": "DALLAS,TX", "Florida (Miami / Tampa)": "MIAMI,FL",
    "Denver / Mountain West": "DENVER,CO", "International": "LONDON",
}

_EFFECTIVE_MPH = 24.0     # urban door-to-door average incl. parking/traffic
_INTERCITY_MILES = 75.0   # above this, treat as a flight/rail leg, not a drive
_INTRACITY_MILES = 3.0    # nominal allowance for two stops in the same city
_INTRACITY_MIN = 20       # nominal local-transit minutes for a same-city hop


def _norm(s):
    return " ".join(str(s or "").upper().split())


def resolve_coords(text):
    """Best-effort city resolution from a free-text address, a metro-region
    label, or a bare city. Returns (lat, lon) or None. Never geocodes to a
    street — this is city-center resolution only."""
    if not text:
        return None
    # Metro-region label match first (exact), then its city.
    for label, key in _METRO_TO_CITY.items():
        if _norm(label) == _norm(text):
            return _CITY_COORDS[key]
    up = _norm(text)
    # "…, City, ST …" or "City, ST" — scan for a "CITY,ST" that we know.
    import re
    for m in re.finditer(r"([A-Z][A-Z .'-]+),\s*([A-Z]{2})\b", up):
        key = f"{m.group(1).strip()},{m.group(2)}"
        if key in _CITY_COORDS:
            return _CITY_COORDS[key]
    # Substring scan: any known city name appears in the text.
    for key, coord in _CITY_COORDS.items():
        city = key.split(",")[0]
        if city in up:
            return coord
    return None


def haversine_miles(a, b):
    """Great-circle distance in statute miles between two (lat, lon) points."""
    lat1, lon1, lat2, lon2 = map(radians, (a[0], a[1], b[0], b[1]))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * asin(sqrt(h)) * 3958.7613


def leg(from_text, to_text):
    """Estimate the travel leg between two stops.

    Returns a dict, or None when either endpoint can't be resolved to a city:
      { miles: float,            # straight-line miles (0 for same-city)
        drive_min: int | None,   # est. local drive minutes; None for inter-city
        basis: 'intracity' | 'drive' | 'intercity',
        label: str }             # a ready-to-print, honestly-qualified summary
    """
    a, b = resolve_coords(from_text), resolve_coords(to_text)
    if not a or not b:
        return None
    if a == b:
        return {"miles": _INTRACITY_MILES, "drive_min": _INTRACITY_MIN,
                "basis": "intracity",
                "label": f"same city — allow ~{_INTRACITY_MIN} min local transit"}
    miles = haversine_miles(a, b)
    if miles > _INTERCITY_MILES:
        return {"miles": miles, "drive_min": None, "basis": "intercity",
                "label": f"~{miles:,.0f} mi straight-line — inter-city leg (book flight/rail)"}
    drive_min = int(round(miles / _EFFECTIVE_MPH * 60))
    return {"miles": miles, "drive_min": drive_min, "basis": "drive",
            "label": f"~{miles:.1f} mi straight-line · ~{drive_min} min drive"}
