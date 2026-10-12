import shutil

import anyio
from fastapi import APIRouter, Query, Request, Response
from fastapi.concurrency import run_in_threadpool

import lazy_bird.crud.llm_model as LLMModel
from lazy_bird.errors import ExternalServiceError, InvalidInputError
from lazy_bird.schemas.llm_model import HubFileOut, LLMModelIn, LLMModelOut, LLMModelUpdate, UploadedFileOut
from lazy_bird.schemas.task import TaskOut
from lazy_bird.tools import hf_cache
from lazy_bird.tools.model_extraction import list_repo_files

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/", response_model=list[LLMModelOut])
def get_llm_models(format: list[str] | None = Query(default=None, description="Only models available in one of these formats")):
    return LLMModel.get_all(format)


@router.post("/", response_model=TaskOut, status_code=202)
def download_llm_model(payload: LLMModelIn):
    """Queue the download of a Hugging Face model (follow it in /tasks)."""
    from lazy_bird.tasks.default.models import download

    return download.submit(hf_path=payload.hf_path, files=payload.files, revision=payload.revision, dedupe_key=f"models.download:{payload.hf_path}")


def _local_repo(name: str) -> str:
    try:
        return f"{hf_cache.LOCAL_NAMESPACE}/{hf_cache.slug(name)}"
    except ValueError as error:
        raise InvalidInputError(str(error), code="invalid_model_name", details={"fields": {"name": str(error)}}) from error


@router.put("/uploads/{name}/files/{path:path}", response_model=UploadedFileOut)
async def upload_model_file(name: str, path: str, request: Request):
    """Receive one file of a model (raw request body), e.g. ``model.gguf`` or ``config.json``.

    Upload every file of the model this way, then ``POST /models/uploads/{name}``.
    """
    await run_in_threadpool(LLMModel.ensure_absent, _local_repo(name))
    try:
        target = await run_in_threadpool(hf_cache.staged_path, name, path)
    except ValueError as error:
        raise InvalidInputError(str(error), code="invalid_path") from error
    await run_in_threadpool(target.parent.mkdir, parents=True, exist_ok=True)
    partial = target.with_name(f".{target.name}.part")  # hidden: ignored if the upload stops midway
    size = 0
    async with await anyio.open_file(partial, "wb") as stream:
        async for chunk in request.stream():
            await stream.write(chunk)
            size += len(chunk)
    await run_in_threadpool(partial.replace, target)
    return UploadedFileOut(path=target.relative_to(hf_cache.staging_folder(name)).as_posix(), size=size)


@router.post("/uploads/{name}", response_model=TaskOut, status_code=202)
def import_uploaded_model(name: str):
    """Queue the import of the uploaded files as the model ``local/<name>``."""
    from lazy_bird.tasks.default.models import import_model

    repo_id = _local_repo(name)
    LLMModel.ensure_absent(repo_id)
    folder = hf_cache.staging_folder(name)
    if not folder.is_dir() or not any(path.is_file() and not path.name.startswith(".") for path in folder.rglob("*")):
        raise InvalidInputError("Upload the model files first.", code="nothing_uploaded")
    return import_model.submit(path=str(folder), name=name, staged=True, dedupe_key=f"models.import:{hf_cache.slug(name)}")


@router.delete("/uploads/{name}", status_code=204)
def discard_uploaded_model(name: str):
    """Delete the files uploaded for a model that will not be imported."""
    _local_repo(name)
    shutil.rmtree(hf_cache.staging_folder(name), ignore_errors=True)
    return Response(status_code=204)


@router.post("/sync")
def sync_llm_models() -> dict[str, list[str]]:
    """Register every model found in the Hugging Face cache and repair broken paths."""
    return LLMModel.sync_cache()


@router.get("/hub/status")
def hub_status() -> dict:
    """Hugging Face login state (store an API key named "HuggingFace" to log in)."""
    from lazy_bird.tools.hf_auth import hub_status as status

    return status()


@router.post("/hub/login")
def hub_login() -> dict:
    """Log in to Hugging Face again with the stored "HuggingFace" API key."""
    from lazy_bird.tools.hf_auth import authenticate_hf, hub_status as status

    authenticate_hf()
    return status()


@router.get("/hub/{repo_id:path}/files", response_model=list[HubFileOut])
def list_hub_files(repo_id: str, revision: str | None = None):
    """Files of a Hugging Face repository, to choose which weights to download."""
    try:
        return list_repo_files(repo_id, revision)
    except Exception as error:
        raise ExternalServiceError(f"Could not list the files of '{repo_id}' on Hugging Face: {error}", code="hub_unreachable") from error


@router.get("/{id}", response_model=LLMModelOut)
def get_llm_model(id: int):
    return LLMModel.get(id)


@router.patch("/{id}", response_model=LLMModelOut)
def update_llm_model(id: int, payload: LLMModelUpdate):
    return LLMModel.update(id, payload.model_dump(exclude_unset=True))


@router.delete("/{id}", status_code=204)
def delete_llm_model(id: int, delete_files: bool = False):
    LLMModel.delete(id, delete_files)
    return Response(status_code=204)
