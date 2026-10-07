import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { mockApi } from '@/test/http';
import { ToastProvider } from '@/ui/Toasts';
import { EnginePresets } from './EnginePresets';

const engine = {
  id: 1,
  name: 'openai-client',
  file_path: 'openai.py',
  formats: [],
  available: true,
  kwargs_key: {
    base_url: {
      default_field: false,
      content: '<input data-field-input aria-label="base_url">',
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

const page = () =>
  render(
    <ToastProvider>
      <EnginePresets kind="inference" />
    </ToastProvider>,
  );

describe('EnginePresets', () => {
  afterEach(() => vi.restoreAllMocks());

  it('lists presets with their default and problems', async () => {
    mockApi({
      'GET /inference-engines/': [engine],
      'GET /inference-presets/': [
        { id: 1, name: 'remote', inference_engine_id: 1, kwargs: {}, default: true, valid: false, errors: { base_url: 'Field required' } },
      ],
    });

    page();

    expect(await screen.findByText('remote', { selector: '.list-row-title' })).toBeTruthy();
    expect(screen.getByText('default')).toBeTruthy();
    expect(screen.getByText('Base URL: Field required')).toBeTruthy();
  });

  it('shows field errors returned when saving a preset', async () => {
    const calls = mockApi({
      'GET /inference-engines/': [engine],
      'GET /inference-presets/': [],
      'POST /inference-presets/': {
        status: 422,
        body: { error: { code: 'invalid_settings', message: 'Invalid', details: { fields: { base_url: 'Field required' } } } },
      },
    });

    page();
    fireEvent.click((await screen.findAllByText('New preset'))[0]);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'remote' } });
    fireEvent.click(screen.getByText('Save preset'));

    await waitFor(() => expect(screen.getByRole('alert').textContent).toBe('Field required'));
    expect(calls('POST /inference-presets/')[0]).toEqual({ name: 'remote', inference_engine_id: 1, kwargs: {} });
  });
});
