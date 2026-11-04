const { expect } = require('@playwright/test');

async function fillSignIn(page, email, password) {
  await page.goto('/');
  const emailInput = page.locator('input[name="email"][type="email"]');
  const passwordInput = page.locator('input[name="password"][autocomplete="current-password"]');
  await expect(emailInput).toBeVisible();
  await expect(passwordInput).toBeVisible();
  await emailInput.fill(email);
  await passwordInput.fill(password);
  return passwordInput;
}

async function signOut(page) {
  await page.getByRole('button', { name: 'Open account menu' }).click();
  await page.getByRole('menuitem', { name: /log out/i }).click();
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible();
}

module.exports = { fillSignIn, signOut };

