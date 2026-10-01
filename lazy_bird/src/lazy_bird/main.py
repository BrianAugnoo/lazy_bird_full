from contextlib import asynccontextmanager
import asyncio
from pathlib import Path
from time import perf_counter

from lazy_bird.logging_config import configure_logging

configure_logging()

from fastapi import FastAPI, File, Form, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse

from lazy_bird.api import router as api_router
from lazy_bird.crud import file as file_crud
from lazy_bird.tools.hf_auth import authenticate_hf
from lazy_bird.tools.hf_cache_worker import sync_cached_models
from lazy_bird.embedding import initialize_embedding_engines
from lazy_bird.inference import initialize_inference_engines
from lazy_bird import database
from lazy_bird.crud import vector_database
from lazy_bird.preferences import apply_preferences, auto_embedding_enabled
from lazy_bird.task_queue import start_worker, stop_worker
from lazy_bird.tools.db_schema import get_schema_diagram
from lazy_bird.agents.tools import initialize_tools

from loguru import logger


def tools_initialization():
    validation = initialize_tools()
    for error, success in zip(validation["failed"], validation["success"]):
        logger.info(
            "Tool loaded: {}.{}.{}",
            success["package"],
            success["module"],
            success["name"],
        )
        logger.warning(
            "Tool failed to load: {}.{}.{} - {}",
            error["package"],
            error["module"],
            error["name"],
            error["error"],
        )

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = None
    database_status = database.initialize_selected_sql_database()
    app.state.database_status = database_status
    app.state.startup_error = database_status.error
    if not database_status.ready:
        yield
        return
    try:
        authenticate_hf()
        sync_cached_models()
        initialize_embedding_engines()
        initialize_inference_engines()
        tools_initialization()
        database.initialize_selected_vector_database()
        vector_database.populate(list(database.VECTOR_ADAPTERS))
        apply_preferences()
        worker = start_worker()
        app.state.startup_error = None
    except Exception as exc:
        app.state.startup_error = f"Application initialization failed: {exc}"
    try:
        yield
    finally:
        stop_worker(worker)


app = FastAPI(lifespan=lifespan)
app.include_router(api_router)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

@app.middleware("http")
async def require_database(request: Request, call_next):
    started = perf_counter()
    database_status = getattr(request.app.state, "database_status", database.status)
    startup_error = getattr(request.app.state, "startup_error", database_status.error)
    if request.url.path != "/" and startup_error:
        logger.warning("HTTP request rejected during startup: method={} path={}", request.method, request.url.path)
        return JSONResponse(status_code=503, content={"success": False, "error": startup_error})
    try:
        response = await call_next(request)
        return response
    finally:
        logger.info(
            "HTTP request: method={} path={} status={} duration_ms={:.2f}",
            request.method,
            request.url.path,
            getattr(locals().get("response"), "status_code", "error"),
            (perf_counter() - started) * 1000,
        )

@app.get("/")
async def read_root():
    database_status = getattr(app.state, "database_status", database.status)
    startup_error = getattr(app.state, "startup_error", database_status.error)
    if startup_error:
        return {"success": False, "error": startup_error}
    return {"success": True, "message": "Welcome to Lazy Bird!", "database_revision": database_status.revision}


@app.get("/shemas", include_in_schema=False)
async def schema_view(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="shemas.html",
        context={"diagram": get_schema_diagram()},
    )


@app.get("/upload_file", include_in_schema=False)
async def upload_file_view(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="upload_file.html",
        context={"uploaded_files": None, "error": None},
    )


@app.post("/upload_file", include_in_schema=False)
async def upload_file_from_view(
    request: Request,
    directory: str = Form(...),
    files: list[UploadFile] = File(...),
):
    try:
        uploaded_files = await file_crud.creates(directory, files)
        return templates.TemplateResponse(
            request=request,
            name="upload_file.html",
            context={"uploaded_files": uploaded_files, "error": None},
        )
    except Exception as exc:
        return templates.TemplateResponse(
            request=request,
            name="upload_file.html",
            context={"uploaded_files": None, "error": str(exc)},
            status_code=400,
        )


@app.websocket("/ws/upload-progress")
async def upload_progress(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.send_json({"files": file_crud.get_processing_status()})
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


