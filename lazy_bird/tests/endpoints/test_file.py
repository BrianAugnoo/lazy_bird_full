from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud


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
    file_id = created.json()[0]["id"]

    response = client.get(f"/files/{file_id}")

    assert response.status_code == 200
    assert response.json()["name"] == "report"


def test_file_endpoint_returns_the_entire_file_by_id(client):
    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("archive.bin", b"\x00\x01complete", "application/octet-stream")},
    )
    file_id = created.json()[0]["id"]

    response = client.get(f"/files/{file_id}/full")

    assert response.status_code == 200
    assert response.content == b"\x00\x01complete"
    assert response.headers["content-type"] == "application/octet-stream"
    assert 'filename="archive.bin"' in response.headers["content-disposition"]
    assert response.headers["content-disposition"].startswith("inline;")
    partial = client.get(f"/files/{file_id}/full", headers={"Range": "bytes=2-5"})
    assert partial.status_code == 206
    assert partial.content == b"comp"


def test_file_output_includes_its_chunk_count(client, crud_database):
    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("report.txt", b"report", "text/plain")},
    )
    file_id = created.json()[0]["id"]
    chunk_crud.replace(file_id, [{"content": "a", "start_line": 1, "end_line": 1}, {"content": "b", "start_line": 2, "end_line": 2}])

    response = client.get(f"/files/{file_id}")

    assert response.status_code == 200
    assert response.json()["chunk_count"] == 2
    assert [chunk["content"] for chunk in client.get(f"/files/{file_id}/chunks").json()] == ["a", "b"]


def test_unknown_files_are_not_found(client):
    for response in (client.get("/files/9999"), client.get("/files/9999/content"), client.get("/files/9999/download"), client.post("/files/9999/process")):
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "file_not_found"


def test_file_endpoint_deletes_file_with_its_chunks_and_vectors(client, crud_database):
    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("embedded.md", b"# document", "text/markdown")},
    )
    file_id = created.json()[0]["id"]
    chunks = chunk_crud.replace(file_id, [{"content": "document", "start_line": 1, "end_line": 1}])
    database.vector_create("org/model", [{"chunk_id": chunks[0].id, "vector": [1.0, 0.0]}])

    response = client.request("DELETE", "/files/", json=[file_id])

    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": 1}
    assert client.get(f"/files/{file_id}").status_code == 404
    assert chunk_crud.for_file(file_id) == []
    assert database.vector_count("org/model") == 0


def test_uploads_need_files_and_default_to_the_storage_root(client):
    at_root = client.post("/files/upload", files={"files": ("file.txt", b"data")})
    missing_files = client.post("/files/upload?dir=documents")

    assert at_root.status_code == 200 and at_root.json()[0]["relative_path"] == "file.txt"
    assert missing_files.status_code == 422 and missing_files.json()["error"]["code"] == "invalid_request"


def test_uploading_an_existing_name_keeps_both_files(client):
    first = client.post("/files/upload?dir=docs", files={"files": ("a.txt", b"one", "text/plain")}).json()[0]
    second = client.post("/files/upload?dir=docs", files={"files": ("a.txt", b"two", "text/plain")}).json()[0]
    third = client.post("/files/upload?dir=docs", files={"files": ("a.txt", b"three", "text/plain")}).json()[0]

    assert [first["relative_path"], second["relative_path"], third["relative_path"]] == ["docs/a.txt", "docs/a (1).txt", "docs/a (2).txt"]
    assert second["name"] == "a (1)"
    assert client.get(f"/files/{first['id']}/content").text == "one"
    assert client.get(f"/files/{second['id']}/content").text == "two"


def test_directories_are_listed_and_binary_content_is_refused(client):
    client.post("/files/directory?path=empty/inner")
    binary = client.post("/files/upload?dir=bin", files={"files": ("blob.bin", b"\xff\xfe\x00", "application/octet-stream")}).json()[0]

    assert client.get("/files/directories").json() == ["bin", "empty", "empty/inner"]
    assert binary["directory"] == "bin"
    assert client.get(f"/files/{binary['id']}/content").json()["error"]["code"] == "not_text"


