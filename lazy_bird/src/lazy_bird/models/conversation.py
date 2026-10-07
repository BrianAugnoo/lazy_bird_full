from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlmodel import SQLModel, Field, Relationship

if TYPE_CHECKING:
    from lazy_bird.models.message import Message
    from lazy_bird.models.agent import Agent

class Conversation(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    agent_id: int = Field(foreign_key="agent.id")
    title: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), 
        nullable=False
    )
    
    # Relationship to messages - cascade delete
    messages: list["Message"] = Relationship(
        back_populates="conversation", 
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "Message.created_at"
        }
    )
    # Relationship to agent
    agent: "Agent" = Relationship(back_populates="conversations")
    