import { test, expect } from '@playwright/test';

test('read-only smoke against the running backend', async ({ page, request }) => {
  test.skip(process.env.LAZY_BIRD_LIVE_QA !== '1', 'Requires the local backend; fixtures cover normal CI.');
  const health = await request.get('/api/health');
  expect((await health.json()).ready).toBe(true);
  const errors: string[] = []; const failures: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
  page.on('response', response => { if (response.status() >= 400) failures.push(`${response.status()} ${new URL(response.url()).pathname}`); });
  for (const name of ['chat', 'files', 'search', 'tools', 'hooks', 'skills', 'instructions', 'agent-presets', 'session-presets', 'models', 'embedding', 'cross-encoder', 'inference', 'tasks', 'users', 'databases', 'api-keys', 'preferences', 'logs', 'extensions', 'schema']) {
    await page.goto('/#/' + name);
    await expect(page.locator('main:not([hidden])')).toBeVisible();
    await expect(page.locator('main:not([hidden]) .state-loading')).toHaveCount(0);
    await expect(page.locator('main:not([hidden]) .state-error')).toHaveCount(0);
  }
  expect(failures).toEqual([]); expect(errors).toEqual([]);
});
