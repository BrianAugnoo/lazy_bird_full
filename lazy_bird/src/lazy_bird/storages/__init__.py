from pathlib import Path
import shutil
from fastapi import UploadFile

storage_dir = Path(__file__).resolve().parent


def _safe_path(path: Path) -> Path:
    root = storage_dir.resolve()
    resolved = path.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValueError("Invalid storage path") from error
    return resolved


def _safe_directory(directory: str) -> Path:
    relative_dir = Path(directory)
    if relative_dir.is_absolute() or ".." in relative_dir.parts:
        raise ValueError("Invalid destination directory")
    return _safe_path(storage_dir / relative_dir)


def create_directory(path: str) -> str:
    target_dir = _safe_directory(path)
    if target_dir.exists() and not target_dir.is_dir():
        raise ValueError("A file with that path already exists")
    target_dir.mkdir(parents=True, exist_ok=True)
    return str(target_dir)


def delete_directory(path: str) -> str:
    target_dir = _safe_directory(path)
    if target_dir == storage_dir.resolve():
        raise ValueError("The storage root cannot be deleted")
    if not target_dir.exists():
        raise FileNotFoundError("Directory not found")
    if not target_dir.is_dir():
        raise ValueError("The path is not a directory")
    shutil.rmtree(target_dir)
    return str(target_dir)


def move_directory(source: str, destination: str) -> tuple[str, str]:
    source_dir = _safe_directory(source)
    destination_dir = _safe_directory(destination)
    if source_dir == storage_dir.resolve():
        raise ValueError("The storage root cannot be moved")
    if not source_dir.exists():
        raise FileNotFoundError("Directory not found")
    if not source_dir.is_dir():
        raise ValueError("The source path is not a directory")
    if destination_dir.exists():
        raise ValueError("A file or directory with that path already exists")
    if source_dir in destination_dir.parents:
        raise ValueError("A directory cannot be moved inside itself")
    destination_dir.parent.mkdir(parents=True, exist_ok=True)
    source_dir.rename(destination_dir)
    return str(source_dir), str(destination_dir)


def store_file(dir: str, file: UploadFile) -> dict:
    target_dir = _safe_directory(dir)

    filename = Path(file.filename or "").name
    if not filename:
        raise ValueError("Invalid file name")

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    full_name = filename
    extension = Path(full_name).suffix.lower()
    file_name = Path(full_name).stem
    size = file.size

    try:
        with open(target_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise RuntimeError(f"Failed to store file {filename}: {e}")

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
            raise ValueError("Invalid file name")
        filename = f"{name}{current_path.suffix}"
    else:
        filename = current_path.name

    target_dir = _safe_directory(dir) if dir is not None else current_path.parent
    target_path = _safe_path(target_dir / filename)
    if target_path != current_path and target_path.exists():
        raise ValueError("A file with that name already exists")
    target_dir.mkdir(parents=True, exist_ok=True)
    current_path.rename(target_path)
    return str(target_path)
