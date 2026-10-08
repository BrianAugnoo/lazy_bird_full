import gc
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.embedding.engines import detect_device

name = "sentence-transformers"
formats = ["safetensors", "bin", "onnx"]


class EngineSettings(BaseModel):
    model_id: int = Field(title="Model", description="Local cross-encoder model used to score the documents.")
    device: Literal["cpu", "cuda", "mps"] | None = Field(
        default=None, description="Torch device; empty selects the best available one."
    )
    batch_size: int = Field(default=32, ge=1, description="Number of query/document pairs scored at once.")
    model_config = ConfigDict(extra="forbid")
    unloading: bool = Field(default=True, description="Unload the model from memory after each reranking call.")


fields = {
    "model_id": {
        "default_field": True,
        "content": "default.basic.reference",
        "args": {"endpoint": "/models/?format=safetensors&format=bin&format=onnx", "value_key": "id", "label_key": "name"},
    },
}


@lru_cache(maxsize=1)
def _load(path: str, device: str, backend: str):
    try:
        from sentence_transformers import CrossEncoder
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The sentence-transformers dependency is missing. Install the project dependencies with 'uv sync'."
        ) from exc
    return CrossEncoder(path, device=device, backend=backend)


def unload() -> None:
    """Drop the cached model and give its memory back (GPU memory included)."""
    _load.cache_clear()
    gc.collect()
    try:
        import torch
    except ModuleNotFoundError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _score(query, documents, settings, model):
    backend = "onnx" if (model.selected_format or "").lower() == "onnx" else "torch"
    scorer = _load(model.local_path, settings.device or detect_device(), backend)
    scores = scorer.predict(
        [(query, document) for document in documents],
        batch_size=settings.batch_size,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return scores.tolist()


def rerank(query, documents, settings, model):
    # The scorer lives only inside _score, so nothing but the cache keeps it alive when unload() runs.
    try:
        return _score(query, documents, settings, model)
    finally:
        if settings.unloading:
            unload()
