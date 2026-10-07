def test_the_data_model_page_draws_the_migrated_schema(client, monkeypatch):
    monkeypatch.setattr("lazy_bird.main.get_schema_diagram", lambda: "erDiagram\n    file {")

    response = client.get("/schemas")

    assert response.status_code == 200
    assert "Data model" in response.text
    assert "erDiagram" in response.text


def test_the_old_schema_address_redirects(client):
    response = client.get("/shemas", follow_redirects=False)

    assert response.status_code == 308
    assert response.headers["location"] == "/schemas"
