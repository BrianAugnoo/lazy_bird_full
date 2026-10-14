import os
import threading
import time
import subprocess
from types import SimpleNamespace

import pytest

from lazy_bird.tasks import memory, resources
from lazy_bird.tasks.memory import Candidate, choose_victims
from lazy_bird.tasks.resources import ResourcePool, detect_capacity


def victims(deficit, *candidates):
    chosen = choose_victims(deficit, [Candidate(*candidate) for candidate in candidates])
    return None if chosen is None else sorted(candidate.holder for candidate in chosen)


# ------------------------------------------------------------------- who yields
def test_only_what_is_needed_is_preempted():
    # 3 free, the request needs 5: 2 are missing. B alone gives 4, C alone 0.5.
    assert victims({"vram_mb": 2}, ("B", 2, {"vram_mb": 4}), ("C", 3, {"vram_mb": 0.5})) == ["B"]


def test_several_tasks_are_asked_only_when_one_is_not_enough():
    assert victims({"vram_mb": 4}, ("B", 2, {"vram_mb": 3}), ("C", 3, {"vram_mb": 2})) == ["B", "C"]
    assert victims({"vram_mb": 6}, ("B", 2, {"vram_mb": 3}), ("C", 3, {"vram_mb": 2})) is None


def test_among_equally_small_sets_the_least_urgent_work_yields():
    assert victims({"vram_mb": 1}, ("urgent", 2, {"vram_mb": 5}), ("background", 5, {"vram_mb": 5})) == ["background"]


def test_among_equally_urgent_work_the_one_giving_back_the_least_yields():
    assert victims({"vram_mb": 1}, ("big", 5, {"vram_mb": 9}), ("small", 5, {"vram_mb": 2})) == ["small"]


def test_every_missing_resource_must_be_covered():
    candidates = (("gpu-task", 5, {"vram_mb": 8}), ("ram-task", 5, {"ram_mb": 8}))
    assert victims({"vram_mb": 4, "ram_mb": 4}, *candidates) == ["gpu-task", "ram-task"]
    assert victims({"ram_mb": 4}, *candidates) == ["ram-task"]


def test_nothing_is_preempted_when_nothing_is_missing():
    assert victims({}, ("B", 5, {"vram_mb": 4})) == []
    assert victims({"vram_mb": 0}, ("B", 5, {"vram_mb": 4})) == []


# -------------------------------------------------------------- what is free now
def test_system_free_reports_what_it_can_read_and_leaves_out_the_rest(monkeypatch):
    monkeypatch.setattr(memory, "_cached", None)
    monkeypatch.setattr(memory, "_ram_usage", lambda: {"total_mb": 4096.0, "used_mb": 2048.0, "available_mb": 2048.0})
    monkeypatch.setattr(memory, "_vram_usage", lambda: None)

    assert memory.system_free() == {"ram_mb": 2048.0}


def test_system_free_is_read_once_per_second(monkeypatch):
    reads = []
    monkeypatch.setattr(memory, "_cached", None)
    monkeypatch.setattr(memory, "_ram_usage", lambda: reads.append(1) or {"total_mb": 4000.0, "used_mb": 3000.0, "available_mb": 1000.0})
    monkeypatch.setattr(memory, "_vram_usage", lambda: {"total_mb": 1000.0, "used_mb": 400.0, "available_mb": 500.0})

    first, second = memory.system_free(), memory.system_free()

    assert first == second == {"ram_mb": 1000.0, "vram_mb": 500.0}
    assert len(reads) == 1
    monkeypatch.setattr(memory, "READ_CACHE_SECONDS", 0)
    memory.system_free()
    assert len(reads) == 2


def test_display_and_admission_share_a_sample_and_callers_cannot_change_it(monkeypatch):
    monkeypatch.setattr(memory, "_cached", None)
    monkeypatch.setattr(memory, "_ram_usage", lambda: {"total_mb": 4000.0, "used_mb": 3000.0, "available_mb": 1000.0})
    monkeypatch.setattr(memory, "_vram_usage", lambda: None)
    sample = memory.system_usage()
    sample["ram_mb"]["available_mb"] = 42
    assert memory.system_free() == {"ram_mb": 1000.0}
    assert memory.system_usage()["ram_mb"]["used_mb"] == 3000.0
    monkeypatch.setattr(memory, "READ_CACHE_SECONDS", 0)
    monkeypatch.setattr(memory, "_ram_usage", lambda: None)
    assert memory.system_usage() == {"ram_mb": None, "vram_mb": None}
    assert memory.system_free() == {}


def test_ram_usage_counts_reclaimable_cache_as_available(monkeypatch):
    import psutil

    monkeypatch.setattr(psutil, "virtual_memory", lambda: SimpleNamespace(total=4096 * 1024**2, available=2048 * 1024**2, used=1500 * 1024**2))
    assert memory._ram_usage() == {"total_mb": 4096.0, "used_mb": 2048.0, "available_mb": 2048.0}


def test_gpu_usage_reads_the_pool_device_and_preserves_driver_reserved_memory(monkeypatch):
    calls = []
    monkeypatch.setattr(memory, "_nvidia_smi", "nvidia-smi")
    monkeypatch.setattr(memory.subprocess, "run", lambda args, **kwargs: calls.append((args, kwargs)) or SimpleNamespace(stdout="16311, 1003, 15048\n"))
    assert memory._vram_usage() == {"total_mb": 16311.0, "used_mb": 1003.0, "available_mb": 15048.0}
    assert "--id=0" in calls[0][0]
    assert "--query-gpu=memory.total,memory.used,memory.free" in calls[0][0]
    assert calls[0][1]["timeout"] == 5


