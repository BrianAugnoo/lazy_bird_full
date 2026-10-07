def test_extensions_are_discovered_again_on_demand(client, monkeypatch):
    import lazy_bird.main as main_module

    calls = []
    monkeypatch.setattr(main_module, "initialize_extensions", lambda: calls.append("reload"))

    response = client.post("/extensions/reload")

    assert response.status_code == 200 and isinstance(response.json(), list)
    assert calls == ["reload"]
