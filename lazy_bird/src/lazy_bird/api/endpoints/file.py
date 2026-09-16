from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
import lazy_bird.crud.file as FileCrud
from lazy_bird.schemas.files import FileContentIn, FileOut, FileUpdate
from lazy_bird.task_queue import enqueue_file, queued_file_ids

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload", response_model=list[FileOut])
async def upload_files(dir: str, files: list[UploadFile] = File(...)):
    try:
        return await FileCrud.creates(dir, files)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

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

@router.post("/{file_id}/process", status_code=202)
async def process_file(file_id: int):
    if FileCrud.get(file_id) is None:
        raise HTTPException(status_code=404, detail="File not found")
    if file_id not in FileCrud.files_requiring_embedding():
        return {"file_id": file_id, "queued": False}
    if file_id in queued_file_ids():
        return {"file_id": file_id, "queued": False}
    task = enqueue_file(file_id)
    return {"file_id": file_id, "task_id": task.id}

@router.delete("/")
async def delete_files(ids: list[int]):
    FileCrud.deletes(ids)
    return {"message": "Files deleted successfully."}

@router.delete("/delete_all")
async def delete_all_files():
    FileCrud.delete_all()
    return {"message": "All files deleted successfully."}
