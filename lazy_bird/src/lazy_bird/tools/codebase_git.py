from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import subprocess
from typing import Callable, Sequence


WATCHED_PATHS = (
    "src/lazy_bird",
    "tests",
    "pyproject.toml",
    "uv.lock",
    "README.md",
    "AGENT.md",
)


class GitInspectionError(RuntimeError):
    """Raised when Git metadata cannot be inspected."""


GitRunner = Callable[[Sequence[str]], str]


@dataclass(frozen=True)
class DocumentationMetadata:
    documented_commit: str | None
    updated_at: str | None


@dataclass(frozen=True)
class GitDocumentationStatus:
    current_commit: str | None
    documented_commit: str | None
    updated_at: str | None
    is_current: bool
    is_stale: bool
    changed_commit_count: int | None
    changed_paths: tuple[str, ...]
    watched_paths: tuple[str, ...]
    error: str | None = None


def _run_git(arguments: Sequence[str], repository_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", *arguments],
            cwd=repository_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise GitInspectionError(detail.strip()) from exc
    return result.stdout.strip()


class GitDocumentationInspector:
    def __init__(
        self,
        repository_root: Path,
        runner: GitRunner | None = None,
        watched_paths: Sequence[str] = WATCHED_PATHS,
    ) -> None:
        self.repository_root = repository_root
        self.runner = runner or (lambda arguments: _run_git(arguments, repository_root))
        self.watched_paths = tuple(watched_paths)

    def current_commit(self) -> str:
        return self.runner(["rev-parse", "HEAD"])

    def status(self, metadata: DocumentationMetadata) -> GitDocumentationStatus:
        try:
            current = self.current_commit()
            if not metadata.documented_commit:
                return GitDocumentationStatus(
                    current_commit=current,
                    documented_commit=None,
                    updated_at=metadata.updated_at,
                    is_current=False,
                    is_stale=False,
                    changed_commit_count=None,
                    changed_paths=(),
                    watched_paths=self.watched_paths,
                )

            changed_paths = self._relevant_paths(metadata.documented_commit, current)
            count = 0
            if current != metadata.documented_commit:
                count = int(self.runner(["rev-list", "--count", f"{metadata.documented_commit}..{current}"]))
            stale = bool(changed_paths)
            return GitDocumentationStatus(
                current_commit=current,
                documented_commit=metadata.documented_commit,
                updated_at=metadata.updated_at,
                is_current=not stale,
                is_stale=stale,
                changed_commit_count=count,
                changed_paths=changed_paths,
                watched_paths=self.watched_paths,
            )
        except GitInspectionError as exc:
            return GitDocumentationStatus(
                current_commit=None,
                documented_commit=metadata.documented_commit,
                updated_at=metadata.updated_at,
                is_current=False,
                is_stale=False,
                changed_commit_count=None,
                changed_paths=(),
                watched_paths=self.watched_paths,
                error=str(exc),
            )

    def changes(self, documented_commit: str, current_commit: str | None = None) -> dict[str, object]:
        current = current_commit or self.current_commit()
        paths = self._relevant_paths(documented_commit, current)
        if not paths:
            return {"commits": [], "diff": "", "paths": []}
        path_arguments = ["--", *paths]
        return {
            "commits": self.runner(["log", "--format=%h %s", f"{documented_commit}..{current}", *path_arguments]).splitlines(),
            "diff": self.runner(["diff", "--no-ext-diff", f"{documented_commit}..{current}", *path_arguments]),
            "paths": list(paths),
        }

    def _relevant_paths(self, documented_commit: str, current_commit: str) -> tuple[str, ...]:
        if documented_commit == current_commit:
            return ()
        raw_paths = self.runner(["diff", "--name-only", f"{documented_commit}..{current_commit}"])
        return tuple(path for path in raw_paths.splitlines() if self._is_watched(path))

    def _is_watched(self, path: str) -> bool:
        normalized = path.replace("\\", "/")
        return any(normalized == watched or normalized.startswith(f"{watched}/") for watched in self.watched_paths)


def documentation_metadata(path: Path) -> DocumentationMetadata:
    try:
        import json

        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return DocumentationMetadata(documented_commit=None, updated_at=None)
    return DocumentationMetadata(
        documented_commit=payload.get("documented_commit"),
        updated_at=payload.get("updated_at"),
    )


def format_updated_at(value: str | None) -> str:
    if not value:
        return "Unknown"
    try:
        return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M %Z")
    except ValueError:
        return value