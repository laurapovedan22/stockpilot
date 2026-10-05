import { defineConfig, devices } from '@playwright/test';
import process from 'node:process';
export default defineConfig({
  testDir: './e2e',
  timeout: 180000,
  expect: { timeout: 20000 },
  workers: 1,
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [
    { name: 'desktop', use: { ...devices['Desktop Chrome'] } },
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' } },
  ],
  reporter: [['list'], ['html', { open: 'never' }]],
});
