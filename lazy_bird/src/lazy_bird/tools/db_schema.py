"""Build a Mermaid diagram from the schema produced by Alembic migrations."""

from __future__ import annotations

import tempfile
from pathlib import Path
from functools import lru_cache

from alembic import command
from sqlalchemy import Engine, create_engine, inspect

from lazy_bird.database import alembic_config_for


def _build_database() -> tuple[Engine, tempfile.TemporaryDirectory[str]]:
    temporary = tempfile.TemporaryDirectory(prefix="lazy-bird-schema-")
    database_url = f"sqlite:///{Path(temporary.name) / 'schema.sqlite3'}"
    # Reuse the app's alembic config so the URL is marked as coming from
    # code and env.py does not redirect migrations to another database.
    config = alembic_config_for(database_url)
    command.upgrade(config, "head")
    return create_engine(database_url), temporary


def _mermaid_schema(engine: Engine) -> str:
    inspector = inspect(engine)
    tables = [name for name in inspector.get_table_names() if name != "alembic_version"]
    lines = ["erDiagram"]
    for table in tables:
        lines.append(f"    {table} {{")
        primary_keys = set(inspector.get_pk_constraint(table).get("constrained_columns") or [])
        foreign_keys = {column for key in inspector.get_foreign_keys(table) for column in key.get("constrained_columns") or []}
        for column in inspector.get_columns(table):
            markers = []
            if column["name"] in primary_keys:
                markers.append("PK")
            if column["name"] in foreign_keys:
                markers.append("FK")
            marker = f" {','.join(markers)}" if markers else ""
            nullable = "NULLABLE" if column["nullable"] else "NOT NULL"
            lines.append(f'        {str(column["type"])} {column["name"]}{marker} "{nullable}"')
        lines.append("    }")
    for table in tables:
        for key in inspector.get_foreign_keys(table):
            referred = key.get("referred_table")
            local = (key.get("constrained_columns") or ["id"])[0]
            remote = (key.get("referred_columns") or ["id"])[0]
            if referred in tables:
                lines.append(f'    {referred} ||--o{{ {table} : "{remote} -> {local}"')
    return "\n".join(lines)


@lru_cache(maxsize=1)
def get_schema_diagram() -> str:
    """Return the current migration head as Mermaid ER diagram source."""
    engine, temporary = _build_database()
    try:
        return _mermaid_schema(engine)
    finally:
        engine.dispose()
        temporary.cleanup()
