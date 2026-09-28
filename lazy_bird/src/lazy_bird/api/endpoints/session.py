from fastapi import APIRouter, HTTPException
import lazy_bird.crud.session as SessionCrud
from lazy_bird.schemas.session import SessionIn, SessionOut

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("/", response_model=list[SessionOut])
async def get_all_sessions():
    return SessionCrud.get_all()


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: int):
    session = SessionCrud.get_by_id(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/", response_model=SessionOut, status_code=201)
async def create_session(payload: SessionIn):
    return SessionCrud.create(payload)


@router.patch("/{session_id}", response_model=SessionOut)
async def update_session(session_id: int, payload: SessionIn):
    session = SessionCrud.update(session_id, payload)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/{session_id}")
async def delete_session(session_id: int):
    deleted = SessionCrud.delete(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted successfully"}