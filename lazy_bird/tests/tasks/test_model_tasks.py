from lazy_bird.tasks.default import models as model_tasks
from tests.tools.gguf_factory import write_gguf


def test_import_task_copies_and_registers_a_local_model(crud_database, model_cache, tmp_path):
    source = tmp_path / "downloads" / "tiny-Q4_K_M.gguf"
    source.parent.mkdir()
    write_gguf(source, {"general.architecture": "llama", "general.name": "Tiny"})

    result = model_tasks.import_model.run(path=str(source), name="Tiny Llama")

    from lazy_bird.crud import llm_model

    model = llm_model.get(result["model_id"])
    assert (model.hf_path, model.name, model.source, model.formats) == ("local/Tiny-Llama", "Tiny Llama", "local", ["gguf"])
    assert model.local_path.startswith(str(model_cache.root))


def test_download_task_registers_the_downloaded_snapshot(crud_database, model_cache, monkeypatch):
    snapshot = model_cache("org/model", {"model.safetensors": b"w"})
    calls = []

    def fake_download(repo_id, *, files, revision, progress):
        calls.append((repo_id, files))
        progress(5, 10)
        return str(snapshot)

    monkeypatch.setattr(model_tasks, "download_model", fake_download)

    result = model_tasks.download.run(hf_path="org/model", files=["model.safetensors"])

    assert calls == [("org/model", ["model.safetensors"])]
    assert result["formats"] == ["safetensors"]
