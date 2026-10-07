from fastapi import APIRouter

from lazy_bird.extension.discovery import load_failures
from lazy_bird.schemas.extensions import LoadFailureOut

router = APIRouter(prefix="/extensions", tags=["extensions"])


@router.get("/failures", response_model=list[LoadFailureOut])
def list_load_failures():
    """Extension modules that could not be loaded, with the reason."""
    return [LoadFailureOut(**failure.as_dict()) for failure in load_failures()]


@router.post("/reload", response_model=list[LoadFailureOut])
def reload_extensions():
    """Discover engines, tools, hooks, skills and tasks again (after adding files)."""
    from lazy_bird.main import initialize_extensions

    initialize_extensions()
    return list_load_failures()
