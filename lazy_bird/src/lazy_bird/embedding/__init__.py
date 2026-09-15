import importlib
import pkgutil
from pathlib import Path

from lazy_bird.crud import embedding_engine as engine_crud
from lazy_bird.crud import selected_embedding_engine


def initialize_embedding_engines():
    package = importlib.import_module("lazy_bird.embedding.engines")
    for info in pkgutil.iter_modules(package.__path__):
        if info.name.startswith("_"):
            continue
        module = importlib.import_module(f"{package.__name__}.{info.name}")
        engine_crud.upsert(module.name, info.name, module.formats)


def _embedding_context():
    selected = selected_embedding_engine.get()
    if selected is None:
        raise RuntimeError("No embedding engine is selected")
    module = importlib.import_module(f"lazy_bird.embedding.engines.{Path(selected.file_path).stem}")
    settings = module.EngineSettings.model_validate(selected.kwargs)
    from lazy_bird.crud import selected_model_embeding
    model = selected_model_embeding.get()
    if model.llm_model_id is None:
        raise RuntimeError("No embedding model is selected")
    from lazy_bird.database import db
    from lazy_bird.models.llm_model import LLMModel
    with db() as session:
        llm_model = session.get(LLMModel, model.llm_model_id)
    if llm_model is None:
        raise RuntimeError("Selected embedding model does not exist")
    if llm_model.selected_format not in selected.formats:
        raise RuntimeError(f"Engine {selected.name} does not support format {llm_model.selected_format}")
    if hasattr(settings, "model_path"):
        settings = settings.model_copy(update={"model_path": llm_model.local_path})
    batch_size = model.batch or 1
    ctx_size = llm_model.max_context_length
    return module, settings, batch_size, ctx_size, llm_model


def generate_embeddings(chunks):
    module, settings, batch_size, ctx_size, _ = _embedding_context()
    vectors = []
    for offset in range(0, len(chunks), batch_size):
        vectors.extend(module.embed(chunks[offset:offset + batch_size], ctx_size, batch_size, settings))
    if len(vectors) != len(chunks):
        raise RuntimeError("Embedding engine returned an unexpected vector count")
    return [{**chunk, "vector": vector} for chunk, vector in zip(chunks, vectors, strict=True)]


def generate_query_embedding(query: str) -> tuple[list[float], object]:
    if not query.strip():
        raise ValueError("query cannot be empty")
    module, settings, batch_size, ctx_size, llm_model = _embedding_context()
    vectors = module.embed([query], ctx_size, batch_size, settings)
    if len(vectors) != 1:
        raise RuntimeError("Embedding engine did not return one query vector")
    return vectors[0], llm_model
