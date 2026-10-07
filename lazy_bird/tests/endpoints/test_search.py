import pytest

from lazy_bird.crud.file_processing import process_file


async def upload_and_process(client, name: str, content: bytes) -> int:
    file_id = client.post("/files/upload?dir=docs", files={"files": (name, content, "text/markdown")}).json()[0]["id"]
    await process_file(file_id)
    return file_id


@pytest.mark.anyio
async def test_search_returns_chunks_with_their_file(client, fake_embedding):
    await upload_and_process(client, "zoo.md", b"zzzz zebra zone\n\naaaa apple")

    response = client.post("/search/", json={"query": "zzz", "top_k": 1})

    assert response.status_code == 200, response.text
    [result] = response.json()
    assert result["chunk"]["content"] == "zzzz zebra zone"
    assert result["file_name"] == "zoo.md"
    assert result["distance"] is not None


@pytest.mark.anyio
async def test_search_can_be_limited_to_some_files(client, fake_embedding):
    first = await upload_and_process(client, "a.md", b"zzzz")
    second = await upload_and_process(client, "b.md", b"zzzz too")

    response = client.post("/search/", json={"query": "zzzz", "top_k": 5, "file_ids": [second]})

    assert {result["chunk"]["file_id"] for result in response.json()} == {second}
    assert first != second


def test_search_without_preset_explains_how_to_fix_it(client):
    response = client.post("/search/", json={"query": "anything"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_default_embedding_preset"


def test_vector_tables_can_be_listed_and_dropped(client, fake_embedding):
    from lazy_bird import database

    database.vector_create("org/model", [{"chunk_id": 1, "vector": [1.0]}])

    assert client.get("/databases/vector/tables").json() == [{"model_name": "org/model", "vectors": 1}]
    assert client.delete("/databases/vector/tables/org/model").status_code == 204
    assert client.get("/databases/vector/tables").json() == []
    assert client.delete("/databases/vector/tables/org/model").json()["error"]["code"] == "vector_table_not_found"
