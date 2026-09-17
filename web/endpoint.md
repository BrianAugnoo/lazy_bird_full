# Lazy Bird API

Documentation for the frontend of Lazy Bird.

## General information

- Base URL in local development: `http://localhost:8000`
- The API returns JSON unless the endpoint is explicitly marked as WebSocket.
- No authentication header is currently required by these routes.
- During a startup failure, every route except `GET /` returns `503` with:

```json
{
  "success": false,
  "error": "..."
}
```

- FastAPI validation errors use status `422` and the usual `detail` array.

## Quick start

```js
const API_URL = "http://localhost:8000";

const response = await fetch(`${API_URL}/files/`);
if (!response.ok) throw new Error(`HTTP ${response.status}`);
const files = await response.json();
```

## Health and application routes

### `GET /`

Checks application and database startup status.

Successful response:

```json
{
  "success": true,
  "message": "Welcome to Lazy Bird!",
  "database_revision": "..."
}
```

When startup failed, the response is still `200`, with `success: false` and an `error` field.


## API keys

> The duplicated path segment is intentional in the current backend: use `/api-keys/api-keys`.

### `POST /api-keys/api-keys`

Creates an API key. The key is accepted by the backend but is not returned in the response.

Request JSON:

```json
{
  "name": "OpenAI",
  "key": "secret-value"
}
```

Response `200`:

```json
{ "name": "OpenAI" }
```

Duplicate names return `400` with `{ "detail": "..." }`.

### `GET /api-keys/api-keys`

Lists keys without exposing their secret values.

Response `200`: `[ { "name": "OpenAI" } ]`

### `GET /api-keys/api-keys/{name}`

Gets one key by name. Returns `404` if it does not exist.

## LLM models

### `GET /models/`

Lists registered LLM/embedding models.

### `POST /models/`

Registers and downloads a Hugging Face model. This can take time because the backend may download and inspect the model.

Request JSON:

```json
{ "hf_path": "sentence-transformers/all-MiniLM-L6-v2" }
```

Response fields:

```json
{
  "id": 1,
  "name": "all-MiniLM-L6-v2",
  "hf_path": "sentence-transformers/all-MiniLM-L6-v2",
  "dimension": 384,
  "formats": ["safetensors"],
  "selected_format": "safetensors",
  "local_path": "/path/to/model",
  "max_context_length": 512,
  "selected_context": null
}
```

### `GET /models/{id}`

Gets one model. An unknown ID currently returns `200` with JSON `null`.

### `PUT /models/{id}/format`

Selects the model format.

Request JSON:

```json
{ "selected_format": "safetensors" }
```

The response is the updated model, or `{ "success": false, "invalid_keys": ["id"] }` when the ID is invalid.

### `DELETE /models/destroy`

Deletes all registered models. Response:

```json
{ "message": "All llm models deleted." }
```

## Selected model

### `GET /selected-models/`

Returns the model used for document embedding:

```json
{ "llm_model_id": 1, "batch": 1 }
```

When none is selected, `llm_model_id` is `null`.

### `PUT /selected-models/`

Selects or replaces the active model.

Request JSON:

```json
{ "llm_model_id": 1, "batch": 1 }
```

`batch` defaults to `1`.

## Preferences

### `GET /preferences/`

Returns the preferences currently stored in `src/lazy_bird/preference.yaml`.
The response contains the complete YAML mapping:

```json
{
  "auto-embedding": {
    "enable": true
  }
}
```

### `PUT /preferences/`

Replaces the YAML preferences mapping. The endpoint reapplies the preferences
only when the new mapping is different from the current file contents.

Request JSON:

```json
{
  "auto-embedding": {
    "enable": false
  }
}
```

When `auto-embedding.enable` is `true`, applying the preferences scans the
database and queues pending files and completed files missing the selected
model embedding or the chunks for the selected vector database. Queuing is
asynchronous; the request does not wait for embeddings to finish.

## Embedding engines

### `GET /embedding-engines/`

Lists available configured embedding engines. Each item contains `id`, `name`, `file_path`, `formats`, `kwargs`, and `kwargs_keys`.

`kwargs_keys` describes the Python type and configuration of each supported keyword. A default value means the keyword is optional; `"required"` means it must be provided.

Example:

```json
{
  "device": ["str", null],
  "model_path": ["str", null],
  "temperature": ["float", null]
}
```

