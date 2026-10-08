"""Semantic search over the chunks embedded with an embedding preset, optionally reranked."""

from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.database import db
from lazy_bird.cross_encoder import engine_family as cross_encoder_family
from lazy_bird.cross_encoder import rerank_scores
from lazy_bird.embedding import embed_query, vector_space
from lazy_bird.errors import InvalidInputError
from lazy_bird.models.file import File
from lazy_bird.schemas.search import DEFAULT_TOP_N, SearchResultOut
from sqlmodel import select


def search(
    query: str,
    top_k: int = 5,
    preset_id: int | None = None,
    file_ids: list[int] | None = None,
    *,
    rerank: bool = False,
    cross_encoder_preset_id: int | None = None,
    top_n: int = DEFAULT_TOP_N,
) -> list[SearchResultOut]:
    """Return the ``top_k`` chunks nearest to ``query``, optionally within some files.

    With ``rerank``, the ``top_n`` nearest chunks are the candidates: a cross-encoder
    scores each one against the query and the ``top_k`` best scores are returned.
    """
    if not rerank:
        return _nearest(query, top_k, preset_id, file_ids)
    if top_n <= top_k:
        raise InvalidInputError(
            "Embedding candidates (top_n) must be greater than the final results (top_k).",
            code="invalid_top_n",
            details={"fields": {"top_n": f"Must be greater than the final results (top_k = {top_k})."}},
        )
    reranker = cross_encoder_family.resolve(cross_encoder_preset_id)  # fail before the embedding model is loaded
    candidates = _nearest(query, top_n, preset_id, file_ids)
    scores = rerank_scores(query, [candidate.chunk.content for candidate in candidates], reranker)
    ranked = sorted(zip(scores, candidates, strict=True), key=lambda pair: pair[0], reverse=True)
    return [candidate.model_copy(update={"score": score}) for score, candidate in ranked[:top_k]]


def _nearest(query: str, count: int, preset_id: int | None, file_ids: list[int] | None) -> list[SearchResultOut]:
    """The ``count`` chunks whose embedding is nearest to ``query``, closest first."""
    vector, resolved = embed_query(query, preset_id)
    scope = None
    if file_ids is not None:
        scope = [chunk_id for file_id in file_ids for chunk_id in chunk_crud.ids_for_file(file_id)]
    hits = database.vector_retrieve(vector_space(resolved), count, vector, scope)
    chunks = chunk_crud.get_many([hit["chunk_id"] for hit in hits])
    with db() as session:
        files = {file.id: file for file in session.exec(select(File).where(File.id.in_({chunk.file_id for chunk in chunks.values()}))).all()}
    results = []
    for hit in hits:
        chunk = chunks.get(hit["chunk_id"])
        if chunk is None or chunk.file_id not in files:
            continue
        file = files[chunk.file_id]
        results.append(
            SearchResultOut(chunk=chunk, file_name=f"{file.name}{file.extension}", file_path=file.path, distance=hit.get("distance"))
        )
    return results
