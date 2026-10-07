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


def test_upload_enqueues_each_file(client, monkeypatch):
    import lazy_bird.crud.file as file_crud

    queued = []
    monkeypatch.setattr(file_crud, "auto_embedding_enabled", lambda: True)
    monkeypatch.setattr(file_crud, "enqueue_file", queued.append)

    response = client.post("/files/upload?dir=documents", files={"files": ("notes.txt", b"content", "text/plain")})

    assert response.status_code == 200
    assert queued == [1]


def test_file_process_endpoint_queues_one_task_per_file(client, idle_scheduler):
    client.post("/files/upload?dir=documents", files={"files": ("notes.md", b"content", "text/markdown")})

    first = client.post("/files/1/process")
    second = client.post("/files/1/process")

    assert first.status_code == 202
    assert first.json()["kind"] == "files.process" and first.json()["params"] == {"file_id": 1}
    assert first.json()["title"] == "Process notes.md"
    assert second.json()["id"] == first.json()["id"]


def test_file_process_endpoint_returns_not_found(client):
    response = client.post("/files/9999/process")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "file_not_found"


def test_upload_progress_websocket_returns_file_states(client, monkeypatch):
    import lazy_bird.main as main_module

    states = [{"id": 1, "name": "queued.txt", "status": "queued", "detail": "pending"}]
    monkeypatch.setattr(main_module.file_crud, "get_processing_status", lambda: states)

    with client.websocket_connect("/ws/upload-progress") as websocket:
        assert websocket.receive_json() == {"files": states}
