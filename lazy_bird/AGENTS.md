# Agent Guide - Lazy Bird

This document provides the minimum context required to work in this repository without exploring every file. It describes the current architecture, the responsibility of each layer, the mandatory engineering rules, and the Git workflow every agent must follow.

## Project purpose

Lazy Bird is a Python application built with FastAPI. It currently provides features to:

- manage API keys;
- register LLM models downloaded from Hugging Face;
- upload and reference files;
- split queued Markdown files into token-bounded chunks with source metadata;
- expose a JSON API and an HTML upload view;
- persist data in SQLite through SQLModel;
- evolve the database schema through Alembic.

## Main technology stack

- Python 3.12 or later
- FastAPI for the HTTP API
- Pydantic for input and output schemas
- SQLModel and SQLAlchemy for models and sessions
- SQLite for local persistence
- Alembic for database migrations
- Jinja2 for HTML views
- pytest for testing
- uv for dependency management and command execution

## Repository structure

```text
lazy_bird/
├── AGENT.md                    Architecture and mandatory agent instructions
├── pyproject.toml              Dependencies and pytest configuration
├── uv.lock                     Locked dependency versions
├── src/lazy_bird/
│   ├── main.py                 FastAPI application and main HTML routes
│   ├── api/
│   │   ├── __init__.py         Automatic router discovery and registration
│   │   └── endpoints/          JSON HTTP layer, organized by resource
│   ├── crud/                   Use cases and data-access operations
│   ├── models/                 SQLModel database tables
│   ├── schemas/                Pydantic input and output contracts
│   ├── database/               SQLite engines and session contexts
│   ├── migration/              Alembic environment and revisions
│   ├── chuncker/               Queued-file chunking orchestration and format extensions
│   ├── storages/               Physical file storage
│   ├── templates/              Jinja2 templates
│   └── tools/                  Hugging Face integrations and model extraction
└── tests/
    ├── conftest.py             Shared fixtures and isolated environments
    ├── crud/                   CRUD operation tests
    ├── endpoints/              HTTP endpoint tests
    ├── models/                 SQLModel table tests
    ├── schemas/                Pydantic contract tests
    ├── database/               SQLite and session tests
    ├── storages/               Local storage tests
    ├── tools/                  External integration tests
    └── views/                  HTML view tests
```

Generated `__pycache__` directories, SQLite runtime files, uploaded files, and temporary test data are not part of the logical architecture.

## Layer responsibilities

### `main.py`

`main.py` is responsible for:

- creating the FastAPI application;
- including the main JSON router;
- configuring Jinja2;
- defining general routes and routes strictly related to HTML views;
- triggering Hugging Face authentication during application startup.

Do not place business logic, SQL queries, or physical storage logic in `main.py`.

### `api/endpoints/`

The endpoint layer translates HTTP requests into application use cases. It is responsible for:

- reading and validating HTTP parameters;
- selecting the correct HTTP status code;
- converting domain errors into HTTP errors;
- declaring response models.

Endpoints must remain short. They must not write directly to SQLite, download models, or copy files.

Modules in this directory are imported automatically by `api/__init__.py` when they expose a `router` object.

Current main routes include:

```text
GET    /
GET    /upload_file
POST   /upload_file
GET    /shemas
GET    /models/
POST   /models/
GET    /models/{id}
DELETE /models/destroy
POST   /files/upload
GET    /files/
GET    /files/{file_id}
POST   /files/{file_id}/process
```

The API-key routes currently contain a duplicated prefix and are exposed under `/api-keys/api-keys`. Tests document this as a known issue. Do not silently change it as part of an unrelated task.

### `schemas/`

Pydantic schemas define the public contracts of the application:

- data accepted by the API;
- data returned to clients;
- validation independent from persistence.

A schema must not contain persistence or filesystem logic. Input schemas must expose only values that clients are allowed to control.

### `crud/`

The CRUD layer orchestrates data-related use cases:

- opening a database session;
- creating, reading, updating, or deleting records;
- calling storage services or external tools when required;
- converting SQLModel records into output schemas.

