from fastapi import APIRouter

from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.errors import NotFoundError
from lazy_bird.schemas.chunk import ChunkOut

router = APIRouter(tags=["chunks"])


@router.get("/files/{file_id}/chunks", response_model=list[ChunkOut])
def list_file_chunks(file_id: int):
    if file_crud.get(file_id) is None:
        raise NotFoundError("File", file_id)
    return chunk_crud.for_file(file_id)


@router.get("/chunks/{chunk_id}", response_model=ChunkOut)
def get_chunk(chunk_id: int):
    return chunk_crud.get(chunk_id)
