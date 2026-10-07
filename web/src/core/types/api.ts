/**
 * Types TypeScript stricts alignés sur la spécification endpoint.md
 */

// 1. Health & Application status (GET /)
export interface HealthResponse {
  success: boolean;
  message?: string;
  database_revision?: string | null;
  error?: string;
}

// 2. API Keys (/api-keys/)
export interface APIKeyIn {
  name: string;
  key: string;
}

export interface APIKeyOut {
  name: string;
}

// 3. LLM Models (/models/)
export interface LLMModel {
  id: number;
  name: string;
  hf_path: string;
  local_path: string;
  revision: string | null;
  source: 'huggingface' | 'local';
  dimension: number | null;
  max_context_length: number | null;
  selected_context: number | null;
  formats: string[];
  /** Weight files per format, relative to `local_path`. */
  files: Record<string, string[]>;
  selected_format: string | null;
  /** The weight file used when the format has alternatives (a GGUF quantization). */
  selected_file: string | null;
  available: boolean;
  size_mb: number | null;
}

export interface LLMModelUpdate {
  name?: string;
  selected_format?: string;
  selected_file?: string;
  selected_context?: number | null;
}

export interface HubFile {
  path: string;
  size: number;
  format: string | null;
}

// 3.1 Tasks (/tasks/, /ws/tasks)
export type TaskStatus = 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';

export interface Task {
  id: number;
  kind: string;
  title: string;
  params: Record<string, unknown>;
  status: TaskStatus;
  control: 'pause' | 'cancel' | null;
  priority: number;
  position: number;
  run_at: string | null;
  resources: Record<string, number>;
  progress: number | null;
  message: string | null;
  result: unknown;
  error: { code: string; message: string; details?: Record<string, unknown> } | null;
  attempts: number;
  max_attempts: number;
  dedupe_key: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  waiting_for: string[];
}

// 4. Engines and presets (/embedding-engines/, /embedding-presets/, /inference-engines/, /inference-presets/)
export type EngineKind = 'embedding' | 'inference';

export interface EngineOut {
  id: number;
  name: string;
  file_path: string;
  formats: string[];
  /** Settings form descriptors, see `core/fields/types.ts`. */
  kwargs_key: import('@/core/fields/types').KwargsKey;
  available: boolean;
}

export interface PresetOut {
  id: number;
  name: string;
  /** Present on embedding presets. */
  embedding_engine_id?: number;
  /** Present on inference presets. */
  inference_engine_id?: number;
  kwargs: Record<string, unknown>;
  default: boolean;
  valid: boolean;
  errors: Record<string, string>;
}

export interface PresetChanges {
  name?: string;
  engine_id?: number;
  kwargs?: Record<string, unknown>;
  default?: boolean;
}

// 5. Files (/files/ et /ws/upload-progress)
export type ProcessingState =
  | 'pending'
  | 'queued'
  | 'running'
  | 'paused'
  | 'done'
  | 'failed'
  | 'cancelled'
  | 'outdated'
  | 'unsupported';

/** One processing of a file: chunking, or embedding with one model (`target`). */
export interface FileProcessing {
  processor: string;
  target: string;
  state: ProcessingState;
  content_hash: string | null;
  task_id: number | null;
  error: { code: string; message: string } | null;
  updated_at: string;
}

/** Summary derived from `processing` for display. */
export type FileState = 'missing' | 'processing' | 'error' | 'outdated' | 'pending' | 'unsupported' | 'ready' | 'new';

export interface FileItem {
  id?: number;
  name: string;
  size: number;
  extension: string;
  path: string;
  content_hash?: string | null;
  missing?: boolean;
  chunk_count?: number;
  state?: FileState;
  processing?: FileProcessing[];
}

export interface DirectoryResponse {
  path: string;
}

export interface FilePatchIn {
  name?: string;
  dir?: string;
}

// 5.1 Preferences (/preferences/)
export interface PreferencesPayload {
  'auto-embedding': {
    enable: boolean;
  };
}

export interface FileProgressItem {
  id: number;
  name: string;
  state: FileState;
}

export interface UploadProgressPayload {
  files: FileProgressItem[];
}

// 6. Search (/search/)
export interface SearchPayload {
  query: string;
  top_k?: number;
  preset_id?: number;
  file_ids?: number[];
}

export interface Chunk {
  id: number;
  file_id: number;
  position: number;
  content: string;
  start_line: number;
  end_line: number;
  start_row: number | null;
  end_row: number | null;
  token_count: number | null;
  meta: Record<string, unknown>;
  created_at: string;
}

export interface SearchResult {
  chunk: Chunk;
  file_name: string;
  file_path: string;
  distance: number | null;
}

export interface VectorTable {
  model_name: string;
  vectors: number;
}

// 7. Databases (/databases/)
export interface DatabaseCatalogItem {
  settings_schema: any | null;
  messages: string[];
}

export interface DatabasesCatalogResponse {
  available: {
    sql: Record<string, DatabaseCatalogItem>;
    vector: Record<string, DatabaseCatalogItem>;
  };
  selected_sql: string;
  selected_vector: string;
}

export interface SelectedDatabaseOut {
  sql: string;
  vector: string;
}

export interface DatabaseSelectionIn {
  kind: 'sql' | 'vector';
  name: string;
  settings: Record<string, any>;
}

export interface DatabaseDisconnectIn {
  kind: 'sql' | 'vector';
  name: string;
  drop?: boolean;
}
