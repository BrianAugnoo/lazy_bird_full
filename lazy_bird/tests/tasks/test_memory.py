import threading
import time

from lazy_bird.tasks import memory
from lazy_bird.tasks.memory import Candidate, choose_victims
from lazy_bird.tasks.resources import ResourcePool


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
    monkeypatch.setattr(memory, "_free_ram_mb", lambda: 2048.0)
    monkeypatch.setattr(memory, "_free_vram_mb", lambda: None)

    assert memory.system_free() == {"ram_mb": 2048.0}


def test_system_free_is_read_once_per_second(monkeypatch):
    reads = []
    monkeypatch.setattr(memory, "_cached", None)
    monkeypatch.setattr(memory, "_free_ram_mb", lambda: reads.append(1) or 1000.0)
    monkeypatch.setattr(memory, "_free_vram_mb", lambda: 500.0)

    first, second = memory.system_free(), memory.system_free()

    assert first == second == {"ram_mb": 1000.0, "vram_mb": 500.0}
    assert len(reads) == 1
    monkeypatch.setattr(memory, "READ_CACHE_SECONDS", 0)
    memory.system_free()
    assert len(reads) == 2


def test_the_real_machine_reports_its_ram():
    free = memory.system_free()

    assert free["ram_mb"] > 0


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
