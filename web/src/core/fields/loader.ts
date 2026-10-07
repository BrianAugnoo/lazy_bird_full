import type { FieldRenderer } from './types';

/** Lazy importers keyed by file path, as returned by `import.meta.glob`. */
export type FieldModules = Record<string, () => Promise<Record<string, unknown>>>;

export class FieldLoadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'FieldLoadError';
  }
}

const FIELD_PATH = /^([A-Za-z0-9_-]+)\.([A-Za-z0-9_-]+)\.([A-Za-z_$][A-Za-z0-9_$]*)$/;

export interface FieldPath {
  extension: string;
  file: string;
  name: string;
}

/** Split `"{extension}.{file}.{function}"`; returns null when malformed. */
export function parseFieldPath(content: string): FieldPath | null {
  const match = FIELD_PATH.exec(content);
  return match ? { extension: match[1], file: match[2], name: match[3] } : null;
}

/** Build a loader resolving field functions from `src/modules/fields/{extension}/{file}.ts`. */
export function createFieldLoader(modules: FieldModules) {
  const byLocation = new Map<string, () => Promise<Record<string, unknown>>>();
  for (const [path, importer] of Object.entries(modules)) {
    const match = /\/fields\/([^/]+)\/([^/]+)\.ts$/.exec(path);
    if (match) byLocation.set(`${match[1]}/${match[2]}`, importer);
  }
  const cache = new Map<string, Promise<FieldRenderer>>();

  async function resolve(content: string): Promise<FieldRenderer> {
    const path = parseFieldPath(content);
    if (!path) {
      throw new FieldLoadError(`"${content}" is not a field function path ("{extension}.{file}.{function}").`);
    }
    const importer = byLocation.get(`${path.extension}/${path.file}`);
    if (!importer) {
      throw new FieldLoadError(
        `No field module src/modules/fields/${path.extension}/${path.file}.ts (needed by "${content}").`,
      );
    }
    const module = await importer();
    const renderer = module[path.name];
    if (typeof renderer !== 'function') {
      throw new FieldLoadError(`src/modules/fields/${path.extension}/${path.file}.ts does not export a function "${path.name}".`);
    }
    return renderer as FieldRenderer;
  }

  return {
    /** Load (once) the renderer named by a descriptor's `content`. */
    load(content: string): Promise<FieldRenderer> {
      let pending = cache.get(content);
      if (!pending) {
        pending = resolve(content);
        pending.catch(() => cache.delete(content));
        cache.set(content, pending);
      }
      return pending;
    },
    /** Every `{extension}/{file}` module the loader can see. */
    modules(): string[] {
      return [...byLocation.keys()].sort();
    },
  };
}

const discovered = import.meta.glob<Record<string, unknown>>([
  '/src/modules/fields/*/*.ts',
  '!/src/modules/fields/*/*.test.ts',
]);

export const fieldLoader = createFieldLoader(discovered);
