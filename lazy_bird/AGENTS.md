# Agent guide — lazy_bird

lazy_bird is an open-source orchestration platform for AI agents built to be
extended: think "WordPress for AI workflows". It stores files, turns them into
searchable knowledge (chunks, embeddings), and runs teams of agents that use tools,
hooks, skills and instructions. Almost everything is an **extension**: a module
dropped in a known folder, found at startup through a documented contract.

This file is the reference for the backend and for how to work in this repository.
The frontend has its own guide: `web/AGENTS.md`.

### Start here

Read §2 (how to work) and §3 (architecture) first, then jump to what you need:

| I want to… | Read | Look at |
| --- | --- | --- |
| understand a request end to end | §3.3, §4 | `api/endpoints/<resource>.py` → `schemas/` → `crud/` → `models/` |
| add an engine, chunker, database, tool, hook, skill, preset or task kind | §5 (table in §5.3) | the `default/` example of that extension point |
| change how agents answer | §6.3 | `inference/__init__.py`, `agents/runtime.py` |
| run something long in the background | §7.1 | `tasks/default/*.py` |
| understand why a file is not searchable | §7.4 | `crud/file_processing.py`, Tasks and Files pages |
| change a table | §9 | `models/`, `migration/versions/`, `tests/test_migrations.py` |
| add or change an endpoint | §10, §4 | `tests/test_api_contract.py`, then the screen in `web/` |
| write tests | §11 | `tests/conftest.py` fixtures |

