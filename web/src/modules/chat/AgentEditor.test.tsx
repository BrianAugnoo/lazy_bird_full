import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { Agent } from '@/core/types/api';
import { callable } from '@/test/callables';
import { mockApi } from '@/test/http';
import { ToastProvider } from '@/ui/Toasts';
import { AgentEditor } from './AgentEditor';

const agent: Agent = {
  id: 7,
  session_id: 1,
  name: 'lead',
  description: null,
  instructions: null,
  instruction_fulls: [],
  instruction_subs: [],
  skills: [],
  tools: [],
  hooks: [],
  master: true,
  meta: { preset_inference_engine_id: 1, color: 'blue' },
  sub_agents_ids: [],
  parent_agents_ids: [],
  preset: null,
  valid: true,
  errors: {},
};

const engine = { id: 3, name: 'openai-client', file_path: 'openai.py', formats: [], local: false, available: true, kwargs_key: {} };

function routes(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /tools/': [{ id: 'default-kb-search', name: 'search', description: 'Search files', extension: 'default', module: 'kb', file_path: 'default/kb.py', class_name: null, needs_settings: false, meta_params: [], required_meta: [], accepts_any_meta: false, parameters: null }],
    'GET /hooks/': [],
    'GET /skills/': [],
    'GET /instructions/full/': [],
    'GET /instructions/sub/': [],
    'GET /inference-presets/': [
      { id: 1, name: 'local', inference_engine_id: 3, kwargs: {}, default: true, valid: true, errors: {} },
      { id: 2, name: 'remote', inference_engine_id: 3, kwargs: {}, default: false, valid: true, errors: {} },
    ],
    'GET /inference-engines/': [engine],
    'GET /agents/7/tools': [],
    ...extra,
  });
}

const open = (onSaved = vi.fn()) =>
  render(
    <ToastProvider>
      <AgentEditor agent={agent} sessionId={1} sessionAgents={[agent]} onClose={vi.fn()} onSaved={onSaved} onDeleted={vi.fn()} />
    </ToastProvider>,
  );

describe('AgentEditor', () => {
  afterEach(() => vi.restoreAllMocks());

  it('saves the chosen preset and tools, keeping other meta values', async () => {
    const sent = routes({ 'PATCH /agents/7': (body: unknown) => ({ ...agent, ...(body as object) }) });
    const onSaved = vi.fn();
    open(onSaved);

    fireEvent.change(await screen.findByLabelText('Inference preset'), { target: { value: '2' } });
    fireEvent.click(await screen.findByText('Choose tools…'));
    fireEvent.click(screen.getByLabelText(/search/));
    fireEvent.click(screen.getByText('Confirm'));
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const body = sent('PATCH /agents/7')[0] as { meta: unknown; tools: string[] };
    expect(body.meta).toEqual({ preset_inference_engine_id: 2, color: 'blue' });
    expect(body.tools).toEqual(['default-kb-search']);
  });

  it('chooses hooks module by module in the picker', async () => {
    const sent = routes({
      'GET /hooks/': [callable('default', 'system', 'date'), callable('default', 'system', 'user_information'), callable('default', 'compress', 'shorten')],
      'PATCH /agents/7': (body: unknown) => ({ ...agent, ...(body as object) }),
    });
    open();

    fireEvent.click(await screen.findByText('Choose hooks…'));
    fireEvent.click(screen.getByLabelText('All hooks of default/system.py'));
    fireEvent.click(screen.getByText('Confirm'));
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => expect(sent('PATCH /agents/7')).toHaveLength(1));
    expect((sent('PATCH /agents/7')[0] as { hooks: string[] }).hooks).toEqual(['default-system-date', 'default-system-user_information']);
  });

  it('switches to custom engine settings', async () => {
    const sent = routes({ 'PATCH /agents/7': (body: unknown) => ({ ...agent, ...(body as object) }) });
    open();

    fireEvent.click(await screen.findByRole('radio', { name: 'Custom settings' }));
    fireEvent.change(screen.getByLabelText('Inference engine'), { target: { value: '3' } });
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => expect(sent('PATCH /agents/7')).toHaveLength(1));
    expect((sent('PATCH /agents/7')[0] as { meta: unknown }).meta).toEqual({ color: 'blue', inference_engine_id: 3, inference_settings: {} });
  });

  it('shows the field errors of an invalid configuration', async () => {
    routes({
      'PATCH /agents/7': { status: 422, body: { error: { code: 'invalid_agent_inference', message: 'Invalid', details: { fields: { meta: 'No inference preset exists' } } } } },
    });
    open();

    fireEvent.click(await screen.findByText('Save'));

    expect(await screen.findByText('No inference preset exists')).toBeTruthy();
  });
});
