from __future__ import annotations

import os

# Tracing every lazy_bird call makes the suite slow and floods the logs.
os.environ.setdefault("LAZY_BIRD_TRACE_ALL", "0")

from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from types import ModuleType
from typing import Iterator

from alembic import command
from alembic.config import Config
from fastapi import UploadFile
from fastapi.testclient import TestClient
from pydantic import BaseModel
from sqlmodel import Session
from starlette.datastructures import Headers
import pytest

import lazy_bird.crud.file as file_crud
import lazy_bird.database as database_module
from lazy_bird.database.vector_db import lancedb as lancedb_adapter
from lazy_bird.database.sql_db.sqlite import initialize
import lazy_bird.main as main_module
import lazy_bird.storages as storage_module
import lazy_bird.tools.hf_auth as hf_auth_module


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIR = REPO_ROOT / "src" / "lazy_bird" / "migration"
ALEMBIC_INI = REPO_ROOT / "src" / "lazy_bird" / "alembic.ini"

@dataclass(frozen=True)
class MigratedDatabase:
    url: str
    path: Path
    engine: object


def alembic_config(db_url: str) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(MIGRATION_DIR))
    config.set_main_option("sqlalchemy.url", db_url)
    config.attributes["url_from_code"] = True
    return config


def make_upload_file(
    filename: str | None = "document.txt",
    content: bytes = b"lazy bird",
    content_type: str = "text/plain",
) -> UploadFile:
    return UploadFile(
        file=BytesIO(content),
        filename=filename,
        size=len(content),
        headers=Headers({"content-type": content_type}),
    )