A CRUD function must represent one precise operation. If it mixes HTTP validation, persistence, storage, and complex transformation, extract those responsibilities into focused services.

### `models/`

Each `SQLModel` class declared with `table=True` represents a SQL table. Models describe persistence only: columns, keys, constraints, and relationships.

`models/__init__.py` imports model modules automatically so every table is registered in `SQLModel.metadata`. This import is required for Alembic autogeneration.

### `database/`

- `database/__init__.py` discovers adapters, validates configuration, and exposes active database operations.
- `database/sql_db/sqlite.py` builds the native SQLite engine and enables the required PRAGMAs.
- `db()` provides a session for the main database.
- `test_db()` is reserved for explicit test scenarios.

Database adapters are discovered dynamically from `database/sql_db/` and
`database/vector_db/`, but discovery is constrained by explicit contracts in
`database/contracts.py`. A SQL adapter exposes `name`, `initialize(**settings)`
returning an SQLAlchemy `Engine`, and `disconnect(engine, drop=False)`; a vector
adapter exposes `name`, connection lifecycle methods, and `create`, `delete`,
and `retrieve`. Their settings and the selected adapters are persisted
in the ignored runtime file `database/config.json`; `config.example.json` is
the versioned template and `database.initialize_database_config()` refreshes
this catalog at startup. The relational database remains responsible for
metadata and workflow state, while vector adapters own chunk content and
vectors. `Embedded` and `EmbeddedVectorDatabase` record which file/model index
is stored in which vector database. SQL adapter settings use a connection
`url`; a local adapter such as SQLite may derive a filesystem path internally,
but `path` is not part of the SQL adapter contract. SQL adapter switching
refuses databases
whose Alembic revision is not current.

Server startup calls `initialize_selected_sql_database()` before any service
uses persistence. This operation connects to the selected SQL adapter, applies
`alembic upgrade head`, and verifies the resulting revision. Authentication,
cache synchronization, embedding-engine registration, and vector database
initialization only run after this succeeds. When startup fails, FastAPI stays
available in degraded mode: `/` reports the error and every other route returns
HTTP 503 without invoking business logic.

### Explicit extension contracts

Dynamic module loading is intentional for adapters and embedding engines. It is
constrained by explicit contracts. Embedding engines provide `name`, `formats`,
`EngineSettings`, and `embed(chunks, ctx_size, batch_size, settings)`, returning
one vector per input. Chunk extensions provide an async
`Chunck(file, max_token)` function returning chunk dictionaries. API endpoint
modules provide a `router` object. Modules that do not satisfy their contract
must fail clearly during registration.

Alembic callers must use `database.alembic_config_for(url)`. This marks the URL
as programmatic and prevents the migration environment from silently selecting
another database.

Alembic owns the persistent database schema. Do not restore `SQLModel.metadata.create_all()` in normal application startup.

### `migration/`

Alembic is the single source of truth for persistent schema evolution.

When a SQL model changes:

1. update the model;
2. generate a revision with `--autogenerate`;
3. manually review both `upgrade()` and `downgrade()`;
4. test the migration on an empty database and, when relevant, a populated database;
5. apply the migration;
6. run the relevant tests and the complete test suite.

A migration must preserve existing data. Adding a non-nullable column requires a temporary default, a backfill, or a multi-step migration strategy.

### `storages/`

The storage layer manages physical files:

- validating and resolving paths;
- creating directories;
- copying bytes;
- calculating storage metadata.

It must not open SQL sessions or produce HTTP responses. Treat every client-provided path as untrusted, including POSIX and Windows path separators.

### `tools/`

This layer contains external or specialized integrations, especially Hugging Face operations. Network calls must be replaceable by test doubles. The standard test suite must never require real network access.

`tools/db_schema.py` applies Alembic migrations to an isolated temporary SQLite database and converts the resulting schema into Mermaid syntax. The `/shemas` endpoint renders that diagram through `templates/shemas.html`; it never modifies the persistent application database.

