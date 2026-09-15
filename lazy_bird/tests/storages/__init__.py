from pathlib import Path

import pytest

import lazy_bird.storages as storage


def test_store_file_writes_nested_file_and_returns_metadata(storage_root: Path, upload_file_factory):
    uploaded = upload_file_factory("Report.PDF", b"pdf-content", "application/pdf")

    result = storage.store_file("documents/2026", uploaded)

    assert result == {
        "name": "Report",
        "path": str(storage_root / "documents" / "2026" / "Report.PDF"),
        "extension": ".pdf",
        "size": 11,
    }
    assert (storage_root / "documents" / "2026" / "Report.PDF").read_bytes() == b"pdf-content"


def test_store_file_removes_path_from_client_filename(storage_root: Path, upload_file_factory):
    uploaded = upload_file_factory("../../outside.txt", b"safe")

    result = storage.store_file("documents", uploaded)

    assert result["name"] == "outside"
    assert Path(result["path"]).parent == storage_root / "documents"
    assert (storage_root / "documents" / "outside.txt").exists()


@pytest.mark.parametrize("directory", ["../outside", "/absolute/path"])
def test_store_file_rejects_unsafe_destination(directory, upload_file_factory):
    with pytest.raises(ValueError, match="Invalid destination directory"):
        storage.store_file(directory, upload_file_factory())


@pytest.mark.xfail(reason="Windows path separators are not normalized on POSIX", strict=True)
def test_store_file_rejects_windows_parent_directory(storage_root, upload_file_factory):
    with pytest.raises(ValueError, match="Invalid destination directory"):
        storage.store_file(r"..\outside", upload_file_factory())


@pytest.mark.parametrize("filename", [None, "", "."])
def test_store_file_rejects_empty_filename(storage_root, upload_file_factory, filename):
    with pytest.raises(ValueError, match="Invalid file name"):
        storage.store_file("documents", upload_file_factory(filename))


def test_store_file_wraps_disk_errors(storage_root, upload_file_factory, monkeypatch):
    def fail_copy(source, destination):
        raise OSError("disk full")

    monkeypatch.setattr(storage.shutil, "copyfileobj", fail_copy)

    with pytest.raises(RuntimeError, match="Failed to store file document.txt: disk full"):
        storage.store_file("documents", upload_file_factory())
