from lazy_bird.database import db
from lazy_bird.models.conversation import Conversation as ConversationORM
from lazy_bird.models.message import Message as MessageORM
from lazy_bird.schemas.conversation import ConversationOut, ConversationIn
from lazy_bird.schemas.message import MessageOut
from sqlmodel import select, delete
from datetime import datetime, timezone

def create(conversation_in: ConversationIn):
    with db() as session:
        conversation = ConversationORM(**conversation_in.model_dump())
        session.add(conversation)
        session.commit()
        session.refresh(conversation)
        return ConversationOut.model_validate(conversation)

def get_all():
    with db() as session:
        statement = select(ConversationORM)
        conversations = session.exec(statement).all()
        return [ConversationOut.model_validate(conv) for conv in conversations]

def get(id: int):
    with db() as session:
        conversation = session.get(ConversationORM, id)
        if conversation is None:
            return None
        return ConversationOut.model_validate(conversation)

def messages(conversation_id: int):
    """Get all messages for a conversation, ordered by created_at (oldest first)"""
    with db() as session:
        statement = select(MessageORM).where(MessageORM.conversation_id == conversation_id).order_by(MessageORM.created_at)
        messages = session.exec(statement).all()
        return [MessageOut.model_validate(msg) for msg in messages]

def delete_conversation(id: int):
    with db() as session:
        conversation = session.get(ConversationORM, id)
        if conversation is None:
            return False
        session.delete(conversation)
        session.commit()
        return True
    
def delete_all():
    with db() as session:
        # Delete messages first (foreign key constraint)
        session.execute(delete(MessageORM))
        # Then delete conversations
        session.execute(delete(ConversationORM))
        session.commit()
        return True