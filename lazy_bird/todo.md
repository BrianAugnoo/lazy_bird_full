# To do — lazy_bird

Planned work found while building smart memory management (residency, host processes,
isolated tasks). Each item says what is wrong today, where to look, and what "done"
means. Read `AGENTS.md` §5.3 (local engines) and §7.5 (smart memory) first. Remove an
item in the commit that finishes it.

## 1. Tests that start processes are slow

- **Today**: the tests starting child processes (`tests/test_engine_host.py`,
  `tests/tasks/test_isolated_tasks.py`, parts of `tests/tasks/test_preemption.py`) take
  about 35 s of the ~80 s suite.
- **Ideas**: share one model host per module where the tests do not depend on a fresh
  process; shorten child start further (the child imports `lazy_bird.tasks`, the
  engine families and their modules).
- **Constraint**: tests must stay isolated and deterministic (`AGENTS.md` §11).

## 2. Reservations forget what a model was measured to take

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

## 3. A pass over every file commits five times per file

- **Today**: `ensure_all()` (startup, a new default preset, a vector database switch)
  costs about 16 ms per file on Windows (300 chunked files: 5 s), almost all of it SQLite
  commits: `_ensure` commits twice, then the task is created (`task_crud.create`) and its
  row linked (`on_task_change`, twice: once by `_queue`, once by the scheduler's event).
  Profile of that pass: 1,500 commits (1.7 s), task creation and its event (2.3 s),
  `on_task_change` (1.6 s). Resolving presets is no longer a factor (the last per-file
  resolve, about 10%, is the memory check of `scheduler.submit` on `files.embed`).
- **Where**: `crud/file_processing._ensure`, `_queue`, `on_task_change`; `Scheduler.submit`.
- **Done when**: a pass over many files commits a bounded number of times per batch of
  files (or a measured large speed-up), the `_queueing` guarantee and the task events
  kept, with a test counting commits or a benchmark in the handoff.
