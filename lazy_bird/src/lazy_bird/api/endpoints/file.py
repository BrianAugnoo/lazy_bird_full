from fastapi import APIRouter, File, Response, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel

import lazy_bird.crud.file as FileCrud
from lazy_bird.schemas.files import FileContentIn, FileOut, FileUpdate, ProcessRequest
from lazy_bird.schemas.task import TaskOut
from lazy_bird.storages import directories

router = APIRouter(prefix="/files", tags=["files"])


class PathOut(BaseModel):
    path: str


class DeletedOut(BaseModel):
    deleted: int


@router.post("/upload", response_model=list[FileOut])
async def upload_files(dir: str = "", files: list[UploadFile] = File(...)):
    """Store files in ``dir`` (relative to the storage); duplicate names get a numbered suffix."""
    return await FileCrud.creates(dir, files)


@router.get("/", response_model=list[FileOut])
def get_all_files():
    return FileCrud.get_all()


@router.get("/directories", response_model=list[str])
def list_directories():
    """Every directory of the storage (relative paths), empty ones included."""
    return directories()


@router.post("/directory", response_model=PathOut, status_code=201)
def create_directory(path: str):
    return PathOut(path=FileCrud.create_empty_directory(path))


@router.patch("/directory", response_model=PathOut)
def move_directory(source: str, destination: str):
    return PathOut(path=FileCrud.move_directory(source, destination))


@router.delete("/directory", response_model=PathOut)
def delete_directory(path: str):
    """Delete a directory and every file in it."""
    return PathOut(path=FileCrud.remove_directory(path))


@router.post("/scan", status_code=202, response_model=TaskOut)
def scan_files():
    """Look for files changed or removed on disk now."""
    from lazy_bird.tasks.default.files import schedule_scan

    return schedule_scan(0)


@router.delete("/", response_model=DeletedOut)
def delete_files(ids: list[int]):
    return DeletedOut(deleted=FileCrud.deletes(ids))


@router.delete("/all", response_model=DeletedOut)
def delete_all_files():
    return DeletedOut(deleted=FileCrud.delete_all())


@router.get("/{file_id}", response_model=FileOut)
def get_file(file_id: int):
    return FileCrud.get_out(file_id)


@router.get("/{file_id}/content", response_class=PlainTextResponse)
def get_file_content(file_id: int):
    """The text of a file (422 ``not_text`` for binary files)."""
    return PlainTextResponse(FileCrud.text_content(file_id), media_type="text/plain; charset=utf-8")


@router.put("/{file_id}/content", response_model=FileOut)
def update_file_content(file_id: int, payload: FileContentIn):
    return FileCrud.update_content(file_id, payload.content)


@router.get("/{file_id}/full")
def get_full_file(file_id: int):
    """The raw bytes of a file, to display it inline."""
    path, filename, media_type = FileCrud.download_info(file_id)
    return FileResponse(
        path,
        filename=filename,
        media_type=media_type or "application/octet-stream",
        content_disposition_type="inline",
    )


@router.get("/{file_id}/download")
def download_file(file_id: int):
    path, filename, media_type = FileCrud.download_info(file_id)
    return FileResponse(path, filename=filename, media_type=media_type)


@router.patch("/{file_id}", response_model=FileOut)
def update_file(file_id: int, payload: FileUpdate):
    """Rename and/or move a file."""
    from lazy_bird.errors import InvalidInputError

    if payload.name is None and payload.dir is None:
        raise InvalidInputError("Give a new name, a new directory, or both.", code="nothing_to_update")
    return FileCrud.update_file(file_id, name=payload.name, dir=payload.dir)


@router.post("/{file_id}/process", status_code=202, response_model=FileOut)
def process_file(file_id: int):
    """Queue what the file still needs: its chunks and the default embedding."""
    return FileCrud.process(file_id)


@router.post("/{file_id}/processing", status_code=202, response_model=FileOut)
def reprocess_file(file_id: int, payload: ProcessRequest):
    """Compute one processing again (e.g. embedding with a given model), even if up to date."""
    return FileCrud.reprocess(file_id, payload.processor, payload.target)
