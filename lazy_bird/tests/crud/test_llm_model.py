import json

import pytest

import lazy_bird.crud.llm_model as llm_model_crud
from lazy_bird.errors import InvalidInputError, NotFoundError
from tests.tools.gguf_factory import write_gguf

CONFIG = json.dumps({"hidden_size": 8, "max_position_embeddings": 128}).encode()


def test_register_reads_formats_files_and_metadata(crud_database, model_cache):
    snapshot = model_cache("org/model", {"model.safetensors": b"w" * 10, "onnx/model.onnx": b"o", "config.json": CONFIG})

    model = llm_model_crud.register("org/model", snapshot)

    assert (model.name, model.source, model.revision) == ("org/model", "huggingface", "rev1")
    assert model.formats == ["safetensors", "onnx"]
    assert model.files == {"safetensors": ["model.safetensors"], "onnx": ["onnx/model.onnx"]}
    assert (model.dimension, model.max_context_length, model.selected_format) == (8, 128, "safetensors")
    assert model.available is True and model.size_mb == 0.0


def test_gguf_models_select_a_preferred_quantization(crud_database, model_cache):
    snapshot = model_cache("org/llm-gguf", {})
    for name in ("llm-Q8_0.gguf", "llm-Q4_K_M.gguf"):
        write_gguf(snapshot / name, {"general.architecture": "llama", "llama.context_length": 4096})

    model = llm_model_crud.register("org/llm-gguf", snapshot)

    assert model.selected_format == "gguf"
    assert model.selected_file == "llm-Q4_K_M.gguf"
    assert llm_model_crud.update(model.id, {"selected_file": "llm-Q8_0.gguf"}).selected_file == "llm-Q8_0.gguf"
    with pytest.raises(InvalidInputError):
        llm_model_crud.update(model.id, {"selected_file": "other.gguf"})


def test_refreshing_keeps_the_user_choices(crud_database, model_cache):
    snapshot = model_cache("org/model", {"model.safetensors": b"w", "onnx/model.onnx": b"o"})
    model = llm_model_crud.register("org/model", snapshot)
    llm_model_crud.update(model.id, {"selected_format": "onnx", "name": "Mine", "selected_context": 64})

    refreshed = llm_model_crud.register("org/model", snapshot)

    assert (refreshed.id, refreshed.name, refreshed.selected_format, refreshed.selected_context) == (model.id, "Mine", "onnx", 64)
    with pytest.raises(InvalidInputError):
        llm_model_crud.update(model.id, {"selected_format": "gguf"})


def test_sync_adds_cached_models_and_repairs_broken_paths(crud_database, model_cache):
    old = model_cache("org/model", {"model.safetensors": b"w"}, revision="old")
    llm_model_crud.register("org/model", old)
    new = model_cache("org/model", {"model.safetensors": b"w2"}, revision="new")
    model_cache("local/mine", {"weights.pth": b"p"})

    report = llm_model_crud.sync_cache()

    assert report == {"added": ["local/mine"], "refreshed": ["org/model"], "skipped": []}
    models = {model.hf_path: model for model in llm_model_crud.get_all()}
    assert models["org/model"].local_path == str(new)
    assert (models["local/mine"].source, models["local/mine"].formats) == ("local", ["pth"])


def test_sync_reports_snapshots_without_weights(crud_database, model_cache):
    model_cache("org/empty", {"README.md": b"nothing"})

    assert llm_model_crud.sync_cache()["skipped"][0].startswith("org/empty")


def test_models_can_be_filtered_by_format(crud_database, model_cache):
    llm_model_crud.register("org/a", model_cache("org/a", {"model.safetensors": b"w"}))
    llm_model_crud.register("org/b", model_cache("org/b", {"model.gguf": b"GGUF"}))

    assert [model.hf_path for model in llm_model_crud.get_all(["GGUF", "bin"])] == ["org/b"]


def test_delete_can_remove_the_files_too(crud_database, model_cache):
    model = llm_model_crud.register("org/a", model_cache("org/a", {"model.safetensors": b"w"}))

    llm_model_crud.delete(model.id, delete_files=True)

    assert llm_model_crud.get_all() == []
    assert not (model_cache.root / "models--org--a").exists()
    with pytest.raises(NotFoundError):
        llm_model_crud.get(model.id)


def test_a_model_whose_files_disappeared_is_unavailable(crud_database, model_cache):
    snapshot = model_cache("org/a", {"model.safetensors": b"w"})
    model = llm_model_crud.register("org/a", snapshot)
    (snapshot / "model.safetensors").unlink()
    snapshot.rmdir()

    assert llm_model_crud.get(model.id).available is False
