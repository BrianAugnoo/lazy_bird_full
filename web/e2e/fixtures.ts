import type { Page } from '@playwright/test';

const date = '2026-10-13T08:00:00Z';
export const file = (id: number, name: string, directory = '') => ({ id, name, extension: '.md', directory, relative_path: `${directory ? directory + '/' : ''}${name}.md`, path: `/storage/${name}.md`, size: 2400, content_hash: 'test', missing: false, chunk_count: 4, state: 'ready', processing: [] });
const agent = { id: 1, session_id: 1, name: 'Research assistant', description: 'Think clearly. Find the useful details. Turn them into a plan.', instructions: '', instruction_fulls: [], instruction_subs: [], tools: [], hooks: [], skills: [], master: true, meta: null, preset: null, sub_agents_ids: [], parent_agents_ids: [], valid: true, errors: {} };
const conversation = { id: 1, agent_id: 1, title: 'Project notes', created_at: date, updated_at: date, running: false, runnable: false };
export const user = { id: 1, name: 'Augnoo', description: null, profession: 'Builder', email: null, age: null, languages: ['English'], meta: null, created_at: date, updated_at: date };
const callable = { id: 'default-files-read_file', name: 'read_file', description: 'Read a document from your workspace.', extension: 'default', module: 'files', file_path: 'default/files', class_name: null, needs_settings: false, meta_params: [], required_meta: [], accepts_any_meta: false, parameters: { type: 'object', properties: { path: { type: 'string', description: 'Document path' } }, required: ['path'] } };
const preset = { id: 'default/research', name: 'research', extension: 'default', editable: false, valid: true, errors: {}, data: { name: 'research', description: 'A focused research assistant.', tools: [callable.id], agents: ['default/research'], master: 'default/research' } };
const adapter = { selected: true, settings: {}, kwargs_key: {}, messages: { initialize: 'Local storage', disconnect: '' } };

export async function mockBackend(page: Page, mode: 'loaded' | 'empty' | 'error' | 'loading' = 'loaded') {
  let files = [file(1, 'README'), file(2, 'Project brief'), file(3, 'Archive notes', 'docs')];
  const calls: Array<{ method: string; path: string; body: unknown }> = [];
  const sockets: Array<{ url: string; closed: boolean; send: (data: string) => void }> = [];
  const responses: Record<string, unknown> = {
    '/health': { ready: true, version: '1.0' },
    '/profile/': { user_id: mode === 'empty' ? null : 1, user: mode === 'empty' ? null : user },
    '/sessions/': [{ id: 1, title: 'Project workspace', meta: {}, created_at: date, updated_at: date }],
    '/agents/session/1': [agent], '/agents/': [agent], '/agents/1/tools': [callable],
    '/conversations/': [conversation],
    '/files/directories': ['docs', 'archive', 'docs/old'],
    '/tools/': [callable], '/tools/settings': [], '/hooks/': [{ ...callable, id: 'default-context-date', name: 'date', description: 'Add the current date to the conversation.', parameters: null }], '/hooks/settings': [],
    '/agent-presets/': [preset], '/session-presets/': [preset],
    '/instructions/full/': [{ id: 'default/research', name: 'research', extension: 'default', editable: false }], '/instructions/sub/': [],
    '/skills/': [], '/users/': [user], '/tasks/': [], '/tasks/kinds': [],
    '/models/': [], '/models/hub/status': { authenticated: false, user: null },
    '/embedding-engines/': [], '/embedding-presets/': [], '/cross-encoder-engines/': [], '/cross-encoder-presets/': [], '/inference-engines/': [], '/inference-presets/': [],
    '/databases/': { available: { sql: { SQLite: adapter }, vector: { Local: adapter } }, selected_sql: 'SQLite', selected_vector: 'Local' }, '/databases/vector/tables': [],
    '/preferences/': { files: { automatic: true } },
    '/preferences/form': { files: { title: 'File processing', kwargs_key: { automatic: { default_field: true, content: 'default.basic.checkbox', args: {}, type: 'boolean', title: 'Process files automatically', default: true } } } },
    '/api-keys/': [], '/extensions/failures': [], '/logs/': [], '/logs/tracing': { enabled: false },
  };
  await page.route(url => url.pathname.startsWith('/api/') || url.port === '8000', async route => {
    const request = route.request(); const url = new URL(request.url());
    const path = url.pathname.replace(/^\/api/, '');
    let body: unknown = null; try { body = request.postDataJSON(); } catch { /* Upload requests are multipart. */ }
    calls.push({ method: request.method(), path: path + url.search, body });
    if (path === '/schemas') { await route.fulfill({ contentType: 'text/html', body: '<html><body style="background:#09090b;color:#ededf0;font-family:system-ui"><h1>Data model</h1><p>Schema endpoint frame</p></body></html>' }); return; }
    if (mode === 'loading' && path !== '/health' && path !== '/profile/') await new Promise(resolve => setTimeout(resolve, 800));
    if (mode === 'error' && path !== '/health' && path !== '/profile/') { await route.fulfill({ status: 503, json: { error: { code: 'unavailable', message: 'The server is temporarily unavailable.', details: {} } } }); return; }
    if (/^\/files\/\d+$/.test(path) && request.method() === 'PATCH') {
      const id = Number(path.split('/').pop()); files = files.map(item => item.id === id ? { ...item, directory: (body as { dir?: string })?.dir ?? item.directory } : item);
      await route.fulfill({ json: files.find(item => item.id === id) }); return;
    }
    if (/^\/files\/\d+\/content$/.test(path)) { await route.fulfill({ json: '# Project notes\n\nKeep the interface calm and the work in focus.\n' }); return; }
    if (/^\/files\/\d+$/.test(path)) { await route.fulfill({ json: files.find(item => item.id === Number(path.split('/').pop())) }); return; }
    if (path === '/files/directory' && request.method() === 'PATCH') { await route.fulfill({ json: { path: url.searchParams.get('destination') } }); return; }
    let result = path === '/files/' ? files : responses[path] ?? [];
    if (mode === 'empty' && Array.isArray(result)) result = [];
    await route.fulfill({ json: result });
  });
  await page.routeWebSocket('**/ws/**', socket => {
    const entry = { url: socket.url(), closed: false, send: (data: string) => socket.send(data) }; sockets.push(entry);
    socket.onClose(() => { entry.closed = true; });
    if (socket.url().includes('/tasks')) socket.send(JSON.stringify({ type: 'snapshot', tasks: [], kinds: [], resources: { capacity: {}, used: {}, holders: {}, models: [] } }));
    else socket.send(JSON.stringify({ type: 'conversation', conversation: { ...conversation, messages: [
      { id: 1, conversation_id: 1, role: 'user', content: 'Review the project notes and outline the next steps.', hooks: {}, meta: null, created_at: date, updated_at: date },
      { id: 2, conversation_id: 1, role: 'assistant', content: 'Here is a focused plan for the next release.\n\n1. Review the requirements and confirm the dependencies.\n2. Break the work into small, verifiable changes.\n3. Check the result and document the decisions.', hooks: {}, meta: null, created_at: date, updated_at: date },
    ] } }));
  });
  return { calls, sockets };
}
