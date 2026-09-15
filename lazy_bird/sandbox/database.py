from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from .models import SandboxModel


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = Path(
    os.getenv("SANDBOX_DB_PATH", str(BASE_DIR / "documents.db"))
).expanduser()
DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DATABASE_PATH}",
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _sqlite_pragmas(connection: object, _record: object) -> None:
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.close()


def init_db() -> None:
    SandboxModel.metadata.create_all(engine)


def get_session():
    with Session(engine) as session:
        yield session
