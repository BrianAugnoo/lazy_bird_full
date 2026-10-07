def test_a_team_is_created_from_a_session_preset(client):
    presets = {item["id"]: item for item in client.get("/session-presets/").json()}
    assert presets["default/research-team"]["valid"] is True

    session = client.post("/sessions/from-preset", json={"preset_id": "default/research-team", "title": "Docs"})
    assert session.status_code == 201, session.text
    agents = client.get(f"/agents/session/{session.json()['id']}").json()

    master = next(agent for agent in agents if agent["master"])
    assert master["preset"] == "default/assistant"
    researcher = next(agent for agent in agents if agent["preset"] == "default/researcher")
    assert [tool["name"] for tool in client.get(f"/agents/{researcher['id']}/tools").json()] == ["search_knowledge_base", "load_skill", "read_skill_file"]


def test_invalid_presets_and_references_are_explained(client):
    session = client.post("/sessions/", json={"title": "s"}).json()

    unknown = client.post("/agents/from-preset", json={"session_id": session["id"], "preset_id": "default/ghost"})
    bad = client.post("/agents/", json={"name": "a", "session_id": session["id"], "tools": ["nope"]})

    assert unknown.status_code == 404 and unknown.json()["error"]["code"] == "preset_not_found"
    assert bad.status_code == 422 and bad.json()["error"]["details"]["fields"] == {"tools": "Unknown: nope"}


def test_tool_settings_are_edited_through_the_api(client):
    settings = client.get("/tools/settings/default/smtp.py").json()
    assert settings["valid"] is False

    invalid = client.put("/tools/settings/default/smtp.py", json={"kwargs": {"smtp_port": "not a port"}})
    valid = client.put(
        "/tools/settings/default/smtp.py",
        json={"kwargs": {"smtp_server": "s", "smtp_port": 465, "smtp_username": "u", "smtp_password": "p", "sender_email": "e@x"}},
    )

    assert invalid.status_code == 422 and "smtp_port" in invalid.json()["error"]["details"]["fields"]
    assert valid.json()["valid"] is True


def test_default_items_are_read_only(client):
    response = client.put("/instructions/full/default/assistant", json={"content": "changed"})

    assert response.status_code == 403 and response.json()["error"]["code"] == "read_only_extension"


def test_extension_failures_are_listed(client):
    assert isinstance(client.get("/extensions/failures").json(), list)
