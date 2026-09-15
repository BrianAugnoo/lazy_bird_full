def test_database_schema_template_route_is_not_exposed(client):
    assert client.get("/shemas").status_code == 404
