from sqlalchemy import MetaData
from sqlmodel import Field, Relationship, SQLModel


class SandboxModel(SQLModel):
    metadata = MetaData()


class DocumentLink(SandboxModel, table=True):
    """A directed edge in the document graph.

    The service writes one row in each direction for every relationship. Keeping
    the rows directed makes SQLModel's self-referential relationship explicit
    while presenting a symmetric graph to API and CLI clients.
    """

    left_document_id: int = Field(
        foreign_key="document.id", primary_key=True, ondelete="CASCADE"
    )
    right_document_id: int = Field(
        foreign_key="document.id", primary_key=True, ondelete="CASCADE"
    )


class Document(SandboxModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True, max_length=512)

    related_docs: list["Document"] = Relationship(
        link_model=DocumentLink,
        sa_relationship_kwargs={
            "primaryjoin": "Document.id == DocumentLink.left_document_id",
            "secondaryjoin": "Document.id == DocumentLink.right_document_id",
            "overlaps": "related_docs,related_to",
        },
    )
    related_to: list["Document"] = Relationship(
        link_model=DocumentLink,
        sa_relationship_kwargs={
            "primaryjoin": "Document.id == DocumentLink.right_document_id",
            "secondaryjoin": "Document.id == DocumentLink.left_document_id",
            "overlaps": "related_docs,related_to",
        },
    )
