from lazy_bird.database import db
from lazy_bird.models.session import Session as SessionORM
from lazy_bird.schemas.session import SessionIn, SessionOut
from sqlmodel import select


def get_all() -> list[SessionOut]:
    with db() as session:
        statement = select(SessionORM)
        sessions = session.exec(statement).all()
        return [SessionOut.model_validate(s) for s in sessions]


def get_by_id(id: int) -> SessionOut | None:
    with db() as session:
        session_orm = session.get(SessionORM, id)
        if session_orm is None:
            return None
        return SessionOut.model_validate(session_orm)


def create(payload: SessionIn) -> SessionOut:
    with db() as session:
        session_orm = SessionORM(**payload.model_dump())
        session.add(session_orm)
        session.commit()
        session.refresh(session_orm)
        return SessionOut.model_validate(session_orm)


def update(id: int, payload: SessionIn) -> SessionOut | None:
    with db() as session:
        session_orm = session.get(SessionORM, id)
        if session_orm is None:
            return None
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(session_orm, key, value)
        session.add(session_orm)
        session.commit()
        session.refresh(session_orm)
        return SessionOut.model_validate(session_orm)


def delete(id: int) -> bool:
    with db() as session:
        session_orm = session.get(SessionORM, id)
        if session_orm is None:
            return False
        session.delete(session_orm)
        session.commit()
        return True