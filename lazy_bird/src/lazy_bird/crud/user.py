"""Users: who the agents work for (name, profession, what they want agents to know)."""

from datetime import datetime, timezone
from typing import Any

from sqlmodel import select

from lazy_bird.database import db
from lazy_bird.errors import InvalidInputError, NotFoundError
from lazy_bird.models.user import User as UserORM
from lazy_bird.schemas.user import UserIn, UserOut


def _row(session, user_id: int) -> UserORM:
    found = session.get(UserORM, user_id)
    if found is None:
        raise NotFoundError("User", user_id)
    return found


def get_all() -> list[UserOut]:
    with db() as session:
        return [UserOut.model_validate(item) for item in session.exec(select(UserORM).order_by(UserORM.id)).all()]


def get(user_id: int) -> UserOut:
    with db() as session:
        return UserOut.model_validate(_row(session, user_id))


def create(payload: UserIn) -> UserOut:
    with db() as session:
        created = UserORM(**payload.model_dump())
        session.add(created)
        session.commit()
        session.refresh(created)
        return UserOut.model_validate(created)


def update(user_id: int, changes: dict[str, Any]) -> UserOut:
    for required in ("name", "languages"):
        if required in changes and changes[required] is None:
            raise InvalidInputError(f"A user needs a value for '{required}'.")
    with db() as session:
        found = _row(session, user_id)
        for key, value in changes.items():
            setattr(found, key, value)
        found.updated_at = datetime.now(timezone.utc)
        session.add(found)
        session.commit()
        session.refresh(found)
        return UserOut.model_validate(found)


def delete(user_id: int) -> None:
    with db() as session:
        session.delete(_row(session, user_id))
        session.commit()
