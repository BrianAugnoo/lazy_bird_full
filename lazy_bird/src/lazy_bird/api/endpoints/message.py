from fastapi import APIRouter, Response

import lazy_bird.crud.message as MessageCrud
from lazy_bird.schemas.message import MessageOut, MessageUpdate

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("/{message_id}", response_model=MessageOut)
def get_message(message_id: int):
    return MessageCrud.get(message_id)


@router.patch("/{message_id}", response_model=MessageOut)
def edit_message(message_id: int, payload: MessageUpdate):
    """Edit a user or system message; rewind the conversation to answer it again."""
    return MessageCrud.edit(message_id, payload.content)


@router.delete("/{message_id}", status_code=204)
def delete_message(message_id: int):
    """Delete the last message of its conversation."""
    MessageCrud.delete(message_id)
    return Response(status_code=204)