### `chuncker/`

The chunker processes one persisted `File` at a time from a Huey SQLite task. Its orchestrator:

- resolves the parent `File` and a format module under `chuncker/extensions/`;
- obtains the token budget from the selected embedding model, using `max_context_length` when `selected_context` is empty;
- leaves the file pending and queued when no embedding model is selected;
- manages the file states `processing`, `format-error`, `chunck-error`, and `incomplete-vectors`;
- delegates format-specific parsing to an async `Chunck(file, max_token)` function;
- persists returned chunk dictionaries through the chunk CRUD;
- records the processing result on the `File` status.

Format modules own parsing and token-boundary logic only. The Markdown implementation reads front matter, splits paragraphs, applies overlapping token windows, and records source line and row positions in each chunk.

### Queue preferences

`preference.yaml` contains runtime preferences for document processing. Its
current option is `auto-embedding.enable`, which defaults to `true`. When it
is enabled, every uploaded file is committed first and then enqueued for
embedding. The Huey consumer drains the SQLite queue until no pending task
remains. When it is disabled, uploads are persisted but are not enqueued
automatically; they can still be submitted through the manual processing
endpoint.

## Main application flows

### Standard API request

```text
HTTP client
  -> FastAPI endpoint
  -> Pydantic schema
  -> CRUD function or service
  -> SQLModel session
  -> SQLite
  -> output schema
  -> HTTP response
```

### File upload

```text
UploadFile
  -> endpoint
  -> storage service
  -> file metadata
  -> File CRUD operation
  -> file table
  -> FileOut
```

### LLM model registration

```text
LLMModelIn
  -> endpoint
  -> Hugging Face download
  -> metadata extraction
  -> LLMModel CRUD operation
  -> llmmodel table
  -> LLMModelOut
```

### Queued file chunking

```text
Huey SQLite task
  -> chunker orchestrator
  -> File extension module
  -> selected LLMModel.selected_context
  -> format-specific Chunck(file, max_token)
  -> embedding service
  -> selected vector database adapter
  -> Embedded/EmbeddedVectorDatabase metadata
  -> File status

Chunks are no longer stored in the relational `chunk` table. The migration
`9d3f1a7c2b44` removes that table; files must be reindexed through the await
file workflow after upgrading.
```

## Mandatory engineering principles

### SOLID

Every addition and revision must follow SOLID principles:

- **Single Responsibility Principle:** a class, function, method, or module must have only one reason to change.
- **Open/Closed Principle:** prefer extending a stable contract or adding an implementation instead of modifying several existing components.
- **Liskov Substitution Principle:** a replacement implementation must preserve the expected inputs, outputs, errors, and behavior of its contract.
- **Interface Segregation Principle:** use small and focused contracts; do not force consumers to depend on operations they do not need.
- **Dependency Inversion Principle:** business logic must depend on injectable contracts rather than directly depending on external services or hard-to-replace global state.

SOLID does not justify premature abstraction. Introduce an interface, class, or service only when it clarifies a boundary, enables a real replacement, or removes observed coupling.

### Single responsibility is non-negotiable

Every instance, function, method, class, and module must have one clearly expressible responsibility.

Before adding code, complete this sentence:

> This component is responsible for ...

If the sentence requires “and,” “then,” or multiple unrelated outcomes, split the component or move one responsibility to the correct layer.

Examples:

- an endpoint handles HTTP translation, not file copying;
- a storage service writes files, not database rows;
- a CRUD function persists records, not HTTP exceptions;
- a schema validates data, not external credentials;
- a migration changes schema or data in one controlled revision.

### Simplicity and readability

- Prefer the simplest solution that satisfies the requirement.
- Names must clearly communicate intent.
- Functions must remain short and keep a consistent level of abstraction.
- Avoid hidden side effects.
- Avoid adding dynamic imports without an architectural need.
- Use type annotations on public interfaces.
- Comments should explain why a non-obvious decision exists, not repeat the code.
- Never mix HTTP, business logic, SQL, and filesystem access in one function.
- Do not introduce generic helpers, base classes, managers, or services without a concrete need.
- Readability takes priority over cleverness and minor reductions in line count.
- Duplicating two clear lines can be preferable to introducing a confusing abstraction.

