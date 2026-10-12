"""Chunks of files, stored in SQL; their vectors live in the vector database.

Whenever chunks disappear (re-chunking, file deletion), their vectors are deleted
from every model table first, so a vector never points to a missing chunk.
"""

from itertools import batched

from sqlalchemy import delete, func, insert
from sqlmodel import select

from lazy_bird import database
from lazy_bird.database import db
from lazy_bird.errors import NotFoundError
from lazy_bird.models.chunk import Chunk
from lazy_bird.schemas.chunk import ChunkIn, ChunkOut

ID_BATCH_SIZE = 500  # Stay below SQLite's bind-parameter limit, including older databases.


def ids_for_files(file_ids: list[int]) -> list[int]:
    """Chunk ids for a file filter, without one SQL round trip per file."""
    ids = []
    with db() as session:
        for batch in batched(dict.fromkeys(file_ids), ID_BATCH_SIZE):
            ids.extend(session.exec(select(Chunk.id).where(Chunk.file_id.in_(batch))).all())
    return ids


def ids_for_file(file_id: int) -> list[int]:
    with db() as session:
        return list(session.exec(select(Chunk.id).where(Chunk.file_id == file_id).order_by(Chunk.position)).all())


def for_file(file_id: int) -> list[ChunkOut]:
    with db() as session:
        rows = session.exec(select(Chunk).where(Chunk.file_id == file_id).order_by(Chunk.position)).all()
        return [ChunkOut.model_validate(row) for row in rows]


def get(chunk_id: int) -> ChunkOut:
    with db() as session:
        row = session.get(Chunk, chunk_id)
        if row is None:
            raise NotFoundError("Chunk", chunk_id)
        return ChunkOut.model_validate(row)


def get_many(chunk_ids: list[int]) -> dict[int, ChunkOut]:
    if not chunk_ids:
        return {}
    found = {}
    with db() as session:
        for batch in batched(dict.fromkeys(chunk_ids), ID_BATCH_SIZE):
            rows = session.exec(select(Chunk).where(Chunk.id.in_(batch))).all()
            found.update((row.id, ChunkOut.model_validate(row)) for row in rows)
    return found


def counts(file_ids: list[int]) -> dict[int, int]:
    """Number of chunks per file."""
    if not file_ids:
        return {}
    found = {}
    with db() as session:
        for batch in batched(dict.fromkeys(file_ids), ID_BATCH_SIZE):
            found.update(session.exec(
                select(Chunk.file_id, func.count()).where(Chunk.file_id.in_(batch)).group_by(Chunk.file_id)
            ).all())
    return {file_id: found.get(file_id, 0) for file_id in file_ids}


def delete_for_file(file_id: int) -> int:
    """Delete the chunks of a file and their vectors; return how many chunks were deleted."""
    chunk_ids = ids_for_file(file_id)
    database.vector_delete_chunks(chunk_ids)
    with db() as session:
        session.execute(delete(Chunk).where(Chunk.file_id == file_id))
        session.commit()
    return len(chunk_ids)


def replace(file_id: int, chunks: list[ChunkIn | dict]) -> list[ChunkOut]:
    """Replace every chunk of a file (and drop the vectors of the old ones)."""
    parsed = [chunk if isinstance(chunk, ChunkIn) else ChunkIn.model_validate(chunk) for chunk in chunks]
    database.vector_delete_chunks(ids_for_file(file_id))
    with db() as session:
        session.execute(delete(Chunk).where(Chunk.file_id == file_id))
        if parsed:
            records = [
                Chunk(file_id=file_id, position=position, **chunk.model_dump()).model_dump(exclude={"id"})
                for position, chunk in enumerate(parsed)
            ]
            # Core executemany inserts every row without fetching generated ids individually.
            session.execute(insert(Chunk.__table__), records)
        rows = session.exec(select(Chunk).where(Chunk.file_id == file_id).order_by(Chunk.position)).all()
        result = [ChunkOut.model_validate(row) for row in rows]
        session.commit()
        return result
