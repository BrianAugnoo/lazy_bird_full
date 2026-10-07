from fastapi import APIRouter, Query, Response

import lazy_bird.crud.llm_model as LLMModel
from lazy_bird.errors import ExternalServiceError
from lazy_bird.schemas.llm_model import HubFileOut, LLMModelImport, LLMModelIn, LLMModelOut, LLMModelUpdate
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


@router.post("/import", response_model=TaskOut, status_code=202)
def import_llm_model(payload: LLMModelImport):
    """Queue the copy of a model folder or weight file from the server's disk into the cache."""
    from lazy_bird.tasks.default.models import import_model

    LLMModel.ensure_absent(f"{hf_cache.LOCAL_NAMESPACE}/{hf_cache.slug(payload.name)}")
    return import_model.submit(path=payload.path, name=payload.name, dedupe_key=f"models.import:{hf_cache.slug(payload.name)}")


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
