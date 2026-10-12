from typing import Annotated, Any

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from lazy_bird.schemas.types import UtcDatetime


def _ranked_languages(languages: list[str]) -> list[str]:
    cleaned = [language.strip() for language in languages]
    if any(not language for language in cleaned):
        raise ValueError("A language cannot be empty.")
    if len({language.casefold() for language in cleaned}) != len(cleaned):
        raise ValueError("A language can only appear once.")
    return cleaned


Languages = Annotated[
    list[str],
    AfterValidator(_ranked_languages),
    Field(description='Languages the user speaks, the best mastered first, e.g. ["French", "English"].'),
]
Age = Annotated[int, Field(ge=0, le=150)]


class UserOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    profession: str | None = None
    email: str | None = None
    age: int | None = None
    languages: list[str]
    meta: dict[str, Any] | None = None
    created_at: UtcDatetime
    updated_at: UtcDatetime

    model_config = ConfigDict(from_attributes=True)


class UserIn(BaseModel):
    name: str = Field(min_length=1)
    description: str | None = None
    profession: str | None = None
    email: str | None = None
    age: Age | None = None
    languages: Languages = []
    meta: dict[str, Any] | None = None


class UserUpdate(BaseModel):
    """Only the fields sent are changed; `null` clears an optional field."""

    name: str | None = Field(default=None, min_length=1)
    description: str | None = None
    profession: str | None = None
    email: str | None = None
    age: Age | None = None
    languages: Languages | None = None
    meta: dict[str, Any] | None = None
