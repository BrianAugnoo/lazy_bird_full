import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import type { FieldRenderer, KwargsKey } from '@/core/fields/types';
import { SettingsForm } from './SettingsForm';

const kwargsKey: KwargsKey = {
  base_url: {
    default_field: true,
    content: 'default.basic.text',
    args: {},
    type: 'string',
    required: true,
    nullable: false,
    default: null,
    title: 'Base URL',
    description: 'OpenAI-compatible endpoint',
  },
  port: {
    default_field: false,
    content: '<input data-field-input aria-label="port">',
    args: {},
    type: 'integer',
    required: false,
    nullable: false,
    default: 80,
    title: 'Port',
    description: null,
  },
};

const textRenderer: FieldRenderer = (container, context) => {
  const input = document.createElement('input');
  input.setAttribute('aria-label', context.name);
  input.value = String(context.value ?? '');
  input.addEventListener('input', () => context.onChange(input.value || undefined));
  container.append(input);
};

describe('SettingsForm', () => {
  it('renders every attribute and reports the whole settings object', async () => {
    const onChange = vi.fn();
    const loader = { load: vi.fn(async () => textRenderer) };
    render(<SettingsForm kwargsKey={kwargsKey} values={{ base_url: 'http://a' }} onChange={onChange} loader={loader} />);

    const url = await screen.findByLabelText('base_url');
    expect((url as HTMLInputElement).value).toBe('http://a');
    expect(loader.load).toHaveBeenCalledWith('default.basic.text');

    fireEvent.input(screen.getByLabelText('port'), { target: { value: '8080' } });
    expect(onChange).toHaveBeenLastCalledWith({ base_url: 'http://a', port: 8080 });

    fireEvent.input(url, { target: { value: '' } });
    expect(onChange).toHaveBeenLastCalledWith({ port: 8080 });
  });

  it('shows per-field errors and loader failures', async () => {
    const loader = { load: vi.fn(async () => Promise.reject(new Error('missing module'))) };
    render(<SettingsForm kwargsKey={kwargsKey} values={{}} onChange={vi.fn()} loader={loader} errors={{ base_url: 'Field required' }} />);

    expect(screen.getByRole('alert').textContent).toBe('Field required');
    await waitFor(() => expect(screen.getByText(/Field unavailable: missing module/)).toBeTruthy());
  });
});
