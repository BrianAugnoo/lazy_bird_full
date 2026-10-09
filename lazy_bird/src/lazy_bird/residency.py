"""Loaded models: who needs the model of a local engine, and when it is released.

A local engine (``local = True``, see ``crud.engine``) builds its model with
``load(settings, model)`` and frees it with ``unload(instance)``; its operations
receive the loaded instance as first argument. This module owns those instances:

- ``residency().use(resolved)`` is a lease. The first lease loads the model, the last
  one to leave unloads it, even when its work failed;
- leases on the same model share one instance (a model is identified by the engine
  and its ``load_key``); operations on a shared instance run one at a time;
- a caller that knows it will make many calls (a task embedding batch after batch)
  wraps them in one lease, so the model is loaded once instead of once per call.

No engine decides by itself, from inside a call, that its model is not needed anymore.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Hashable, Iterator

from loguru import logger

if TYPE_CHECKING:
    from lazy_bird.crud.engine import ResolvedEngine


class Loaded:
    """A model held in memory, shared by every lease that has the same key."""

    def __init__(self, key: Hashable, module: Any) -> None:
        self.key = key
        self.module = module
        self.instance: Any = None
        self.leases = 0
        self._loading = threading.Lock()  # the first lease loads, the others wait for it
        self._calls = threading.Lock()  # a model serves one call at a time

    def run(self, operation: str, *args: Any, **kwargs: Any) -> Any:
        with self._calls:
            return getattr(self.module, operation)(self.instance, *args, **kwargs)


def _key(resolved: ResolvedEngine) -> Hashable:
    """Engine + the settings that change what is loaded (``load_key``; all settings by default)."""
    load_key = getattr(resolved.module, "load_key", None)
    detail = load_key(resolved.settings, resolved.model) if load_key else resolved.settings.model_dump_json()
    return resolved.engine.name, getattr(resolved.model, "id", None), detail


class Residency:
    def __init__(self) -> None:
        # Every change of the leases happens under this lock, unloading included: while a
        # model is being freed nobody can load a second copy of it next to the first one.
        self._lock = threading.Lock()
        self._entries: dict[Hashable, Loaded] = {}

    @contextmanager
    def use(self, resolved: ResolvedEngine) -> Iterator[Loaded]:
        """Hold the model of a local engine for the duration of a ``with`` block."""
        entry = self._join(resolved)
        try:
            self._ensure_loaded(entry, resolved)
            yield entry
        finally:
            self._leave(entry)

    def _join(self, resolved: ResolvedEngine) -> Loaded:
        key = _key(resolved)
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                entry = self._entries[key] = Loaded(key, resolved.module)
            entry.leases += 1
            return entry

    @staticmethod
    def _ensure_loaded(entry: Loaded, resolved: ResolvedEngine) -> None:
        with entry._loading:
            if entry.instance is None:
                entry.instance = entry.module.load(resolved.settings, resolved.model)

    def _leave(self, entry: Loaded) -> None:
        with self._lock:
            entry.leases -= 1
            if entry.leases > 0:
                return
            del self._entries[entry.key]
            instance, entry.instance = entry.instance, None
            if instance is not None:
                try:
                    entry.module.unload(instance)
                except Exception:
                    logger.exception("Unloading the model of engine '{}' failed", entry.key[0])


_residency: Residency | None = None


def residency() -> Residency:
    """The process-wide residency of local engines."""
    global _residency
    if _residency is None:
        _residency = Residency()
    return _residency
