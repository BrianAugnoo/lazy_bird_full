from pathlib import Path

import pytest

import lazy_bird.chuncker as chuncker_module
from lazy_bird.chuncker import ChunckerError, UnsupportedFormatError, chunck
from lazy_bird.errors import NotFoundError
from lazy_bird.models.file import File


def create_file(db_session_factory, path: Path, extension: str) -> int:
    with db_session_factory() as session:
        file = File(name=path.stem, path=str(path), extension=extension, size=path.stat().st_size)
        session.add(file)
        session.commit()
        session.refresh(file)
        return file.id


@pytest.mark.anyio
async def test_unknown_extensions_are_unsupported(crud_database, tmp_path: Path):
    path = tmp_path / "notes.xyz"
    path.write_text("content", encoding="utf-8")

    with pytest.raises(UnsupportedFormatError) as error:
        await chunck(create_file(crud_database, path, ".xyz"))

    assert error.value.code == "unsupported_format"
    assert ".md" in error.value.message


@pytest.mark.anyio
async def test_markdown_files_are_chunked_without_any_embedding_model(crud_database, tmp_path: Path):
    path = tmp_path / "notes.md"
    path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")

    records = await chunck(create_file(crud_database, path, ".md"))

    assert [record["content"] for record in records] == ["First paragraph.", "Second paragraph."]


@pytest.mark.anyio
async def test_chunks_respect_the_chunking_preference_budget(crud_database, tmp_path: Path, monkeypatch):
    path = tmp_path / "notes.md"
    path.write_text("one two three four five six seven eight nine ten", encoding="utf-8")
    monkeypatch.setattr(chuncker_module, "chunking_max_tokens", lambda: 4)

    records = await chunck(create_file(crud_database, path, ".md"))

    assert len(records) > 1
    assert all(record["token_count"] <= 4 for record in records)


@pytest.mark.anyio
async def test_chunker_failures_are_reported_as_chunking_errors(crud_database, tmp_path: Path, monkeypatch):
    path = tmp_path / "notes.md"
    path.write_text("content", encoding="utf-8")
    monkeypatch.setattr(chuncker_module, "chunking_max_tokens", lambda: 1)

    with pytest.raises(ChunckerError):
        await chunck(create_file(crud_database, path, ".md"))


@pytest.mark.anyio
async def test_missing_files_are_not_found(crud_database):
    with pytest.raises(NotFoundError):
        await chunck(404)
