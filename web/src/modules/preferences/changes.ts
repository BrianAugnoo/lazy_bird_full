import type { Preferences } from '@/core/types/api';

/** Changed keys only, per section. */
export function changedPreferences(saved: Preferences, draft: Preferences): Preferences {
  const changes: Preferences = {};
  for (const [section, values] of Object.entries(draft)) {
    for (const [key, value] of Object.entries(values)) {
      if (JSON.stringify(saved[section]?.[key]) !== JSON.stringify(value)) (changes[section] ??= {})[key] = value;
    }
  }
  return changes;
}
