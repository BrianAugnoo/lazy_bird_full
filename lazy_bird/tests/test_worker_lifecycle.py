import pytest

import lazy_bird.main as main_module
from lazy_bird.database import DatabaseStatus


@pytest.mark.anyio
async def test_lifespan_starts_and_stops_worker_when_auto_embedding_enabled(monkeypatch):
    worker = object()
    started = []
    stopped = []
    monkeypatch.setattr(
        main_module.database,
        "initialize_selected_sql_database",
        lambda: DatabaseStatus(ready=True, revision="test"),
    )
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: None)
    monkeypatch.setattr(main_module, "sync_cached_models", lambda: 0)
    monkeypatch.setattr(main_module, "initialize_embedding_engines", lambda: None)
    monkeypatch.setattr(main_module.database, "initialize_selected_vector_database", lambda: None)
    monkeypatch.setattr(main_module.vector_database, "populate", lambda names: None)
    monkeypatch.setattr(main_module, "auto_embedding_enabled", lambda: True)
    monkeypatch.setattr(main_module, "start_worker", lambda: started.append(True) or worker)
    monkeypatch.setattr(main_module, "stop_worker", lambda value: stopped.append(value))

    async with main_module.lifespan(main_module.app):
        assert started == [True]

    assert stopped == [worker]


@pytest.mark.anyio
async def test_lifespan_does_not_start_worker_when_auto_embedding_disabled(monkeypatch):
    started = []
    monkeypatch.setattr(
        main_module.database,
        "initialize_selected_sql_database",
        lambda: DatabaseStatus(ready=True, revision="test"),
    )
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: None)
    monkeypatch.setattr(main_module, "sync_cached_models", lambda: 0)
    monkeypatch.setattr(main_module, "initialize_embedding_engines", lambda: None)
    monkeypatch.setattr(main_module.database, "initialize_selected_vector_database", lambda: None)
    monkeypatch.setattr(main_module.vector_database, "populate", lambda names: None)
    monkeypatch.setattr(main_module, "auto_embedding_enabled", lambda: False)
    monkeypatch.setattr(main_module, "start_worker", lambda: started.append(True))
    monkeypatch.setattr(main_module, "stop_worker", lambda worker: None)

    async with main_module.lifespan(main_module.app):
        assert started == []