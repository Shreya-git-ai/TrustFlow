import { test, expect } from '@playwright/test'
import { apiUrl, credentials, login } from './helpers.js'

test('sign-in form requires an email and password', async ({ page }) => {
  await page.goto('/')
  const email = page.getByLabel('Email', { exact: true })
  const password = page.locator('input[type="password"]').first()
  await expect(email).toBeVisible()
  await expect(email).toHaveAttribute('required', '')
  await expect(password).toBeVisible()
  await expect(password).toHaveAttribute('required', '')
})

test('password visibility toggle preserves the entered password', async ({ page }) => {
  await page.goto('/')
  const password = page.locator('input[type="password"]').first()
  await password.fill('SamplePassword123!')
  await page.getByRole('button', { name: 'Show password' }).click()
  await expect(page.locator('input[type="text"]').first()).toHaveValue('SamplePassword123!')
  await page.getByRole('button', { name: 'Hide password' }).click()
  await expect(page.locator('input[type="password"]').first()).toHaveValue('SamplePassword123!')
})

test('account creation form exposes name, role, and password requirements', async ({ page }) => {
  await page.goto('/')
  await page.getByRole('button', { name: 'Create account', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Create your account' })).toBeVisible()
  await expect(page.locator('input[name="name"]')).toBeVisible()
  await expect(page.locator('select[name="role"] option')).toHaveCount(2)
  await expect(page.locator('input[name="password"]')).toHaveAttribute('minlength', '12')
  await page.getByRole('button', { name: 'Sign in', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
})

test('client can log in, log out, and no longer use the session', async ({ page, context }) => {
  await login(page, 'client')
  const current = await context.request.get(apiUrl('/api/auth/me'))
  expect(current.status()).toBe(200)

  await page.getByRole('button', { name: 'Open account menu' }).click()
  await page.getByRole('menuitem', { name: /Log out/ }).click()
  await expect(page.getByRole('heading', { name: 'Welcome back' })).toBeVisible()
  expect((await context.request.get(apiUrl('/api/auth/me'))).status()).toBe(401)
  expect((await context.request.get(apiUrl('/api/projects'))).status()).toBe(401)
})

test('freelancer can log in to the freelancer workspace', async ({ page, context }) => {
  await login(page, 'freelancer')
  const response = await context.request.get(apiUrl('/api/auth/me'))
  expect(response.status()).toBe(200)
  expect((await response.json()).user.role).toBe('freelancer')
})

test('invalid password is rejected without opening a session', async ({ page, context }) => {
  await page.goto('/')
  await page.getByLabel('Email', { exact: true }).fill(credentials.client.email)
  await page.locator('input[type="password"]').first().fill(`${credentials.client.password}-invalid`)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page.getByRole('alert')).toContainText(/invalid|incorrect|sign in/i)
  expect((await context.request.get(apiUrl('/api/auth/me'))).status()).toBe(401)
})
