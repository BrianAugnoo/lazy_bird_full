from datetime import datetime, timezone
from pathlib import Path
import hashlib
import shutil
from fastapi import UploadFile

from lazy_bird.errors import AppError, ConflictError, InvalidInputError, NotFoundError


class StorageError(AppError):
    status_code = 500
    code = "storage_failed"


def _invalid_path(message: str) -> InvalidInputError:
    return InvalidInputError(message, code="invalid_path")

storage_dir = Path(__file__).resolve().parent


def _safe_path(path: Path) -> Path:
    root = storage_dir.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise _invalid_path("The path is outside the storage directory.") from error
    return resolved


def _safe_directory(directory: str) -> Path:
    # Client paths may use Windows separators; normalize them on every platform.
    relative_dir = Path(directory.replace("\\", "/"))
    if relative_dir.is_absolute() or ".." in relative_dir.parts:
        raise _invalid_path("Directories are relative paths inside the storage, without '..'.")
    return _safe_path(storage_dir / relative_dir)


def create_directory(path: str) -> str:
    target_dir = _safe_directory(path)
    if target_dir.exists() and not target_dir.is_dir():
        raise ConflictError("A file with that path already exists.", code="path_exists")
    target_dir.mkdir(parents=True, exist_ok=True)
    return str(target_dir)


def delete_directory(path: str) -> str:
    target_dir = _safe_directory(path)
    if target_dir == storage_dir.resolve():
        raise _invalid_path("The storage root cannot be deleted.")
    if not target_dir.exists():
        raise NotFoundError("Directory", path)
    if not target_dir.is_dir():
        raise _invalid_path("The path is not a directory.")
    shutil.rmtree(target_dir)
    return str(target_dir)


def move_directory(source: str, destination: str) -> tuple[str, str]:
    source_dir = _safe_directory(source)
    destination_dir = _safe_directory(destination)
    if source_dir == storage_dir.resolve():
        raise _invalid_path("The storage root cannot be moved.")
    if not source_dir.exists():
        raise NotFoundError("Directory", source)
    if not source_dir.is_dir():
        raise _invalid_path("The source path is not a directory.")
    if destination_dir.exists():
        raise ConflictError("A file or directory with that path already exists.", code="path_exists")
    if source_dir in destination_dir.parents:
        raise _invalid_path("A directory cannot be moved inside itself.")
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    source_dir.rename(destination_dir)
    return str(source_dir), str(destination_dir)


def free_path(path: Path) -> Path:
    """``path``, or ``name (1).ext``, ``name (2).ext``... when it is taken."""
    candidate, index = path, 1
    while candidate.exists():
        candidate = path.with_name(f"{path.stem} ({index}){path.suffix}")
        index += 1
    return candidate


def store_file(dir: str, file: UploadFile) -> dict:
    """Write an upload into ``dir``; an existing name gets a numbered suffix (both files are kept)."""
    target_dir = _safe_directory(dir)

    filename = Path(file.filename or "").name
    if not filename:
        raise InvalidInputError("The file name is empty or invalid.", code="invalid_file_name")

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = free_path(target_dir / filename)
    extension = target_path.suffix.lower()
    file_name = target_path.stem
    size = file.size

    try:
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise StorageError(f"Failed to store file {filename}: {e}") from e

    return {
        "name": file_name,
        "path": str(target_path),
        "extension": extension,
        "size": size
    }


def read_file(path: str) -> bytes:
    return _safe_path(Path(path)).read_bytes()


def write_file(path: str, content: str) -> int:
    target_path = _safe_path(Path(path))
    target_path.write_text(content, encoding="utf-8")
    return target_path.stat().st_size


def rename_or_move_file(path: str, name: str | None = None, dir: str | None = None) -> str:
    current_path = _safe_path(Path(path))
    if name is not None:
        if not name or Path(name).name != name or name in {".", ".."}:
            raise InvalidInputError("The file name is empty or invalid.", code="invalid_file_name")
        filename = f"{name}{current_path.suffix}"
    else:
        filename = current_path.name

    target_dir = _safe_directory(dir) if dir is not None else current_path.parent
    target_path = _safe_path(target_dir / filename)
    if target_path != current_path and target_path.exists():
        raise ConflictError("A file with that name already exists.", code="path_exists")
    target_dir.mkdir(parents=True, exist_ok=True)
    current_path.rename(target_path)
    return str(target_path)


def fingerprint(path: str) -> tuple[int, datetime] | None:
    """``(size, modification time)`` of a stored file, or None when it is missing."""
    try:
        stat = _safe_path(Path(path)).stat()
    except (FileNotFoundError, InvalidInputError):
        return None
    return stat.st_size, datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)


def content_hash(path: str) -> str:
    """SHA-256 of a stored file, read in blocks."""
    digest = hashlib.sha256()
    with _safe_path(Path(path)).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def relative_path(path: str) -> str:
    """Path of a stored file relative to the storage directory (POSIX separators)."""
    try:
        return Path(path).resolve().relative_to(storage_dir.resolve()).as_posix()
    except ValueError:
        return Path(path).name


def directories() -> list[str]:
    """Every directory of the storage, relative to it, sorted (empty ones included)."""
    root = storage_dir.resolve()
    if not root.is_dir():
        return []
    return sorted(path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_dir() and not path.name.startswith("."))
