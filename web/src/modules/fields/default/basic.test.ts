import { describe, expect, it, vi } from 'vitest';
import type { FieldContext, FieldDescriptor } from '@/core/fields/types';
import { integer, password, reference, select } from './basic';

const descriptor = (overrides: Partial<FieldDescriptor> = {}): FieldDescriptor => ({
  default_field: true,
  content: 'default.basic.text',
  args: {},
  type: 'string',
  required: true,
  nullable: false,
  default: null,
  title: 'Field',
  description: null,
  ...overrides,
});

const context = (d: FieldDescriptor, extra: Partial<FieldContext> = {}): FieldContext => ({
  name: 'field',
  value: undefined,
  descriptor: d,
  args: d.args,
  onChange: vi.fn(),
  api: { get: vi.fn() },
  ...extra,
});

describe('default.basic widgets', () => {
  it('integer applies bounds and reports numbers, unsetting when cleared', () => {
    const container = document.createElement('div');
    const ctx = context(descriptor({ type: 'integer', args: { min: 1, max: 9 } }));
    integer(container, ctx);
    const input = container.querySelector('input')!;

    expect(input.min).toBe('1');
    expect(input.max).toBe('9');
    input.value = '5';
    input.dispatchEvent(new Event('input'));
    input.value = '';
    input.dispatchEvent(new Event('input'));
    expect(ctx.onChange).toHaveBeenNthCalledWith(1, 5);
    expect(ctx.onChange).toHaveBeenNthCalledWith(2, undefined);
  });

  it('select keeps the original option values', () => {
    const container = document.createElement('div');
    const ctx = context(descriptor({ type: 'integer', args: { options: [1, 2] } }), { value: 2 });
    select(container, ctx);
    const input = container.querySelector('select')!;

    expect(input.options[input.selectedIndex].textContent).toBe('2');
    input.value = '0';
    input.dispatchEvent(new Event('change'));
    expect(ctx.onChange).toHaveBeenCalledWith(1);
  });

  it('password can ask for a confirmation', () => {
    const container = document.createElement('div');
    password(container, context(descriptor({ args: { confirm: true } })));

    expect(container.querySelectorAll('input[type="password"]')).toHaveLength(2);
  });

  it('reference lists the items of a backend endpoint', async () => {
    const container = document.createElement('div');
    const get = vi.fn(async () => [
      { id: 1, name: 'MiniLM' },
      { id: 2, name: 'Qwen' },
    ]);
    const ctx = context(descriptor({ type: 'integer', args: { endpoint: '/models/', value_key: 'id', label_key: 'name' } }), {
      api: { get: get as FieldContext['api']['get'] },
    });
    reference(container, ctx);
    await vi.waitFor(() => expect(container.querySelector('select')!.disabled).toBe(false));
    const input = container.querySelector('select')!;

    expect(get).toHaveBeenCalledWith('/models/');
    expect([...input.options].map((option) => option.textContent)).toEqual(['Select…', 'MiniLM', 'Qwen']);
    input.value = '1';
    input.dispatchEvent(new Event('change'));
    expect(ctx.onChange).toHaveBeenCalledWith(2);
  });
});
