from lazy_bird.database import db
from lazy_bird.models.message import Message as MessageORM
from lazy_bird.models.conversation import Conversation as ConversationORM
from lazy_bird.schemas.message import MessageOut, MessageIn, MessageUpdate
from sqlmodel import select, delete
from datetime import datetime, timezone

def get(id: int):
    with db() as session:
        message = session.get(MessageORM, id)
        if message is None:
            return None
        return MessageOut.model_validate(message)

def create(message_in: MessageIn):
    with db() as session:
        # Verify conversation exists
        conversation = session.get(ConversationORM, message_in.conversation_id)
        if conversation is None:
            return None
        
        message = MessageORM(
            conversation_id=message_in.conversation_id,
            role=message_in.role,
            meta=message_in.meta,
        )
        session.add(message)
        session.commit()
        session.refresh(message)
        return MessageOut.model_validate(message)

def delete(id: int):
    """Delete a message only if it's not from assistant and it's the most recent message in its conversation"""
    with db() as session:
        message = session.get(MessageORM, id)
        if message is None:
            return False
        
        # Check if role is assistant
        if message.role == "assistant":
            return False
        
        # Check if it's the most recent message in the conversation
        latest_message = session.exec(
            select(MessageORM)
            .where(MessageORM.conversation_id == message.conversation_id)
            .order_by(MessageORM.created_at.desc())
        ).first()
        
        if latest_message is None or latest_message.id != message.id:
            return False
        
        session.delete(message)
        session.commit()
        return True

def edit(id: int, message_update: MessageUpdate):
    """Edit a message only if it's not from assistant and it's the most recent message in its conversation"""
    with db() as session:
        message = session.get(MessageORM, id)
        if message is None:
            return None
        
        # Check if role is assistant
        if message.role == "assistant":
            return None
        
        # Check if it's the most recent message in the conversation
        latest_message = session.exec(
            select(MessageORM)
            .where(MessageORM.conversation_id == message.conversation_id)
            .order_by(MessageORM.created_at.desc())
        ).first()
        
        if latest_message is None or latest_message.id != message.id:
            return None
        
        # Update fields
        if message_update.role is not None:
            message.role = message_update.role
        if message_update.meta is not None:
            message.meta = message_update.meta
        
        message.updated_at = datetime.now(timezone.utc)
        session.add(message)
        session.commit()
        session.refresh(message)
        return MessageOut.model_validate(message)