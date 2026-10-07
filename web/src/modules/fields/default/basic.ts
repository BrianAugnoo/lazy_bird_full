/**
 * Default settings widgets, referenced as `default.basic.<function>` in `kwargs_key`.
 *
 * Every export is a `FieldRenderer`: it builds plain DOM inside `container`, reports
 * changes through `context.onChange` and may return a cleanup function.
 */
import { coerceFieldValue, formatFieldValue } from '@/core/fields/html';
import type { FieldContext, FieldRenderer } from '@/core/fields/types';

function element<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attributes: Record<string, string> = {},
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [name, value] of Object.entries(attributes)) node.setAttribute(name, value);
  return node;
}

function placeholder(context: FieldContext): string {
  const fallback = context.descriptor.default;
  if (fallback !== null && fallback !== undefined && fallback !== '') return `Default: ${formatFieldValue(fallback, context.descriptor.type)}`;
  return context.descriptor.required ? 'Required' : 'Optional';
}

function textLike(type: 'text' | 'password' | 'email' | 'url'): FieldRenderer {
  return (container, context) => {
    const input = element('input', { type, class: 'form-input', id: `field-${context.name}`, placeholder: placeholder(context) });
    input.value = formatFieldValue(context.value, 'string');
    if (type === 'password') input.autocomplete = 'new-password';
    const onInput = () => context.onChange(input.value === '' ? undefined : input.value);
    input.addEventListener('input', onInput);
    container.append(input);
    if (type !== 'password' || !context.args.confirm) return () => input.removeEventListener('input', onInput);

    const confirmation = element('input', { type: 'password', class: 'form-input', placeholder: 'Confirm', autocomplete: 'new-password' });
    const check = () => confirmation.setCustomValidity(confirmation.value === input.value ? '' : 'The values do not match');
    confirmation.addEventListener('input', check);
    input.addEventListener('input', check);
    container.append(confirmation);
    return () => {
      input.removeEventListener('input', onInput);
      input.removeEventListener('input', check);
      confirmation.removeEventListener('input', check);
    };
  };
}

export const text = textLike('text');
export const password = textLike('password');
export const email = textLike('email');
export const url = textLike('url');

export const textarea: FieldRenderer = (container, context) => {
  const input = element('textarea', { class: 'form-textarea', rows: String(context.args.rows ?? 4), placeholder: placeholder(context) });
  input.value = formatFieldValue(context.value, 'string');
  input.addEventListener('input', () => context.onChange(input.value === '' ? undefined : input.value));
  container.append(input);
};

function numeric(kind: 'integer' | 'number'): FieldRenderer {
  return (container, context) => {
    const input = element('input', { type: 'number', class: 'form-input', placeholder: placeholder(context) });
    if (kind === 'integer') input.step = '1';
    else input.step = 'any';
    if (typeof context.args.min === 'number') input.min = String(context.args.min);
    if (typeof context.args.max === 'number') input.max = String(context.args.max);
    input.value = formatFieldValue(context.value, kind);
    input.addEventListener('input', () => {
      try {
        context.onChange(coerceFieldValue(input.value, kind));
        input.setCustomValidity('');
      } catch (error) {
        input.setCustomValidity(error instanceof Error ? error.message : 'Invalid number');
      }
    });
    container.append(input);
  };
}

export const integer = numeric('integer');
export const number = numeric('number');

export const checkbox: FieldRenderer = (container, context) => {
  const label = element('label', { class: 'field-checkbox' });
  const input = element('input', { type: 'checkbox' });
  input.checked = Boolean(context.value ?? context.descriptor.default);
  input.addEventListener('change', () => context.onChange(input.checked));
  label.append(input, document.createTextNode(context.descriptor.description ?? 'Enabled'));
  container.append(label);
};

function fillOptions(select: HTMLSelectElement, options: Array<{ value: unknown; label: string }>, context: FieldContext) {
  select.replaceChildren();
  const empty = element('option', { value: '' });
  empty.textContent = context.descriptor.required ? 'Select…' : placeholder(context);
  select.append(empty);
  options.forEach((option, index) => {
    const node = element('option', { value: String(index) });
    node.textContent = option.label;
    if (context.value !== undefined && option.value === context.value) node.selected = true;
    select.append(node);
  });
}

function bindSelect(select: HTMLSelectElement, options: () => Array<{ value: unknown }>, context: FieldContext) {
  select.addEventListener('change', () => {
    context.onChange(select.value === '' ? undefined : options()[Number(select.value)]?.value);
  });
}

export const select: FieldRenderer = (container, context) => {
  const options = ((context.args.options as unknown[]) ?? []).map((value) => ({ value, label: String(value) }));
  const input = element('select', { class: 'form-select' });
  fillOptions(input, options, context);
  bindSelect(input, () => options, context);
  container.append(input);
};

/**
 * A choice among the items of a backend list endpoint.
 * args: `endpoint` (GET path returning a JSON array), `value_key`, `label_key`.
 */
export const reference: FieldRenderer = (container, context) => {
  const endpoint = String(context.args.endpoint ?? '');
  const valueKey = String(context.args.value_key ?? 'id');
  const labelKey = String(context.args.label_key ?? 'name');
  const input = element('select', { class: 'form-select' });
  input.disabled = true;
  fillOptions(input, [], context);
  const status = element('div', { class: 'form-hint' });
  status.textContent = 'Loading…';
  container.append(input, status);

  let options: Array<{ value: unknown; label: string }> = [];
  let active = true;
  bindSelect(input, () => options, context);
  context.api
    .get<Array<Record<string, unknown>>>(endpoint)
    .then((items) => {
      if (!active) return;
      options = (Array.isArray(items) ? items : []).map((item) => ({
        value: item[valueKey],
        label: String(item[labelKey] ?? item[valueKey]),
      }));
      fillOptions(input, options, context);
      input.disabled = false;
      status.textContent = options.length ? '' : 'Nothing to choose from yet.';
    })
    .catch((error: unknown) => {
      if (!active) return;
      status.textContent = error instanceof Error ? error.message : 'Could not load the choices.';
      status.className = 'form-error';
    });
  return () => {
    active = false;
  };
};

/** One string item per line. */
export const list: FieldRenderer = (container, context) => {
  const input = element('textarea', { class: 'form-textarea', rows: '3', placeholder: 'One item per line' });
  input.value = Array.isArray(context.value) ? context.value.join('\n') : '';
  input.addEventListener('input', () => {
    const items = input.value.split('\n').map((item) => item.trim()).filter(Boolean);
    context.onChange(items.length ? items : undefined);
  });
  container.append(input);
};

/** Free JSON value, validated while typing. */
export const json: FieldRenderer = (container, context) => {
  const input = element('textarea', { class: 'form-textarea field-json', rows: '4', spellcheck: 'false', placeholder: placeholder(context) });
  input.value = formatFieldValue(context.value, 'object');
  const hint = element('div', { class: 'form-error' });
  input.addEventListener('input', () => {
    try {
      context.onChange(coerceFieldValue(input.value, 'object'));
      hint.textContent = '';
    } catch {
      hint.textContent = 'Invalid JSON';
    }
  });
  container.append(input, hint);
};
