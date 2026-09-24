from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class MessageOut(BaseModel):
    id: int
    conversation_id: int
    role: str
    meta: dict | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class MessageIn(BaseModel):
    conversation_id: int
    role: str
    meta: dict | None = None

    model_config = ConfigDict(from_attributes=True)

class MessageUpdate(BaseModel):
    role: str | None = None
    meta: dict | None = None

    model_config = ConfigDict(from_attributes=True)