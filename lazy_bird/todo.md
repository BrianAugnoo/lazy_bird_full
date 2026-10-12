# To do — lazy_bird

Planned work found while building smart memory management (residency, host processes,
isolated tasks). Each item says what is wrong today, where to look, and what "done"
means. Read `AGENTS.md` §5.3 (local engines) and §7.5 (smart memory) first. Remove an
item in the commit that finishes it.

## 1. Tests that start processes are slow

- **Today** (Windows, 2026-10-09): the suite takes about 86 s, of which the tests starting
  child processes (`tests/test_engine_host.py`, `tests/tasks/test_isolated_tasks.py`,
  `tests/inference/test_local_engine.py`, parts of `tests/tasks/test_preemption.py`) take
  about 25 s. A model host starts in about 0.3 s (0.6 s when its module imports
  `lazy_bird.inference`); an isolated task's process in about 1.2 s, 0.55 s of which is
  importing `lazy_bird.task_host` (`lazy_bird.tasks` → `scheduler` → `crud.task` →
  SQLAlchemy/SQLModel and every model). Already done: the OpenAI SDK is imported on first
  use (it cost 0.8 s in every task process), and models left at the end of a test are
  freed into the test's own pool (a default scheduler was built for them, importing torch).
- **Ideas**: share one model host per module where the tests do not depend on a fresh
  process; make `lazy_bird.task_host` import less before the task module needs it.
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

## 3. Batch commits when queueing processing for many files

- **Today** (2026-10-12): the performance pass reduced a 300-file embedding queue
  from 1,500 to 900 commits (three per file: wanted row, task, task link). On a
  temporary Windows SQLite database with memory checks disabled, that pass fell
  from 3.147 s to 2.644 s. Ensuring unchanged queued files now commits nothing.
  `_ensure` reads processing rows once and duplicate status notifications do not
  write. Task creation and its listener still own separate transactions.
- **Where**: `crud/file_processing._ensure`, `_queue`, `on_task_change`; `Scheduler.submit`.
- **Done when**: a pass over many files commits a bounded number of times per batch of
  files, preserving `_queueing`, task deduplication and publication only after commit,
  with rollback and concurrent default-preset-change tests. Combining those transactions
  needs a scheduler transaction contract; do not defer events while allowing tasks to start.
