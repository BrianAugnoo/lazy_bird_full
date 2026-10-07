from fastapi import APIRouter

from lazy_bird import inference
from lazy_bird.api.engine_routes import engine_router
from lazy_bird.crud.conversation import messages
from lazy_bird.schemas.inference_engine import PresetInferenceIn, PresetInferenceOut, PresetInferenceUpdate, Response

router = APIRouter()
router.include_router(
    engine_router(
        inference.engine_family,
        engines_prefix="/inference-engines",
        presets_prefix="/inference-presets",
        tag="inference",
        preset_in=PresetInferenceIn,
        preset_update=PresetInferenceUpdate,
        preset_out=PresetInferenceOut,
    )
)


@router.post("/inference-engines/single-turn", response_model=Response, tags=["inference"])
def single_turn(query: str, instructions: str | None = None, preset_id: int | None = None):
    return inference.single_turn(query, instructions, preset_id)


@router.post("/inference-engines/agentic-loop", tags=["inference"])
def agentic_loop(conversation_id: int, max_iter: int = 20, preset_id: int | None = None):
    inference.agentic_loop(conversation_id, None, max_iter, preset_id)
    return messages(conversation_id)
