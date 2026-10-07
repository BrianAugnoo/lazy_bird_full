import { describe, expect, it } from 'vitest';
import { formatValue, parseValue, rowsToObject } from './keyValue';

describe('key/value rows', () => {
  it('keeps JSON-looking values typed and the rest as text', () => {
    expect(parseValue('42')).toBe(42);
    expect(parseValue('true')).toBe(true);
    expect(parseValue('[1, 2]')).toEqual([1, 2]);
    expect(parseValue('{"a": 1}')).toEqual({ a: 1 });
    expect(parseValue('hello')).toBe('hello');
    expect(parseValue('{broken')).toBe('{broken');
  });

  it('shows non-text values as JSON', () => {
    expect(formatValue('x')).toBe('x');
    expect(formatValue({ a: 1 })).toBe('{"a":1}');
  });

  it('drops rows without a key', () => {
    expect(rowsToObject([{ key: ' workspace ', value: 'lazy' }, { key: '', value: 'ignored' }])).toEqual({ workspace: 'lazy' });
  });
});
