from pathlib import Path

import pytest

import lazy_bird.chuncker as chuncker_module
from lazy_bird.chuncker import ChunckerError, UnsupportedFormatError, chunck
from lazy_bird.models.file import File


def create_file(db_session_factory, path: Path, extension: str) -> int:
    with db_session_factory() as session:
        file = File(name=path.stem, path=str(path), extension=extension, size=path.stat().st_size)
        session.add(file)
        session.commit()
        session.refresh(file)
        return file.id


@pytest.mark.anyio
async def test_chunck_marks_unknown_extension_as_format_error(crud_database, tmp_path: Path):
    path = tmp_path / "notes.xyz"
    path.write_text("content", encoding="utf-8")
    file_id = create_file(crud_database, path, ".xyz")

    error = await chunck(file_id)

    with crud_database() as session:
        assert isinstance(error, UnsupportedFormatError)
        assert session.get(File, file_id).status == "format-error"


@pytest.mark.anyio
async def test_chunck_creates_markdown_chunks_without_any_embedding_model(crud_database, tmp_path: Path):
    path = tmp_path / "notes.md"
    path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
    file_id = create_file(crud_database, path, ".md")

    records = await chunck(file_id)

    with crud_database() as session:
        assert [record["content"] for record in records] == ["First paragraph.", "Second paragraph."]
        assert session.get(File, file_id).status == "processing"


@pytest.mark.anyio
async def test_chunck_splits_with_the_chunking_preference_budget(crud_database, tmp_path: Path, monkeypatch):
    path = tmp_path / "notes.md"
    path.write_text("one two three four five six seven eight nine ten", encoding="utf-8")
    file_id = create_file(crud_database, path, ".md")
    monkeypatch.setattr(chuncker_module, "chunking_max_tokens", lambda: 4)

    records = await chunck(file_id)

    assert len(records) > 1
    assert all(record["token_count"] <= 4 for record in records)


@pytest.mark.anyio
async def test_chunck_marks_processing_failure(crud_database, tmp_path: Path, monkeypatch):
    path = tmp_path / "notes.md"
    path.write_text("content", encoding="utf-8")
    file_id = create_file(crud_database, path, ".md")
    monkeypatch.setattr(chuncker_module, "chunking_max_tokens", lambda: 1)

    error = await chunck(file_id)

    with crud_database() as session:
        assert isinstance(error, Exception)
        assert session.get(File, file_id).status == "chunck-error"


@pytest.mark.anyio
async def test_chunck_reports_missing_file(crud_database):
    assert isinstance(await chunck(404), ChunckerError)
