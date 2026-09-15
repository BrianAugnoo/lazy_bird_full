import logging

from lazy_bird import database
from lazy_bird.chuncker import chunck
from lazy_bird.crud import embedded as embedded_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.crud import selected_model_embeding
from lazy_bird.database import db
from lazy_bird.embedding import generate_embeddings
from lazy_bird.models.llm_model import LLMModel

logger = logging.getLogger(__name__)


async def process_file(file_id: int):
    logger.info("Starting file processing: file_id=%s", file_id)
    file = file_crud.get(file_id)
    if file is None:
        raise ValueError("File not found")

    chunks = await chunck(file_id)
    if isinstance(chunks, Exception):
        raise chunks

    selection = selected_model_embeding.get()
    if selection.llm_model_id is None:
        raise ValueError("No embedding model is selected")
    with db() as session:
        model = session.get(LLMModel, selection.llm_model_id)
    if model is None:
        raise ValueError("Selected embedding model does not exist")

    embedded = embedded_crud.create(file_id, model.id, database.config.selected_vector_database)
    try:
        rows = generate_embeddings(chunks)
        database.vector_delete(model.name, embedded.id)
        database.vector_create(model.name, embedded.id, rows)
        embedded_crud.update_status(embedded.id, "ready")
        file_crud.update_status(file_id, "done")
        return {"embedded_id": embedded.id, "chunks_created": len(rows)}
    except Exception:
        embedded_crud.update_status(embedded.id, "failed")
        file_crud.update_status(file_id, "embedding-error")
        logger.exception("File processing failed: file_id=%s embedded_id=%s", file_id, embedded.id)
        raise