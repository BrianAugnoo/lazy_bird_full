from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from lazy_bird.schemas.message import MessageOut


class ConversationOut(BaseModel):
    """A conversation; ``runnable`` is true when the agent can answer now
    (the last message is from the user, an error or an unfinished tool turn)."""

    id: int
    agent_id: int
    title: str
    created_at: datetime
    updated_at: datetime
    runnable: bool = False
    running: bool = False

    model_config = ConfigDict(from_attributes=True)


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = Field(default_factory=list)


class ConversationIn(BaseModel):
    agent_id: int
    title: str | None = Field(default=None, min_length=1)


class ConversationUpdate(BaseModel):
    title: str = Field(min_length=1)


class RewindIn(BaseModel):
    """Delete every message after ``message_id`` (kept)."""

    message_id: int


class RunOptions(BaseModel):
    retry: int = Field(default=3, ge=0, le=10)
    max_iter: int = Field(default=20, ge=1, le=100)


class RunOut(BaseModel):
    """End of an agent run: ``completed``, ``stopped`` (by the user) or ``error``."""

    reason: Literal["completed", "stopped", "error"]
    messages: list[MessageOut]


class ChatIn(BaseModel):
    """A user message for a session's master agent (in ``conversation_id``, or its latest one)."""

    content: str = Field(min_length=1)
    conversation_id: int | None = None
