"""Chunks of files, stored in SQL; their vectors live in the vector database.

Whenever chunks disappear (re-chunking, file deletion), their vectors are deleted
from every model table first, so a vector never points to a missing chunk.
"""

from collections import Counter

from sqlmodel import select

from lazy_bird import database
from lazy_bird.database import db
from lazy_bird.errors import NotFoundError
from lazy_bird.models.chunk import Chunk
from lazy_bird.schemas.chunk import ChunkIn, ChunkOut


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
    with db() as session:
        rows = session.exec(select(Chunk).where(Chunk.id.in_(chunk_ids))).all()
        return {row.id: ChunkOut.model_validate(row) for row in rows}


def counts(file_ids: list[int]) -> dict[int, int]:
    """Number of chunks per file."""
    if not file_ids:
        return {}
    with db() as session:
        found = Counter(session.exec(select(Chunk.file_id).where(Chunk.file_id.in_(file_ids))).all())
    return {file_id: found.get(file_id, 0) for file_id in file_ids}


def delete_for_file(file_id: int) -> int:
    """Delete the chunks of a file and their vectors; return how many chunks were deleted."""
    chunk_ids = ids_for_file(file_id)
    database.vector_delete_chunks(chunk_ids)
    with db() as session:
        for row in session.exec(select(Chunk).where(Chunk.file_id == file_id)).all():
            session.delete(row)
        session.commit()
    return len(chunk_ids)


def replace(file_id: int, chunks: list[ChunkIn | dict]) -> list[ChunkOut]:
    """Replace every chunk of a file (and drop the vectors of the old ones)."""
    parsed = [chunk if isinstance(chunk, ChunkIn) else ChunkIn.model_validate(chunk) for chunk in chunks]
    delete_for_file(file_id)
    with db() as session:
        rows = [Chunk(file_id=file_id, position=position, **chunk.model_dump()) for position, chunk in enumerate(parsed)]
        session.add_all(rows)
        session.commit()
        for row in rows:
            session.refresh(row)
        return [ChunkOut.model_validate(row) for row in rows]
