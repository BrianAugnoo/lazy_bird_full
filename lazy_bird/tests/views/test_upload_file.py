def test_upload_file_view_renders_multipart_form(client):
    response = client.get("/upload_file")

    assert response.status_code == 200
    assert "Upload de fichiers" in response.text
    assert 'action="/upload_file"' in response.text
    assert 'enctype="multipart/form-data"' in response.text
    assert 'name="directory"' in response.text
    assert 'name="files"' in response.text
    assert "multiple" in response.text


def test_upload_file_view_uploads_and_renders_results(client):
    response = client.post(
        "/upload_file",
        data={"directory": "documents"},
        files=[
            ("files", ("one.txt", b"one", "text/plain")),
            ("files", ("two.txt", b"two", "text/plain")),
        ],
    )

    assert response.status_code == 200, response.text
    assert "2 fichier(s) enregistré(s)" in response.text
    assert "one.txt" in response.text
    assert "two.txt" in response.text


def test_upload_file_view_renders_storage_error(client):
    response = client.post(
        "/upload_file",
        data={"directory": "../outside"},
        files={"files": ("file.txt", b"data", "text/plain")},
    )

    assert response.status_code == 400
    assert "Invalid destination directory" in response.text


def test_upload_file_view_requires_form_fields(client):
    response = client.post("/upload_file")

    assert response.status_code == 422
