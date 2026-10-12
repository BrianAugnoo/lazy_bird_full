def _create(client, **fields):
    response = client.post("/users/", json={"name": "Ada", **fields})
    assert response.status_code == 201, response.text
    return response.json()


def test_a_user_is_created_with_its_profile_and_listed(client):
    created = _create(
        client,
        description="Writes compilers",
        profession="Engineer",
        email="ada@example.com",
        age=36,
        languages=["French", "English"],
        meta={"timezone": "Europe/Paris", "likes": ["chess"]},
    )

    assert created["id"] > 0
    assert {key: created[key] for key in ("name", "description", "profession", "email", "age", "languages", "meta")} == {
        "name": "Ada",
        "description": "Writes compilers",
        "profession": "Engineer",
        "email": "ada@example.com",
        "age": 36,
        "languages": ["French", "English"],
        "meta": {"timezone": "Europe/Paris", "likes": ["chess"]},
    }
    assert created["created_at"].endswith("Z")
    assert client.get(f"/users/{created['id']}").json() == created
    assert client.get("/users/").json() == [created]


def test_only_the_name_is_required(client):
    created = _create(client)

    assert created["description"] is None
    assert created["profession"] is None
    assert created["age"] is None
    assert created["languages"] == []
    assert created["meta"] is None


def test_languages_keep_the_order_of_proficiency(client):
    created = _create(client, languages=["Spanish", "English", "French"])

    assert client.get(f"/users/{created['id']}").json()["languages"] == ["Spanish", "English", "French"]
    reordered = client.patch(f"/users/{created['id']}", json={"languages": ["French", "Spanish"]})
    assert reordered.json()["languages"] == ["French", "Spanish"]


def test_languages_are_trimmed_and_cannot_be_empty_or_repeated(client):
    assert _create(client, languages=[" French "])["languages"] == ["French"]

    for languages in ([""], ["  "], ["French", "french"]):
        response = client.post("/users/", json={"name": "Ada", "languages": languages})

        assert response.status_code == 422, languages
        assert "languages" in response.json()["error"]["details"]["fields"]


def test_the_age_must_be_a_plausible_number(client):
    for age in (-1, 151, "old"):
        response = client.post("/users/", json={"name": "Ada", "age": age})

        assert response.status_code == 422, age
        assert "age" in response.json()["error"]["details"]["fields"]
    assert _create(client, age=0)["age"] == 0


def test_meta_must_be_an_object(client):
    response = client.post("/users/", json={"name": "Ada", "meta": ["not", "an", "object"]})

    assert response.status_code == 422
    assert "meta" in response.json()["error"]["details"]["fields"]


def test_a_user_needs_a_name(client):
    for body in ({}, {"name": ""}):
        response = client.post("/users/", json=body)

        assert response.status_code == 422
        assert "name" in response.json()["error"]["details"]["fields"]


def test_an_update_changes_only_the_fields_sent_and_null_clears_one(client):
    created = _create(client, profession="Engineer", description="Writes compilers")

    updated = client.patch(f"/users/{created['id']}", json={"profession": "Mathematician", "description": None})

    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert (body["name"], body["profession"], body["description"]) == ("Ada", "Mathematician", None)
    assert body["created_at"] == created["created_at"]
    assert body["updated_at"] > created["updated_at"]
    assert client.get(f"/users/{created['id']}").json() == body


def test_a_name_cannot_be_removed_or_emptied(client):
    created = _create(client)

    for name in (None, ""):
        response = client.patch(f"/users/{created['id']}", json={"name": name})

        assert response.status_code == 422
    assert client.get(f"/users/{created['id']}").json()["name"] == "Ada"


def test_languages_cannot_be_removed_but_can_be_emptied(client):
    created = _create(client, languages=["French"])

    assert client.patch(f"/users/{created['id']}", json={"languages": None}).status_code == 422
    assert client.patch(f"/users/{created['id']}", json={"languages": []}).json()["languages"] == []


def test_age_and_meta_can_be_changed_and_cleared(client):
    created = _create(client, age=36, meta={"a": 1})

    changed = client.patch(f"/users/{created['id']}", json={"age": 37, "meta": {"b": 2}}).json()
    cleared = client.patch(f"/users/{created['id']}", json={"age": None, "meta": None}).json()

    assert (changed["age"], changed["meta"]) == (37, {"b": 2})
    assert (cleared["age"], cleared["meta"]) == (None, None)


def test_a_deleted_user_is_gone(client):
    created = _create(client)

    assert client.delete(f"/users/{created['id']}").status_code == 204
    assert client.get(f"/users/{created['id']}").json()["error"]["code"] == "user_not_found"
    assert client.get("/users/").json() == []


def test_unknown_users_are_not_found(client):
    assert client.get("/users/99").status_code == 404
    assert client.patch("/users/99", json={"name": "Bob"}).status_code == 404
    assert client.delete("/users/99").status_code == 404
