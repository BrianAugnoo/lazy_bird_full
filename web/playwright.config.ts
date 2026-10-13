import { defineConfig } from '@playwright/test';
const production = process.env.LAZY_BIRD_PRODUCTION_QA === '1';
const baseURL = production ? 'http://127.0.0.1:4173' : 'http://127.0.0.1:5173';
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: { baseURL, viewport: { width: 1440, height: 900 }, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  webServer: { command: production ? 'npm run preview -- --host 127.0.0.1 --port 4173' : 'npm run dev -- --host 127.0.0.1 --port 5173', url: baseURL, reuseExistingServer: true },
});
