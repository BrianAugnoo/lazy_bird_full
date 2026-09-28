from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING
from datetime import datetime, timezone

if TYPE_CHECKING:
    from lazy_bird.models.agent import Agent
    
class Session(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str = Field(nullable=False, default="Undefined")
    meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationship to agent
    agents: list["Agent"] = Relationship(back_populates="session", sa_relationship_kwargs={"cascade": "all, delete-orphan"})