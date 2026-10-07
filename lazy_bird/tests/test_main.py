def test_root_endpoint_returns_welcome_message(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["message"] == "Welcome to Lazy Bird!"


def test_development_template_routes_are_not_exposed(client):
    assert client.get("/codebase").status_code == 404
    assert client.get("/upload_file").status_code == 200
    assert client.get("/shemas").status_code == 200


def test_openapi_contains_all_application_surfaces(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/models/" in paths
    assert "/files/upload" in paths
    assert "/upload_file" not in paths
    assert "/api-keys/" in paths
    assert "/embedding-presets/" in paths
    assert "/inference-presets/" in paths
from contextlib import contextmanager
from fastapi.testclient import TestClient

import lazy_bird.main as main_module
from lazy_bird.database import DatabaseStatus


def test_root_reports_database_failure_without_running_startup_services(monkeypatch):
    calls = []
    monkeypatch.setattr(main_module.database, "initialize_selected_sql_database", lambda: DatabaseStatus(ready=False, error="connection refused"))
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: calls.append("auth"))
    monkeypatch.setattr(main_module, "sync_cached_models", lambda: calls.append("sync"))
    monkeypatch.setattr(main_module, "initialize_embedding_engines", lambda: calls.append("engines"))

    with TestClient(main_module.app) as client:
        root = client.get("/")
        blocked = client.get("/models/")

    assert root.status_code == 200
    assert root.json() == {"success": False, "error": "connection refused"}
    assert blocked.status_code == 503
    assert calls == []


def test_successful_startup_runs_services_after_database_is_ready(migrated_database, monkeypatch):
    calls = []
    ready = DatabaseStatus(ready=True, revision="head")
    monkeypatch.setattr(main_module.database, "initialize_selected_sql_database", lambda: calls.append("database") or ready)
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: calls.append("auth"))
    monkeypatch.setattr(main_module, "sync_cached_models", lambda: calls.append("sync"))
    monkeypatch.setattr(main_module, "initialize_embedding_engines", lambda: calls.append("engines"))
    monkeypatch.setattr(main_module.database, "initialize_selected_vector_database", lambda: calls.append("vector"))
    monkeypatch.setattr(main_module.vector_database, "populate", lambda names: calls.append("populate"))

    with TestClient(main_module.app) as client:
        response = client.get("/")

    assert response.json()["success"] is True
    assert calls == ["database", "auth", "sync", "engines", "vector", "populate"]


def test_service_initialization_failure_is_exposed_without_starting_later_services(migrated_database, monkeypatch):
    calls = []
    monkeypatch.setattr(main_module.database, "initialize_selected_sql_database", lambda: DatabaseStatus(ready=True, revision="head"))
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: calls.append("auth"))
    monkeypatch.setattr(main_module, "sync_cached_models", lambda: (_ for _ in ()).throw(RuntimeError("cache unavailable")))
    monkeypatch.setattr(main_module, "initialize_embedding_engines", lambda: calls.append("engines"))

    with TestClient(main_module.app) as client:
        root = client.get("/")
        blocked = client.get("/models/")

    assert root.json() == {"success": False, "error": "Application initialization failed: cache unavailable"}
    assert blocked.status_code == 503
    assert calls == ["auth"]
