from __future__ import annotations

import asyncio
import multiprocessing
import os
from pathlib import Path

from huey import SqliteHuey


def queue_database_path() -> str:
    configured_path = os.getenv("LAZY_BIRD_QUEUE_DB")
    if configured_path:
        return configured_path
    return str(Path(__file__).resolve().parent / "database" / "storage" / "lazy_bird_queue.db")


huey = SqliteHuey("lazy-bird", filename=queue_database_path())


@huey.task()
def process_file_task(file_id: int):
    from lazy_bird import database
    from lazy_bird.embedding import initialize_embedding_engines
    from lazy_bird.crud.file_processing import process_file

    database_status = database.initialize_selected_sql_database()
    if not database_status.ready:
        raise RuntimeError(database_status.error or "Database is unavailable")
    initialize_embedding_engines()
    database.initialize_selected_vector_database()
    return asyncio.run(process_file(file_id))


def enqueue_file(file_id: int):
    return process_file_task(file_id)


def queued_file_ids() -> set[int]:
    return {
        task.args[0]
        for task in huey.pending()
        if task.name == process_file_task.name and task.args
    }


def _run_worker() -> None:
    from huey.consumer import Consumer

    Consumer(huey, workers=1, worker_type="thread").run()


def start_worker() -> multiprocessing.Process:
    worker = multiprocessing.Process(target=_run_worker, name="lazy-bird-huey-worker")
    worker.start()
    return worker


def stop_worker(worker: multiprocessing.Process | None) -> None:
    if worker is None or not worker.is_alive():
        return
    worker.terminate()
    worker.join(timeout=5)