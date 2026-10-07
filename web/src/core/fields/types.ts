/**
 * Contract of extension settings fields.
 *
 * The backend describes every attribute of an extension `*Settings` model in a
 * `kwargs_key` map (see `lazy_bird/extension/settings.py`). Each descriptor says
 * how to render the attribute:
 *
 * - `default_field: true`  -> `content` is `"{extension}.{file}.{function}"`, a
 *   function exported by `src/modules/fields/{extension}/{file}.ts`, called with `args`;
 * - `default_field: false` -> `content` is an HTML snippet (see `renderHtmlField`).
 */

export type FieldValueType = 'string' | 'integer' | 'number' | 'boolean' | 'array' | 'object' | 'any';

export interface FieldDescriptor {
  default_field: boolean;
  content: string;
  args: Record<string, unknown>;
  type: FieldValueType;
  required: boolean;
  nullable: boolean;
  default: unknown;
  title: string;
  description: string | null;
}

export type KwargsKey = Record<string, FieldDescriptor>;

/** Settings values keyed by attribute; a missing key means "use the default". */
export type SettingsValues = Record<string, unknown>;

export interface FieldApi {
  /** GET a backend path (e.g. `/models/`) and return its JSON body. */
  get<T = unknown>(path: string): Promise<T>;
}

export interface FieldContext {
  /** Attribute name in the settings model. */
  name: string;
  /** Current value, `undefined` when the attribute is not set. */
  value: unknown;
  descriptor: FieldDescriptor;
  /** Shortcut for `descriptor.args`. */
  args: Record<string, unknown>;
  /** Report a new value; `undefined` removes the attribute so its default applies. */
  onChange: (value: unknown) => void;
  api: FieldApi;
}

/**
 * Renders one settings attribute into `container` (plain DOM, no framework).
 * It may return a cleanup function, called when the field is unmounted.
 */
export type FieldRenderer = (container: HTMLElement, context: FieldContext) => void | (() => void);
