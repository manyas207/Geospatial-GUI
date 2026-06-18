"""Census Geocoder API — free, no API key required."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

GEOCODER_GEOGRAPHIES_URL = "https://geocoding.geo.census.gov/geocoder/geographies/onelineaddress"
GEOCODER_LOCATIONS_URL = "https://geocoding.geo.census.gov/geocoder/locations/onelineaddress"
GEOCODER_COORDS_URL = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "Geospatial-GUI-1/1.0"

# Fallback centroids for common demo cities when one-line geocoding returns no match.
CITY_CENTROIDS: dict[str, tuple[float, float]] = {
    "phoenix, az": (33.4484, -112.0740),
    "houston, tx": (29.7604, -95.3698),
    "dallas, tx": (32.7767, -96.7970),
    "miami, fl": (25.7617, -80.1918),
    "los angeles, ca": (34.0522, -118.2437),
    "atlanta, ga": (33.7490, -84.3880),
    "memphis, tn": (35.1495, -90.0490),
    "chicago, il": (41.8781, -87.6298),
    "detroit, mi": (42.3314, -83.0458),
    "baltimore, md": (39.2904, -76.6122),
    "cleveland, oh": (41.4993, -81.6944),
}


def _fetch_json(url: str, *, timeout: int = 30) -> dict:
    request = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Census Geocoder unavailable: {exc}") from exc


def _geocode_via_nominatim(
    address: str, *, timeout: int = 30
) -> tuple[float, float, str]:
    """Resolve a US place name to coordinates via OpenStreetMap Nominatim."""
    params = urllib.parse.urlencode(
        {
            "q": address,
            "format": "json",
            "limit": 1,
            "countrycodes": "us",
        }
    )
    request = urllib.request.Request(
        f"{NOMINATIM_URL}?{params}",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            matches = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Nominatim geocoder unavailable: {exc}") from exc

    if not matches:
        raise ValueError("no_match")

    hit = matches[0]
    return float(hit["lat"]), float(hit["lon"]), hit.get("display_name") or address


def _geographies_from_coords(lat: float, lon: float, *, timeout: int = 30) -> dict:
    params = urllib.parse.urlencode(
        {
            "x": lon,
            "y": lat,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }
    )
    payload = _fetch_json(f"{GEOCODER_COORDS_URL}?{params}", timeout=timeout)
    geographies = (payload.get("result") or {}).get("geographies") or {}
    counties = geographies.get("Counties") or []
    if not counties:
        raise ValueError("No county found at coordinates.")
    return geographies, lat, lon


def geocode_address(address: str, *, timeout: int = 30) -> dict:
    """Geocode a one-line US address and return coordinates + FIPS geographies."""
    address = address.strip()
    if not address:
        raise ValueError("Address is required.")

    params = urllib.parse.urlencode(
        {
            "address": address,
            "benchmark": "Public_AR_Current",
            "vintage": "Current_Current",
            "format": "json",
        }
    )
    payload = _fetch_json(f"{GEOCODER_GEOGRAPHIES_URL}?{params}", timeout=timeout)
    matches = (payload.get("result") or {}).get("addressMatches") or []

    matched_address = address
    lat = lon = None

    if matches:
        match = matches[0]
        coords = match.get("coordinates") or {}
        geographies = match.get("geographies") or {}
        matched_address = match.get("matchedAddress") or address
        lat = float(coords.get("y", 0))
        lon = float(coords.get("x", 0))
    else:
        centroid = CITY_CENTROIDS.get(address.lower().strip())
        if centroid:
            lat, lon = centroid
            matched_address = f"{address} (city centroid)"
            geographies, lat, lon = _geographies_from_coords(lat, lon, timeout=timeout)
        else:
            loc_params = urllib.parse.urlencode(
                {
                    "address": address,
                    "benchmark": "Public_AR_Current",
                    "format": "json",
                }
            )
            loc_payload = _fetch_json(f"{GEOCODER_LOCATIONS_URL}?{loc_params}", timeout=timeout)
            loc_matches = (loc_payload.get("result") or {}).get("addressMatches") or []
            if loc_matches:
                coords = loc_matches[0].get("coordinates") or {}
                lat = float(coords.get("y", 0))
                lon = float(coords.get("x", 0))
                matched_address = loc_matches[0].get("matchedAddress") or address
                geographies, lat, lon = _geographies_from_coords(lat, lon, timeout=timeout)
            else:
                try:
                    lat, lon, matched_address = _geocode_via_nominatim(
                        address, timeout=timeout
                    )
                    geographies, lat, lon = _geographies_from_coords(
                        lat, lon, timeout=timeout
                    )
                except ValueError:
                    raise ValueError(
                        f"Could not geocode address: {address!r}. "
                        'Use a US city with state, e.g. "Round Rock, TX".'
                    ) from None

    if matches:
        geographies = match.get("geographies") or {}

    counties = geographies.get("Counties") or []
    if not counties:
        raise ValueError(f"No county found for address: {address!r}")

    county = counties[0]
    state_fips = str(county.get("STATE", "")).zfill(2)
    county_fips = str(county.get("COUNTY", "")).zfill(3)

    states = geographies.get("States") or []
    state_name = states[0].get("NAME", "") if states else ""

    return {
        "matched_address": matched_address,
        "latitude": lat,
        "longitude": lon,
        "state_fips": state_fips,
        "county_fips": county_fips,
        "county_name": county.get("NAME") or "",
        "state_name": state_name,
        "state_code": (states[0].get("STUSAB") if states else "") or "",
    }
