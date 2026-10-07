from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
import mimetypes

from fastapi import UploadFile
from sqlmodel import select

from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.crud import file_processing
from lazy_bird.database import db
from lazy_bird.models.file import File as FileORM
from lazy_bird.preferences import auto_embedding_enabled
from lazy_bird.errors import InvalidInputError, NotFoundError
from lazy_bird.schemas.files import FileOut
from lazy_bird.storages import (
    content_hash,
    create_directory,
    delete_directory,
    fingerprint,
    move_directory as move_storage_directory,
    read_file,
    relative_path,
    rename_or_move_file,
    store_file,
    write_file,
)


def _directory(relative: str) -> str:
    parent = Path(relative).parent.as_posix()
    return "" if parent == "." else parent


def _outputs(files: list[FileORM]) -> list[FileOut]:
    file_ids = [file.id for file in files]
    chunk_counts = chunk_crud.counts(file_ids)
    rows = file_processing.rows_for(file_ids)
    return [
        FileOut.model_validate(file).model_copy(
            update={
                "relative_path": relative_path(file.path),
                "directory": _directory(relative_path(file.path)),
                "chunk_count": chunk_counts.get(file.id, 0),
                "state": file_processing.summarize(file, rows.get(file.id, [])),
                "processing": [file_processing.to_out(row, file) for row in rows.get(file.id, [])],
            }
        )
        for file in files
    ]


def _refresh_identity(file: FileORM) -> bool:
    """Recompute size, modification time and hash from disk; return whether the content changed."""
    found = fingerprint(file.path)
    if found is None:
        file.missing = True
        return False
    previous = file.content_hash
    file.size, file.modified_at = found
    file.content_hash = content_hash(file.path)
    file.missing = False
    return previous is not None and previous != file.content_hash


def create_empty_directory(path: str) -> str:
    return relative_path(create_directory(path))


def remove_directory(path: str) -> str:
    """Delete a directory with every file it contains (and their chunks and vectors)."""
    directory_path = Path(delete_directory(path))
    with db() as session:
        files = session.exec(select(FileORM)).all()
        affected = [file for file in files if Path(file.path).resolve().is_relative_to(directory_path)]
        for file in affected:
            chunk_crud.delete_for_file(file.id)
            session.delete(file)
        session.commit()
    return relative_path(str(directory_path))


def move_directory(source: str, destination: str) -> str:
    source_path, destination_path = move_storage_directory(source, destination)
    source_root = Path(source_path)
    destination_root = Path(destination_path)
    with db() as session:
        files = session.exec(select(FileORM)).all()
        for file in files:
            file_path = Path(file.path)
            try:
                relative_path = file_path.resolve().relative_to(source_root)
            except ValueError:
                continue
            file.path = str(destination_root / relative_path)
            session.add(file)
        session.commit()
    return relative_path(str(destination_root))


async def creates(dir: str, files: list[UploadFile]):
    """Store uploaded files; a name already used in the directory gets a numbered suffix."""
    created = []
    with db() as session:
        for file in files:
            try:
                file_info = store_file(dir, file)
            finally:
                await file.close()
            record = FileORM(**file_info)
            _refresh_identity(record)
            session.add(record)
            session.flush()
            created.append(record)
        session.commit()
        file_ids = [record.id for record in created]

    if auto_embedding_enabled():
        for file_id in file_ids:
            file_processing.ensure(file_id)
    return [find(file_id) for file_id in file_ids]


def process(file_id: int) -> FileOut:
    """Queue whatever the file still needs (chunks, default embedding)."""
    file_processing.ensure(file_id)
    return get_out(file_id)


def reprocess(file_id: int, processor: str, target: str = "") -> FileOut:
    """Compute one processing of the file again, even if it is up to date."""
    file_processing.request(file_id, processor, target)
    return get_out(file_id)


