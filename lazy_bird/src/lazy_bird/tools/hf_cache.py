"""The Hugging Face cache (``~/.cache/huggingface/hub``) as the home of every model.

Downloaded models already live there; imported local models are copied there with
the same layout, under the repository ``local/<name>``::

    models--local--<name>/
        blobs/<sha256>                 file contents
        snapshots/<revision>/<path>    links to the blobs (copies where links are unavailable)
        refs/main                      the current revision

So the cache alone is enough to rebuild the model list after a restart.

Models uploaded from the browser are first written, file by file, into a staging
folder next to the cache (``.lazy_bird_uploads/<name>/``, same disk), then imported
with ``move=True``: the files become blobs without being copied twice.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path
from typing import Callable, Iterator

from huggingface_hub.constants import HF_HUB_CACHE

LOCAL_NAMESPACE = "local"
BLOCK = 4 * 1024 * 1024
STAGING = ".lazy_bird_uploads"


def cache_root() -> Path:
    return Path(HF_HUB_CACHE).expanduser()


def repo_folder(repo_id: str, cache: Path | None = None) -> Path:
    return (cache or cache_root()) / ("models--" + repo_id.replace("/", "--"))


def repo_id_of(folder: Path) -> str | None:
    prefix = "models--"
    if not folder.name.startswith(prefix):
        return None
    parts = folder.name[len(prefix):].split("--")
    return "/".join(parts) if len(parts) >= 2 else None


def current_snapshot(folder: Path) -> Path | None:
    """The snapshot ``refs/main`` points to, else the most recently modified one."""
    snapshots = folder / "snapshots"
    if not snapshots.is_dir():
        return None
    ref = folder / "refs" / "main"
    if ref.is_file():
        candidate = snapshots / ref.read_text(encoding="utf-8").strip()
        if candidate.is_dir():
            return candidate.resolve()
    folders = [path for path in snapshots.iterdir() if path.is_dir()]
    return max(folders, key=lambda path: path.stat().st_mtime).resolve() if folders else None


def cached_models(cache: Path | None = None) -> Iterator[tuple[str, Path]]:
    """Yield ``(repo_id, snapshot path)`` for every model in the cache."""
    root = cache or cache_root()
    if not root.is_dir():
        return
    for folder in sorted(root.iterdir()):
        repo_id = repo_id_of(folder) if folder.is_dir() else None
        snapshot = current_snapshot(folder) if repo_id else None
        if repo_id and snapshot is not None:
            yield repo_id, snapshot


def slug(name: str) -> str:
    """A repository-safe version of a model name."""
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", name.strip()).strip("-.")
    if not value:
        raise ValueError("The model name must contain letters or digits")
    return value[:96]


def staging_folder(name: str, cache: Path | None = None) -> Path:
    """Where the files of a model being uploaded are gathered before the import."""
    return (cache or cache_root()) / STAGING / slug(name)


def staged_path(name: str, relative: str, cache: Path | None = None) -> Path:
    """Destination of one uploaded file; refuses absolute paths, ``..`` and hidden parts."""
    parts = [part for part in relative.replace("\\", "/").split("/") if part]
    if not parts or relative.startswith("/") or any(part in (".", "..") or part.startswith(".") for part in parts):
        raise ValueError(f"Invalid file path '{relative}'")
    return staging_folder(name, cache).joinpath(*parts)


def _source_files(source: Path) -> list[tuple[Path, str]]:
    if source.is_file():
        return [(source, source.name)]
    files = []
    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_file() and not any(part.startswith(".") for part in relative.parts):
            files.append((path, relative.as_posix()))
    return files


def _hash_file(path: Path, on_bytes: Callable[[int], None]) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(BLOCK), b""):
            digest.update(block)
            on_bytes(len(block))
    return digest.hexdigest()


def _link(target: Path, blob: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() or target.is_symlink():
        target.unlink()
    try:
        target.symlink_to(os.path.relpath(blob, target.parent))
    except OSError:  # no symlink support (Windows without developer mode): copy, like huggingface_hub
        shutil.copy2(blob, target)


def import_local(
    source: str | Path,
    name: str,
    *,
    cache: Path | None = None,
    progress: Callable[[int, int], None] = lambda done, total: None,
    move: bool = False,
) -> tuple[str, Path]:
    """Store a local model folder (or single weight file) in the cache.

    Returns ``(repo_id, snapshot path)``. Importing identical content again reuses
    the same blobs and revision. ``move`` moves the files instead of copying them
    (staged uploads, on the same disk as the cache).
    """
    source_path = Path(source).expanduser()
    if not source_path.exists():
        raise FileNotFoundError(f"{source_path} does not exist")
    files = _source_files(source_path)
    if not files:
        raise ValueError(f"{source_path} contains no files")
    repo_id = f"{LOCAL_NAMESPACE}/{slug(name)}"
    folder = repo_folder(repo_id, cache)
    total = sum(path.stat().st_size for path, _ in files) * (1 if move else 2)  # hashing, then copying
    done = 0

    def advance(count: int) -> None:
        nonlocal done
        done += count
        progress(done, total)

    blobs = folder / "blobs"
    blobs.mkdir(parents=True, exist_ok=True)
    entries = []
    for path, relative in files:
        digest = _hash_file(path, advance)
        blob = blobs / digest
        if move:
            if blob.exists():
                path.unlink()
            else:
                shutil.move(path, blob)
        elif not blob.exists():
            partial = blob.with_suffix(".incomplete")
            with path.open("rb") as reader, partial.open("wb") as writer:
                for block in iter(lambda: reader.read(BLOCK), b""):
                    writer.write(block)
                    advance(len(block))
            partial.replace(blob)
        else:
            advance(path.stat().st_size)
        entries.append((relative, digest))
    revision = hashlib.sha1("".join(f"{relative}:{digest}\n" for relative, digest in sorted(entries)).encode()).hexdigest()
    snapshot = folder / "snapshots" / revision
    for relative, digest in entries:
        _link(snapshot / relative, blobs / digest)
    (folder / "refs").mkdir(exist_ok=True)
    (folder / "refs" / "main").write_text(revision, encoding="utf-8")
    return repo_id, snapshot.resolve()


def delete_repo(repo_id: str, cache: Path | None = None) -> bool:
    """Remove a model and its files from the cache; return whether something was removed."""
    folder = repo_folder(repo_id, cache)
    if not folder.is_dir():
        return False
    shutil.rmtree(folder)
    return True
