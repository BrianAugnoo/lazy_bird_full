"""Skills: instructions an agent loads only when it needs them.

A skill is a folder ``skill/{extension_name}/{name}/`` holding a ``SKILL.md`` file and
optional resources (references, examples, scripts)::

    ---
    name: pdf-reports          # must equal the folder name
    description: How to write PDF reports. Use when the user asks for a report.
    ---
    Step-by-step instructions...

An agent's system prompt lists the name and description of its skills; the body is
loaded on demand with the ``load_skill`` tool, and resource files with
``read_skill_file`` (both in ``tools/default/skills.py``). Ids are
``"{extension}/{name}"``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import frontmatter

from lazy_bird.agents.files import CUSTOM, check_name, ensure_layout, extensions, require_custom, split_id, write_text
from lazy_bird.errors import ConflictError, InvalidInputError, NotFoundError
from lazy_bird.extension.discovery import LoadFailure, record_failures

ROOT = Path(__file__).resolve().parent
SKILL_FILE = "SKILL.md"
MAX_RESOURCE_BYTES = 200_000


@dataclass(frozen=True)
class Skill:
    id: str
    extension: str
    name: str
    description: str
    folder: Path
    files: list[str] = field(default_factory=list)

    @property
    def editable(self) -> bool:
        return self.extension == CUSTOM

    def content(self) -> str:
        return frontmatter.load(self.folder / SKILL_FILE).content


def ensure_folders() -> None:
    ensure_layout(ROOT)


def _load(folder: Path) -> Skill:
    document = frontmatter.load(folder / SKILL_FILE)
    name, description = document.metadata.get("name"), document.metadata.get("description")
    if name != folder.name:
        raise ValueError(f"frontmatter name '{name}' must equal the folder name '{folder.name}'")
    if not isinstance(description, str) or not description.strip():
        raise ValueError("frontmatter 'description' is required")
    resources = sorted(
        path.relative_to(folder).as_posix()
        for path in folder.rglob("*")
        if path.is_file() and path.name != SKILL_FILE and not any(part.startswith(".") for part in path.relative_to(folder).parts)
    )
    return Skill(f"{folder.parent.name}/{folder.name}", folder.parent.name, folder.name, description.strip(), folder, resources)


def skills() -> list[Skill]:
    """Every valid skill; invalid ones are reported as extension load failures."""
    found, failures = [], []
    for extension in extensions(ROOT):
        for folder in sorted(path for path in extension.iterdir() if (path / SKILL_FILE).is_file()):
            try:
                found.append(_load(folder))
            except Exception as error:
                failures.append(LoadFailure("skill", f"{extension.name}/{folder.name}", str(error)))
    record_failures("skill", failures)
    return found


def get(skill_id: str) -> Skill:
    extension, name = split_id(skill_id, "Skill")
    folder = ROOT / extension / name
    if not (folder / SKILL_FILE).is_file():
        raise NotFoundError("Skill", skill_id)
    try:
        return _load(folder)
    except ValueError as error:
        raise InvalidInputError(f"Skill '{skill_id}' is invalid: {error}", code="invalid_skill") from error


def exists(skill_id: str) -> bool:
    try:
        get(skill_id)
    except (NotFoundError, InvalidInputError):
        return False
    return True


def find(reference: str) -> Skill:
    """A skill by id, or by name when only one extension has it."""
    if "/" in reference:
        return get(reference)
    matches = [skill for skill in skills() if skill.name == reference]
    if len(matches) != 1:
        hint = ", ".join(skill.id for skill in matches) or "none"
        raise NotFoundError("Skill", f"{reference} (matches: {hint})")
    return matches[0]


def _document(name: str, description: str, body: str) -> str:
    post = frontmatter.Post(body.strip() + "\n", name=name, description=description.strip())
    return frontmatter.dumps(post) + "\n"


def create(name: str, description: str, body: str) -> Skill:
    folder = ROOT / CUSTOM / check_name(name)
    if folder.exists():
        raise ConflictError(f"The skill '{CUSTOM}/{name}' already exists.", code="skill_exists")
    write_text(folder / SKILL_FILE, _document(name, description, body))
    return get(f"{CUSTOM}/{name}")


def update(skill_id: str, description: str, body: str) -> Skill:
    skill = get(skill_id)
    require_custom(skill.extension, "Skills")
    write_text(skill.folder / SKILL_FILE, _document(skill.name, description, body))
    return get(skill_id)


def delete(skill_id: str) -> None:
    import shutil

    skill = get(skill_id)
    require_custom(skill.extension, "Skills")
    shutil.rmtree(skill.folder)


def read_file(skill: Skill, relative: str) -> str:
    """Read a resource of a skill (never outside its folder)."""
    target = (skill.folder / relative).resolve()
    if not target.is_relative_to(skill.folder.resolve()) or not target.is_file():
        raise NotFoundError("Skill file", f"{skill.id}/{relative}")
    if target.stat().st_size > MAX_RESOURCE_BYTES:
        raise InvalidInputError(f"{relative} is larger than {MAX_RESOURCE_BYTES} bytes.", code="skill_file_too_large")
    return target.read_text(encoding="utf-8", errors="replace")


def listing(skill_ids: list[str]) -> str:
    """The section of a system prompt presenting an agent's skills."""
    if not skill_ids:
        return ""
    lines = [f"- {get(skill_id).id}: {get(skill_id).description}" for skill_id in skill_ids]
    return (
        "You have skills: instructions you load only when a task needs them. "
        "Call `load_skill` with a skill id to read it before using it.\n" + "\n".join(lines)
    )
