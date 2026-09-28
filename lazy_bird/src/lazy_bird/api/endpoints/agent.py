from fastapi import APIRouter, HTTPException
import lazy_bird.crud.agent as AgentCrud
from lazy_bird.schemas.agent import AgentIn, AgentOut
from lazy_bird.schemas.conversation import ConversationOut

router = APIRouter(prefix="/agents", tags=["agents"])


@router.get("/", response_model=list[AgentOut])
async def get_all_agents():
    return AgentCrud.get_all()

@router.post("/chat", response_model=ConversationOut)
async def chat_with_agent(agent_id: int, query: str, selected_conversation_id: int = None, max_iter: int = 20):
    try:
        return AgentCrud.chat(agent_id, query, selected_conversation_id, max_iter)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    
@router.post("/continue_chat", response_model=list[ConversationOut])
async def continue_chat_with_agent(agent_id: int, conversation_id: int, max_iter: int = 20):
    try:
        return AgentCrud.continue_chat(agent_id, conversation_id, max_iter)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

@router.get("/session/{session_id}", response_model=list[AgentOut])
async def get_agents_by_session(session_id: int):
    return AgentCrud.get_by_session(session_id)


@router.get("/{agent_id}", response_model=AgentOut)
async def get_agent(agent_id: int):
    agent = AgentCrud.get_by_id(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/", response_model=AgentOut, status_code=201)
async def create_agent(payload: AgentIn):
    try:
        return AgentCrud.create(payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.patch("/{agent_id}", response_model=AgentOut)
async def update_agent(agent_id: int, payload: AgentIn):
    try:
        agent = AgentCrud.update(agent_id, payload)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.delete("/{agent_id}")
async def delete_agent(agent_id: int):
    deleted = AgentCrud.delete(agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {"message": "Agent deleted successfully"}