def test_file_endpoint_reads_edits_renames_moves_and_downloads_file(client):
    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("report.txt", b"report", "text/plain")},
    )
    file_id = created.json()[0]["id"]

    content = client.get(f"/files/{file_id}/content")
    assert content.status_code == 200
    assert content.text == "report"

    edited = client.put(f"/files/{file_id}/content", json={"content": "updated"})
    assert edited.status_code == 200
    assert edited.json()["size"] == 7
    assert client.get(f"/files/{file_id}/content").text == "updated"

    moved = client.patch(f"/files/{file_id}", json={"name": "renamed", "dir": "archive"})
    assert moved.status_code == 200
    assert moved.json()["name"] == "renamed"
    assert moved.json()["path"].endswith("archive\\renamed.txt") or moved.json()["path"].endswith("archive/renamed.txt")

    download = client.get(f"/files/{file_id}/download")
    assert download.status_code == 200
    assert download.content == b"updated"
    assert "renamed.txt" in download.headers["content-disposition"]

def test_file_endpoint_rejects_parent_directory(client):
    response = client.post(
        "/files/upload?dir=../outside",
        files={"files": ("file.txt", b"data", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_path"


def test_deleting_multiple_files_batches_vectors_and_preserves_other_files(client, monkeypatch):
    from pathlib import Path
    from lazy_bird.crud import file_processing
    from lazy_bird.models.file_processing import FileProcessing

    files = client.post("/files/upload?dir=docs", files=[("files", (f"{name}.md", b"Text")) for name in "abc"]).json()
    chunks = [chunk_crud.replace(file["id"], [{"content": file["name"], "start_line": 1, "end_line": 1}])[0] for file in files]
    database.vector_create("org/model", [{"chunk_id": chunk.id, "vector": [1.0, 0.0]} for chunk in chunks])
    with database.db() as session:
        session.add_all([FileProcessing(file_id=file["id"], processor="chunking") for file in files])
        session.commit()
    calls = []
    delete = database.vector_delete
    monkeypatch.setattr(database, "vector_delete", lambda model, ids: calls.append((model, ids)) or delete(model, ids))

    response = client.request("DELETE", "/files/", json=[files[0]["id"], files[1]["id"], files[0]["id"], 9999])

    assert response.status_code == 200, response.text
    assert response.json() == {"deleted": 2}
    assert len(calls) == 1 and set(calls[0][1]) == {chunk.id for chunk in chunks[:2]}
    assert database.vector_count("org/model") == 1
    assert [item["id"] for item in client.get("/files/").json()] == [files[2]["id"]]
    assert all(not Path(file["path"]).exists() for file in files[:2])
    assert file_processing.rows_for([files[0]["id"]]) == {files[0]["id"]: []}
    assert client.delete("/files/all").json() == {"deleted": 1}
    assert database.vector_count("org/model") == 0


def test_directory_moves_update_nested_paths_and_directory_delete_removes_chunks(client):
    first = client.post("/files/upload?dir=docs", files={"files": ("a.md", b"first")}).json()[0]
    second = client.post("/files/upload?dir=docs/nested", files={"files": ("b.md", b"second")}).json()[0]
    for file in (first, second):
        chunk_crud.replace(file["id"], [{"content": "text", "start_line": 1, "end_line": 1}])

    moved = client.patch("/files/directory?source=docs&destination=archive")

    assert moved.status_code == 200, moved.text
    assert moved.json() == {"path": "archive"}
    assert client.get(f"/files/{second['id']}").json()["relative_path"] == "archive/nested/b.md"
    assert client.get(f"/files/{first['id']}/content").text == "first"
    assert client.delete("/files/directory?path=archive").status_code == 200
    assert client.get("/files/").json() == []
    assert all(chunk_crud.for_file(file["id"]) == [] for file in (first, second))
