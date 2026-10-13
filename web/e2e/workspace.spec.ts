import { test, expect } from '@playwright/test';
import { mockBackend } from './fixtures';
import AxeBuilder from '@axe-core/playwright';

test('menu navigation retains drafts, editor content, scroll and live connections in one tab', async ({ page }) => {
  const backend = await mockBackend(page);
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message)); page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await page.goto('/#/chat?session=1&conversation=1');
  await expect(page.getByText('Here is a focused plan', { exact: false })).toBeVisible();
  const live = backend.sockets.find(socket => socket.url.includes('/conversations/1') && !socket.closed);
  expect(live).toBeDefined();
  const socketCount = backend.sockets.length;
  await page.screenshot({ path: '../web_design/qa-conversation-1440.png' });
  live?.send(JSON.stringify({ type: 'message', message: { id: 3, conversation_id: 1, role: 'assistant', content: Array.from({ length: 60 }, (_, index) => `Project detail ${index + 1}.`).join('\n\n'), hooks: {}, meta: null, created_at: '2026-10-13T08:00:00Z', updated_at: '2026-10-13T08:00:00Z' } }));
  await expect(page.getByText('Project detail 60.', { exact: true })).toBeVisible();
  await page.locator('.chat-scroll').evaluate(node => { node.scrollTop = 120; node.dispatchEvent(new Event('scroll')); });
  const scrollTop = await page.locator('.chat-scroll').evaluate(node => node.scrollTop);
  expect(scrollTop).toBe(120);
  await page.getByRole('textbox', { name: 'Message', exact: true }).fill('Keep this draft');
  await page.getByRole('link', { name: 'Files', exact: true }).click();
  await expect(page.getByRole('button', { name: 'README.md' })).toBeVisible();
  await page.getByRole('button', { name: 'README.md' }).click();
  await page.getByRole('textbox', { name: 'Markdown source' }).fill('Unsaved editor notes');
  await page.screenshot({ path: '../web_design/qa-editor-1440.png' });
  live?.send(JSON.stringify({ type: 'token', delta: 'Progress received while another tab is active.' }));
  await page.getByRole('link', { name: 'Chat', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Message', exact: true })).toHaveValue('Keep this draft');
  await expect(page.getByText('Progress received while another tab is active.', { exact: true })).toBeVisible();
  expect(await page.locator('main:not([hidden]) .chat-scroll').evaluate(node => node.scrollTop)).toBe(scrollTop);
  expect(live?.closed).toBe(false);
  expect(backend.sockets).toHaveLength(socketCount);
  await expect(page.getByRole('tab')).toHaveCount(1);
  await page.getByRole('link', { name: 'Files', exact: true }).click();
  await expect(page.getByRole('textbox', { name: 'Markdown source' })).toHaveValue('Unsaved editor notes');
  await page.getByRole('button', { name: 'Close Files tab' }).click();
  await expect(page.getByRole('dialog', { name: 'Close this tab?' })).toBeVisible();
  await page.getByRole('button', { name: 'Cancel', exact: true }).click();
  expect(errors).toEqual([]);
});

