from pathlib import Path

from lazy_bird import database
from lazy_bird.database import db
from lazy_bird.models.embedded import Embedded, EmbeddedVectorDatabase
from lazy_bird.models.file import File as FileORM
from lazy_bird.models.selected_model_embeding import SelectedModelEmbeding
from lazy_bird.models.vector_database import VectorDatabase
from lazy_bird.task_queue import enqueue_file, queued_file_ids
from lazy_bird.preferences import auto_embedding_enabled
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


def _with_embedding_details(session, files: list[FileORM]) -> list[FileOut]:
    if not files:
        return []

    file_ids = [file.id for file in files]
    embedded_rows = session.exec(
        select(Embedded).where(Embedded.file_id.in_(file_ids))
    ).all()
    embedded_by_file: dict[int, list[int]] = {file_id: [] for file_id in file_ids}
    embedded_ids: list[int] = []
    for embedded in embedded_rows:
        embedded_by_file[embedded.file_id].append(embedded.llm_model_id)
        embedded_ids.append(embedded.id)

    vector_by_file: dict[int, list[str]] = {file_id: [] for file_id in file_ids}
    if embedded_ids:
        links = session.exec(
            select(EmbeddedVectorDatabase).where(
                EmbeddedVectorDatabase.embedded_id.in_(embedded_ids)
            )
        ).all()
        vector_databases = {
            vector_database.id: vector_database.name
            for vector_database in session.exec(select(VectorDatabase)).all()
        }
        file_by_embedded = {embedded.id: embedded.file_id for embedded in embedded_rows}
        for link in links:
            file_id = file_by_embedded[link.embedded_id]
            vector_database_name = vector_databases.get(link.vector_database_id)
            if vector_database_name is not None:
                vector_by_file[file_id].append(vector_database_name)

    return [
        FileOut.model_validate(file).model_copy(
            update={
                "embedded_by": embedded_by_file[file.id],
                "vector_db": vector_by_file[file.id],
            }
        )
        for file in files
    ]


def files_requiring_embedding() -> list[int]:
    with db() as session:
        files = session.exec(
            select(FileORM).where(FileORM.status.in_(["pending", "done"]))
        ).all()
        pending_ids = {file.id for file in files if file.status == "pending"}
        done_files = [file for file in files if file.status == "done"]
        if not done_files:
            return sorted(pending_ids)

        selection = session.exec(select(SelectedModelEmbeding)).first()
        if selection is None:
            return sorted(pending_ids)

        vector_database = session.exec(
            select(VectorDatabase).where(
                VectorDatabase.name == database.config.selected_vector_database
            )
        ).first()
        if vector_database is None:
            return sorted(pending_ids | {file.id for file in done_files})

        done_ids = {file.id for file in done_files}
        embedded_rows = session.exec(
            select(Embedded).where(
                Embedded.file_id.in_(done_ids),
                Embedded.llm_model_id == selection.llm_model_id,
            )
        ).all()
        embedded_by_file = {embedded.file_id: embedded.id for embedded in embedded_rows}
        linked_embedded_ids = {
            link.embedded_id
            for link in session.exec(
                select(EmbeddedVectorDatabase).where(
                    EmbeddedVectorDatabase.embedded_id.in_(embedded_by_file.values()),
                    EmbeddedVectorDatabase.vector_database_id == vector_database.id,
                )
            ).all()
        }
        done_needing_embedding = {
            file_id
            for file_id in done_ids
            if file_id not in embedded_by_file
            or embedded_by_file[file_id] not in linked_embedded_ids
        }
        return sorted(pending_ids | done_needing_embedding)


def enqueue_files_requiring_embedding(file_ids: list[int] | None = None) -> list[int]:
    candidates = files_requiring_embedding() if file_ids is None else file_ids
    queued = queued_file_ids()
    enqueued = []
    for file_id in candidates:
        if file_id in queued:
            continue
        enqueue_file(file_id)
        queued.add(file_id)
        enqueued.append(file_id)
    return enqueued


def create_empty_directory(path: str) -> str:
    return create_directory(path)


def delete_empty_directory(path: str) -> str:
    with db() as session:
        directory_path = Path(delete_directory(path))
        files = session.exec(select(FileORM)).all()
        affected_files = []
        for file in files:
            try:
                Path(file.path).resolve().relative_to(directory_path)
            except ValueError:
                continue
            affected_files.append(file)

        for file in affected_files:
            embedded_rows = session.exec(
                select(Embedded).where(Embedded.file_id == file.id)
            ).all()
            for embedded in embedded_rows:
                links = session.exec(
                    select(EmbeddedVectorDatabase).where(
                        EmbeddedVectorDatabase.embedded_id == embedded.id
                    )
                ).all()
                for link in links:
                    session.delete(link)
                session.delete(embedded)
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

        downloaded_files = _with_embedding_details(session, downloaded_files)

    if auto_embedding_enabled():
        enqueue_files_requiring_embedding(file_ids)

    return downloaded_files

def get_all():
    with db() as session:
        statement = select(FileORM)
        files = session.exec(statement).all()
        return _with_embedding_details(session, files)


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
        return _with_embedding_details(session, [file])[0]


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
        return _with_embedding_details(session, [file])[0]


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
        return _with_embedding_details(session, [file])[0]


def update_status(id: int, status: str) -> bool:
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return False
        file.status = status
        session.add(file)
        session.commit()
        return True


def _delete_file_dependencies(session, file_id: int) -> None:
    embedded_rows = session.exec(
        select(Embedded).where(Embedded.file_id == file_id)
    ).all()
    for embedded in embedded_rows:
        links = session.exec(
            select(EmbeddedVectorDatabase).where(
                EmbeddedVectorDatabase.embedded_id == embedded.id
            )
        ).all()
        for link in links:
            session.delete(link)
        session.flush()
        session.delete(embedded)
        session.flush()  

def deletes(ids: list[int]):
    with db() as session:
        for id in ids:
            file = session.get(FileORM, id)
            if file:
                _delete_file_dependencies(session, file.id)
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
            _delete_file_dependencies(session, file.id)
            session.delete(file)
            path = Path(file.path)
            if path.exists():
                path.unlink()
        session.commit()
