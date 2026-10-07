import DOMPurify from 'dompurify';
import type { FieldContext, FieldValueType } from './types';

/**
 * Convert the raw string of an input into the value type a descriptor expects.
 * Returns `undefined` for an empty input (the attribute is unset) and throws on
 * values that cannot be converted.
 */
export function coerceFieldValue(raw: string, type: FieldValueType): unknown {
  const text = raw.trim();
  if (text === '') return undefined;
  switch (type) {
    case 'integer': {
      if (!/^[-+]?\d+$/.test(text)) throw new Error('Expected a whole number');
      return Number.parseInt(text, 10);
    }
    case 'number': {
      const value = Number(text);
      if (Number.isNaN(value)) throw new Error('Expected a number');
      return value;
    }
    case 'boolean':
      return ['true', '1', 'yes', 'on'].includes(text.toLowerCase());
    case 'array':
    case 'object':
    case 'any':
      return JSON.parse(text);
    default:
      return raw;
  }
}

/** Format a value for display in a text input. */
export function formatFieldValue(value: unknown, type: FieldValueType): string {
  if (value === undefined || value === null) return '';
  if (type === 'array' || type === 'object' || type === 'any') return JSON.stringify(value, null, 2);
  return String(value);
}

/**
 * Render a custom HTML field (`default_field: false`).
 *
 * Contract for extension authors: the snippet must contain one form element
 * marked with `data-field-input` (otherwise the first input/select/textarea is
 * used). Its value is converted with the descriptor `type` and reported on every
 * `input`/`change` event. Scripts and inline event handlers are stripped.
 */
export function renderHtmlField(container: HTMLElement, context: FieldContext): () => void {
  container.innerHTML = DOMPurify.sanitize(context.descriptor.content);
  const input = container.querySelector<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>(
    '[data-field-input], input, select, textarea',
  );
  if (!input) return () => undefined;
  const type = context.descriptor.type;
  if (input instanceof HTMLInputElement && input.type === 'checkbox') {
    input.checked = Boolean(context.value ?? context.descriptor.default);
  } else {
    input.value = formatFieldValue(context.value, type);
  }
  const report = () => {
    if (input instanceof HTMLInputElement && input.type === 'checkbox') {
      context.onChange(input.checked);
      return;
    }
    try {
      context.onChange(coerceFieldValue(input.value, type));
      input.setCustomValidity('');
    } catch (error) {
      input.setCustomValidity(error instanceof Error ? error.message : 'Invalid value');
    }
  };
  input.addEventListener('input', report);
  input.addEventListener('change', report);
  return () => {
    input.removeEventListener('input', report);
    input.removeEventListener('change', report);
  };
}
