from tests.conftest import MODEL_INPUT


def test_selected_model_endpoint_sets_and_updates_current_model(client):
    first = client.post("/models/", json=MODEL_INPUT)
    assert first.status_code == 200, first.text

    second = client.post("/models/", json={"hf_path": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"})
    assert second.status_code == 200, second.text

    create_response = client.put("/selected-models/", json={"llm_model_id": 1})
    assert create_response.status_code == 200, create_response.text
    assert create_response.json() == {"llm_model_id": 1, "batch": 1}
    assert client.get("/selected-models/").json() == {"llm_model_id": 1, "batch": 1}

    update_response = client.put("/selected-models/", json={"llm_model_id": 2})
    assert update_response.status_code == 200, update_response.text
    assert update_response.json() == {"llm_model_id": 2, "batch": 1}
    assert client.get("/selected-models/").json() == {"llm_model_id": 2, "batch": 1}


def test_selected_model_endpoint_returns_none_when_table_is_empty(client):
    response = client.get("/selected-models/")

    assert response.status_code == 200
    assert response.json() == {"llm_model_id": None, "batch": 1}
