"""Models in host processes: where they live, what happens when they fail, how a stuck user is forced out."""

import os
import threading
import time

import psutil
import pytest

import lazy_bird.tasks as tasks_module
from lazy_bird import preferences
from lazy_bird.embedding import engine_family
from lazy_bird.engine_host import EngineProcessError
from lazy_bird.errors import InsufficientResourcesError
from lazy_bird.residency import ModelEvicted, acting_as, residency
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler


@pytest.fixture
def hosted_engine(crud_database, monkeypatch):
    import tests.hosting.engine as module

    monkeypatch.setattr(engine_family, "_loaded", dict(engine_family._loaded))
    return engine_family.register(module)


@pytest.fixture
def machine(migrated_database, monkeypatch):
    """A machine with 1000 MB of GPU memory and 4000 MB of RAM."""
    pool = ResourcePool({"cpu": 8, "vram_mb": 1000, "ram_mb": 4000})
    monkeypatch.setattr(tasks_module, "_scheduler", Scheduler(pool, workers=2, poll_interval=0.02))
    return pool


def resolved(engine, **settings):
    return engine_family.resolve_settings(engine.id, settings)


def wait_until(predicate, timeout=10.0, message="condition not reached"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.02)
    raise AssertionError(message)


def children():
    return psutil.Process().children()


def test_a_model_lives_in_a_process_of_its_own_and_ends_with_its_last_user(hosted_engine, tmp_path):
    marker = tmp_path / "unloaded"
    model = resolved(hosted_engine, marker=str(marker))

    with model.loaded():
        [[first, _]] = model.call("embed", ["a"])
        [[second, _]] = model.call("embed", ["bb"])
        host = psutil.Process(int(first))
        assert host.is_running() and host.ppid() == os.getpid()

    assert first == second != float(os.getpid())  # one process, loaded once, not the server
    wait_until(lambda: not psutil.pid_exists(int(first)), message="the host process is still running")
    assert marker.read_text() == str(int(first))  # unload ran in the host, before it ended
    assert children() == []


def test_isolation_can_be_turned_off(hosted_engine):
    preferences.update_preferences({"smart-memory": {"isolate_models": False}})

    [[pid, _]] = resolved(hosted_engine).call("embed", ["a"])

    assert pid == float(os.getpid())


def test_an_error_in_the_host_is_reported_and_the_model_stays_usable(hosted_engine):
    model = resolved(hosted_engine)

    with model.loaded():
        [[before, _]] = model.call("embed", ["a"])
        with pytest.raises(EngineProcessError) as error:
            model.call("fail")
        [[after, _]] = model.call("embed", ["a"])

    assert error.value.message == "bad input" and error.value.details["type"] == "ValueError"
    assert "ValueError" in error.value.details["traceback"]
    assert before == after  # the same process kept the model


def test_a_crashed_host_does_not_take_the_server_down_and_is_replaced_on_the_next_call(hosted_engine):
    model = resolved(hosted_engine)

    with model.loaded():
        [[before, _]] = model.call("embed", ["a"])
        with pytest.raises(EngineProcessError) as error:
            model.call("crash")
        [[after, _]] = model.call("embed", ["a"])

    assert error.value.code == "engine_crashed" and error.value.details["exit_code"] == 3
    assert after != before and not psutil.pid_exists(int(before))
    assert children() == []


def test_a_model_that_fails_to_load_leaves_no_process_behind(hosted_engine):
    with pytest.raises(EngineProcessError) as error:
        resolved(hosted_engine, fail_load=True).call("embed", ["a"])

    assert "CUDA out of memory" in error.value.message
    wait_until(lambda: children() == [], message="a process was left running")


def test_a_module_that_cannot_be_imported_by_name_stays_in_the_server(fake_local_embedding):
    resolved_fake = engine_family.resolve()

    assert resolved_fake.call("embed", ["a"])  # the fake engine is a module built on the fly: no child process
    assert children() == []


def test_loaded_models_are_described_with_their_process_and_memory(hosted_engine, machine):
    model = resolved(hosted_engine, gpu_mb=300)

    with model.loaded():
        model.call("embed", ["a"])
        [described] = residency().describe()

    assert described["engine"] == "hosted-fake" and described["needs"] == {"vram_mb": 300} and described["idle"] is False
    assert described["pid"] != os.getpid() and described["memory"]["rss_mb"] > 10
    [idle] = residency().describe()  # kept while idle, accounted
    assert idle["idle"] is True and idle["pid"] == described["pid"]


def test_a_user_that_does_not_step_aside_is_forced_out_by_ending_its_models_process(hosted_engine, machine):
    stuck = resolved(hosted_engine, dimension=3, gpu_mb=600)
    urgent = resolved(hosted_engine, dimension=5, gpu_mb=600)
    residency().reserve(stuck, lessee="task:9", priority=5)
    outcome = []

    def stuck_task():
        with acting_as("task:9", 5):
            try:
                stuck.call("sleep", 30)  # never reaches a checkpoint
            except BaseException as error:
                outcome.append(error)

    thread = threading.Thread(target=stuck_task)
    thread.start()
    wait_until(lambda: residency().describe() and residency().describe()[0]["pid"], message="the model never loaded")
    pid = residency().describe()[0]["pid"]
    assert machine.snapshot()["used"] == {"vram_mb": 600}

    released = residency().force_release("task:9")

    assert released == ["hosted-fake"]
    thread.join(5)
    assert not thread.is_alive() and isinstance(outcome[0], ModelEvicted)  # the stuck call failed at once
    assert not psutil.pid_exists(pid) and machine.snapshot()["used"] == {}  # and its memory is back
    with acting_as("task:9", 5), pytest.raises(ModelEvicted):
        stuck.call("embed", ["a"])  # it cannot get the model back behind the scheduler's back
    residency().release_lessee("task:9")
    assert urgent.call("embed", ["a"]) and machine.snapshot()["used"] == {"vram_mb": 600}  # the urgent one has the room


def test_models_shared_with_others_are_not_taken_away(hosted_engine, machine):
    shared = resolved(hosted_engine, gpu_mb=300)
    residency().reserve(shared, lessee="task:9", priority=5)
    residency().reserve(shared, lessee="task:10", priority=5)

    assert residency().force_release("task:9") == []
    residency().release_lessee("task:9")
    residency().release_lessee("task:10")


def test_a_model_taken_away_while_it_loads_is_freed_as_soon_as_it_is_loaded(hosted_engine, machine, monkeypatch):
    from lazy_bird.engine_host import EngineHost

    loading, release = threading.Event(), threading.Event()
    real_start = EngineHost.start.__func__

    def slow_start(cls, module_name, settings, model):
        host = real_start(cls, module_name, settings, model)
        loading.set()
        release.wait(5)  # the server stops right now, while the model is loading
        return host

    monkeypatch.setattr(EngineHost, "start", classmethod(slow_start))
    model = resolved(hosted_engine, gpu_mb=300)
    outcome = []

    def call():
        try:
            outcome.append(model.call("embed", ["a"]))
        except BaseException as error:
            outcome.append(error)

    thread = threading.Thread(target=call)
    thread.start()
    assert loading.wait(10), outcome
    residency().shutdown()
    release.set()
    thread.join(10)

    assert isinstance(outcome[0], ModelEvicted)
    wait_until(lambda: children() == [], message="the model loaded during shutdown was left running")
    assert machine.snapshot()["used"] == {}
