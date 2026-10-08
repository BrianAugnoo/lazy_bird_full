from fastapi import APIRouter

from lazy_bird.crud import search as search_crud
from lazy_bird.schemas.search import SearchIn, SearchResultOut

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/", response_model=list[SearchResultOut])
def search(payload: SearchIn):
    return search_crud.search(
        payload.query,
        payload.top_k,
        payload.preset_id,
        payload.file_ids,
        rerank=payload.rerank,
        cross_encoder_preset_id=payload.cross_encoder_preset_id,
        top_n=payload.top_n,
    )
