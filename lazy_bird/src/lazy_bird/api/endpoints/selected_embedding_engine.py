from fastapi import APIRouter
from lazy_bird.crud import selected_embedding_engine as crud
from lazy_bird.schemas.embedding_engine import SelectedEmbeddingEngineIn

router = APIRouter(prefix="/selected-embedding-engine", tags=["embedding-engines"])


@router.put("/")
def select_engine(payload: SelectedEmbeddingEngineIn):
    return crud.select_engine(payload.embedding_engine_id) or {"configured": False, "engine": None}


@router.get("/")
def get_selected_engine():
    return crud.get()
