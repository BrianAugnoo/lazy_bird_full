import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { AgentPresetData, ExtensionPreset } from '@/core/types/api';
import { callable } from '@/test/callables';
import { mockApi } from '@/test/http';
import { DialogProvider } from '@/ui/Dialogs';
import { ToastProvider } from '@/ui/Toasts';
import { PresetsPage } from './PresetsPage';

const preset = (extension: string, data: AgentPresetData): ExtensionPreset<AgentPresetData> => ({
  id: `${extension}/${data.name}`,
  extension,
  name: data.name,
  editable: extension === 'custom',
  valid: true,
  errors: {},
  data,
});

const writer = preset('custom', { name: 'writer', description: 'Writes', tools: [], hooks: ['default-system-date'] });
const assistant = preset('default', { name: 'assistant', description: 'Helps', tools: ['default-smtp-send_email'], hooks: [] });

function routes(extra: Record<string, unknown> = {}) {
  return mockApi({
    'GET /agent-presets/': [writer, assistant],
    'GET /tools/': [callable('default', 'smtp', 'send_email'), callable('default', 'smtp', 'read_inbox')],
    'GET /hooks/': [callable('default', 'system', 'date'), callable('default', 'system', 'user_information')],
    'GET /skills/': [],
    'GET /instructions/full/': [],
    'GET /instructions/sub/': [],
    ...extra,
  });
}

const renderPage = () =>
  render(
    <ToastProvider>
      <DialogProvider>
        <PresetsPage kind="agent" />
      </DialogProvider>
    </ToastProvider>,
  );

describe('PresetsPage', () => {
  afterEach(() => vi.restoreAllMocks());

  it('saves the tools and hooks chosen in the picker', async () => {
    const sent = routes({ 'PUT /agent-presets/custom/writer': (body: unknown) => ({ ...writer, data: body }) });
    renderPage();

    fireEvent.click(await screen.findByText('writer'));
    fireEvent.click(await screen.findByText('Choose tools…'));
    fireEvent.click(screen.getByLabelText('All tools of default'));
    fireEvent.click(screen.getByText('Confirm'));
    fireEvent.click(screen.getByText('Choose hooks…'));
    fireEvent.click(screen.getByLabelText(/user_information/));
    fireEvent.click(screen.getByText('Confirm'));
    fireEvent.click(screen.getByText('Save'));

    await waitFor(() => expect(sent('PUT /agent-presets/custom/writer')).toHaveLength(1));
    const body = sent('PUT /agent-presets/custom/writer')[0] as AgentPresetData;
    expect(body.tools).toEqual(['default-smtp-send_email', 'default-smtp-read_inbox']);
    expect(body.hooks).toEqual(['default-system-date', 'default-system-user_information']);
  });

  it('shows the tools of a built-in preset without letting them change', async () => {
    routes();
    renderPage();

    fireEvent.click(await screen.findByText('assistant'));

    expect(await screen.findByText('send_email')).toBeTruthy();
    expect(screen.queryByText('Choose tools…')).toBeNull();
  });
});
