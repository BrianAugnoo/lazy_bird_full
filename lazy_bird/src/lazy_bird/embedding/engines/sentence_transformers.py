from pydantic import BaseModel, ConfigDict
import torch

from . import detect_device

name = "sentence-transformers"
formats = ["safetensors", "ONNX"]


class EngineSettings(BaseModel):
    device: str | None = None
    model_path: str | None = None
    temperature: float | None = None
    model_config = ConfigDict(extra="forbid")


def validate_kwargs(kwargs):
    try:
        EngineSettings.model_validate(kwargs)
        return True
    except Exception as exc:
        return sorted({str(error.get("loc", ["unknown"])[0]) for error in exc.errors()})


def embed(docs, ctx_size, batch_size, settings):
    try:
        from sentence_transformers import SentenceTransformer
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "The sentence-transformers dependency is missing. Install the project dependencies with 'uv sync'."
        ) from exc
    if not settings.model_path:
        raise ValueError("model_path is required for sentence-transformers")
    model = SentenceTransformer(
        settings.model_path, 
        device=settings.device or detect_device(),
        model_kwargs={
            "torch_dtype": torch.float16
        }
    )
    texts = [doc["content"] if isinstance(doc, dict) else str(doc) for doc in docs]
    return model.encode(texts, batch_size=batch_size, convert_to_numpy=True, show_progress_bar=False).tolist()
