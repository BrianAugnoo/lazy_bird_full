from fastapi import APIRouter, Response

import lazy_bird.crud.agent as AgentCrud
from lazy_bird.schemas.agent import AgentFromPreset, AgentIn, AgentOut, AgentToolOut, AgentUpdate

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=list[AgentOut])
def get_all_agents():
    return AgentCrud.get_all()


@router.get("/session/{session_id}", response_model=list[AgentOut])
def get_agents_by_session(session_id: int):
    return AgentCrud.get_by_session(session_id)


@router.post("/", response_model=AgentOut, status_code=201)
def create_agent(payload: AgentIn):
    return AgentCrud.create(payload)


@router.post("/from-preset", response_model=AgentOut, status_code=201)
def create_agent_from_preset(payload: AgentFromPreset):
    """Create an agent (and its missing sub-agents) in a session from an agent preset."""
    return AgentCrud.create_from_preset(payload.session_id, payload.preset_id)


@router.get("/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: int):
    return AgentCrud.get(agent_id)


@router.get("/{agent_id}/tools", response_model=list[AgentToolOut])
def get_agent_tools(agent_id: int):
    """The agent's tools under the names its LLM sees (skill tools included)."""
    return AgentCrud.tools_of(agent_id)


@router.patch("/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: int, payload: AgentUpdate):
    return AgentCrud.update(agent_id, payload.model_dump(exclude_unset=True))


@router.delete("/{agent_id}", status_code=204)
def delete_agent(agent_id: int):
    AgentCrud.delete(agent_id)
    return Response(status_code=204)
