import json
from pathlib import Path

import pytest

from lazy_bird.tools import model_extraction as extraction
from tests.tools.gguf_factory import write_gguf


def touch(root: Path, relative: str, size: int = 1) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\0" * size)


@pytest.mark.parametrize(
    ("relative", "expected"),
    [
        ("model.safetensors", "safetensors"),
        ("onnx/model_qint8_avx512.onnx", "onnx"),
        ("qwen-Q4_K_M.gguf", "gguf"),
        ("pytorch_model-00001-of-00002.bin", "bin"),
        ("weights.pth", "pth"),
        ("weights.pt", "pth"),
        ("last.ckpt", "ckpt"),
        ("tf_model.h5", "h5"),
        ("flax_model.msgpack", "msgpack"),
        ("openvino/openvino_model.xml", "openvino"),
        ("openvino/openvino_model.bin", None),
        ("training_args.bin", None),
        ("tokenizer.json", None),
    ],
)
def test_each_file_is_mapped_to_its_weight_format(relative, expected):
    assert extraction.format_of(relative) == expected


def test_weight_files_are_grouped_by_format_and_hidden_files_ignored(tmp_path):
    for relative in ("model.safetensors", "onnx/model.onnx", "a-Q8_0.gguf", "b-Q4_K_M.gguf", ".git/x.bin", "config.json"):
        touch(tmp_path, relative)

    files = extraction.weight_files(tmp_path)

    assert files == {"safetensors": ["model.safetensors"], "gguf": ["a-Q8_0.gguf", "b-Q4_K_M.gguf"], "onnx": ["onnx/model.onnx"]}
    assert extraction.default_file("gguf", files) == "b-Q4_K_M.gguf"
    assert extraction.default_file("safetensors", files) is None


def test_extract_reads_configuration_and_sentence_transformers_context(tmp_path):
    touch(tmp_path, "model.safetensors")
    touch(tmp_path, "onnx/model.onnx")
    (tmp_path / "config.json").write_text(json.dumps({"hidden_size": 384, "max_position_embeddings": 512}))
    (tmp_path / "sentence_bert_config.json").write_text(json.dumps({"max_seq_length": 256}))

    result = extraction.extract(tmp_path)

    assert result["formats"] == ["safetensors", "onnx"]
    assert (result["dimension"], result["max_context_length"]) == (384, 256)


def test_extract_reads_gguf_metadata_when_there_is_no_configuration(tmp_path):
    write_gguf(tmp_path / "tiny-Q4_K_M.gguf", {"general.architecture": "llama", "general.name": "Tiny", "llama.context_length": 2048, "llama.embedding_length": 64})

    result = extraction.extract(tmp_path)

    assert result == {
        "formats": ["gguf"],
        "files": {"gguf": ["tiny-Q4_K_M.gguf"]},
        "name": "Tiny",
        "dimension": 64,
        "max_context_length": 2048,
    }


def test_extract_accepts_a_single_weight_file(tmp_path):
    path = write_gguf(tmp_path / "solo.gguf", {"general.architecture": "llama"})

    assert extraction.extract(path)["files"] == {"gguf": ["solo.gguf"]}


def test_extract_requires_weights(tmp_path):
    (tmp_path / "README.md").write_text("no weights here")

    with pytest.raises(ValueError):
        extraction.extract(tmp_path)
    with pytest.raises(FileNotFoundError):
        extraction.extract(tmp_path / "missing")


def test_weights_size_counts_only_the_loaded_weights(tmp_path):
    touch(tmp_path, "model.safetensors", 1024 * 1024)
    touch(tmp_path, "pytorch_model.bin", 2 * 1024 * 1024)
    touch(tmp_path, "onnx/model.onnx", 3 * 1024 * 1024)
    touch(tmp_path, "onnx/model_qint8.onnx", 1024 * 1024)
    touch(tmp_path, "a-Q4_K_M.gguf", 4 * 1024 * 1024)
    touch(tmp_path, "a-Q8_0.gguf", 8 * 1024 * 1024)

    assert extraction.weights_size_mb(str(tmp_path), "safetensors") == 1
    assert extraction.weights_size_mb(str(tmp_path), "bin") == 2
    assert extraction.weights_size_mb(str(tmp_path), "ONNX") == 3
    assert extraction.weights_size_mb(str(tmp_path), "gguf", "a-Q4_K_M.gguf") == 4
    assert extraction.weights_size_mb(str(tmp_path / "missing")) == 0


def test_download_fetches_only_the_chosen_weights_with_support_files(monkeypatch):
    calls = []
    monkeypatch.setattr("huggingface_hub.snapshot_download", lambda **kwargs: calls.append(kwargs) or "/cache/snapshot")

    assert extraction.download_model("org/model", files=["model-Q4_K_M.gguf"]) == "/cache/snapshot"

    assert calls[0]["allow_patterns"][0] == "model-Q4_K_M.gguf"
    assert "*.json" in calls[0]["allow_patterns"]
    assert extraction.download_model("org/model") and calls[1]["allow_patterns"] is None


def test_download_progress_adds_up_the_byte_bars():
    reports = []
    progress_class = extraction._progress_class(lambda done, total: reports.append((done, total)))

    first = progress_class(total=100, unit="B")
    second = progress_class(total=50, unit="B")
    files = progress_class(total=2)
    first.update(60)
    second.update(50)
    files.update(1)
    first.update(40)

    assert reports == [(60, 100), (110, 150), (150, 150)]
