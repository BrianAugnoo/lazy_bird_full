from pydantic import BaseModel, Field, ValidationInfo, field_validator

from lazy_bird.schemas.chunk import ChunkOut

DEFAULT_TOP_N = 50


class SearchIn(BaseModel):
    """A search: nearest chunks by embedding, optionally reranked by a cross-encoder.

    Without ``rerank``, the ``top_k`` nearest chunks are returned. With it, the ``top_n``
    nearest chunks (the candidates) are scored by a cross-encoder and the best ``top_k``
    are returned, so ``top_n`` must be greater than ``top_k``.
    """

    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=100, description="Number of results returned.")
    preset_id: int | None = Field(default=None, description="Embedding preset; the default preset when omitted.")
    file_ids: list[int] | None = Field(default=None, description="Restrict the search to these files.")
    rerank: bool = Field(default=False, description="Rerank the embedding candidates with a cross-encoder.")
    cross_encoder_preset_id: int | None = Field(
        default=None, description="Cross-encoder preset used when reranking; the default preset when omitted."
    )
    top_n: int = Field(
        default=DEFAULT_TOP_N,
        ge=1,
        le=500,
        validate_default=True,
        description="Candidates retrieved by the embedding stage before reranking (only used with rerank).",
    )

    @field_validator("top_n")
    @classmethod
    def candidates_outnumber_results(cls, top_n: int, info: ValidationInfo) -> int:
        if info.data.get("rerank") and "top_k" in info.data and top_n <= info.data["top_k"]:
            raise ValueError("Embedding candidates (top_n) must be greater than the final results (top_k).")
        return top_n


class SearchResultOut(BaseModel):
    chunk: ChunkOut
    file_name: str
    file_path: str
    distance: float | None = None
    score: float | None = Field(default=None, description="Cross-encoder score; only set when the search reranks.")
