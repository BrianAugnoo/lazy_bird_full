from pathlib import Path
from types import SimpleNamespace

from lazy_bird.tools import hf_cache_worker


def make_snapshot(cache_path: Path, repository: str, revision: str = "revision") -> Path:
    snapshot = cache_path / repository / "snapshots" / revision
    snapshot.mkdir(parents=True)
    return snapshot


def test_find_cached_model_paths_ignores_locks_and_invalid_repositories(tmp_path: Path):
    expected = make_snapshot(tmp_path, "models--owner--model")
    make_snapshot(tmp_path / ".locks", "models--ignored--model")
    make_snapshot(tmp_path, "datasets--owner--dataset")
    make_snapshot(tmp_path, "models--owner--multiple", "first")
    make_snapshot(tmp_path, "models--owner--multiple", "second")

    assert hf_cache_worker.find_cached_model_paths(tmp_path) == [
        ("owner/model", expected.resolve())
    ]


def test_sync_cached_models_creates_only_unknown_paths(tmp_path: Path, monkeypatch):
    known = make_snapshot(tmp_path, "models--owner--known")
    new = make_snapshot(tmp_path, "models--owner--new")
    created = []

    monkeypatch.setattr(
        hf_cache_worker.llm_model_crud,
        "get_all",
        lambda: [SimpleNamespace(local_path=str(known))],
    )
    monkeypatch.setattr(
        hf_cache_worker.llm_model_crud,
        "create_from_local_path",
        lambda hf_path, local_path: created.append((hf_path, local_path)),
    )

    assert hf_cache_worker.sync_cached_models(tmp_path) == 1
    assert created == [("owner/new", str(new.resolve()))]


def test_sync_cached_models_skips_models_that_cannot_be_extracted(tmp_path: Path, monkeypatch):
    make_snapshot(tmp_path, "models--owner--invalid")
    monkeypatch.setattr(hf_cache_worker.llm_model_crud, "get_all", lambda: [])
    monkeypatch.setattr(
        hf_cache_worker.llm_model_crud,
        "create_from_local_path",
        lambda *_: (_ for _ in ()).throw(FileNotFoundError("config.json")),
    )

    assert hf_cache_worker.sync_cached_models(tmp_path) == 0
