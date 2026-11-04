const { test, expect } = require('@playwright/test');
const { fillSignIn, signOut } = require('./helpers');

const email = process.env.TRUSTFLOW_CLIENT_EMAIL;
const password = process.env.TRUSTFLOW_CLIENT_PASSWORD;

test('login form exposes required email and password inputs', async ({ page }) => {
  await page.goto('/');
  const emailInput = page.locator('input[name="email"][type="email"]');
  const passwordInput = page.locator('input[name="password"][autocomplete="current-password"]');
  await expect(emailInput).toBeVisible();
  await expect(passwordInput).toBeVisible();
  await expect(emailInput).toHaveAttribute('required', '');
  await expect(passwordInput).toHaveAttribute('required', '');
});

test('password visibility toggle changes input type without losing its value', async ({ page }) => {
  await page.goto('/');
  const passwordInput = page.locator('input[name="password"]');
  await passwordInput.fill('SamplePassword123!');
  await expect(passwordInput).toHaveAttribute('type', 'password');
  await page.getByRole('button', { name: 'Show password' }).click();
  await expect(passwordInput).toHaveAttribute('type', 'text');
  await expect(passwordInput).toHaveValue('SamplePassword123!');
  await page.getByRole('button', { name: 'Hide password' }).click();
  await expect(passwordInput).toHaveAttribute('type', 'password');
});

test('signup screen shows name, role, and a 12 character password requirement', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Create account', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible();
  await expect(page.locator('input[name="name"]')).toBeVisible();
  await expect(page.locator('select[name="role"]')).toBeVisible();
  await expect(page.locator('select[name="role"] option')).toHaveCount(2);
  await expect(page.locator('input[name="password"]')).toHaveAttribute('minlength', '12');
  await page.getByRole('button', { name: /^Sign in/ }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
});

test('invalid credentials show an error and keep the user on the sign-in screen', async ({ page }) => {
  await page.goto('/');
  await page.locator('input[name="email"]').fill('missing-user@example.test');
  await page.locator('input[name="password"]').fill('NotARealPassword123!');
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByRole('alert')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
});

test('client signs in, survives reload, and logs out', async ({ page }) => {
  test.skip(!email || !password, 'Set TRUSTFLOW_CLIENT_EMAIL and TRUSTFLOW_CLIENT_PASSWORD.');
  await fillSignIn(page, email, password);
  await page.getByRole('button', { name: /sign in/i }).click();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');

  await page.reload();
  await expect(page.getByRole('heading', { level: 1 })).toContainText('Good work starts with');
  await signOut(page);
});