@pytest.fixture(scope="session")
def migrated_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One database migrated to head per test session; tests get a copy of it."""
    import lazy_bird.database as database

    path = tmp_path_factory.mktemp("template") / "template.db"
    url = f"sqlite:///{path}"
    previous = database.db_url
    database.db_url = url
    try:
        command.upgrade(alembic_config(url), "head")
    finally:
        database.db_url = previous
    return path


@pytest.fixture
def migrated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, migrated_template: Path) -> Iterator[MigratedDatabase]:
    """A temporary SQLite database migrated to head and used by ``database.db()``."""
    import shutil

    db_path = tmp_path / "lazy_bird_test.db"
    db_url = f"sqlite:///{db_path}"
    shutil.copyfile(migrated_template, db_path)

    # env.py imports this value when Alembic starts.
    monkeypatch.setattr(database_module, "db_url", db_url)
    monkeypatch.setitem(database_module.config.sql_databases["sqlite"].settings, "url", db_url)
    monkeypatch.setitem(database_module.config.vector_databases["lancedb"].settings, "path", str(tmp_path / "lance"))
    monkeypatch.setattr(lancedb_adapter, "_connection", None)
    monkeypatch.setattr(database_module, "_vector_initialized", None)
    engine = initialize(url=f"sqlite:///{db_path}")
    monkeypatch.setattr(database_module, "engine", engine)
    monkeypatch.setattr(database_module, "status", database_module.DatabaseStatus(ready=True, revision="head"))

    yield MigratedDatabase(url=db_url, path=db_path, engine=engine)

    engine.dispose()


@pytest.fixture
def db_session_factory(migrated_database: MigratedDatabase):
    @contextmanager
    def session_factory() -> Iterator[Session]:
        with Session(migrated_database.engine) as session:
            yield session

    return session_factory


@pytest.fixture
def crud_database(db_session_factory, monkeypatch: pytest.MonkeyPatch):
    """Migrated database used by every CRUD module; uploads are not auto-embedded."""
    monkeypatch.setattr(file_crud, "auto_embedding_enabled", lambda: False)
    return db_session_factory


@pytest.fixture
def storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "storage"
    monkeypatch.setattr(storage_module, "storage_dir", root)
    return root


@pytest.fixture
def model_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """An empty Hugging Face cache; ``add(repo_id, files)`` creates a snapshot in it."""
    from lazy_bird.tools import hf_cache

    root = tmp_path / "hf-cache"
    root.mkdir()
    monkeypatch.setattr(hf_cache, "HF_HUB_CACHE", str(root))

    def add(repo_id: str, files: dict[str, bytes], revision: str = "rev1") -> Path:
        folder = hf_cache.repo_folder(repo_id, root)
        snapshot = folder / "snapshots" / revision
        snapshot.mkdir(parents=True, exist_ok=True)
        for relative, content in files.items():
            (snapshot / relative).parent.mkdir(parents=True, exist_ok=True)
            (snapshot / relative).write_bytes(content)
        (folder / "refs").mkdir(exist_ok=True)
        (folder / "refs" / "main").write_text(revision)
        return snapshot

    add.root = root
    return add


@pytest.fixture
def upload_file_factory():
    return make_upload_file


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def client(
    crud_database,
    storage_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[TestClient]:
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: None)
    monkeypatch.setattr(hf_auth_module, "authenticate_hf", lambda: None)
    monkeypatch.setattr(main_module, "sync_cached_models", lambda: 0)
    monkeypatch.setattr(main_module, "start_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "stop_scheduler", lambda: None)
    monkeypatch.setattr(main_module, "apply_preferences", lambda: 0)

    with TestClient(main_module.app, raise_server_exceptions=False) as test_client:
        yield test_client


class FakeEmbeddingSettings(BaseModel):
    dimension: int = 4


def _fake_embed(texts, settings, model):
    """Deterministic vectors: letter frequencies folded on ``dimension`` axes."""
    vectors = []
    for text in texts:
        vector = [0.0] * settings.dimension
        for character in text.lower():
            if character.isalpha():
                vector[ord(character) % settings.dimension] += 1.0
        vectors.append(vector)
    return vectors


@pytest.fixture
def fake_embedding(crud_database, monkeypatch):
    """Register a fake embedding engine and make one of its presets the default."""
    from lazy_bird.embedding import engine_family

    module = ModuleType("fake_embedding_engine")
    module.name = "fake-embedding"
    module.EngineSettings = FakeEmbeddingSettings
    module.embed = _fake_embed
    module.vector_space = lambda settings: f"fake/space-{settings.dimension}"
    monkeypatch.setattr(engine_family, "_loaded", dict(engine_family._loaded))
    engine = engine_family.register(module)
    return engine_family.create_preset("fake", engine.id, {}, default=True)


@pytest.fixture
def running_scheduler(migrated_database, monkeypatch):
    """A started scheduler with generous resources, stopped after the test."""
    import lazy_bird.tasks as tasks_module
    from lazy_bird.tasks.resources import ResourcePool
    from lazy_bird.tasks.scheduler import Scheduler

    tasks_module.discover_tasks()
    scheduler = Scheduler(ResourcePool({"cpu": 8, "vram_mb": 1e6, "ram_mb": 1e6}), workers=2, poll_interval=0.02)
    monkeypatch.setattr(tasks_module, "_scheduler", scheduler)
    scheduler.start()
    yield scheduler
    scheduler.stop(timeout=5)


def wait_until(predicate, timeout: float = 10.0, message: str = "condition not reached"):
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError(message)


def process_inline(file_id: int) -> None:
    """Chunk and embed a file with the default preset, synchronously."""
    from lazy_bird.crud.file_processing import embedding_preset_for
    from lazy_bird.embedding import engine_family, vector_space
    from lazy_bird.tasks.default.files import chunk_file, embed_file

    chunk_file.run(file_id=file_id)
    target = vector_space(engine_family.resolve())
    embed_file.run(file_id=file_id, target=target, preset_id=embedding_preset_for(target))


@pytest.fixture(autouse=True)
def isolated_hf_cache(tmp_path_factory, monkeypatch):
    """No test may touch the real Hugging Face cache (``model_cache`` gives a filled one)."""
    from lazy_bird.tools import hf_cache

    monkeypatch.setattr(hf_cache, "HF_HUB_CACHE", str(tmp_path_factory.mktemp("hf-cache-isolated")))


@pytest.fixture(autouse=True)
def isolated_scheduler():
    """Every test starts without the process-wide scheduler and leaves none behind."""
    import lazy_bird.tasks as tasks_module

    tasks_module._scheduler = None
    yield
    if tasks_module._scheduler is not None and tasks_module._scheduler.started:
        tasks_module._scheduler.stop(timeout=2)
    tasks_module._scheduler = None


class FakeInferenceSettings(BaseModel):
    label: str = "fake"


def _fake_chat(messages, tools, settings, model, emit):
    """Replay the next scripted step: a ChatResult (its content is streamed) or an exception."""
    from lazy_bird.inference.types import ChatResult

    module = _fake_chat.module
    module.calls.append({"messages": list(messages), "tools": list(tools)})
    step = module.script.pop(0) if module.script else ChatResult(content="(no script)")
    if callable(step) and not isinstance(step, ChatResult):
        step = step(messages, emit)
    if isinstance(step, BaseException):
        raise step
    streamed = []
    for piece in step.content.split(" ") if step.content else []:
        if emit.stopped:
            return ChatResult(content=" ".join(streamed), stopped=True, model="fake-model")
        text = piece if not streamed else f" {piece}"
        streamed.append(piece)
        emit.token(text)
    if step.reasoning:
        emit.reasoning(step.reasoning)
    step.model = step.model or "fake-model"
    return step


@pytest.fixture
def fake_inference(crud_database, monkeypatch):
    """A scriptable inference engine registered as the default inference preset.

    Set ``fake_inference.script`` to a list of ``ChatResult``s, exceptions or
    ``callable(messages, emit)``; ``fake_inference.calls`` records each request.
    """
    from lazy_bird.inference import engine_family

    module = ModuleType("fake_inference_engine")
    module.name = "fake-llm"
    module.EngineSettings = FakeInferenceSettings
    module.chat = _fake_chat
    module.script = []
    module.calls = []
    _fake_chat.module = module
    monkeypatch.setattr(engine_family, "_loaded", dict(engine_family._loaded))
    engine = engine_family.register(module)
    module.preset = engine_family.create_preset("fake", engine.id, {}, default=True)
    module.engine = engine
    return module
