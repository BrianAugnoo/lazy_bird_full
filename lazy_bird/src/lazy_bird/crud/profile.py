"""Profile: the single record saying which user the agents currently work for.

With at least one user there is always a profile; without any there is none. It points
to the first user added until another one is chosen, and moves on when its user is deleted.
"""

from sqlmodel import select

from lazy_bird.database import db
from lazy_bird.errors import NotFoundError
from lazy_bird.models.profile import PROFILE_ID, Profile as ProfileORM
from lazy_bird.models.user import User as UserORM
from lazy_bird.schemas.profile import ProfileOut
from lazy_bird.schemas.user import UserOut


def _first_user_id(session, *, excluding: int | None = None) -> int | None:
    statement = select(UserORM.id).order_by(UserORM.id).limit(1)
    if excluding is not None:
        statement = statement.where(UserORM.id != excluding)
    return session.exec(statement).first()


def ensure(session) -> None:
    """Create the profile on the first user when users exist but it does not (no commit)."""
    if session.get(ProfileORM, PROFILE_ID) is not None:
        return
    first = _first_user_id(session)
    if first is not None:
        session.add(ProfileORM(user_id=first))


def release(session, user_id: int) -> None:
    """Hand the profile to the next user (or drop it) before `user_id` is deleted (no commit)."""
    profile = session.get(ProfileORM, PROFILE_ID)
    if profile is None or profile.user_id != user_id:
        return
    successor = _first_user_id(session, excluding=user_id)
    if successor is None:
        session.delete(profile)
    else:
        profile.user_id = successor
        session.add(profile)
    session.flush()


def get() -> ProfileOut:
    with db() as session:
        profile = session.get(ProfileORM, PROFILE_ID)
        if profile is None:
            return ProfileOut()
        return ProfileOut(user_id=profile.user_id, user=UserOut.model_validate(profile.user))


def switch_to(user_id: int) -> ProfileOut:
    with db() as session:
        if session.get(UserORM, user_id) is None:
            raise NotFoundError("User", user_id)
        profile = session.get(ProfileORM, PROFILE_ID)
        if profile is None:
            session.add(ProfileORM(user_id=user_id))
        else:
            profile.user_id = user_id
            session.add(profile)
        session.commit()
    return get()
