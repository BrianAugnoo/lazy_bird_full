from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.embedding.engines import detect_device, inference_mode, release_memory, release_model

name = "sentence-transformers"
local = True
formats = ["safetensors", "bin", "onnx"]


class EngineSettings(BaseModel):
    model_id: int = Field(title="Model", description="Local cross-encoder model used to score the documents.")
    device: Literal["cpu", "cuda", "mps"] | None = Field(
        default=None, description="Torch device; empty selects the best available one."
    )
    batch_size: int = Field(default=32, ge=1, description="Number of query/document pairs scored at once.")
    cache_optimization: bool = Field(
        default=False,
        description="Run the model in inference mode and clear the memory caches after every batch: slower, but memory use stays close to the size of the model.",
    )
    model_config = ConfigDict(extra="forbid")


fields = {
    "model_id": {
        "default_field": True,
        "content": "default.basic.reference",
        "args": {"endpoint": "/models/?format=safetensors&format=bin&format=onnx", "value_key": "id", "label_key": "name"},
    },
}


def _backend(model) -> str:
    return "onnx" if (model.selected_format or "").lower() == "onnx" else "torch"


def load_key(settings, model):
    """What changes the loaded model: presets differing only by batch size share it."""
    return model.local_path, settings.device or detect_device(), _backend(model)


def load(settings, model):
    try:
        from sentence_transformers import CrossEncoder
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The sentence-transformers dependency is missing. Install the project dependencies with 'uv sync'."
        ) from exc
    return CrossEncoder(model.local_path, device=settings.device or detect_device(), backend=_backend(model))


def unload(scorer) -> None:
    release_model(scorer)


def _score(scorer, query, documents, settings):
    scores = scorer.predict(
        [(query, document) for document in documents],
        batch_size=settings.batch_size,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return scores.tolist()


def rerank(scorer, query, documents, settings, model):
    documents = list(documents)
    if not settings.cache_optimization:
        return _score(scorer, query, documents, settings)
    scores = []
    with inference_mode():
        for start in range(0, len(documents), settings.batch_size):
            scores.extend(_score(scorer, query, documents[start : start + settings.batch_size], settings))
            release_memory()
    return scores
