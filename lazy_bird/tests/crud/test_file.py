from pathlib import Path

import pytest

import lazy_bird.crud.file as file_crud


@pytest.mark.anyio
async def test_creates_stores_and_persists_each_file(
    crud_database,
    storage_root: Path,
    upload_file_factory,
):
    first = upload_file_factory("first.TXT", b"first")
    second = upload_file_factory("second.pdf", b"second", "application/pdf")

    records = await file_crud.creates("documents", [first, second])

    assert [record.name for record in records] == ["first", "second"]
    assert [record.extension for record in records] == [".txt", ".pdf"]
    assert [record.size for record in records] == [5, 6]
    assert (storage_root / "documents" / "first.TXT").read_bytes() == b"first"
    assert (storage_root / "documents" / "second.pdf").read_bytes() == b"second"
    assert first.file.closed
    assert second.file.closed
    assert len(file_crud.get_all()) == 2
    assert records[0].content_hash == "a7937b64b8caa58f03721bb6bacf5c78cb235febe0e70b1b84cd99541461a08e"


@pytest.mark.anyio
async def test_creates_does_not_process_when_auto_embedding_is_disabled(
    crud_database,
    storage_root: Path,
    upload_file_factory,
    monkeypatch,
):
    monkeypatch.setattr(file_crud, "auto_embedding_enabled", lambda: False)

    [created] = await file_crud.creates("documents", [upload_file_factory("manual.txt", b"content")])

    assert created.state == "new" and created.processing == []


@pytest.mark.anyio
async def test_creates_closes_upload_when_storage_fails(
    crud_database,
    upload_file_factory,
    monkeypatch,
):
    upload = upload_file_factory("broken.txt", b"content")
    monkeypatch.setattr(file_crud, "store_file", lambda directory, file: (_ for _ in ()).throw(OSError("disk full")))

    with pytest.raises(OSError, match="disk full"):
        await file_crud.creates("documents", [upload])

    assert upload.file.closed
    assert file_crud.get_all() == []


def test_find_returns_persisted_file(crud_database, db_session_factory):
    from lazy_bird.models.file import File

    with db_session_factory() as session:
        record = File(name="report", path="/tmp/report.pdf", extension=".pdf", size=42)
        session.add(record)
        session.commit()
        session.refresh(record)
        record_id = record.id

    found = file_crud.find(record_id)

    assert (found.id, found.name, found.extension, found.size) == (record_id, "report", ".pdf", 42)
    assert found.state == "new" and found.processing == [] and found.chunk_count == 0


def test_find_returns_none_for_unknown_id(crud_database):
    assert file_crud.find(9999) is None


def test_get_all_returns_empty_list(crud_database):
    assert file_crud.get_all() == []


@pytest.mark.anyio
async def test_upload_disk_work_does_not_block_the_event_loop(crud_database, storage_root, upload_file_factory, monkeypatch):
    import asyncio
    import threading

    loop = asyncio.get_running_loop()
    real_store = file_crud.store_file

    def store(directory, file):
        responded = threading.Event()
        loop.call_soon_threadsafe(responded.set)
        assert responded.wait(2), "Upload disk work blocked the server event loop"
        return real_store(directory, file)

    monkeypatch.setattr(file_crud, "store_file", store)
    [created] = await file_crud.creates("docs", [upload_file_factory("note.md", b"Text")])
    assert created.name == "note"


@pytest.mark.anyio
async def test_unchanged_missing_files_are_not_written_on_every_scan(crud_database, storage_root, upload_file_factory, sql_activity):
    [created] = await file_crud.creates("docs", [upload_file_factory("note.md", b"Text")])
    Path(created.path).unlink()
    assert file_crud.detect_changes()["missing"] == [created.id]
    sql_activity["commits"].clear()
    assert file_crud.detect_changes()["missing"] == [created.id]
    assert sql_activity["commits"] == []
