"""File processing tasks. Their states are tracked by ``crud/file_processing.py``."""

import asyncio
from datetime import datetime, timedelta, timezone

from lazy_bird import chunker, database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.crud import file as file_crud
from lazy_bird.crud import file_processing
from lazy_bird.embedding import embed_texts, engine_family, vector_space
from lazy_bird.errors import AppError, ConflictError
from lazy_bird.tasks import TaskContext, on_status_change, task

EMBEDDING_BATCH = 64

on_status_change(file_processing.on_task_change)


@task("files.chunk", title="Chunk file {file_id}", resources={"cpu": 1})
def chunk_file(ctx: TaskContext, file_id: int) -> dict:
    """Split a file into chunks and store them (replacing the previous ones)."""
    ctx.report(0.0, "Chunking")
    chunks = asyncio.run(chunker.chunk_file(file_id))
    ctx.checkpoint(0.9, f"Storing {len(chunks)} chunks")
    stored = chunk_crud.replace(file_id, chunks)
    return {"file_id": file_id, "chunks": len(stored)}


def embedding_resources(file_id: int, target: str, preset_id: int) -> dict[str, float]:
    """Resources declared by the preset's engine (one CPU slot by default)."""
    try:
        resolved = engine_family.resolve(preset_id)
    except AppError:
        return {"cpu": 1}
    estimate = getattr(resolved.module, "resources", None)
    return dict(estimate(resolved.settings, resolved.model)) if estimate else {"cpu": 1}


@task("files.embed", title="Embed file {file_id} with {target}", resources=embedding_resources)
def embed_file(ctx: TaskContext, file_id: int, target: str, preset_id: int) -> dict:
    """Embed the chunks of a file with a preset into the vector table of ``target``."""
    resolved = engine_family.resolve(preset_id)
    if vector_space(resolved) != target:
        raise ConflictError(f"Preset {preset_id} no longer embeds with {target}.", code="preset_target_changed")
    chunks = chunk_crud.for_file(file_id)
    done = ctx.state.get("done", 0)
    for start in range(done, len(chunks), EMBEDDING_BATCH):
        batch = chunks[start:start + EMBEDDING_BATCH]
        vectors = embed_texts([chunk.content for chunk in batch], resolved)
        database.vector_create(target, [{"chunk_id": chunk.id, "vector": vector} for chunk, vector in zip(batch, vectors, strict=True)])
        finished = start + len(batch)
        ctx.checkpoint(finished / len(chunks), f"Embedded {finished}/{len(chunks)} chunks", {"done": finished})
    return {"file_id": file_id, "chunks": len(chunks), "model": target}


@task("files.scan", title="Look for files changed on disk", resources={"cpu": 1})
def scan_files(ctx: TaskContext, every_minutes: int = 0, slot: int = 0) -> dict:
    """Rehash files whose size or modification time changed.

    With ``every_minutes``, the scan queues its next run. Runs alternate between two
    ``slot`` dedupe keys so the next run is never merged with the current one, while
    two periodic chains (e.g. after a restart) merge into one.
    """
    changed = file_crud.detect_changes(progress=lambda value: ctx.report(value, "Checking files"))
    if every_minutes > 0:
        schedule_scan(every_minutes, slot=1 - slot, delay_minutes=every_minutes)
    return changed


def schedule_scan(every_minutes: int, slot: int = 0, delay_minutes: int = 0):
    """Queue a periodic scan (every ``every_minutes``), or a single one when it is 0."""
    if every_minutes <= 0:
        return scan_files.submit(dedupe_key="files.scan:now", priority=-10)
    return scan_files.submit(
        every_minutes=every_minutes,
        slot=slot,
        run_at=datetime.now(timezone.utc) + timedelta(minutes=delay_minutes) if delay_minutes else None,
        dedupe_key=f"files.scan:{slot}",
        priority=-10,
    )
