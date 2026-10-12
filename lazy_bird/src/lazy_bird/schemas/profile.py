from pydantic import BaseModel

from lazy_bird.schemas.user import UserOut


class ProfileOut(BaseModel):
    """The user the agents currently work for; both are `null` until a user exists."""

    user_id: int | None = None
    user: UserOut | None = None


class ProfileIn(BaseModel):
    user_id: int
