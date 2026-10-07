import { request } from '../client';
import type { HubFile, LLMModel, LLMModelUpdate, Task } from '@/core/types/api';

/** GET /models/ — optionally only models available in one of `formats`. */
export async function getModels(formats: string[] = []): Promise<LLMModel[]> {
  const query = formats.map((format) => `format=${encodeURIComponent(format)}`).join('&');
  return request<LLMModel[]>(`/models/${query ? `?${query}` : ''}`);
}

/** GET /models/{id} */
export async function getModel(id: number): Promise<LLMModel> {
  return request<LLMModel>(`/models/${id}`);
}

/** POST /models/ — queue a Hugging Face download; `files` limits the weights fetched. */
export async function createModel(hf_path: string, files?: string[]): Promise<Task> {
  return request<Task>('/models/', { method: 'POST', body: JSON.stringify({ hf_path, files }) });
}

/** POST /models/import — queue the copy of a folder or weight file from the server's disk. */
export async function importModel(path: string, name: string): Promise<Task> {
  return request<Task>('/models/import', { method: 'POST', body: JSON.stringify({ path, name }) });
}

/** GET /models/hub/{repo}/files — files of a Hugging Face repository with their format. */
export async function getHubFiles(repoId: string): Promise<HubFile[]> {
  return request<HubFile[]>(`/models/hub/${repoId}/files`);
}

/** PATCH /models/{id} — rename, choose the format / weight file / context. */
export async function updateModel(id: number, changes: LLMModelUpdate): Promise<LLMModel> {
  return request<LLMModel>(`/models/${id}`, { method: 'PATCH', body: JSON.stringify(changes) });
}

/** PATCH /models/{id} with only the format. */
export async function setModelFormat(id: number, selected_format: string): Promise<LLMModel> {
  return updateModel(id, { selected_format });
}

/** DELETE /models/{id} — `deleteFiles` also removes the files from the cache. */
export async function deleteModel(id: number, deleteFiles = false): Promise<void> {
  return request<void>(`/models/${id}?delete_files=${deleteFiles}`, { method: 'DELETE' });
}

/** POST /models/sync — register every model found in the Hugging Face cache. */
export async function syncModels(): Promise<Record<'added' | 'refreshed' | 'skipped', string[]>> {
  return request('/models/sync', { method: 'POST' });
}
