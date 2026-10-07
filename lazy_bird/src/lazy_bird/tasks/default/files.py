"""File processing tasks: chunk a file, then embed its chunks."""

import asyncio

from lazy_bird import database
from lazy_bird.chuncker import chunck
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.embedding import embed_texts, engine_family, vector_space
from lazy_bird.errors import AppError
from lazy_bird.tasks import TaskContext, task

EMBEDDING_BATCH = 64
CHUNKED = 0.1  # share of the progress bar taken by chunking


def processing_resources(file_id: int) -> dict[str, float]:
    """Resources of the default embedding preset's engine (one CPU slot by default)."""
    try:
        resolved = engine_family.resolve()
    except AppError:
        return {"cpu": 1}
    estimate = getattr(resolved.module, "resources", None)
    return dict(estimate(resolved.settings, resolved.model)) if estimate else {"cpu": 1}


@task("files.process", title="Process file {file_id}", resources=processing_resources)
def process_file(ctx: TaskContext, file_id: int) -> dict:
    """Chunk a file, store its chunks, then embed them with the default embedding preset."""
    if file_crud.get(file_id) is None:
        raise ValueError(f"File {file_id} does not exist")
    if ctx.state.get("stage") != "embedding":
        ctx.report(0.0, "Chunking")
        chunks = asyncio.run(chunck(file_id))
        if isinstance(chunks, Exception):
            raise chunks
        stored = chunk_crud.replace(file_id, chunks)
        ctx.checkpoint(CHUNKED, f"{len(stored)} chunks", {"stage": "embedding", "done": 0})
    try:
        return _embed(ctx, file_id)
    except Exception:
        file_crud.update_status(file_id, "embedding-error")
        raise


def _embed(ctx: TaskContext, file_id: int) -> dict:
    # The preset is fixed at the first embedding run so a resumed task never mixes models.
    resolved = engine_family.resolve(ctx.state.get("preset_id"))
    ctx.state["preset_id"] = resolved.preset_id
    model_name = vector_space(resolved)
    chunks = chunk_crud.for_file(file_id)
    done = ctx.state.get("done", 0)
    for start in range(done, len(chunks), EMBEDDING_BATCH):
        batch = chunks[start:start + EMBEDDING_BATCH]
        vectors = embed_texts([chunk.content for chunk in batch], resolved)
        database.vector_create(model_name, [{"chunk_id": chunk.id, "vector": vector} for chunk, vector in zip(batch, vectors, strict=True)])
        finished = start + len(batch)
        ctx.checkpoint(
            CHUNKED + (1 - CHUNKED) * finished / len(chunks),
            f"Embedded {finished}/{len(chunks)} chunks",
            {**ctx.state, "done": finished},
        )
    file_crud.update_status(file_id, "done")
    return {"file_id": file_id, "chunks": len(chunks), "model": model_name}