@pytest.mark.parametrize("output", ["", "N/A, N/A, N/A", "16311, nan, 15048", "16311, -1, 15048", "1000, 2000, 0", "1, 2"])
def test_bad_gpu_readings_are_unavailable(monkeypatch, output):
    monkeypatch.setattr(memory, "_nvidia_smi", "nvidia-smi")
    monkeypatch.setattr(memory.subprocess, "run", lambda *args, **kwargs: SimpleNamespace(stdout=output))
    assert memory._vram_usage() is None


def test_gpu_timeout_and_missing_driver_are_unavailable(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("nvidia-smi", 5)

    monkeypatch.setattr(memory, "_nvidia_smi", "nvidia-smi")
    monkeypatch.setattr(memory.subprocess, "run", timeout)
    assert memory._vram_usage() is None
    monkeypatch.setattr(memory, "_nvidia_smi", None)
    assert memory._vram_usage() is None


def test_gpu_capacity_uses_the_same_driver_total_without_loading_torch(monkeypatch):
    monkeypatch.setattr(memory, "system_usage", lambda: {"vram_mb": {"total_mb": 16311.0, "used_mb": 1003.0, "available_mb": 15048.0}})
    assert resources._total_vram_mb() == 16311.0


def test_the_real_machine_reports_its_ram():
    free = memory.system_free()

    assert free["ram_mb"] > 0


def test_the_ram_capacity_is_the_whole_ram_of_the_machine(monkeypatch):
    import psutil

    monkeypatch.delattr(os, "sysconf", raising=False)  # as on Windows
    monkeypatch.setattr(resources, "_total_vram_mb", lambda: 0.0)  # torch is slow to import, and not the point
    total = psutil.virtual_memory().total / 1024**2

    assert detect_capacity()["ram_mb"] == round(total)


# ------------------------------------------------------------ the pool, for real
def test_free_memory_is_capped_by_what_the_machine_reports():
    pool = ResourcePool({"vram_mb": 1000, "ram_mb": 4000}, monitor=lambda: {"vram_mb": 300})  # another program uses the GPU

    assert pool.fits({"vram_mb": 500}) is True  # the pool alone would allow it
    assert pool.fits({"vram_mb": 500}, real=True) is False
    assert pool.deficit({"vram_mb": 500, "ram_mb": 100}, real=True) == {"vram_mb": 200}
    assert pool.free(real=True) == {"vram_mb": 300, "ram_mb": 4000}  # ram is not reported: no limit but the pool


def test_try_acquire_for_real_refuses_what_is_not_really_free():
    pool = ResourcePool({"vram_mb": 1000}, monitor=lambda: {"vram_mb": 300})

    assert pool.try_acquire("a", {"vram_mb": 500}, real=True) is False
    assert pool.try_acquire("a", {"vram_mb": 200}, real=True) is True
    assert pool.held("a") == {"vram_mb": 200}


def test_the_ceiling_counts_what_the_pool_holds_as_releasable():
    pool = ResourcePool({"vram_mb": 1000}, monitor=lambda: {"vram_mb": 100})
    pool.try_acquire("task", {"vram_mb": 400})

    # 100 free + 400 held by a task that could finish: never more than that, however long we wait
    assert pool.ceiling() == {"vram_mb": 500}
    assert ResourcePool({"vram_mb": 1000}).ceiling() == {"vram_mb": 1000}


def test_a_holder_can_be_resized_to_what_it_really_takes():
    pool = ResourcePool({"vram_mb": 1000, "ram_mb": 4000})
    pool.try_acquire("model", {"vram_mb": 800})

    pool.resize("model", {"vram_mb": 300, "ram_mb": 2000})  # measured: less GPU memory, and RAM too

    assert pool.held("model") == {"vram_mb": 300, "ram_mb": 2000}
    assert pool.fits({"vram_mb": 700}) and not pool.fits({"ram_mb": 2500})


def test_a_released_holder_stays_released_when_a_late_measurement_comes():
    pool = ResourcePool({"vram_mb": 1000})
    pool.try_acquire("model", {"vram_mb": 800})
    pool.release("model")

    pool.resize("model", {"vram_mb": 300})

    assert pool.snapshot()["used"] == {} and pool.held("model") == {}


def test_waiting_for_a_release_wakes_up_when_something_is_released():
    pool = ResourcePool({"cpu": 1})
    pool.try_acquire("a", {"cpu": 1})
    woke = []

    waiter = threading.Thread(target=lambda: (pool.wait_for_release(5), woke.append(time.monotonic())))
    started = time.monotonic()
    waiter.start()
    time.sleep(0.05)
    pool.release("a")
    waiter.join(timeout=5)

    assert woke and woke[0] - started < 2


def test_the_machine_is_only_asked_when_memory_is_involved():
    readings = []
    pool = ResourcePool({"cpu": 4, "vram_mb": 1000}, monitor=lambda: readings.append(1) or {"vram_mb": 100})

    assert pool.try_acquire("cpu-only", {"cpu": 1}, real=True)
    assert readings == []  # no nvidia-smi for work that needs only CPU slots
    assert not pool.try_acquire("gpu", {"cpu": 1, "vram_mb": 500}, real=True)
    assert readings == [1]
