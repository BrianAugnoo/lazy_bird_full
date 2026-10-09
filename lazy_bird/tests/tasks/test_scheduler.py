import threading
import time
from datetime import datetime, timedelta, timezone

import pytest

import lazy_bird.tasks as tasks_module
from lazy_bird.crud import task as task_crud
from lazy_bird.errors import ConflictError
from lazy_bird.tasks import TaskContext, task
from lazy_bird.tasks.resources import InsufficientResourcesError, ResourcePool
from lazy_bird.tasks.scheduler import Scheduler

GATES: dict[str, threading.Event] = {}
LOG: list[str] = []


def gate(name: str) -> threading.Event:
    return GATES.setdefault(name, threading.Event())


@task("test.record", title="Record {name}", resources={"cpu": 1})
def record(ctx: TaskContext, name: str) -> str:
    LOG.append(name)
    return name.upper()


@task("test.hold", resources=lambda name, vram=0: {"cpu": 1, "vram_mb": vram})
def hold(ctx: TaskContext, name: str, vram: int = 0) -> None:
    LOG.append(f"start:{name}")
    assert gate(name).wait(5)
    LOG.append(f"end:{name}")


@task("test.steps")
def steps(ctx: TaskContext, name: str, count: int) -> int:
    for index in range(ctx.state.get("done", 0), count):
        LOG.append(f"{name}:{index}")
        gate(f"{name}:{index}").wait(5)
        ctx.checkpoint(progress=(index + 1) / count, message=f"step {index}", state={"done": index + 1})
    return count


@task("test.fail", retries=1)
def fail(ctx: TaskContext) -> None:
    raise RuntimeError("boom")


class Clock:
    def __init__(self) -> None:
        self.value = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def sched(migrated_database, monkeypatch, clock):
    GATES.clear()
    LOG.clear()
    scheduler = Scheduler(ResourcePool({"cpu": 4, "vram_mb": 10, "ram_mb": 1000}), workers=2, poll_interval=0.02, now=clock)
    monkeypatch.setattr(tasks_module, "_scheduler", scheduler)
    yield scheduler
    for event in GATES.values():
        event.set()
    scheduler.stop(timeout=2)


