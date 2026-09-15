"""Explicit contracts implemented by database adapter modules."""

from __future__ import annotations

from typing import Any, Protocol

from sqlalchemy.engine import Engine


class SQLDatabaseAdapter(Protocol):
    name: str

    def initialize(self, **settings: Any) -> Engine:
        """Create a SQL engine from adapter-specific settings."""
        ...

    def disconnect(self, engine: Engine, drop: bool = False) -> None:
        """Close the engine and optionally remove its database."""
        ...


class VectorDatabaseAdapter(Protocol):
    name: str

    def initialize(self, **settings: Any) -> Any:
        """Connect to the vector database from adapter-specific settings."""
        ...

    def disconnect(self, drop: bool = False) -> None:
        """Close the connection and optionally remove stored vectors."""
        ...

    def create(self, model_name: str, embedded_id: int, chunks: list[dict[str, Any]]) -> int:
        ...

    def delete(self, model_name: str, embedded_id: int) -> int:
        ...

    def retrieve(self, model_name: str, top_k: int, vector: list[float]) -> list[dict[str, Any]]:
        ...
