from pydantic import BaseModel, ConfigDict

class AgentOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    instructions: str | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    master: bool
    meta: dict | None = None
    session_id: int

    sub_agents_ids: list[int] = []
    parent_agents_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)

class AgentIn(BaseModel):
    name: str
    description: str | None = None
    instructions: str | None = None
    skills: list[str] | None = None
    tools: list[str] | None = None
    master: bool
    meta: dict | None = None
    session_id: int
    
    sub_agents_ids: list[int] = []
    parent_agents_ids: list[int] = []

    model_config = ConfigDict(from_attributes=True)
    