import lazy_bird.crud.embedding_engine as embedding_engine_crud


def test_upsert_persists_engine_kwargs_metadata(crud_database):
    engine = embedding_engine_crud.upsert(
        "sentence-transformers", "sentence_transformers", ["safetensors"]
    )

    assert engine.kwargs_keys == {
        "device": ["str", None],
        "model_path": ["str", None],
        "temperature": ["float", None],
    }


def test_upsert_refreshes_engine_kwargs_metadata(crud_database):
    first = embedding_engine_crud.upsert(
        "sentence-transformers", "sentence_transformers", ["safetensors"]
    )
    first.kwargs_keys["device"] = ["outdated", "required"]

    refreshed = embedding_engine_crud.upsert(
        "sentence-transformers", "sentence_transformers", ["safetensors"]
    )

    assert refreshed.kwargs_keys["device"] == ["str", None]