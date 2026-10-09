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
  local: false,
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

  it('tells when an engine runs its model on this computer', async () => {
    mockApi({ 'GET /inference-engines/': [{ ...engine, local: true }], 'GET /inference-presets/': [] });

    page();
    fireEvent.click((await screen.findAllByText('New preset'))[0]);

    expect(await screen.findByText(/Runs the model on this computer/)).toBeTruthy();
  });

  it('says nothing about memory for engines that call a server', async () => {
    mockApi({ 'GET /inference-engines/': [engine], 'GET /inference-presets/': [] });

    page();
    fireEvent.click((await screen.findAllByText('New preset'))[0]);
    await screen.findByLabelText('Name');

    expect(screen.queryByText(/Runs the model on this computer/)).toBeNull();
  });

  it('manages cross-encoder presets through their own routes', async () => {
    const calls = mockApi({
      'GET /cross-encoder-engines/': [{ ...engine, name: 'sentence-transformers' }],
      'GET /cross-encoder-presets/': [{ id: 1, name: 'reranker', cross_encoder_engine_id: 1, kwargs: {}, default: true, valid: true, errors: {} }],
      'POST /cross-encoder-presets/': { id: 2 },
    });

    render(
      <ToastProvider>
        <EnginePresets kind="cross_encoder" />
      </ToastProvider>,
    );

    expect(await screen.findByText('reranker', { selector: '.list-row-title' })).toBeTruthy();
    expect(screen.getByText('sentence-transformers', { selector: '.list-row-meta' })).toBeTruthy();
    fireEvent.click((await screen.findAllByText('New preset'))[0]);
    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'second' } });
    fireEvent.click(screen.getByText('Save preset'));

    await waitFor(() => expect(calls('POST /cross-encoder-presets/')).toHaveLength(1));
    expect(calls('POST /cross-encoder-presets/')[0]).toEqual({ name: 'second', cross_encoder_engine_id: 1, kwargs: {} });
  });
});
