from pathlib import Path

from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.database import db
from lazy_bird.models.file import File as FileORM
from lazy_bird.preferences import auto_embedding_enabled
from lazy_bird.errors import AppError
from lazy_bird.schemas.files import FileOut
from sqlmodel import select
from lazy_bird.storages import (
    create_directory,
    delete_directory,
    move_directory as move_storage_directory,
    store_file,
)
from lazy_bird.storages import read_file, rename_or_move_file, write_file
from fastapi import UploadFile
import mimetypes


def _outputs(files: list[FileORM]) -> list[FileOut]:
    chunk_counts = chunk_crud.counts([file.id for file in files])
    return [
        FileOut.model_validate(file).model_copy(update={"chunk_count": chunk_counts.get(file.id, 0)})
        for file in files
    ]


def _default_vector_space() -> str | None:
    """Vector table of the default embedding preset, if it is usable."""
    from lazy_bird.embedding import engine_family, vector_space

    try:
        return vector_space(engine_family.resolve())
    except AppError:
        return None


def _missing_vectors(model_name: str, file_id: int) -> bool:
    chunk_ids = chunk_crud.ids_for_file(file_id)
    return bool(chunk_ids) and database.vector_count(model_name, chunk_ids) < len(chunk_ids)


def files_requiring_embedding() -> list[int]:
    """Pending files, plus processed files lacking vectors in the default model table."""
    with db() as session:
        files = session.exec(select(FileORM).where(FileORM.status.in_(["pending", "done"]))).all()
    pending_ids = {file.id for file in files if file.status == "pending"}
    done_ids = [file.id for file in files if file.status == "done"]
    model_name = _default_vector_space() if done_ids else None
    if model_name is None:
        return sorted(pending_ids)
    return sorted(pending_ids | {file_id for file_id in done_ids if _missing_vectors(model_name, file_id)})


def enqueue_file(file_id: int):
    """Queue the processing task of a file (an already active one is reused)."""
    from lazy_bird.tasks.default.files import process_file

    file = get(file_id)
    title = f"Process {file.name}{file.extension}" if file else None
    return process_file.submit(file_id=file_id, title=title, dedupe_key=f"files.process:{file_id}")


def enqueue_files_requiring_embedding(file_ids: list[int] | None = None) -> list[int]:
    candidates = files_requiring_embedding() if file_ids is None else file_ids
    for file_id in candidates:
        enqueue_file(file_id)
    return list(candidates)


def create_empty_directory(path: str) -> str:
    return create_directory(path)


def delete_empty_directory(path: str) -> str:
    directory_path = Path(delete_directory(path))
    with db() as session:
        files = session.exec(select(FileORM)).all()
        affected = [file for file in files if Path(file.path).resolve().is_relative_to(directory_path)]
        for file in affected:
            chunk_crud.delete_for_file(file.id)
            session.delete(file)
        session.commit()
    return str(directory_path)


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
    return str(destination_root)

async def creates(dir: str, files: list[UploadFile]):
    downloaded_files = []
    file_ids = []

    with db() as session:
        for file in files:
            try:
                file_info = store_file(dir, file)
            finally:
                await file.close()
            file_record = FileORM(**file_info)
            session.add(file_record)
            session.flush()
            session.refresh(file_record)
            downloaded_files.append(file_record)
            file_ids.append(file_record.id)
        session.commit()

        downloaded_files = _outputs(downloaded_files)

    if auto_embedding_enabled():
        enqueue_files_requiring_embedding(file_ids)

    return downloaded_files

def get_all():
    with db() as session:
        statement = select(FileORM)
        files = session.exec(statement).all()
        return _outputs(files)


def get_processing_status() -> list[dict]:
    with db() as session:
        statement = select(FileORM).order_by(FileORM.id)
        files = session.exec(statement).all()
        return [
            {
                "id": file.id,
                "name": f"{file.name}{file.extension}",
                "status": {
                    "pending": "queued",
                    "processing": "processing",
                    "done": "finished",
                }.get(file.status, "failed"),
                "detail": file.status,
            }
            for file in files
        ]

def find(id: int):
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return None
        return _outputs([file])[0]


def get(id: int):
    with db() as session:
        return session.get(FileORM, id)


def content(id: int):
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return None
        return file, read_file(file.path)


def full(id: int):
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return None
        return (
            read_file(file.path),
            f"{file.name}{file.extension}",
            mimetypes.guess_type(file.path)[0],
        )


def download_info(id: int):
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return None
        return file.path, f"{file.name}{file.extension}", mimetypes.guess_type(file.path)[0]


def update_content(id: int, value: str):
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return None
        file.size = write_file(file.path, value)
        file.status = "pending"
        session.add(file)
        session.commit()
        session.refresh(file)
        return _outputs([file])[0]


def update_file(id: int, name: str | None = None, dir: str | None = None):
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return None
        if name is not None or dir is not None:
            file.path = rename_or_move_file(file.path, name=name, dir=dir)
            if name is not None:
                file.name = Path(file.path).stem
            session.add(file)
            session.commit()
            session.refresh(file)
        return _outputs([file])[0]


def update_status(id: int, status: str) -> bool:
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return False
        file.status = status
        session.add(file)
        session.commit()
        return True


def deletes(ids: list[int]):
    with db() as session:
        for id in ids:
            file = session.get(FileORM, id)
            if file:
                chunk_crud.delete_for_file(file.id)
                session.delete(file)
                path = Path(file.path)
                if path.exists():
                    path.unlink()
        session.commit()

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
