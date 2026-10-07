from loguru import logger

from lazy_bird import database
from lazy_bird.chuncker import chunck
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.embedding import embed_texts, engine_family, vector_space


async def process_file(file_id: int):
    """Chunk a file, store its chunks, then embed them with the default embedding preset."""
    logger.info("Starting file processing: file_id={}", file_id)
    if file_crud.get(file_id) is None:
        raise ValueError("File not found")

    chunks = await chunck(file_id)
    if isinstance(chunks, Exception):
        raise chunks
    try:
        stored = chunk_crud.replace(file_id, chunks)
        resolved = engine_family.resolve()
        model_name = vector_space(resolved)
        vectors = embed_texts([chunk.content for chunk in stored], resolved)
        if stored:
            database.vector_create(
                model_name, [{"chunk_id": chunk.id, "vector": vector} for chunk, vector in zip(stored, vectors, strict=True)]
            )
    except Exception:
        file_crud.update_status(file_id, "embedding-error")
        logger.exception("File processing failed: file_id={}", file_id)
        raise
    file_crud.update_status(file_id, "done")
    return {"file_id": file_id, "chunks_created": len(stored), "model": model_name}
