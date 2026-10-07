from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.schemas.types import UtcDatetime


class SessionOut(BaseModel):
    id: int
    title: str
    meta: dict[str, Any] | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    model_config = ConfigDict(from_attributes=True)


class SessionIn(BaseModel):
    title: str = Field(min_length=1)
    meta: dict[str, Any] | None = None


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1)
    meta: dict[str, Any] | None = None


class SessionFromPreset(BaseModel):
    preset_id: str = Field(description='Session preset id, "{extension}/{name}".')
    title: str | None = None
