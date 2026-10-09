"""Model installation tasks: download from Hugging Face, import uploaded files."""

import shutil
from pathlib import Path

from lazy_bird.crud import llm_model as llm_model_crud
from lazy_bird.tasks import TaskContext, task
from lazy_bird.tools import hf_cache
from lazy_bird.tools.model_extraction import download_model


def _reporter(ctx: TaskContext, verb: str):
    def report(done: int, total: int) -> None:
        if total:
            ctx.report(done / total, f"{verb} {done / 1024**2:,.0f} / {total / 1024**2:,.0f} MiB")

    return report


@task("models.download", title="Download {hf_path}", resources={"cpu": 1}, isolated=True)
def download(ctx: TaskContext, hf_path: str, files: list[str] | None = None, revision: str | None = None) -> dict:
    """Download a Hugging Face model (optionally only some weight files) into the cache.

    Isolated: the download runs in threads of Hugging Face's that no checkpoint can stop, so a
    pause or cancellation ends the task's process. The cache keeps the files already
    downloaded, and a resumed download continues from them.
    """
    snapshot = ctx.run_blocking(download_model, hf_path, files=files, revision=revision, progress=_reporter(ctx, "Downloaded"))
    model = llm_model_crud.register(hf_path, snapshot, "huggingface")
    return {"model_id": model.id, "formats": model.formats}


@task("models.import", title="Import {name}", resources={"cpu": 1})
def import_model(ctx: TaskContext, path: str, name: str, staged: bool = False) -> dict:
    """Store a model folder or weight file in the cache as ``local/<name>``.

    ``staged`` files (uploaded into the staging folder) are moved, and the staging
    folder is removed once the model is registered.

    Not stoppable midway on purpose: files already moved out of the staging folder would be
    missing from a resumed import.
    """
    repo_id, snapshot = hf_cache.import_local(path, name, progress=_reporter(ctx, "Stored"), move=staged)
    model = llm_model_crud.register(repo_id, snapshot, "local", name=name)
    if staged:
        shutil.rmtree(Path(path), ignore_errors=True)
    return {"model_id": model.id, "formats": model.formats}
