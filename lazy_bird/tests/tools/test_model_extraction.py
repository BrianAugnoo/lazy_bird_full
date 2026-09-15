import json
from pathlib import Path

import pytest

import lazy_bird.tools.model_extraction as extraction


def test_download_model_delegates_to_snapshot_download(monkeypatch):
    calls = []

    def fake_snapshot_download(**kwargs):
        calls.append(kwargs)
        return "/tmp/model"

    monkeypatch.setattr(extraction, "snapshot_download", fake_snapshot_download)

    assert extraction.download_model("owner/model") == "/tmp/model"
    assert calls == [{"repo_id": "owner/model"}]


def test_download_model_passes_local_directory(monkeypatch):
    calls = []
    monkeypatch.setattr(
        extraction,
        "snapshot_download",
        lambda **kwargs: calls.append(kwargs) or "/tmp/model",
    )

    extraction.download_model("owner/model", local_dir="/tmp/cache")

    assert calls == [{"repo_id": "owner/model", "local_dir": "/tmp/cache"}]


def test_download_model_propagates_download_errors(monkeypatch):
    monkeypatch.setattr(
        extraction,
        "snapshot_download",
        lambda **kwargs: (_ for _ in ()).throw(ConnectionError("offline")),
    )

    with pytest.raises(ConnectionError, match="offline"):
        extraction.download_model("owner/model")


def test_extract_reads_name_dimension_and_formats(tmp_path: Path):
    model_dir = tmp_path / "model"
    (model_dir / "onnx").mkdir(parents=True)
    (model_dir / "config.json").write_text(
        json.dumps(
            {
                "_name_or_path": "owner/model",
                "hidden_size": 384,
                "max_position_embeddings": 768,
            }
        ),
        encoding="utf-8",
    )

    assert extraction.extract(str(model_dir)) == {
        "formats": ["safetensors", "ONNX"],
        "name": "owner/model",
        "dimension": 384,
        "max_context_length": 768,
    }


def test_extract_reports_safetensors_when_onnx_directory_is_missing(tmp_path: Path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}", encoding="utf-8")

    assert extraction.extract(str(model_dir)) == {
        "formats": ["safetensors"],
        "name": None,
        "dimension": None,
        "max_context_length": None,
    }


def test_extract_requires_existing_model_directory(tmp_path):
    with pytest.raises(FileNotFoundError, match="does not exist"):
        extraction.extract(str(tmp_path / "missing"))
