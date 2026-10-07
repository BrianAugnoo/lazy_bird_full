import os
import time

import pytest

from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.crud import file_processing
from lazy_bird.crud.file_processing import InvalidProcessingTransitionError
from lazy_bird.models.file_processing import FileProcessing
from tests.conftest import wait_until


@pytest.fixture
def pipeline(crud_database, storage_root, fake_embedding, running_scheduler, monkeypatch):
    """Auto-embedding on, a running scheduler and the fake embedding preset."""
    monkeypatch.setattr(file_crud, "auto_embedding_enabled", lambda: True)
    monkeypatch.setattr("lazy_bird.preferences.auto_embedding_enabled", lambda: True)
    return running_scheduler


async def upload(upload_file_factory, name: str, content: bytes) -> int:
    [created] = await file_crud.creates("docs", [upload_file_factory(name, content, "text/markdown")])
    return created.id


def states(file_id: int) -> dict[tuple[str, str], str]:
    return {(row.processor, row.target): row.state for row in file_crud.find(file_id).processing}


def wait_for_state(file_id: int, state: str):
    return wait_until(
        lambda: (found := file_crud.find(file_id)).state == state and found,
        message=f"file {file_id} never became {state}: {states(file_id)}",
    )


@pytest.mark.anyio
async def test_an_uploaded_file_is_chunked_then_embedded(pipeline, upload_file_factory):
    file_id = await upload(upload_file_factory, "notes.md", b"Alpha paragraph.\n\nBeta paragraph.")

    ready = wait_for_state(file_id, "ready")

    assert states(file_id) == {("chunking", ""): "done", ("embedding", "fake/space-4"): "done"}
    assert all(row.content_hash == ready.content_hash for row in ready.processing)
    assert ready.chunk_count == 2
    assert database.vector_count("fake/space-4") == 2


@pytest.mark.anyio
async def test_unsupported_formats_stop_the_pipeline_without_error(pipeline, upload_file_factory):
    file_id = await upload(upload_file_factory, "image.xyz", b"\x00\x01")

    wait_for_state(file_id, "unsupported")

    assert states(file_id) == {("chunking", ""): "unsupported", ("embedding", "fake/space-4"): "unsupported"}


@pytest.mark.anyio
async def test_editing_a_file_recomputes_everything_from_the_new_content(pipeline, upload_file_factory):
    file_id = await upload(upload_file_factory, "notes.md", b"One.\n\nTwo.\n\nThree.")
    first = wait_for_state(file_id, "ready")

    file_crud.update_content(file_id, "Only one now.")

    second = wait_until(lambda: (found := file_crud.find(file_id)).state == "ready" and found.content_hash != first.content_hash and found)
    assert [chunk.content for chunk in chunk_crud.for_file(file_id)] == ["Only one now."]
    assert all(row.content_hash == second.content_hash for row in second.processing)
    assert database.vector_count("fake/space-4") == 1


@pytest.mark.anyio
async def test_a_change_on_disk_is_detected_by_the_scan(pipeline, upload_file_factory):
    file_id = await upload(upload_file_factory, "notes.md", b"Before.")
    before = wait_for_state(file_id, "ready")
    path = file_crud.get(file_id).path
    with open(path, "w", encoding="utf-8") as stream:
        stream.write("After the edit.")
    os.utime(path, (time.time() + 5, time.time() + 5))

    report = file_crud.detect_changes()

    assert report["changed"] == [file_id]
    after = wait_until(lambda: (found := file_crud.find(file_id)).state == "ready" and found.content_hash != before.content_hash and found)
    assert [chunk.content for chunk in chunk_crud.for_file(file_id)] == ["After the edit."]
    assert after.processing[0].content_hash == after.content_hash


@pytest.mark.anyio
async def test_a_file_removed_from_disk_is_reported_missing(pipeline, upload_file_factory):
    file_id = await upload(upload_file_factory, "notes.md", b"Text.")
    wait_for_state(file_id, "ready")
    os.remove(file_crud.get(file_id).path)

    assert file_crud.detect_changes()["missing"] == [file_id]
    assert file_crud.find(file_id).state == "missing"


