"""Semantic search over the chunks embedded with an embedding preset."""

from lazy_bird import database
from lazy_bird.crud import chunk as chunk_crud
from lazy_bird.database import db
from lazy_bird.embedding import embed_query, vector_space
from lazy_bird.models.file import File
from lazy_bird.schemas.search import SearchResultOut
from sqlmodel import select


def search(query: str, top_k: int = 5, preset_id: int | None = None, file_ids: list[int] | None = None) -> list[SearchResultOut]:
    """Return the ``top_k`` chunks nearest to ``query``, optionally within some files."""
    vector, resolved = embed_query(query, preset_id)
    scope = None
    if file_ids is not None:
        scope = [chunk_id for file_id in file_ids for chunk_id in chunk_crud.ids_for_file(file_id)]
    hits = database.vector_retrieve(vector_space(resolved), top_k, vector, scope)
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
