from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session

from .crud import (
    DocumentNotFound,
    DuplicateDocument,
    create_document,
    delete_document,
    get_document,
    list_documents,
    related_documents,
    set_related_documents,
    update_document,
)
from .database import get_session, init_db
from .schemas import DocumentCreate, DocumentOut, DocumentSummary, DocumentUpdate
from .storage import InvalidDocumentPath, read_document


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Document Atlas",
    description="Sandbox for building and exploring a document relationship dataset.",
    version="0.1.0",
    lifespan=lifespan,
)


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, DocumentNotFound):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, DuplicateDocument):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, (InvalidDocumentPath, ValueError)):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="Document operation failed")


def _summary(session: Session, document) -> DocumentSummary:
    return DocumentSummary(
        id=int(document.id),
        name=document.name,
        related_docs=[
            {"id": int(item.id), "name": item.name}
            for item in related_documents(session, int(document.id))
        ],
    )


def _output(session: Session, document) -> DocumentOut:
    return DocumentOut(
        id=int(document.id),
        name=document.name,
        content=read_document(document.name),
        related_docs=[
            {"id": int(item.id), "name": item.name}
            for item in related_documents(session, int(document.id))
        ],
    )


def _create(session: Session, payload: DocumentCreate):
    try:
        return create_document(
            session,
            name=payload.name,
            content=payload.content,
            subfolder=payload.subfolder,
            related_ids=payload.related_docs,
        )
    except Exception as error:
        raise _http_error(error) from error


def _update(session: Session, document_id: int, payload: DocumentUpdate):
    try:
        return update_document(
            session,
            document_id,
            name=payload.name,
            content=payload.content,
            subfolder=payload.subfolder,
            related_ids=payload.related_docs,
        )
    except Exception as error:
        raise _http_error(error) from error


@app.get("/api/documents", response_model=list[DocumentSummary], tags=["documents"])
@app.get("/documents", response_model=list[DocumentSummary], tags=["documents"])
def api_list_documents(
    query: str | None = Query(default=None, description="Filter by document name"),
    session: Session = Depends(get_session),
):
    return [_summary(session, item) for item in list_documents(session, query)]


@app.post(
    "/api/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
@app.post(
    "/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    tags=["documents"],
)
def api_create_document(payload: DocumentCreate, session: Session = Depends(get_session)):
    return _output(session, _create(session, payload))


@app.get(
    "/api/documents/{document_id}", response_model=DocumentOut, tags=["documents"]
)
@app.get("/documents/{document_id}", response_model=DocumentOut, tags=["documents"])
def api_get_document(document_id: int, session: Session = Depends(get_session)):
    try:
        return _output(session, get_document(session, document_id))
    except Exception as error:
        raise _http_error(error) from error


@app.put(
    "/api/documents/{document_id}", response_model=DocumentOut, tags=["documents"]
)
@app.patch(
    "/api/documents/{document_id}", response_model=DocumentOut, tags=["documents"]
)
@app.put("/documents/{document_id}", response_model=DocumentOut, tags=["documents"])
@app.patch("/documents/{document_id}", response_model=DocumentOut, tags=["documents"])
def api_update_document(
    document_id: int,
    payload: DocumentUpdate,
    session: Session = Depends(get_session),
):
    return _output(session, _update(session, document_id, payload))


@app.delete(
    "/api/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["documents"],
)
@app.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["documents"],
)
def api_delete_document(document_id: int, session: Session = Depends(get_session)):
    try:
        delete_document(session, document_id)
    except Exception as error:
        raise _http_error(error) from error


@app.post(
    "/api/documents/{document_id}/relations/{related_id}",
    response_model=DocumentOut,
    tags=["relations"],
)
@app.post(
    "/documents/{document_id}/relations/{related_id}",
    response_model=DocumentOut,
    tags=["relations"],
)
def api_add_relation(
    document_id: int, related_id: int, session: Session = Depends(get_session)
):
    try:
        get_document(session, document_id)
        get_document(session, related_id)
        current = {int(item.id) for item in related_documents(session, document_id)}
        current.add(related_id)
        set_related_documents(session, document_id, current)
        return _output(session, get_document(session, document_id))
    except Exception as error:
        raise _http_error(error) from error


@app.delete(
    "/api/documents/{document_id}/relations/{related_id}",
    response_model=DocumentOut,
    tags=["relations"],
)
@app.delete(
    "/documents/{document_id}/relations/{related_id}",
    response_model=DocumentOut,
    tags=["relations"],
)
def api_remove_relation(
    document_id: int, related_id: int, session: Session = Depends(get_session)
):
    try:
        document = get_document(session, document_id)
        current = {int(item.id) for item in related_documents(session, document_id)}
        current.discard(related_id)
        set_related_documents(session, document_id, current)
        return _output(session, document)
    except Exception as error:
        raise _http_error(error) from error


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard(
    request: Request,
    selected: int | None = Query(default=None),
    query: str | None = Query(default=None),
    new: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    documents = list_documents(session, query)
    all_documents = list_documents(session)
    current = None
    if selected is not None and not new:
        try:
            current = get_document(session, selected)
        except DocumentNotFound:
            current = None
    if current is None and documents and not new:
        current = documents[0]
    current_output = _output(session, current).model_dump() if current else None
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "documents": documents,
            "all_documents": all_documents,
            "selected": current_output,
            "related_ids": {
                item["id"] for item in current_output["related_docs"]
            } if current_output else set(),
            "query": query or "",
        },
    )


@app.post("/ui/documents", response_class=HTMLResponse, include_in_schema=False)
def ui_create_document(
    name: str = Form(...),
    content: str = Form(""),
    subfolder: str = Form(""),
    session: Session = Depends(get_session),
):
    document = _create(
        session,
        DocumentCreate(name=name, content=content, subfolder=subfolder or None),
    )
    return RedirectResponse(url=f"/?selected={document.id}", status_code=303)


@app.post(
    "/ui/documents/{document_id}",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def ui_update_document(
    document_id: int,
    name: str = Form(...),
    content: str = Form(""),
    subfolder: str = Form(""),
    session: Session = Depends(get_session),
):
    document = _update(
        session,
        document_id,
        DocumentUpdate(name=name, content=content, subfolder=subfolder or None),
    )
    return RedirectResponse(url=f"/?selected={document.id}", status_code=303)


@app.post(
    "/ui/documents/{document_id}/delete",
    response_class=HTMLResponse,
    include_in_schema=False,
)
def ui_delete_document(document_id: int, session: Session = Depends(get_session)):
    try:
        delete_document(session, document_id)
    except Exception as error:
        raise _http_error(error) from error
    return RedirectResponse(url="/", status_code=303)
