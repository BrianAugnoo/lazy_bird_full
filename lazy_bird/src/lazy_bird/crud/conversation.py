"""Conversations between the user and one agent.

A conversation starts with the agent's system prompt (when it has one). The agent
answers only when the conversation is *runnable*: its last message is from the user,
an error (retry), or an unfinished tool turn. After a system or assistant message
it waits for the user.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import select

from lazy_bird.crud import message as message_crud
from lazy_bird.database import db
from lazy_bird.errors import NotFoundError
from lazy_bird.models.agent import Agent as AgentORM
from lazy_bird.models.conversation import Conversation as ConversationORM
from lazy_bird.models.message import Message as MessageORM
from lazy_bird.schemas.conversation import ConversationDetail, ConversationOut
from lazy_bird.schemas.message import MessageOut

RUNNABLE_ROLES = ("user", "error", "tool-calling", "tool-response")
DEFAULT_TITLE = "New conversation"
TITLE_LENGTH = 60


def runnable(messages: list[MessageOut]) -> bool:
    return bool(messages) and messages[-1].role in RUNNABLE_ROLES


def pending_tool_calls(messages: list[MessageOut]) -> list[dict]:
    """Tool calls of the last tool-calling turn that have no response yet."""
    for index in range(len(messages) - 1, -1, -1):
        if messages[index].role == "tool-calling":
            answered = {message.meta.get("tool_call_id") for message in messages[index + 1:] if message.role == "tool-response" and message.meta}
            return [call for call in (messages[index].meta or {}).get("tool_calls", []) if call.get("id") not in answered]
        if messages[index].role in ("user", "assistant", "system"):
            return []
    return []


def _out(row: ConversationORM, last_role: str | None) -> ConversationOut:
    from lazy_bird.inference import is_running

    return ConversationOut.model_validate(row).model_copy(update={"runnable": last_role in RUNNABLE_ROLES, "running": is_running(row.id)})


def _summaries():
    # The conversation list needs only the last role, never message bodies or metadata.
    last_role = select(MessageORM.role).where(MessageORM.conversation_id == ConversationORM.id).order_by(MessageORM.id.desc()).limit(1).scalar_subquery()
    return select(ConversationORM, last_role).order_by(ConversationORM.updated_at.desc())


def _row(session, conversation_id: int) -> ConversationORM:
    row = session.get(ConversationORM, conversation_id)
    if row is None:
        raise NotFoundError("Conversation", conversation_id)
    return row


def create(agent_id: int, title: str | None = None) -> ConversationDetail:
    """Start a conversation with an agent; its system prompt becomes the first message."""
    from lazy_bird.agents.runtime import system_prompt
    from lazy_bird.crud import agent as agent_crud

    agent = agent_crud.get(agent_id)
    prompt = system_prompt(agent)
    with db() as session:
        row = ConversationORM(agent_id=agent_id, title=title or DEFAULT_TITLE)
        session.add(row)
        session.commit()
        session.refresh(row)
    if prompt:
        message_crud.create(row.id, "system", prompt)
    return detail(row.id)


def get(conversation_id: int) -> ConversationOut:
    with db() as session:
        found = session.exec(_summaries().where(ConversationORM.id == conversation_id)).first()
        if found is None:
            raise NotFoundError("Conversation", conversation_id)
        return _out(*found)


def detail(conversation_id: int) -> ConversationDetail:
    with db() as session:
        row = _row(session, conversation_id)
        messages = message_crud.for_conversation(conversation_id)
        return ConversationDetail(**_out(row, messages[-1].role if messages else None).model_dump(), messages=messages)


def get_all(agent_id: int | None = None) -> list[ConversationOut]:
    with db() as session:
        query = _summaries()
        if agent_id is not None:
            if session.get(AgentORM, agent_id) is None:
                raise NotFoundError("Agent", agent_id)
            query = query.where(ConversationORM.agent_id == agent_id)
        return [_out(row, role) for row, role in session.exec(query).all()]


def latest(agent_id: int) -> ConversationOut | None:
    with db() as session:
        if session.get(AgentORM, agent_id) is None:
            raise NotFoundError("Agent", agent_id)
        found = session.exec(_summaries().where(ConversationORM.agent_id == agent_id).limit(1)).first()
        return _out(*found) if found else None


def rename(conversation_id: int, title: str) -> ConversationOut:
    with db() as session:
        row = _row(session, conversation_id)
        row.title = title
        session.add(row)
        session.commit()
    return get(conversation_id)


def delete(conversation_id: int) -> None:
    with db() as session:
        session.delete(_row(session, conversation_id))
        session.commit()


def add_user_message(conversation_id: int, content: str) -> MessageOut:
    """Append a user message.

    Tool calls left unanswered by an interrupted turn get a "cancelled" response
    first, so the history stays valid for the LLM. The first user message gives an
    untitled conversation its title.
    """
    history = message_crud.for_conversation(conversation_id)
    for call in pending_tool_calls(history):
        message_crud.create(
            conversation_id,
            "tool-response",
            "Cancelled: the user sent a new message before this tool ran.",
            {"tool_call_id": call.get("id"), "name": call.get("name"), "status": "cancelled"},
        )
    with db() as session:
        row = _row(session, conversation_id)
        if row.title == DEFAULT_TITLE and not any(message.role == "user" for message in history):
            row.title = " ".join(content.split())[:TITLE_LENGTH] or DEFAULT_TITLE
            row.updated_at = datetime.now(timezone.utc)
            session.add(row)
            session.commit()
    return message_crud.create(conversation_id, "user", content)


def rewind(conversation_id: int, message_id: int) -> ConversationDetail:
    """Delete everything after ``message_id`` (to regenerate an answer or resend an edited prompt)."""
    message_crud.delete_after(conversation_id, message_id)
    return detail(conversation_id)