test('profile menu, keyboard navigation and coming-soon controls', async ({ page }) => {
  const backend = await mockBackend(page);
  await page.goto('/#/chat?session=1&conversation=1');
  await page.getByRole('button', { name: /Augnoo Your workspace/ }).click();
  await expect(page.getByRole('dialog', { name: 'Workspace settings' })).toBeVisible();
  await page.getByRole('button', { name: 'Preferences', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Preferences' })).toBeVisible();
  await page.keyboard.press('Control+k');
  await page.getByRole('searchbox', { name: 'Search pages' }).fill('tools');
  await page.getByRole('button', { name: 'Tools Agents' }).click();
  await expect(page.getByRole('heading', { name: 'Tools', exact: true })).toBeVisible();
  await expect(page.getByRole('tab')).toHaveCount(1);
  await page.getByRole('link', { name: 'Chat', exact: true }).click();
  await page.getByRole('button', { name: 'Add to message', exact: true }).click();
  await expect(page.getByRole('dialog', { name: 'Add to message' }).getByText('Coming soon')).toHaveCount(3);
  await page.screenshot({ path: '../web_design/qa-composer-menu.png' });
  await expect(page.getByRole('button', { name: /Create an image/ })).toHaveAttribute('aria-disabled', 'true');
  const count = backend.calls.length;
  // The UI is explicitly unavailable; no command is wired to any of these controls.
  await page.getByRole('button', { name: /Create an image/ }).dispatchEvent('click');
  expect(backend.calls.length).toBe(count);
  await page.keyboard.press('Escape');
  await expect(page.getByRole('button', { name: 'Add to message', exact: true })).toBeFocused();
  await expect(page.getByRole('button', { name: 'Audio — coming soon' })).toHaveAttribute('aria-disabled', 'true');
});

test('dragging files and folders uses existing move endpoints and rejects descendant moves', async ({ page }) => {
  const backend = await mockBackend(page);
  await page.goto('/#/files');
  await expect(page.getByRole('button', { name: 'README.md' })).toBeVisible();
  const transfer = await page.evaluateHandle(() => new DataTransfer());
  await page.getByRole('row').filter({ hasText: 'README.md' }).dispatchEvent('dragstart', { dataTransfer: transfer });
  const folder = page.getByRole('row').filter({ has: page.getByRole('button', { name: 'docs', exact: true }) });
  await folder.dispatchEvent('dragover', { dataTransfer: transfer });
  await expect(folder).toHaveClass(/is-drop-target/);
  await folder.dispatchEvent('drop', { dataTransfer: transfer });
  await expect(page.getByRole('button', { name: 'README.md' })).toHaveCount(0);
  expect(backend.calls.some(call => call.method === 'PATCH' && call.path === '/files/1' && JSON.stringify(call.body) === '{"dir":"docs"}')).toBe(true);
  const transferFolder = await page.evaluateHandle(() => new DataTransfer());
  await folder.dispatchEvent('dragstart', { dataTransfer: transferFolder });
  const archive = page.getByRole('row').filter({ has: page.getByRole('button', { name: 'archive', exact: true }) });
  await archive.dispatchEvent('dragover', { dataTransfer: transferFolder });
  await archive.dispatchEvent('drop', { dataTransfer: transferFolder });
  await expect.poll(() => backend.calls.some(call => call.method === 'PATCH' && call.path.includes('/files/directory?source=docs&destination=archive%2Fdocs'))).toBe(true);
});

test('tool schema and library search, collapsing and reopen', async ({ page }) => {
  await mockBackend(page); await page.goto('/#/tools');
  await page.getByText('JSON schema', { exact: true }).click();
  await expect(page.locator('.schema-details pre')).toContainText('"required"');
  await page.getByRole('searchbox', { name: 'Search tools' }).fill('missing');
  await expect(page.getByText('No tools match “missing”.')).toBeVisible();
  await page.getByRole('button', { name: 'Extensions', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Tools extensions' })).toHaveCount(0);
  await page.getByRole('button', { name: 'Show', exact: true }).click();
  await expect(page.getByRole('navigation', { name: 'Tools extensions' })).toBeVisible();
});

test('navigation and chat panels close and reopen on desktop and mobile', async ({ page }) => {
  await mockBackend(page); await page.goto('/#/chat?session=1&conversation=1');
  await page.getByRole('button', { name: 'Collapse navigation' }).click();
  await expect(page.getByRole('complementary', { name: 'Main navigation' })).toBeHidden();
  await page.getByRole('button', { name: 'Show navigation', exact: true }).click();
  await expect(page.getByRole('complementary', { name: 'Main navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Hide sessions and conversations' }).first().click();
  await expect(page.getByRole('complementary', { name: 'Sessions and conversations' })).toBeHidden();
  await page.getByRole('button', { name: 'Show sessions and conversations' }).click();
  await expect(page.getByRole('complementary', { name: 'Sessions and conversations' })).toBeVisible();
  await page.setViewportSize({ width: 390, height: 900 });
  // Collapse inside the mobile overlay must dismiss it, not leave an invisible focus region.
  await page.getByRole('button', { name: 'Collapse navigation' }).click();
  await expect(page.locator('.sidebar')).toHaveAttribute('inert', '');
  await page.getByRole('button', { name: 'Show navigation', exact: true }).click();
  await expect(page.getByRole('complementary', { name: 'Main navigation' })).toBeVisible();
  await page.getByRole('button', { name: 'Close navigation' }).click();
  await expect(page.locator('.sidebar')).toHaveAttribute('inert', '');
  await page.getByRole('button', { name: 'Show navigation', exact: true }).click();
  await page.keyboard.press('Escape');
  await expect(page.locator('.sidebar')).toHaveAttribute('inert', '');
});

const pages = ['chat', 'files', 'search', 'tools', 'hooks', 'skills', 'instructions', 'agent-presets', 'session-presets', 'models', 'embedding', 'cross-encoder', 'inference', 'tasks', 'users', 'databases', 'api-keys', 'preferences', 'logs', 'extensions', 'schema'];
for (const width of [1440, 390]) test(`all registered screens render cleanly at ${width}px`, async ({ page }) => {
  const errors: string[] = []; page.on('pageerror', error => errors.push(error.message)); page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  await mockBackend(page); await page.setViewportSize({ width, height: 900 });
  for (const name of pages) {
    await page.goto('/#/' + name); await expect(page.locator('main:not([hidden])')).toBeVisible();
    await expect(page.locator('main:not([hidden]) .state-loading')).toHaveCount(0);
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    if (['chat', 'files', 'tools', 'instructions', 'preferences'].includes(name)) await page.screenshot({ path: `../web_design/qa-${name}-${width}.png` });
  }
  expect(errors).toEqual([]);
});

test('empty, loading and recoverable error states', async ({ browser, baseURL }) => {
  for (const mode of ['empty', 'loading', 'error'] as const) {
    const context = await browser.newContext(); const page = await context.newPage(); await mockBackend(page, mode);
    for (const name of ['chat', 'files', 'tools', 'hooks', 'skills', 'instructions', 'agent-presets', 'session-presets', 'models', 'embedding', 'cross-encoder', 'inference', 'users', 'databases', 'preferences', 'api-keys', 'logs', 'extensions']) {
      await page.goto(baseURL + '/#/' + name);
      if (mode === 'loading') await expect(page.locator('main:not([hidden]) > .content-viewport:not([hidden]) .state-loading').first()).toBeVisible();
      else if (mode === 'error') await expect(page.locator('main:not([hidden]) > .content-viewport:not([hidden])').getByText('The server is temporarily unavailable.').first()).toBeVisible();
      else await expect(page.locator('main:not([hidden]) .state-loading')).toHaveCount(0);
      if (name === 'files') await page.screenshot({ path: `../web_design/qa-files-${mode}.png` });
    }
    await context.close();
  }
});

test('contrast and accessible controls on primary screens', async ({ page }) => {
  await mockBackend(page);
  for (const name of ['files', 'chat', 'tools', 'instructions', 'agent-presets', 'session-presets', 'users', 'preferences', 'search', 'logs']) {
    await page.goto('/#/' + name);
    await expect(page.locator('main:not([hidden]) .state-loading')).toHaveCount(0);
    const result = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa']).analyze();
    expect(result.violations.map(item => ({ id: item.id, nodes: item.nodes.map(node => node.target) })), name).toEqual([]);
  }
});
