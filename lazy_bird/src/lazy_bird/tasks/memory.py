"""Memory supervision: what the machine really has free, and who should make room.

Live readings are displayed regardless of the ``smart-memory`` preference. The pool
only knows what its holders declared; ``system_free`` tells what the OS reports, so memory used by
other programs (or by a holder that under-declared) is taken into account too.
``choose_victims`` picks which running work has to yield to a more urgent request.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from itertools import combinations
from typing import TypedDict

from loguru import logger

Resources = dict[str, float]

MAX_CANDIDATES = 12  # subsets are enumerated: only the least urgent ones are considered
READ_CACHE_SECONDS = 1.0


class MemoryUsage(TypedDict):
    total_mb: float
    used_mb: float
    available_mb: float


_lock = threading.Lock()
_cached: tuple[float, dict[str, MemoryUsage | None]] | None = None
_nvidia_smi: str | None | bool = True  # True: not looked up yet, None: not installed


def _ram_usage() -> MemoryUsage | None:
    try:
        import psutil

        ram = psutil.virtual_memory()
        # Reclaimable caches are available for new work, on Linux as well as Windows.
        return {"total_mb": ram.total / 1024**2, "used_mb": (ram.total - ram.available) / 1024**2, "available_mb": ram.available / 1024**2}
    except Exception as error:
        logger.debug("Could not read RAM usage: {}", error)
        return None


def _vram_usage() -> MemoryUsage | None:
    """Memory of GPU 0, the pool's device, without creating a CUDA context."""
    global _nvidia_smi
    if _nvidia_smi is True:
        _nvidia_smi = shutil.which("nvidia-smi")
    if not _nvidia_smi:
        return None
    try:
        output = subprocess.run(
            [_nvidia_smi, "--id=0", "--query-gpu=memory.total,memory.used,memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        ).stdout
        total, used, available = (float(value.strip()) for value in output.splitlines()[0].split(","))
        if not all(math.isfinite(value) and value >= 0 for value in (total, used, available)) or used > total or available > total:
            raise ValueError("Invalid GPU memory reading")
        # Driver-reserved memory means used + free need not equal total.
        return {"total_mb": total, "used_mb": used, "available_mb": available}
    except Exception as error:
        logger.debug("Could not read GPU memory usage: {}", error)
        return None


def system_usage() -> dict[str, MemoryUsage | None]:
    """Machine-wide memory in MiB, including other programs; unavailable readings are null.

    The UI and admission checks share one sample, cached for at most a second.
    Failed reads replace stale samples, so they cannot appear as current usage.
    """
    global _cached
    with _lock:
        if _cached is not None and time.monotonic() - _cached[0] < READ_CACHE_SECONDS:
            return {name: dict(value) if value is not None else None for name, value in _cached[1].items()}
        usage = {"ram_mb": _ram_usage(), "vram_mb": _vram_usage()}
        _cached = (time.monotonic(), usage)
        return {name: dict(value) if value is not None else None for name, value in usage.items()}


def system_free() -> Resources:
    """Available memory from the same live sample used by the UI; omit unknown limits."""
    return {name: value["available_mb"] for name, value in system_usage().items() if value is not None}


@dataclass(frozen=True)
class Candidate:
    """Running work that could yield: what it would give back, and how urgent it is."""

    holder: str
    priority: int
    releases: Resources


def choose_victims(deficit: Resources, candidates: list[Candidate]) -> list[Candidate] | None:
    """The fewest candidates whose releases cover the deficit; None when all of them together do not.

    Among equally small sets the one made of the least urgent work wins, then the one
    that gives back the least. Example: 2 missing, A gives 4, B gives 0.5: only A is asked.
    """
    needed = {name: amount for name, amount in deficit.items() if amount > 0}
    if not needed:
        return []
    pool = sorted(candidates, key=lambda candidate: candidate.priority, reverse=True)[:MAX_CANDIDATES]
    for size in range(1, len(pool) + 1):
        covering = [
            subset
            for subset in combinations(pool, size)
            if all(sum(candidate.releases.get(name, 0) for candidate in subset) >= amount for name, amount in needed.items())
        ]
        if covering:
            best = min(covering, key=lambda subset: (-sum(c.priority for c in subset), sum(sum(c.releases.values()) for c in subset)))
            return list(best)
    return None