def detect_changes(progress: Callable[[float], None] = lambda value: None) -> dict:
    """Compare every file with the disk; rehash changed ones and outdate their results."""
    with db() as session:
        file_ids = list(session.exec(select(FileORM.id)).all())
    changed, missing = [], []
    for index, file_id in enumerate(file_ids, start=1):
        outcome = _check_on_disk(file_id)
        if outcome == "changed":
            changed.append(file_id)
            file_processing.on_content_changed(file_id)
        elif outcome == "reappeared":
            file_processing.ensure(file_id, automatic=auto_embedding_enabled())
        elif outcome == "missing":
            missing.append(file_id)
        progress(index / len(file_ids))
    return {"checked": len(file_ids), "changed": changed, "missing": missing}


def _check_on_disk(file_id: int) -> str | None:
    """Return "changed", "reappeared", "missing" or None (nothing to do)."""
    with db() as session:
        file = session.get(FileORM, file_id)
        if file is None:
            return None
        found = fingerprint(file.path)
        if found is None:
            file.missing = True
            session.add(file)
            session.commit()
            return "missing"
        was_missing = file.missing
        stored = (file.size, _as_utc(file.modified_at))
        if not was_missing and file.content_hash is not None and stored == found:
            return None
        content_changed = _refresh_identity(file)
        session.add(file)
        session.commit()
    return "changed" if content_changed else "reappeared" if was_missing else None


def _as_utc(value: datetime | None) -> datetime | None:
    return value.replace(tzinfo=timezone.utc) if value is not None and value.tzinfo is None else value


def get_all():
    with db() as session:
        files = session.exec(select(FileORM).order_by(FileORM.id)).all()
    return _outputs(list(files))


def find(id: int):
    with db() as session:
        file = session.get(FileORM, id)
    return _outputs([file])[0] if file is not None else None


def get_out(id: int) -> FileOut:
    found = find(id)
    if found is None:
        raise NotFoundError("File", id)
    return found


def _require(session, id: int) -> FileORM:
    file = session.get(FileORM, id)
    if file is None:
        raise NotFoundError("File", id)
    return file


def get(id: int):
    with db() as session:
        return session.get(FileORM, id)


def text_content(id: int) -> str:
    """The content of a text file (422 for binary files)."""
    with db() as session:
        file = _require(session, id)
        data = read_file(file.path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise InvalidInputError("This file is not a UTF-8 text file; download it instead.", code="not_text") from error


def full(id: int):
    with db() as session:
        file = _require(session, id)
        return read_file(file.path), f"{file.name}{file.extension}", mimetypes.guess_type(file.path)[0]


def download_info(id: int):
    with db() as session:
        file = _require(session, id)
        return file.path, f"{file.name}{file.extension}", mimetypes.guess_type(file.path)[0]


def update_content(id: int, value: str) -> FileOut:
    with db() as session:
        file = _require(session, id)
        write_file(file.path, value)
        content_changed = _refresh_identity(file)
        session.add(file)
        session.commit()
    if content_changed:
        file_processing.on_content_changed(id)
    return get_out(id)


def update_file(id: int, name: str | None = None, dir: str | None = None) -> FileOut:
    with db() as session:
        file = _require(session, id)
        if name is not None or dir is not None:
            file.path = rename_or_move_file(file.path, name=name, dir=dir)
            if name is not None:
                file.name = Path(file.path).stem
            found = fingerprint(file.path)
            if found is not None:
                file.size, file.modified_at = found
            session.add(file)
            session.commit()
    return get_out(id)


def deletes(ids: list[int]) -> int:
    """Delete files (disk, chunks, vectors); unknown ids are ignored. Returns how many were deleted."""
    deleted = 0
    with db() as session:
        for id in ids:
            file = session.get(FileORM, id)
            if file:
                chunk_crud.delete_for_file(file.id)
                session.delete(file)
                Path(file.path).unlink(missing_ok=True)
                deleted += 1
        session.commit()
    return deleted


def delete_all():
    with db() as session:
        statement = select(FileORM)
        files = session.exec(statement).all()
        for file in files:
            chunk_crud.delete_for_file(file.id)
            session.delete(file)
            path = Path(file.path)
            if path.exists():
                path.unlink()
        session.commit()