def wait_for(scheduler: Scheduler, task_id: int, *statuses: str, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        current = scheduler.task(task_id)
        if current.status in statuses:
            return current
        time.sleep(0.02)
    raise AssertionError(f"task {task_id} stayed {scheduler.task(task_id).status}, expected {statuses}")


def wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not reached")


def test_a_task_runs_and_keeps_its_result(sched):
    submitted = record.submit(name="a")
    assert submitted.title == "Record a" and submitted.status == "queued"

    sched.start()

    done = wait_for(sched, submitted.id, "completed")
    assert done.result == "A" and done.attempts == 1 and LOG == ["a"]


def test_lower_priority_number_runs_first(sched):
    sched.workers = 1
    low, high = record.submit(name="low"), record.submit(name="high", priority=1)

    sched.start()

    wait_for(sched, low.id, "completed")
    wait_for(sched, high.id, "completed")
    assert LOG == ["high", "low"]


def test_scheduled_tasks_wait_for_their_time(sched, clock):
    later = record.submit(name="later", run_at=clock.value + timedelta(minutes=5))

    assert sched.schedule_once() == []
    assert sched.task(later.id).waiting_for == ["schedule"]

    clock.value += timedelta(minutes=6)
    assert sched.schedule_once() == [later.id]
    wait_for(sched, later.id, "completed")


def test_a_task_waiting_for_vram_blocks_smaller_vram_tasks_but_not_cpu_tasks(sched):
    first = hold.submit(name="first", vram=6)
    second = hold.submit(name="second", vram=6)
    small = hold.submit(name="small", vram=2)
    cpu = record.submit(name="cpu")

    sched.workers = 4
    started = sched.schedule_once()

    assert started == [first.id, cpu.id]
    assert sched.task(second.id).waiting_for == ["vram_mb"]
    assert sched.task(small.id).waiting_for == ["vram_mb"]
    gate("first").set()
    wait_for(sched, first.id, "completed")
    assert sched.schedule_once() == [second.id, small.id]


def test_tasks_run_in_parallel_when_resources_allow(sched):
    sched.pool.capacity["vram_mb"] = 20
    first, second = hold.submit(name="one", vram=6), hold.submit(name="two", vram=6)

    sched.start()

    wait_for(sched, first.id, "running")
    wait_for(sched, second.id, "running")
    assert sched.pool.snapshot()["used"]["vram_mb"] == 12
    gate("one").set(), gate("two").set()
    wait_for(sched, first.id, "completed"), wait_for(sched, second.id, "completed")
    assert sched.pool.snapshot()["used"] == {}


def test_impossible_requirements_are_rejected_at_submit(sched):
    with pytest.raises(InsufficientResourcesError):
        hold.submit(name="huge", vram=99)


def test_pause_stops_at_a_checkpoint_and_resume_continues_from_its_state(sched):
    sched.start()
    running = steps.submit(name="s", count=3)
    wait_until(lambda: "s:0" in LOG)

    sched.pause(running.id)
    assert sched.task(running.id).control == "pause"
    gate("s:0").set()
    paused = wait_for(sched, running.id, "paused")
    assert paused.progress == pytest.approx(1 / 3)

    gate("s:1").set(), gate("s:2").set()
    sched.resume(running.id)
    done = wait_for(sched, running.id, "completed")
    assert LOG == ["s:0", "s:1", "s:2"]
    assert done.result == 3


def test_cancel_a_running_task_at_its_next_checkpoint(sched):
    sched.start()
    running = steps.submit(name="c", count=5)
    wait_until(lambda: "c:0" in LOG)

    sched.cancel(running.id)
    gate("c:0").set()

    assert wait_for(sched, running.id, "cancelled").finished_at is not None
    assert LOG == ["c:0"]


def test_waiting_tasks_are_paused_or_cancelled_immediately(sched):
    queued = record.submit(name="q")

    assert sched.pause(queued.id).status == "paused"
    assert sched.resume(queued.id).status == "queued"
    assert sched.cancel(queued.id).status == "cancelled"
    with pytest.raises(ConflictError):
        sched.resume(queued.id)


def test_failures_are_retried_then_recorded(sched, clock):
    failing = fail.submit()

    sched.schedule_once()
    retried = wait_for(sched, failing.id, "queued")
    assert retried.error["message"] == "boom" and retried.run_at is not None

    clock.value += timedelta(minutes=1)
    sched.schedule_once()
    failed = wait_for(sched, failing.id, "failed")
    assert failed.attempts == 2 and failed.error == {"code": "RuntimeError", "message": "boom"}

    again = sched.retry(failing.id)
    assert again.status == "queued" and again.error is None


def test_dedupe_key_returns_the_active_task(sched):
    first = record.submit(name="x", dedupe_key="record:x")
    second = record.submit(name="x", dedupe_key="record:x")

    assert first.id == second.id
    assert len(sched.tasks()) == 1


def test_waiting_tasks_can_be_reordered(sched):
    a, b, c = (record.submit(name=name) for name in "abc")
    urgent = record.submit(name="urgent", priority=1)

    sched.move(c.id, before_id=a.id)
    moved = sched.move(b.id, before_id=urgent.id)

    assert [item.id for item in sched.tasks()] == [b.id, urgent.id, c.id, a.id]
    assert moved.priority == 1


def test_unknown_kinds_fail_clearly(sched):
    created, _ = task_crud.create("test.missing", "Missing", {}, priority=0, run_at=None, resources={}, max_attempts=1, dedupe_key=None)

    sched.schedule_once()

    assert sched.task(created.id).error["code"] == "unknown_task_kind"


def test_tasks_running_at_shutdown_are_requeued_on_start(sched):
    created = record.submit(name="r")
    task_crud.claim(created.id)

    sched.start()

    wait_for(sched, created.id, "completed")


def test_stop_puts_running_tasks_back_in_the_queue(sched):
    sched.start()
    running = steps.submit(name="stop", count=2)
    wait_until(lambda: "stop:0" in LOG)

    threading.Timer(0.2, gate("stop:0").set).start()
    sched.stop(timeout=3)

    stopped = sched.task(running.id)
    assert stopped.status == "queued" and task_crud.state_of(running.id) == {"done": 1}


def test_finished_tasks_can_be_deleted(sched):
    done = record.submit(name="d")
    sched.start()
    wait_for(sched, done.id, "completed")

    with pytest.raises(ConflictError):
        sched.delete(record.submit(name="active", run_at=datetime(2099, 1, 1, tzinfo=timezone.utc)).id)
    sched.delete(done.id)
    assert all(item.id != done.id for item in sched.tasks())
