"""Census Data API — ACS 5-year estimates at census tract level."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

# ACS 5-year (2022 vintage — widely available).
ACS_YEAR = "2022"
ACS_DATASET = "acs/acs5"

# Median income, total pop, race/ethnicity (B03002).
ACS_VARIABLES = [
    "NAME",
    "B19013_001E",  # median household income
    "B01003_001E",  # total population
    "B03002_001E",  # race total
    "B03002_003E",  # white alone not Hispanic
    "B03002_004E",  # Black alone
    "B03002_006E",  # Asian alone
    "B03002_012E",  # Hispanic or Latino
]


def _census_api_key() -> str | None:
    key = os.environ.get("CENSUS_API_KEY", "").strip()
    return key or None


def fetch_tract_acs(state_fips: str, county_fips: str, *, timeout: int = 60) -> dict[str, dict]:
    """Return ACS attributes keyed by 11-digit tract GEOID."""
    state_fips = str(state_fips).zfill(2)
    county_fips = str(county_fips).zfill(3)

    params: dict[str, str] = {
        "get": ",".join(ACS_VARIABLES),
        "for": "tract:*",
        "in": f"state:{state_fips} county:{county_fips}",
    }
    api_key = _census_api_key()
    if api_key:
        params["key"] = api_key

    url = f"https://api.census.gov/data/{ACS_YEAR}/{ACS_DATASET}?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(url)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        try:
            rows = json.loads(raw)
        except json.JSONDecodeError as exc:
            if "Missing Key" in raw or "key" in raw.lower():
                raise ValueError(
                    "Census API requires CENSUS_API_KEY. "
                    "Get a free key at https://api.census.gov/data/key_signup.html"
                ) from exc
            raise ValueError("Census API returned invalid JSON.") from exc
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 403 and not api_key:
            raise ValueError(
                "Census API requires CENSUS_API_KEY for tract queries. "
                "Get a free key at https://api.census.gov/data/key_signup.html"
            ) from exc
        raise ValueError(f"Census API error ({exc.code}): {body[:200]}") from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Census API unavailable: {exc}") from exc

    if not rows or len(rows) < 2:
        raise ValueError("Census API returned no tract data.")

    headers = rows[0]
    index = {name: i for i, name in enumerate(headers)}

    def as_int(value: str | None) -> int | None:
        if value is None or value in ("", "-", "null", "-666666666"):
            return None
        try:
            return int(value)
        except ValueError:
            return None

    tract_data: dict[str, dict] = {}
    for row in rows[1:]:
        state = str(row[index["state"]]).zfill(2)
        county = str(row[index["county"]]).zfill(3)
        tract = str(row[index["tract"]]).zfill(6)
        geoid = f"{state}{county}{tract}"

        population = as_int(row[index["B01003_001E"]])
        income = as_int(row[index["B19013_001E"]])
        hispanic = as_int(row[index["B03002_012E"]])
        black = as_int(row[index["B03002_004E"]])
        white = as_int(row[index["B03002_003E"]])
        asian = as_int(row[index["B03002_006E"]])

        hispanic_pct = round(100 * hispanic / population, 1) if population and hispanic is not None else None
        black_pct = round(100 * black / population, 1) if population and black is not None else None

        tract_data[geoid] = {
            "acs_name": row[index["NAME"]],
            "population": population,
            "median_income_usd": income,
            "hispanic_count": hispanic,
            "black_count": black,
            "white_count": white,
            "asian_count": asian,
            "hispanic_pct": hispanic_pct,
            "black_pct": black_pct,
            "population_density_per_km2": None,  # filled after merge with tract area
        }

    return tract_data


def merge_acs_into_geojson(geojson: dict, acs_by_geoid: dict[str, dict]) -> dict:
    """Attach ACS attributes to tract GeoJSON features."""
    for feature in geojson.get("features") or []:
        props = feature.setdefault("properties", {})
        geoid = str(props.get("GEOID") or "").zfill(11)
        acs = acs_by_geoid.get(geoid, {})
        props.update(acs)

        aland = props.get("ALAND")
        population = acs.get("population")
        if aland and population and int(aland) > 0:
            km2 = int(aland) / 1_000_000
            props["population_density_per_km2"] = round(population / km2, 1) if km2 else None

    return geojson
