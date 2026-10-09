import pytest

from lazy_bird.cross_encoder import CrossEncoderEngineError, engine_family, rerank_scores
from lazy_bird.models.llm_model import LLMModel


def add_model(crud_database) -> int:
    with crud_database() as session:
        model = LLMModel(name="MiniLM reranker", hf_path="org/reranker", local_path="/tmp/reranker", formats=["safetensors"], selected_format="safetensors")
        session.add(model)
        session.commit()
        return model.id


def sentence_transformers_id(client) -> int:
    engines = client.get("/cross-encoder-engines/").json()
    return next(engine["id"] for engine in engines if engine["name"] == "sentence-transformers")


def test_cross_encoder_engines_expose_their_settings_form(client):
    engine = client.get(f"/cross-encoder-engines/{sentence_transformers_id(client)}").json()

    assert engine["available"] is True
    assert engine["kwargs_key"]["model_id"]["content"] == "default.basic.reference"
    assert engine["local"] is True
    assert engine["kwargs_key"]["cache_optimization"]["default"] is False
    assert "unloading" not in engine["kwargs_key"]


def test_cross_encoder_presets_are_independent_from_embedding_presets(client, crud_database):
    model_id = add_model(crud_database)

    created = client.post(
        "/cross-encoder-presets/",
        json={"name": "reranker", "cross_encoder_engine_id": sentence_transformers_id(client), "kwargs": {"model_id": model_id}},
    )

    assert created.status_code == 201, created.text
    assert created.json()["default"] is True and created.json()["valid"] is True
    assert client.get("/cross-encoder-presets/default").json()["id"] == created.json()["id"]
    assert client.get("/embedding-presets/").json() == []


def test_invalid_cross_encoder_settings_are_reported_per_field(client):
    response = client.post(
        "/cross-encoder-presets/",
        json={"name": "bad", "cross_encoder_engine_id": sentence_transformers_id(client), "kwargs": {"batch_size": 0}},
    )

    assert response.status_code == 422
    assert set(response.json()["error"]["details"]["fields"]) == {"model_id", "batch_size"}


def test_resolving_without_preset_names_the_cross_encoder(client):
    response = client.get("/cross-encoder-presets/default")

    assert response.status_code == 404
    with pytest.raises(Exception) as error:
        engine_family.resolve()
    assert error.value.code == "no_default_cross_encoder_preset"
    assert "cross encoder" in error.value.message


def test_an_engine_returning_the_wrong_number_of_scores_is_an_error(fake_cross_encoder, monkeypatch):
    resolved = engine_family.resolve()
    monkeypatch.setattr(resolved.module, "rerank", lambda *args: [1.0])

    with pytest.raises(CrossEncoderEngineError):
        rerank_scores("query", ["a", "b"], resolved)
    assert rerank_scores("query", [], resolved) == []
