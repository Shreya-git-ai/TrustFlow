const { defineConfig } = require('@playwright/test');

module.exports = defineConfig({
  testDir: '.',
  testMatch: '*.spec.js',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: 'list',
  use: {
    baseURL: process.env.TRUSTFLOW_FRONTEND_URL || 'https://trustflow-test.vercel.app/',
    headless: false,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
});

