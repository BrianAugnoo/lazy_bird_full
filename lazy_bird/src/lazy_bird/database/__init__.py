from __future__ import annotations
import importlib, json, pkgutil
from dataclasses import dataclass
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType
from typing import Any
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import SQLModel, Session
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.config import Config
from alembic import command
from lazy_bird.database.contracts import SQLDatabaseAdapter, VectorDatabaseAdapter

DATABASE_DIR = Path(__file__).resolve().parent
CONFIG_FILE = DATABASE_DIR / "config.json"

@dataclass(frozen=True)
class DatabaseStatus:
    ready: bool
    error: str | None = None
    revision: str | None = None

class DatabaseEntry(BaseModel):
    enabled: bool = True
    settings: dict[str, Any] = Field(default_factory=dict)

class DatabaseConfig(BaseModel):
    sql_databases: dict[str, DatabaseEntry] = Field(default_factory=dict)
    vector_databases: dict[str, DatabaseEntry] = Field(default_factory=dict)
    selected_sql_database: str = "sqlite"
    selected_vector_database: str = "lancedb"
    model_config = ConfigDict(extra="forbid")

SQL_ADAPTER_ATTRIBUTES = ("name", "messages", "initialize", "disconnect")
VECTOR_ADAPTER_ATTRIBUTES = SQL_ADAPTER_ATTRIBUTES + ("tables", "create", "delete", "count", "retrieve", "drop")


def _discover(package_name: str) -> dict[str, ModuleType]:
    package = importlib.import_module(package_name)
    modules = {}
    required = VECTOR_ADAPTER_ATTRIBUTES if package_name.endswith("vector_db") else SQL_ADAPTER_ATTRIBUTES
    for info in pkgutil.iter_modules(package.__path__):
        if not info.name.startswith("_"):
            module = importlib.import_module(f"{package_name}.{info.name}")
            missing = [attribute for attribute in required if not hasattr(module, attribute)]
            if missing:
                raise ImportError(f"Adapter '{module.__name__}' is missing: {', '.join(missing)}")
            modules[module.name] = module
    return modules

SQL_ADAPTERS: dict[str, SQLDatabaseAdapter] = _discover("lazy_bird.database.sql_db")
VECTOR_ADAPTERS: dict[str, VectorDatabaseAdapter] = _discover("lazy_bird.database.vector_db")

def initialize_database_config() -> DatabaseConfig:
    raw = json.loads(CONFIG_FILE.read_text(encoding="utf-8")) if CONFIG_FILE.exists() else {}
    config = DatabaseConfig.model_validate(raw or {})
    for name in SQL_ADAPTERS:
        config.sql_databases.setdefault(name, DatabaseEntry())
    for name in VECTOR_ADAPTERS:
        config.vector_databases.setdefault(name, DatabaseEntry())
    if config.selected_sql_database not in SQL_ADAPTERS:
        config.selected_sql_database = "sqlite"
    if config.selected_vector_database not in VECTOR_ADAPTERS:
        config.selected_vector_database = next(iter(VECTOR_ADAPTERS), "")
    CONFIG_FILE.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return config

def _settings(module, values):
    schema = getattr(module, "Settings", None)
    return schema.model_validate(values).model_dump(exclude_none=True) if schema else {}

config = initialize_database_config()
engine = SQL_ADAPTERS[config.selected_sql_database].initialize(**_settings(SQL_ADAPTERS[config.selected_sql_database], config.sql_databases[config.selected_sql_database].settings))
db_url = str(engine.url)
db_type = config.selected_sql_database
test_engine = SQL_ADAPTERS["sqlite"].initialize(url=f"sqlite:///{DATABASE_DIR / 'storage' / 'lazy_bird_test.db'}")
status = DatabaseStatus(ready=False, error="Database has not been initialized")

def alembic_config_for(url: str) -> Config:
    """Build the only supported Alembic configuration for a database URL."""
    alembic_config = Config(str(DATABASE_DIR.parent / "alembic.ini"))
    alembic_config.set_main_option("script_location", str(DATABASE_DIR.parent / "migration"))
    alembic_config.set_main_option("sqlalchemy.url", url)
    # Mark that the URL was provided programmatically so env.py does not
    # fall back to the static value in alembic.ini.
    alembic_config.attributes["url_from_code"] = True
    return alembic_config


_alembic_config = alembic_config_for

def selected_sql_adapter():
    """Return the module of the currently selected SQL database."""
    return SQL_ADAPTERS[config.selected_sql_database]

def selected_sql_url() -> str:
    """Return the connection URL of the selected SQL adapter.

    Adapters expose connection URLs, even when an implementation stores data
    in a local file. This keeps Alembic independent from SQLite details.
    """
    module = selected_sql_adapter()
    settings = _settings(module, config.sql_databases[module.name].settings)
    override = settings.get("url")
    if override:
        return str(override)
    default_url = getattr(module, "default_url", None)
    if default_url is not None:
        return str(default_url)
    return db_url

def _current_revision(target_engine) -> str | None:
    with target_engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()

