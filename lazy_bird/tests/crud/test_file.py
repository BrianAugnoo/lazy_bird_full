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


@pytest.mark.anyio
async def test_creates_does_not_enqueue_when_auto_embedding_is_disabled(
    crud_database,
    storage_root: Path,
    upload_file_factory,
    monkeypatch,
):
    queued = []
    monkeypatch.setattr(file_crud, "auto_embedding_enabled", lambda: False)
    monkeypatch.setattr(file_crud, "enqueue_file", queued.append)

    await file_crud.creates("documents", [upload_file_factory("manual.txt", b"content")])

    assert queued == []
    assert len(file_crud.get_all()) == 1


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

    assert found.model_dump() == {
        "name": "report",
        "size": 42,
        "extension": ".pdf",
        "path": "/tmp/report.pdf",
        "status": "pending",
    }


def test_find_returns_none_for_unknown_id(crud_database):
    assert file_crud.find(9999) is None


def test_get_all_returns_empty_list(crud_database):
    assert file_crud.get_all() == []
