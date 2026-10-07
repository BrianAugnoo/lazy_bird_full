import os
from pathlib import Path

import pytest

from lazy_bird.tools import hf_cache


@pytest.fixture
def source(tmp_path: Path) -> Path:
    folder = tmp_path / "my model"
    (folder / "sub").mkdir(parents=True)
    (folder / "model.safetensors").write_bytes(b"weights")
    (folder / "sub" / "config.json").write_text("{}")
    (folder / ".git").mkdir()
    (folder / ".git" / "HEAD").write_text("ignored")
    return folder


def test_import_copies_a_folder_into_the_cache_layout(source, tmp_path):
    cache = tmp_path / "cache"

    repo_id, snapshot = hf_cache.import_local(source, "My Model!", cache=cache)

    folder = cache / "models--local--My-Model"
    assert repo_id == "local/My-Model"
    assert snapshot.parent == (folder / "snapshots").resolve()
    assert (folder / "refs" / "main").read_text() == snapshot.name
    assert (snapshot / "model.safetensors").read_bytes() == b"weights"
    assert (snapshot / "sub" / "config.json").exists()
    assert not (snapshot / ".git").exists()
    assert len(list((folder / "blobs").iterdir())) == 2


def test_imported_models_survive_the_removal_of_their_source(source, tmp_path):
    cache = tmp_path / "cache"
    hf_cache.import_local(source, "mine", cache=cache)

    for path in sorted(source.rglob("*"), reverse=True):
        path.rmdir() if path.is_dir() else path.unlink()

    [(repo_id, snapshot)] = hf_cache.cached_models(cache)
    assert repo_id == "local/mine"
    assert (snapshot / "model.safetensors").read_bytes() == b"weights"


def test_importing_the_same_content_reuses_its_revision(source, tmp_path):
    cache = tmp_path / "cache"
    progress = []

    first = hf_cache.import_local(source, "mine", cache=cache, progress=lambda done, total: progress.append((done, total)))
    second = hf_cache.import_local(source, "mine", cache=cache)

    assert first == second
    assert progress[-1][0] == progress[-1][1]


def test_a_single_weight_file_can_be_imported(tmp_path):
    weights = tmp_path / "solo.gguf"
    weights.write_bytes(b"GGUF")

    repo_id, snapshot = hf_cache.import_local(weights, "solo", cache=tmp_path / "cache")

    assert [path.name for path in snapshot.iterdir()] == ["solo.gguf"]


def test_the_current_snapshot_follows_refs_main(tmp_path):
    folder = tmp_path / "models--org--model"
    for revision in ("old", "new"):
        (folder / "snapshots" / revision).mkdir(parents=True)
    os.utime(folder / "snapshots" / "old", (2e9, 2e9))
    (folder / "refs").mkdir()
    (folder / "refs" / "main").write_text("new")

    assert hf_cache.current_snapshot(folder).name == "new"
    (folder / "refs" / "main").unlink()
    assert hf_cache.current_snapshot(folder).name == "old"


def test_cached_models_skip_datasets_and_locks(tmp_path):
    for folder in ("models--org--model/snapshots/rev", "datasets--org--data/snapshots/rev", ".locks/models--x--y/snapshots/rev"):
        (tmp_path / folder).mkdir(parents=True)

    assert [repo_id for repo_id, _ in hf_cache.cached_models(tmp_path)] == ["org/model"]


def test_delete_repo_removes_the_cache_folder(source, tmp_path):
    cache = tmp_path / "cache"
    hf_cache.import_local(source, "mine", cache=cache)

    assert hf_cache.delete_repo("local/mine", cache) is True
    assert hf_cache.delete_repo("local/mine", cache) is False


def test_names_must_contain_letters_or_digits():
    with pytest.raises(ValueError):
        hf_cache.slug("///")


def test_staged_files_are_moved_into_the_cache(source, tmp_path):
    cache = tmp_path / "cache"

    repo_id, snapshot = hf_cache.import_local(source, "mine", cache=cache, move=True)

    assert (snapshot / "model.safetensors").read_bytes() == b"weights"
    assert not (source / "model.safetensors").exists()
    assert not (source / "sub" / "config.json").exists()


def test_staged_paths_stay_inside_the_staging_folder(tmp_path):
    folder = hf_cache.staging_folder("My Model", tmp_path)

    assert hf_cache.staged_path("My Model", "sub\\config.json", tmp_path) == folder / "sub" / "config.json"
    for bad in ("../x", "/etc/passwd", "a/../../x", ".git/HEAD", ""):
        with pytest.raises(ValueError):
            hf_cache.staged_path("My Model", bad, tmp_path)
