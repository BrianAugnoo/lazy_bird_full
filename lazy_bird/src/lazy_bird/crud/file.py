from pathlib import Path

from lazy_bird.database import db
from lazy_bird.models.file import File as FileORM
from lazy_bird.task_queue import enqueue_file
from lazy_bird.preferences import auto_embedding_enabled
from lazy_bird.schemas.files import FileOut
from sqlmodel import select
from lazy_bird.storages import store_file
from lazy_bird.storages import read_file, rename_or_move_file, write_file
from fastapi import UploadFile
import mimetypes

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
            downloaded_files.append(FileOut.model_validate(file_record))
            file_ids.append(file_record.id)
        session.commit()

    if auto_embedding_enabled():
        for file_id in file_ids:
            enqueue_file(file_id)

    return downloaded_files

def get_all():
    with db() as session:
        statement = select(FileORM)
        files = session.exec(statement).all()
        return [FileOut.model_validate(file) for file in files]


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
        return FileOut.model_validate(file)


def get(id: int):
    with db() as session:
        return session.get(FileORM, id)


def content(id: int):
    with db() as session:
        file = session.get(FileORM, id)
        if file is None:
            return None
        return file, read_file(file.path)


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
        return FileOut.model_validate(file)


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
        return FileOut.model_validate(file)


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
            session.delete(file)
            path = Path(file.path)
            if path.exists():
                path.unlink()
        session.commit()
