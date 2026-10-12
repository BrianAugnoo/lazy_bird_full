from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from functools import lru_cache

import os

from lazy_bird.logging_config import configure_logging

# Tracing every lazy_bird call logs each call and its result: off unless LAZY_BIRD_TRACE_ALL=1
# (for a debugging session; it can also be switched from the Logs page).
TRACE_ALL_LAZY_BIRD = os.getenv("LAZY_BIRD_TRACE_ALL", "0").lower() in {"1", "true", "yes", "on"}
configure_logging(trace_all=TRACE_ALL_LAZY_BIRD)

from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, RedirectResponse

from lazy_bird.api import router as api_router
from lazy_bird.api.error_handlers import install_error_handlers
from lazy_bird.errors import error_payload
from lazy_bird.tools.hf_auth import authenticate_hf
from lazy_bird.crud.llm_model import sync_cache as sync_cached_models
from lazy_bird.cross_encoder import initialize_cross_encoder_engines
from lazy_bird.embedding import initialize_embedding_engines
from lazy_bird.inference import initialize_inference_engines
from lazy_bird import database
from lazy_bird.preferences import apply_preferences
from lazy_bird.residency import residency
from lazy_bird.tasks import start_scheduler, stop_scheduler
from lazy_bird.tools.db_schema import get_schema_diagram
from lazy_bird.agents.tools import initialize_tools

from loguru import logger


def initialize_extensions() -> None:
    """Discover every extension point (failures are logged and listed in /extensions/failures)."""
    from lazy_bird.agents import agent_preset, instruction, session_preset, skill
    from lazy_bird.agents.hook import initialize_hooks
    from lazy_bird.tasks import discover_tasks

    initialize_embedding_engines()
    initialize_cross_encoder_engines()
    initialize_inference_engines()
    for ensure in (instruction.ensure_folders, skill.ensure_folders, agent_preset.registry.ensure_folders, session_preset.registry.ensure_folders):
        ensure()
    tools = initialize_tools()
    hooks = initialize_hooks()
    skill.skills()
    discover_tasks()
    logger.info("Extensions loaded: {} tools, {} hooks", len(tools.entries), len(hooks.entries))


@asynccontextmanager
async def lifespan(app: FastAPI):
    database_status = database.initialize_selected_sql_database()
    app.state.database_status = database_status
    app.state.startup_error = database_status.error
    if not database_status.ready:
        yield
        return
    scheduler_started = False
    try:
        authenticate_hf()
        sync_cached_models()
        initialize_extensions()
        database.initialize_selected_vector_database()
        apply_preferences()
        start_scheduler()
        scheduler_started = True
        app.state.startup_error = None
    except Exception as exc:
        logger.opt(exception=exc).error("Application initialization failed")
        app.state.startup_error = f"Application initialization failed: {exc}"
    try:
        yield
    finally:
        if scheduler_started:
            stop_scheduler()
        residency().shutdown()


app = FastAPI(lifespan=lifespan)
install_error_handlers(app)
app.include_router(api_router)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent / "templates")

@app.middleware("http")
async def require_database(request: Request, call_next):
    started = perf_counter()
    database_status = getattr(request.app.state, "database_status", database.status)
    startup_error = getattr(request.app.state, "startup_error", database_status.error)
    if request.url.path not in ("/", "/health") and startup_error:
        logger.warning("HTTP request rejected during startup: method={} path={}", request.method, request.url.path)
        return JSONResponse(status_code=503, content=error_payload("startup_failed", startup_error))
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

@lru_cache(maxsize=1)
def _version() -> str:
    from importlib.metadata import PackageNotFoundError, version

    try:
        return version("lazy-bird")
    except PackageNotFoundError:
        return "unknown"


@app.get("/")
@app.get("/health")
async def health():
    """Whether the server is ready; ``error`` explains a failed startup."""
    database_status = getattr(app.state, "database_status", database.status)
    startup_error = getattr(app.state, "startup_error", database_status.error)
    return {
        "ready": not startup_error,
        "version": _version(),
        "database_revision": database_status.revision,
        "error": {"code": "startup_failed", "message": startup_error, "details": {}} if startup_error else None,
    }


@app.get("/schemas", include_in_schema=False)
def schema_view(request: Request):
    """The data model as a diagram (pan by dragging, zoom with the wheel)."""
    return templates.TemplateResponse(request=request, name="schemas.html", context={"diagram": get_schema_diagram()})


@app.get("/shemas", include_in_schema=False)
async def old_schema_view():
    return RedirectResponse("/schemas", status_code=308)