### `PUT /embedding-engines/{engine_id}`

Updates engine-specific keyword arguments.

Request JSON:

```json
{ "kwargs": { "device": "cpu" } }
```

Invalid IDs return `200` with `{ "success": false, "invalid_keys": ["engine_id"] }`.

### `GET /selected-embedding-engine/`

Returns the active engine:

```json
{
  "configured": true,
  "engine": {
    "id": 1,
    "name": "...",
    "file_path": "...",
    "formats": ["..."],
    "kwargs": {},
    "kwargs_keys": {
      "device": ["str", null],
      "model_path": ["str", null]
    }
  }
}
```

If none is configured, `engine` is `null` and `configured` is `false`.

### `PUT /selected-embedding-engine/`

Selects an embedding engine.

Request JSON:

```json
{ "embedding_engine_id": 1 }
```

## Files

### `POST /files/upload`

Uploads one or more files. Use `multipart/form-data`, with:

- query parameter `dir`: destination directory, for example `documents`;
- repeated form field `files`: one field per file.

Example:

```js
const form = new FormData();
form.append("files", fileInput.files[0]);
form.append("files", fileInput.files[1]);

const response = await fetch(`${API_URL}/files/upload?dir=documents`, {
  method: "POST",
  body: form,
});
```

Response `200` is an array of file objects:

```json
[
  {
    "id": 1,
    "name": "notes",
    "size": 2048,
    "extension": ".md",
    "path": "documents/notes.md",
    "status": "pending",
    "embedded_by": [],
    "vector_db": []
  }
]
```

`embedded_by` contains the IDs of the embedding models used for the file.
`vector_db` contains the names of the vector databases that contain chunks for
the file, not their database IDs.

If `auto-embedding.enable` is enabled, uploaded files are queued after being
persisted. If it is disabled, new files remain `pending` and are not queued
automatically.

### `POST /files/directory`

Creates an empty directory below the backend storage root. The `path` query
parameter may contain nested relative directories, but must not be absolute or
contain `..` path components.

Example:

```http
POST /files/directory?path=documents/archive
```

Response `200`:

```json
{
  "path": "/path/to/lazy_bird/storage/documents/archive"
}
```

Creating an already existing directory is successful and leaves its contents
unchanged. A path occupied by a file, or an invalid path, returns `400`.

### `PATCH /files/directory`

Moves a directory and all its contents to a new relative path. The `source`
and `destination` query parameters are required. File paths stored in the
database are updated as part of the operation.

```http
PATCH /files/directory?source=documents/archive&destination=archive/2026
```

Response `200`:

```json
{
  "path": "/path/to/lazy_bird/storage/archive/2026"
}
```

The destination must not already exist. Moving the storage root, moving a
directory inside itself, invalid paths, or a missing source returns an error.

### `DELETE /files/directory`

Deletes a directory recursively, including its files and subdirectories. File
records and their embedding metadata belonging to that directory are deleted
from the database as well.

```http
DELETE /files/directory?path=archive/2026
```

Response `200`:

```json
{
  "path": "/path/to/lazy_bird/storage/archive/2026"
}
```

The storage root cannot be deleted. A missing directory returns `404`; an
invalid path or a path that is not a directory returns `400`.

### `GET /files/`

Lists all stored files. Response is an array with the same file object shape as the upload response.

### `GET /files/{file_id}`

Gets one file. An unknown ID currently returns `200` with JSON `null`.

### `GET /files/{file_id}/full`

Returns the complete file by ID as a binary response. The response preserves
the stored bytes, sets the detected MIME type when available, and includes the
file name in `Content-Disposition`. Returns `404` when the file ID does not
exist.

### `GET /files/{file_id}/content`

Returns the UTF-8 text content of a file as `text/plain`. Returns `404` when the file ID does not exist.

### `PUT /files/{file_id}/content`

Replaces the UTF-8 text content of a file. Editing resets its processing status to `pending` because existing embeddings may no longer match.

Request JSON:

```json
{ "content": "Updated document text" }
```

Response `200` is the updated file object. Returns `404` when the file ID does not exist.

### `GET /files/{file_id}/download`

Downloads the stored file as a binary response. The `Content-Disposition` filename contains the original file name and extension. Returns `404` when the file ID does not exist.

### `PATCH /files/{file_id}`

Renames and/or moves a file. `name` is the base name without the extension; `dir` is a relative directory under the backend storage root. At least one field is required.

