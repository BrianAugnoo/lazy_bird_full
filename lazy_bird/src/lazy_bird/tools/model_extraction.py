from huggingface_hub import snapshot_download
from pathlib import Path
import json

def download_model(path: str, local_dir: str = None):
    try:
        if local_dir is None:
            downloaded_path = snapshot_download(repo_id=path)
        else:
            downloaded_path = snapshot_download(repo_id=path, local_dir=local_dir)
        return downloaded_path
    except Exception as e:
        print(f"Error downloading model: {e}")
        raise e

def extract(local_path: str):
    try:
        local_path = Path(local_path)
        if not local_path.exists():
            raise FileNotFoundError(f"Local path {local_path} does not exist.")

        formats = ["safetensors"]
        if (local_path / "onnx").is_dir():
            formats.append("ONNX")

        with open(local_path / "config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        print(config)

        return {
            "formats": formats,
            "name": config.get("_name_or_path"),
            "dimension": config.get("hidden_size"),
            "max_context_length": config.get("max_position_embeddings"),
        }
    except Exception as e:
        print(f"Error extracting model: {e}")
        raise e


FORMAT_SUFFIXES = {
    "safetensors": (".safetensors",),
    "onnx": (".onnx",),
    "gguf": (".gguf",),
    "bin": (".bin",),
    "pth": (".pth", ".pt"),
    "ckpt": (".ckpt",),
}


def weights_size_mb(local_path: str, weight_format: str | None = None) -> float:
    """Size of the weights a model loads, in MiB.

    Repositories often ship the same weights in several formats; only the files of
    ``weight_format`` are counted. For ONNX, the main ``model.onnx`` is preferred over
    quantized variants.
    """
    root = Path(local_path)
    if root.is_file():
        return root.stat().st_size / 1024**2
    if not root.is_dir():
        return 0.0
    suffixes = FORMAT_SUFFIXES.get((weight_format or "").lower(), tuple(suffix for group in FORMAT_SUFFIXES.values() for suffix in group))
    files = [path for path in root.rglob("*") if path.is_file() and path.suffix.lower() in suffixes]
    if (weight_format or "").lower() == "onnx" and files:
        main = [path for path in files if path.name == "model.onnx"]
        files = main[:1] or [max(files, key=lambda path: path.stat().st_size)]
    return sum(path.stat().st_size for path in files) / 1024**2
