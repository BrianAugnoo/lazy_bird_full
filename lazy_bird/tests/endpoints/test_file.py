from lazy_bird.models.embedded import Embedded, EmbeddedVectorDatabase
from lazy_bird.models.llm_model import LLMModel
from lazy_bird.models.vector_database import VectorDatabase
from sqlmodel import select


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


def test_file_output_includes_embedding_and_vector_database_ids(client, crud_database):
    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("report.txt", b"report", "text/plain")},
    )
    file_id = created.json()[0]["id"]

    with crud_database() as session:
        first_vector_db = VectorDatabase(name="test-vector-a")
        second_vector_db = VectorDatabase(name="test-vector-b")
        llm_model = LLMModel(
            name="test-model",
            hf_path="test/model",
            local_path="test/model",
            dimension=3,
        )
        session.add_all([first_vector_db, second_vector_db, llm_model])
        session.flush()
        llm_model_id = llm_model.id
        first_vector_db_id = first_vector_db.id
        second_vector_db_id = second_vector_db.id
        embedded = Embedded(file_id=file_id, llm_model_id=llm_model.id)
        session.add(embedded)
        session.flush()
        session.add_all(
            [
                EmbeddedVectorDatabase(
                    embedded_id=embedded.id,
                    vector_database_id=first_vector_db.id,
                ),
                EmbeddedVectorDatabase(
                    embedded_id=embedded.id,
                    vector_database_id=second_vector_db.id,
                ),
            ]
        )
        session.commit()

    response = client.get(f"/files/{file_id}")

    assert response.status_code == 200
    assert response.json()["embedded_by"] == [llm_model_id]
    assert response.json()["vetor_db"] == [first_vector_db_id, second_vector_db_id]


def test_file_endpoint_returns_null_for_unknown_id(client):
    response = client.get("/files/9999")

    assert response.status_code == 200
    assert response.json() is None


def test_file_endpoint_deletes_file_with_embedding_dependencies(client, crud_database):
    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("embedded.md", b"# document", "text/markdown")},
    )
    file_id = created.json()[0]["id"]

    with crud_database() as session:
        llm_model = LLMModel(
            name="test-model",
            hf_path="test/model",
            local_path="test/model",
            dimension=3,
        )
        session.add(llm_model)
        session.flush()
        embedded = Embedded(file_id=file_id, llm_model_id=llm_model.id)
        session.add(embedded)
        session.flush()
        vector_database = VectorDatabase(name="test-vector")
        session.add(vector_database)
        session.flush()
        session.add(
            EmbeddedVectorDatabase(
                embedded_id=embedded.id,
                vector_database_id=vector_database.id,
            )
        )
        session.commit()

    response = client.request("DELETE", "/files/", json=[file_id])

    assert response.status_code == 200, response.text
    assert client.get(f"/files/{file_id}").json() is None
    with crud_database() as session:
        assert session.exec(select(Embedded).where(Embedded.file_id == file_id)).first() is None


def test_file_endpoint_requires_directory_and_files(client):
    missing_directory = client.post("/files/upload", files={"files": ("file.txt", b"data")})
    missing_files = client.post("/files/upload?dir=documents")

    assert missing_directory.status_code == 422
    assert missing_files.status_code == 422


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

    assert response.status_code == 400
