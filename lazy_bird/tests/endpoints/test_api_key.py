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



def test_keys_can_be_replaced_and_deleted(client):
    from lazy_bird.crud import api_key as api_key_crud

    client.post("/api-keys/", json={"name": "OpenAI", "key": "first"})

    assert client.put("/api-keys/OpenAI", json={"key": "second"}).json() == {"name": "OpenAI"}
    assert api_key_crud.find_key("OpenAI") == "second"
    assert client.delete("/api-keys/OpenAI").status_code == 204
    assert client.get("/api-keys/OpenAI").json()["error"]["code"] == "api_key_not_found"
    assert client.put("/api-keys/OpenAI", json={"key": "third"}).status_code == 404


def test_the_hugging_face_login_follows_its_key(client, monkeypatch):
    from lazy_bird.tools import hf_auth

    calls = []
    monkeypatch.setattr(hf_auth, "authenticate_hf", lambda: calls.append("login"))
    monkeypatch.setattr(hf_auth, "logout_hf", lambda: calls.append("logout"))

    client.post("/api-keys/", json={"name": "HuggingFace", "key": "hf_first"})
    client.put("/api-keys/HuggingFace", json={"key": "hf_second"})
    client.post("/api-keys/", json={"name": "OpenAI", "key": "other"})
    client.delete("/api-keys/OpenAI")
    client.delete("/api-keys/HuggingFace")

    assert calls == ["login", "login", "logout"]
