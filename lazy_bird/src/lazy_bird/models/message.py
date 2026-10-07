from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import Column, JSON, Text
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from lazy_bird.models.conversation import Conversation

ROLES = ("system", "user", "assistant", "tool-calling", "tool-response", "error")


class Message(SQLModel, table=True):
    """One message of a conversation.

    Roles: ``system``, ``user``, ``assistant`` (final answer), ``tool-calling``
    (assistant turn asking for tools: ``meta.tool_calls``), ``tool-response``
    (``meta.tool_call_id``, ``meta.name``) and ``error`` (``meta.code``; never sent to the LLM).
    """

    id: int | None = Field(default=None, primary_key=True)
    conversation_id: int = Field(foreign_key="conversation.id", nullable=False, index=True)
    role: str
    content: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    conversation: "Conversation" = Relationship(back_populates="messages")
