"""Folders of file-based extensions: instructions, skills, agent and session presets.

Each root holds ``{extension_name}/`` folders. ``default/`` ships with lazy_bird and is
read-only through the API; ``custom/`` holds what the user creates. Items are
identified by ``"{extension}/{name}"``: neither part can contain ``/``, so the id is
unambiguous (unlike ``{extension}_{name}`` when names contain ``_``).
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

from lazy_bird.errors import ForbiddenError, InvalidInputError, NotFoundError

DEFAULT = "default"
CUSTOM = "custom"
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


def check_name(name: str) -> str:
    if not NAME_PATTERN.match(name or "") or name.endswith("."):
        raise InvalidInputError(
            "Names use letters, digits, '-', '_' and '.', start with a letter or digit, and have at most 64 characters.",
            code="invalid_name",
            details={"fields": {"name": "Invalid name"}},
        )
    return name


def split_id(item_id: str, kind: str) -> tuple[str, str]:
    parts = item_id.split("/")
    if len(parts) != 2 or not all(parts):
        raise NotFoundError(kind, item_id)
    return parts[0], parts[1]


def ensure_layout(root: Path) -> None:
    """Create the ``default/`` and ``custom/`` folders of an extension root."""
    for name in (DEFAULT, CUSTOM):
        (root / name).mkdir(parents=True, exist_ok=True)


def extensions(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return sorted(path for path in root.iterdir() if path.is_dir() and not path.name.startswith((".", "_")))


def require_custom(extension: str, kind: str) -> None:
    if extension != CUSTOM:
        raise ForbiddenError(
            f"{kind} of the '{extension}' extension are read-only; create or copy them in 'custom'.",
            code="read_only_extension",
        )


def write_text(path: Path, text: str) -> None:
    """Write a file atomically (a crash never leaves it half written)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(text)
        os.replace(temporary, path)
    except BaseException:
        Path(temporary).unlink(missing_ok=True)
        raise
