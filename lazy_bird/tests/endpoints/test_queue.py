import pytest

import lazy_bird.tasks as tasks_module
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler


@pytest.fixture
def idle_scheduler(monkeypatch):
    """A scheduler that is never started: submitted tasks stay queued."""
    scheduler = Scheduler(ResourcePool({"cpu": 2, "vram_mb": 16000, "ram_mb": 100}))
    monkeypatch.setattr(tasks_module, "_scheduler", scheduler)
    return scheduler


def test_upload_queues_processing_when_auto_embedding_is_on(client, idle_scheduler, monkeypatch):
    import lazy_bird.crud.file as file_crud

    monkeypatch.setattr(file_crud, "auto_embedding_enabled", lambda: True)

    response = client.post("/files/upload?dir=documents", files={"files": ("notes.md", b"content", "text/markdown")})

    assert response.status_code == 200
    assert response.json()[0]["state"] == "processing"
    assert [task.kind for task in idle_scheduler.tasks()] == ["files.chunk"]


def test_file_process_endpoint_queues_chunking_once(client, idle_scheduler):
    client.post("/files/upload?dir=documents", files={"files": ("notes.md", b"content", "text/markdown")})

    first = client.post("/files/1/process")
    second = client.post("/files/1/process")

    assert first.status_code == 202
    [chunking] = first.json()["processing"]
    assert (chunking["processor"], chunking["state"]) == ("chunking", "queued")
    assert second.json()["processing"][0]["task_id"] == chunking["task_id"]
    [task] = idle_scheduler.tasks()
    assert (task.kind, task.title, task.params) == ("files.chunk", "Chunk notes.md", {"file_id": 1})


def test_file_process_endpoint_returns_not_found(client):
    response = client.post("/files/9999/process")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "file_not_found"
