from datetime import datetime, timezone

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False)
    description: str | None = Field(default=None)
    profession: str | None = Field(default=None)
    email: str | None = Field(default=None)
    age: int | None = Field(default=None)
    # Spoken languages, the one the user masters best first.
    languages: list[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    meta: dict | None = Field(default=None, sa_column=Column(JSON, nullable=True))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), nullable=False)
