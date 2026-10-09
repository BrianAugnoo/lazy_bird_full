"""Smart memory in the scheduler: tasks reserve the models they use, and more urgent work makes less urgent work yield."""

import sys
import threading
import time
from types import SimpleNamespace

import psutil
import pytest

import lazy_bird.tasks as tasks_module
from lazy_bird import preferences
from lazy_bird.embedding import engine_family
from lazy_bird.residency import residency
from lazy_bird.errors import InsufficientResourcesError
from lazy_bird.tasks import TaskContext, task
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler

GATES: dict[str, threading.Event] = {}
LOG: list[str] = []
ENGINES: dict[str, object] = {}


def gate(name: str) -> threading.Event:
    return GATES.setdefault(name, threading.Event())


@task("test.work", title="Work {name}", resources={"cpu": 1}, engines=lambda name, model: [ENGINES[model]])
def work(ctx: TaskContext, name: str, model: str) -> str:
    """Uses a model until its gate opens; stops at checkpoints, so it can yield."""
    with ENGINES[model].loaded():
        LOG.append(f"start:{name}")
        while not gate(name).is_set():
            ctx.checkpoint(message="working")
            time.sleep(0.005)
        LOG.append(f"end:{name}")
    return name


@task("test.stubborn", title="Stubborn {name}", resources={"cpu": 1}, engines=lambda name, model: [ENGINES[model]])
def stubborn(ctx: TaskContext, name: str, model: str) -> str:
    """Uses a model until its gate opens and never reaches a checkpoint."""
    with ENGINES[model].loaded():
        LOG.append(f"start:{name}")
        gate(name).wait(10)
        LOG.append(f"end:{name}")
    return name


@pytest.fixture
def machine(fake_local_embedding, monkeypatch):
    """A started scheduler on a machine with 1000 MB of GPU memory; models A (600), B (600), C (100) and D (500)."""
    GATES.clear()
    LOG.clear()
    scheduler = Scheduler(ResourcePool({"cpu": 8, "vram_mb": 1000, "ram_mb": 4000}), workers=4, poll_interval=0.02)
    monkeypatch.setattr(tasks_module, "_scheduler", scheduler)
    for name, dimension, memory in (("A", 3, 600), ("B", 4, 600), ("C", 5, 100), ("D", 6, 500)):
        ENGINES[name] = engine_family.resolve_settings(fake_local_embedding.engine.id, {"dimension": dimension, "gpu_mb": memory})
    scheduler.start()
    yield scheduler
    for event in GATES.values():
        event.set()
    residency().shutdown()
    scheduler.stop(timeout=3)
    ENGINES.clear()


@pytest.fixture
def hosted_engine(machine, monkeypatch):
    import tests.hosting.engine as module

    monkeypatch.setattr(engine_family, "_loaded", dict(engine_family._loaded))
    return engine_family.register(module)


