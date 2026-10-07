from fastapi import APIRouter
from pydantic import BaseModel, Field

from lazy_bird import inference
from lazy_bird.api.engine_routes import engine_router
from lazy_bird.schemas.inference_engine import PresetInferenceIn, PresetInferenceOut, PresetInferenceUpdate

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


class CompletionIn(BaseModel):
    prompt: str = Field(min_length=1)
    instructions: str | None = None
    preset_id: int | None = Field(default=None, description="Inference preset; the default one when omitted.")


class CompletionOut(BaseModel):
    content: str
    reasoning: str | None = None
    model: str | None = None
    usage: dict | None = None


@router.post("/inference/complete", response_model=CompletionOut, tags=["inference"])
def complete(payload: CompletionIn):
    """One prompt, one answer: handy to check that an inference preset works."""
    result = inference.complete(payload.prompt, payload.instructions, payload.preset_id)
    return CompletionOut(content=result.content, reasoning=result.reasoning, model=result.model, usage=result.usage)
