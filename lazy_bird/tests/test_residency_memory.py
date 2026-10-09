"""Residency with smart memory: models hold the memory they take, idle ones give way, big ones fall back or are refused."""

import threading
import time

import pytest

import lazy_bird.residency as residency_module
import lazy_bird.tasks as tasks_module
from lazy_bird import preferences
from lazy_bird.embedding import embed_texts, engine_family
from lazy_bird.errors import InsufficientResourcesError, UnavailableError
from lazy_bird.residency import MemoryPending, acting_as, residency
from lazy_bird.tasks.resources import ResourcePool
from lazy_bird.tasks.scheduler import Scheduler


@pytest.fixture
def machine(migrated_database, monkeypatch):
    """A machine with 1000 MB of GPU memory and 4000 MB of RAM (nothing else running on it)."""
    pool = ResourcePool({"cpu": 8, "vram_mb": 1000, "ram_mb": 4000})
    monkeypatch.setattr(tasks_module, "_scheduler", Scheduler(pool, workers=2, poll_interval=0.02))
    return pool


def model(fake, **settings):
    return engine_family.resolve_settings(fake.engine.id, settings)


def holders(pool: ResourcePool) -> dict[str, dict]:
    return {holder.split(":", 2)[2]: needs for holder, needs in pool.snapshot()["holders"].items()}


def test_a_loaded_model_holds_its_memory_and_stays_loaded_while_idle(fake_local_embedding, machine):
    small = model(fake_local_embedding, gpu_mb=600)

    embed_texts(["a"], small)
    embed_texts(["b"], small)

    assert len(fake_local_embedding.loads) == 1  # the second call found it still loaded
    assert fake_local_embedding.unloads == []
    assert machine.snapshot()["used"] == {"vram_mb": 600}


def test_an_idle_model_is_evicted_when_another_one_needs_the_room(fake_local_embedding, machine):
    embed_texts(["a"], model(fake_local_embedding, dimension=3, gpu_mb=700))

    embed_texts(["a"], model(fake_local_embedding, dimension=5, gpu_mb=600))

    assert [m.dimension for m in fake_local_embedding.unloads] == [3]
    assert machine.snapshot()["used"] == {"vram_mb": 600}


def test_only_idle_models_holding_the_missing_resource_are_evicted(fake_local_embedding, machine):
    embed_texts(["a"], model(fake_local_embedding, dimension=3, device="cpu", cpu_mb=500))  # lives in RAM
    embed_texts(["a"], model(fake_local_embedding, dimension=4, gpu_mb=700))  # lives in VRAM

    embed_texts(["a"], model(fake_local_embedding, dimension=5, gpu_mb=600))

    assert [m.dimension for m in fake_local_embedding.unloads] == [4]  # the RAM model was no obstacle
    assert machine.snapshot()["used"] == {"ram_mb": 500, "vram_mb": 600}


def test_the_least_recently_used_idle_model_goes_first(fake_local_embedding, machine):
    for dimension in (3, 4):
        embed_texts(["a"], model(fake_local_embedding, dimension=dimension, gpu_mb=400))
    embed_texts(["a"], model(fake_local_embedding, dimension=3, gpu_mb=400))  # 3 was used again after 4

    embed_texts(["a"], model(fake_local_embedding, dimension=5, gpu_mb=400))

    assert [m.dimension for m in fake_local_embedding.unloads] == [4]


def test_a_model_in_use_is_never_evicted(fake_local_embedding, machine):
    busy = model(fake_local_embedding, dimension=3, gpu_mb=700)
    other = model(fake_local_embedding, dimension=5, gpu_mb=600)

    with busy.loaded():
        with pytest.raises(MemoryPending) as pending:
            residency().reserve(other, lessee="task:1", priority=5)

    assert pending.value.missing == {"vram_mb"}
    assert fake_local_embedding.unloads == []


def test_a_caller_waits_until_the_memory_it_needs_is_free(fake_local_embedding, machine):
    busy = model(fake_local_embedding, dimension=3, gpu_mb=700)
    other = model(fake_local_embedding, dimension=5, gpu_mb=600)
    result = []

    holder = threading.Event()

    def hold_then_release():
        with busy.loaded():
            holder.set()
            time.sleep(0.3)

    threading.Thread(target=hold_then_release).start()
    holder.wait(2)
    started = time.monotonic()
    result.append(embed_texts(["a"], other))  # blocks while `busy` is in use, then evicts it

    assert time.monotonic() - started >= 0.2
    assert result and [m.dimension for m in fake_local_embedding.unloads] == [3]


