from lazy_bird.models.llm_model import LLMModel


def add_model(crud_database, selected_format: str = "safetensors") -> int:
    with crud_database() as session:
        model = LLMModel(name="MiniLM", hf_path="org/minilm", local_path="/tmp/minilm", dimension=4, formats=[selected_format], selected_format=selected_format)
        session.add(model)
        session.commit()
        return model.id


def sentence_transformers_id(client) -> int:
    engines = client.get("/embedding-engines/").json()
    return next(engine["id"] for engine in engines if engine["name"] == "sentence-transformers")


def test_embedding_engines_expose_their_settings_form(client):
    engine = client.get(f"/embedding-engines/{sentence_transformers_id(client)}").json()

    assert engine["available"] is True
    assert engine["kwargs_key"]["model_id"]["content"] == "default.basic.reference"
    assert engine["kwargs_key"]["model_id"]["required"] is True
    assert engine["kwargs_key"]["batch_size"]["content"] == "default.basic.integer"
    assert engine["kwargs_key"]["device"]["args"] == {"options": ["cpu", "cuda", "mps"]}


def test_preset_lifecycle(client, crud_database):
    model_id = add_model(crud_database)
    engine_id = sentence_transformers_id(client)

    created = client.post("/embedding-presets/", json={"name": "local", "embedding_engine_id": engine_id, "kwargs": {"model_id": model_id}})
    assert created.status_code == 201, created.text
    preset = created.json()
    assert preset["default"] is True and preset["valid"] is True and preset["errors"] == {}
    assert client.get("/embedding-presets/default").json()["id"] == preset["id"]

    renamed = client.patch(f"/embedding-presets/{preset['id']}", json={"name": "renamed", "kwargs": {"model_id": model_id, "batch_size": 8}})
    assert renamed.status_code == 200, renamed.text
    assert renamed.json()["kwargs"] == {"model_id": model_id, "batch_size": 8}

    assert client.delete(f"/embedding-presets/{preset['id']}").status_code == 204
    missing = client.get("/embedding-presets/default")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "no_default_preset"


def test_invalid_preset_settings_are_reported_per_field(client):
    response = client.post(
        "/embedding-presets/",
        json={"name": "bad", "embedding_engine_id": sentence_transformers_id(client), "kwargs": {"batch_size": 0, "device": "tpu"}},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "invalid_settings"
    assert set(error["details"]["fields"]) == {"model_id", "batch_size", "device"}


def test_unsetting_the_only_default_is_a_conflict(client, crud_database):
    model_id = add_model(crud_database)
    preset = client.post("/embedding-presets/", json={"name": "local", "embedding_engine_id": sentence_transformers_id(client), "kwargs": {"model_id": model_id}}).json()

    response = client.patch(f"/embedding-presets/{preset['id']}", json={"default": False})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "default_preset_required"


def test_inference_presets_validate_engine_settings(client):
    engine = next(engine for engine in client.get("/inference-engines/").json() if engine["name"] == "openai-client")

    invalid = client.post("/inference-presets/", json={"name": "remote", "inference_engine_id": engine["id"], "kwargs": {}})
    valid = client.post(
        "/inference-presets/",
        json={"name": "remote", "inference_engine_id": engine["id"], "kwargs": {"base_url": "http://localhost:1/v1", "model_name": "m"}},
    )

    assert invalid.status_code == 422
    assert set(invalid.json()["error"]["details"]["fields"]) == {"base_url", "model_name"}
    assert valid.status_code == 201
    assert valid.json()["default"] is True


def test_unknown_resources_return_typed_not_found_errors(client):
    assert client.get("/embedding-presets/404").json()["error"]["code"] == "preset_not_found"
    assert client.get("/inference-engines/404").json()["error"]["code"] == "engine_not_found"
