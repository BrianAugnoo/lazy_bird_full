from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from lazy_bird.models.conversation import Conversation

class Message(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", nullable=False)
    role: str  # "assistant", "user", "system"
    meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    
    # Relationship to conversation
    conversation: "Conversation" = Relationship(back_populates="messages")