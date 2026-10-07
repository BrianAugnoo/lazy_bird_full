"""Models stored in the Hugging Face cache, mirrored in the ``llmmodel`` table.

The cache is the source of truth for the files: ``register`` records (or refreshes)
a snapshot, ``sync_cache`` re-registers everything found in the cache at startup,
which also repairs rows whose ``local_path`` points to a snapshot that no longer
exists.
"""

from pathlib import Path
from typing import Any

from sqlmodel import select

from lazy_bird.database import db
from lazy_bird.errors import ConflictError, InvalidInputError, NotFoundError
from lazy_bird.models.llm_model import LLMModel as LLMModelORM
from lazy_bird.schemas.llm_model import LLMModelOut
from lazy_bird.tools import hf_cache
from lazy_bird.tools.model_extraction import default_file, extract, weights_size_mb


def _out(row: LLMModelORM) -> LLMModelOut:
    available = Path(row.local_path).exists()
    size = weights_size_mb(row.local_path, row.selected_format, row.selected_file) if available else None
    return LLMModelOut.model_validate(row).model_copy(
        update={"available": available, "size_mb": round(size, 1) if size is not None else None}
    )


def _row(session, model_id: int) -> LLMModelORM:
    row = session.get(LLMModelORM, model_id)
    if row is None:
        raise NotFoundError("Model", model_id)
    return row


def register(hf_path: str, local_path: str | Path, source: str = "huggingface", name: str | None = None) -> LLMModelOut:
    """Create or refresh the row of a snapshot, keeping the user's choices when still valid."""
    metadata = extract(local_path)
    snapshot = Path(local_path)
    with db() as session:
        row = session.exec(select(LLMModelORM).where(LLMModelORM.hf_path == hf_path)).first()
        if row is None:
            default_name = hf_path.split("/", 1)[1] if source == "local" else hf_path
            row = LLMModelORM(name=name or default_name, hf_path=hf_path, local_path=str(snapshot))
        row.local_path = str(snapshot)
        row.revision = snapshot.name if snapshot.parent.name == "snapshots" else None
        row.source = source
        row.formats = metadata["formats"]
        row.files = metadata["files"]
        row.dimension = metadata["dimension"] or row.dimension
        row.max_context_length = metadata["max_context_length"] or row.max_context_length
        if row.selected_format not in row.formats:
            row.selected_format = row.formats[0]
        if row.selected_file not in row.files.get(row.selected_format, []):
            row.selected_file = default_file(row.selected_format, row.files)
        session.add(row)
        session.commit()
        session.refresh(row)
        return _out(row)


def find(id: int) -> LLMModelOut | None:
    with db() as session:
        row = session.get(LLMModelORM, id)
        return _out(row) if row is not None else None


def get(id: int) -> LLMModelOut:
    with db() as session:
        return _out(_row(session, id))


def get_all(formats: list[str] | None = None) -> list[LLMModelOut]:
    """Every model, or those available in one of ``formats``."""
    wanted = {value.lower() for value in formats or []}
    with db() as session:
        rows = session.exec(select(LLMModelORM).order_by(LLMModelORM.id)).all()
    return [_out(row) for row in rows if not wanted or wanted & {value.lower() for value in row.formats}]


def update(id: int, changes: dict[str, Any]) -> LLMModelOut:
    with db() as session:
        row = _row(session, id)
        if changes.get("name") is not None:
            row.name = changes["name"]
        if changes.get("selected_format") is not None:
            if changes["selected_format"] not in row.formats:
                raise InvalidInputError(
                    f"Format '{changes['selected_format']}' is not available for this model (available: {', '.join(row.formats)}).",
                    code="unknown_format",
                    details={"fields": {"selected_format": "Not available for this model"}},
                )
            row.selected_format = changes["selected_format"]
            if row.selected_file not in row.files.get(row.selected_format, []):
                row.selected_file = default_file(row.selected_format, row.files)
        if "selected_file" in changes and changes["selected_file"] is not None:
            if changes["selected_file"] not in row.files.get(row.selected_format, []):
                raise InvalidInputError(
                    "This file is not a weight file of the selected format.",
                    code="unknown_weight_file",
                    details={"fields": {"selected_file": "Not a file of the selected format"}},
                )
            row.selected_file = changes["selected_file"]
        if "selected_context" in changes:
            row.selected_context = changes["selected_context"]
        session.add(row)
        session.commit()
        session.refresh(row)
        return _out(row)


def delete(id: int, delete_files: bool = False) -> None:
    """Forget a model; with ``delete_files`` its files are removed from the cache too.

    Presets using it become invalid; its vector table (if any) is kept.
    """
    with db() as session:
        row = _row(session, id)
        hf_path = row.hf_path
        session.delete(row)
        session.commit()
    if delete_files:
        hf_cache.delete_repo(hf_path)


def ensure_absent(hf_path: str) -> None:
    with db() as session:
        if session.exec(select(LLMModelORM).where(LLMModelORM.hf_path == hf_path)).first() is not None:
            raise ConflictError(f"The model '{hf_path}' is already installed.", code="model_exists", details={"hf_path": hf_path})


def sync_cache(cache: Path | None = None) -> dict[str, list[str]]:
    """Register every model of the cache; report what was added, refreshed or skipped."""
    with db() as session:
        known = {row.hf_path for row in session.exec(select(LLMModelORM)).all()}
    report: dict[str, list[str]] = {"added": [], "refreshed": [], "skipped": []}
    for repo_id, snapshot in hf_cache.cached_models(cache):
        try:
            register(repo_id, snapshot, "local" if repo_id.startswith(f"{hf_cache.LOCAL_NAMESPACE}/") else "huggingface")
        except (OSError, ValueError) as error:
            report["skipped"].append(f"{repo_id}: {error}")
            continue
        report["refreshed" if repo_id in known else "added"].append(repo_id)
    return report


def delete_all() -> None:
    with db() as session:
        for row in session.exec(select(LLMModelORM)).all():
            session.delete(row)
        session.commit()
