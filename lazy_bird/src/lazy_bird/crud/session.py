"""Sessions: groups of agents sharing a ``meta`` dict, one of them being the master."""

from typing import Any

from sqlmodel import select

from lazy_bird.agents import session_preset
from lazy_bird.database import db
from lazy_bird.errors import NotFoundError
from lazy_bird.models.agent import Agent as AgentORM, AgentHierarchy
from lazy_bird.models.session import Session as SessionORM
from lazy_bird.schemas.session import SessionIn, SessionOut


def _row(session, session_id: int) -> SessionORM:
    found = session.get(SessionORM, session_id)
    if found is None:
        raise NotFoundError("Session", session_id)
    return found


def get_all() -> list[SessionOut]:
    with db() as session:
        return [SessionOut.model_validate(item) for item in session.exec(select(SessionORM).order_by(SessionORM.id)).all()]


def get(session_id: int) -> SessionOut:
    with db() as session:
        return SessionOut.model_validate(_row(session, session_id))


def get_by_id(session_id: int) -> SessionOut | None:
    try:
        return get(session_id)
    except NotFoundError:
        return None


def meta_of(session_id: int) -> dict[str, Any]:
    with db() as session:
        return dict(_row(session, session_id).meta or {})


def create(payload: SessionIn) -> SessionOut:
    with db() as session:
        created = SessionORM(**payload.model_dump())
        session.add(created)
        session.commit()
        session.refresh(created)
        return SessionOut.model_validate(created)


def update(session_id: int, changes: dict[str, Any]) -> SessionOut:
    with db() as session:
        found = _row(session, session_id)
        for key, value in changes.items():
            setattr(found, key, value)
        session.add(found)
        session.commit()
        session.refresh(found)
        return SessionOut.model_validate(found)


def delete(session_id: int) -> None:
    """Delete a session with its agents, their links, conversations and messages."""
    with db() as session:
        found = _row(session, session_id)
        agent_ids = [agent.id for agent in found.agents]
        if agent_ids:
            links = session.exec(
                select(AgentHierarchy).where(AgentHierarchy.parent_id.in_(agent_ids) | AgentHierarchy.child_id.in_(agent_ids))
            ).all()
            for link in links:
                session.delete(link)
            session.flush()
        session.delete(found)
        session.commit()


def create_from_preset(preset_id: str, title: str | None = None) -> SessionOut:
    """Create a session, its agents (sharing sub-agents) and its master from a preset."""
    from lazy_bird.crud import agent as agent_crud

    data = session_preset.registry.valid_data(preset_id)
    created = create(SessionIn(title=title or data.name, meta=data.meta))
    existing: dict[str, int] = {}
    for agent_preset_id in data.agents:
        if agent_preset_id not in existing:
            agent_crud.instantiate(created.id, agent_preset_id, existing, ())
    with db() as session:
        master = session.get(AgentORM, existing[data.master])
        master.master = True
        session.add(master)
        session.commit()
    return get(created.id)


def master_of(session_id: int):
    """The master agent of a session (the one receiving the user's prompts)."""
    from lazy_bird.crud import agent as agent_crud
    from lazy_bird.errors import ConflictError

    agents = agent_crud.get_by_session(session_id)
    master = next((agent for agent in agents if agent.master), None)
    if master is None:
        raise ConflictError("This session has no master agent: mark one of its agents as master.", code="no_master_agent")
    return master


def chat(session_id: int, content: str, conversation_id: int | None = None):
    """Give a user prompt to the session's master, in a conversation of its own.

    Uses ``conversation_id`` (which must belong to the master), else the master's
    latest conversation, else a new one. Returns the conversation; run it to answer.
    """
    from lazy_bird.crud import conversation as conversation_crud
    from lazy_bird.errors import InvalidInputError

    master = master_of(session_id)
    if conversation_id is not None:
        conversation = conversation_crud.get(conversation_id)
        if conversation.agent_id != master.id:
            raise InvalidInputError("This conversation does not belong to the session's master agent.", code="not_master_conversation")
    else:
        conversation = conversation_crud.latest(master.id) or conversation_crud.create(master.id)
    conversation_crud.add_user_message(conversation.id, content)
    return conversation_crud.detail(conversation.id)
