from fastapi import APIRouter, HTTPException
from lazy_bird.schemas.message import MessageIn, MessageOut, MessageUpdate
import lazy_bird.crud.message as MessageCrud

router = APIRouter(prefix="/messages", tags=["messages"])

@router.get("/{id}", response_model=MessageOut)
async def get_message(id: int):
    message = MessageCrud.get(id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found")
    return message

@router.post("/", response_model=MessageOut)
async def create_message(message: MessageIn):
    result = MessageCrud.create(message)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result

@router.delete("/{id}")
async def delete_message(id: int):
    success = MessageCrud.delete(id)
    if not success:
        raise HTTPException(status_code=404, detail="Message not found or cannot be deleted (must be non-assistant and most recent)")
    return {"message": "Message deleted"}

@router.patch("/{id}", response_model=MessageOut)
async def edit_message(id: int, message_update: MessageUpdate):
    result = MessageCrud.edit(id, message_update)
    if result is None:
        raise HTTPException(status_code=404, detail="Message not found or cannot be edited (must be non-assistant and most recent)")
    return result