import type { CallableItem } from '@/core/types/api';

export type CallableKind = 'tools' | 'hooks';

/** One Python file of an extension and the tools or hooks it defines. */
export interface CallableModule {
  module: string;
  filePath: string;
  items: CallableItem[];
}

/** One folder of agents/tools/ or agents/hook/: `default` ships with lazy_bird, `custom` is the user's. */
export interface CallableExtension {
  extension: string;
  modules: CallableModule[];
  items: CallableItem[];
}

/** Always listed, even empty, so users see where their own files go. */
const BUILT_IN = ['default', 'custom'];

/** Items grouped by extension (`default`, `custom`, then the others by name), then by module. */
export function groupByExtension(items: CallableItem[]): CallableExtension[] {
  const names = [...new Set(items.map((item) => item.extension))].filter((name) => !BUILT_IN.includes(name)).sort();
  return [...BUILT_IN, ...names].map((extension) => {
    const own = items.filter((item) => item.extension === extension);
    const modules = new Map<string, CallableModule>();
    for (const item of own) {
      const entry = modules.get(item.file_path) ?? { module: item.module, filePath: item.file_path, items: [] };
      entry.items.push(item);
      modules.set(item.file_path, entry);
    }
    return { extension, items: own, modules: [...modules.values()].sort((a, b) => a.module.localeCompare(b.module)) };
  });
}

export type SelectionState = 'none' | 'some' | 'all';

/** How many of `ids` are in `selected`: none, some or all (an empty group counts as none). */
export function selectionState(ids: string[], selected: string[]): SelectionState {
  const count = ids.filter((id) => selected.includes(id)).length;
  if (count === 0) return 'none';
  return count === ids.length ? 'all' : 'some';
}

/** Select or deselect `ids` at once; newly selected ids go at the end, in the given order. */
export function setSelected(selected: string[], ids: string[], on: boolean): string[] {
  if (!on) return selected.filter((id) => !ids.includes(id));
  return [...selected, ...ids.filter((id) => !selected.includes(id))];
}
