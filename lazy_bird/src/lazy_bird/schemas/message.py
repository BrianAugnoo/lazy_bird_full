from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    content: str | None = None
    meta: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserMessageIn(BaseModel):
    content: str = Field(min_length=1)


class MessageUpdate(BaseModel):
    content: str = Field(min_length=1)
