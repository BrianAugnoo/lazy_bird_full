/**
 * Types of the backend payloads (see the OpenAPI schema at `/docs` of the backend).
 * Keep them in sync with `lazy_bird/src/lazy_bird/schemas/`.
 */
import type { KwargsKey } from '@/core/fields/types';

/** Uniform backend error body: `{"error": ApiErrorBody}`. */
export interface ApiErrorBody {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

// ------------------------------------------------------------------ health
export interface HealthResponse {
  ready: boolean;
  version: string;
  database_revision: string | null;
  /** Why the server could not start. */
  error: ApiErrorBody | null;
}

// ---------------------------------------------------------------- api keys
export interface APIKeyOut {
  name: string;
}

// ------------------------------------------------------------------ models
export interface LLMModel {
  id: number;
  name: string;
  hf_path: string;
  local_path: string;
  revision: string | null;
  source: 'huggingface' | 'local' | string;
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

export interface HubStatus {
  authenticated: boolean;
  user: string | null;
  error: string | null;
}

// ------------------------------------------------------------------- tasks
export type TaskStatus = 'queued' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';

export interface Task {
  id: number;
  kind: string;
  title: string;
  params: Record<string, unknown>;
  status: TaskStatus;
  /** A pause or cancel asked while running, applied at the next checkpoint. */
  control: 'pause' | 'cancel' | null;
  priority: number;
  position: number;
  run_at: string | null;
  resources: Record<string, number>;
  progress: number | null;
  message: string | null;
  result: unknown;
  error: ApiErrorBody | null;
  attempts: number;
  max_attempts: number;
  dedupe_key: string | null;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
  /** Resources a queued task waits for. */
  waiting_for: string[];
}

export interface TaskKind {
  kind: string;
  title: string;
  description: string;
  priority: number;
  retries: number;
}

/** Capacity and use of each resource (`cpu`, `vram_mb`, ...); `holders` maps a task or run to what it holds. */
export interface ResourceSnapshot {
  capacity: Record<string, number>;
  used: Record<string, number>;
  holders: Record<string, Record<string, number>>;
}

// ----------------------------------------------------- engines and presets
export type EngineKind = 'embedding' | 'cross_encoder' | 'inference';

export interface EngineOut {
  id: number;
  name: string;
  file_path: string;
  formats: string[];
  /** Settings form descriptors, see `core/fields/types.ts`. */
  kwargs_key: KwargsKey;
  available: boolean;
}

export interface PresetOut {
  id: number;
  name: string;
  /** Present on embedding presets. */
  embedding_engine_id?: number;
  /** Present on cross-encoder presets. */
  cross_encoder_engine_id?: number;
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

export interface CompletionOut {
  content: string;
  reasoning: string | null;
  model: string | null;
  usage: Record<string, unknown> | null;
}

// ------------------------------------------------------------------- files
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
  error: ApiErrorBody | null;
  updated_at: string;
}

/** Summary of `processing` for display. */
export type FileState = 'missing' | 'processing' | 'error' | 'outdated' | 'pending' | 'unsupported' | 'ready' | 'new';

export interface FileItem {
  id: number;
  name: string;
  size: number;
  extension: string;
  /** Absolute path on the server. */
  path: string;
  /** Path inside the storage, e.g. `notes/a.md`. */
  relative_path: string;
  /** Folder inside the storage, `''` at the root. */
  directory: string;
  content_hash: string | null;
  missing: boolean;
  chunk_count: number;
  state: FileState;
  processing: FileProcessing[];
}

export interface FilePatchIn {
  name?: string;
  dir?: string;
}

// ------------------------------------------------------------ preferences
export type Preferences = Record<string, Record<string, unknown>>;

export interface PreferencesForm {
  [section: string]: { title: string; kwargs_key: KwargsKey };
}

export interface PreferencesUpdateOut {
  preferences: Preferences;
  restart_required: string[];
}

// ------------------------------------------------------------------ search
export interface SearchPayload {
  query: string;
  top_k?: number;
  preset_id?: number | null;
  file_ids?: number[] | null;
  /** Rerank the embedding candidates with a cross-encoder. */
  rerank?: boolean;
  /** Cross-encoder preset used when reranking; the default preset when null. */
  cross_encoder_preset_id?: number | null;
  /** Embedding candidates handed to the reranker; must be greater than `top_k`. */
  top_n?: number;
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
  /** Cross-encoder score; only set when the search reranked. */
  score: number | null;
}

// --------------------------------------------------------------- databases
export interface DatabaseAdapter {
  kwargs_key: KwargsKey;
  settings: Record<string, unknown>;
  /** Notes shown when connecting (`initialize`) and disconnecting (`disconnect`). */
  messages: Record<string, string>;
  selected: boolean;
}

export interface DatabasesCatalog {
  available: { sql: Record<string, DatabaseAdapter>; vector: Record<string, DatabaseAdapter> };
  selected_sql: string;
  selected_vector: string;
}

export type DatabaseKind = 'sql' | 'vector';

export interface VectorTable {
  model_name: string;
  vectors: number;
}

// ----------------------------------------------- sessions, agents, chats
export interface Session {
  id: number;
  title: string;
  meta: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

/** How an agent answers: an inference preset, or an engine with its own settings. */
export interface AgentInferenceMeta {
  preset_inference_engine_id?: number | null;
  inference_engine_id?: number | null;
  inference_settings?: Record<string, unknown> | null;
  [key: string]: unknown;
}

export interface AgentFields {
  name: string;
  description: string | null;
  instructions: string | null;
  instruction_fulls: string[];
  instruction_subs: string[];
  skills: string[];
  tools: string[];
  hooks: string[];
  master: boolean;
  meta: AgentInferenceMeta | null;
  sub_agents_ids: number[];
}

export interface Agent extends AgentFields {
  id: number;
  session_id: number;
  /** Agent preset it was created from, `{extension}/{name}`. */
  preset: string | null;
  parent_agents_ids: number[];
  /** False when it references something missing (see `errors`). */
  valid: boolean;
  errors: Record<string, string>;
}

export interface AgentTool {
  id: string;
  name: string;
  description: string;
}

export type MessageRole = 'system' | 'user' | 'assistant' | 'tool-calling' | 'tool-response' | 'error';

export interface ToolCallMeta {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface Message {
  id: number;
  conversation_id: number;
  role: MessageRole;
  content: string | null;
  meta: Record<string, unknown> | null;
  created_at: string;
  updated_at: string;
}

export interface Conversation {
  id: number;
  agent_id: number;
  title: string;
  created_at: string;
  updated_at: string;
  /** The agent can answer now (last message from the user, an error or a tool turn). */
  runnable: boolean;
  running: boolean;
}

export interface ConversationDetail extends Conversation {
  messages: Message[];
}

export interface RunOut {
  reason: 'completed' | 'stopped' | 'error';
  messages: Message[];
}

// --------------------------------------------- extensions (tools, hooks, ...)
/** A tool or a hook found in an extension file. */
export interface CallableItem {
  id: string;
  name: string;
  description: string;
  extension: string;
  module: string;
  file_path: string;
  class_name: string | null;
  needs_settings: boolean;
  /** Session meta keys it reads. */
  meta_params: string[];
  required_meta: string[];
  accepts_any_meta: boolean;
  /** JSON schema of its arguments (tools only). */
  parameters: Record<string, unknown> | null;
}

export interface ModuleSettings {
  file_path: string;
  kwargs: Record<string, unknown>;
  kwargs_key: KwargsKey;
  available: boolean;
  valid: boolean;
  errors: Record<string, string>;
}

export type InstructionKind = 'full' | 'sub';

export interface Instruction {
  id: string;
  kind: InstructionKind | string;
  extension: string;
  name: string;
  editable: boolean;
  content: string | null;
}

export interface Skill {
  id: string;
  extension: string;
  name: string;
  description: string;
  files: string[];
  editable: boolean;
  content: string | null;
}

export interface AgentPresetData {
  name: string;
  description?: string;
  tools?: string[];
  hooks?: string[];
  skills?: string[];
  sub_agents?: string[];
  instruction_fulls?: string[];
  instruction_subs?: string[];
}

export interface SessionPresetData {
  name: string;
  description?: string;
  agents: string[];
  meta?: Record<string, unknown>;
  master: string;
}

/** An agent or session preset file. */
export interface ExtensionPreset<T> {
  id: string;
  extension: string;
  name: string;
  editable: boolean;
  valid: boolean;
  errors: Record<string, string>;
  data: T | null;
}

export interface LoadFailure {
  kind: string;
  source: string;
  error: string;
}

// -------------------------------------------------------------------- logs
export interface LogEntry {
  start_line: number;
  end_line: number;
  timestamp: string | null;
  level: string | null;
  location: string | null;
  message: string;
  payload: Record<string, unknown> | null;
  score: number | null;
}
