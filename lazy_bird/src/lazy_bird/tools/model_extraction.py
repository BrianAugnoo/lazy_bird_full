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
