"""Loaded models: who needs the model of a local engine, where it lives, and when it is released.

A local engine (``local = True``, see ``crud.engine``) builds its model with
``load(settings, model)`` and frees it with ``unload(instance)``; its operations
receive the loaded instance as first argument. This module owns those instances:

- ``residency().use(resolved)`` is a lease. The first lease loads the model; leases on
  the same model (same engine and ``load_key``) share one instance, and calls on a
  shared instance run one at a time;
- a caller that knows it will make many calls (a task embedding batch after batch)
  wraps them in one lease, so the model is loaded once instead of once per call;
- the model lives in a host process of its own (``engine_host.py``) when the
  ``smart-memory.isolate_models`` preference is on and the engine module can be
  imported by name; otherwise it lives in the server;
- with ``smart-memory`` off the last lease to leave unloads the model and nothing is
  accounted (unsupervised);
- with ``smart-memory`` on every model holds the memory it takes in the shared resource
  pool (``engine:*`` holders): what its engine estimates (``placements``) until it is
  loaded; for a hosted model, then what its process really takes, read after it loads and
  after every call. An idle model stays loaded until that memory is needed:
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
from lazy_bird.engine_host import EngineHost, EngineProcessError, importable
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
# Orders the uses of models, for "least recently used first". A counter, not a clock:
# time.monotonic() only moves every 15.6 ms on Windows, so close uses would tie.
_uses = itertools.count()


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


class ModelEvicted(Exception):
    """The model of a task was taken away because the task did not make room when asked.

    The scheduler puts the task back in the queue, as if it had yielded."""


class HostedModule:
    """Stands in for an engine module whose model lives in a host process."""

    def __init__(self, module: Any) -> None:
        self._module = module
        self.__name__ = module.__name__

    def load(self, settings: Any, model: Any) -> EngineHost:
        return EngineHost.start(self._module.__name__, settings, model)

    @staticmethod
    def unload(host: EngineHost) -> None:
        host.stop()

    def __getattr__(self, operation: str) -> Callable[..., Any]:
        return lambda host, *args: host.call(operation, args)


class MemoryPending(Exception):
    """The memory a model needs is not free yet; it will be when ``missing`` is released."""

    def __init__(self, missing: set[str]) -> None:
        super().__init__(f"Waiting for {', '.join(sorted(missing))}")
        self.missing = frozenset(missing)


class Loaded:
    """A model held in memory, shared by every lease that has the same key."""

    def __init__(self, key: Hashable, module: Any, overrides: dict[str, Any], needs: Resources, holder: str, label: str) -> None:
        self.key = key
        self.module = module
        self.hosted = isinstance(module, HostedModule)
        self.label = label
        self.evicted = False  # taken away from its users by force
        self.removed = False
        self.overrides = overrides  # settings the placement changes (e.g. the device)
        self.estimate = dict(needs)  # the memory its engine said it takes
        self.needs = needs  # memory it takes in the pool: the estimate, then what a hosted model really takes
        self.usage: Resources = {}  # what its host process took at the last reading
        self.served = False  # it ran a call: its working memory is in the readings
        self.estimate_checked = False
        self.holder = holder
        self.instance: Any = None
        self.leases = 0
        self.lessees: Counter[str] = Counter()
        self.last_used = next(_uses)
        self._loading = threading.Lock()  # the first lease loads, the others wait for it
        self._calls = threading.Lock()  # a model serves one call at a time

    def placed(self, settings: Any) -> Any:
        """The settings of a caller, as they apply where this model lives."""
        return settings.model_copy(update=self.overrides) if self.overrides else settings

    def run(self, operation: str, *args: Any) -> Any:
        with self._calls:
            if self.evicted:
                raise ModelEvicted("The model was taken away to make room for more urgent work.")
            instance = self.instance
            try:
                result = getattr(self.module, operation)(instance, *args)
            except EngineProcessError:
                if self.evicted:
                    raise ModelEvicted("The model was taken away to make room for more urgent work.") from None
                if self.hosted and not instance.alive:
                    instance.kill()  # reap it
                    if self.instance is instance:
                        self.instance = None  # the process is gone: the next use loads the model again
                raise
            if self.hosted:
                self.served = True
                self.usage = _usage(instance)  # read while no other call runs in the process
            return result


def _usage(host: EngineHost) -> Resources:
    """What a host process really takes, as pool resources (only what could be read)."""
    stats = host.stats() or {}
    usage = {}
    if stats.get("rss_mb"):
        usage["ram_mb"] = stats["rss_mb"]
    if stats.get("vram_peak_mb"):
        usage["vram_mb"] = stats["vram_peak_mb"]  # the peak: a batch needs that much again
    return usage


def _misestimated(estimate: Resources, usage: Resources) -> dict[str, tuple[float, float]]:
    """The resources an engine estimated badly (by more than a quarter and more than 256 MB): (estimated, used)."""
    return {
        name: (amount, usage[name])
        for name, amount in estimate.items()
        if name in usage and abs(usage[name] - amount) > max(256.0, amount / 4)
    }


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
        # Every change of the entries and of their leases happens under this lock. It is
        # never held while waiting for memory nor while a model unloads (a hosted model
        # waits for its process to end): a model being freed keeps its memory in the pool
        # until it is gone, so a second copy can never be accounted next to it.
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

    def call(self, resolved: ResolvedEngine, operation: str, args: tuple) -> Any:
        """Run an operation on the model of a local engine: ``operation(instance, *args, settings, model)``.

        ``settings`` are the caller's, as they apply where the model was placed.
        """
        with self.use(resolved) as loaded:
            result = loaded.run(operation, *args, loaded.placed(resolved.settings), resolved.model)
            self._account(loaded)
            return result

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
        entry.last_used = next(_uses)

    def _leave(self, entry: Loaded, lessee: str | None) -> None:
        with self._lock:
            name = lessee or "call"
            entry.leases -= 1
            entry.lessees[name] -= 1
            if entry.lessees[name] <= 0:
                del entry.lessees[name]
            if entry.leases > 0:
                return
            entry.last_used = next(_uses)
            if entry.needs and entry.instance is not None and smart_memory().enable:
                return  # kept while idle, until its memory is needed
            detached = self._detach(entry)  # unsupervised, nothing accounted, or never loaded
        self._free([detached])

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
            module = HostedModule(resolved.module) if smart_memory().isolate_models and importable(resolved.module) else resolved.module
            label = getattr(resolved.model, "name", None) or resolved.engine.name
            entry = Loaded(key, module, overrides, needs, holder or self._new_holder(resolved), label)
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
    def _ensure_loaded(self, entry: Loaded, resolved: ResolvedEngine) -> None:
        with entry._loading:
            if entry.evicted:
                raise ModelEvicted("The model was taken away to make room for more urgent work.")
            if entry.instance is not None:
                return
            instance = entry.module.load(entry.placed(resolved.settings), resolved.model)
            if entry.hosted:
                entry.usage = _usage(instance)
            with self._lock:
                if not entry.removed:
                    entry.instance = instance
                    self._account(entry)
                    return
            # Taken away (shutdown, eviction) while it was loading: nobody would ever free it.
            try:
                entry.module.unload(instance)
            except Exception:
                logger.exception("Unloading the model of engine '{}' failed", entry.key[0])
            raise ModelEvicted("The model was taken away while it was loading.")

    def _account(self, entry: Loaded) -> None:
        """Make the pool hold what a hosted model really takes (its last reading) instead of its estimate.

        Until it has served a call a model has not used its working memory yet (the
        activations of a batch): the reading taken after it loads can raise the estimate
        (the RAM of its process, for a model on the GPU) but not lower it.
        """
        usage = entry.usage
        if not usage or not entry.needs:  # not hosted, not read, or not accounted at all
            return
        with self._lock:
            if entry.removed:
                return
            needs = dict(entry.needs)
            for name, amount in usage.items():
                needs[name] = amount if entry.served else max(needs.get(name, 0.0), amount)
            entry.needs = needs
            _pool().resize(entry.holder, needs)
            if not entry.served or entry.estimate_checked:
                return
            entry.estimate_checked = True
        if off := _misestimated(entry.estimate, usage):
            logger.warning(
                "Engine '{}' misestimates the memory of '{}': {}",
                entry.key[0],
                entry.label,
                ", ".join(f"{name} estimated {estimated:,.0f} MB, really {used:,.0f} MB" for name, (estimated, used) in off.items()),
            )

    # ------------------------------------------------------------------ eviction
    def evict_idle(self, needs: Resources) -> bool:
        """Unload idle models, least recently used first, until ``needs`` fit in the pool; whether they do."""
        pool = _pool()
        return self._evict_idle_while(lambda: pool.blocked_by(needs, real=True))

    def fit_to_capacity(self) -> None:
        """Unload idle models, least recently used first, while the pool holds more than its capacity.

        After the capacity was lowered (``tasks.resources``): the memory set aside for other
        programs is given back as soon as nobody uses the models in it.
        """
        pool = _pool()

        def over_capacity() -> set[str]:
            snapshot = pool.snapshot()
            return {name for name, used in snapshot["used"].items() if used > snapshot["capacity"].get(name, 0)}

        self._evict_idle_while(over_capacity)

    def _evict_idle_while(self, missing: Callable[[], set[str]]) -> bool:
        """Unload idle models holding one of the ``missing()`` resources, least recently used
        first, until nothing is missing; whether that happened."""
        while names := missing():
            with self._lock:
                idle = [entry for entry in self._entries.values() if entry.leases == 0 and entry.needs.keys() & names]
                if not idle:
                    return False
                detached = self._detach(min(idle, key=lambda entry: entry.last_used))
            self._free([detached])
        return True

    def release_idle(self) -> None:
        """Unload every model nobody holds (``smart-memory`` turned off, shutdown)."""
        with self._lock:
            detached = [self._detach(entry) for entry in list(self._entries.values()) if entry.leases == 0]
        self._free(detached)

    def shutdown(self) -> None:
        """Server stopping: unload idle models, and end the host processes of the ones still in use.

        Users of those models get ``ModelEvicted`` on their next call (a task goes back to the queue).
        """
        self.release_idle()
        self._take_away(lambda entry: True)

    def force_release(self, lessee: str) -> list[str]:
        """Take away from ``lessee`` the hosted models only it holds, ending their processes.

        For a lessee that does not step aside when asked: the memory comes back at once even
        though its thread cannot be stopped, and its next call on those models raises
        ``ModelEvicted``. Models living in the server itself cannot be taken back this way.
        """
        return self._take_away(lambda entry: entry.leases > 0 and set(entry.lessees) <= {lessee})

    def _take_away(self, chosen: Callable[[Loaded], bool]) -> list[str]:
        """End the processes of the hosted models ``chosen`` picks, even in use; their names."""
        with self._lock:
            entries = [entry for entry in self._entries.values() if entry.hosted and chosen(entry)]
            detached = []
            for entry in entries:
                entry.evicted = True
                if entry.instance is not None:
                    entry.instance.kill()
                detached.append(self._detach(entry))
        self._free(detached)
        return [entry.label for entry in entries]

    def _detach(self, entry: Loaded) -> tuple[Loaded, Any] | None:
        """Forget a model (lock held); returns what ``_free`` must release, None if already forgotten."""
        if entry.removed:
            return None
        entry.removed = True
        if self._entries.get(entry.key) is entry:
            del self._entries[entry.key]
        instance, entry.instance = entry.instance, None
        return entry, instance

    def _free(self, detached: list[tuple[Loaded, Any] | None]) -> None:
        """Unload forgotten models, then give their memory back to the pool (lock not held)."""
        for item in detached:
            if item is None:
                continue
            entry, instance = item
            if instance is not None:
                try:
                    entry.module.unload(instance)
                except Exception:
                    logger.exception("Unloading the model of engine '{}' failed", entry.key[0])
            if entry.needs:
                _pool().release(entry.holder)

    def describe(self) -> list[dict[str, Any]]:
        """The models in memory: where they live, what they take, who uses them (for the interface)."""
        with self._lock:
            entries = list(self._entries.values())
        return [
            {
                "model": entry.label,
                "engine": entry.key[0],
                "device": entry.overrides.get("device"),
                "needs": dict(entry.needs),
                "idle": entry.leases == 0,
                "users": sorted(entry.lessees),
                "pid": entry.instance.pid if entry.hosted and entry.instance is not None else None,
                "memory": entry.instance.stats() if entry.hosted and entry.instance is not None else None,
            }
            for entry in entries
        ]

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
