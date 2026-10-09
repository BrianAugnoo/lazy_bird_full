"""Cross-encoder: score how well documents answer a query, to rerank search candidates.

Engine modules live in ``cross_encoder/engines/`` (see ``crud.engine`` for the shared
contract). A cross-encoder engine additionally defines::

    def rerank(query: str, documents: list[str], settings: EngineSettings, model: LLMModelOut | None) -> list[float]

returning one relevance score per document, in order (higher is more relevant).
``model`` is the ``LLMModel`` referenced by ``settings.model_id``. Unlike an
embedding engine, a cross-encoder has no vector space: it only scores pairs.
A local engine receives its loaded model first, ``rerank(scorer, query, documents,
settings, model)``, like an embedding engine (see ``embedding``).
"""

from __future__ import annotations

from lazy_bird.crud.engine import EngineFamily, ResolvedEngine
from lazy_bird.models.cross_encoder_engine import CrossEncoderEngine, PresetCrossEncoder
from lazy_bird.schemas.cross_encoder_engine import PresetCrossEncoderOut

engine_family = EngineFamily(
    kind="cross_encoder",
    package="lazy_bird.cross_encoder.engines",
    required=("rerank",),
    engine_table=CrossEncoderEngine,
    preset_table=PresetCrossEncoder,
    engine_fk="cross_encoder_engine_id",
    preset_out=PresetCrossEncoderOut,
)


class CrossEncoderEngineError(RuntimeError):
    """A cross-encoder engine broke its contract while scoring."""


def initialize_cross_encoder_engines():
    return engine_family.discover()


def rerank_scores(query: str, documents: list[str], resolved: ResolvedEngine) -> list[float]:
    """Score every document against the query with a resolved engine."""
    if not documents:
        return []
    scores = resolved.call("rerank", query, list(documents))
    if len(scores) != len(documents):
        raise CrossEncoderEngineError(
            f"Engine '{resolved.engine.name}' returned {len(scores)} scores for {len(documents)} documents"
        )
    return [float(score) for score in scores]
