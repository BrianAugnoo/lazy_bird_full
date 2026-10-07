import { downloadFileBlob, request, requestBlob } from '../client';
import type { Chunk, FileItem, FilePatchIn, SearchPayload, SearchResult, Task } from '@/core/types/api';

const enc = encodeURIComponent;

export const files = {
  list: () => request<FileItem[]>('/files/'),
  get: (id: number) => request<FileItem>(`/files/${id}`),
  /** Every folder of the storage, empty ones included. */
  directories: () => request<string[]>('/files/directories'),
  /** Upload into `dir`; a name already taken gets a numbered suffix. */
  upload: (dir: string, list: File[]) => {
    const form = new FormData();
    for (const file of list) form.append('files', file);
    return request<FileItem[]>(`/files/upload?dir=${enc(dir)}`, { method: 'POST', body: form });
  },
  /** Text content; fails with `not_text` for binary files. */
  content: (id: number) => request<string>(`/files/${id}/content`),
  full: async (id: number) => (await requestBlob(`/files/${id}/full`)).text(),
  saveContent: (id: number, content: string) =>
    request<FileItem>(`/files/${id}/content`, { method: 'PUT', body: JSON.stringify({ content }) }),
  download: (id: number, filename: string) => downloadFileBlob(`/files/${id}/download`, filename),
  /** Rename and/or move to another folder. */
  patch: (id: number, changes: FilePatchIn) => request<FileItem>(`/files/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  remove: (ids: number[]) => request<{ deleted: number }>('/files/', { method: 'DELETE', body: JSON.stringify(ids) }),
  removeAll: () => request<{ deleted: number }>('/files/all', { method: 'DELETE' }),
  createDirectory: (path: string) => request<{ path: string }>(`/files/directory?path=${enc(path)}`, { method: 'POST' }),
  moveDirectory: (source: string, destination: string) =>
    request<{ path: string }>(`/files/directory?source=${enc(source)}&destination=${enc(destination)}`, { method: 'PATCH' }),
  removeDirectory: (path: string) => request<{ path: string }>(`/files/directory?path=${enc(path)}`, { method: 'DELETE' }),
  /** Queue what the file still needs (chunks, default embedding). */
  process: (id: number) => request<FileItem>(`/files/${id}/process`, { method: 'POST' }),
  /** Compute one processing again, even when up to date. */
  reprocess: (id: number, processor: string, target = '') =>
    request<FileItem>(`/files/${id}/processing`, { method: 'POST', body: JSON.stringify({ processor, target }) }),
  /** Check every file for changes on disk now. */
  scan: () => request<Task>('/files/scan', { method: 'POST' }),
  chunks: (id: number) => request<Chunk[]>(`/files/${id}/chunks`),
};

export const search = (payload: SearchPayload) => request<SearchResult[]>('/search/', { method: 'POST', body: JSON.stringify(payload) });
