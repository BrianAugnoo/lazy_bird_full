import pytest

import lazy_bird.crud.llm_model as llm_model_crud
import lazy_bird.tasks as tasks_module
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler


@pytest.fixture
def idle_scheduler(monkeypatch):
    scheduler = Scheduler(ResourcePool({"cpu": 2, "vram_mb": 0, "ram_mb": 100}))
    monkeypatch.setattr(tasks_module, "_scheduler", scheduler)
    return scheduler


def test_models_are_listed_updated_and_deleted(client, model_cache):
    model = llm_model_crud.register("org/a", model_cache("org/a", {"model.safetensors": b"w", "pytorch_model.bin": b"b"}))

    assert [item["hf_path"] for item in client.get("/models/?format=bin").json()] == ["org/a"]
    assert client.get("/models/?format=gguf").json() == []
    assert client.patch(f"/models/{model.id}", json={"selected_format": "bin"}).json()["selected_format"] == "bin"
    rejected = client.patch(f"/models/{model.id}", json={"selected_format": "gguf"})
    assert rejected.status_code == 422 and rejected.json()["error"]["code"] == "unknown_format"
    assert client.delete(f"/models/{model.id}").status_code == 204
    assert client.get(f"/models/{model.id}").json()["error"]["code"] == "model_not_found"


def test_download_is_queued_as_a_task(client, idle_scheduler):
    first = client.post("/models/", json={"hf_path": "org/llm-GGUF", "files": ["llm-Q4_K_M.gguf"]})
    second = client.post("/models/", json={"hf_path": "org/llm-GGUF"})

    assert first.status_code == 202
    assert first.json()["kind"] == "models.download"
    assert first.json()["params"] == {"hf_path": "org/llm-GGUF", "files": ["llm-Q4_K_M.gguf"], "revision": None}
    assert second.json()["id"] == first.json()["id"]
    assert client.post("/models/", json={"hf_path": "not a repo"}).status_code == 422


def test_uploaded_files_are_imported_as_a_local_model(client, model_cache, idle_scheduler):
    from lazy_bird.tasks.default import models as model_tasks
    from lazy_bird.tools import hf_cache

    assert client.put("/models/uploads/My Model/files/model.safetensors", content=b"weights").json() == {"path": "model.safetensors", "size": 7}
    assert client.put("/models/uploads/My Model/files/tokenizer/vocab.txt", content=b"a b").status_code == 200

    queued = client.post("/models/uploads/My Model")

    assert queued.status_code == 202
    task = queued.json()
    assert task["kind"] == "models.import" and task["params"]["staged"] is True
    result = model_tasks.import_model.run(**task["params"])
    model = llm_model_crud.get(result["model_id"])
    assert (model.hf_path, model.name, model.source, model.formats) == ("local/My-Model", "My Model", "local", ["safetensors"])
    assert (llm_model_crud.get(model.id).local_path.startswith(str(model_cache.root)))
    assert not hf_cache.staging_folder("My Model").exists()
    assert client.put("/models/uploads/My Model/files/other.bin", content=b"x").json()["error"]["code"] == "model_exists"


def test_uploads_are_checked_and_can_be_discarded(client, model_cache, idle_scheduler):
    from lazy_bird.tools import hf_cache

    for bad in ("../escape.bin", ".hidden/model.bin"):
        response = client.put(f"/models/uploads/mine/files/{bad}", content=b"x")
        assert response.status_code in (404, 422), bad
        if response.status_code == 422:
            assert response.json()["error"]["code"] == "invalid_path"
    assert client.post("/models/uploads/mine").json()["error"]["code"] == "nothing_uploaded"
    client.put("/models/uploads/mine/files/w.gguf", content=b"x")

    assert client.delete("/models/uploads/mine").status_code == 204
    assert not hf_cache.staging_folder("mine").exists()
    assert client.post("/models/uploads/!!!").json()["error"]["code"] == "invalid_model_name"


def test_importing_an_installed_name_is_a_conflict(client, model_cache, idle_scheduler):
    llm_model_crud.register("local/mine", model_cache("local/mine", {"w.pth": b"p"}), "local")

    response = client.post("/models/uploads/mine")

    assert response.status_code == 409 and response.json()["error"]["code"] == "model_exists"


def test_hub_files_are_listed_with_their_format(client, monkeypatch):
    import lazy_bird.api.endpoints.llm_model as endpoint

    monkeypatch.setattr(endpoint, "list_repo_files", lambda repo_id, revision: [{"path": "m-Q4_K_M.gguf", "size": 10, "format": "gguf"}])

    assert client.get("/models/hub/org/llm/files").json() == [{"path": "m-Q4_K_M.gguf", "size": 10, "format": "gguf"}]


def test_hub_failures_are_reported_as_external_errors(client, monkeypatch):
    import lazy_bird.api.endpoints.llm_model as endpoint

    def offline(repo_id, revision):
        raise ConnectionError("offline")

    monkeypatch.setattr(endpoint, "list_repo_files", offline)

    response = client.get("/models/hub/org/llm/files")

    assert response.status_code == 502 and response.json()["error"]["code"] == "hub_unreachable"