@pytest.mark.anyio
async def test_a_cancelled_processing_stays_cancelled_until_requested_again(pipeline, upload_file_factory, monkeypatch):
    import lazy_bird.chunker as chunker

    original = chunker.chunk_file

    async def slow_chunk_file(file_id):
        time.sleep(0.5)
        return await original(file_id)

    monkeypatch.setattr(chunker, "chunk_file", slow_chunk_file)
    file_id = await upload(upload_file_factory, "notes.md", b"Text.")
    chunking = wait_until(lambda: next((row for row in file_crud.find(file_id).processing if row.state == "running"), None))

    pipeline.cancel(chunking.task_id)

    wait_until(lambda: states(file_id)[("chunking", "")] == "cancelled")
    file_processing.ensure(file_id)
    assert states(file_id)[("chunking", "")] == "cancelled"
    assert file_crud.find(file_id).state == "pending"

    file_crud.reprocess(file_id, "chunking")
    wait_for_state(file_id, "ready")


@pytest.mark.anyio
async def test_a_new_default_preset_embeds_every_file_with_its_model(pipeline, upload_file_factory):
    from lazy_bird.embedding import engine_family

    file_id = await upload(upload_file_factory, "notes.md", b"Text.")
    wait_for_state(file_id, "ready")
    engine = next(engine for engine in engine_family.engines() if engine.name == "fake-embedding")

    engine_family.create_preset("wide", engine.id, {"dimension": 8}, default=True)

    wait_until(lambda: states(file_id).get(("embedding", "fake/space-8")) == "done")
    assert states(file_id)[("embedding", "fake/space-4")] == "done"


@pytest.mark.anyio
async def test_dropping_a_vector_table_forgets_its_embeddings(client, pipeline, upload_file_factory, monkeypatch):
    file_id = await upload(upload_file_factory, "notes.md", b"Text.")
    wait_for_state(file_id, "ready")
    monkeypatch.setattr("lazy_bird.preferences.auto_embedding_enabled", lambda: False)

    assert client.delete("/databases/vector/tables/fake/space-4").status_code == 204

    assert ("embedding", "fake/space-4") not in states(file_id)


@pytest.mark.anyio
async def test_dropping_the_default_model_vectors_embeds_files_again(client, pipeline, upload_file_factory):
    file_id = await upload(upload_file_factory, "notes.md", b"Text.")
    wait_for_state(file_id, "ready")

    assert client.delete("/databases/vector/tables/fake/space-4").status_code == 204

    wait_until(lambda: states(file_id).get(("embedding", "fake/space-4")) == "done", message="not embedded again")
    assert database.vector_count("fake/space-4") > 0


@pytest.mark.anyio
async def test_switching_vector_database_outdates_embeddings(pipeline, upload_file_factory, monkeypatch):
    monkeypatch.setattr("lazy_bird.preferences.auto_embedding_enabled", lambda: False)
    file_id = await upload(upload_file_factory, "notes.md", b"Text.")
    wait_for_state(file_id, "ready")

    file_processing.outdate_processor("embedding", "The vector database changed.")

    assert states(file_id)[("embedding", "fake/space-4")] == "outdated"
    assert file_crud.find(file_id).state == "outdated"


def test_illegal_transitions_are_refused():
    row = FileProcessing(file_id=1, processor="chunking", target="", state="done")

    with pytest.raises(InvalidProcessingTransitionError):
        file_processing._move(row, "running")
    assert file_processing._move(row, "outdated") is True
    assert file_processing._move(row, "outdated") is False


def test_without_auto_embedding_nothing_is_queued_on_upload(crud_database, storage_root, upload_file_factory, running_scheduler):
    import asyncio

    [created] = asyncio.run(file_crud.creates("docs", [upload_file_factory("notes.md", b"Text.", "text/markdown")]))

    assert created.state == "new"
    assert running_scheduler.tasks() == []
