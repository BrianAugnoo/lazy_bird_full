/**
 * Live view of the background task queue, shared by every page.
 *
 * One `/ws/tasks` connection is opened while something is subscribed. It keeps
 * the tasks, resources and waiting reasons up to date and relays `file` events
 * (a file's processing changed) to `onFileChange` listeners. Commands go through
 * the socket when it is open, through HTTP otherwise.
 */
import { useSyncExternalStore } from 'react';
import { ApiError } from '@/api/client';
import { tasks as tasksApi } from '@/api/endpoints/tasks';
import { LiveSocket, type SocketStatus } from '@/api/socket';
import type { ApiErrorBody, ResourceSnapshot, Task, TaskKind } from '@/core/types/api';

export interface TaskState {
  tasks: Task[];
  kinds: TaskKind[];
  resources: ResourceSnapshot;
  /** Why queued tasks wait, by task id. */
  waiting: Record<string, string[]>;
  status: SocketStatus;
}

export const ACTIVE: Task['status'][] = ['running', 'queued', 'paused'];

/** A queued task whose start time is still to come (e.g. the next periodic scan). */
export const isScheduled = (task: Task, now = Date.now()) => task.status === 'queued' && task.run_at !== null && new Date(task.run_at).getTime() > now;

/** Same order as the backend: running, then waiting by priority and position, then finished (newest first). */
export function sortTasks(list: Task[]): Task[] {
  const active = list.filter((task) => ACTIVE.includes(task.status));
  const finished = list.filter((task) => !ACTIVE.includes(task.status));
  active.sort(
    (a, b) =>
      Number(b.status === 'running') - Number(a.status === 'running') || b.priority - a.priority || a.position - b.position || a.id - b.id,
  );
  finished.sort((a, b) => (b.finished_at ?? b.updated_at).localeCompare(a.finished_at ?? a.updated_at));
  return [...active, ...finished];
}

type TaskEvent =
  | { type: 'snapshot'; tasks: Task[]; resources: ResourceSnapshot; kinds: TaskKind[] }
  | { type: 'task'; task: Task }
  | { type: 'task_deleted'; id: number }
  | { type: 'resources'; resources: ResourceSnapshot }
  | { type: 'waiting'; waiting: Record<string, string[]> }
  | { type: 'reordered' }
  | { type: 'file'; file_id: number }
  | { type: 'ack'; request_id: string; task: Task | null }
  | { type: 'error'; request_id: string; error: ApiErrorBody };

/** Apply one socket event to the state (pure, for tests). */
export function applyTaskEvent(state: TaskState, event: TaskEvent): TaskState {
  switch (event.type) {
    case 'snapshot':
      return { ...state, tasks: sortTasks(event.tasks), resources: event.resources, kinds: event.kinds };
    case 'task': {
      const others = state.tasks.filter((task) => task.id !== event.task.id);
      return { ...state, tasks: sortTasks([...others, event.task]) };
    }
    case 'task_deleted':
      return { ...state, tasks: state.tasks.filter((task) => task.id !== event.id) };
    case 'resources':
      return { ...state, resources: event.resources };
    case 'waiting':
      return { ...state, waiting: event.waiting };
    default:
      return state;
  }
}

const EMPTY: TaskState = { tasks: [], kinds: [], resources: { capacity: {}, used: {}, holders: {} }, waiting: {}, status: 'closed' };

let state: TaskState = EMPTY;
let socket: LiveSocket | null = null;
const listeners = new Set<() => void>();
const fileListeners = new Set<(fileId: number) => void>();
const pending = new Map<string, { resolve: (task: Task | null) => void; reject: (error: ApiError) => void }>();
let closeTimer: ReturnType<typeof setTimeout> | null = null;

function setState(next: TaskState) {
  state = next;
  for (const listener of listeners) listener();
}

async function refetchOrder() {
  try {
    setState({ ...state, tasks: sortTasks(await tasksApi.list()) });
  } catch {
    // The next event or reconnection brings the queue back.
  }
}

function handle(data: unknown) {
  const event = data as TaskEvent;
  if (event.type === 'file') {
    for (const listener of fileListeners) listener(event.file_id);
    return;
  }
  if (event.type === 'reordered') {
    void refetchOrder();
    return;
  }
  if (event.type === 'ack' || event.type === 'error') {
    const waiter = pending.get(event.request_id);
    pending.delete(event.request_id);
    if (event.type === 'ack') waiter?.resolve(event.task);
    else waiter?.reject(new ApiError(event.error.message, 400, event.error.code, event.error.details ?? {}));
    return;
  }
  setState(applyTaskEvent(state, event));
}

function ensureSocket() {
  if (closeTimer) {
    clearTimeout(closeTimer);
    closeTimer = null;
  }
  socket ??= new LiveSocket('/ws/tasks', { onMessage: handle, onStatus: (status) => setState({ ...state, status }) });
}

function releaseSocket() {
  if (listeners.size > 0 || fileListeners.size > 0) return;
  // Keep the connection briefly: pages subscribe again right after a navigation.
  closeTimer = setTimeout(() => {
    socket?.close();
    socket = null;
  }, 5000);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  ensureSocket();
  return () => {
    listeners.delete(listener);
    releaseSocket();
  };
}

/** The live task queue; connects to `/ws/tasks` while mounted. */
export function useTaskStore(): TaskState {
  return useSyncExternalStore(subscribe, () => state, () => state);
}

/** Called with a file id whenever one of its processings changes. */
export function onFileChange(listener: (fileId: number) => void): () => void {
  fileListeners.add(listener);
  ensureSocket();
  return () => {
    fileListeners.delete(listener);
    releaseSocket();
  };
}

export type TaskAction = 'pause' | 'resume' | 'cancel' | 'retry' | 'delete';

let requestCounter = 0;

function viaSocket(command: Record<string, unknown>): Promise<Task | null> | null {
  if (!socket) return null;
  const request_id = `r${++requestCounter}`;
  const promise = new Promise<Task | null>((resolve, reject) => pending.set(request_id, { resolve, reject }));
  if (!socket.send({ ...command, request_id })) {
    pending.delete(request_id);
    return null;
  }
  return promise;
}

/** Pause, resume, cancel, retry or delete a task. */
export function taskAction(action: TaskAction, taskId: number): Promise<Task | null> {
  const sent = viaSocket({ action, task_id: taskId });
  if (sent) return sent;
  if (action === 'delete') return tasksApi.remove(taskId).then(() => null);
  return tasksApi[action](taskId);
}

/** Place a waiting task before or after another one (it takes that task's priority). */
export function moveTask(taskId: number, target: { before_id?: number; after_id?: number }): Promise<Task | null> {
  return viaSocket({ action: 'move', task_id: taskId, ...target }) ?? tasksApi.move(taskId, target);
}

export function setTaskPriority(taskId: number, priority: number): Promise<Task | null> {
  return viaSocket({ action: 'update', task_id: taskId, priority }) ?? tasksApi.update(taskId, { priority });
}

/** Reset the module state (tests). */
export function resetTaskStore() {
  socket?.close();
  socket = null;
  listeners.clear();
  fileListeners.clear();
  pending.clear();
  state = EMPTY;
}
