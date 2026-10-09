import gc
import threading
import weakref

import pytest

from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.embedding import embed_texts, engine_family


def resolve(**kwargs):
    engine = engine_family.resolve()
    return engine_family.resolve_settings(engine.engine.id, kwargs) if kwargs else engine


def test_without_a_lease_every_call_loads_and_frees_the_model(fake_local_embedding):
    resolved = engine_family.resolve()

    embed_texts(["a"], resolved)
    embed_texts(["b"], resolved)

    assert len(fake_local_embedding.loads) == 2
    assert len(fake_local_embedding.unloads) == 2


def test_calls_inside_a_lease_share_one_load_and_the_model_is_freed_after_it(fake_local_embedding):
    resolved = engine_family.resolve()

    with resolved.loaded():
        embed_texts(["a"], resolved)
        embed_texts(["b"], resolved)
        assert (len(fake_local_embedding.loads), len(fake_local_embedding.unloads)) == (1, 0)

    assert len(fake_local_embedding.unloads) == 1


def test_the_model_is_freed_when_the_work_inside_the_lease_fails(fake_local_embedding):
    resolved = engine_family.resolve()

    with pytest.raises(RuntimeError, match="boom"):
        with resolved.loaded():
            embed_texts(["a"], resolved)
            raise RuntimeError("boom")

    assert len(fake_local_embedding.unloads) == 1
    reference = weakref.ref(fake_local_embedding.unloads[0])
    fake_local_embedding.unloads.clear()
    gc.collect()
    assert reference() is None  # nothing keeps the freed model alive


def test_leases_with_the_same_load_key_share_a_model_even_when_other_settings_differ(fake_local_embedding):
    small, large = resolve(batch_size=2), resolve(batch_size=64)

    with small.loaded(), large.loaded():
        embed_texts(["a"], small)
        embed_texts(["b"], large)

    assert len(fake_local_embedding.loads) == 1


def test_settings_that_change_the_loaded_model_get_their_own_load(fake_local_embedding):
    first, second = resolve(dimension=3), resolve(dimension=5)

    with first.loaded(), second.loaded():
        assert embed_texts(["ab"], first) != embed_texts(["ab"], second)

    assert sorted(fake_local_embedding.loads) == [3, 5]
    assert len(fake_local_embedding.unloads) == 2


def test_concurrent_leases_load_the_model_once(fake_local_embedding):
    resolved = engine_family.resolve()
    ready = threading.Barrier(4)

    def work():
        with resolved.loaded():
            ready.wait(timeout=5)  # all four hold a lease at the same time
            embed_texts(["a"], resolved)

    threads = [threading.Thread(target=work) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)

    assert len(fake_local_embedding.loads) == 1
    assert len(fake_local_embedding.unloads) == 1


def test_calls_on_a_shared_model_run_one_at_a_time(fake_local_embedding):
    resolved = engine_family.resolve()
    fake_local_embedding.delay = 0.02

    with resolved.loaded():
        threads = [threading.Thread(target=embed_texts, args=(["a"], resolved)) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)

    assert fake_local_embedding.peak == 1


def test_a_failed_load_leaves_nothing_loaded_and_the_next_call_loads_again(fake_local_embedding):
    resolved = engine_family.resolve()
    real_load = fake_local_embedding.load
    fake_local_embedding.load = lambda settings, model: (_ for _ in ()).throw(MemoryError("no room"))

    with pytest.raises(MemoryError):
        embed_texts(["a"], resolved)
    assert fake_local_embedding.unloads == []

    fake_local_embedding.load = real_load
    assert embed_texts(["a"], resolved)
    assert len(fake_local_embedding.unloads) == 1


def test_an_unload_that_fails_does_not_break_the_caller(fake_local_embedding):
    resolved = engine_family.resolve()
    fake_local_embedding.unload = lambda instance: 1 / 0

    assert embed_texts(["ab"], resolved) == [[0.0, 1.0, 1.0, 0.0]]
    assert embed_texts(["ab"], resolved) == [[0.0, 1.0, 1.0, 0.0]]
    assert len(fake_local_embedding.loads) == 2  # the failed unload did not leave a model behind


def test_api_engines_are_called_directly_without_any_lease(fake_embedding):
    resolved = engine_family.resolve()

    with resolved.loaded():
        assert embed_texts(["ab"], resolved) == [[0.0, 1.0, 1.0, 0.0]]

    assert not resolved.local


def test_embedding_a_file_loads_the_model_once_for_all_its_batches(client, fake_local_embedding, monkeypatch):
    monkeypatch.setattr("lazy_bird.tasks.default.files.EMBEDDING_BATCH", 2)
    file_id = client.post("/files/upload?dir=docs", files={"files": ("many.md", b"a", "text/markdown")}).json()[0]["id"]
    chunk_crud.replace(file_id, [{"content": f"chunk {n}", "start_line": n, "end_line": n} for n in range(1, 8)])
    from lazy_bird.embedding import vector_space
    from lazy_bird.tasks.default.files import embed_file

    target = vector_space(engine_family.resolve())
    embed_file.run(file_id=file_id, target=target, preset_id=fake_local_embedding.preset.id)

    assert database.vector_count(target) == 7
    assert len(fake_local_embedding.loads) == 1  # 4 batches, one load
    assert len(fake_local_embedding.unloads) == 1
