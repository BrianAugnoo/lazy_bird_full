from lazy_bird.database import db
from lazy_bird.models.agent import Agent as AgentORM, AgentHierarchy
from lazy_bird.schemas.agent import AgentIn, AgentOut
from sqlmodel import select
import lazy_bird.crud.conversation as ConversationCrud
from lazy_bird.schemas.conversation import ConversationIn, ConversationOut
from lazy_bird.crud.message import create as create_message
from lazy_bird.schemas.message import MessageIn
from lazy_bird.agents.tools import get_tools
from lazy_bird.inference import agentic_loop
import traceback

def _populate_agent_out(agent_orm: AgentORM) -> AgentOut:
    """Convert Agent ORM to AgentOut with sub_agents_ids and parent_agents_ids populated."""
    return AgentOut(
        id=agent_orm.id,
        name=agent_orm.name,
        description=agent_orm.description,
        instructions=agent_orm.instructions,
        skills=agent_orm.skills,
        tools=agent_orm.tools,
        master=agent_orm.master,
        meta=agent_orm.meta,
        session_id=agent_orm.session_id,
        sub_agents_ids=[a.id for a in agent_orm.sub_agents],
        parent_agents_ids=[a.id for a in agent_orm.parent_agents],
    )


def _sync_hierarchy(session, agent_orm: AgentORM, sub_agents_ids: list[int], parent_agents_ids: list[int]) -> None:
    """Synchronize the agent hierarchy relationships."""
    # Clear existing relationships
    session.exec(
        select(AgentHierarchy).where(
            (AgentHierarchy.parent_id == agent_orm.id) | (AgentHierarchy.child_id == agent_orm.id)
        )
    ).all()
    # Actually delete them
    for link in session.exec(
        select(AgentHierarchy).where(
            (AgentHierarchy.parent_id == agent_orm.id) | (AgentHierarchy.child_id == agent_orm.id)
        )
    ).all():
        session.delete(link)
    
    # Add new sub_agents (this agent is parent)
    for sub_id in sub_agents_ids:
        if sub_id != agent_orm.id:  # Prevent self-reference
            session.add(AgentHierarchy(parent_id=agent_orm.id, child_id=sub_id))
    
    # Add new parent_agents (this agent is child)
    for parent_id in parent_agents_ids:
        if parent_id != agent_orm.id:  # Prevent self-reference
            session.add(AgentHierarchy(parent_id=parent_id, child_id=agent_orm.id))


def get_all() -> list[AgentOut]:
    with db() as session:
        statement = select(AgentORM)
        agents = session.exec(statement).all()
        return [_populate_agent_out(a) for a in agents]


def get_by_id(id: int) -> AgentOut | None:
    with db() as session:
        agent_orm = session.get(AgentORM, id)
        if agent_orm is None:
            return None
        return _populate_agent_out(agent_orm)


def get_by_session(session_id: int) -> list[AgentOut]:
    with db() as session:
        statement = select(AgentORM).where(AgentORM.session_id == session_id)
        agents = session.exec(statement).all()
        return [_populate_agent_out(a) for a in agents]


def create(payload: AgentIn) -> AgentOut:
    with db() as session:
        # Check master constraint: only one master per session
        if payload.master:
            existing_master = session.exec(
                select(AgentORM).where(
                    AgentORM.session_id == payload.session_id,
                    AgentORM.master == True
                )
            ).first()
            if existing_master:
                raise ValueError(f"Session {payload.session_id} already has a master agent")
        
        # Extract hierarchy IDs before creating the agent
        sub_agents_ids = payload.sub_agents_ids or []
        parent_agents_ids = payload.parent_agents_ids or []
        
        # Create agent without hierarchy fields
        agent_data = payload.model_dump(exclude={"sub_agents_ids", "parent_agents_ids"})
        agent_orm = AgentORM(**agent_data)
        session.add(agent_orm)
        session.flush()  # Get the ID without committing
        
        # Sync hierarchy relationships
        _sync_hierarchy(session, agent_orm, sub_agents_ids, parent_agents_ids)
        
        session.commit()
        session.refresh(agent_orm)
        return _populate_agent_out(agent_orm)


