"""Shared pool of machine resources (CPU slots, VRAM, RAM).

Every consumer of heavy resources declares what it needs as a dict, e.g.
``{"cpu": 1, "vram_mb": 1500}``. Tasks get their resources from the scheduler;
code running outside tasks (local inference) holds them with ``pool.hold(...)``.
Work that does not fit waits until enough is released, which is what lets local
embedding and local inference run side by side only when the GPU has room.

Capacities are detected at startup and can be overridden with the preference
``tasks.resources`` (for instance to keep VRAM for other applications).

With ``smart-memory`` on, callers pass ``real=True``: what is free is then also capped by
what the operating system reports (``monitor``), so memory used by other programs counts.
"""

from __future__ import annotations

import os
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Callable, Iterator

from loguru import logger

from lazy_bird.errors import InsufficientResourcesError

Resources = dict[str, float]
MONITORED = frozenset({"ram_mb", "vram_mb"})  # what the machine reports (tasks.memory.system_free)

__all__ = ["InsufficientResourcesError", "ResourcePool", "Resources", "detect_capacity"]


def _total_ram_mb() -> float:
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 1024**2
    except (ValueError, OSError, AttributeError):
        return 8192.0


def _total_vram_mb() -> float:
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.get_device_properties(0).total_memory / 1024**2
    except Exception as error:
        logger.warning("Could not detect GPU memory: {}", error)
    return 0.0


def detect_capacity() -> Resources:
    return {"cpu": float(os.cpu_count() or 1), "ram_mb": round(_total_ram_mb()), "vram_mb": round(_total_vram_mb())}


@dataclass
class ResourcePool:
    capacity: Resources
    monitor: Callable[[], Resources] | None = None  # what the machine really has free, see tasks.memory.system_free
    _used: Resources = field(default_factory=dict)
    _holders: dict[str, Resources] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._condition = threading.Condition()

    def _actual(self, real: bool, needs: Resources | None = None) -> Resources:
        """Free memory reported by the machine, when ``needs`` involve memory.

        Read outside the lock: reading GPU memory starts a process (``nvidia-smi``), which
        work needing only CPU slots does not have to wait for.
        """
        if not real or self.monitor is None or (needs is not None and not MONITORED & {name for name, amount in needs.items() if amount > 0}):
            return {}
        return self.monitor()

    def check(self, needs: Resources) -> None:
        """Raise when ``needs`` could never fit, even on an idle machine."""
        too_big = {
            name: amount
            for name, amount in needs.items()
            if amount > 0 and amount > self.capacity.get(name, 0)
        }
        if too_big:
            details = ", ".join(f"{name}: needs {amount:g}, capacity {self.capacity.get(name, 0):g}" for name, amount in too_big.items())
            raise InsufficientResourcesError(f"Not enough resources on this machine ({details}).", details={"needs": needs, "capacity": self.capacity})

    def ceiling(self) -> Resources:
        """The most each resource could ever give: its capacity, or less when other programs hold part of it for good.

        Counts everything held through this pool as releasable (it can all finish or yield)
        and the memory the machine reports free.
        """
        actual = self._actual(True)
        with self._condition:
            return {
                name: min(total, actual[name] + self._used.get(name, 0)) if name in actual else total
                for name, total in self.capacity.items()
            }

    def free(self, real: bool = False) -> Resources:
        actual = self._actual(real)
        with self._condition:
            return {name: self._free(name, actual) for name in self.capacity}

    def _free(self, name: str, actual: Resources) -> float:
        free = self.capacity.get(name, 0) - self._used.get(name, 0)
        return min(free, actual[name]) if name in actual else free

    def fits(self, needs: Resources, real: bool = False) -> bool:
        actual = self._actual(real, needs)
        with self._condition:
            return self._fits(needs, actual)

    def _fits(self, needs: Resources, actual: Resources) -> bool:
        return all(amount <= self._free(name, actual) for name, amount in needs.items() if amount > 0)

    def blocked_by(self, needs: Resources, real: bool = False) -> set[str]:
        """Resource names that currently prevent ``needs`` from fitting."""
        return set(self.deficit(needs, real))

    def deficit(self, needs: Resources, real: bool = False) -> Resources:
        """How much of each resource is missing for ``needs`` to fit now (only the missing ones)."""
        actual = self._actual(real, needs)
        with self._condition:
            missing = {name: amount - self._free(name, actual) for name, amount in needs.items() if amount > 0}
        return {name: amount for name, amount in missing.items() if amount > 0}

    def held(self, holder: str) -> Resources:
        with self._condition:
            return dict(self._holders.get(holder, {}))

    def try_acquire(self, holder: str, needs: Resources, real: bool = False) -> bool:
        actual = self._actual(real, needs)
        with self._condition:
            if not self._fits(needs, actual):
                return False
            self._take(holder, needs)
            return True

    def acquire(self, holder: str, needs: Resources, timeout: float | None = None) -> bool:
        """Block until ``needs`` fit (or ``timeout`` expires); return whether they were taken."""
        self.check(needs)
        with self._condition:
            if not self._condition.wait_for(lambda: self._fits(needs, {}), timeout=timeout):
                return False
            self._take(holder, needs)
            return True

    def wait_for_release(self, timeout: float) -> None:
        """Sleep until something is released (or ``timeout`` passes)."""
        with self._condition:
            self._condition.wait(timeout)

    def _take(self, holder: str, needs: Resources) -> None:
        for name, amount in needs.items():
            self._used[name] = self._used.get(name, 0) + amount
        held = self._holders.setdefault(holder, {})
        for name, amount in needs.items():
            held[name] = held.get(name, 0) + amount

    def release(self, holder: str) -> None:
        with self._condition:
            for name, amount in self._holders.pop(holder, {}).items():
                self._used[name] = max(0.0, self._used.get(name, 0) - amount)
            self._condition.notify_all()

    @contextmanager
    def hold(self, holder: str, needs: Resources, timeout: float | None = None) -> Iterator[None]:
        """Hold resources for the duration of a ``with`` block (waiting for them if needed)."""
        if not self.acquire(holder, needs, timeout):
            raise TimeoutError(f"Resources {needs} were not available in time")
        try:
            yield
        finally:
            self.release(holder)

    def snapshot(self) -> dict:
        with self._condition:
            return {
                "capacity": dict(self.capacity),
                "used": {name: amount for name, amount in self._used.items() if amount},
                "holders": {holder: dict(needs) for holder, needs in self._holders.items()},
            }
