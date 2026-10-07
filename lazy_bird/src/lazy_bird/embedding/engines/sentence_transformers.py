from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import detect_device

name = "sentence-transformers"
formats = ["safetensors", "bin", "onnx"]


class EngineSettings(BaseModel):
    model_id: int = Field(title="Model", description="Local model used to compute the embeddings.")
    device: Literal["cpu", "cuda", "mps"] | None = Field(
        default=None, description="Torch device; empty selects the best available one."
    )
    batch_size: int = Field(default=32, ge=1, description="Number of texts encoded at once.")
    model_config = ConfigDict(extra="forbid")


fields = {
    "model_id": {
        "default_field": True,
        "content": "default.basic.reference",
        "args": {"endpoint": "/models/?format=safetensors&format=bin&format=onnx", "value_key": "id", "label_key": "name"},
    },
}


CUDA_OVERHEAD_MB = 512


def resources(settings, model):
    """GPU runs hold the model weights plus the CUDA context in VRAM."""
    from lazy_bird.tools.model_extraction import weights_size_mb

    if (settings.device or detect_device()) != "cuda":
        return {"cpu": 1}
    return {"cpu": 1, "vram_mb": round(weights_size_mb(model.local_path, model.selected_format, model.selected_file) + CUDA_OVERHEAD_MB)}


@lru_cache(maxsize=1)
def _load(path: str, device: str, backend: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The sentence-transformers dependency is missing. Install the project dependencies with 'uv sync'."
        ) from exc
    model_kwargs = {}
    if backend == "torch" and device == "cuda":
        import torch

        model_kwargs["torch_dtype"] = torch.float16
    return SentenceTransformer(path, device=device, backend=backend, model_kwargs=model_kwargs)


def embed(texts, settings, model):
    backend = "onnx" if (model.selected_format or "").lower() == "onnx" else "torch"
    encoder = _load(model.local_path, settings.device or detect_device(), backend)
    vectors = encoder.encode(
        list(texts), batch_size=settings.batch_size, convert_to_numpy=True, show_progress_bar=False
    )
    return vectors.tolist()
