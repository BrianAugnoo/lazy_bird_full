"""Conventions shared by every dynamic discovery point.

Two layouts exist:

- flat packages (``embedding/engines/``, ``inference/engines/``): every module of
  the package whose name does not start with ``_`` is an extension module;
- extension folders (``agents/tools/``, ``agents/hook/``...): the package contains
  one directory per extension (``{extension_name}/``), each holding modules.
  ``default/`` ships with lazy_bird and ``custom/`` belongs to the user.

A module that breaks its contract never stops the application: discovery records
a ``LoadFailure`` (exposed by ``GET /extensions/failures``) and skips the module.
"""

from __future__ import annotations

import importlib
import pkgutil
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType
from typing import Iterable, Iterator

from loguru import logger

from lazy_bird.extension import ExtensionContractError


@dataclass(frozen=True)
class LoadFailure:
    kind: str
    source: str
    error: str

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


_failures: dict[str, list[LoadFailure]] = {}


def record_failures(kind: str, failures: Iterable[LoadFailure]) -> None:
    """Replace the recorded failures of one discovery point and log them."""
    _failures[kind] = list(failures)
    for failure in _failures[kind]:
        logger.warning("Extension failed to load: kind={} source={} error={}", failure.kind, failure.source, failure.error)


def load_failures() -> list[LoadFailure]:
    return [failure for failures in _failures.values() for failure in failures]


def is_public(name: str) -> bool:
    return not name.startswith(("_", "."))


def iter_package_modules(package_name: str) -> Iterator[str]:
    """Yield the import path of every public module of a flat package."""
    package = importlib.import_module(package_name)
    for info in sorted(pkgutil.iter_modules(package.__path__), key=lambda item: item.name):
        if is_public(info.name):
            yield f"{package_name}.{info.name}"


def package_directory(package_name: str) -> Path:
    package = importlib.import_module(package_name)
    return Path(next(iter(package.__path__)))


def iter_extension_directories(root: Path) -> Iterator[Path]:
    """Yield every ``{extension_name}/`` directory of an extension root, sorted by name."""
    if not root.is_dir():
        return
    for entry in sorted(root.iterdir(), key=lambda path: path.name):
        if entry.is_dir() and is_public(entry.name) and entry.name != "__pycache__":
            yield entry


def iter_extension_modules(package_name: str) -> Iterator[tuple[str, str, str]]:
    """Yield ``(extension_name, module_name, import_path)`` for ``{extension_name}/*.py``."""
    for directory in iter_extension_directories(package_directory(package_name)):
        for info in sorted(pkgutil.iter_modules([str(directory)]), key=lambda item: item.name):
            if is_public(info.name):
                yield directory.name, info.name, f"{package_name}.{directory.name}.{info.name}"


def import_module(import_path: str) -> ModuleType:
    """Import (or re-import) an extension module."""
    return importlib.import_module(import_path)


def require_attributes(module: ModuleType, names: Iterable[str]) -> None:
    missing = [name for name in names if not hasattr(module, name)]
    if missing:
        raise ExtensionContractError(f"missing required attribute(s): {', '.join(missing)}")
