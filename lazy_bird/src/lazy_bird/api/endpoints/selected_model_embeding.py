from fastapi import APIRouter

import lazy_bird.crud.selected_model_embeding as selected_model
from lazy_bird.schemas.selected_model_embeding import (
    SelectedModelEmbedingIn,
    SelectedModelEmbedingOut,
)

router = APIRouter(prefix="/selected-models", tags=["selected-models"])


@router.put("/", response_model=SelectedModelEmbedingOut)
def set_selected_model(model_in: SelectedModelEmbedingIn):
    return selected_model.upsert(model_in)


@router.get("/", response_model=SelectedModelEmbedingOut)
def get_selected_model():
    return selected_model.get()