### Modularity

- A business resource should normally have one module per relevant layer: endpoint, schema, CRUD, model, and tests.
- Isolate external dependencies behind replaceable functions or services.
- Internal layers must not depend on FastAPI unless they require the HTTP protocol.
- SQL models must not automatically become public input schemas.
- SQLite-specific details must not propagate into endpoints.
- A module's public surface must remain small and intentional.

## Mandatory Git and branch policy

These rules apply before any code change. An agent must inspect the repository state with read-only commands such as:

```bash
git status --short
git branch --show-current
git log -1 --oneline
git rev-parse --abbrev-ref --symbolic-full-name @{upstream}
git status --branch --short
git remote -v
```

Do not assume that the current branch is clean, committed, or synchronized. Do not run `git pull`, reset, discard, stash, rebase, merge, or overwrite developer work without explicit authorization.

### Exercise engineering judgment

Agents must apply these Git rules with judgment instead of following them mechanically. The purpose of the branch policy is to protect developer work, maintain a clear history, and reduce risk—not to create unnecessary branches or process overhead.

Before creating or switching branches, determine:

- whether the current branch is `main` or already a secondary branch;
- whether the current secondary branch is appropriate for the requested scope;
- whether its commits and uncommitted changes belong to the same task;
- whether it is based on a sufficiently current base branch;
- whether reusing it is safer and clearer than creating another branch.

If the working environment is already on an appropriate secondary branch, do not create another secondary branch. Continue on the existing branch after verifying its state and scope. Do not create nested, duplicate, or disposable branches merely to satisfy a checklist.

If the current secondary branch belongs to a different task, contains unrelated changes, or has an unclear purpose, stop and ask the developer which branch should be used. Never move, copy, or merge unrelated work merely to make the branch layout appear compliant.

### Bug-fix exception

A bug fix may proceed when the branch is not fully updated only when the requested work is strictly limited to resolving that bug.

For this exception:

- inspect and document the exact bug before changing code;
- do not include unrelated developer changes;
- add or update a regression test that reproduces the bug;
- make the smallest safe correction;
- commit the bug fix separately;
- explain in the commit description the problem being resolved in the current `HEAD`;
- record the cause, the applied fix, the tests executed, and any remaining uncertainty.

Recommended bug-fix commit format:

```text
fix(scope): concise bug description

Agent: <agent name>
Problem in HEAD: <observable problem and affected behavior>
Cause: <verified root cause>
Fix: <small correction applied>
Tests: <commands and results>
Remaining risks: <none or explicit limitations>
```

The bug-fix commit must contain only files required for the bug and its regression tests. Never commit unrelated modifications already present in the working tree.

### Minor changes

A minor change is narrow, low-risk, reversible, and confined to one responsibility. Examples include:

- documentation corrections;
- a small test addition;
- a localized naming or typing correction;
- a small refactor with unchanged behavior;
- a narrowly scoped configuration adjustment.

An agent may remain on the main branch for a minor change when the branch policy above is satisfied and the developer's work is protected.

The agent must create a focused commit containing:

- the agent's name;
- a concise title;
- a detailed description of every applied change;
- the tests or verification performed;
- any known limitation.

Recommended minor-change commit format:

```text
chore(scope): concise change description

Agent: <agent name>
Changes:
- <first applied change>
- <second applied change>

Verification:
- <command and result>

Known limitations: <none or explicit limitations>
```

### Major changes

A major change includes any work that:

- affects several layers or resources;
- changes a public API contract;
- introduces a new feature or subsystem;
- changes persistence or requires significant migrations;
- has broad operational, security, or data-integrity risk;
- requires several independently testable steps.

Major work must be performed on an appropriate secondary branch. Create a new branch only when the current environment is on `main` or the existing secondary branch is not appropriate for the requested work. Use a descriptive branch name such as:

