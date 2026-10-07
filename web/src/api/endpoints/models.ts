import { request } from '../client';
import type { HubFile, HubStatus, LLMModel, LLMModelUpdate, Task } from '@/core/types/api';

export const models = {
  /** Optionally only models available in one of `formats`. */
  list: (formats: string[] = []) => {
    const query = formats.map((format) => `format=${encodeURIComponent(format)}`).join('&');
    return request<LLMModel[]>(`/models/${query ? `?${query}` : ''}`);
  },
  get: (id: number) => request<LLMModel>(`/models/${id}`),
  /** Queue a Hugging Face download; `files` limits the weights fetched. */
  download: (hf_path: string, files?: string[], revision?: string) =>
    request<Task>('/models/', { method: 'POST', body: JSON.stringify({ hf_path, files: files?.length ? files : null, revision: revision || null }) }),
  /** Queue the copy of a folder or weight file from the server's disk. */
  importLocal: (path: string, name: string) => request<Task>('/models/import', { method: 'POST', body: JSON.stringify({ path, name }) }),
  update: (id: number, changes: LLMModelUpdate) => request<LLMModel>(`/models/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  /** `deleteFiles` also removes the weights from the cache. */
  remove: (id: number, deleteFiles = false) => request<void>(`/models/${id}?delete_files=${deleteFiles}`, { method: 'DELETE' }),
  /** Register every model found in the Hugging Face cache. */
  sync: () => request<Record<'added' | 'refreshed' | 'skipped', string[]>>('/models/sync', { method: 'POST' }),
  hubStatus: () => request<HubStatus>('/models/hub/status'),
  hubLogin: () => request<HubStatus>('/models/hub/login', { method: 'POST' }),
  hubFiles: (repoId: string, revision?: string) =>
    request<HubFile[]>(`/models/hub/${repoId.trim()}/files${revision ? `?revision=${encodeURIComponent(revision)}` : ''}`),
};
