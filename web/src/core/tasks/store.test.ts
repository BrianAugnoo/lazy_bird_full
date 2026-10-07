import { describe, expect, it } from 'vitest';
import type { Task } from '@/core/types/api';
import { applyTaskEvent, isScheduled, sortTasks, type TaskState } from './store';

const task = (id: number, changes: Partial<Task> = {}): Task => ({
  id,
  kind: 'files.chunk',
  title: `Task ${id}`,
  params: {},
  status: 'queued',
  control: null,
  priority: 0,
  position: id,
  run_at: null,
  resources: {},
  progress: null,
  message: null,
  result: null,
  error: null,
  attempts: 0,
  max_attempts: 3,
  dedupe_key: null,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  started_at: null,
  finished_at: null,
  waiting_for: [],
  ...changes,
});

const empty: TaskState = { tasks: [], kinds: [], resources: { capacity: {}, used: {}, holders: {} }, waiting: {}, status: 'open' };

describe('task queue order', () => {
  it('puts running tasks first, then waiting ones by priority and position, then finished ones', () => {
    const list = [
      task(1, { status: 'completed', finished_at: '2026-01-01T00:00:01Z' }),
      task(2, { priority: 0, position: 2 }),
      task(3, { status: 'running' }),
      task(4, { priority: 5, position: 9 }),
      task(5, { status: 'failed', finished_at: '2026-01-01T00:00:09Z' }),
      task(6, { priority: 0, position: 1 }),
    ];
    expect(sortTasks(list).map((item) => item.id)).toEqual([3, 4, 6, 2, 5, 1]);
  });

  it('applies live events', () => {
    let state = applyTaskEvent(empty, { type: 'snapshot', tasks: [task(1), task(2, { status: 'running' })], resources: empty.resources, kinds: [] });
    expect(state.tasks.map((item) => item.id)).toEqual([2, 1]);
    state = applyTaskEvent(state, { type: 'task', task: task(1, { status: 'running', progress: 0.5 }) });
    expect(state.tasks.find((item) => item.id === 1)?.progress).toBe(0.5);
    state = applyTaskEvent(state, { type: 'task_deleted', id: 2 });
    expect(state.tasks.map((item) => item.id)).toEqual([1]);
    state = applyTaskEvent(state, { type: 'waiting', waiting: { '1': ['vram_mb'] } });
    expect(state.waiting).toEqual({ '1': ['vram_mb'] });
  });

  it('tells scheduled tasks apart from waiting ones', () => {
    const now = Date.parse('2026-01-01T12:00:00Z');
    expect(isScheduled(task(1, { run_at: '2026-01-01T13:00:00Z' }), now)).toBe(true);
    expect(isScheduled(task(1, { run_at: '2026-01-01T11:00:00Z' }), now)).toBe(false);
    expect(isScheduled(task(1), now)).toBe(false);
  });
});
