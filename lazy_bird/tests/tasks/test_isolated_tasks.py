"""Isolated tasks: each run in a process of its own, served by the scheduler, ended when it does not stop."""

import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import psutil
import pytest

import lazy_bird.tasks as tasks_module
from lazy_bird.crud import task as task_crud
from lazy_bird.embedding import engine_family
from lazy_bird.residency import residency
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler
from tests.hosting.tasks import blocking, crash, embed, refuse, steps, stuck, where


@pytest.fixture
def sched(migrated_database, monkeypatch):
    """A started scheduler (tasks asked to stop get 0.5 s before being dealt with)."""
    monkeypatch.setattr(
        sys.modules[Scheduler.__module__],
        "smart_memory",
        lambda: SimpleNamespace(enable=True, fallback="wait", isolate_models=True, interrupt_timeout_seconds=0.5),
    )
    scheduler = Scheduler(ResourcePool({"cpu": 8, "vram_mb": 1000, "ram_mb": 4000}), workers=3, poll_interval=0.02)
    monkeypatch.setattr(tasks_module, "_scheduler", scheduler)
    scheduler.start()
    yield scheduler
    scheduler.stop(timeout=1)


@pytest.fixture
def gates(tmp_path) -> Path:
    return tmp_path


def open_gate(gates: Path, name: str) -> None:
    (gates / name).write_text("go")


def wait_for(scheduler, task_id, *statuses, timeout=30.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = scheduler.task(task_id)
        if current.status in statuses:
            return current
        time.sleep(0.05)
    raise AssertionError(f"task {task_id} stayed {scheduler.task(task_id).status} ({scheduler.task(task_id).error}), expected {statuses}")


def wait_until(predicate, timeout=30.0, message="condition not reached"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError(message)


def test_an_isolated_task_runs_in_a_process_of_its_own(sched):
    submitted = where.submit(label="x")

    done = wait_for(sched, submitted.id, "completed")

    assert done.result["pid"] != os.getpid() and not psutil.pid_exists(done.result["pid"])
    assert done.result["title"] == "Where am I"  # it read the server's database
    assert task_crud.state_of(submitted.id) == {"seen": "x"} and done.message == "almost"  # progress and checkpoints reached the task row


def test_pausing_an_isolated_task_keeps_its_progress_and_it_resumes_in_a_new_process(sched, gates):
    submitted = steps.submit(name="s", gate_dir=str(gates))
    open_gate(gates, "s-0")
    wait_until(lambda: task_crud.state_of(submitted.id).get("done") == 1)

    sched.pause(submitted.id)

    wait_for(sched, submitted.id, "paused")
    assert task_crud.state_of(submitted.id)["done"] == 1
    for name in ("s-1", "s-2"):
        open_gate(gates, name)
    sched.resume(submitted.id)
    done = wait_for(sched, submitted.id, "completed")
    assert task_crud.state_of(submitted.id)["done"] == 3
    assert len(set(done.result["pids"])) == 2  # two runs, two processes


def test_a_failure_in_an_isolated_task_keeps_its_error(sched):
    failed = wait_for(sched, refuse.submit().id, "failed")

    assert failed.error["code"] == "bad_input"
    assert failed.error["message"] == "This input cannot be processed."
    assert failed.error["details"]["why"] == "test"


def test_a_crash_only_fails_the_task(sched):
    failed = wait_for(sched, crash.submit().id, "failed")

    assert failed.error["code"] == "task_crashed" and failed.error["details"]["exit_code"] == 7
    assert wait_for(sched, where.submit(label="after").id, "completed")  # the server goes on


def test_a_stuck_isolated_task_is_ended_when_it_is_cancelled(sched, gates):
    submitted = stuck.submit(name="k", gate_dir=str(gates))
    pid = int(wait_until(lambda: (gates / "k.pid").exists() and (gates / "k.pid").read_text()))

    sched.cancel(submitted.id)

    cancelled = wait_for(sched, submitted.id, "cancelled", timeout=10)
    assert cancelled.status == "cancelled" and not psutil.pid_exists(pid)


def test_an_isolated_task_waiting_for_a_blocking_call_stops_at_once_when_it_is_cancelled(sched, gates, monkeypatch):
    patient = SimpleNamespace(enable=True, fallback="wait", isolate_models=True, interrupt_timeout_seconds=60)
    monkeypatch.setattr(sys.modules[Scheduler.__module__], "smart_memory", lambda: patient)  # it is not ended for being late
    submitted = blocking.submit(name="b", gate_dir=str(gates))
    pid = int(wait_until(lambda: (gates / "b.pid").exists() and (gates / "b.pid").read_text()))

    asked = time.monotonic()
    sched.cancel(submitted.id)

    assert wait_for(sched, submitted.id, "cancelled", timeout=10)
    assert time.monotonic() - asked < 4  # neither the 60 s wait nor its own threads hold it
    wait_until(lambda: not psutil.pid_exists(pid), timeout=5, message="the task process is still running")


def test_a_stuck_isolated_task_that_must_make_room_is_ended_and_goes_back_to_the_queue(sched, gates):
    blocking = stuck.submit(name="k", gate_dir=str(gates), resources={"cpu": 1, "ram_mb": 3000}, priority=5)
    pid = int(wait_until(lambda: (gates / "k.pid").exists() and (gates / "k.pid").read_text()))

    urgent = where.submit(label="urgent", resources={"cpu": 1, "ram_mb": 3000}, priority=1)

    assert wait_for(sched, urgent.id, "completed", timeout=15)
    assert not psutil.pid_exists(pid)
    assert sched.task(blocking.id).attempts <= 1  # ended to make room: not counted as a failed attempt


def test_an_isolated_task_uses_the_models_of_the_server(sched, crud_database, monkeypatch):
    import tests.hosting.engine as module

    monkeypatch.setattr(engine_family, "_loaded", dict(engine_family._loaded))
    engine = engine_family.register(module)

    done = wait_for(sched, embed.submit(engine_id=engine.id, settings={"gpu_mb": 300}).id, "completed")

    # Completion is persisted before the worker's finally block releases its lease.
    wait_until(lambda: all(model["idle"] for model in residency().describe()), message="the finished task kept its model lease")
    [model] = residency().describe()  # the model was loaded by the server, for the task, and stays there idle
    assert done.result["model_pid"] == model["pid"] != done.result["pid"]
    assert model["idle"] is True and model["needs"]["vram_mb"] == 300
    assert done.result["length"] == 3


def test_the_processes_of_isolated_tasks_are_listed_with_their_memory(sched, gates):
    submitted = stuck.submit(name="k", gate_dir=str(gates))
    pid = int(wait_until(lambda: (gates / "k.pid").exists() and (gates / "k.pid").read_text()))

    process = sched.resources()["processes"][str(submitted.id)]

    assert process["pid"] == pid and process["memory_mb"] > 10


def test_stopping_the_server_ends_isolated_tasks_that_do_not_stop(sched, gates):
    submitted = stuck.submit(name="k", gate_dir=str(gates))
    pid = int(wait_until(lambda: (gates / "k.pid").exists() and (gates / "k.pid").read_text()))

    sched.stop(timeout=0.5)

    assert sched.task(submitted.id).status == "queued"  # it runs again at the next start
    assert not psutil.pid_exists(pid)
