"""FastAPI entry point: multi-city LST projects, city layers, and static web UI."""



from pathlib import Path



from fastapi import FastAPI, File, HTTPException, Request, UploadFile

from fastapi.responses import FileResponse, JSONResponse

from fastapi.staticfiles import StaticFiles



from backend.city_compare import compare_demo_cities

from backend.city_layers import (

    decode_preview_token,

    get_demo_portfolio,

    load_city_layers,

    load_vector_geojson,

)

from backend.dashboard_chat import answer_about_dashboard

from backend.presets import DEMO_CITY_LST, PRESET_CITIES

from backend.project import (

    compare_project,

    create_project,

    get_city_geojson,

    get_city_gpkg_path,

    get_project,

    register_city,

    run_city_lst_upload,

    run_city_model_upload,

)

from backend.rate_limit import chat_max_question_length, chat_rate_limiter

from backend.schemas import (

    CityLayersRequest,

    CityLayersResponse,

    FollowupRequest,

    FollowupResponse,

    ModelsListResponse,

    ModelInfoSchema,

    ProjectCityRequest,

    ProjectCreateRequest,

)

from backend.tract_query import query_tract_gpkg, query_tract_layer

from backend.uploads import save_upload_files

from models.registry import list_models_public



PROJECT_ROOT = Path(__file__).resolve().parent.parent

WEB_DIR = PROJECT_ROOT / "web"

DATA_DIR = PROJECT_ROOT / "data"



DATA_DIR.mkdir(parents=True, exist_ok=True)

CITY_LAYERS_CACHE = DATA_DIR / "city_layers_cache"

CITY_LAYERS_CACHE.mkdir(parents=True, exist_ok=True)

PROJECTS_DIR = DATA_DIR / "projects"

PROJECTS_DIR.mkdir(parents=True, exist_ok=True)



app = FastAPI(title="Geospatial Dashboard API")

_chat_limiter = chat_rate_limiter()





def _client_ip(request: Request) -> str:

    forwarded = request.headers.get("X-Forwarded-For", "").split(",")[0].strip()

    if forwarded:

        return forwarded

    if request.client:

        return request.client.host

    return "unknown"





def _city_png_preview(token: str) -> FileResponse:

    try:

        path = decode_preview_token(token, CITY_LAYERS_CACHE)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not path.exists():

        raise HTTPException(status_code=404, detail="Preview not found.")

    return FileResponse(path, media_type="image/png")





@app.get("/api/models", response_model=ModelsListResponse)

async def list_analysis_models() -> ModelsListResponse:

    return ModelsListResponse(

        models=[ModelInfoSchema(**item) for item in list_models_public()]

    )





@app.post("/api/projects")

async def create_lst_project(body: ProjectCreateRequest) -> JSONResponse:

    try:

        manifest = create_project(

            body.name,

            projects_dir=PROJECTS_DIR,

            model_id=body.model_id,

        )

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(content=manifest)





@app.get("/api/projects/presets")

async def project_presets() -> JSONResponse:

    return JSONResponse(content={"cities": PRESET_CITIES, "demo_lst": DEMO_CITY_LST})





@app.get("/api/projects/{project_id}")

async def get_lst_project(project_id: str) -> JSONResponse:

    try:

        return JSONResponse(content=get_project(project_id, projects_dir=PROJECTS_DIR))

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc





@app.post("/api/projects/{project_id}/cities")

async def add_project_city(project_id: str, body: ProjectCityRequest) -> JSONResponse:

    try:

        return JSONResponse(

            content=register_city(

                project_id,

                body.address,

                projects_dir=PROJECTS_DIR,

                city_layers_cache=CITY_LAYERS_CACHE,

            )

        )

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc





@app.post("/api/projects/{project_id}/cities/{city_key}/run")

async def upload_project_city_run(

    project_id: str,

    city_key: str,

    model: str = "lst",

    files: list[UploadFile] = File(...),

) -> JSONResponse:

    city_dir = PROJECTS_DIR / project_id / "cities" / city_key / "uploads"

    try:

        saved = await save_upload_files(files, city_dir)

        result = run_city_model_upload(

            project_id,

            city_key,

            saved,

            model_id=model,

            projects_dir=PROJECTS_DIR,

            city_layers_cache=CITY_LAYERS_CACHE,

        )

        return JSONResponse(content=result)

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc)) from exc





@app.post("/api/projects/{project_id}/cities/{city_key}/lst")

