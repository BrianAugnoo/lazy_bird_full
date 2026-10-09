# To do — lazy_bird

Planned work found while building smart memory management (residency, host processes,
isolated tasks). Each item says what is wrong today, where to look, and what "done"
means. Read `AGENTS.md` §5.3 (local engines) and §7.5 (smart memory) first. Remove an
item in the commit that finishes it.

## 1. RAM of models running on the GPU is not accounted

- **Today**: a GPU placement declares only `vram_mb`. Measured on Qwen3-Embedding-0.6B:
  its host process uses about 2.3–2.5 GB of RAM (torch, CUDA libraries, loading
  buffers) while the model sits on the GPU. The real-memory reading (`tasks/memory.py`)
  limits admission, but the pool's own accounting undercounts RAM, so several hosted
  GPU models can overcommit it.
- **Where**: `placements()` in `embedding/engines/sentence_transformers.py` and
  `cross_encoder/engines/sentence_transformers.py`; `Residency._try_create`.
- **Done when**: a hosted GPU model also holds a `ram_mb` amount (a measured process
  baseline, or the host's real RSS after load, see item 2), with a test.

## 2. Use measured memory instead of estimates

- **Today**: the pool keeps the declared estimate for the whole life of a model
  (weights + 512 MB). Qwen3-Embedding-0.6B is declared at 1,648 MB of VRAM and really
  reserves about 1,300 MB (`torch.cuda.memory_reserved` in its host).
- **Where**: `EngineHost.stats()` already reports `rss_mb` and `vram_mb`;
  `Residency._ensure_loaded` is where a model becomes loaded; `ResourcePool` holders.
- **Done when**: after a hosted model loads, its pool holder is adjusted to what it
  really uses (never below the reservation while loading), and an engine whose
  estimate is badly off is logged. Test with the hosting fake engine
  (`tests/hosting/engine.py`).

## 3. Cancelling a model download does not stop it

- **Today**: `models.download` (`tasks/default/models.py`) only reports progress and
  never reaches a checkpoint, so pause and cancel wait for the whole download.
- **Fix**: declare it `isolated=True`: after `smart-memory.interrupt_timeout_seconds`
  its process is ended and the task finishes as asked. `models.import` is a candidate
  too.
- **Watch out**: `tests/tasks/test_model_tasks.py` monkeypatches `download_model` in the
  server process, which a task process does not see. Those tests have to use a module
  importable by name (like `tests/hosting/tasks.py`), or the network call has to be
  replaced another way.

## 4. Importing `lazy_bird.database` has side effects

- **Today**: on import, `database/__init__.py` reads and **rewrites**
  `database/config.json` and creates a SQL engine for the configured database. Every
  process pays for it (model hosts and task processes included), and tests have to
  monkeypatch module globals afterwards.
- **Done when**: the configuration is read and the engine created on first use (or at
  startup), importing the module writes nothing, and `attach()` (task processes) and the
  test fixtures still work.

## 5. `ensure_all` resolves the default preset once per file

- **Today**: `crud/file_processing.ensure_all()` calls `ensure()` per file, and each
  call runs `automatic_targets()` -> `engine_family.resolve()` (several database
  queries and a settings validation). With thousands of files, a default-preset change
  or a startup spends that much again for every file.
- **Done when**: the targets are resolved once per `ensure_all()` and passed down,
  without breaking the `_queueing` lock (a restart must still never miss a queued
  task, see the comment above `_queueing`).

## 6. Streaming in the engine host protocol

- **Today**: operations of a hosted engine must take and return picklable values
  (`engine_host.py`). A local inference engine needs `chat(..., emit)`: tokens streamed
  through an `Emitter`, and `emit.stopped` read during generation.
- **Done when**: the host protocol can send events (tokens, reasoning) during a call
  and receive a stop request, the agentic loop calls a local engine through
  `ResolvedEngine.call` under `acting_as(..., priority.INFERENCE)`, and `_hold` in
  `inference/__init__.py` remains only for engines that are not local.

## 7. Tests that start processes are slow

- **Today**: the tests starting child processes (`tests/test_engine_host.py`,
  `tests/tasks/test_isolated_tasks.py`, parts of `tests/tasks/test_preemption.py`) take
  about 35 s of the ~80 s suite.
- **Ideas**: share one model host per module where the tests do not depend on a fresh
  process; shorten child start further (the child imports `lazy_bird.tasks`, the
  engine families and their modules).
- **Constraint**: tests must stay isolated and deterministic (`AGENTS.md` §11).
