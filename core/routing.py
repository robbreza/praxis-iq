"""
core/routing.py — real driving distance/time for the NDR itinerary via the
OpenRouteService (ORS) API.

This upgrades the offline great-circle estimate in `core/geo.py` to actual
routed driving miles and minutes. It slots in behind the same `leg(from, to)`
contract, so the itinerary builders don't care which one answered — they try
routing first and fall back to `geo.leg()` when there's no API key or the
network/geocoder can't resolve an address.

Design:
* The ORS key is read from Settings (`settings.json` → "routing_api_key") or,
  failing that, the ORS_API_KEY environment variable. No key → is_configured()
  is False and every caller transparently uses the offline estimate.
* Two cheap ORS endpoints, both on the free tier:
    - Geocoding (`/geocode/search`) turns a street address (or "City, ST") into
      [lon, lat]. Results are cached in db so we never re-geocode the same text.
    - Directions (`/v2/directions/driving-car`) returns a real driving route's
      distance (m) and duration (s) between two points. Leg results are cached
      too, keyed by the address pair.
* Everything is best-effort: any error, timeout, or unresolved address returns
  None so the caller falls back. Failures are NOT cached, so fixing the key or
  connectivity works on the next build without a restart.

Free-tier limits (ample for NDR planning): geocode 1,000/day, directions
2,000/day. Caching means a re-exported itinerary makes zero new calls.
"""

import os

import requests

from core import db
from core.geo import _METRO_TO_CITY, _INTERCITY_MILES

_BASE = "https://api.openrouteservice.org"
_TIMEOUT = 8
_GEOCACHE_KEY = "routing_geocode.json"
_LEGCACHE_KEY = "routing_legs.json"

# Metro-region label -> a geocodable "City, ST" string, so a stop that only has
# a metro (no street address yet) still routes from a real city center.
_METRO_TO_QUERY = {
    "New York Metro": "New York, NY", "Boston / New England": "Boston, MA",
    "Chicago / Midwest": "Chicago, IL", "Los Angeles / SoCal": "Los Angeles, CA",
    "San Francisco / Bay Area": "San Francisco, CA",
    "Philadelphia / Baltimore": "Philadelphia, PA",
    "Texas (Dallas / Austin)": "Dallas, TX", "Florida (Miami / Tampa)": "Miami, FL",
    "Denver / Mountain West": "Denver, CO", "International": "London, UK",
}

# Metro-region label -> a (lat, lon) BUSINESS-DISTRICT bias for geocoding. A
# generic city center isn't good enough: "New York,NY" resolves to City Hall
# (lower Manhattan), which sits about as close to Brooklyn's 5th Ave as to
# Manhattan's, so an ambiguous "745 5th Ave" still lands in the wrong borough.
# Pointing the bias at where NDR meetings actually cluster (Midtown, the Loop,
# FiDi) disambiguates reliably.
_METRO_FOCUS = {
    "New York Metro": (40.7549, -73.9840),        # Midtown
    "Boston / New England": (42.3559, -71.0568),  # Financial District
    "Chicago / Midwest": (41.8823, -87.6300),     # The Loop
    "Los Angeles / SoCal": (34.0522, -118.2437),  # Downtown LA
    "San Francisco / Bay Area": (37.7929, -122.3971),  # FiDi
    "Philadelphia / Baltimore": (39.9526, -75.1652),   # Center City
    "Texas (Dallas / Austin)": (32.7810, -96.7970),    # Downtown Dallas
    "Florida (Miami / Tampa)": (25.7690, -80.1918),    # Brickell / Downtown
    "Denver / Mountain West": (39.7440, -104.9900),    # Downtown Denver
    "International": (51.5140, -0.0900),               # City of London
}


def focus_for(city_label):
    """A (lat, lon) geocoding bias for a trip's city/metro. Prefers the
    business-district point; falls back to offline city-center resolution."""
    from core import geo
    # Normalise onto the canonical metro vocabulary first: a trip saved as "Boston"
    # instead of "Boston / New England" otherwise misses the Financial District bias
    # and silently falls through to a generic city-centre geocode.
    try:
        from core.ndr_calendar import canonical_metro
        city_label = canonical_metro(city_label)
    except Exception:
        pass
    t = _norm(city_label)
    for label, coord in _METRO_FOCUS.items():
        if _norm(label) == t:
            return coord
    return geo.resolve_coords(city_label)


def api_key():
    """The ORS key from Settings, then the environment. '' when unset."""
    try:
        key = (db.load_json("settings.json", {}) or {}).get("routing_api_key", "")
    except Exception:
        key = ""
    return (key or os.environ.get("ORS_API_KEY", "") or "").strip()


