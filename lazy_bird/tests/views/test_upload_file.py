def test_upload_file_template_route_is_not_exposed(client):
    assert client.get("/upload_file").status_code == 404
    assert client.post("/upload_file").status_code == 404
