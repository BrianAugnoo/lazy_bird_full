# Lazy Bird API

Documentation for the frontend of Lazy Bird.

## General information

- Base URL in local development: `http://localhost:8000`
- The API returns JSON unless the endpoint is explicitly marked as HTML or WebSocket.
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

### `GET /codebase`

Returns the HTML page showing Git/codebase documentation status. This route is not part of the JSON API.

### `GET /codebase/changes`

Returns the changes since the last documented commit:

```json
{
  "commits": [],
  "diff": "",
  "paths": []
}
```

Can return `503` with `{ "error": "..." }` if Git inspection fails.

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

## Embedding engines

### `GET /embedding-engines/`

Lists available configured embedding engines. Each item contains `id`, `name`, `file_path`, `formats`, and `kwargs`.

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
    "kwargs": {}
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
    "name": "notes",
    "size": 2048,
    "extension": ".md",
    "path": "documents/notes.md",
    "status": "pending"
  }
]
```

If automatic embedding is enabled, uploaded files are queued after being persisted.

### `GET /files/`

Lists all stored files. Response is an array with the same file object shape as the upload response.

### `GET /files/{file_id}`

Gets one file. An unknown ID currently returns `200` with JSON `null`.

### `POST /files/{file_id}/process`

Queues an existing file for processing.

Successful response is `202`:

```json
{ "file_id": 1, "task_id": "task-1" }
```

Returns `404` when the file does not exist.

### `DELETE /files/?ids=1&ids=2`

Deletes selected files. `ids` is a repeated query parameter, not a JSON body.

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

## Real-time and HTML routes

### `GET /upload_file` and `POST /upload_file`

HTML upload page for browser use. The POST expects form fields `directory` and repeated `files`, then renders HTML rather than returning JSON. The JSON frontend should use `POST /files/upload` instead.

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

### `GET /shemas`

Renders the database schema as an HTML page. The spelling `shemas` is part of the current API.

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
