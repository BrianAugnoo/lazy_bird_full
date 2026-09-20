from fastapi import APIRouter
from lazy_bird.crud import selected_inference_engine as crud
from lazy_bird.schemas.inference_engine import SelectedInferenceEngineIn

router = APIRouter(prefix="/selected-inference-engine", tags=["inference-engines"])


@router.put("/")
def select_engine(payload: SelectedInferenceEngineIn):
    return crud.select_engine(payload.inference_engine_id) or {"configured": False, "engine": None}


@router.get("/")
def get_selected_engine():
    return crud.get()