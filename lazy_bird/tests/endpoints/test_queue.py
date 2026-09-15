from types import SimpleNamespace


def test_upload_enqueues_each_file(client, monkeypatch):
    import lazy_bird.crud.file as file_crud

    queued = []
    monkeypatch.setattr(file_crud, "enqueue_file", queued.append)

    response = client.post(
        "/files/upload?dir=documents",
        files={"files": ("notes.txt", b"content", "text/plain")},
    )

    assert response.status_code == 200
    assert queued == [1]


def test_file_process_endpoint_enqueues_existing_file(client, monkeypatch):
    import lazy_bird.api.endpoints.file as file_endpoint

    task = SimpleNamespace(id="task-1")
    queued = []
    monkeypatch.setattr(file_endpoint, "enqueue_file", lambda file_id: queued.append(file_id) or task)

    created = client.post(
        "/files/upload?dir=documents",
        files={"files": ("notes.txt", b"content", "text/plain")},
    )
    response = client.post("/files/1/process")

    assert created.status_code == 200
    assert response.status_code == 202
    assert response.json() == {"file_id": 1, "task_id": "task-1"}
    assert queued == [1]


def test_file_process_endpoint_returns_not_found(client):
    response = client.post("/files/9999/process")

    assert response.status_code == 404


def test_upload_progress_websocket_returns_file_states(client, monkeypatch):
    import lazy_bird.main as main_module

    monkeypatch.setattr(
        main_module.file_crud,
        "get_processing_status",
        lambda: [
            {"id": 1, "name": "queued.txt", "status": "queued", "detail": "pending"},
            {"id": 2, "name": "active.txt", "status": "processing", "detail": "processing"},
            {"id": 3, "name": "done.txt", "status": "finished", "detail": "done"},
        ],
    )

    with client.websocket_connect("/ws/upload-progress") as websocket:
        assert websocket.receive_json() == {
            "files": [
                {"id": 1, "name": "queued.txt", "status": "queued", "detail": "pending"},
                {"id": 2, "name": "active.txt", "status": "processing", "detail": "processing"},
                {"id": 3, "name": "done.txt", "status": "finished", "detail": "done"},
            ]
        }