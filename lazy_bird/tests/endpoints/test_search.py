import pytest


from tests.conftest import process_inline


def upload_and_process(client, name: str, content: bytes) -> int:
    file_id = client.post("/files/upload?dir=docs", files={"files": (name, content, "text/markdown")}).json()[0]["id"]
    process_inline(file_id)
    return file_id


def test_search_returns_chunks_with_their_file(client, fake_embedding):
    upload_and_process(client, "zoo.md", b"zzzz zebra zone\n\naaaa apple")

    response = client.post("/search/", json={"query": "zzz", "top_k": 1})

    assert response.status_code == 200, response.text
    [result] = response.json()
    assert result["chunk"]["content"] == "zzzz zebra zone"
    assert result["file_name"] == "zoo.md"
    assert result["distance"] is not None


def test_search_can_be_limited_to_some_files(client, fake_embedding):
    first = upload_and_process(client, "a.md", b"zzzz")
    second = upload_and_process(client, "b.md", b"zzzz too")

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


# With the fake engines, the embedding order for "zebra zone" is b, d, a, c while
# the cross-encoder (words shared with the query) prefers b, then a and c, then d.
CORPUS = {"a": b"zzzz zzzz zebra", "b": b"zebra zone", "c": b"zebra apple apple apple", "d": b"quiet river"}


def upload_corpus(client) -> dict[str, int]:
    return {name: upload_and_process(client, f"{name}.md", content) for name, content in CORPUS.items()}


def contents(response) -> list[str]:
    return [result["chunk"]["content"] for result in response.json()]


def test_embedding_only_search_has_no_cross_encoder_score(client, fake_embedding):
    upload_corpus(client)

    response = client.post("/search/", json={"query": "zebra zone", "top_k": 2})

    assert contents(response) == ["zebra zone", "quiet river"]
    assert [result["score"] for result in response.json()] == [None, None]


def test_reranking_orders_the_embedding_candidates_by_cross_encoder_score(client, fake_embedding, fake_cross_encoder):
    ids = upload_corpus(client)

    response = client.post("/search/", json={"query": "zebra zone", "top_k": 2, "top_n": 3, "rerank": True})

    assert response.status_code == 200, response.text
    assert contents(response) == ["zebra zone", "zzzz zzzz zebra"]
    assert [result["score"] for result in response.json()] == [2.0, 1.0]
    best = response.json()[0]
    assert best["file_name"] == "b.md" and best["chunk"]["file_id"] == ids["b"] and best["distance"] == 0.0


def test_only_the_top_n_embedding_candidates_are_reranked(client, fake_embedding, fake_cross_encoder):
    upload_corpus(client)

    response = client.post("/search/", json={"query": "zebra zone", "top_k": 1, "top_n": 2, "rerank": True})

    assert contents(response) == ["zebra zone"]
    # With every chunk a candidate, equal scores keep the embedding order and the worst chunk drops out.
    wide = client.post("/search/", json={"query": "zebra zone", "top_k": 3, "top_n": 4, "rerank": True})
    assert contents(wide) == ["zebra zone", "zzzz zzzz zebra", "zebra apple apple apple"]


def test_reranking_respects_the_file_filter(client, fake_embedding, fake_cross_encoder):
    ids = upload_corpus(client)

    response = client.post(
        "/search/", json={"query": "zebra zone", "top_k": 1, "top_n": 2, "rerank": True, "file_ids": [ids["a"], ids["d"]]}
    )

    assert contents(response) == ["zzzz zzzz zebra"]


def test_reranking_can_use_a_chosen_cross_encoder_preset(client, fake_embedding, fake_cross_encoder):
    upload_corpus(client)

    response = client.post(
        "/search/",
        json={"query": "zebra zone", "top_k": 1, "top_n": 2, "rerank": True, "cross_encoder_preset_id": fake_cross_encoder.id},
    )
    missing = client.post("/search/", json={"query": "zebra zone", "top_k": 1, "top_n": 2, "rerank": True, "cross_encoder_preset_id": 999})

    assert response.status_code == 200
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "preset_not_found"


@pytest.mark.parametrize("top_n", [1, 5])
def test_candidates_must_outnumber_the_final_results(client, fake_embedding, fake_cross_encoder, top_n):
    upload_corpus(client)

    response = client.post("/search/", json={"query": "zebra zone", "top_k": 5, "top_n": top_n, "rerank": True})

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_request"
    assert error["details"]["fields"]["top_n"] == "Must be greater than the final results (top_k = 5)."


def test_default_candidates_must_also_outnumber_the_final_results(client, fake_embedding, fake_cross_encoder):
    response = client.post("/search/", json={"query": "zebra", "top_k": 60, "rerank": True})

    assert response.status_code == 422
    assert "top_n" in response.json()["error"]["details"]["fields"]


def test_top_n_is_not_checked_without_reranking(client, fake_embedding):
    upload_corpus(client)

    response = client.post("/search/", json={"query": "zebra zone", "top_k": 5, "top_n": 1})

    assert response.status_code == 200


def test_the_search_function_rejects_invalid_candidates_too(crud_database, fake_embedding, fake_cross_encoder):
    from lazy_bird.crud.search import search
    from lazy_bird.errors import InvalidInputError

    with pytest.raises(InvalidInputError) as error:
        search("zebra", top_k=5, rerank=True, top_n=5)

    assert error.value.code == "invalid_top_n"


def test_reranking_without_cross_encoder_preset_explains_how_to_fix_it(client, fake_embedding):
    upload_corpus(client)

    response = client.post("/search/", json={"query": "zebra zone", "top_k": 2, "rerank": True})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "no_default_cross_encoder_preset"


def test_a_search_only_reads_the_table_of_the_model_it_embeds_the_query_with(client, fake_embedding):
    from lazy_bird.embedding import engine_family, vector_space
    from lazy_bird.tasks.default.files import chunk_file, embed_file

    wide = engine_family.create_preset("wide", fake_embedding.embedding_engine_id, {"dimension": 8})  # not the default

    def upload_embedded_with(name: str, content: bytes, preset_id: int) -> int:
        file_id = client.post("/files/upload?dir=docs", files={"files": (name, content, "text/markdown")}).json()[0]["id"]
        chunk_file.run(file_id=file_id)
        embed_file.run(file_id=file_id, target=vector_space(engine_family.resolve(preset_id)), preset_id=preset_id)
        return file_id

    with_default = upload_embedded_with("small.md", b"zzzz", fake_embedding.id)
    with_wide = upload_embedded_with("wide.md", b"zzzz", wide.id)

    by_default = client.post("/search/", json={"query": "zzzz", "top_k": 10}).json()
    by_wide = client.post("/search/", json={"query": "zzzz", "top_k": 10, "preset_id": wide.id}).json()

    assert {result["chunk"]["file_id"] for result in by_default} == {with_default}
    assert {result["chunk"]["file_id"] for result in by_wide} == {with_wide}


def test_a_model_that_embedded_nothing_finds_nothing(client, fake_embedding):
    from lazy_bird.embedding import engine_family

    unused = engine_family.create_preset("unused", fake_embedding.embedding_engine_id, {"dimension": 8})
    upload_and_process(client, "zoo.md", b"zzzz zebra")

    response = client.post("/search/", json={"query": "zzzz", "preset_id": unused.id})

    assert response.status_code == 200 and response.json() == []
