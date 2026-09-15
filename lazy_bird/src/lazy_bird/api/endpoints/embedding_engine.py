from fastapi import APIRouter
from lazy_bird.crud import embedding_engine as crud
from lazy_bird.schemas.embedding_engine import EmbeddingEngineKwargsIn

router = APIRouter(prefix="/embedding-engines", tags=["embedding-engines"])


@router.get("/")
def get_engines():
    return crud.get_all()


@router.put("/{engine_id}")
def update_engine(engine_id: int, payload: EmbeddingEngineKwargsIn):
    result = crud.update_kwargs(engine_id, payload.kwargs)
    return result or {"success": False, "invalid_keys": ["engine_id"]}
