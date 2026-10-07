import { request } from '../client';
import type {
  APIKeyOut,
  DatabaseKind,
  DatabasesCatalog,
  HealthResponse,
  LoadFailure,
  LogEntry,
  Preferences,
  PreferencesForm,
  PreferencesUpdateOut,
  VectorTable,
} from '@/core/types/api';

const json = (body: unknown) => JSON.stringify(body);
const enc = encodeURIComponent;

export const health = () => request<HealthResponse>('/health');

export const apiKeys = {
  list: () => request<APIKeyOut[]>('/api-keys/'),
  create: (name: string, key: string) => request<APIKeyOut>('/api-keys/', { method: 'POST', body: json({ name, key }) }),
  update: (name: string, key: string) => request<APIKeyOut>(`/api-keys/${enc(name)}`, { method: 'PUT', body: json({ key }) }),
  remove: (name: string) => request<void>(`/api-keys/${enc(name)}`, { method: 'DELETE' }),
};

export const preferences = {
  get: () => request<Preferences>('/preferences/'),
  form: () => request<PreferencesForm>('/preferences/form'),
  /** Only the changed keys, `{section: {key: value}}`. */
  update: (changes: Preferences) => request<PreferencesUpdateOut>('/preferences/', { method: 'PATCH', body: json(changes) }),
};

export const databases = {
  catalog: () => request<DatabasesCatalog>('/databases/'),
  select: (kind: DatabaseKind, name: string, settings: Record<string, unknown>) =>
    request<unknown>('/databases/select', { method: 'PUT', body: json({ kind, name, settings }) }),
  disconnect: (kind: DatabaseKind, name: string, drop = false) =>
    request<unknown>('/databases/disconnect', { method: 'PUT', body: json({ kind, name, drop }) }),
  vectorTables: () => request<VectorTable[]>('/databases/vector/tables'),
  dropVectorTable: (modelName: string) => request<void>(`/databases/vector/tables/${modelName}`, { method: 'DELETE' }),
};

export const extensions = {
  failures: () => request<LoadFailure[]>('/extensions/failures'),
  reload: () => request<LoadFailure[]>('/extensions/reload', { method: 'POST' }),
};

export interface LogQuery {
  query?: string;
  mode?: 'bm25' | 'regex';
  levels?: string[];
  lastN?: number;
  since?: string;
  until?: string;
}

export const logs = {
  search: ({ query, mode = 'bm25', levels = [], lastN = 200, since, until }: LogQuery) => {
    const params = new URLSearchParams({ mode, last_n: String(lastN) });
    if (query) params.set('query', query);
    if (since) params.set('since', since);
    if (until) params.set('until', until);
    for (const level of levels) params.append('level', level);
    return request<LogEntry[]>(`/logs/?${params}`);
  },
  trace: (fn: string, module?: string, lastN = 5) => {
    const params = new URLSearchParams({ function: fn, last_n: String(lastN) });
    if (module) params.set('module', module);
    return request<Record<string, unknown>[]>(`/logs/trace?${params}`);
  },
  tracing: () => request<{ enabled: boolean }>('/logs/tracing'),
  setTracing: (enabled: boolean) => request<{ enabled: boolean }>('/logs/tracing', { method: 'PUT', body: json({ enabled }) }),
};
