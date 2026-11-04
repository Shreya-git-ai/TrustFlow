const { test, expect } = require('@playwright/test');
const { fillSignIn } = require('./helpers');

const email = process.env.TRUSTFLOW_CLIENT_EMAIL;
const password = process.env.TRUSTFLOW_CLIENT_PASSWORD;

test('client can visit the main workspace sections', async ({ page }) => {
  test.skip(!email || !password, 'Set TRUSTFLOW_CLIENT_EMAIL and TRUSTFLOW_CLIENT_PASSWORD.');
  await fillSignIn(page, email, password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');

  await page.getByRole('button', { name: 'Payments' }).click();
  await expect(page.getByRole('heading', { name: 'Payments', exact: true })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Milestone payments' })).toBeVisible();
  await page.getByRole('button', { name: 'Insights' }).click();
  await expect(page.getByRole('heading', { name: 'Insights', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Resources' }).click();
  await expect(page.getByRole('heading', { name: 'Resources', exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Overview' }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
});

test('account settings and notification preferences are available', async ({ page }) => {
  test.skip(!email || !password, 'Set TRUSTFLOW_CLIENT_EMAIL and TRUSTFLOW_CLIENT_PASSWORD.');
  await fillSignIn(page, email, password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');

  await page.getByRole('button', { name: 'Open account settings' }).click();
  await expect(page.getByRole('heading', { name: 'Account settings' })).toBeVisible();
  await expect(page.getByText('Project updates', { exact: true })).toBeVisible();
  await expect(page.getByText('Payment alerts', { exact: true })).toBeVisible();
  await expect(page.locator('input[type="checkbox"]')).toHaveCount(2);
});

test('notification centre opens and supports its empty or mark-read state', async ({ page }) => {
  test.skip(!email || !password, 'Set TRUSTFLOW_CLIENT_EMAIL and TRUSTFLOW_CLIENT_PASSWORD.');
  await fillSignIn(page, email, password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');

  await page.getByRole('button', { name: /open notifications/i }).click();
  const dialog = page.getByRole('dialog', { name: 'Notification centre' });
  await expect(dialog).toBeVisible();
  const markRead = dialog.getByRole('button', { name: 'Mark all read' });
  if (await markRead.isEnabled()) {
    await markRead.click();
    await expect(dialog.getByRole('button', { name: 'All caught up' })).toBeDisabled();
  } else {
    await expect(dialog.getByText('You’re all caught up.')).toBeVisible();
  }
});

