def test_api_key_endpoint_creates_gets_and_lists_records(client):
    payload = {"name": "OpenAI", "key": "secret"}

    created = client.post("/api-keys/api-keys", json=payload)
    fetched = client.get("/api-keys/api-keys/OpenAI")
    listed = client.get("/api-keys/api-keys")

    assert created.status_code == 200, created.text
    assert created.json() == {"name": "OpenAI"}
    assert fetched.status_code == 200
    assert fetched.json() == {"name": "OpenAI"}
    assert listed.status_code == 200
    assert listed.json() == [{"name": "OpenAI"}]


def test_api_key_endpoint_returns_not_found_for_unknown_name(client):
    response = client.get("/api-keys/api-keys/missing")

    assert response.status_code == 404
    assert response.json() == {"detail": "API key not found"}


def test_api_key_endpoint_translates_duplicate_error(client):
    payload = {"name": "OpenAI", "key": "first"}
    client.post("/api-keys/api-keys", json=payload)

    response = client.post("/api-keys/api-keys", json={"name": "OpenAI", "key": "second"})

    assert response.status_code == 400
    assert "OpenAI" in response.json()["detail"]


def test_api_key_endpoint_rejects_invalid_json(client):
    response = client.post("/api-keys/api-keys", json={"name": "OpenAI"})

    assert response.status_code == 422

