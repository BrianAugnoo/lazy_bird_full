"""Loaded models: who needs the model of a local engine, where it lives, and when it is released.

A local engine (``local = True``, see ``crud.engine``) builds its model with
``load(settings, model)`` and frees it with ``unload(instance)``; its operations
receive the loaded instance as first argument. This module owns those instances:

- ``residency().use(resolved)`` is a lease. The first lease loads the model; leases on
  the same model (same engine and ``load_key``) share one instance, and calls on a
  shared instance run one at a time;
- a caller that knows it will make many calls (a task embedding batch after batch)
  wraps them in one lease, so the model is loaded once instead of once per call;
- with ``smart-memory`` off the last lease to leave unloads the model and nothing is
  accounted (unsupervised);
- with ``smart-memory`` on every model holds the memory it takes in the shared resource
  pool (``engine:*`` holders) and an idle model stays loaded until that memory is needed:
  it is then evicted, least recently used first. A model that does not fit in GPU memory
  goes to the CPU when the ``fallback`` preference says so (engines tell where they can
  live with ``placements``); a model that cannot fit in the machine at all is refused
  with ``InsufficientResourcesError``.

No engine decides by itself, from inside a call, that its model is not needed anymore.
"""

from __future__ import annotations

import itertools
import threading
import time
from collections import Counter
from contextlib import contextmanager
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any, Callable, Hashable, Iterator

from loguru import logger

from lazy_bird import priority as priorities
from lazy_bird.errors import InsufficientResourcesError, UnavailableError
from lazy_bird.preferences import smart_memory

if TYPE_CHECKING:
    from lazy_bird.crud.engine import ResolvedEngine

Resources = dict[str, float]
Preempt = Callable[[Resources, int], bool]

WAIT_STEP_SECONDS = 0.25
WAIT_TIMEOUT_SECONDS = 600  # how long a caller that cannot go on without a model waits for memory

_lessee: ContextVar[str | None] = ContextVar("lessee", default=None)
_priority: ContextVar[int] = ContextVar("priority", default=priorities.SEARCH)


@contextmanager
def acting_as(lessee: str | None, priority: int) -> Iterator[None]:
    """Say who the model calls made inside the block are for.

    The scheduler wraps a task's run (``lessee`` = its holder name, ``priority`` = its own),
    so the task finds the models reserved for it and is only displaced by more urgent work.
    Outside any block a call counts as a search (the most urgent kind).
    """
    tokens = _lessee.set(lessee), _priority.set(priority)
    try:
        yield
    finally:
        _lessee.reset(tokens[0])
        _priority.reset(tokens[1])


class MemoryPending(Exception):
    """The memory a model needs is not free yet; it will be when ``missing`` is released."""

    def __init__(self, missing: set[str]) -> None:
        super().__init__(f"Waiting for {', '.join(sorted(missing))}")
        self.missing = frozenset(missing)


class Loaded:
    """A model held in memory, shared by every lease that has the same key."""

    def __init__(self, key: Hashable, module: Any, overrides: dict[str, Any], needs: Resources, holder: str) -> None:
        self.key = key
        self.module = module
        self.overrides = overrides  # settings the placement changes (e.g. the device)
        self.needs = needs  # memory it takes in the pool
        self.holder = holder
        self.instance: Any = None
        self.leases = 0
        self.lessees: Counter[str] = Counter()
        self.last_used = time.monotonic()
        self._loading = threading.Lock()  # the first lease loads, the others wait for it
        self._calls = threading.Lock()  # a model serves one call at a time

    def placed(self, settings: Any) -> Any:
        """The settings of a caller, as they apply where this model lives."""
        return settings.model_copy(update=self.overrides) if self.overrides else settings

    def run(self, operation: str, *args: Any) -> Any:
        with self._calls:
            return getattr(self.module, operation)(self.instance, *args)


def _placements(resolved: ResolvedEngine) -> list[tuple[dict[str, Any], Resources]]:
    """Where the model can live, best first: (settings changes, memory taken there)."""
    declared = getattr(resolved.module, "placements", None)
    plans = declared(resolved.settings, resolved.model) if declared else []
    parsed = [(dict(changes), {name: float(amount) for name, amount in needs.items() if amount > 0}) for changes, needs in plans]
    return parsed or [({}, {})]


def _key(resolved: ResolvedEngine, overrides: dict[str, Any]) -> Hashable:
    """Engine + the settings that change what is loaded (``load_key``; all settings by default)."""
    settings = resolved.settings.model_copy(update=overrides) if overrides else resolved.settings
    load_key = getattr(resolved.module, "load_key", None)
    detail = load_key(settings, resolved.model) if load_key else settings.model_dump_json()
    return resolved.engine.name, getattr(resolved.model, "id", None), detail


