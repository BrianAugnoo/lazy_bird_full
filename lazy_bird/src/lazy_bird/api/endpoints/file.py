from fastapi import APIRouter, UploadFile, File, HTTPException
import lazy_bird.crud.file as FileCrud
from lazy_bird.task_queue import enqueue_file

router = APIRouter(prefix="/files", tags=["files"])

@router.post("/upload")
async def upload_files(dir: str, files: list[UploadFile] = File(...)):
    return await FileCrud.creates(dir, files)

@router.get("/")
async def get_all_files():
    return FileCrud.get_all()

@router.get("/{file_id}")
async def get_file(file_id: int):
    return FileCrud.find(file_id)

@router.post("/{file_id}/process", status_code=202)
async def process_file(file_id: int):
    if FileCrud.get(file_id) is None:
        raise HTTPException(status_code=404, detail="File not found")
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
