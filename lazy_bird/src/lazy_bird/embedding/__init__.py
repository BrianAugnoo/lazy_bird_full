"""Embedding: turn texts into vectors with an embedding preset.

Engine modules live in ``embedding/engines/`` (see ``crud.engine`` for the shared
contract). An embedding engine additionally defines::

    def embed(texts: list[str], settings: EngineSettings, model: LLMModelOut | None) -> list[list[float]]

returning one vector per text, in order. ``model`` is the ``LLMModel`` referenced
by ``settings.model_id`` (``None`` when the engine declares no ``model_id``). An
engine without ``model_id`` must define ``vector_space(settings) -> str`` naming
the embedding space its vectors belong to (for instance the remote model name).

A local engine (``local = True``) receives its loaded model first,
``embed(encoder, texts, settings, model)``, from ``load(settings, model)``; wrap many
calls in ``with resolved.loaded():`` to load the model once for all of them.
"""

from __future__ import annotations

from lazy_bird.crud.engine import EngineFamily, ResolvedEngine
from lazy_bird.errors import InvalidInputError
from lazy_bird.models.embedding_engine import EmbeddingEngine, PresetEmbedding
from lazy_bird.schemas.embedding_engine import PresetEmbeddingOut

engine_family = EngineFamily(
    kind="embedding",
    package="lazy_bird.embedding.engines",
    required=("embed",),
    engine_table=EmbeddingEngine,
    preset_table=PresetEmbedding,
    engine_fk="embedding_engine_id",
    preset_out=PresetEmbeddingOut,
    on_default_change=lambda: _queue_default_embeddings(),
)


def _queue_default_embeddings() -> None:
    """A new default preset may embed with another model: restart the automatic embedding with it.

    Files are embedded again with the new model even if another one embedded them (vectors
    of different models cannot be compared, so each model keeps its own table); work still
    in progress for the previous model is stopped.
    """
    from lazy_bird.crud import file_processing
    from lazy_bird.preferences import auto_embedding_enabled

    if auto_embedding_enabled():
        file_processing.restart_embedding()
        file_processing.ensure_all()


class EmbeddingEngineError(RuntimeError):
    """An embedding engine broke its contract while embedding."""


def initialize_embedding_engines():
    return engine_family.discover()


def vector_space(resolved: ResolvedEngine) -> str:
    """Identify the embedding space of a resolved engine: the model its vectors come from."""
    if resolved.model is not None:
        return resolved.model.hf_path
    custom = getattr(resolved.module, "vector_space", None)
    if custom is None:
        raise EmbeddingEngineError(f"Engine '{resolved.engine.name}' has no model_id and no vector_space()")
    return str(custom(resolved.settings))


def embed_texts(texts: list[str], resolved: ResolvedEngine) -> list[list[float]]:
    if not texts:
        return []
    vectors = resolved.call("embed", list(texts))
    if len(vectors) != len(texts):
        raise EmbeddingEngineError(
            f"Engine '{resolved.engine.name}' returned {len(vectors)} vectors for {len(texts)} texts"
        )
    return [list(vector) for vector in vectors]


def embed_query(query: str, preset_id: int | None = None) -> tuple[list[float], ResolvedEngine]:
    if not query.strip():
        raise InvalidInputError("The query cannot be empty.", code="empty_query")
    resolved = engine_family.resolve(preset_id)
    return embed_texts([query], resolved)[0], resolved
