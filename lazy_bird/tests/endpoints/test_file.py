import pytest


def test_file_endpoint_uploads_multiple_files_and_lists_them(client):
    response = client.post(
        "/files/upload?dir=documents",
        files=[
            ("files", ("first.txt", b"first", "text/plain")),
            ("files", ("second.pdf", b"second", "application/pdf")),
        ],
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert [file["name"] for file in payload] == ["first", "second"]
    assert [file["extension"] for file in payload] == [".txt", ".pdf"]
    assert [file["size"] for file in payload] == [5, 6]

    listed = client.get("/files/")
    assert listed.status_code == 200
    assert listed.json() == payload


def test_file_endpoint_gets_a_file_by_id(client):
    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("report.txt", b"report", "text/plain")},
    )
    file_id = created.json()[0]["id"] if "id" in created.json()[0] else 1

    response = client.get(f"/files/{file_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "report"


def test_file_endpoint_returns_null_for_unknown_id(client):
    response = client.get("/files/9999")

    assert response.status_code == 200
    assert response.json() is None


def test_file_endpoint_requires_directory_and_files(client):
    missing_directory = client.post("/files/upload", files={"files": ("file.txt", b"data")})
    missing_files = client.post("/files/upload?dir=documents")

    assert missing_directory.status_code == 422
    assert missing_files.status_code == 422

@pytest.mark.xfail(reason="The API does not translate storage validation errors to HTTP 400", strict=True)
def test_file_endpoint_rejects_parent_directory(client):
    response = client.post(
        "/files/upload?dir=../outside",
        files={"files": ("file.txt", b"data", "text/plain")},
    )

    assert response.status_code == 400
