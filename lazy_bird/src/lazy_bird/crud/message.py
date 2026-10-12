"""Messages of conversations."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete as sql_delete
from sqlmodel import select

from lazy_bird.database import db
from lazy_bird.errors import ConflictError, InvalidInputError, NotFoundError
from lazy_bird.models.conversation import Conversation as ConversationORM
from lazy_bird.models.message import ROLES, Message as MessageORM
from lazy_bird.schemas.message import MessageOut

EDITABLE_ROLES = ("user", "system")


def _row(session, message_id: int) -> MessageORM:
    message = session.get(MessageORM, message_id)
    if message is None:
        raise NotFoundError("Message", message_id)
    return message


def get(message_id: int) -> MessageOut:
    with db() as session:
        return MessageOut.model_validate(_row(session, message_id))


def create(conversation_id: int, role: str, content: str | None = None, meta: dict[str, Any] | None = None) -> MessageOut:
    if role not in ROLES:
        raise InvalidInputError(f"Unknown role '{role}'.", code="invalid_role")
    with db() as session:
        conversation = session.get(ConversationORM, conversation_id)
        if conversation is None:
            raise NotFoundError("Conversation", conversation_id)
        message = MessageORM(conversation_id=conversation_id, role=role, content=content, meta=meta)
        conversation.updated_at = datetime.now(timezone.utc)
        session.add_all([message, conversation])
        session.commit()
        session.refresh(message)
        return MessageOut.model_validate(message)


def for_conversation(conversation_id: int) -> list[MessageOut]:
    with db() as session:
        rows = session.exec(select(MessageORM).where(MessageORM.conversation_id == conversation_id).order_by(MessageORM.id)).all()
        return [MessageOut.model_validate(row) for row in rows]


def edit(message_id: int, content: str) -> MessageOut:
    """Change the text of a user or system message (follow with a rewind to answer it again)."""
    with db() as session:
        message = _row(session, message_id)
        if message.role not in EDITABLE_ROLES:
            raise ConflictError(f"Only {' and '.join(EDITABLE_ROLES)} messages can be edited.", code="message_not_editable")
        message.content = content
        message.updated_at = datetime.now(timezone.utc)
        session.add(message)
        session.commit()
        session.refresh(message)
        return MessageOut.model_validate(message)


def delete_after(conversation_id: int, message_id: int) -> int:
    """Delete every message of a conversation after ``message_id``; return how many."""
    with db() as session:
        anchor = _row(session, message_id)
        if anchor.conversation_id != conversation_id:
            raise NotFoundError("Message", message_id)
        deleted = session.execute(sql_delete(MessageORM).where(MessageORM.conversation_id == conversation_id, MessageORM.id > message_id)).rowcount
        session.commit()
        return deleted


def delete(message_id: int) -> None:
    """Delete the last message of its conversation."""
    with db() as session:
        message = _row(session, message_id)
        last_id = session.exec(select(MessageORM.id).where(MessageORM.conversation_id == message.conversation_id).order_by(MessageORM.id.desc()).limit(1)).first()
        if last_id != message.id:
            raise ConflictError("Only the last message can be deleted; rewind the conversation to remove several.", code="message_not_last")
        session.delete(message)
        session.commit()
