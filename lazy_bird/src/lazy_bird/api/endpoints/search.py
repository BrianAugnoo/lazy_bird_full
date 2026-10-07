from fastapi import APIRouter
from lazy_bird import database
from lazy_bird.embedding import embed_query, vector_space
from lazy_bird.schemas.search import ChunkOut, SearchIn

router = APIRouter(prefix="/search", tags=["search"])

@router.post("/", response_model=list[ChunkOut])
def search(payload: SearchIn):
    vector, resolved = embed_query(payload.query, payload.preset_id)
    rows = database.vector_retrieve(vector_space(resolved), payload.top_k, vector)
    return [ChunkOut.model_validate({**row, "distance": row.get("_distance")}) for row in rows]
