from pathlib import Path

from lazy_bird.database import db
from lazy_bird.models.file import File as FileORM
from lazy_bird.task_queue import enqueue_file
from lazy_bird.preferences import auto_embedding_enabled
from lazy_bird.schemas.files import FileOut
from sqlmodel import select
from lazy_bird.storages import store_file
from fastapi import UploadFile

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
