/**
 * Hash router: the location is `#/{page}?key=value`, so reloading keeps the page and
 * links can point inside a page (e.g. `#/chat?conversation=3`).
 */
import { useSyncExternalStore } from 'react';

export interface Route {
  page: string;
  params: Record<string, string>;
}

export function parseHash(hash: string): Route {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const params: Record<string, string> = {};
  new URLSearchParams(query).forEach((value, key) => {
    params[key] = value;
  });
  return { page: path || '', params };
}

export function buildHash(page: string, params: Record<string, string | number | null | undefined> = {}): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined && value !== '') query.set(key, String(value));
  }
  const text = query.toString();
  return `#/${page}${text ? `?${text}` : ''}`;
}

export function navigate(page: string, params: Record<string, string | number | null | undefined> = {}): void {
  const next = buildHash(page, params);
  if (window.location.hash !== next) window.location.hash = next;
}

/** Change some params of the current page without adding a history entry. */
export function setParams(changes: Record<string, string | number | null | undefined>): void {
  const current = parseHash(window.location.hash);
  const next = buildHash(current.page, { ...current.params, ...changes });
  window.history.replaceState(null, '', next);
  window.dispatchEvent(new HashChangeEvent('hashchange'));
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

export function useRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash, () => '');
  return parseHash(hash);
}
