def test_api_key_endpoint_creates_gets_and_lists_records(client):
    payload = {"name": "OpenAI", "key": "secret"}

    created = client.post("/api-keys/", json=payload)
    fetched = client.get("/api-keys/OpenAI")
    listed = client.get("/api-keys/")

    assert created.status_code == 201, created.text
    assert created.json() == {"name": "OpenAI"}
    assert fetched.status_code == 200
    assert fetched.json() == {"name": "OpenAI"}
    assert listed.status_code == 200
    assert listed.json() == [{"name": "OpenAI"}]


def test_api_key_endpoint_returns_not_found_for_unknown_name(client):
    response = client.get("/api-keys/missing")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "api_key_not_found"


def test_api_key_endpoint_translates_duplicate_error(client):
    payload = {"name": "OpenAI", "key": "first"}
    client.post("/api-keys/", json=payload)

    response = client.post("/api-keys/", json={"name": "OpenAI", "key": "second"})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "unique_field_violation"
    assert "OpenAI" in response.json()["error"]["message"]


def test_api_key_endpoint_rejects_invalid_json(client):
    response = client.post("/api-keys/", json={"name": "OpenAI"})

    assert response.status_code == 422

