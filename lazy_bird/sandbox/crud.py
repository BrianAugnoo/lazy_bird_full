from __future__ import annotations

from sqlmodel import Session, select

from .models import Document, DocumentLink
from .storage import (
    delete_document_file,
    move_document,
    normalize_document_name,
    write_document,
)


class DocumentNotFound(LookupError):
    pass


class DuplicateDocument(ValueError):
    pass


def get_document(session: Session, document_id: int) -> Document:
    document = session.get(Document, document_id)
    if document is None:
        raise DocumentNotFound(f"Document {document_id} was not found")
    return document


def list_documents(session: Session, query: str | None = None) -> list[Document]:
    statement = select(Document).order_by(Document.name)
    if query:
        statement = statement.where(Document.name.contains(query))
    return list(session.exec(statement).all())


def related_document_ids(session: Session, document_id: int) -> set[int]:
    rows = session.exec(
        select(DocumentLink.right_document_id).where(
            DocumentLink.left_document_id == document_id
        )
    ).all()
    return {int(row) for row in rows}


def related_documents(session: Session, document_id: int) -> list[Document]:
    ids = related_document_ids(session, document_id)
    if not ids:
        return []
    docs = session.exec(
        select(Document).where(Document.id.in_(ids)).order_by(Document.name)
    ).all()
    return list(docs)


def _validate_related_ids(
    session: Session, document_id: int, related_ids: list[int] | None
) -> set[int]:
    if related_ids is None:
        return related_document_ids(session, document_id)
    desired = {int(item) for item in related_ids}
    if document_id in desired:
        raise ValueError("A document cannot be related to itself")
    if desired:
        found = set(
            session.exec(select(Document.id).where(Document.id.in_(desired))).all()
        )
        missing = desired - {int(item) for item in found if item is not None}
        if missing:
            raise DocumentNotFound(
                "Related document(s) not found: " + ", ".join(map(str, sorted(missing)))
            )
    return desired


def set_related_documents(
    session: Session, document_id: int, related_ids: list[int] | set[int]
) -> list[Document]:
    desired = _validate_related_ids(session, document_id, list(related_ids))
    current = related_document_ids(session, document_id)
    for target_id in current - desired:
        links = session.exec(
            select(DocumentLink).where(
                (
                    (DocumentLink.left_document_id == document_id)
                    & (DocumentLink.right_document_id == target_id)
                )
                | (
                    (DocumentLink.left_document_id == target_id)
                    & (DocumentLink.right_document_id == document_id)
                )
            )
        ).all()
        for link in links:
            session.delete(link)
    for target_id in desired:
        for left_id, right_id in ((document_id, target_id), (target_id, document_id)):
            if session.get(DocumentLink, (left_id, right_id)) is None:
                session.add(
                    DocumentLink(
                        left_document_id=left_id,
                        right_document_id=right_id,
                    )
                )
    session.commit()
    return related_documents(session, document_id)


def create_document(
    session: Session,
    *,
    name: str,
    content: str = "",
    subfolder: str | None = None,
    related_ids: list[int] | None = None,
) -> Document:
    normalized = normalize_document_name(name, subfolder)
    existing = session.exec(select(Document).where(Document.name == normalized)).first()
    if existing is not None:
        raise DuplicateDocument(f"A document named {normalized!r} already exists")
    document = Document(name=normalized)
    session.add(document)
    session.commit()
    session.refresh(document)
    try:
        write_document(normalized, content)
        set_related_documents(session, int(document.id), related_ids or [])
    except Exception:
        session.delete(document)
        session.commit()
        delete_document_file(normalized)
        raise
    return document


def update_document(
    session: Session,
    document_id: int,
    *,
    name: str | None = None,
    content: str | None = None,
    subfolder: str | None = None,
    related_ids: list[int] | None = None,
) -> Document:
    document = get_document(session, document_id)
    if related_ids is not None:
        _validate_related_ids(session, document_id, related_ids)
    old_name = document.name
    requested_name = name
    if requested_name is None and subfolder is not None:
        requested_name = old_name.rsplit("/", 1)[-1]
    new_name = (
        normalize_document_name(requested_name, subfolder)
        if requested_name is not None
        else old_name
    )
    if new_name != old_name:
        duplicate = session.exec(
            select(Document).where(Document.name == new_name, Document.id != document_id)
        ).first()
        if duplicate is not None:
            raise DuplicateDocument(f"A document named {new_name!r} already exists")
        move_document(old_name, new_name)
        document.name = new_name
    if content is not None:
        write_document(new_name, content)
    session.add(document)
    session.commit()
    if related_ids is not None:
        set_related_documents(session, document_id, related_ids)
    return document


def delete_document(session: Session, document_id: int) -> None:
    document = get_document(session, document_id)
    name = document.name
    session.delete(document)
    session.commit()
    delete_document_file(name)
