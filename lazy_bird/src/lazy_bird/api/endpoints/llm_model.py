from fastapi import APIRouter
from lazy_bird.schemas.llm_model import LLMModelIn
from lazy_bird.schemas.llm_model_format import SelectedFormatIn
from lazy_bird.crud.llm_model_format import update_selected_format
import lazy_bird.crud.llm_model as LLMModel

router = APIRouter(prefix="/models", tags=["models"])

@router.get("/")
async def get_llm_models():
    return LLMModel.get_all()

@router.get("/{id}")
async def get_llm_model(id: int):
    return LLMModel.find(id)

@router.post("/")
async def create_llm_model(llm_model: LLMModelIn):
    return LLMModel.create(llm_model)

@router.put("/{id}/format")
async def set_selected_format(id: int, payload: SelectedFormatIn):
    return update_selected_format(id, payload.selected_format) or {"success": False, "invalid_keys": ["id"]}

@router.delete("/destroy")
async def delete_llm_models():
    LLMModel.delete_all()
    return {"message": "All llm models deleted."}
