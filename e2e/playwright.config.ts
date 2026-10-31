import 'dotenv/config'
import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.BASE_URL

if (!baseURL) throw new Error('BASE_URL must be set in the environment before running Playwright.')

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: Boolean(process.env.CI),
  retries: process.env.CI ? 2 : 0,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 12_000 },
  reporter: [['list'], ['html', { outputFolder: 'playwright-report', open: 'never' }]],
  use: {
    baseURL,
    ...devices['Desktop Chrome'],
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'off',
  },
})
