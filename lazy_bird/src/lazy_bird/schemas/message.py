from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.schemas.types import UtcDatetime


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str | None = None
    meta: dict[str, Any] | None = None
    hooks: dict[str, Any] = Field(default_factory=dict)
    created_at: UtcDatetime
    updated_at: UtcDatetime

    model_config = ConfigDict(from_attributes=True)


class UserMessageIn(BaseModel):
    content: str = Field(min_length=1)


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1)
