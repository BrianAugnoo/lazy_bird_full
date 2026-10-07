from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PresetInferenceIn(BaseModel):
    name: str = Field(min_length=1)
    inference_engine_id: int
    kwargs: dict[str, Any] = Field(default_factory=dict)
    default: bool = False


class PresetInferenceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    inference_engine_id: int | None = None
    kwargs: dict[str, Any] | None = None
    default: bool | None = None


class PresetInferenceOut(BaseModel):
    """A stored inference preset; ``errors`` lists why it cannot be used (empty when ``valid``)."""

    id: int
    name: str
    inference_engine_id: int
    kwargs: dict[str, Any]
    default: bool
    valid: bool = True
    errors: dict[str, str] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)
