from pathlib import Path
import pytest

from lazy_bird import database
from lazy_bird.database.vector_db import lancedb


def test_database_catalog_exposes_adapter_schemas():
    catalog = database.adapter_catalog()
    assert "sqlite" in catalog["sql"]
    assert "lancedb" in catalog["vector"]
    assert catalog["sql"]["sqlite"]["settings_schema"]["type"] == "object"


def test_unknown_database_cannot_be_selected():
    with pytest.raises(ValueError, match="Unknown vector database"):
        database.switch_database("vector", "missing", {})


def test_lancedb_create_retrieve_and_delete(tmp_path: Path):
    lancedb.initialize(path=str(tmp_path / "vectors"))
    rows = [{"content": "one", "start_line": 1, "end_line": 1, "start_row": 0, "end_row": 2, "meta_data": {}, "vector": [1.0, 0.0]}]
    assert lancedb.create("owner/model", 7, rows) == 1
    result = lancedb.retrieve("owner/model", 1, [1.0, 0.0])
    assert result[0]["content"] == "one"
    assert result[0]["embedded_id"] == 7
    assert lancedb.delete("owner/model", 7) == 1