Request JSON:

```json
{ "name": "renamed-notes", "dir": "archive" }
```

Response `200` is the updated file object. Invalid paths or duplicate destinations return `400`; an unknown ID returns `404`.

### `POST /files/{file_id}/process`

Manually queues an existing file for processing. This endpoint works whether
automatic embedding is enabled or disabled. A file is queued only when it is
`pending`, or when it is `done` but lacks the embedding for the selected model
or the chunks for the selected vector database. A file already present in the
Huey queue, or a file that needs no processing, is not queued again.

Successful response is `202`:

```json
{ "file_id": 1, "task_id": "task-1" }
```

When no processing is required, or the file is already queued, the response is
also `202`:

```json
{ "file_id": 1, "queued": false }
```

Returns `404` when the file does not exist.

### Queue worker behavior

The backend starts one Huey consumer after successful application startup,
regardless of the `auto-embedding.enable` value. The consumer processes tasks
already stored in the queue, keeps consuming while tasks are available, and
also picks up tasks added while another file is being processed. Therefore,
manual processing remains useful when automatic embedding is disabled.

### `DELETE /files/`

Deletes selected files. The request body is a JSON array of file IDs.

```json
[1, 2]
```

Response:

```json
{ "message": "Files deleted successfully." }
```

### `DELETE /files/delete_all`

Deletes all stored files. Response:

```json
{ "message": "All files deleted successfully." }
```

## Search

### `POST /search/`

Performs semantic search against the vector database. A usable embedding/model configuration must be selected first.

Request JSON:

```json
{
  "query": "How are Markdown documents processed?",
  "top_k": 5
}
```

`query` must not be empty. `top_k` defaults to `5` and must be between `1` and `100`.

Response `200` is an array of matching chunks:

```json
[
  {
    "content": "...",
    "start_line": 10,
    "end_line": 18,
    "start_row": 0,
    "end_row": 42,
    "meta_data": {},
    "embedded_id": 7,
    "distance": 0.12
  }
]
```

## Databases

### `GET /vector-databases/`

Returns all vector databases registered in the `vectordatabase` table.

Response `200`:

```json
[
  { "id": 1, "name": "lancedb" },
  { "id": 2, "name": "another-vector-db" }
]
```

### `GET /vector-databases/{vector_database_id}`

Returns one vector database by its ID.

Response `200`:

```json
{ "id": 1, "name": "lancedb" }
```

An unknown ID returns `404` with `{ "detail": "Vector database not found" }`.

### `GET /databases/`

Returns available database adapters and the selected SQL/vector adapters. Adapter details are dynamic and depend on the installation:

```json
{
  "available": {},
  "selected_sql": "sqlite",
  "selected_vector": "lancedb"
}
```

### `GET /databases/selected_db`

Returns only the selected adapters:

```json
{ "sql": "sqlite", "vector": "lancedb" }
```

### `PUT /databases/select`

Switches the selected SQL or vector database.

Request JSON:

```json
{
  "kind": "vector",
  "name": "lancedb",
  "settings": {}
}
```

`kind` must be `sql` or `vector`. Database selection errors return `422` with `{ "detail": "..." }`.

### `PUT /databases/disconnect`

Disconnects a database adapter, optionally dropping its data.

Request JSON:

```json
{
  "kind": "vector",
  "name": "lancedb",
  "drop": false
}
```

Errors return `422`.

## Real-time routes

### `WebSocket /ws/upload-progress`

Opens a WebSocket and receives a status snapshot approximately every 500 ms:

```json
{
  "files": [
    {
      "id": 1,
      "name": "notes.md",
      "status": "processing",
      "detail": "processing"
    }
  ]
}
```

Possible display statuses are `queued`, `processing`, `finished`, and `failed`. The connection stays open until the client disconnects.

## Recommended frontend flows

### Configure search

1. `GET /models/`
2. `PUT /selected-models/` with the chosen `llm_model_id`.
3. `GET /embedding-engines/`
4. `PUT /selected-embedding-engine/` with the chosen `embedding_engine_id`.
5. `POST /search/` with `query` and optional `top_k`.

### Upload and process documents

1. `POST /files/upload?dir=documents` using `FormData`.
2. Track progress with `WebSocket /ws/upload-progress`, or poll `GET /files/`.
3. If automatic embedding is disabled, call `POST /files/{file_id}/process` for each file.
