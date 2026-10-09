# To do — lazy_bird

Planned work found while building smart memory management (residency, host processes,
isolated tasks). Each item says what is wrong today, where to look, and what "done"
means. Read `AGENTS.md` §5.3 (local engines) and §7.5 (smart memory) first. Remove an
item in the commit that finishes it.

## 1. Cancelling a model download does not stop it

- **Today**: `models.download` (`tasks/default/models.py`) only reports progress and
  never reaches a checkpoint, so pause and cancel wait for the whole download.
- **Fix**: declare it `isolated=True`: after `smart-memory.interrupt_timeout_seconds`
  its process is ended and the task finishes as asked. `models.import` is a candidate
  too.
- **Watch out**: `tests/tasks/test_model_tasks.py` monkeypatches `download_model` in the
  server process, which a task process does not see. Those tests have to use a module
  importable by name (like `tests/hosting/tasks.py`), or the network call has to be
  replaced another way.

## 2. Importing `lazy_bird.database` has side effects

- **Today**: on import, `database/__init__.py` reads and **rewrites**
  `database/config.json` and creates a SQL engine for the configured database. Every
  process pays for it (model hosts and task processes included), and tests have to
  monkeypatch module globals afterwards.
- **Done when**: the configuration is read and the engine created on first use (or at
  startup), importing the module writes nothing, and `attach()` (task processes) and the
  test fixtures still work.

## 3. `ensure_all` resolves the default preset once per file

- **Today**: `crud/file_processing.ensure_all()` calls `ensure()` per file, and each
  call runs `automatic_targets()` -> `engine_family.resolve()` (several database
  queries and a settings validation). With thousands of files, a default-preset change
  or a startup spends that much again for every file.
- **Done when**: the targets are resolved once per `ensure_all()` and passed down,
  without breaking the `_queueing` lock (a restart must still never miss a queued
  task, see the comment above `_queueing`).

## 4. Streaming in the engine host protocol

- **Today**: operations of a hosted engine must take and return picklable values
  (`engine_host.py`). A local inference engine needs `chat(..., emit)`: tokens streamed
  through an `Emitter`, and `emit.stopped` read during generation.
- **Done when**: the host protocol can send events (tokens, reasoning) during a call
  and receive a stop request, the agentic loop calls a local engine through
  `ResolvedEngine.call` under `acting_as(..., priority.INFERENCE)`, and `_hold` in
  `inference/__init__.py` remains only for engines that are not local.

## 5. Tests that start processes are slow

- **Today**: the tests starting child processes (`tests/test_engine_host.py`,
  `tests/tasks/test_isolated_tasks.py`, parts of `tests/tasks/test_preemption.py`) take
  about 35 s of the ~80 s suite.
- **Ideas**: share one model host per module where the tests do not depend on a fresh
  process; shorten child start further (the child imports `lazy_bird.tasks`, the
  engine families and their modules).
- **Constraint**: tests must stay isolated and deterministic (`AGENTS.md` §11).

## 6. Reservations forget what a model was measured to take

- **Today**: a hosted model holds what its process really takes once it is read (after it
  loads, after every call: `Residency._account`), but the next time the same model is
  loaded its reservation is the engine's estimate again. For a model on the GPU that
  estimate has no RAM (its process takes 2–3 GB), and Qwen3-Embedding-0.6B is estimated
  at 1,648 MB of VRAM where a batch of 32 long texts takes 3.7 GB: two such models loading
  at the same time can overcommit until their first reading.
- **Where**: `Residency._acquire` (the `needs` of each placement), `Loaded.usage`.
- **Done when**: the last reading of a model key (engine + `load_key` + placement) is kept
  and used as its reservation when it is bigger than the estimate, `_check_possible`
  included, with a test.