async def upload_project_city_lst(

    project_id: str,

    city_key: str,

    files: list[UploadFile] = File(...),

) -> JSONResponse:

    city_dir = PROJECTS_DIR / project_id / "cities" / city_key / "uploads"

    try:

        saved = await save_upload_files(files, city_dir)

        result = run_city_lst_upload(

            project_id,

            city_key,

            saved,

            projects_dir=PROJECTS_DIR,

            city_layers_cache=CITY_LAYERS_CACHE,

        )

        return JSONResponse(content=result)

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc)) from exc





@app.get("/api/projects/{project_id}/cities/{city_key}/geojson")

async def project_city_geojson(project_id: str, city_key: str) -> JSONResponse:

    try:

        return JSONResponse(content=get_city_geojson(project_id, city_key, projects_dir=PROJECTS_DIR))

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc





@app.get("/api/projects/{project_id}/cities/{city_key}/gpkg")

async def project_city_gpkg(project_id: str, city_key: str) -> FileResponse:

    try:

        path = get_city_gpkg_path(project_id, city_key, projects_dir=PROJECTS_DIR)

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return FileResponse(path, filename=path.name, media_type="application/geopackage+sqlite3")





@app.post("/api/city-layers", response_model=CityLayersResponse)

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





@app.get("/api/city-layers/demo-portfolio")

async def city_layers_demo_portfolio(warm: bool = False) -> JSONResponse:

    """Cached city-layers payloads for all 11 demo cities. Pass warm=true to prefetch missing."""

    try:

        return JSONResponse(content=get_demo_portfolio(cache_dir=CITY_LAYERS_CACHE, warm=warm))

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc)) from exc





@app.get("/api/city-layers/map/{token}/preview")

async def city_map_preview(token: str) -> FileResponse:

    return _city_png_preview(token)





@app.get("/api/city-layers/worldpop/{token}/preview")

async def city_worldpop_preview(token: str) -> FileResponse:

    return _city_png_preview(token)





@app.get("/api/city-layers/vector/{token}/geojson")

async def city_vector_geojson(token: str) -> JSONResponse:

    try:

        geojson = load_vector_geojson(token, CITY_LAYERS_CACHE)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except FileNotFoundError as exc:

        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return JSONResponse(content=geojson)





@app.get("/api/city-layers/vector/{token}/download")

async def city_vector_download(token: str) -> FileResponse:

    try:

        path = decode_preview_token(token, CITY_LAYERS_CACHE)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if path.suffix.lower() != ".gpkg" or not path.exists():

        raise HTTPException(status_code=404, detail="GeoPackage not found.")

    return FileResponse(path, filename=path.name, media_type="application/geopackage+sqlite3")





@app.post("/api/followup", response_model=FollowupResponse)

async def followup(body: FollowupRequest, request: Request) -> FollowupResponse:

    question = body.question.strip()

    if not question:

        raise HTTPException(status_code=400, detail="Question is required.")



    max_len = chat_max_question_length()

    if len(question) > max_len:

        raise HTTPException(

            status_code=400,

            detail=f"Question is too long (max {max_len} characters).",

        )



    allowed, retry_after = _chat_limiter.check(_client_ip(request))

    if not allowed:

        return JSONResponse(

            status_code=429,

            content={

                "detail": (

                    f"Too many chat requests. Try again in {retry_after} seconds."

                ),

            },

            headers={"Retry-After": str(retry_after)},

        )



    try:

        context = body.context.model_dump()

        project_id = body.context.project_id

        token = body.context.tract_layer_token



        if project_id:

            try:

                context["city_comparison"] = compare_project(

                    project_id.strip(), question, projects_dir=PROJECTS_DIR

                )

            except FileNotFoundError:

                pass

        elif body.context.demo_cities:

            context["city_comparison"] = compare_demo_cities(

                question, body.context.demo_cities

            )



        if token:

            try:

                if project_id and ":" in token:

                    _, city_key = token.split(":", 1)

                    gpkg = get_city_gpkg_path(project_id, city_key, projects_dir=PROJECTS_DIR)

                    context["tract_query"] = query_tract_gpkg(gpkg, question)

                else:

                    context["tract_query"] = query_tract_layer(

                        token.strip(), question, CITY_LAYERS_CACHE

                    )

            except (ValueError, FileNotFoundError):

                pass

        answer = answer_about_dashboard(question, context)

    except ValueError as exc:

        raise HTTPException(status_code=400, detail=str(exc)) from exc

    except Exception as exc:

        raise HTTPException(status_code=500, detail=str(exc)) from exc



    return FollowupResponse(answer=answer)





app.mount("/", StaticFiles(directory=str(WEB_DIR), html=True), name="web")


