def test_selected_database_endpoint_returns_current_adapters(client):
    response = client.get("/databases/selected_db")

    assert response.status_code == 200
    assert response.json() == {"sql": "sqlite", "vector": "lancedb"}