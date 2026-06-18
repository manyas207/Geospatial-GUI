"""City layers and map preview routes."""

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from backend.api.deps import city_png_preview
from backend.config import CITY_LAYERS_CACHE
from backend.core.schemas import CityLayersRequest, CityLayersResponse
from backend.layers.orchestrator import (
    decode_preview_token,
    get_demo_portfolio,
    load_city_layers,
    load_vector_geojson,
)

router = APIRouter(tags=["city-layers"])


@router.post("/api/city-layers", response_model=CityLayersResponse)
async def city_layers(body: CityLayersRequest) -> CityLayersResponse:
    address = body.address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="Address is required.")

    try:
        result = load_city_layers(address, cache_dir=CITY_LAYERS_CACHE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ConnectionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return CityLayersResponse(**result)


@router.get("/api/city-layers/demo-portfolio")
async def city_layers_demo_portfolio(warm: bool = False) -> JSONResponse:
    """Cached city-layers payloads for all 11 demo cities. Pass warm=true to prefetch missing."""
    try:
        return JSONResponse(content=get_demo_portfolio(cache_dir=CITY_LAYERS_CACHE, warm=warm))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/api/city-layers/map/{token}/preview")
async def city_map_preview(token: str) -> FileResponse:
    return city_png_preview(token)


@router.get("/api/city-layers/worldpop/{token}/preview")
async def city_worldpop_preview(token: str) -> FileResponse:
    return city_png_preview(token)


@router.get("/api/city-layers/vector/{token}/geojson")
async def city_vector_geojson(token: str) -> JSONResponse:
    try:
        geojson = load_vector_geojson(token, CITY_LAYERS_CACHE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return JSONResponse(content=geojson)


@router.get("/api/city-layers/vector/{token}/download")
async def city_vector_download(token: str) -> FileResponse:
    try:
        path = decode_preview_token(token, CITY_LAYERS_CACHE)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if path.suffix.lower() != ".gpkg" or not path.exists():
        raise HTTPException(status_code=404, detail="GeoPackage not found.")
    return FileResponse(path, filename=path.name, media_type="application/geopackage+sqlite3")
