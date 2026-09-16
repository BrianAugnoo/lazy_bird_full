def test_upload_file_template_route_is_exposed(client):
    response = client.get("/upload_file")

    assert response.status_code == 200
    assert "Upload de fichiers" in response.text


def test_upload_file_template_accepts_files(client, upload_file_factory, storage_root):
    response = client.post(
        "/upload_file",
        data={"directory": "uploads"},
        files={"files": ("document.txt", b"lazy bird", "text/plain")},
    )

    assert response.status_code == 200
    assert "document.txt" in response.text
