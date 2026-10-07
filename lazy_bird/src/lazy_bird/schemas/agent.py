from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AgentBase(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    instructions: str | None = Field(default=None, description="Free text appended to the system prompt.")
    instruction_fulls: list[str] = Field(default_factory=list)
    instruction_subs: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    hooks: list[str] = Field(default_factory=list)
    master: bool = False
    meta: dict[str, Any] | None = None
    sub_agents_ids: list[int] = Field(default_factory=list, description="Agents of the same session this agent directs.")


class AgentIn(AgentBase):
    session_id: int


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    instructions: str | None = None
    instruction_fulls: list[str] | None = None
    instruction_subs: list[str] | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    hooks: list[str] | None = None
    master: bool | None = None
    meta: dict[str, Any] | None = None
    sub_agents_ids: list[int] | None = None


class AgentOut(AgentBase):
    """An agent; ``errors`` lists broken references (an uninstalled tool...)."""

    id: int
    session_id: int
    preset: str | None = None
    parent_agents_ids: list[int] = Field(default_factory=list)
    valid: bool = True
    errors: dict[str, str] = Field(default_factory=dict)
    model_config = ConfigDict(from_attributes=True)


class AgentFromPreset(BaseModel):
    session_id: int
    preset_id: str = Field(description='Agent preset id, "{extension}/{name}".')


class AgentToolOut(BaseModel):
    """A tool as the agent's LLM sees it."""

    id: str
    name: str
    description: str
