import { fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { TaskState } from '@/core/tasks/store';
import type { Task } from '@/core/types/api';
import { ToastProvider } from '@/ui/Toasts';
import { TasksPage } from './TasksPage';

const store = vi.hoisted(() => ({ state: null as unknown, taskAction: vi.fn(() => Promise.resolve(null)) }));
vi.mock('@/core/tasks/store', async (original) => ({
  ...(await original<typeof import('@/core/tasks/store')>()),
  useTaskStore: () => store.state,
  taskAction: store.taskAction,
}));

const task = (id: number, changes: Partial<Task> = {}): Task => ({
  id,
  kind: 'files.embed',
  title: `Task ${id}`,
  params: {},
  status: 'queued',
  control: null,
  priority: 5,
  position: id,
  run_at: null,
  resources: {},
  progress: null,
  message: null,
  result: null,
  error: null,
  attempts: 1,
  max_attempts: 1,
  dedupe_key: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  started_at: null,
  finished_at: null,
  waiting_for: [],
  ...changes,
});

const show = (changes: Partial<TaskState>) => {
  store.state = { tasks: [], kinds: [], resources: { capacity: {}, used: {}, holders: {} }, waiting: {}, unresponsive: [], status: 'open', ...changes };
  render(
    <ToastProvider>
      <TasksPage />
    </ToastProvider>,
  );
};

describe('TasksPage', () => {
  afterEach(() => vi.clearAllMocks());

  it('runs a waiting task now', () => {
    show({ tasks: [task(3)] });

    fireEvent.click(screen.getByText('Run now'));

    expect(store.taskAction).toHaveBeenCalledWith('run_now', 3);
  });

  it('does not offer to run now a task that already runs now, and says so', () => {
    show({ tasks: [task(3, { priority: 0 })] });

    expect(screen.queryByText('Run now')).toBeNull();
    expect(screen.getByText('run now')).toBeTruthy();
  });

  it('says what a waiting task waits for in plain words', () => {
    show({ tasks: [task(3)], waiting: { '3': ['vram_mb'] } });

    expect(screen.getByText('Waiting for gpu memory')).toBeTruthy();
  });

  it('flags a running task that was asked to make room but has not stopped', () => {
    show({ tasks: [task(3, { status: 'running' }), task(4, { status: 'running' })], unresponsive: [3] });

    expect(screen.getAllByText('not responding')).toHaveLength(1);
  });

  it('lists the models in memory, in use or idle, with what they really take', () => {
    show({
      resources: {
        capacity: {},
        used: {},
        holders: {},
        models: [
          { model: 'Qwen3-Embedding-0.6B', engine: 'sentence-transformers', device: 'cuda', needs: { vram_mb: 1648 }, idle: true, users: [], pid: 42, memory: { rss_mb: 2300, vram_mb: 1160 } },
          { model: 'MiniLM', engine: 'sentence-transformers', device: 'cpu', needs: { ram_mb: 400 }, idle: false, users: ['task:3'], pid: null, memory: null },
        ],
      },
    });

    expect(screen.getByText('Qwen3-Embedding-0.6B')).toBeTruthy();
    expect(screen.getByText('idle')).toBeTruthy();
    expect(screen.getByText('in use')).toBeTruthy();
    expect(screen.getByText(/1\.6 GB of GPU memory \(really using 2\.2 GB memory, 1\.1 GB GPU\)/)).toBeTruthy();
    expect(screen.getAllByText('own process')).toHaveLength(1); // only the model with a process of its own
  });
});