def test_a_caller_gives_up_when_the_memory_stays_busy(fake_local_embedding, machine, monkeypatch):
    monkeypatch.setattr(residency_module, "WAIT_TIMEOUT_SECONDS", 0.3)
    busy = model(fake_local_embedding, dimension=3, gpu_mb=700)

    with busy.loaded():
        with pytest.raises(UnavailableError) as error:
            embed_texts(["a"], model(fake_local_embedding, dimension=5, gpu_mb=600))

    assert error.value.code == "resources_busy"


# -------------------------------------------------------------------- fallback

def test_with_the_wait_policy_a_model_waits_for_gpu_memory(fake_local_embedding, machine):
    preferences.update_preferences({"smart-memory": {"fallback": "wait"}})
    other = model(fake_local_embedding, dimension=5, gpu_mb=600, cpu_mb=300)

    with model(fake_local_embedding, dimension=3, gpu_mb=700).loaded():
        with pytest.raises(MemoryPending) as pending:
            residency().reserve(other, lessee="task:1", priority=5)

    assert pending.value.missing == {"vram_mb"}
    assert fake_local_embedding.devices == ["gpu"]  # nothing was loaded on the CPU


def test_with_the_cpu_policy_a_model_that_does_not_fit_on_the_gpu_goes_to_the_cpu(fake_local_embedding, machine):
    preferences.update_preferences({"smart-memory": {"fallback": "cpu"}})
    other = model(fake_local_embedding, dimension=5, gpu_mb=600, cpu_mb=300)

    with model(fake_local_embedding, dimension=3, gpu_mb=700).loaded():
        vectors = embed_texts(["ab"], other)

    assert vectors
    assert fake_local_embedding.devices == ["gpu", "cpu"]
    assert fake_local_embedding.last_settings.device == "cpu"  # the operation saw where the model lives
    assert machine.snapshot()["used"] == {"vram_mb": 700, "ram_mb": 300}


def test_with_the_cpu_policy_the_gpu_is_still_preferred_when_it_fits(fake_local_embedding, machine):
    preferences.update_preferences({"smart-memory": {"fallback": "cpu"}})

    embed_texts(["a"], model(fake_local_embedding, gpu_mb=600, cpu_mb=300))

    assert fake_local_embedding.devices == ["gpu"]


def test_a_device_chosen_in_the_preset_is_never_replaced_by_the_fallback(fake_local_embedding, machine):
    preferences.update_preferences({"smart-memory": {"fallback": "cpu"}})
    pinned = model(fake_local_embedding, dimension=5, device="gpu", gpu_mb=600, cpu_mb=300)

    with model(fake_local_embedding, dimension=3, gpu_mb=700).loaded():
        with pytest.raises(MemoryPending):
            residency().reserve(pinned, lessee="task:1", priority=5)


# ------------------------------------------------------------ models too big
def test_a_model_larger_than_the_machine_is_refused_with_the_numbers(fake_local_embedding, machine):
    huge = model(fake_local_embedding, gpu_mb=2000)

    with pytest.raises(InsufficientResourcesError) as error:
        embed_texts(["a"], huge)

    assert error.value.code == "insufficient_memory"
    assert "use a smaller model" in error.value.message
    assert "Required memory: 2,000 MB" in error.value.message and "available memory: 1,000 MB" in error.value.message
    assert error.value.details["required_mb"] == 2000 and error.value.details["available_mb"] == 1000
    assert fake_local_embedding.loads == []


def test_a_model_that_only_fits_on_the_cpu_is_refused_unless_the_cpu_fallback_is_on(fake_local_embedding, machine):
    big_for_gpu = model(fake_local_embedding, gpu_mb=2000, cpu_mb=1000)

    with pytest.raises(InsufficientResourcesError) as error:
        residency().check(big_for_gpu)
    assert "fallback to 'cpu'" in error.value.message

    preferences.update_preferences({"smart-memory": {"fallback": "cpu"}})
    residency().check(big_for_gpu)  # fits in RAM
    embed_texts(["a"], big_for_gpu)
    assert fake_local_embedding.devices == ["cpu"]


def test_memory_used_by_other_programs_counts_against_the_model(fake_local_embedding, machine):
    machine.monitor = lambda: {"vram_mb": 300}  # another program holds most of the GPU

    with pytest.raises(InsufficientResourcesError) as error:
        embed_texts(["a"], model(fake_local_embedding, gpu_mb=500))

    assert "available memory: 300 MB" in error.value.message


