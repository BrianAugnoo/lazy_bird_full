from pathlib import Path
import json, re
import lancedb
from pydantic import BaseModel, ConfigDict

name = "lancedb"
messages = {"initialize": "LanceDB stores vectors locally.", "disconnect": "Dropping LanceDB removes all vector tables."}
_connection = None

class Settings(BaseModel):
    path: str | None = None
    model_config = ConfigDict(extra="forbid")

def initialize(**kwargs):
    global _connection
    settings = Settings.model_validate(kwargs)
    path = Path(settings.path) if settings.path else Path(__file__).resolve().parents[1] / "storage" / "lance"
    path.mkdir(parents=True, exist_ok=True); _connection = lancedb.connect(str(path)); return _connection

def _db(): return _connection if _connection is not None else initialize()
def _tables(database): return database.list_tables().tables
def _table_name(model_name: str):
    value = re.sub(r"[^a-zA-Z0-9_]+", "_", model_name).strip("_").lower()
    if not value: raise ValueError("Invalid model name")
    return f"model_{value}"

def create(model_name: str, embedded_id: int, chunks: list[dict]):
    rows = [{**chunk, "meta_data": json.dumps(chunk.get("meta_data", {})), "embedded_id": embedded_id} for chunk in chunks]
    if not rows: return 0
    database, table_name = _db(), _table_name(model_name)
    if table_name in _tables(database): database.open_table(table_name).add(rows)
    else: database.create_table(table_name, data=rows)
    return len(rows)

def delete(model_name: str, embedded_id: int):
    database, table_name = _db(), _table_name(model_name)
    if table_name not in _tables(database): return 0
    database.open_table(table_name).delete(f"embedded_id = {int(embedded_id)}"); return 1

def retrieve(model_name: str, top_k: int, vector: list[float]):
    database, table_name = _db(), _table_name(model_name)
    if table_name not in _tables(database): return []
    rows = database.open_table(table_name).search(vector).limit(top_k).to_list()
    for row in rows: row["meta_data"] = json.loads(row["meta_data"])
    return rows

def disconnect(drop: bool = False):
    global _connection
    if drop and _connection is not None:
        for table in _tables(_connection): _connection.drop_table(table)
    _connection = None
