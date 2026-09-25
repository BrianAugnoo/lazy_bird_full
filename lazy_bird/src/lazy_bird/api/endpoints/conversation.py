from fastapi import APIRouter, HTTPException
from lazy_bird.schemas.conversation import ConversationIn, ConversationOut
from lazy_bird.schemas.message import MessageOut
import lazy_bird.crud.conversation as ConversationCrud
import lazy_bird.crud.message as MessageCrud

router = APIRouter(prefix="/conversations", tags=["conversations"])

@router.get("/", response_model=list[ConversationOut])
async def get_conversations():
    return ConversationCrud.get_all()

@router.delete("/")
async def delete_all_conversations():
    try:
        ConversationCrud.delete_all()
        return {"message": "All conversations deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/", response_model=ConversationOut)
async def create_conversation(conversation: ConversationIn):
    return ConversationCrud.create(conversation)

@router.get("/{id}", response_model=ConversationOut)
async def get_conversation(id: int):
    conversation = ConversationCrud.get(id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/{id}/messages", response_model=list[MessageOut])
async def get_conversation_messages(id: int):
    # Verify conversation exists
    conversation = ConversationCrud.get(id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ConversationCrud.messages(id)

@router.delete("/{id}")
async def delete_conversation(id: int):
    try:
        success = ConversationCrud.delete_conversation(id)
        if not success:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return {"message": "Conversation deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
