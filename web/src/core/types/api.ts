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

// 2. API Keys (/api-keys/api-keys)
export interface APIKeyIn {
  name: string;
  key: string;
}

export interface APIKeyOut {
  name: string;
}

// 3. LLM Models (/models/ et /selected-models/)
export interface LLMModel {
  id: number;
  name: string;
  hf_path: string;
  dimension: number;
  formats: string[];
  selected_format: string;
  local_path: string;
  max_context_length: number;
  selected_context: number | null;
}

export interface CreateLLMModelIn {
  hf_path: string;
}

export interface SelectedFormatIn {
  selected_format: string;
}

export interface SelectedModel {
  llm_model_id: number | null;
  batch: number;
}

// 4. Embedding Engines (/embedding-engines/ et /selected-embedding-engine/)
export interface EmbeddingEngine {
  id: number;
  name: string;
  file_path: string;
  formats: string[];
  kwargs: Record<string, any>;
  kwargs_keys: Record<string, [type: string, defaultValue: any]>;
}

export interface SelectedEmbeddingEngine {
  configured: boolean;
  engine: EmbeddingEngine | null;
}

// 5. Files (/files/ et /ws/upload-progress)
export interface FileItem {
  id?: number;
  name: string;
  size: number;
  extension: string;
  path: string;
  status: string; // 'pending' | 'processing' | 'done' | 'format-error' | 'chunck-error' | 'incomplete-vectors'
  embedded_by?: number[];
  vector_db?: string[];
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

export interface FileProcessResponse {
  file_id: number;
  task_id: string;
}

export interface FileProgressItem {
  id: number;
  name: string;
  status: 'queued' | 'processing' | 'finished' | 'failed';
  detail: string;
}

export interface UploadProgressPayload {
  files: FileProgressItem[];
}

// 6. Search (/search/)
export interface SearchPayload {
  query: string;
  top_k?: number;
}

export interface SearchResultChunk {
  content: string;
  start_line: number;
  end_line: number;
  start_row?: number;
  end_row?: number;
  meta_data?: Record<string, any>;
  embedded_id: number;
  distance?: number;
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
