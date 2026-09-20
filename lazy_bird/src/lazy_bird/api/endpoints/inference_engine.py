from fastapi import APIRouter
from lazy_bird.crud import inference_engine as crud
from lazy_bird.schemas.inference_engine import InferenceEngineKwargsIn

router = APIRouter(prefix="/inference-engines", tags=["inference-engines"])

@router.get("/")
def get_engines():
    return crud.get_all()


@router.put("/{engine_id}")
def update_engine(engine_id: int, payload: InferenceEngineKwargsIn):
    result = crud.update_kwargs(engine_id, payload.kwargs)
    return result or {"success": False, "invalid_keys": ["engine_id"]}

@router.post("/single-turn")
def single_turn(query: str, instructions: str=None):
    try:
        return crud.single_turn(query, instructions)
    except Exception as e:
        return {"success": False, "error": str(e)}