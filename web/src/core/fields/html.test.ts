import { describe, expect, it, vi } from 'vitest';
import { coerceFieldValue, renderHtmlField } from './html';
import type { FieldContext, FieldDescriptor } from './types';

const descriptor = (overrides: Partial<FieldDescriptor> = {}): FieldDescriptor => ({
  default_field: false,
  content: '<label>Port <input data-field-input></label>',
  args: {},
  type: 'integer',
  required: false,
  nullable: false,
  default: null,
  title: 'Port',
  description: null,
  ...overrides,
});

const context = (d: FieldDescriptor, onChange = vi.fn(), value?: unknown): FieldContext => ({
  name: 'port',
  value,
  descriptor: d,
  args: d.args,
  onChange,
  api: { get: vi.fn() },
});

describe('coerceFieldValue', () => {
  it('converts by value type and unsets empty input', () => {
    expect(coerceFieldValue('42', 'integer')).toBe(42);
    expect(coerceFieldValue('4.5', 'number')).toBe(4.5);
    expect(coerceFieldValue('yes', 'boolean')).toBe(true);
    expect(coerceFieldValue('[1, 2]', 'array')).toEqual([1, 2]);
    expect(coerceFieldValue('  ', 'string')).toBeUndefined();
    expect(coerceFieldValue(' keep ', 'string')).toBe(' keep ');
  });

  it('throws on values that cannot be converted', () => {
    expect(() => coerceFieldValue('4.5', 'integer')).toThrow();
    expect(() => coerceFieldValue('{', 'object')).toThrow();
  });
});

describe('renderHtmlField', () => {
  it('reports the converted value of the marked input', () => {
    const container = document.createElement('div');
    const onChange = vi.fn();
    renderHtmlField(container, context(descriptor(), onChange, 8080));
    const input = container.querySelector('input')!;

    expect(input.value).toBe('8080');
    input.value = '9000';
    input.dispatchEvent(new Event('input'));
    expect(onChange).toHaveBeenLastCalledWith(9000);
  });

  it('strips scripts and inline handlers from extension HTML', () => {
    const container = document.createElement('div');
    renderHtmlField(container, context(descriptor({ content: '<input data-field-input onclick="alert(1)"><script>alert(2)</script>' })));

    expect(container.querySelector('script')).toBeNull();
    expect(container.querySelector('input')!.getAttribute('onclick')).toBeNull();
  });
});
