from tests.conftest import MODEL_INPUT, MODEL_OUTPUT


def test_model_endpoint_creates_gets_and_lists_models(client, fake_model_services):
    created = client.post("/models/", json=MODEL_INPUT)
    listed = client.get("/models/")
    fetched = client.get("/models/1")

    assert created.status_code == 200, created.text
    assert created.json() == MODEL_OUTPUT
    assert listed.status_code == 200
    assert listed.json() == [MODEL_OUTPUT]
    assert fetched.status_code == 200
    assert fetched.json() == MODEL_OUTPUT


def test_model_endpoint_returns_null_for_unknown_model(client):
    response = client.get("/models/9999")

    assert response.status_code == 200
    assert response.json() is None


def test_model_endpoint_deletes_all_models(client, fake_model_services):
    client.post("/models/", json=MODEL_INPUT)

    response = client.delete("/models/destroy")

    assert response.status_code == 200
    assert response.json() == {"message": "All llm models deleted."}
    assert client.get("/models/").json() == []


def test_model_endpoint_rejects_missing_hugging_face_path(client):
    response = client.post("/models/", json={})

    assert response.status_code == 422
