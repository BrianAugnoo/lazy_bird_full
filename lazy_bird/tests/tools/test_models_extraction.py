import pytest
from lazy_bird.tools.model_extraction import download_model, extract
from pathlib import Path

local_dir = Path(__file__).parent / "test_models"
local_dir.mkdir(exist_ok=True)

def test_download_model():
    model_path = "sentence-transformers/all-MiniLM-L6-v2"
    downloaded_path = download_model(model_path, local_dir=str(local_dir))
    assert Path(downloaded_path).exists()
    assert (Path(downloaded_path) / "config.json").exists()

def test_extract():
    model_path = local_dir / ".cache" / "huggingface" / "hub" / "models--sentence-transformers--all-MiniLM-L6-v2" / "snapshots" / "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
    if not model_path.exists():
        raise FileNotFoundError("Model not downloaded. test_download_model should be run first.")
    result = extract(str(model_path))
    expected_result = {
        "onnx": True,
        "name": "nreimers/MiniLM-L6-H384-uncased",
        "dimension": 512,
    }
    assert result == expected_result