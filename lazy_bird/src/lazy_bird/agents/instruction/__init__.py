"""Instructions: system prompts (``full/``) and fragments appended to them (``sub/``).

Files: ``instruction/{full|sub}/{extension_name}/{name}.md``, identified by
``"{extension}/{name}"`` within their kind. An agent's system prompt is its full
instructions, then its sub instructions, then its own free text, separated by
blank lines.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from lazy_bird.agents.files import CUSTOM, check_name, ensure_layout, extensions, require_custom, split_id, write_text
from lazy_bird.errors import ConflictError, InvalidInputError, NotFoundError

ROOT = Path(__file__).resolve().parent
KINDS = ("full", "sub")


@dataclass(frozen=True)
class Instruction:
    id: str
    kind: str
    extension: str
    name: str
    path: Path

    @property
    def editable(self) -> bool:
        return self.extension == CUSTOM

    def content(self) -> str:
        return self.path.read_text(encoding="utf-8")


def _kind_root(kind: str) -> Path:
    if kind not in KINDS:
        raise InvalidInputError(f"Instruction kind must be one of {', '.join(KINDS)}.", code="invalid_instruction_kind")
    return ROOT / kind


def ensure_folders() -> None:
    for kind in KINDS:
        ensure_layout(ROOT / kind)


def instructions(kind: str) -> list[Instruction]:
    found = []
    for folder in extensions(_kind_root(kind)):
        for path in sorted(folder.glob("*.md")):
            found.append(Instruction(f"{folder.name}/{path.stem}", kind, folder.name, path.stem, path))
    return found


def get(kind: str, instruction_id: str) -> Instruction:
    extension, name = split_id(instruction_id, "Instruction")
    path = _kind_root(kind) / extension / f"{name}.md"
    if not path.is_file():
        raise NotFoundError("Instruction", f"{kind}/{instruction_id}")
    return Instruction(instruction_id, kind, extension, name, path)


def exists(kind: str, instruction_id: str) -> bool:
    try:
        get(kind, instruction_id)
    except NotFoundError:
        return False
    return True


def create(kind: str, name: str, content: str) -> Instruction:
    path = _kind_root(kind) / CUSTOM / f"{check_name(name)}.md"
    if path.exists():
        raise ConflictError(f"The instruction '{CUSTOM}/{name}' already exists.", code="instruction_exists")
    write_text(path, content)
    return get(kind, f"{CUSTOM}/{name}")


def update(kind: str, instruction_id: str, content: str) -> Instruction:
    instruction = get(kind, instruction_id)
    require_custom(instruction.extension, "Instructions")
    write_text(instruction.path, content)
    return instruction


def delete(kind: str, instruction_id: str) -> None:
    instruction = get(kind, instruction_id)
    require_custom(instruction.extension, "Instructions")
    instruction.path.unlink()


def compose(fulls: list[str], subs: list[str], extra: str | None = None) -> str:
    """Join full instructions, sub instructions and free text into one system prompt."""
    parts = [get("full", item).content().strip() for item in fulls]
    parts += [get("sub", item).content().strip() for item in subs]
    if extra and extra.strip():
        parts.append(extra.strip())
    return "\n\n".join(part for part in parts if part)
