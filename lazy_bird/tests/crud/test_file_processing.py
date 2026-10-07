import pytest

from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.tasks.default.files import process_file
from lazy_bird.models.file import File


def create_markdown(crud_database, tmp_path, text: str) -> int:
    path = tmp_path / "notes.md"
    path.write_text(text, encoding="utf-8")
    with crud_database() as session:
        file = File(name="notes", path=str(path), extension=".md", size=path.stat().st_size)
        session.add(file)
        session.commit()
        return file.id


def test_processing_stores_chunks_and_their_vectors(crud_database, fake_embedding, tmp_path):
    file_id = create_markdown(crud_database, tmp_path, "Alpha paragraph.\n\nBeta paragraph.")

    result = process_file.run(file_id=file_id)

    chunks = chunk_crud.for_file(file_id)
    assert result == {"file_id": file_id, "chunks": 2, "model": "fake/space-4"}
    assert [chunk.content for chunk in chunks] == ["Alpha paragraph.", "Beta paragraph."]
    assert database.vector_count("fake/space-4", [chunk.id for chunk in chunks]) == 2
    assert file_crud.get(file_id).status == "done"


def test_processing_again_replaces_chunks_and_vectors(crud_database, fake_embedding, tmp_path):
    file_id = create_markdown(crud_database, tmp_path, "One.\n\nTwo.\n\nThree.")
    process_file.run(file_id=file_id)
    (tmp_path / "notes.md").write_text("Only one now.", encoding="utf-8")

    process_file.run(file_id=file_id)

    assert [chunk.content for chunk in chunk_crud.for_file(file_id)] == ["Only one now."]
    assert database.vector_count("fake/space-4") == 1


def test_processing_without_embedding_preset_marks_an_embedding_error(crud_database, tmp_path):
    file_id = create_markdown(crud_database, tmp_path, "Text.")

    with pytest.raises(Exception):
        process_file.run(file_id=file_id)

    assert file_crud.get(file_id).status == "embedding-error"


def test_done_files_without_vectors_require_embedding(crud_database, fake_embedding, tmp_path):
    file_id = create_markdown(crud_database, tmp_path, "Text.")
    process_file.run(file_id=file_id)
    assert file_crud.files_requiring_embedding() == []

    database.vector_drop("fake/space-4")

    assert file_crud.files_requiring_embedding() == [file_id]
