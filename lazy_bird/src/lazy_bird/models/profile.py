from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from lazy_bird.models.user import User

# The table holds at most one row, with this id: the database refuses any other.
PROFILE_ID = 1


class Profile(SQLModel, table=True):
    __table_args__ = (CheckConstraint(f"id = {PROFILE_ID}", name="ck_profile_single_instance"),)

    id: int = Field(default=PROFILE_ID, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True)

    user: "User" = Relationship(back_populates="profile")
