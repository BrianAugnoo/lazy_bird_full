def test_database_schema_view_renders_migration_schema(client):
    response = client.get("/shemas")

    assert response.status_code == 200
    assert "Schéma de la base de données" in response.text
    assert "erDiagram" in response.text
    assert "selectedmodelembeding" in response.text
    assert "llmmodel ||--o{" in response.text
