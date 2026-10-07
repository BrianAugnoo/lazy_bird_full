from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class PresetEmbeddingIn(BaseModel):
    name: str = Field(min_length=1)
    embedding_engine_id: int
    kwargs: dict[str, Any] = Field(default_factory=dict)
    default: bool = False


class PresetEmbeddingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    embedding_engine_id: int | None = None
    kwargs: dict[str, Any] | None = None
    default: bool | None = None


class PresetEmbeddingOut(BaseModel):
    """A stored embedding preset; ``errors`` lists why it cannot be used (empty when ``valid``)."""

    id: int
    name: str
    embedding_engine_id: int
    kwargs: dict[str, Any]
    default: bool
    valid: bool = True
    errors: dict[str, str] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)