```text
feature/file-collections
refactor/storage-service
fix/file-migration-backfill
```

Keep major work incremental:

1. reuse the appropriate current secondary branch, or create one when necessary;
2. divide the work into small responsibilities;
3. add or update tests for each step;
4. create focused commits after stable steps;
5. run targeted tests after each step;
6. run the full suite before considering a merge.

### Push-before-merge policy

Every branch must be pushed to the repository's GitHub remote before it is merged. This repository already has a configured GitHub remote, currently named `origin`.

Before any merge, the agent must:

1. verify the intended remote with `git remote -v`;
2. verify the current branch and exact commit with `git branch --show-current` and `git rev-parse HEAD`;
3. push the complete working branch to GitHub;
4. configure its upstream when needed;
5. verify that the remote branch contains the exact commit intended for merge;
6. report the pushed branch name and commit in the handoff or merge summary.

Typical command for a new secondary branch:

```bash
git push -u origin <branch-name>
```

For an existing tracked branch, use a normal non-force push. Never force-push unless the developer explicitly requests it and the consequences have been reviewed.

If the push fails because of authentication, connectivity, permissions, remote rejection, or any other reason, the agent must not merge. Keep the commits on the current branch and ask the developer to complete or authorize the required GitHub operation.

The existence of a local branch or successful local tests is not sufficient evidence for merging. The corresponding GitHub branch must exist and contain the reviewed `HEAD`.

### Merge policy

An agent may merge a secondary branch into `main` only when all of the following are true:

- the implemented behavior matches the requested scope;
- the changes are stable and well understood;
- relevant automated tests pass;
- the complete test suite passes, except for explicitly documented pre-existing expected failures;
- migrations have been tested against the required database states;
- no unresolved uncertainty affects correctness, security, compatibility, or data integrity;
- the merge will not overwrite or include unrelated developer work.
- the complete working branch has been pushed to GitHub;
- the remote branch contains the exact reviewed `HEAD` intended for merge.

If any meaningful uncertainty remains, the agent must not merge. Keep the work on the secondary branch and ask the developer to perform the checks the agent cannot complete.

The handoff must state:

- the branch name;
- the GitHub remote branch and pushed commit;
- the commits created;
- what changed;
- which tests passed;
- which tests or manual checks remain;
- the exact uncertainty preventing a safe merge;
- how the developer can verify it.

Never describe a change as stable or safe without evidence.

### Commit safety

- Review `git status` and the exact staged diff before every commit.
- Stage explicit files; do not use broad staging when unrelated changes exist.
- Never commit secrets, `.env` values, generated databases, upload contents, caches, or unrelated developer changes.
- Do not rewrite, amend, squash, or force-push developer commits without explicit authorization.
- Do not delete branches or tags unless explicitly requested.
- A commit must represent one coherent responsibility.
- If a clean commit cannot be created without touching unrelated work, stop and ask the developer.

## Incremental change policy

Every change must be small, progressive, and verifiable:

1. understand the behavior and tests of the affected resource;
2. define one limited change;
3. add or adjust the closest test;
4. apply the smallest implementation change;
5. run the targeted tests;
6. run the full suite when a shared contract or cross-cutting layer changes;
7. leave unrelated refactoring for a separate change and commit.

Do not combine the following in one change or commit:

- a new feature and a general refactor;
- a migration and unrelated business changes;
- several independent resources;
- functional corrections and mass formatting;
- dependency upgrades and unrelated feature work.

A change must be independently reviewable, testable, and reversible whenever possible.

## Mandatory living documentation

`AGENT.md` is a living source of truth for the repository. Every agent must keep it synchronized with the actual project, including when the developer made a change but forgot to document it.

During every task, the agent must check whether the affected area introduces or reveals a material change to:

- the repository structure;
- layer responsibilities or architectural boundaries;
- application flows or public routes;
- dependencies, tools, or supported runtime versions;
- database ownership, models, or migration procedures;
- testing structure, fixtures, commands, or expected failures;
- Git, branch, commit, review, or release procedures;
- security, storage, external-service, or operational constraints;
- known defects, limitations, or required verification steps.