def initialize_selected_sql_database() -> DatabaseStatus:
    global engine, db_url, db_type, status
    try:
        module = SQL_ADAPTERS[config.selected_sql_database]
        settings = _settings(module, config.sql_databases[module.name].settings)
        new_engine = module.initialize(**settings)
        new_url = str(new_engine.url)
        command.upgrade(alembic_config_for(new_url), "head")
        expected = ScriptDirectory.from_config(alembic_config_for(new_url)).get_current_head()
        current = _current_revision(new_engine)
        if current != expected:
            raise RuntimeError(f"Migration verification failed: expected {expected}, found {current}")
        if engine is not new_engine:
            engine.dispose()
        engine, db_url, db_type = new_engine, new_url, module.name
        status = DatabaseStatus(ready=True, revision=current)
    except Exception as exc:
        status = DatabaseStatus(ready=False, error=f"Database initialization failed: {exc}")
    return status

@contextmanager
def db():
    if not status.ready:
        raise RuntimeError(status.error or "Database is unavailable")
    with Session(engine) as session:
        yield session

@contextmanager
def test_db():
    SQLModel.metadata.create_all(test_engine)
    with Session(test_engine) as session:
        yield session

def vector_adapter():
    return VECTOR_ADAPTERS[config.selected_vector_database]

def initialize_selected_vector_database():
    module = vector_adapter()
    return module.initialize(**_settings(module, config.vector_databases[module.name].settings))

def switch_database(kind: str, name: str, settings: dict[str, Any]):
    global config, engine, db_url, db_type
    adapters = SQL_ADAPTERS if kind == "sql" else VECTOR_ADAPTERS
    if name not in adapters:
        raise ValueError(f"Unknown {kind} database: {name}")
    validated = _settings(adapters[name], settings)
    if kind == "sql":
        new_engine = adapters[name].initialize(**validated)
        alembic_config = alembic_config_for(str(new_engine.url))
        expected = ScriptDirectory.from_config(alembic_config).get_current_head()
        current = _current_revision(new_engine)
        if current != expected:
            new_engine.dispose()
            raise RuntimeError(f"Database migrations are not current: expected {expected}, found {current}")
        engine.dispose(); engine = new_engine
        db_url, db_type = str(engine.url), name
        config.selected_sql_database = name
        config.sql_databases[name] = DatabaseEntry(settings=validated)
    else:
        adapters[name].initialize(**validated)
        config.selected_vector_database = name
        config.vector_databases[name] = DatabaseEntry(settings=validated)
    CONFIG_FILE.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return {"selected": name, "messages": adapters[name].messages}

def adapter_catalog():
    def describe(items):
        return {name: {"settings_schema": module.Settings.model_json_schema() if hasattr(module, "Settings") else None, "messages": module.messages} for name, module in items.items()}
    return {"sql": describe(SQL_ADAPTERS), "vector": describe(VECTOR_ADAPTERS)}

def disconnect_database(kind: str, name: str, drop: bool = False):
    global config, engine, db_url, db_type
    adapters = SQL_ADAPTERS if kind == "sql" else VECTOR_ADAPTERS
    if name not in adapters: raise ValueError(f"Unknown {kind} database: {name}")
    if kind == "sql":
        if name != config.selected_sql_database: raise ValueError("SQL database is not selected")
        adapters[name].disconnect(engine, drop)
        config.selected_sql_database = "sqlite"
        engine = SQL_ADAPTERS["sqlite"].initialize(**_settings(SQL_ADAPTERS["sqlite"], config.sql_databases["sqlite"].settings))
        db_url, db_type = str(engine.url), "sqlite"
    else:
        adapters[name].disconnect(drop)
        config.selected_vector_database = "lancedb"
        initialize_selected_vector_database()
    CONFIG_FILE.write_text(config.model_dump_json(indent=2), encoding="utf-8")
    return {"selected_sql": config.selected_sql_database, "selected_vector": config.selected_vector_database}

def vector_tables() -> list[str]:
    """Model names having a vector table in the selected vector database."""
    return vector_adapter().tables()

def vector_create(model_name: str, rows: list[dict]) -> int:
    """Insert or replace ``{"chunk_id", "vector"}`` rows in the table of a model."""
    return vector_adapter().create(model_name, rows)

def vector_delete(model_name: str, chunk_ids: list[int]) -> int:
    return vector_adapter().delete(model_name, chunk_ids)

def vector_delete_chunks(chunk_ids: list[int]) -> int:
    """Delete the vectors of these chunks from every model table."""
    if not chunk_ids:
        return 0
    return sum(vector_delete(model_name, chunk_ids) for model_name in vector_tables())

def vector_count(model_name: str, chunk_ids: list[int] | None = None) -> int:
    return vector_adapter().count(model_name, chunk_ids)

def vector_retrieve(model_name: str, top_k: int, vector: list[float], chunk_ids: list[int] | None = None) -> list[dict]:
    return vector_adapter().retrieve(model_name, top_k, vector, chunk_ids)

def vector_drop(model_name: str) -> None:
    vector_adapter().drop(model_name)
