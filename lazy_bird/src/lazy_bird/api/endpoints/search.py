from fastapi import APIRouter
from lazy_bird import database
from lazy_bird.embedding import generate_query_embedding
from lazy_bird.schemas.search import ChunkOut, SearchIn

router = APIRouter(prefix="/search", tags=["search"])

@router.post("/", response_model=list[ChunkOut])
def search(payload: SearchIn):
    vector, model = generate_query_embedding(payload.query)
    rows = database.vector_retrieve(model.name, payload.top_k, vector)
    return [ChunkOut.model_validate({**row, "distance": row.get("_distance")}) for row in rows]
