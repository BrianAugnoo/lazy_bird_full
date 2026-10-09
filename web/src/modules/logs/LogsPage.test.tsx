import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { LogEntry } from '@/core/types/api';
import { mockApi } from '@/test/http';
import { ToastProvider } from '@/ui/Toasts';
import { LogsPage } from './LogsPage';

const entry = (line: number, level: string, message: string): LogEntry => ({
  start_line: line,
  end_line: line,
  timestamp: '2026-01-01T10:00:00Z',
  level,
  location: 'lazy_bird.main:startup:1',
  message,
  payload: null,
  score: null,
});

/** The query strings of the log searches sent so far. */
const searches = () =>
  vi
    .mocked(globalThis.fetch)
    .mock.calls.map(([input]) => new URL(String(input), 'http://test'))
    .filter((url) => url.pathname.endsWith('/logs/'));

const renderPage = () =>
  render(
    <ToastProvider>
      <LogsPage />
    </ToastProvider>,
  );

describe('LogsPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists the entries without debug lines until they are asked for', async () => {
    mockApi({ 'GET /logs/': [entry(1, 'INFO', 'Server started')], 'GET /logs/tracing': { enabled: false } });
    renderPage();

    expect(await screen.findByText('Server started')).toBeTruthy();
    expect(searches()[0].searchParams.getAll('level')).toEqual(['INFO', 'WARNING', 'ERROR', 'CRITICAL']);

    fireEvent.click(screen.getByRole('button', { name: 'debug' }));

    await waitFor(() => expect(searches()).toHaveLength(2));
    expect(searches()[1].searchParams.getAll('level')).toContain('DEBUG');
  });

  it('switches call tracing on', async () => {
    const calls = mockApi({ 'GET /logs/': [], 'GET /logs/tracing': { enabled: false }, 'PUT /logs/tracing': { enabled: true } });
    renderPage();

    const toggle = await screen.findByRole('checkbox');
    await waitFor(() => expect(toggle).toHaveProperty('disabled', false));
    fireEvent.click(toggle);

    expect(await screen.findByText('On')).toBeTruthy();
    expect(calls('PUT /logs/tracing')).toEqual([{ enabled: true }]);
  });
});
