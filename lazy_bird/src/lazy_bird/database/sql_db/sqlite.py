from pathlib import Path
from pydantic import BaseModel, ConfigDict
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import create_engine

name = "sqlite"
messages = {"initialize": "SQLite requires no configuration.", "disconnect": "Dropping SQLite removes its local file."}
default_url = f"sqlite:///{Path(__file__).resolve().parents[1] / 'storage' / 'lazy_bird.db'}"

class Settings(BaseModel):
    url: str | None = None
    model_config = ConfigDict(extra="forbid")

def initialize(**kwargs) -> Engine:
    settings = Settings.model_validate(kwargs)
    url = settings.url or default_url
    if not url.startswith("sqlite:///"):
        raise ValueError("SQLite adapter requires a sqlite URL")
    file_path = Path(url.removeprefix("sqlite:///"))
    file_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def set_pragmas(connection, _):
        cursor = connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()
    return engine

def disconnect(engine: Engine, drop: bool = False) -> None:
    database_path = Path(engine.url.database)
    engine.dispose()
    if drop and database_path.exists():
        database_path.unlink()
