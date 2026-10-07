import { request } from '../client';
import type { ResourceSnapshot, Task, TaskKind, TaskStatus } from '@/core/types/api';

const post = (id: number, action: string) => request<Task>(`/tasks/${id}/${action}`, { method: 'POST' });

export const tasks = {
  list: (status?: TaskStatus, kind?: string) => {
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (kind) params.set('kind', kind);
    return request<Task[]>(`/tasks/${params.size ? `?${params}` : ''}`);
  },
  get: (id: number) => request<Task>(`/tasks/${id}`),
  kinds: () => request<TaskKind[]>('/tasks/kinds'),
  resources: () => request<ResourceSnapshot>('/tasks/resources'),
  update: (id: number, changes: { priority?: number; run_at?: string | null }) =>
    request<Task>(`/tasks/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  pause: (id: number) => post(id, 'pause'),
  resume: (id: number) => post(id, 'resume'),
  cancel: (id: number) => post(id, 'cancel'),
  retry: (id: number) => post(id, 'retry'),
  move: (id: number, target: { before_id?: number; after_id?: number }) =>
    request<Task>(`/tasks/${id}/move`, { method: 'POST', body: JSON.stringify(target) }),
  remove: (id: number) => request<void>(`/tasks/${id}`, { method: 'DELETE' }),
  clearFinished: () => request<{ deleted: number }>('/tasks/finished', { method: 'DELETE' }),
};
