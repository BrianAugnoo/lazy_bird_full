from pathlib import Path

import pytest

from lazy_bird import database
from lazy_bird.database.contracts import VectorTableNotFoundError
from lazy_bird.errors import InvalidSettingsError, NotFoundError
from lazy_bird.database.vector_db import lancedb


def test_database_catalog_exposes_adapter_settings_forms():
    catalog = database.adapter_catalog()
    assert catalog["sql"]["sqlite"]["kwargs_key"]["url"]["content"] == "default.basic.text"
    assert catalog["vector"]["lancedb"]["kwargs_key"]["path"]["nullable"] is True
    assert catalog["sql"]["sqlite"]["selected"] is True


def test_unknown_database_cannot_be_selected():
    with pytest.raises(NotFoundError) as error:
        database.switch_database("vector", "missing", {})
    assert error.value.code == "unknown_database"


def test_invalid_adapter_settings_are_reported_per_field():
    with pytest.raises(InvalidSettingsError) as error:
        database.switch_database("vector", "lancedb", {"path": 3, "other": 1})
    assert set(error.value.fields) == {"path", "other"}


@pytest.fixture
def vectors(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(lancedb, "_connection", None)
    lancedb.initialize(path=str(tmp_path / "vectors"))
    yield lancedb
    lancedb.disconnect()


MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def test_tables_are_named_after_the_model(vectors):
    vectors.create(MODEL, [{"chunk_id": 1, "vector": [1.0, 0.0]}])
    vectors.create("org/other_model", [{"chunk_id": 1, "vector": [1.0, 0.0, 0.0]}])

    assert vectors.tables() == ["org/other_model", MODEL]


@pytest.mark.parametrize("name", [MODEL, "a_b/c", "_s", "é/x_y", "text-embedding-3-small"])
def test_table_names_round_trip(name):
    assert lancedb.model_name_of(lancedb.table_name(name)) == name


def test_create_inserts_or_replaces_vectors_by_chunk_id(vectors):
    assert vectors.create(MODEL, [{"chunk_id": 1, "vector": [1.0, 0.0]}, {"chunk_id": 2, "vector": [0.0, 1.0]}]) == 2
    assert vectors.create(MODEL, [{"chunk_id": 2, "vector": [1.0, 0.1]}]) == 1

    assert vectors.count(MODEL) == 2
    assert [hit["chunk_id"] for hit in vectors.retrieve(MODEL, 2, [1.0, 0.0])] == [1, 2]


def test_create_rejects_empty_rows(vectors):
    with pytest.raises(ValueError):
        vectors.create(MODEL, [])


def test_retrieve_returns_chunk_ids_and_distances(vectors):
    vectors.create(MODEL, [{"chunk_id": 7, "vector": [1.0, 0.0]}, {"chunk_id": 8, "vector": [0.0, 1.0]}])

    hits = vectors.retrieve(MODEL, 1, [0.0, 1.0])

    assert hits == [{"chunk_id": 8, "distance": 0.0}]
    assert vectors.retrieve(MODEL, 5, [1.0, 0.0], chunk_ids=[8]) == [{"chunk_id": 8, "distance": 2.0}]
    assert vectors.retrieve(MODEL, 5, [1.0, 0.0], chunk_ids=[]) == []
    assert vectors.retrieve("missing/model", 5, [1.0, 0.0]) == []


def test_delete_and_count_by_chunk_ids(vectors):
    vectors.create(MODEL, [{"chunk_id": 1, "vector": [1.0, 0.0]}, {"chunk_id": 2, "vector": [0.0, 1.0]}])

    assert vectors.count(MODEL, [1, 3]) == 1
    assert vectors.delete(MODEL, [1, 3]) == 1
    assert vectors.count(MODEL) == 1
    assert vectors.count("missing/model") == 0


def test_missing_tables_cannot_be_deleted_from_or_dropped(vectors):
    with pytest.raises(VectorTableNotFoundError):
        vectors.delete("missing/model", [1])
    with pytest.raises(VectorTableNotFoundError):
        vectors.drop("missing/model")


def test_drop_removes_a_model_table(vectors):
    vectors.create(MODEL, [{"chunk_id": 1, "vector": [1.0, 0.0]}])

    vectors.drop(MODEL)

    assert vectors.tables() == []


def test_existing_table_operations_do_not_list_the_catalog(vectors, monkeypatch):
    vectors.create(MODEL, [{"chunk_id": 1, "vector": [1.0, 0.0]}])

    def unexpected_listing(database):
        pytest.fail("Opening an existing table should not scan the catalog")

    monkeypatch.setattr(vectors, "_table_names", unexpected_listing)
    vectors.create(MODEL, [{"chunk_id": 2, "vector": [0.0, 1.0]}])
    assert vectors.count(MODEL) == 2
    assert vectors.retrieve(MODEL, 1, [0.0, 1.0]) == [{"chunk_id": 2, "distance": 0.0}]
    assert vectors.delete(MODEL, [2]) == 1
    vectors.drop(MODEL)


def test_failed_open_of_an_existing_table_is_not_hidden(vectors, monkeypatch):
    vectors.create(MODEL, [{"chunk_id": 1, "vector": [1.0, 0.0]}])

    def failed_open(name):
        raise ValueError("damaged manifest")

    monkeypatch.setattr(vectors._db(), "open_table", failed_open)
    with pytest.raises(ValueError, match="damaged manifest"):
        vectors.count(MODEL)


def test_workers_can_create_the_same_model_table_concurrently(vectors):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    start = threading.Barrier(4)

    def create(chunk_id):
        start.wait(timeout=5)
        return vectors.create(MODEL, [{"chunk_id": chunk_id, "vector": [float(chunk_id), 0.0]}])

    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(create, range(4))) == [1, 1, 1, 1]
    assert vectors.count(MODEL) == 4
