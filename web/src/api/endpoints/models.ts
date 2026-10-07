import { request, uploadBody } from '../client';
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
  /** Send one file of a model to upload (`relativePath` keeps its place in the model folder). */
  uploadFile: (name: string, relativePath: string, file: Blob, options: { onProgress?: (sent: number) => void; signal?: AbortSignal } = {}) =>
    uploadBody<{ path: string; size: number }>(`/models/uploads/${encodeURIComponent(name)}/files/${relativePath.split('/').map(encodeURIComponent).join('/')}`, file, options),
  /** Import the uploaded files as the model `local/<name>` (a background task). */
  importUpload: (name: string) => request<Task>(`/models/uploads/${encodeURIComponent(name)}`, { method: 'POST' }),
  /** Forget the files uploaded for a model that will not be imported. */
  discardUpload: (name: string) => request<void>(`/models/uploads/${encodeURIComponent(name)}`, { method: 'DELETE' }),
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
