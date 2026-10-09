from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from . import detect_device, inference_mode, release_memory, release_model

name = "sentence-transformers"
local = True
formats = ["safetensors", "bin", "onnx"]


class EngineSettings(BaseModel):
    model_id: int = Field(title="Model", description="Local model used to compute the embeddings.")
    device: Literal["cpu", "cuda", "mps"] | None = Field(
        default=None, description="Torch device; empty selects the best available one."
    )
    batch_size: int = Field(default=32, ge=1, description="Number of texts encoded at once.")
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


CUDA_OVERHEAD_MB = 512  # the CUDA context and the working memory of a batch
CPU_OVERHEAD_MB = 256


def placements(settings, model):
    """Where the model can live, best first: (settings it needs there, memory it takes there).

    A device chosen in the preset is the only place; with the device left empty the best
    device comes first and the CPU is the fallback.
    """
    from lazy_bird.tools.model_extraction import weights_size_mb

    size = weights_size_mb(model.local_path, model.selected_format, model.selected_file)

    def at(device):
        memory = {"vram_mb": size + CUDA_OVERHEAD_MB} if device == "cuda" else {"ram_mb": size + CPU_OVERHEAD_MB}
        return {"device": device}, {name: round(amount) for name, amount in memory.items()}

    if settings.device:
        return [at(settings.device)]
    best = detect_device()
    return [at(best)] + ([at("cpu")] if best != "cpu" else [])


def _backend(model) -> str:
    return "onnx" if (model.selected_format or "").lower() == "onnx" else "torch"


def load_key(settings, model):
    """What changes the loaded model: presets differing only by batch size share it."""
    return model.local_path, settings.device or detect_device(), _backend(model)


def load(settings, model):
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The sentence-transformers dependency is missing. Install the project dependencies with 'uv sync'."
        ) from exc
    device, backend = settings.device or detect_device(), _backend(model)
    model_kwargs = {}
    if backend == "torch" and device == "cuda":
        import torch

        model_kwargs["torch_dtype"] = torch.float16
    return SentenceTransformer(model.local_path, device=device, backend=backend, model_kwargs=model_kwargs)


def unload(encoder) -> None:
    release_model(encoder)


def _encode(encoder, texts, settings):
    return encoder.encode(texts, batch_size=settings.batch_size, convert_to_numpy=True, show_progress_bar=False).tolist()


def embed(encoder, texts, settings, model):
    texts = list(texts)
    if not settings.cache_optimization:
        return _encode(encoder, texts, settings)
    vectors = []
    with inference_mode():
        for start in range(0, len(texts), settings.batch_size):
            vectors.extend(_encode(encoder, texts[start : start + settings.batch_size], settings))
            release_memory()
    return vectors