def update(id: int, payload: AgentIn) -> AgentOut | None:
    with db() as session:
        agent_orm = session.get(AgentORM, id)
        if agent_orm is None:
            return None
        
        # Check master constraint if trying to set master=True
        if payload.master and not agent_orm.master:
            existing_master = session.exec(
                select(AgentORM).where(
                    AgentORM.session_id == payload.session_id,
                    AgentORM.master == True,
                    AgentORM.id != id
                )
            ).first()
            if existing_master:
                raise ValueError(f"Session {payload.session_id} already has a master agent")
        
        # Extract hierarchy IDs
        sub_agents_ids = payload.sub_agents_ids if payload.sub_agents_ids is not None else [a.id for a in agent_orm.sub_agents]
        parent_agents_ids = payload.parent_agents_ids if payload.parent_agents_ids is not None else [a.id for a in agent_orm.parent_agents]
        
        # Update agent fields (exclude hierarchy fields)
        for key, value in payload.model_dump(exclude={"sub_agents_ids", "parent_agents_ids"}, exclude_unset=True).items():
            setattr(agent_orm, key, value)
        
        # Sync hierarchy relationships
        _sync_hierarchy(session, agent_orm, sub_agents_ids, parent_agents_ids)
        
        session.add(agent_orm)
        session.commit()
        session.refresh(agent_orm)
        return _populate_agent_out(agent_orm)


def delete(id: int) -> bool:
    with db() as session:
        agent_orm = session.get(AgentORM, id)
        if agent_orm is None:
            return False
        
        # Delete hierarchy relationships first
        for link in session.exec(
            select(AgentHierarchy).where(
                (AgentHierarchy.parent_id == id) | (AgentHierarchy.child_id == id)
            )
        ).all():
            session.delete(link)
        
        session.delete(agent_orm)
        session.commit()
        return True

from sqlalchemy.orm import selectinload

def chat(agent_id: int, query: str, selected_conversation_id: int = None, max_iter=20) -> list[ConversationOut]:
    try:
        with db() as session:
            agent = (
                session.query(AgentORM)
                .options(
                    selectinload(AgentORM.conversations),  # uniquement les vraies relations
                )
                .filter(AgentORM.id == agent_id)
                .one_or_none()
            )
            if agent is None:
                raise ValueError(f"Agent with id {agent_id} not found")

            # Extraction pendant que la session est encore ouverte
            agent_name = agent.name
            agent_instructions = agent.instructions
            agent_tools = agent.tools  # colonne simple, déjà chargée, pas besoin de selectinload
            conversation_ids = [c.id for c in agent.conversations]

        # --- session is closed from here on; only plain data is used below ---

        if selected_conversation_id is not None:
            if selected_conversation_id not in conversation_ids:
                raise ValueError(
                    f"Conversation with id {selected_conversation_id} not found for agent {agent_id}"
                )
            conversation_id = selected_conversation_id
        elif conversation_ids:
            conversation_id = conversation_ids[0]
        else:
            conversation = ConversationCrud.create(
                ConversationIn(title=f"Conversation with {agent_name}", agent_id=agent_id)
            )
            conversation_id = conversation.id
            if agent_instructions:
                create_message(
                    MessageIn(
                        conversation_id=conversation_id,
                        role="system",
                        meta={"content": agent_instructions},
                    )
                )

        create_message(
            MessageIn(
                conversation_id=conversation_id,
                role="user",
                meta={"content": query},
            )
        )

        tools = get_tools(agent_tools)
        agentic_loop(conversation_id, tools, max_iter=max_iter)
        return ConversationCrud.get(conversation_id)
    except Exception as e:
        print(f"Error in chat function: {e}")
        traceback.print_exc()

def continue_chat(agent_id: int, conversation_id: int, max_iter=20) -> list[ConversationOut]:
    agent = get_by_id(agent_id)
    if agent is None:
        raise ValueError(f"Agent with id {agent_id} not found")

    conversation = next(
        (c for c in agent.conversations if c.id == conversation_id), None
    )
    if conversation is None:
        raise ValueError(
            f"Conversation with id {conversation_id} not found for agent {agent_id}"
        )

    tools = get_tools(agent.tools)
    agentic_loop(conversation_id, tools, max_iter=max_iter)
    return ConversationCrud.get(conversation_id)
    
        