def wait_until(predicate, timeout: float = 5.0, message: str = "condition not reached"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            return value
        time.sleep(0.02)
    raise AssertionError(message)


def status(scheduler: Scheduler, task_id: int) -> str:
    return scheduler.task(task_id).status


def running(scheduler: Scheduler, task_id: int) -> bool:
    return status(scheduler, task_id) == "running"


def test_a_task_waits_for_the_memory_of_its_model_then_starts(machine):
    first = work.submit(name="first", model="A")
    wait_until(lambda: running(machine, first.id))

    second = work.submit(name="second", model="B")  # same urgency: it cannot take the GPU from the first one

    wait_until(lambda: machine.task(second.id).waiting_for == ["vram_mb"])
    assert status(machine, second.id) == "queued" and LOG == ["start:first"]
    gate("first").set()
    wait_until(lambda: running(machine, second.id), message="the second task never started")
    assert LOG[:2] == ["start:first", "end:first"]


def test_tasks_using_the_same_model_run_side_by_side(machine):
    first, second = work.submit(name="first", model="A"), work.submit(name="second", model="A")

    wait_until(lambda: running(machine, first.id) and running(machine, second.id))

    assert machine.pool.snapshot()["used"]["vram_mb"] == 600  # one copy of the model, counted once


def test_a_more_urgent_task_makes_a_running_one_yield_and_it_resumes_afterwards(machine):
    low = work.submit(name="low", model="A", priority=5)
    wait_until(lambda: running(machine, low.id))

    high = work.submit(name="high", model="B", priority=1)

    wait_until(lambda: running(machine, high.id), message="the urgent task never started")
    assert LOG == ["start:low", "start:high"]  # the low one stopped at a checkpoint
    assert status(machine, low.id) == "queued" and machine.task(low.id).waiting_for == ["vram_mb"]
    gate("high").set()
    wait_until(lambda: LOG.count("start:low") == 2, message="the low-priority task never resumed")
    gate("low").set()
    wait_until(lambda: status(machine, low.id) == "completed")
    assert LOG == ["start:low", "start:high", "end:high", "start:low", "end:low"]
    assert machine.task(low.id).attempts == 1  # being displaced is not a failed attempt


def test_a_task_is_never_displaced_by_one_that_is_not_more_urgent(machine):
    first = work.submit(name="first", model="A", priority=2)
    wait_until(lambda: running(machine, first.id))

    work.submit(name="same", model="B", priority=2)
    work.submit(name="later", model="B", priority=5)
    time.sleep(0.3)

    assert status(machine, first.id) == "running" and LOG == ["start:first"]


def test_only_the_tasks_that_are_needed_are_displaced(machine):
    big = work.submit(name="big", model="A", priority=2)  # 600 MB
    small = work.submit(name="small", model="C", priority=3)  # 100 MB, 300 MB stay free
    wait_until(lambda: running(machine, big.id) and running(machine, small.id))

    urgent = work.submit(name="urgent", model="D", priority=1)  # needs 500: 200 are missing

    wait_until(lambda: running(machine, urgent.id), message="the urgent task never started")
    assert status(machine, big.id) == "queued"  # freeing the small one would not have been enough
    assert running(machine, small.id) and LOG.count("start:small") == 1


def test_running_now_displaces_even_an_urgent_task(machine):
    urgent = work.submit(name="urgent", model="A", priority=1)
    wait_until(lambda: running(machine, urgent.id))

    now = work.submit(name="now", model="B", priority=0)

    wait_until(lambda: running(machine, now.id))
    assert status(machine, urgent.id) == "queued"


def test_a_task_that_does_not_yield_is_reported_and_waited_for(machine, monkeypatch):
    monkeypatch.setattr(  # `lazy_bird.tasks.scheduler` names the function of the package, so go through the class
        sys.modules[Scheduler.__module__],
        "smart_memory",
        lambda: SimpleNamespace(enable=True, fallback="wait", interrupt_timeout_seconds=0.3),
    )
    events = []
    publish = machine.events.publish
    monkeypatch.setattr(machine.events, "publish", lambda event: (events.append(event), publish(event)))
    stuck = stubborn.submit(name="stuck", model="A", priority=5)
    wait_until(lambda: running(machine, stuck.id))

    urgent = work.submit(name="urgent", model="B", priority=1)

    wait_until(lambda: {"type": "task_unresponsive", "task_id": stuck.id, "released": []} in events, message="the stuck task was not reported")
    assert status(machine, urgent.id) == "queued" and running(machine, stuck.id)  # nothing can take its place by force
    gate("stuck").set()
    wait_until(lambda: running(machine, urgent.id), message="the urgent task did not start once the stuck one ended")


def test_a_task_whose_model_can_never_fit_is_refused_when_it_is_submitted(machine):
    ENGINES["huge"] = engine_family.resolve_settings(ENGINES["A"].engine.id, {"dimension": 9, "gpu_mb": 2000})

    with pytest.raises(InsufficientResourcesError) as error:
        work.submit(name="huge", model="huge")

    assert error.value.code == "insufficient_memory"
    assert "use a smaller model" in error.value.message and "Required memory: 2,000 MB" in error.value.message
    assert machine.tasks() == []


def test_with_smart_memory_off_tasks_run_without_any_memory_check(machine):
    preferences.update_preferences({"smart-memory": {"enable": False}})
    ENGINES["huge"] = engine_family.resolve_settings(ENGINES["A"].engine.id, {"dimension": 9, "gpu_mb": 5000})

    first = work.submit(name="first", model="huge")
    second = work.submit(name="second", model="A")

    wait_until(lambda: running(machine, first.id) and running(machine, second.id))  # neither waits for the other
    assert machine.pool.snapshot()["holders"] == {}


def test_the_models_of_a_finished_task_stay_loaded_but_give_way(machine, fake_local_embedding):
    first = work.submit(name="first", model="A")
    wait_until(lambda: running(machine, first.id))
    gate("first").set()
    wait_until(lambda: status(machine, first.id) == "completed")
    assert fake_local_embedding.unloads == [] and machine.pool.snapshot()["used"]["vram_mb"] == 600

    second = work.submit(name="second", model="B")  # equal urgency, but the idle model is simply evicted

    wait_until(lambda: running(machine, second.id))
    assert [m.dimension for m in fake_local_embedding.unloads] == [3]


@task("test.hosted_stubborn", title="Stubborn {name}", resources={"cpu": 1}, engines=lambda name, model: [ENGINES[model]])
def hosted_stubborn(ctx: TaskContext, name: str, model: str) -> str:
    """Sits in one long model call: it never reaches a checkpoint."""
    LOG.append(f"start:{name}")
    ENGINES[model].call("sleep", 30)
    LOG.append(f"end:{name}")
    return name


def test_a_stuck_task_is_forced_out_by_taking_its_hosted_model_away(machine, hosted_engine, monkeypatch):
    monkeypatch.setattr(
        sys.modules[Scheduler.__module__],
        "smart_memory",
        lambda: SimpleNamespace(enable=True, fallback="wait", interrupt_timeout_seconds=0.5),
    )
    ENGINES["H1"] = engine_family.resolve_settings(hosted_engine.id, {"dimension": 3, "gpu_mb": 600})
    ENGINES["H2"] = engine_family.resolve_settings(hosted_engine.id, {"dimension": 5, "gpu_mb": 600})
    stuck = hosted_stubborn.submit(name="stuck", model="H1", priority=5)
    wait_until(lambda: LOG == ["start:stuck"] and machine.resources()["models"] and machine.resources()["models"][0]["pid"], message="the model never loaded")
    pid = machine.resources()["models"][0]["pid"]

    urgent = work.submit(name="urgent", model="H2", priority=1)

    wait_until(lambda: running(machine, urgent.id), timeout=10, message="the urgent task never got the memory")
    assert not psutil.pid_exists(pid)  # the model's process was ended
    assert status(machine, stuck.id) == "queued" and machine.task(stuck.id).attempts == 0  # sent back to the queue, nothing lost
    gate("urgent").set()
    wait_until(lambda: status(machine, urgent.id) == "completed")
