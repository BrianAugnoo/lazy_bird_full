"""Explicit contracts implemented by database adapter modules.

SQL adapters (``database/sql_db/<name>.py``) and vector adapters
(``database/vector_db/<name>.py``) are discovered at import time. Every adapter
defines ``name`` and ``messages`` ({"initialize": str, "disconnect": str}, shown to
the user) and may define a pydantic ``Settings`` model for its configuration.

Vector adapters store one table per embedding model ("vector space"), named after
the model, with two columns: ``chunk_id`` (the ``chunk.id`` of the SQL database)
and ``vector``. Chunk content and metadata live in the SQL ``chunk`` table only.
"""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.engine import Engine

from lazy_bird.errors import NotFoundError


class VectorTableNotFoundError(NotFoundError):
    def __init__(self, model_name: str) -> None:
        super().__init__("Vector table", model_name, code="vector_table_not_found")


class SQLDatabaseAdapter(Protocol):
    name: str
    messages: dict[str, str]

    def initialize(self, **settings: Any) -> Engine:
        """Create a SQL engine from adapter-specific settings."""
        ...

    def disconnect(self, engine: Engine, drop: bool = False) -> None:
        """Close the engine and optionally remove its database."""
        ...


class VectorDatabaseAdapter(Protocol):
    name: str
    messages: dict[str, str]

    def initialize(self, **settings: Any) -> Any:
        """Connect to the vector database from adapter-specific settings."""
        ...

    def disconnect(self, drop: bool = False) -> None:
        """Close the connection and optionally remove stored vectors."""
        ...

    def tables(self) -> list[str]:
        """Return the model names that have a vector table."""
        ...

    def create(self, model_name: str, rows: list[dict[str, Any]]) -> int:
        """Insert or replace ``{"chunk_id": int, "vector": list[float]}`` rows.

        Creates the table on first use. Raises ``ValueError`` when ``rows`` is empty.
        Returns the number of rows written.
        """
        ...

    def delete(self, model_name: str, chunk_ids: list[int]) -> int:
        """Delete the vectors of these chunks; return how many were deleted.

        Raises ``VectorTableNotFoundError`` when the model has no table.
        """
        ...

    def count(self, model_name: str, chunk_ids: list[int] | None = None) -> int:
        """Count the vectors of a table (restricted to ``chunk_ids`` when given); 0 without table."""
        ...

    def retrieve(
        self, model_name: str, top_k: int, vector: list[float], chunk_ids: list[int] | None = None
    ) -> list[dict[str, Any]]:
        """Return up to ``top_k`` ``{"chunk_id": int, "distance": float}``, nearest first.

        ``chunk_ids`` restricts the search to these chunks. Returns ``[]`` without table.
        """
        ...

    def drop(self, model_name: str) -> None:
        """Remove the table of a model. Raises ``VectorTableNotFoundError`` when missing."""
        ...
