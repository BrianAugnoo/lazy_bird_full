from fastapi import APIRouter, UploadFile, File, HTTPException
from lazy_bird.errors import NotFoundError
from fastapi.responses import FileResponse, PlainTextResponse, Response
import lazy_bird.crud.file as FileCrud
from lazy_bird.schemas.files import FileContentIn, FileOut, FileUpdate
from lazy_bird.schemas.task import TaskOut

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload", response_model=list[FileOut])
async def upload_files(dir: str, files: list[UploadFile] = File(...)):
    try:
        return await FileCrud.creates(dir, files)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@router.post("/directory")
def create_directory(path: str):
    try:
        created_path = FileCrud.create_empty_directory(path)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"path": created_path}


@router.patch("/directory")
def move_directory(source: str, destination: str):
    try:
        moved_path = FileCrud.move_directory(source, destination)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"path": moved_path}


@router.delete("/directory")
def delete_directory(path: str):
    try:
        deleted_path = FileCrud.delete_empty_directory(path)
    except FileNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"path": deleted_path}

@router.get("/", response_model=list[FileOut])
async def get_all_files():
    return FileCrud.get_all()

@router.get("/{file_id}")
async def get_file(file_id: int) -> FileOut | None:
    return FileCrud.find(file_id)


@router.get("/{file_id}/content")
async def get_file_content(file_id: int):
    result = FileCrud.content(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    file, content = result
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


@router.get("/{file_id}/full")
async def get_full_file(file_id: int):
    result = FileCrud.full(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    content, filename, media_type = result
    return Response(
        content=content,
        media_type=media_type or "application/octet-stream",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


@router.get("/{file_id}/download")
async def download_file(file_id: int):
    result = FileCrud.download_info(file_id)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    path, filename, media_type = result
    return FileResponse(path, filename=filename, media_type=media_type)


@router.put("/{file_id}/content", response_model=FileOut)
async def update_file_content(file_id: int, payload: FileContentIn):
    result = FileCrud.update_content(file_id, payload.content)
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return result


@router.patch("/{file_id}", response_model=FileOut)
async def update_file(file_id: int, payload: FileUpdate):
    if payload.name is None and payload.dir is None:
        raise HTTPException(status_code=422, detail="At least one field is required")
    try:
        result = FileCrud.update_file(file_id, name=payload.name, dir=payload.dir)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if result is None:
        raise HTTPException(status_code=404, detail="File not found")
    return result

@router.post("/{file_id}/process", status_code=202, response_model=TaskOut)
async def process_file(file_id: int):
    """Queue (or return the already active) processing task of a file."""
    if FileCrud.get(file_id) is None:
        raise NotFoundError("File", file_id)
    return FileCrud.enqueue_file(file_id)

@router.delete("/")
async def delete_files(ids: list[int]):
    FileCrud.deletes(ids)
    return {"message": "Files deleted successfully."}

@router.delete("/delete_all")
async def delete_all_files():
    try:
        FileCrud.delete_all()
        return {"message": "All files deleted successfully."}
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