def is_configured():
    return bool(api_key())


def _norm(s):
    return " ".join(str(s or "").strip().split())


def _query_for(text):
    """Turn a stop's location string into something geocodable — expand a known
    metro-region label to its representative city, else use the text as-is."""
    t = _norm(text)
    for label, q in _METRO_TO_QUERY.items():
        if _norm(label) == t:
            return q
    return t


def geocode(text, focus=None):
    """[lon, lat] for an address/city string, or None. Cached in db.

    `focus` is an optional (lat, lon) city-center bias (e.g. the trip city) so an
    ambiguous street like "745 5th Ave, New York" resolves to Manhattan, not the
    5th Ave in Brooklyn. Without it, a bare street name can geocode to the wrong
    borough/city and inflate the leg by miles."""
    key = api_key()
    if not key or not text:
        return None
    q = _query_for(text)
    # Cache key includes the focus bias (rounded) so biased vs unbiased results
    # don't collide.
    ck = q if not focus else f"{q}@@{round(focus[0], 2)},{round(focus[1], 2)}"
    cache = db.load_json(_GEOCACHE_KEY, {})
    if ck in cache:
        return cache[ck]  # coord list; misses are never cached
    params = {"api_key": key, "text": q, "size": 1, "boundary.country": "US"}
    if focus:
        params["focus.point.lat"], params["focus.point.lon"] = focus[0], focus[1]
    else:
        params.pop("boundary.country")  # unknown focus → don't force US (intl filers)
    try:
        r = requests.get(f"{_BASE}/geocode/search", params=params, timeout=_TIMEOUT)
        r.raise_for_status()
        feats = (r.json() or {}).get("features") or []
        if not feats:
            return None
        lon, lat = feats[0]["geometry"]["coordinates"][:2]
        coord = [float(lon), float(lat)]
    except Exception:
        return None
    cache[ck] = coord
    db.save_json(_GEOCACHE_KEY, cache)
    return coord


def leg(from_text, to_text, focus=None):
    """Real driving leg between two stops. Same return contract as geo.leg():
      { miles, drive_min, basis:'routed', label } or None on any failure.

    `focus` is an optional (lat, lon) city bias passed through to geocoding so
    ambiguous street addresses resolve in the right city (see geocode())."""
    key = api_key()
    if not key or not from_text or not to_text:
        return None
    _fc = "" if not focus else f"@@{round(focus[0], 2)},{round(focus[1], 2)}"
    cache_id = f"{_norm(_query_for(from_text))}||{_norm(_query_for(to_text))}{_fc}"
    legcache = db.load_json(_LEGCACHE_KEY, {})
    if cache_id in legcache:
        return legcache[cache_id]

    a, b = geocode(from_text, focus), geocode(to_text, focus)
    if not a or not b:
        return None
    try:
        r = requests.get(
            f"{_BASE}/v2/directions/driving-car",
            params={"api_key": key,
                    "start": f"{a[0]},{a[1]}", "end": f"{b[0]},{b[1]}"},
            timeout=_TIMEOUT)
        r.raise_for_status()
        summ = ((r.json() or {}).get("features") or [{}])[0].get("properties", {}).get("summary", {})
        dist_m, dur_s = summ.get("distance"), summ.get("duration")
        if dist_m is None or dur_s is None:
            return None
        miles = dist_m / 1609.344
        drive_min = int(round(dur_s / 60))
    except Exception:
        return None

    if miles > _INTERCITY_MILES:
        label = (f"~{miles:,.0f} mi driving · ~{drive_min // 60}h {drive_min % 60:02d}m "
                 f"— long haul, consider flight/rail")
    else:
        label = f"~{miles:.1f} mi driving · ~{drive_min} min (routed)"
    result = {"miles": miles, "drive_min": drive_min, "basis": "routed", "label": label}
    legcache[cache_id] = result
    db.save_json(_LEGCACHE_KEY, legcache)
    return result


def test(sample_from="55 E 52nd St, New York, NY", sample_to="200 Vesey St, New York, NY"):
    """Used by the Settings 'Test' button. Returns (ok: bool, message: str)."""
    if not is_configured():
        return False, "No API key set."
    coord = geocode(sample_from)
    if not coord:
        return False, "Key set, but geocoding failed (check the key is valid/active)."
    lg = leg(sample_from, sample_to)
    if not lg:
        return False, "Geocoding worked but the routing call failed (check daily quota)."
    return True, f"Working — sample leg: {lg['label']}."
