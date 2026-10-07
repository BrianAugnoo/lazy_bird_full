import { vi } from 'vitest';

type Reply = unknown | { status: number; body: unknown };

/**
 * Mock `fetch` with replies keyed by `"METHOD /path"` (the `/api` prefix and the
 * query string are ignored). Returns a function giving the JSON bodies sent to a key.
 */
export function mockApi(routes: Record<string, Reply | ((body: unknown) => Reply)>) {
  const sent: Record<string, unknown[]> = {};
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = new URL(String(input), 'http://test');
    const path = url.pathname.replace(/^\/api/, '');
    const key = `${init?.method ?? 'GET'} ${path}`;
    const body = typeof init?.body === 'string' ? JSON.parse(init.body) : init?.body;
    (sent[key] ??= []).push(body);
    if (!(key in routes)) throw new Error(`Unexpected request ${key}`);
    const route = routes[key];
    let reply = typeof route === 'function' ? (route as (body: unknown) => Reply)(body) : route;
    let status = 200;
    if (reply && typeof reply === 'object' && 'status' in reply && 'body' in reply) {
      status = (reply as { status: number }).status;
      reply = (reply as { body: unknown }).body;
    }
    return {
      ok: status < 400,
      status,
      statusText: '',
      headers: new Headers({ 'content-type': 'application/json' }),
      json: async () => reply,
      text: async () => JSON.stringify(reply),
    } as Response;
  });
  return (key: string) => sent[key] ?? [];
}
