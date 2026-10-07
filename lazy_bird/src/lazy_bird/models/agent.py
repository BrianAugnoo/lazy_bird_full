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
    """An agent of a session. Lists hold ids of extension items (see ``lazy_bird.agents``)."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    session_id: int = Field(foreign_key="session.id", nullable=False)
    description: str | None = Field(default=None)
    # Free text appended to the composed system prompt.
    instructions: str | None = Field(default=None)
    instruction_fulls: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    instruction_subs: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    skills: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    tools: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    hooks: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    master: bool = Field(default=False)
    # Agent preset ("{extension}/{name}") the agent was created from, if any.
    preset: str | None = Field(default=None)
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