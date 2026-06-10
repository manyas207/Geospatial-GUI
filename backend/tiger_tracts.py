"""Census tract boundaries — TIGER shapefile download (cached) with TIGERweb fallback."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

TIGER_TRACT_ZIP = "https://www2.census.gov/geo/tiger/TIGER2023/TRACT/tl_2023_{state_fips}_tract.zip"
TIGERWEB_LAYERS = (7, 10, 4, 0)


def _fetch_tigerweb_geojson(state_fips: str, county_fips: str, *, timeout: int = 60) -> dict | None:
    """Best-effort TIGERweb query; returns None when the service errors."""
    state_fips = str(state_fips).zfill(2)
    county_fips = str(county_fips).zfill(3)

    for layer in TIGERWEB_LAYERS:
        params = urllib.parse.urlencode(
            {
                "where": f"STATE='{state_fips}' AND COUNTY='{county_fips}'",
                "outFields": "GEOID,TRACT,NAME,STATE,COUNTY,ALAND,AWATER,BASENAME",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultRecordCount": "2000",
            }
        )
        url = (
            f"https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/Tracts_Blocks/MapServer/{layer}/query?"
            + params
        )
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            continue

        if payload.get("type") == "FeatureCollection" and payload.get("features"):
            return payload

    return None


def _download_state_tract_zip(state_fips: str, cache_dir: Path, *, timeout: int = 180) -> Path:
    state_fips = str(state_fips).zfill(2)
    cache_dir.mkdir(parents=True, exist_ok=True)
    zip_path = cache_dir / f"tl_2023_{state_fips}_tract.zip"

    if zip_path.exists() and zip_path.stat().st_size > 100_000:
        return zip_path

    url = TIGER_TRACT_ZIP.format(state_fips=state_fips)
    request = urllib.request.Request(url, headers={"User-Agent": "Geospatial-GUI/1.0"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read()
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Could not download Census tract shapefile: {exc}") from exc

    zip_path.write_bytes(data)
    if not zipfile.is_zipfile(zip_path):
        zip_path.unlink(missing_ok=True)
        raise ValueError("Downloaded tract file is not a valid zip archive.")

    return zip_path


def _tracts_from_shapefile(state_fips: str, county_fips: str, cache_dir: Path) -> dict:
    import geopandas as gpd

    state_fips = str(state_fips).zfill(2)
    county_fips = str(county_fips).zfill(3)
    zip_path = _download_state_tract_zip(state_fips, cache_dir)

    gdf = gpd.read_file(f"zip://{zip_path}!tl_2023_{state_fips}_tract.shp")
    county_col = "COUNTYFP" if "COUNTYFP" in gdf.columns else "COUNTY"
    gdf[county_col] = gdf[county_col].astype(str).str.zfill(3)
    county_gdf = gdf[gdf[county_col] == county_fips].copy()

    if county_gdf.empty:
        raise ValueError(f"No census tracts found for state {state_fips} county {county_fips}.")

    if county_gdf.crs is None:
        county_gdf = county_gdf.set_crs("EPSG:4269")
    county_gdf = county_gdf.to_crs("EPSG:4326")

    rename = {}
    if "GEOID20" in county_gdf.columns and "GEOID" not in county_gdf.columns:
        rename["GEOID20"] = "GEOID"
    if "NAME20" in county_gdf.columns and "NAME" not in county_gdf.columns:
        rename["NAME20"] = "NAME"
    if "ALAND20" in county_gdf.columns and "ALAND" not in county_gdf.columns:
        rename["ALAND20"] = "ALAND"
    if "AWATER20" in county_gdf.columns and "AWATER" not in county_gdf.columns:
        rename["AWATER20"] = "AWATER"
    if rename:
        county_gdf = county_gdf.rename(columns=rename)

    return json.loads(county_gdf.to_json())


def fetch_tract_geojson(
    state_fips: str,
    county_fips: str,
    *,
    cache_dir: Path,
    timeout: int = 60,
) -> dict:
    """Return census tract polygons for a county as a GeoJSON FeatureCollection."""
    web = _fetch_tigerweb_geojson(state_fips, county_fips, timeout=timeout)
    if web is not None:
        return web

    return _tracts_from_shapefile(state_fips, county_fips, cache_dir)
