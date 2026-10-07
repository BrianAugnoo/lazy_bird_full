from fastapi import APIRouter, Response

import lazy_bird.crud.session as SessionCrud
from lazy_bird.schemas.conversation import ChatIn, ConversationDetail
from lazy_bird.schemas.session import SessionFromPreset, SessionIn, SessionOut, SessionUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/", response_model=list[SessionOut])
def get_all_sessions():
    return SessionCrud.get_all()


@router.post("/", response_model=SessionOut, status_code=201)
def create_session(payload: SessionIn):
    return SessionCrud.create(payload)


@router.post("/from-preset", response_model=SessionOut, status_code=201)
def create_session_from_preset(payload: SessionFromPreset):
    """Create a session with the agents of a session preset and its master."""
    return SessionCrud.create_from_preset(payload.preset_id, payload.title)


@router.get("/{session_id}", response_model=SessionOut)
def get_session(session_id: int):
    return SessionCrud.get(session_id)


@router.patch("/{session_id}", response_model=SessionOut)
def update_session(session_id: int, payload: SessionUpdate):
    return SessionCrud.update(session_id, payload.model_dump(exclude_unset=True))


@router.delete("/{session_id}", status_code=204)
def delete_session(session_id: int):
    SessionCrud.delete(session_id)
    return Response(status_code=204)


@router.post("/{session_id}/chat", response_model=ConversationDetail, status_code=201)
def chat(session_id: int, payload: ChatIn):
    """Send a prompt to the session's master agent; run the returned conversation to get the answer."""
    return SessionCrud.chat(session_id, payload.content, payload.conversation_id)
