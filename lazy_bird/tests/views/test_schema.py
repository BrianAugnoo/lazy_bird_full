def test_database_schema_template_route_is_exposed(client, monkeypatch):
    monkeypatch.setattr("lazy_bird.main.get_schema_diagram", lambda: "erDiagram\n    file {")

    response = client.get("/shemas")

    assert response.status_code == 200
    assert "Schéma de la base de données" in response.text
    assert "erDiagram" in response.text
