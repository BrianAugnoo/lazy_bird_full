from __future__ import annotations

import os

# Tracing every lazy_bird call makes the suite slow and floods the logs.
os.environ.setdefault("LAZY_BIRD_TRACE_ALL", "0")

from contextlib import contextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Iterator

from alembic import command
from alembic.config import Config
from fastapi import UploadFile
from fastapi.testclient import TestClient
from sqlmodel import Session
from starlette.datastructures import Headers
import pytest

import lazy_bird.crud.file as file_crud
import lazy_bird.crud.llm_model as llm_model_crud
import lazy_bird.database as database_module
from lazy_bird.database.vector_db import lancedb as lancedb_adapter
from lazy_bird.database.sql_db.sqlite import initialize
import lazy_bird.main as main_module
import lazy_bird.storages as storage_module
import lazy_bird.tools.hf_auth as hf_auth_module
import lazy_bird.tools.hf_cache_worker as hf_cache_worker_module


REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATION_DIR = REPO_ROOT / "src" / "lazy_bird" / "migration"
ALEMBIC_INI = REPO_ROOT / "src" / "lazy_bird" / "alembic.ini"

MODEL_INPUT = {
    "hf_path": "sentence-transformers/all-MiniLM-L6-v2",
}
MODEL_OUTPUT = {
    "id": 1,
    "name": "nreimers/MiniLM-L6-H384-uncased",
    "hf_path": MODEL_INPUT["hf_path"],
    "dimension": 512,
    "formats": ["safetensors", "ONNX"],
    "selected_format": "safetensors",
    "local_path": "/tmp/fake-model",
    "max_context_length": None,
    "selected_context": None,
}


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


@pytest.fixture
def migrated_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[MigratedDatabase]:
    """A temporary SQLite database migrated to head and used by ``database.db()``."""
    db_path = tmp_path / "lazy_bird_test.db"
    db_url = f"sqlite:///{db_path}"

    # env.py imports this value when Alembic starts.
    monkeypatch.setattr(database_module, "db_url", db_url)
    monkeypatch.setitem(database_module.config.sql_databases["sqlite"].settings, "url", db_url)
    monkeypatch.setitem(database_module.config.vector_databases["lancedb"].settings, "path", str(tmp_path / "lance"))
    monkeypatch.setattr(lancedb_adapter, "_connection", None)
    command.upgrade(alembic_config(db_url), "head")
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
    """Migrated database used by every CRUD module; background enqueueing is disabled."""
    monkeypatch.setattr(file_crud, "enqueue_file", lambda file_id: None)
    return db_session_factory


@pytest.fixture
def storage_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "storage"
    monkeypatch.setattr(storage_module, "storage_dir", root)
    return root


@pytest.fixture
def fake_model_services(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm_model_crud, "download_model", lambda hf_path: MODEL_OUTPUT["local_path"])
    monkeypatch.setattr(
        llm_model_crud,
        "extract",
        lambda local_path: {
            "name": MODEL_OUTPUT["name"],
            "dimension": MODEL_OUTPUT["dimension"],
            "formats": MODEL_OUTPUT["formats"],
        },
    )


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
    monkeypatch.setattr(hf_cache_worker_module, "sync_cached_models", lambda: 0)
    monkeypatch.setattr(main_module, "start_worker", lambda: None)
    monkeypatch.setattr(main_module, "stop_worker", lambda worker: None)

    with TestClient(main_module.app, raise_server_exceptions=False) as test_client:
        yield test_client
