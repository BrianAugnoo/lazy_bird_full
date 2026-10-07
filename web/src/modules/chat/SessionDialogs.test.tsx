import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockApi } from '@/test/http';
import { ToastProvider } from '@/ui/Toasts';
import { AddAgentDialog, NewSessionDialog } from './SessionDialogs';

const session = { id: 4, title: 'Notes', meta: null, created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z' };
const sessionPreset = {
  id: 'default/research-team',
  extension: 'default',
  name: 'research-team',
  editable: false,
  valid: true,
  errors: {},
  data: { name: 'research-team', description: 'A team', agents: ['default/assistant'], master: 'default/assistant', meta: {} },
};

const inToasts = (node: React.ReactNode) => render(<ToastProvider>{node}</ToastProvider>);

describe('NewSessionDialog', () => {
  afterEach(() => vi.restoreAllMocks());

  it('creates an empty session with its title even when presets cannot be loaded', async () => {
    const sent = mockApi({
      'GET /session-presets/': { status: 500, body: { error: { code: 'internal_error', message: 'Broken', details: {} } } },
      'POST /sessions/': session,
    });
    const onCreated = vi.fn();
    inToasts(<NewSessionDialog onClose={vi.fn()} onCreated={onCreated} />);

    expect(await screen.findByText(/Presets could not be loaded/)).toBeTruthy();
    expect(screen.getByRole('radio', { name: /Empty session/ }).getAttribute('aria-checked')).toBe('true');
    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'Notes' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(session));
    expect(sent('POST /sessions/')).toEqual([{ title: 'Notes' }]);
  });

  it('suggests the first preset and lets the user pick an empty session instead', async () => {
    const sent = mockApi({ 'GET /session-presets/': [sessionPreset], 'POST /sessions/': session, 'POST /sessions/from-preset': session });
    const onCreated = vi.fn();
    inToasts(<NewSessionDialog onClose={vi.fn()} onCreated={onCreated} />);

    const preset = await screen.findByRole('radio', { name: /research-team/ });
    expect(preset.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(screen.getByRole('radio', { name: /Empty session/ }));
    fireEvent.submit(screen.getByLabelText(/Title/).closest('form')!);

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(sent('POST /sessions/')).toEqual([{ title: 'New session' }]);
    expect(sent('POST /sessions/from-preset')).toEqual([]);
  });

  it('creates the team of the chosen preset', async () => {
    const sent = mockApi({ 'GET /session-presets/': [sessionPreset], 'POST /sessions/from-preset': session });
    const onCreated = vi.fn();
    inToasts(<NewSessionDialog onClose={vi.fn()} onCreated={onCreated} />);

    await screen.findByRole('radio', { name: /research-team/ });
    fireEvent.change(screen.getByLabelText(/Title/), { target: { value: 'Solar' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create session' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(sent('POST /sessions/from-preset')).toEqual([{ preset_id: 'default/research-team', title: 'Solar' }]);
  });
});

describe('AddAgentDialog', () => {
  afterEach(() => vi.restoreAllMocks());

  it('continues to the agent editor for a blank agent', async () => {
    mockApi({ 'GET /agent-presets/': [] });
    const onBlank = vi.fn();
    inToasts(<AddAgentDialog sessionId={1} onClose={vi.fn()} onCreated={vi.fn()} onBlank={onBlank} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Continue' }));

    expect(onBlank).toHaveBeenCalled();
  });

  it('adds the chosen preset to the session', async () => {
    const preset = { id: 'default/researcher', extension: 'default', name: 'researcher', editable: false, valid: true, errors: {}, data: { name: 'researcher' } };
    const agent = { id: 9, name: 'researcher' };
    const sent = mockApi({ 'GET /agent-presets/': [preset], 'POST /agents/from-preset': agent });
    const onCreated = vi.fn();
    inToasts(<AddAgentDialog sessionId={3} onClose={vi.fn()} onCreated={onCreated} onBlank={vi.fn()} />);

    fireEvent.click(await screen.findByRole('button', { name: 'Add agent' }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(agent));
    expect(sent('POST /agents/from-preset')).toEqual([{ session_id: 3, preset_id: 'default/researcher' }]);
  });
});
