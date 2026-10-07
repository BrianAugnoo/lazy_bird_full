import pytest

import lazy_bird.tasks as tasks_module
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler
from tests.tasks.test_scheduler import record


@pytest.fixture
def api_scheduler(client, monkeypatch):
    scheduler = Scheduler(ResourcePool({"cpu": 2, "vram_mb": 0, "ram_mb": 100}), workers=1, poll_interval=0.02)
    monkeypatch.setattr(tasks_module, "_scheduler", scheduler)
    yield scheduler
    scheduler.stop(timeout=2)


def test_rest_endpoints_control_tasks(client, api_scheduler):
    queued = record.submit(name="rest")

    assert client.get("/tasks/").json()[0]["id"] == queued.id
    assert client.post(f"/tasks/{queued.id}/pause").json()["status"] == "paused"
    assert client.post(f"/tasks/{queued.id}/pause").json()["error"]["code"] == "invalid_task_transition"
    assert client.patch(f"/tasks/{queued.id}", json={"priority": 3}).json()["priority"] == 3
    assert client.post(f"/tasks/{queued.id}/cancel").json()["status"] == "cancelled"
    assert client.delete(f"/tasks/{queued.id}").status_code == 204
    assert client.get(f"/tasks/{queued.id}").json()["error"]["code"] == "task_not_found"
    assert "test.record" in {kind["kind"] for kind in client.get("/tasks/kinds").json()}
    assert client.get("/tasks/resources").json()["capacity"]["cpu"] == 2


def test_websocket_sends_a_snapshot_then_answers_commands_and_streams_changes(client, api_scheduler):
    queued = record.submit(name="ws")

    with client.websocket_connect("/ws/tasks") as socket:
        snapshot = socket.receive_json()
        assert snapshot["type"] == "snapshot"
        assert [item["id"] for item in snapshot["tasks"]] == [queued.id]
        assert {"capacity", "used", "holders"} <= snapshot["resources"].keys()

        socket.send_json({"action": "pause", "task_id": queued.id, "request_id": "r1"})
        messages = [socket.receive_json(), socket.receive_json()]
        ack = next(message for message in messages if message["type"] == "ack")
        change = next(message for message in messages if message["type"] == "task")
        assert ack["request_id"] == "r1" and ack["task"]["status"] == "paused"
        assert change["task"]["status"] == "paused"

        socket.send_json({"action": "fly", "task_id": queued.id, "request_id": "r2"})
        error = socket.receive_json()
        assert error == {"type": "error", "request_id": "r2", "error": {"code": "invalid_command", "message": "Unknown action 'fly'.", "details": {}}}

        socket.send_text("not json")
        assert socket.receive_json()["error"]["code"] == "invalid_command"
