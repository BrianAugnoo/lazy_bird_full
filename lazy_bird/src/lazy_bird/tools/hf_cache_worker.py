import logging
from pathlib import Path

from huggingface_hub.constants import HF_HUB_CACHE
from sqlalchemy.exc import SQLAlchemyError

from lazy_bird.crud import llm_model as llm_model_crud


logger = logging.getLogger(__name__)


def _repository_id(cache_directory: Path) -> str | None:
    prefix = "models--"
    if not cache_directory.name.startswith(prefix):
        return None

    parts = cache_directory.name[len(prefix):].split("--")
    return "/".join(parts) if len(parts) >= 2 else None


def find_cached_model_paths(cache_path: str | Path = HF_HUB_CACHE):
    cache_directory = Path(cache_path).expanduser()
    if not cache_directory.is_dir():
        return []

    cached_models = []
    for repository_directory in cache_directory.iterdir():
        if repository_directory.name == ".locks" or not repository_directory.is_dir():
            continue

        hf_path = _repository_id(repository_directory)
        snapshots_directory = repository_directory / "snapshots"
        if hf_path is None or not snapshots_directory.is_dir():
            continue

        snapshots = [path for path in snapshots_directory.iterdir() if path.is_dir()]
        if len(snapshots) == 1:
            cached_models.append((hf_path, snapshots[0].resolve()))

    return cached_models


def sync_cached_models(cache_path: str | Path = HF_HUB_CACHE) -> int:
    known_paths = {
        Path(model.local_path).expanduser().resolve()
        for model in llm_model_crud.get_all()
    }
    created_count = 0

    for hf_path, local_path in find_cached_model_paths(cache_path):
        if local_path in known_paths:
            continue

        try:
            llm_model_crud.create_from_local_path(hf_path, str(local_path))
        except (FileNotFoundError, KeyError, OSError, ValueError, SQLAlchemyError) as exc:
            logger.warning("Could not import cached model at %s: %s", local_path, exc)
            continue

        known_paths.add(local_path)
        created_count += 1

    return created_count
