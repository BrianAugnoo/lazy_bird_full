from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from lazy_bird.schemas.message import MessageOut

class ConversationOut(BaseModel):
    id: int
    title: str
    created_at: datetime
    updated_at: datetime
    messages: list[MessageOut] = []

    model_config = ConfigDict(from_attributes=True)

class ConversationIn(BaseModel):
    title: str

    model_config = ConfigDict(from_attributes=True)