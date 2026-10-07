import logging

from lazy_bird import database
from lazy_bird.chuncker import chunck
from lazy_bird.crud import embedded as embedded_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.embedding import embed_texts, engine_family, vector_space

logger = logging.getLogger(__name__)


async def process_file(file_id: int):
    logger.info("Starting file processing: file_id=%s", file_id)
    file = file_crud.get(file_id)
    if file is None:
        raise ValueError("File not found")

    chunks = await chunck(file_id)
    if isinstance(chunks, Exception):
        raise chunks

    resolved = engine_family.resolve()
    model = resolved.model
    if model is None:
        raise ValueError("The default embedding preset does not use a local model")
    space = vector_space(resolved)

    embedded = embedded_crud.create(file_id, model.id, database.config.selected_vector_database)
    try:
        vectors = embed_texts([chunk["content"] for chunk in chunks], resolved)
        rows = [{**chunk, "vector": vector} for chunk, vector in zip(chunks, vectors, strict=True)]
        database.vector_delete(space, embedded.id)
        database.vector_create(space, embedded.id, rows)
        embedded_crud.update_status(embedded.id, "ready")
        file_crud.update_status(file_id, "done")
        return {"embedded_id": embedded.id, "chunks_created": len(rows)}
    except Exception:
        embedded_crud.update_status(embedded.id, "failed")
        file_crud.update_status(file_id, "embedding-error")
        logger.exception("File processing failed: file_id=%s embedded_id=%s", file_id, embedded.id)
        raise