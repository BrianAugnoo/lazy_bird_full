from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field, Relationship
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lazy_bird.models.conversation import Conversation
    from lazy_bird.models.session import Session


class AgentHierarchy(SQLModel, table=True):
    """Table d'association parent <-> enfant"""
    parent_id: int = Field(foreign_key="agent.id", primary_key=True)
    child_id: int = Field(foreign_key="agent.id", primary_key=True)


class Agent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    session_id: int = Field(foreign_key="session.id", nullable=False)
    description: str | None = Field(default=None)
    instructions: str | None = Field(default=None)
    skills: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    tools: list[str] | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    master: bool = Field(default=False)
    meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))

    sub_agents: list["Agent"] = Relationship(
        back_populates="parent_agents",
        link_model=AgentHierarchy,
        sa_relationship_kwargs=dict(
            primaryjoin="Agent.id==AgentHierarchy.parent_id",
            secondaryjoin="Agent.id==AgentHierarchy.child_id",
        ),
    )
    parent_agents: list["Agent"] = Relationship(
        back_populates="sub_agents",
        link_model=AgentHierarchy,
        sa_relationship_kwargs=dict(
            primaryjoin="Agent.id==AgentHierarchy.child_id",
            secondaryjoin="Agent.id==AgentHierarchy.parent_id",
        ),
    )

    conversations: list["Conversation"] = Relationship(
        back_populates="agent",
        sa_relationship_kwargs={
            "cascade": "all, delete-orphan",
            "order_by": "desc(Conversation.updated_at)"
        },
    )
    session: "Session" = Relationship(back_populates="agents")