def test_ram_is_watched_too(fake_local_embedding, machine):
    machine.monitor = lambda: {"ram_mb": 200}
    preferences.update_preferences({"smart-memory": {"fallback": "cpu"}})

    with pytest.raises(InsufficientResourcesError) as error:
        embed_texts(["a"], model(fake_local_embedding, device="cpu", cpu_mb=500))

    assert "available memory: 200 MB" in error.value.message


# ------------------------------------------------------------------- unsupervised
def test_with_smart_memory_off_nothing_is_accounted_and_nothing_is_kept(fake_local_embedding, machine):
    preferences.update_preferences({"smart-memory": {"enable": False}})
    huge = model(fake_local_embedding, gpu_mb=5000)  # would be refused otherwise

    embed_texts(["a"], huge)

    assert machine.snapshot()["holders"] == {}
    assert len(fake_local_embedding.unloads) == 1  # freed right after the call, like before smart memory


def test_turning_smart_memory_off_unloads_idle_models(fake_local_embedding, machine):
    embed_texts(["a"], model(fake_local_embedding, gpu_mb=600))
    assert fake_local_embedding.unloads == []

    preferences.update_preferences({"smart-memory": {"enable": False}})
    preferences.apply_preferences()

    assert len(fake_local_embedding.unloads) == 1
    assert machine.snapshot()["holders"] == {}


def test_shutting_down_unloads_idle_models(fake_local_embedding, machine):
    embed_texts(["a"], model(fake_local_embedding, gpu_mb=600))

    residency().shutdown()

    assert len(fake_local_embedding.unloads) == 1 and machine.snapshot()["used"] == {}


# ------------------------------------------------------------------ reservations
def test_a_reservation_holds_the_memory_without_loading_the_model(fake_local_embedding, machine):
    resolved = model(fake_local_embedding, gpu_mb=600)

    residency().reserve(resolved, lessee="task:1", priority=5)

    assert machine.snapshot()["used"] == {"vram_mb": 600} and fake_local_embedding.loads == []
    residency().release_lessee("task:1")
    assert machine.snapshot()["used"] == {} and fake_local_embedding.loads == []  # never loaded: nothing to keep


def test_a_task_uses_the_model_reserved_for_it_wherever_it_was_placed(fake_local_embedding, machine):
    preferences.update_preferences({"smart-memory": {"fallback": "cpu"}})
    resolved = model(fake_local_embedding, dimension=5, gpu_mb=600, cpu_mb=300)

    with model(fake_local_embedding, dimension=3, gpu_mb=700).loaded():
        residency().reserve(resolved, lessee="task:1", priority=5)  # placed on the CPU
        with acting_as("task:1", 5):
            embed_texts(["a"], resolved)
        residency().release_lessee("task:1")

    assert fake_local_embedding.devices == ["gpu", "cpu"]
    assert machine.snapshot()["used"] == {"vram_mb": 700, "ram_mb": 300}  # both stay loaded, idle


def test_the_memory_only_a_task_holds_is_what_stopping_it_would_release(fake_local_embedding, machine):
    resolved = model(fake_local_embedding, gpu_mb=600)
    shared = model(fake_local_embedding, dimension=7, gpu_mb=100)
    residency().reserve(resolved, lessee="task:1", priority=5)
    residency().reserve(shared, lessee="task:1", priority=5)
    residency().reserve(shared, lessee="task:2", priority=5)

    assert residency().exclusive_to("task:1") == {"vram_mb": 600}  # the shared one would stay in use
    assert residency().exclusive_to("task:2") == {}


def test_lowering_the_capacity_unloads_the_idle_models_that_no_longer_fit(fake_local_embedding, machine):
    embed_texts(["a"], model(fake_local_embedding, dimension=3, gpu_mb=400))
    embed_texts(["a"], model(fake_local_embedding, dimension=4, gpu_mb=500))  # used last
    machine.capacity["vram_mb"] = 600  # e.g. tasks.resources now keeps GPU memory for another program

    residency().fit_to_capacity()

    assert [m.dimension for m in fake_local_embedding.unloads] == [3]  # one was enough, the least recently used
    assert machine.snapshot()["used"] == {"vram_mb": 500}


def test_a_model_in_use_stays_even_above_a_lowered_capacity(fake_local_embedding, machine):
    busy = model(fake_local_embedding, gpu_mb=800)
    with busy.loaded():
        machine.capacity["vram_mb"] = 600
        residency().fit_to_capacity()
        assert fake_local_embedding.unloads == []
    residency().fit_to_capacity()  # once idle, it goes
    assert len(fake_local_embedding.unloads) == 1