def _pool():
    from lazy_bird.tasks import scheduler

    return scheduler().pool


def _preempt(deficit: Resources, priority: int) -> bool:
    from lazy_bird.tasks import scheduler

    return scheduler().preempt(deficit, priority)


class Residency:
    def __init__(self) -> None:
        # Every change of the entries and of their leases happens under this lock,
        # unloading included: while a model is being freed nobody can load a second
        # copy of it next to the first one. It is never held while waiting for memory.
        self._lock = threading.RLock()
        self._entries: dict[Hashable, Loaded] = {}
        self._reservations: dict[str, list[Loaded]] = {}
        self._holders = itertools.count(1)

    # -------------------------------------------------------------------- leases
    @contextmanager
    def use(self, resolved: ResolvedEngine) -> Iterator[Loaded]:
        """Hold the model of a local engine for the duration of a ``with`` block."""
        lessee = _lessee.get()
        entry = self._reserved(resolved, lessee)
        if entry is None:
            entry = self._wait_for(resolved, lessee)
        try:
            self._ensure_loaded(entry, resolved)
            yield entry
        finally:
            self._leave(entry, lessee)

    def reserve(self, resolved: ResolvedEngine, *, lessee: str, priority: int, preempt: Preempt | None = None) -> Loaded:
        """Make the memory of a model ready for ``lessee`` (a task about to start) without loading it.

        Raises ``MemoryPending`` when the memory is not free yet (after asking ``preempt``
        to free it), ``InsufficientResourcesError`` when the model can never fit.
        ``release_lessee`` gives the reservation back.
        """
        entry = self._acquire(resolved, lessee, priority, preempt)
        with self._lock:
            self._reservations.setdefault(lessee, []).append(entry)
        return entry

    def release_lessee(self, lessee: str) -> None:
        with self._lock:
            entries = self._reservations.pop(lessee, [])
        for entry in entries:
            self._leave(entry, lessee)

    def _reserved(self, resolved: ResolvedEngine, lessee: str | None) -> Loaded | None:
        """The model a task reserved before it started, when the call is for that model."""
        if lessee is None:
            return None
        with self._lock:
            for entry in self._reservations.get(lessee, []):
                if _key(resolved, entry.overrides) == entry.key:
                    self._join(entry, lessee)
                    return entry
        return None

    def _wait_for(self, resolved: ResolvedEngine, lessee: str | None) -> Loaded:
        """A lease for a caller that cannot go on without the model: wait until its memory is free."""
        priority = _priority.get()
        deadline = time.monotonic() + WAIT_TIMEOUT_SECONDS
        while True:
            try:
                return self._acquire(resolved, lessee, priority, _preempt)
            except MemoryPending:
                if time.monotonic() > deadline:
                    raise UnavailableError("The memory this model needs stayed busy for too long.", code="resources_busy") from None
                _pool().wait_for_release(WAIT_STEP_SECONDS)

    def _join(self, entry: Loaded, lessee: str | None) -> None:
        entry.leases += 1
        entry.lessees[lessee or "call"] += 1
        entry.last_used = time.monotonic()

    def _leave(self, entry: Loaded, lessee: str | None) -> None:
        with self._lock:
            name = lessee or "call"
            entry.leases -= 1
            entry.lessees[name] -= 1
            if entry.lessees[name] <= 0:
                del entry.lessees[name]
            if entry.leases > 0:
                return
            entry.last_used = time.monotonic()
            if not (entry.needs and entry.instance is not None and smart_memory().enable):
                self._remove(entry)  # unsupervised, nothing accounted, or never loaded: no reason to keep it

    # --------------------------------------------------------------- reservation
    def _acquire(self, resolved: ResolvedEngine, lessee: str | None, priority: int, preempt: Preempt | None) -> Loaded:
        """A lease on the model, in the best place it fits now; raises ``MemoryPending`` / ``InsufficientResourcesError``."""
        plans = _placements(resolved)
        with self._lock:
            for overrides, _ in plans:  # a model that is already there is taken, even if it is not the best place
                entry = self._entries.get(_key(resolved, overrides))
                if entry is not None:
                    self._join(entry, lessee)
                    return entry
        memory = smart_memory()
        if not memory.enable:
            return self._create(resolved, plans[0][0], {}, lessee)
        allowed = plans if memory.fallback == "cpu" else plans[:1]
        for overrides, needs in allowed:
            entry = self._try_create(resolved, overrides, needs, lessee)
            if entry is not None:
                return entry
        self._check_possible(resolved, plans, allowed)
        deficit = _pool().deficit(allowed[-1][1], real=True)
        if preempt is not None:
            preempt(deficit, priority)
        raise MemoryPending(set(deficit))

    def _try_create(self, resolved: ResolvedEngine, overrides: dict[str, Any], needs: Resources, lessee: str | None) -> Loaded | None:
        if needs:
            pool, holder = _pool(), self._new_holder(resolved)
            if not pool.try_acquire(holder, needs, real=True):
                self.evict_idle(needs)
                if not pool.try_acquire(holder, needs, real=True):
                    return None
            return self._create(resolved, overrides, needs, lessee, holder)
        return self._create(resolved, overrides, needs, lessee)

    def _create(self, resolved: ResolvedEngine, overrides: dict[str, Any], needs: Resources, lessee: str | None, holder: str | None = None) -> Loaded:
        key = _key(resolved, overrides)
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:  # another thread created the same model meanwhile: share it
                if holder is not None:
                    _pool().release(holder)
                self._join(entry, lessee)
                return entry
            entry = Loaded(key, resolved.module, overrides, needs, holder or self._new_holder(resolved))
            self._entries[key] = entry
            self._join(entry, lessee)
            return entry

    def _new_holder(self, resolved: ResolvedEngine) -> str:
        return f"engine:{next(self._holders)}:{resolved.engine.name}"

    def _check_possible(self, resolved: ResolvedEngine, plans: list, allowed: list) -> None:
        """Refuse a model that does not fit in the machine even when everything else gives way."""
        ceiling = _pool().ceiling()
        if any(all(amount <= ceiling.get(name, 0) for name, amount in needs.items()) for _, needs in allowed):
            return
        _, needs = min(allowed, key=lambda plan: sum(plan[1].values()))
        required, available = sum(needs.values()), sum(ceiling.get(name, 0) for name in needs)
        name = getattr(resolved.model, "name", None) or resolved.engine.name
        message = f"Cannot process with '{name}': use a smaller model. Required memory: {required:,.0f} MB, available memory: {available:,.0f} MB."
        elsewhere = len(allowed) < len(plans) and any(all(amount <= ceiling.get(n, 0) for n, amount in plan.items()) for _, plan in plans)
        if elsewhere:
            message += " It would fit on the CPU: set the memory fallback to 'cpu'."
        raise InsufficientResourcesError(
            message, code="insufficient_memory", details={"model": name, "required_mb": round(required), "available_mb": round(available)}
        )

    def check(self, resolved: ResolvedEngine) -> None:
        """Raise ``InsufficientResourcesError`` when the model of an engine can never fit (nothing is reserved)."""
        memory = smart_memory()
        if not memory.enable:
            return
        plans = _placements(resolved)
        if any(needs for _, needs in plans):
            self._check_possible(resolved, plans, plans if memory.fallback == "cpu" else plans[:1])

    # ------------------------------------------------------------------- loading
    @staticmethod
    def _ensure_loaded(entry: Loaded, resolved: ResolvedEngine) -> None:
        with entry._loading:
            if entry.instance is None:
                entry.instance = entry.module.load(entry.placed(resolved.settings), resolved.model)

    # ------------------------------------------------------------------ eviction
    def evict_idle(self, needs: Resources) -> bool:
        """Unload idle models, least recently used first, until ``needs`` fit in the pool; whether they do."""
        pool = _pool()
        while True:
            missing = pool.blocked_by(needs, real=True)
            if not missing:
                return True
            with self._lock:
                idle = [entry for entry in self._entries.values() if entry.leases == 0 and entry.needs.keys() & missing]
                if not idle:
                    return False
                self._remove(min(idle, key=lambda entry: entry.last_used))

    def release_idle(self) -> None:
        """Unload every model nobody holds (``smart-memory`` turned off, shutdown)."""
        with self._lock:
            for entry in [entry for entry in self._entries.values() if entry.leases == 0]:
                self._remove(entry)

    def shutdown(self) -> None:
        self.release_idle()

    def _remove(self, entry: Loaded) -> None:
        """Forget a model and give back its memory (lock held)."""
        self._entries.pop(entry.key, None)
        instance, entry.instance = entry.instance, None
        if instance is not None:
            try:
                entry.module.unload(instance)
            except Exception:
                logger.exception("Unloading the model of engine '{}' failed", entry.key[0])
        if entry.needs:
            _pool().release(entry.holder)

    def exclusive_to(self, lessee: str) -> Resources:
        """The memory of the models only ``lessee`` holds: what freeing it would let go of."""
        total: Resources = {}
        with self._lock:
            for entry in self._entries.values():
                if entry.leases > 0 and set(entry.lessees) <= {lessee}:
                    for name, amount in entry.needs.items():
                        total[name] = total.get(name, 0) + amount
        return total


_residency: Residency | None = None


def residency() -> Residency:
    """The process-wide residency of local engines."""
    global _residency
    if _residency is None:
        _residency = Residency()
    return _residency
