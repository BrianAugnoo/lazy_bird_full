from pathlib import Path

import pytest

from lazy_bird.chuncker import (
    ChunckerError,
    NoSelectedEmbeddingModelError,
    UnsupportedFormatError,
    chunck,
)
from lazy_bird.models.file import File
from lazy_bird.models.llm_model import LLMModel
from lazy_bird.models.selected_model_embeding import SelectedModelEmbeding


def prepare_queue(
    db_session_factory,
    path: Path,
    extension: str,
    selected_context=32,
    max_context_length=None,
    select_model=True,
):
    with db_session_factory() as session:
        file = File(
            name=path.stem,
            path=str(path),
            extension=extension,
            size=path.stat().st_size,
        )
        model = LLMModel(
            name="model",
            hf_path="owner/model",
            local_path="/tmp/model",
            dimension=384,
            max_context_length=max_context_length,
            selected_context=selected_context,
            formats=["safetensors"],
            selected_format="safetensors",
        )
        session.add(file)
        session.add(model)
        session.flush()
        if select_model:
            session.add(SelectedModelEmbeding(id=1, llm_model_id=model.id))
        session.commit()
        session.refresh(file)
        return file.id


@pytest.mark.anyio
async def test_chunck_marks_unknown_extension_and_removes_queue(
    crud_database,
    db_session_factory,
    tmp_path: Path,
):
    path = tmp_path / "notes.xyz"
    path.write_text("content", encoding="utf-8")
    file_id = prepare_queue(db_session_factory, path, ".xyz")

    error = await chunck(file_id)

    with db_session_factory() as session:
        assert isinstance(error, UnsupportedFormatError)
        assert session.get(File, file_id).status == "format-error"


@pytest.mark.anyio
async def test_chunck_keeps_pending_queue_when_no_model_is_selected(
    crud_database,
    db_session_factory,
    tmp_path: Path,
):
    path = tmp_path / "notes.md"
    path.write_text("content", encoding="utf-8")
    file_id = prepare_queue(
        db_session_factory,
        path,
        ".md",
        select_model=False,
    )

    error = await chunck(file_id)

    with db_session_factory() as session:
        assert isinstance(error, NoSelectedEmbeddingModelError)
        assert session.get(File, file_id).status == "pending"


@pytest.mark.anyio
async def test_chunck_creates_markdown_chunks_and_finishes_queue(
    crud_database,
    db_session_factory,
    tmp_path: Path,
):
    path = tmp_path / "notes.md"
    path.write_text("First paragraph.\n\nSecond paragraph.", encoding="utf-8")
    file_id = prepare_queue(db_session_factory, path, ".md")

    records = await chunck(file_id)

    with db_session_factory() as session:
        assert [record["content"] for record in records] == ["First paragraph.", "Second paragraph."]
        assert session.get(File, file_id).status == "processing"


@pytest.mark.anyio
async def test_chunck_uses_max_context_when_selected_context_is_empty(
    crud_database,
    db_session_factory,
    tmp_path: Path,
):
    path = tmp_path / "notes.md"
    path.write_text("A paragraph that can be chunked.", encoding="utf-8")
    file_id = prepare_queue(
        db_session_factory,
        path,
        ".md",
        selected_context=None,
        max_context_length=64,
    )

    records = await chunck(file_id)

    with db_session_factory() as session:
        assert [record["content"] for record in records] == ["A paragraph that can be chunked."]
        assert session.get(File, file_id).status == "processing"


@pytest.mark.anyio
async def test_chunck_marks_processing_failure_and_removes_queue(
    crud_database,
    db_session_factory,
    tmp_path: Path,
):
    path = tmp_path / "notes.md"
    path.write_text("content", encoding="utf-8")
    file_id = prepare_queue(db_session_factory, path, ".md", selected_context=None)

    error = await chunck(file_id)

    with db_session_factory() as session:
        assert isinstance(error, ChunckerError)
        assert session.get(File, file_id).status == "chunck-error"