To see it running: `uv run uvicorn lazy_bird.main:app --reload`, then `cd ../web &&
npm run dev` (http://localhost:5173); `/docs` lists every route and `/schemas`
draws the data model.

## 1. Repository

```text
lazy_bird_full/
  lazy_bird/          backend (FastAPI, Python ≥ 3.12, uv)   ← this guide
    src/lazy_bird/    the package
    tests/            pytest suite
    sandbox/          independent experiments (git-ignored, not tracked): ignore it entirely
  web/                frontend (React, Vite) — see web/AGENTS.md
```

## 2. How to work

### 2.1 Workflow

1. **Start from a clean state.** Inspect what changed since `HEAD`; if work is
   uncommitted, commit it as a snapshot before starting anything else.
2. **Work in steps.** Split large work into steps (phases), done in order. A step is
   finished when its behavior is implemented, tested and the whole suite is green.
3. **One commit per successful step**, with tests green (backend and, when touched,
   frontend). Never push: the developer pushes.
4. **Ask before committing what was not specified.** If the expected outcome of a
   step was not defined down to the details, list the decisions you took and ask the
   developer to validate them before the commit.
5. **Revert rather than pile up fixes.** If a step goes badly wrong, go back to the
   previous commit and redo it, instead of stacking fixes on a broken base.
6. **Fix what you find.** Inconsistencies, bad practices and bugs met on the way are
   fixed without asking (with a test), and mentioned in the handoff.
7. **Every schema change has a migration** (Alembic revision preserving data), or a
   documented reset procedure when data cannot be converted (see §9).
8. **Keep the docs true.** This file and `web/AGENTS.md` describe the current code;
   update them in the same commit as the change that makes them stale.

### 2.2 Commands

```bash
uv sync                                          # install (never use pip / uv pip)
uv run uvicorn lazy_bird.main:app --reload       # dev server on :8000 (docs at /docs)
uv run pytest -q                                 # full suite (~35 s)
uv run pytest tests/crud -q                      # one area

# Alembic (from src/lazy_bird/)
cd src/lazy_bird && uv run alembic revision --autogenerate -m "describe the change"
cd src/lazy_bird && uv run alembic upgrade head
```

The server migrates the selected SQL database to the latest revision at startup.
`LAZY_BIRD_TRACE_ALL=0` disables call tracing at startup (it can also be switched
at runtime from the Logs page / `PUT /logs/tracing`).

### 2.3 Engineering principles

- **One responsibility per unit.** Before adding a function, class or module, finish
  the sentence "this is responsible for …" without "and". Endpoints translate HTTP,
  schemas validate, CRUD persists, storages touch the disk, extensions do their one job.
- **Contracts over branching.** Variable behavior comes from an extension point with
  a documented contract (§5), not from `if kind == …` scattered in the code.
- **Simple and readable.** The simplest solution that fits; clear names; short
  functions; no generic helpers, base classes or managers without a concrete need;
  comments explain *why*. Two clear duplicated lines beat a confusing abstraction.
- **Typed errors only.** Raise `AppError` subclasses (§4); never let a traceback or
  a bare `HTTPException` reach a client.
- **Small, reviewable changes.** Do not mix a feature with a general refactor, a
  migration with unrelated changes, or functional changes with mass formatting.

### 2.4 LLM proxy for manual tests

An OpenAI-compatible proxy (Omniroute) is available for manual and end-to-end tests.
Its base URL, model name and API key live in the git-ignored `lazy_bird/.env`
(`LAZY_BIRD_TEST_LLM_BASE_URL`, `LAZY_BIRD_TEST_LLM_MODEL`, `LAZY_BIRD_TEST_LLM_API_KEY`).
**Never commit the key itself.** From WSL, `localhost` does not reach the Windows
host: use the host IP given by `LAZY_BIRD_TEST_LLM_BASE_URL_WSL`. The automated
suite never calls it (it uses the `fake_inference` fixture).

## 3. Architecture

### 3.1 Package layout (`src/lazy_bird/`)

| Folder / module | Responsibility |
| --- | --- |
| `main.py` | FastAPI app, startup (lifespan), `/health`, `/schemas`, middleware refusing requests while startup failed |
| `api/` | `endpoints/*.py` (one router per resource), `error_handlers.py` (uniform errors), `engine_routes.py` (router factory shared by engine families) |
| `schemas/` | pydantic input/output models of the API (`types.py`: `UtcDatetime`) |
| `crud/` | persistence and business rules per resource (no HTTP) |
| `models/` | SQLModel tables |
| `migration/` | Alembic environment and revisions |
| `errors.py` | typed errors (§4) |
| `extension/` | discovery conventions (`discovery.py`) and the settings contract (`settings.py`) |
| `database/` | SQL and vector adapters, selection, connection, vector operations (`contracts.py`) |
| `storages/` | files on disk: uploads in `storages/uploads/` (git-ignored), safe paths, hashes |
| `chunker/` | splits files into chunks, one extension per file type |
| `embedding/` | embedding engine family, `embed_texts`, `embed_query`, vector spaces |
| `cross_encoder/` | cross-encoder engine family (reranking), `rerank_scores` |
| `inference/` | inference engine family, agentic loop, streaming types |
| `agents/` | tools, hooks, skills, instructions, agent and session presets, agent runtime |
| `tasks/` | background task system: registry, scheduler, resources, events, task kinds |
| `residency.py` | models of local engines in memory: who holds them, where they live, when they are loaded and freed (§5.3, §7.5) |
| `priority.py` | the priority ranks: `NOW` 0, `SEARCH` 1, `INFERENCE` 2, `BACKGROUND` 5 (lower = more urgent) |
| `tools/` | utilities: Hugging Face cache and auth, model inspection, GGUF reader, schema diagram |
| `preferences.py` + `preference.yaml` | runtime preferences (§8) |
| `logging_config.py`, `log_*.py` | loguru setup, call tracing, log search and call trees |
| `templates/schemas.html` | the data model diagram (pan by dragging, zoom with the wheel) |

### 3.2 Startup

`lifespan` in `main.py`:

1. connect the selected SQL database and migrate it to `head` (failure → the server
   answers `/health` with the error and every other route with `503 startup_failed`);
2. log in to Hugging Face with the `HuggingFace` API key (anonymous without it);
3. register every model found in the Hugging Face cache (`sync_cache`);
4. `initialize_extensions()`: engines, instruction/skill/preset folders, tools, hooks,
   skills, task kinds (also run by `POST /extensions/reload`);
5. connect the selected vector database;
6. `apply_preferences()`: queue missing processing of files, schedule the periodic
   file scan, apply resource capacity overrides;
7. start the task scheduler (stopped on shutdown; running tasks are re-queued).

### 3.3 Request path

`endpoint (HTTP) → schema (validation) → crud / domain module → models / adapters`.
Endpoints stay thin; anything reusable lives below them. Long or heavy work never
runs in a request: it is submitted as a task (§7).

## 4. Errors

Every error response has the same shape, whatever the route:

```json
{"error": {"code": "file_not_found", "message": "File 9 was not found.", "details": {}}}
```

`errors.py` defines `AppError(message, *, code, details)` and its subclasses with
their status: `NotFoundError(resource, identifier)` 404 (code
`{resource}_not_found`), `InvalidInputError` 422, `InvalidSettingsError(fields)` 422
(`details.fields` = one message per attribute), `ForbiddenError` 403, `ConflictError`
409, `UnavailableError` 503, `ExternalServiceError` 502. Request validation errors are
reported per field the same way (`details.fields`), unknown routes too, and any
unexpected exception becomes `500 internal_error` with no traceback (it is logged).
WebSockets send `{"type": "error", "error": {...}}` with the same body.

## 5. Extensions

### 5.1 Discovery conventions (`extension/discovery.py`)

Two layouts:

- **flat packages** — `embedding/engines/`, `cross_encoder/engines/`, `inference/engines/`, `chunker/extensions/`,
  `database/sql_db/`, `database/vector_db/`: every module whose name does not start
  with `_` is an extension;
- **extension folders** — `agents/tools/`, `agents/hook/`, `agents/skill/`,
  `agents/instruction/{full,sub}/`, `agents/agent_preset/`, `agents/session_preset/`,
  `tasks/`: one directory per extension, `{extension_name}/`. **`default/` ships with
  lazy_bird** (read-only through the API); **`custom/` belongs to the user** (its
  content is git-ignored); other folder names are other extensions.

A module that breaks its contract never stops the application: discovery records a
`LoadFailure` (shown by `GET /extensions/failures` and the Extensions page) and
skips it. Ids of file-based items are `"{extension}/{name}"`; ids of tools and hooks
are `{extension}-{module}-{function}` (or `-{Class}-{method}`).

### 5.2 Settings contract (`extension/settings.py`)

Configurable extensions declare a pydantic model under a fixed name
(`EngineSettings`, `ToolSettings`, `HookSettings`, database `Settings`, preference
sections) and optionally `fields` to choose the form widget of some attributes:

```python
class EngineSettings(BaseModel):
    model_id: int
    device: str | None = None

fields = {
    "model_id": {"default_field": True, "content": "default.basic.reference", "args": {"endpoint": "/models/"}},
}
```

From these, `SettingsContract` derives without hand-written code:

- `kwargs_key`: one descriptor per attribute — the widget (`default_field`,
  `content`, `args`) plus `type`, `required`, `nullable`, `default`, `title`,
  `description`. Attributes without `fields` get a default widget
  `default.basic.<text|textarea|integer|number|checkbox|select|password|list|json|reference|email|url>`
  implemented in `web/src/modules/fields/default/basic.ts`. `default_field: true`
  names a frontend function `"{extension}.{file}.{function}"`
  (`web/src/modules/fields/{extension}/{file}.ts`); `false` means `content` is HTML;
- validation: `validate(kwargs)` returns the model or raises `InvalidSettingsError`
  with one message per attribute (unknown keys are rejected).

The frontend builds every settings form from `kwargs_key` (see `web/AGENTS.md` §11.2).

### 5.3 Extension points

| Extension point | Where | Contract |
| --- | --- | --- |
| SQL database | `database/sql_db/<name>.py` | `name`, `messages = {"initialize", "disconnect"}`, optional `Settings`; `initialize(**settings) -> Engine`, `disconnect(engine, drop=False)` (`database/contracts.py`) |
| Vector database | `database/vector_db/<name>.py` | same metadata; `initialize`, `disconnect(drop)`, `tables()`, `create(model_name, rows)`, `delete(model_name, chunk_ids)`, `count(model_name, chunk_ids=None)`, `retrieve(model_name, top_k, vector, chunk_ids=None)`, `drop(model_name)`. One table per model with `chunk_id` + `vector` only; chunk content lives in SQL |
| Embedding engine | `embedding/engines/<name>.py` | `name`, `EngineSettings`, optional `fields`; `formats` when settings have `model_id`; `embed(texts, settings, model) -> list[list[float]]`; `vector_space(settings) -> str` when there is no `model_id`; `local` engines: see below |
| Cross-encoder engine | `cross_encoder/engines/<name>.py` | same as an embedding engine (`name`, `EngineSettings`, `fields`, `formats`); `rerank(query, documents, settings, model) -> list[float]`: one relevance score per document, in order, higher = more relevant. No vector space; `local` engines: see below |
| Inference engine | `inference/engines/<name>.py` | `name`, `EngineSettings`, optional `fields`/`formats`/`local`, and `resources(settings, model) -> {"cpu", "vram_mb", "ram_mb"}` for engines that are not local (held in the pool during each call); `chat(messages, tools, settings, model, emit) -> ChatResult` (§6.3) |
| Chunker | `chunker/extensions/<ext>.py` (`md.py` for `.md`) | `async def chunk(file, max_token) -> list[dict]`; each dict has `content`, `start_line`, `end_line` and optionally `start_row`, `end_row`, `token_count`, `meta` |
| Task kind | `tasks/{extension}/*.py` | functions decorated with `@task(...)` (§7) |
| Tool | `agents/tools/{extension}/<module>.py` | `tools = [...]` functions and/or classes; optional `ToolSettings` + `fields` (§6.1) |
| Hook | `agents/hook/{extension}/<module>.py` | `hooks = [...]`; each hook takes exactly `conversation_id`; optional `HookSettings` |
| Instruction | `agents/instruction/{full|sub}/{extension}/<name>.md` | markdown text; `full` = base system prompts, `sub` = fragments added after them |
| Skill | `agents/skill/{extension}/<name>/SKILL.md` (+ resource files) | front matter `name` (= folder name) and `description`, body = instructions |
| Agent preset | `agents/agent_preset/{extension}/<name>.json` | keys `name` (= file name), `description`, `tools`, `hooks`, `skills`, `sub_agents` (agent preset ids), `instruction_fulls`, `instruction_subs`; unknown keys rejected |
| Session preset | `agents/session_preset/{extension}/<name>.json` | `name` (= file name), `description`, `agents` (agent preset ids), `meta`, `master` (one of `agents`) |
| File processor | `file_processing.register_processor(...)` | a processing type with a task taking `file_id` (§7.4) |
| Frontend pages, fields, viewers | `web/src/modules/` | see `web/AGENTS.md` §11 |

Engines are grouped in **engine families** (`crud/engine.py`): one table row per
discovered engine and any number of **presets** (named settings) per engine. When
presets exist, **exactly one is the default** (a partial unique index forbids two;
the first preset becomes default; deleting the default promotes the oldest one;
unsetting the default without choosing another is a conflict). Settings with
`model_id` reference an `LLMModel`: the family checks it exists and that the engine
supports its selected format, then hands the resolved model to the engine.

**Local engines** run a model on this machine (`local = True`; the default is `False`,
an API called directly; the flag is stored in the `local` column of the engine tables
and shown on the engine page). Besides the family functions they define
`load(settings, model) -> instance`, `unload(instance)` and, optionally,
`load_key(settings, model)`: the settings that change what is loaded (without it, all
of them), so presets differing only by e.g. `batch_size` share one model, and
`placements(settings, model)`: where the model can live, best first, as `(settings
changes, memory taken)` pairs, e.g. `({"device": "cuda"}, {"vram_mb": 1648})` then
`({"device": "cpu"}, {"ram_mb": 1392})` (a device chosen in the preset is the only
place; without `placements` the engine declares no memory and nothing is accounted).
Their operations receive the loaded instance first: `embed(encoder, texts, settings,
model)`, `rerank(scorer, query, documents, settings, model)`, with `settings` as they
apply where the model was placed. A local engine without `load` and `unload` fails to
load like any broken extension.

`residency.py` owns the loaded models. `resolved.call("embed", texts)` (what
`embed_texts` / `rerank_scores` do) loads the model for that call and frees it right
after, even when the call fails; `with resolved.loaded():` is a lease that keeps it
loaded for every call inside the block, so a caller that knows its workload loads the
model once (the `files.embed` task wraps all the batches of a file in one). The first
lease loads; leases on the same engine and `load_key` share one instance, and calls on
a shared instance run one at a time. No engine decides alone, inside a call, to unload.
What happens when the last lease leaves, and how memory is shared, depends on the
`smart-memory` preference (§7.5): off, the model is freed right away and nothing is
accounted; on, it stays loaded, holding its memory in the pool, until that memory is
needed.

The shipped `sentence-transformers` embedding and cross-encoder engines are local. Their
`cache_optimization` setting (default off) runs the model in inference mode and clears
the Python and CUDA memory caches after every batch: slower, but memory use stays
close to the size of the model. Their `unload` moves the weights to the CPU first, which
frees the GPU copy even if something still references the model. The cross-encoder
family is separate from the embedding one (own tables and presets,
`/cross-encoder-engines`, `/cross-encoder-presets`); it only scores query/document
pairs. `sentence-transformers` loads `CrossEncoder` models (e.g.
`cross-encoder/ms-marco-MiniLM-L6-v2`); listwise rerankers with custom code such as
`jinaai/jina-reranker-v3.5` are not cross-encoders and need an engine of their own.

Python tool and hook code is only added on disk (never uploaded over HTTP). Through
the API, `default/` items are read-only and `custom/` items can be created, edited
and deleted (instructions, skills, presets) or configured (tool/hook settings).

## 6. Agents and inference

### 6.1 Tools and hooks (`agents/callables.py`, `agents/tools/`, `agents/hook/`)

An entry is a function, or a public method of a class listed in `tools` / `hooks`.
Its docstring (with an `Args:` section) and type hints become the JSON schema shown
to the LLM (`self` is never shown). A class is instantiated once per agent run with:

- `settings`: the module settings saved in `toolsettings` / `hooksettings`
  (edited through `/tools/settings/{file_path}`), if `__init__` takes `settings`;
- the session `meta` values matching its other `__init__` parameters (all of them if
  it accepts `**kwargs`). Missing required values raise `MissingMetaError`.

A tool returns text, a JSON-serializable value, or
`inference.ToolOutput(content, meta)` to attach `meta` to the stored tool-response
message (for the interface only). Raising `AppError` gives the LLM its message and
marks the call as failed.

Names shown to the LLM: a tool keeps its plain name; when two tools of one agent
share a name, the one from `default/` (else the first) keeps it and the others are
shown under their id. Built-in tools: `load_skill` / `read_skill_file` for agents
with skills, `delegate_to_agent` for agents with sub-agents.

Hooks run, in order, before every call to the LLM, with the conversation id; they
change the conversation through the CRUD (inject context, compress history…). A
failing hook ends the turn with an error message.

### 6.2 Sessions, agents, presets

- A **session** groups agents sharing a `meta` dict (values read by tools); exactly
  one agent is the **master** (it receives the user's messages, `POST
  /sessions/{id}/chat`).
- An **agent** has instructions (`instruction_fulls`, `instruction_subs`, free
  `instructions`), `tools`, `hooks`, `skills`, sub-agents (`agenthierarchy`, same
  session, no cycle) and `meta`. Its inference configuration lives in `meta`: either
  `preset_inference_engine_id`, or `inference_engine_id` + `inference_settings`
  (validated against the engine; an agent without it gets the default preset; with
  no inference preset at all, creation fails with `no_inference_preset`).
- Agents and sessions can be created from presets; an agent preset creates (or
  reuses, within the session) the sub-agents it lists. Agents referencing missing
  items are listed with `valid: false` and one message per key.
- System prompt = full instructions + sub instructions + own text (blank lines
  between) + the list of skills.

### 6.3 The agentic loop (`inference/__init__.py`)

A conversation is **runnable** when its last message is from the user, an error
(retry) or an unfinished tool turn. `agentic_loop(conversation_id, emit, retry=3,
max_iter=20)` (one run per conversation at a time, `conversation_busy` otherwise):

1. build the agent runtime (system prompt, tools, hooks) and resolve its engine;
2. for each step: run pending tool calls if any; else run the hooks, read the
   conversation, call the engine (`status: generating`), retrying retryable
   `EngineError`s with exponential backoff (`status: retrying`, delay ≤ 8 s), holding
   the engine's declared `resources` from the shared pool when it is not a local engine
   (`status: waiting_resources`);
3. tool calls → store a `tool-calling` message, run each tool, store
   `tool-response` messages (`meta.status` ok/error), continue;
4. an answer → store an `assistant` message and finish (`done: completed`);
5. any failure (engine, hook, too many steps, missing configuration) → store an
   `error` message (`meta.code`) and finish (`done: error`). Error messages are
   never sent to the LLM.

Message roles: `system`, `user`, `assistant`, `tool-calling`, `tool-response`,
`error`. Engines receive `ChatMessage` objects (OpenAI-like roles) and an `Emitter`
(`token`, `reasoning`, `event`, `stopped`); they return
`ChatResult(content, reasoning, tool_calls, usage, model, stopped)` and raise
`EngineError(message, code, retryable, details)`. When `emit.stopped` becomes true
they stop and return what they have (`stopped=True`).

**Delegation**: `delegate_to_agent(agent, task)` runs the sub-agent in a new
conversation ("Task from {parent}"), relays its activity as `delegation` events and
returns its final answer; the tool response's `meta.delegation` holds `agent_id`,
`agent` and `conversation_id`.

**Streaming** — `WS /ws/conversations/{id}`: the server sends `conversation` on
connection, then `message`, `token`, `reasoning`, `tool_start`, `status`,
`delegation`, `done` and `error` events; clients send `{"type": "message",
"content"}`, `{"type": "run"}` or `{"type": "stop"}`. The same run is available
without streaming (`POST /conversations/{id}/run`, `/stop`). `rewind` deletes the
messages after one (edit and regenerate).

## 7. Background tasks (`tasks/`)

### 7.1 Declaring a task

```python
from lazy_bird.tasks import TaskContext, task

@task("files.reindex", title="Reindex {folder}", resources={"cpu": 1})
def reindex(ctx: TaskContext, folder: str) -> dict:
    done = ctx.state.get("done", 0)                 # resume where the last checkpoint stopped
    items = list_items(folder)
    for index in range(done, len(items)):
        handle(items[index])
        ctx.checkpoint(progress=(index + 1) / len(items), state={"done": index + 1})
    return {"count": len(items)}                    # JSON-serializable result

reindex.submit(folder="notes", priority=1)          # -> TaskOut
```

- parameters are keyword arguments, JSON-serializable;
- `resources` (dict, or function of the parameters): `cpu` slots, `vram_mb`, `ram_mb`;
- `engines` (function of the parameters returning resolved engines): the local models the
  task uses (`files.embed` declares its preset's engine). Their memory is reserved before
  the task starts and is not part of `resources` (§7.5);
- `ctx.checkpoint(progress, message, state)` is the **only** place where pause,
  cancel and shutdown stop a task; resuming runs the function again with
  `ctx.state` = last saved state. `ctx.report(progress, message)` only reports;
- `submit(..., dedupe_key=…)` returns the active task with the same key instead of
  queueing a duplicate; `run_at` schedules it; `priority` orders it: **the lower the
  number, the sooner it runs** (default 5, background work; search is 1 and inference
  2 where they take part; 0 means "run now" and only comes from the user, the program
  never creates it; the periodic file scan is 10);
- failures are retried up to the kind's `retries` (typed permanent failures are not).

Shipped kinds: `files.chunk`, `files.embed`, `files.scan` (periodic, every
`files.scan_every_minutes`), `models.download`, `models.import` (uploaded models).

### 7.2 Scheduling

Statuses: `queued`, `running`, `paused`, `completed`, `failed`, `cancelled`. Queued
tasks whose `run_at` has come run in order: running first, then priority (lowest
number first), then position (manual order), then age. A task starts when a worker is free
(`tasks.workers`) and its resources fit the pool. A task that does not fit **blocks
every later task needing one of the missing resources** (a big GPU job is not
starved by small ones) while tasks needing other resources still start. Capacities
are detected at startup and overridden by `tasks.resources`. Local inference holds
resources from the same pool. Pausing or cancelling a running task sets `control`,
applied at its next checkpoint; queued/paused tasks change immediately. Moving a
task places it before/after another and gives it that task's priority. At shutdown,
running tasks go back to the queue. Only the most recent finished tasks are kept.
With `smart-memory` off none of the resource rules above applies: only `tasks.workers`
limits what runs (§7.5).

### 7.3 Live control

`WS /ws/tasks` sends `{"type": "snapshot", "tasks", "resources", "kinds"}`, then
`task`, `task_deleted`, `resources`, `waiting` (why queued tasks wait), `reordered`,
`task_unresponsive` (`task_id` asked to yield that did not stop in time, §7.5)
and `file` (`file_id` whose processing changed) events. Commands:
`{"action": "pause"|"resume"|"cancel"|"retry"|"delete", "task_id", "request_id"}`,
`{"action": "move", "task_id", "before_id"|"after_id"}`,
`{"action": "update", "task_id", "priority"?, "run_at"?}`, answered by `ack` or
`error` with the same `request_id`. REST mirrors every command under `/tasks/`.

### 7.4 File processing states (`crud/file_processing.py`)

Each file has one row per `(processor, target)`: `chunking` (target `""`) and
`embedding` (target = model / vector space name). States and allowed transitions:

| state | meaning | → |
| --- | --- | --- |
| `pending` | wanted; queued once its dependency is up to date (`error` tells why not yet) | queued, running, paused, unsupported |
| `queued` / `running` / `paused` | mirror the task computing it (`task_id`) | done, failed, cancelled, outdated, unsupported… |
| `done` | computed from the current content (`content_hash` = file hash) | outdated, pending |
| `failed` | last run failed (`error`) | queued, outdated, pending |
| `cancelled` | cancelled by the user; rerun on request or content change | queued, outdated, pending |
| `outdated` | computed from older content, or its inputs were replaced | pending |
| `unsupported` | cannot be computed (no chunker for the type) | pending |

Any other move is a bug (`InvalidProcessingTransitionError`). Tasks never write
states: `on_task_change` maps task status changes onto rows. Triggers:

- upload, edit, or a change detected by the scan (content hash differs) → results
  from the old content become `outdated`, then `ensure()` queues what is wanted;
- new chunks → embeddings of the old chunks are deleted and become `outdated`;
- a new default embedding preset → the automatic embedding restarts with it: every file
  gets that model's embedding, even if another model already embedded it (vectors of
  different models cannot be compared; each model keeps its own table, and search only
  reads the table of the model it embeds the query with). Work in progress for the
  previous model is cancelled and marked `outdated` (it is computed again if that model
  becomes the default again); embeddings of other models do not count in the file's
  `state`, they only appear in its `processing` list unless they are being computed;
- switching the vector database → every embedding is `outdated` and redone;
- dropping a model's vector table → its rows are forgotten (and redone when it is
  the default preset's model and automatic processing is on);
- `POST /files/{id}/process` queues what is missing; `POST /files/{id}/processing`
  recomputes one processing.

With `auto-embedding.enable` (default), every file is chunked and embedded with the
default preset automatically. The API summarizes rows into one file `state`:
`missing`, `processing`, `error`, `outdated`, `pending`, `unsupported`, `ready`, `new`.

### 7.5 Smart memory (`residency.py`, `tasks/memory.py`, `tasks/scheduler.py`)

The `smart-memory` preference section decides how much the machine is supervised:

- `enable: false` — **unsupervised**: tasks start whenever a worker is free, models are
  loaded without any check and freed when their last lease leaves, even at the risk of
  running out of memory;
- `enable: true` (default) — RAM and GPU memory are watched. The pool caps what is free
  by what the operating system reports (`tasks/memory.system_free`: `psutil` for RAM,
  `nvidia-smi` for GPU memory, so no CUDA context is created in the server), which
  counts memory used by other programs too. A reading that is unavailable means "no
  limit besides the pool".
- `fallback: wait | cpu` — a model that does not fit in GPU memory right now either
  waits for it (`wait`, default) or is loaded in RAM instead (`cpu`). It only applies to
  engines whose `device` is left empty; a device chosen in the preset is respected.
- `interrupt_timeout_seconds` (T_max, default 60) — how long a task asked to yield may
  take to reach a checkpoint.

With it on, a loaded model holds its memory in the pool (`engine:*` holders). A model
nobody uses stays loaded until its memory is needed: it is then evicted, least recently
used first, and only if it holds the missing resource. A task that declares `engines`
reserves their models (in the best place that fits, the CPU being the fallback) before
it starts, and the memory they take is counted once however many tasks share them.
Search and other direct calls ask for a model the same way and wait for it (up to
10 minutes, then `resources_busy`).

When a request does not fit, the less urgent work gives way (`priority.py`: the lower the
number the more urgent; only strictly less urgent running tasks are asked):

1. idle models are evicted first, at no cost to anyone;
2. otherwise the **fewest** running tasks whose release covers what is missing are asked to
   yield (among equal sets, the least urgent ones): they stop at their next checkpoint,
   go back to the queue (the interruption does not count as an attempt) and resume from
   their saved state once the urgent work is done. What a task releases is its own
   resources plus the models only it uses;
3. a task that has not stopped after `interrupt_timeout_seconds` is reported with a
   `task_unresponsive` event and no longer counted on: the urgent request keeps waiting.
   Tasks run in threads, so they cannot be killed; forcing them out needs processes
   (planned: an engine host process, and isolated tasks).

A model that cannot fit in the machine even if everything else gave way is refused with
`InsufficientResourcesError` (code `insufficient_memory`, 422): "Cannot process with
'<model>': use a smaller model. Required memory: N MB, available memory: M MB." (M is the
most the machine could provide: its capacity, or less when other programs hold part of
it). It is raised when a task is submitted, when a task is about to start, and for direct
calls such as search. If the model would fit on the CPU, the message says to set the
fallback to `cpu`.

## 8. Files, models, search, preferences

- **Files**: uploads go to `storages/uploads/{dir}/`; a name already taken in the
  folder gets a numbered suffix (`notes (1).md`). Folders can be created, renamed,
  moved and deleted; text content can be read and edited (`not_text` for binary).
- **Models** (`llmmodel`): the Hugging Face cache (`~/.cache/huggingface/hub`) is the
  source of truth. Downloads (`models.download`, optionally only some weight files,
  e.g. one GGUF quantization) and uploads are tasks. An upload works from any
  browser (Docker, remote server): each file is streamed as the raw body of
  `PUT /models/uploads/{name}/files/{path}` into a staging folder next to the cache
  (`.lazy_bird_uploads/<name>/`), then `POST /models/uploads/{name}` queues
  `models.import`, which moves the files into the cache as `models--local--<name>/`
  (blobs/snapshots/refs) and removes the staging folder; `DELETE
  /models/uploads/{name}` discards an abandoned upload. A model
  records its weight `formats` (safetensors, gguf, onnx, openvino, bin, pth, ckpt, h5, msgpack — `tools/model_extraction.FORMATS`), the files
  of each format, the `selected_format` / `selected_file` and context lengths; GGUF
  metadata is read without extra dependencies (`tools/gguf.py`). Engines declare the
  formats they load.
- **Search**: `POST /search/` embeds the query with a preset (default one when
  omitted) and returns the nearest chunks of that model's table, optionally limited
  to some files. Two modes: *embedding only* (`rerank: false`, the default) returns
  the `top_k` nearest chunks; *reranking* (`rerank: true`) retrieves `top_n`
  candidates (default 50), scores each against the query with a cross-encoder preset
  (`cross_encoder_preset_id`, default preset when omitted) and returns the `top_k`
  best, ordered by `score` (results keep their embedding `distance`). `top_n` is the
  candidate pool, `top_k` the final count, and `top_n > top_k` is required: `422
  invalid_request` with `details.fields.top_n` at the API, `invalid_top_n` from
  `crud.search.search`. The cross-encoder preset is resolved before the embedding
  model runs, so a missing preset fails fast.
- **Preferences** (`preference.yaml`, `GET/PATCH /preferences/`, form at
  `/preferences/form`): `auto-embedding.enable`, `chunking.max_tokens` (chunk budget,
  independent of models), `files.scan_every_minutes` (0 = startup only),
  `tasks.workers` (restart required), `tasks.resources` (capacity overrides) and the
  `smart-memory` section (`enable`, `fallback`, `interrupt_timeout_seconds`, §7.5).
- **API keys** (`apikey`): secrets for extensions, never returned by the API. The
  `HuggingFace` key logs in to the Hub (again when replaced, out when deleted).
- **Logs**: loguru to the console and `logs.txt` (in the server's working directory); `/logs/` searches entries (BM25 or
  regex, levels, time range), `/logs/trace` rebuilds call trees of traced functions.

## 9. Data model and schema changes

Tables (see the live diagram at `/schemas`):

| table | content | relations |
| --- | --- | --- |
| `file` | path, name, extension, size, `content_hash`, `modified_at`, `missing` | → `chunk`, `fileprocessing` |
| `chunk` | content, line/row ranges, `token_count`, `meta`, position | `file_id` |
| `fileprocessing` | processor, target, state, `content_hash`, error | `file_id`, `task_id` |
| `task` | kind, title, params, status, control, priority (lowest number first), position, `run_at`, resources, progress, state, result, error, attempts, `dedupe_key` | |
| `llmmodel` | name, `hf_path`, `local_path`, source, formats, files, selections, dimensions, context | |
| `embeddingengine`, `crossencoderengine`, `inferenceengine` | discovered engines: name, file, formats, `local`, `kwargs_key` | → presets |
| `presetembedding`, `presetcrossencoder`, `presetinference` | name, kwargs, `default` (one per table) | engine id |
| `toolsettings`, `hooksettings` | saved settings per module file | |
| `session` | title, meta | → `agent` |
| `agent` | name, description, instructions, lists of tools/hooks/skills/instructions, master, preset, meta | `session_id`, `agenthierarchy` (parent/child) |
| `conversation` | title, timestamps | `agent_id` → `message` |
| `message` | role, content (text), meta | `conversation_id` |
| `apikey` | name, key | |

Vectors are not in SQL: each vector table (one per model) stores `chunk_id` +
`vector`. Timestamps are stored in UTC; the API sends them with their offset.

**Changing the schema**: edit the model, generate a revision from `src/lazy_bird/`
(`alembic revision --autogenerate`), review `upgrade()`/`downgrade()` so existing
data is kept (use a single `sa.table()` per table in data migrations; SQLite needs
`render_as_batch`), and test it on a populated database (`tests/test_migrations.py`
checks that models match the migrated schema and that downgrade/upgrade works).

**Reset procedures** (when data cannot be converted):

- *Vectors* (changing the vector layout or recovering a broken vector store):
  delete the model tables from the Databases page (or `DELETE
  /databases/vector/tables/{model}`), or disconnect the vector database with
  "delete its data"; files are embedded again from their chunks (automatic
  processing on, or "Process" on the Files page).
- *Chunks* (changing what chunkers produce): `POST /files/{id}/processing` with
  `chunking`, or re-upload; embeddings follow automatically.
- *Uploads*: files live in `src/lazy_bird/storages/uploads/`. Installs created before
  this folder existed stored them directly in `src/lazy_bird/storages/`: move those
  folders into `uploads/` and update `file.path`, or delete and upload them again.
- *Everything*: stop the server, delete `src/lazy_bird/database/storage/` (SQLite
  database and LanceDB vectors) and `storages/uploads/`, then start the server (it
  creates and migrates a new database).

## 10. API surface

Routers (`api/endpoints/`): `files`, `chunks`, `search`, `models` (+ uploads, hub
status, login, files), `embedding-engines`/`embedding-presets`, `cross-encoder-engines`/`cross-encoder-presets`, `inference-engines`/
`inference-presets` (+ `/inference/complete`), `tasks` (+ `/ws/tasks`), `databases`,
`api-keys`, `preferences`, `logs`, `extensions`, `tools`, `hooks`, `skills`,
`instructions`, `agent-presets`, `session-presets`, `sessions`, `agents`,
`conversations` (+ `/ws/conversations/{id}`), `messages`. Every feature is reachable
from the web interface; when you add an endpoint, add its screen and update
`web/AGENTS.md` §13. `tests/test_api_contract.py` calls every route of the OpenAPI
schema with unknown ids / invalid bodies and checks the uniform error format.

## 11. Tests

- Test **behavior** (what an API call, a function or a task does), never structure
  (table shapes, imports, attribute lists). Every new implementation and every bug
  fix comes with tests.
- The suite never touches the developer's database, storage, model cache or network.
  Fixtures (`tests/conftest.py`):
  - `migrated_database` — a copy of a session-wide migrated SQLite template, with
    vectors in a temporary LanceDB folder; `crud_database` adds no auto-processing;
  - `client` — `TestClient` without scheduler start, Hugging Face login or cache sync;
  - `isolated_hf_cache` (autouse) — every test gets an empty temporary Hugging Face cache;
  - `storage_root`, `upload_file_factory`, `model_cache` (temporary HF cache);
  - `fake_embedding`, `fake_local_embedding` (a local engine recording its `loads` / `unloads`, with `gpu_mb` / `cpu_mb` placements), `fake_inference` (scriptable `ChatResult`s, `.calls`) ;
  - `running_scheduler`, `wait_until`, `process_inline`;
  - autouse: `isolated_scheduler`, `isolated_residency`, `isolated_preferences` (default preferences), `unknown_system_memory`.
- Tests must be deterministic; never weaken or skip a failing test to get green.
- Frontend tests: `cd web && npm test` (see `web/AGENTS.md` §17).

## 12. Completion checklist

- [ ] The work started from a committed state; the step has one clear intention.
- [ ] Behavior is covered by tests; backend (`uv run pytest -q`) and, when touched,
      frontend (`npm test`, `npm run build`, `npm run lint`) are green.
- [ ] No route can return a traceback; errors use the typed format.
- [ ] Schema changes have a migration or a documented reset procedure.
- [ ] New features are reachable from the interface.
- [ ] This file and `web/AGENTS.md` describe the code as it is now.
- [ ] Decisions that were not specified were validated by the developer before the commit.
- [ ] Nothing was pushed; no secret was committed.
