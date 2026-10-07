import { useEffect, useRef, useState } from 'react';
import { request } from '@/api/client';
import { fieldLoader } from '@/core/fields/loader';
import { renderHtmlField } from '@/core/fields/html';
import type { FieldApi, FieldDescriptor, KwargsKey, SettingsValues } from '@/core/fields/types';

type Loader = Pick<typeof fieldLoader, 'load'>;

const fieldApi: FieldApi = { get: (path) => request(path) };

interface SettingsFieldProps {
  name: string;
  descriptor: FieldDescriptor;
  initialValue: unknown;
  error?: string;
  onValueChange: (value: unknown) => void;
  loader: Loader;
}

function SettingsField({ name, descriptor, initialValue, error, onValueChange, loader }: SettingsFieldProps) {
  const container = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onValueChange);
  const initialRef = useRef(initialValue);
  const [loadError, setLoadError] = useState<string | null>(null);
  onChangeRef.current = onValueChange;
  const argsKey = JSON.stringify(descriptor.args ?? {});

  useEffect(() => {
    const node = container.current;
    if (!node) return;
    let cancelled = false;
    let cleanup: void | (() => void);
    const context = {
      name,
      value: initialRef.current,
      descriptor,
      args: descriptor.args ?? {},
      onChange: (value: unknown) => onChangeRef.current(value),
      api: fieldApi,
    };
    setLoadError(null);
    if (!descriptor.default_field) {
      cleanup = renderHtmlField(node, context);
    } else {
      loader
        .load(descriptor.content)
        .then((render) => {
          if (!cancelled) cleanup = render(node, context);
        })
        .catch((reason: unknown) => {
          if (!cancelled) setLoadError(reason instanceof Error ? reason.message : String(reason));
        });
    }
    return () => {
      cancelled = true;
      if (typeof cleanup === 'function') cleanup();
      node.replaceChildren();
    };
    // The DOM widget owns its state: it is rebuilt only when its definition changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, descriptor.content, descriptor.default_field, argsKey, loader]);

  return (
    <div className="form-group settings-field" data-field={name}>
      <label className="form-label" htmlFor={`field-${name}`}>
        {descriptor.title}
        {descriptor.required && <span className="settings-required" aria-label="required"> *</span>}
      </label>
      <div ref={container} className="settings-field-control" />
      {descriptor.description && descriptor.content !== 'default.basic.checkbox' && (
        <div className="form-hint">{descriptor.description}</div>
      )}
      {loadError && <div className="form-error">Field unavailable: {loadError}</div>}
      {error && <div className="form-error" role="alert">{error}</div>}
    </div>
  );
}

export interface SettingsFormProps {
  /** Descriptors returned by the backend (`kwargs_key`). */
  kwargsKey: KwargsKey;
  /** Initial values; re-key the form to load other values. */
  values: SettingsValues;
  onChange: (values: SettingsValues) => void;
  /** Messages per attribute, e.g. `ApiError.fieldErrors`. */
  errors?: Record<string, string>;
  loader?: Loader;
}

/** Form generated from an extension settings model (engines, tools, hooks). */
export function SettingsForm({ kwargsKey, values, onChange, errors = {}, loader = fieldLoader }: SettingsFormProps) {
  const current = useRef<SettingsValues>({ ...values });
  const entries = Object.entries(kwargsKey);
  const generalError = errors.__root__;

  if (entries.length === 0) {
    return <p className="form-hint">This extension has no settings.</p>;
  }

  const update = (name: string, value: unknown) => {
    const next = { ...current.current };
    if (value === undefined) delete next[name];
    else next[name] = value;
    current.current = next;
    onChange(next);
  };

  return (
    <div className="settings-form">
      {generalError && <div className="alert alert-error">{generalError}</div>}
      {entries.map(([name, descriptor]) => (
        <SettingsField
          key={name}
          name={name}
          descriptor={descriptor}
          initialValue={values[name]}
          error={errors[name]}
          loader={loader}
          onValueChange={(value) => update(name, value)}
        />
      ))}
    </div>
  );
}
