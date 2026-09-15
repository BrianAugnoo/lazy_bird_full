from __future__ import annotations

import os
from pathlib import Path, PurePosixPath


BASE_DIR = Path(__file__).resolve().parent
DOCUMENTS_DIR = Path(
    os.getenv("SANDBOX_DOCUMENTS_DIR", str(BASE_DIR / "documents"))
).expanduser().resolve()
DOCUMENTS_DIR.mkdir(parents=True, exist_ok=True)


class InvalidDocumentPath(ValueError):
    pass


def normalize_document_name(name: str, subfolder: str | None = None) -> str:
    """Return a safe, POSIX-style path relative to the documents directory."""

    raw_name = (name or "").strip().replace("\\", "/")
    raw_subfolder = (subfolder or "").strip().replace("\\", "/")
    if raw_name.startswith("documents/"):
        raw_name = raw_name.removeprefix("documents/")
    if raw_subfolder.startswith("documents/"):
        raw_subfolder = raw_subfolder.removeprefix("documents/")

    combined = "/".join(part for part in (raw_subfolder, raw_name) if part)
    path = PurePosixPath(combined)
    parts = path.parts
    if not parts or path.name in {"", ".", ".."}:
        raise InvalidDocumentPath("Document name must include a file name")
    if any(part in {"", ".", ".."} for part in parts):
        raise InvalidDocumentPath("Document path must stay inside documents/")
    if any("\x00" in part for part in parts):
        raise InvalidDocumentPath("Document path contains an invalid character")
    if path.is_absolute() or ":" in parts[0]:
        raise InvalidDocumentPath("Absolute document paths are not allowed")
    return "/".join(parts)


def document_path(name: str) -> Path:
    normalized = normalize_document_name(name)
    candidate = (DOCUMENTS_DIR / Path(*normalized.split("/"))).resolve()
    try:
        candidate.relative_to(DOCUMENTS_DIR)
    except ValueError as exc:
        raise InvalidDocumentPath("Document path must stay inside documents/") from exc
    return candidate


def read_document(name: str) -> str:
    path = document_path(name)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_document(name: str, content: str) -> Path:
    path = document_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)
    return path


def move_document(old_name: str, new_name: str) -> None:
    old_path = document_path(old_name)
    new_path = document_path(new_name)
    new_path.parent.mkdir(parents=True, exist_ok=True)
    if old_path.exists() and old_path != new_path:
        old_path.replace(new_path)


def delete_document_file(name: str) -> None:
    path = document_path(name)
    if path.exists():
        path.unlink()
        parent = path.parent
        while parent != DOCUMENTS_DIR and parent.exists():
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent

