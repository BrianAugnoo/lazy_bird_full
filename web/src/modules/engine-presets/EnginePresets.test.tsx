import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { EnginePresets } from './EnginePresets';

const engine = {
  id: 1,
  name: 'openai-client',
  file_path: 'openai.py',
  formats: [],
  available: true,
  kwargs_key: {
    base_url: {
      default_field: true,
      content: 'default.basic.text',
      args: {},
      type: 'string',
      required: true,
      nullable: false,
      default: null,
      title: 'Base URL',
      description: null,
    },
  },
};

function respond(body: unknown, status = 200) {
  return Promise.resolve({
    ok: status < 400,
    status,
    statusText: '',
    headers: new Headers({ 'content-type': 'application/json' }),
    json: async () => body,
  } as Response);
}

describe('EnginePresets', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists presets with their default and validity', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation((input) => {
      const url = String(input);
      if (url.endsWith('/inference-engines/')) return respond([engine]);
      return respond([
        { id: 1, name: 'remote', inference_engine_id: 1, kwargs: {}, default: true, valid: false, errors: { base_url: 'Field required' } },
      ]);
    });

    render(<EnginePresets kind="inference" />);

    expect(await screen.findByText('remote')).toBeTruthy();
    expect(screen.getByText('Default')).toBeTruthy();
    expect(screen.getByText('Base URL: Field required')).toBeTruthy();
  });

  it('shows field errors returned when saving a preset', async () => {
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation((input, init) => {
      const url = String(input);
      if (url.endsWith('/inference-engines/')) return respond([engine]);
      if (init?.method === 'POST') {
        return respond({ error: { code: 'invalid_settings', message: 'Invalid', details: { fields: { base_url: 'Field required' } } } }, 422);
      }
      return respond([]);
    });

    render(<EnginePresets kind="inference" />);
    fireEvent.click(await screen.findByText('+ New preset'));
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'remote' } });
    fireEvent.click(screen.getByText('Save preset'));

    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('Field required'));
    const post = fetchMock.mock.calls.find(([, init]) => init?.method === 'POST')!;
    expect(JSON.parse(String(post[1]!.body))).toEqual({ name: 'remote', inference_engine_id: 1, kwargs: {} });
  });
});
