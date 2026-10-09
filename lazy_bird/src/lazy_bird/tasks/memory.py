"""Memory supervision: what the machine really has free, and who should make room.

Used when the ``smart-memory`` preference is on. The pool only knows what its holders
declared; ``system_free`` tells what the operating system reports, so memory used by
other programs (or by a holder that under-declared) is taken into account too.
``choose_victims`` picks which running work has to yield to a more urgent request.
"""

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from itertools import combinations

from loguru import logger

Resources = dict[str, float]

MAX_CANDIDATES = 12  # subsets are enumerated: only the least urgent ones are considered
READ_CACHE_SECONDS = 1.0

_lock = threading.Lock()
_cached: tuple[float, Resources] | None = None
_nvidia_smi: str | None | bool = True  # True: not looked up yet, None: not installed


def _free_ram_mb() -> float | None:
    try:
        import psutil

        return psutil.virtual_memory().available / 1024**2
    except Exception as error:
        logger.debug("Could not read the free RAM: {}", error)
        return None


def _free_vram_mb() -> float | None:
    """Free memory of the first NVIDIA GPU, without creating a CUDA context in this process."""
    global _nvidia_smi
    if _nvidia_smi is True:
        _nvidia_smi = shutil.which("nvidia-smi")
    if not _nvidia_smi:
        return None
    try:
        output = subprocess.run(
            [_nvidia_smi, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
        return float(output.splitlines()[0])
    except Exception as error:
        logger.debug("Could not read the free GPU memory: {}", error)
        return None


def system_free() -> Resources:
    """Memory the operating system reports free right now (MiB): ``ram_mb`` and, with an NVIDIA GPU, ``vram_mb``.

    A kind that cannot be read is left out, which means "no known limit". Readings are
    cached for a second: the scheduler asks on every pass.
    """
    global _cached
    with _lock:
        if _cached is not None and time.monotonic() - _cached[0] < READ_CACHE_SECONDS:
            return dict(_cached[1])
        free = {name: value for name, value in (("ram_mb", _free_ram_mb()), ("vram_mb", _free_vram_mb())) if value is not None}
        _cached = (time.monotonic(), free)
        return dict(free)


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
