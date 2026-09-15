from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class DocumentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=512)
    content: str = ""
    subfolder: str | None = None
    related_docs: list[int] = Field(default_factory=list)


class DocumentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=512)
    content: str | None = None
    subfolder: str | None = None
    related_docs: list[int] | None = None


class RelatedDocument(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class DocumentOut(BaseModel):
    id: int
    name: str
    content: str
    related_docs: list[RelatedDocument]


class DocumentSummary(BaseModel):
    id: int
    name: str
    related_docs: list[RelatedDocument]

