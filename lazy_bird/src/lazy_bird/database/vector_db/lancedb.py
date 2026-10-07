import re
from pathlib import Path

import lancedb
from pydantic import BaseModel, ConfigDict

from lazy_bird.database.contracts import VectorTableNotFoundError

name = "lancedb"
messages = {"initialize": "LanceDB stores vectors locally.", "disconnect": "Dropping LanceDB removes all vector tables."}
TABLE_PREFIX = "vectors__"
_connection = None


class Settings(BaseModel):
    path: str | None = None
    model_config = ConfigDict(extra="forbid")


def initialize(**kwargs):
    global _connection
    settings = Settings.model_validate(kwargs)
    path = Path(settings.path) if settings.path else Path(__file__).resolve().parents[1] / "storage" / "lance"
    path.mkdir(parents=True, exist_ok=True)
    _connection = lancedb.connect(str(path))
    return _connection


def _db():
    return _connection if _connection is not None else initialize()


def table_name(model_name: str) -> str:
    """Encode a model name into a reversible LanceDB table name."""
    if not model_name:
        raise ValueError("A vector table needs a model name")

    def escape(match: re.Match) -> str:
        character = match.group(0)
        return "_s" if character == "/" else "__" if character == "_" else f"_x{ord(character):04x}"

    return TABLE_PREFIX + re.sub(r"[^A-Za-z0-9.-]", escape, model_name)


def model_name_of(table: str) -> str | None:
    """Decode a table name produced by ``table_name``; None for foreign tables."""
    if not table.startswith(TABLE_PREFIX):
        return None
    encoded = table[len(TABLE_PREFIX):]

    def unescape(match: re.Match) -> str:
        token = match.group(0)
        return "/" if token == "_s" else "_" if token == "__" else chr(int(token[2:], 16))

    return re.sub(r"_s|__|_x[0-9a-f]{4}", unescape, encoded)


def _table_names(database) -> list[str]:
    names, token = [], None
    while True:
        page = database.list_tables(page_token=token) if token else database.list_tables()
        names.extend(page.tables)
        token = page.page_token
        if not token:
            return names


def _open(model_name: str):
    database, table = _db(), table_name(model_name)
    if table not in _table_names(database):
        return None
    return database.open_table(table)


def _ids_filter(chunk_ids: list[int]) -> str:
    return f"chunk_id IN ({', '.join(str(int(chunk_id)) for chunk_id in chunk_ids)})"


def tables() -> list[str]:
    return sorted(name for name in map(model_name_of, _table_names(_db())) if name is not None)


def create(model_name: str, rows: list[dict]) -> int:
    if not rows:
        raise ValueError("create() needs at least one row")
    records = [{"chunk_id": int(row["chunk_id"]), "vector": [float(value) for value in row["vector"]]} for row in rows]
    table = _open(model_name)
    if table is None:
        _db().create_table(table_name(model_name), data=records)
    else:
        table.merge_insert("chunk_id").when_matched_update_all().when_not_matched_insert_all().execute(records)
    return len(records)


def delete(model_name: str, chunk_ids: list[int]) -> int:
    table = _open(model_name)
    if table is None:
        raise VectorTableNotFoundError(model_name)
    if not chunk_ids:
        return 0
    return table.delete(_ids_filter(chunk_ids)).num_deleted_rows


def count(model_name: str, chunk_ids: list[int] | None = None) -> int:
    table = _open(model_name)
    if table is None:
        return 0
    if chunk_ids is None:
        return table.count_rows()
    return table.count_rows(_ids_filter(chunk_ids)) if chunk_ids else 0


def retrieve(model_name: str, top_k: int, vector: list[float], chunk_ids: list[int] | None = None) -> list[dict]:
    table = _open(model_name)
    if table is None or (chunk_ids is not None and not chunk_ids):
        return []
    query = table.search(vector).limit(top_k)
    if chunk_ids is not None:
        query = query.where(_ids_filter(chunk_ids), prefilter=True)
    return [{"chunk_id": int(row["chunk_id"]), "distance": float(row["_distance"])} for row in query.to_list()]


def drop(model_name: str) -> None:
    if _open(model_name) is None:
        raise VectorTableNotFoundError(model_name)
    _db().drop_table(table_name(model_name))


def disconnect(drop: bool = False):
    global _connection
    if drop and _connection is not None:
        for table in _table_names(_connection):
            if model_name_of(table) is not None:
                _connection.drop_table(table)
    _connection = None
