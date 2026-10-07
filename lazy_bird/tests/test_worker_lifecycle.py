import pytest

import lazy_bird.main as main_module
from lazy_bird.database import DatabaseStatus


@pytest.mark.anyio
async def test_lifespan_starts_and_stops_the_task_scheduler(migrated_database, monkeypatch):
    calls = []
    monkeypatch.setattr(main_module.database, "initialize_selected_sql_database", lambda: DatabaseStatus(ready=True, revision="test"))
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: None)
    monkeypatch.setattr(main_module, "sync_cached_models", lambda: 0)
    monkeypatch.setattr(main_module, "start_scheduler", lambda: calls.append("start"))
    monkeypatch.setattr(main_module, "stop_scheduler", lambda: calls.append("stop"))

    async with main_module.lifespan(main_module.app):
        assert calls == ["start"]

    assert calls == ["start", "stop"]


@pytest.mark.anyio
async def test_scheduler_is_not_started_when_initialization_fails(migrated_database, monkeypatch):
    calls = []
    monkeypatch.setattr(main_module.database, "initialize_selected_sql_database", lambda: DatabaseStatus(ready=True, revision="test"))
    monkeypatch.setattr(main_module, "authenticate_hf", lambda: (_ for _ in ()).throw(RuntimeError("offline")))
    monkeypatch.setattr(main_module, "start_scheduler", lambda: calls.append("start"))
    monkeypatch.setattr(main_module, "stop_scheduler", lambda: calls.append("stop"))

    async with main_module.lifespan(main_module.app):
        assert main_module.app.state.startup_error == "Application initialization failed: offline"

    assert calls == []