If any such information is missing, outdated, or incorrect, the agent must update `AGENT.md` as part of the same task, even when the developer did not explicitly request the documentation update.

This requirement also applies when the agent discovers an undocumented change that was previously made by the developer or another agent. The agent must document the verified current state instead of leaving `AGENT.md` stale.

Documentation updates must follow these rules:

- verify the information against the current code, configuration, migrations, tests, or Git state;
- describe stable architecture and working agreements, not temporary implementation details;
- keep the update limited to facts relevant to the discovered change;
- do not invent requirements, developer intent, guarantees, or future plans;
- do not remove an existing rule merely because the current code violates it;
- document known inconsistencies explicitly when they cannot be fixed within the current scope;
- include the `AGENT.md` update in the same focused commit as the change that made it necessary;
- mention the documentation update in the commit description and final handoff.

Before completing any task, the agent must explicitly ask:

> Does `AGENT.md` still accurately describe the repository after this work and after any relevant undocumented developer changes I observed?

If the answer is no, the task is not complete until the document is updated or a concrete blocker is reported.

## Testing rules

The test structure mirrors the application structure. One test file covers one resource or one module:

```text
tests/crud/api_key.py
tests/endpoints/file.py
tests/models/llm_model.py
tests/views/upload_file.py
```

Mandatory testing rules:

- each test verifies one precise behavior;
- tests must be deterministic;
- use a migrated temporary database, never the main database;
- use a temporary directory, never the main storage directory;
- replace downloads, authentication, and other external calls;
- test success, absence, validation, and important error paths;
- add a regression test before or with every bug fix;
- do not modify business code only to satisfy an incorrect assertion;
- use dependency injection when it materially improves isolation and modularity;
- do not silently remove, weaken, or mark a failing test as expected merely to obtain a green suite;
- document pre-existing expected failures and their causes.

Useful commands:

```bash
# Complete test suite
uv run pytest -q

# One layer
uv run pytest tests/crud -q

# One resource
uv run pytest tests/endpoints/file.py -q

# Alembic state and migrations
uv run alembic -c src/lazy_bird/alembic.ini current
uv run alembic -c src/lazy_bird/alembic.ini check
uv run alembic -c src/lazy_bird/alembic.ini upgrade head

# Local development server
uv run uvicorn lazy_bird.main:app --reload
```

## Completion checklist

Before declaring work complete, verify all applicable items:

- The branch was clean, committed, and confirmed current before feature work began.
- The change has one clearly expressible intention.
- Every function, method, class, and module retains a single responsibility.
- Endpoint, schema, business, persistence, and storage boundaries are respected.
- The code is simpler, or at least no more complex, than before.
- No unrelated behavior was changed.
- Errors are handled in the appropriate layer.
- Migrations preserve existing data.
- Targeted tests pass.
- The complete suite was executed when justified by the scope.
- Tests did not use real external services or production data.
- Known unrelated defects were not hidden or silently changed.
- The exact staged diff was reviewed before committing.
- The commit contains only the intended responsibility.
- Major work remains on a secondary branch unless every merge condition is satisfied.
- An appropriate existing secondary branch was reused instead of creating an unnecessary branch.
- Every branch intended for merge was pushed to GitHub and its remote `HEAD` was verified.
- Any uncertainty that could not be verified has been clearly handed back to the developer.
- `AGENT.md` accurately reflects every material repository change discovered during the task.

## Omniroute for test with LLM
A local OpenAI-compatible proxy (Omniroute) is available for manual and end-to-end LLM tests.
Its base URL, model name and API key live in the git-ignored file `lazy_bird/.env`
(`LAZY_BIRD_TEST_LLM_BASE_URL`, `LAZY_BIRD_TEST_LLM_MODEL`, `LAZY_BIRD_TEST_LLM_API_KEY`).
Never commit the key itself.