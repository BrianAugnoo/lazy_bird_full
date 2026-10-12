import type { UserIn, UserOut } from '@/core/types/api';

/** The form keeps the age as text while it is typed; see `payloadOf`. */
export interface UserDraft {
  name: string;
  description: string;
  profession: string;
  email: string;
  age: string;
  /** Best mastered first. */
  languages: string[];
}

export const emptyDraft: UserDraft = { name: '', description: '', profession: '', email: '', age: '', languages: [] };

export const draftOf = (user: UserOut): UserDraft => ({
  name: user.name,
  description: user.description ?? '',
  profession: user.profession ?? '',
  email: user.email ?? '',
  age: user.age === null ? '' : String(user.age),
  languages: user.languages,
});

const orNull = (text: string) => text.trim() || null;

export const payloadOf = (draft: UserDraft): UserIn => ({
  name: draft.name.trim(),
  description: orNull(draft.description),
  profession: orNull(draft.profession),
  email: orNull(draft.email),
  age: draft.age.trim() === '' ? null : Number(draft.age),
  languages: draft.languages,
});

/** Only what differs from the saved user, so an edit never overwrites other changes. */
export function changesOf(user: UserOut, draft: UserDraft): Partial<UserIn> {
  const next = payloadOf(draft);
  const changes: Partial<UserIn> = {};
  for (const key of Object.keys(next) as Array<keyof UserIn>) {
    if (JSON.stringify(next[key]) !== JSON.stringify(user[key])) Object.assign(changes, { [key]: next[key] });
  }
  return changes;
}

/** Adds a language at the end (the least mastered), ignoring blanks and ones already listed. */
export function addLanguage(languages: string[], name: string): string[] {
  const language = name.trim();
  if (!language || languages.some((item) => item.toLowerCase() === language.toLowerCase())) return languages;
  return [...languages, language];
}

/** Moves a language one place toward the best (`-1`) or the worst (`1`). */
export function moveLanguage(languages: string[], index: number, step: -1 | 1): string[] {
  const target = index + step;
  if (target < 0 || target >= languages.length) return languages;
  const next = [...languages];
  [next[index], next[target]] = [next[target], next[index]];
  return next;
}
